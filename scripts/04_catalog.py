#!/usr/bin/env python3
"""Write parquet/files.parquet, one row per raster, for the Hub viewer and for search.

Rasters are not tables, so the Hub cannot show them. This table can: what
each file is (product, year, resolution, sex and age band, urbanisation
level), where its original and its COG are in this repository, their sizes
and sha256, and the count and sum of its valid pixels. The sum of a
population raster is the number of people it places, so the table answers
"how many people of 80 or over in 2030" without opening a raster.
"""

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFERENCE = ROOT / "scripts" / "REFERENCE.json"
OUT = ROOT / "data" / "parquet" / "files.parquet"


def describe(r: dict) -> dict:
    """sex, age_from and level from a WorldPop asset name."""
    m = re.fullmatch(r"(female|male|total)_(\d+)_\d{4}", r["asset"])
    if m:
        return {"sex": m.group(1), "age_from": int(m.group(2)), "level": None}
    m = re.fullmatch(r"grid_l(\d)", r["asset"])
    if m:
        return {"sex": None, "age_from": None, "level": int(m.group(1))}
    return {"sex": None, "age_from": None, "level": None}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def rows(ref: dict) -> list[dict]:
    out = []
    for rel, r in ref.items():
        cog = ROOT / "data" / "cog" / rel
        out.append({
            "project": r["project"], "year": r["year"], "resolution": r["resolution"],
            **describe(r),
            "raw_path": f"raw/{rel}", "raw_bytes": r["source_bytes"], "raw_sha256": r["source_sha256"],
            "cog_path": f"cog/{rel}", "cog_bytes": cog.stat().st_size, "cog_sha256": sha256(cog),
            "width": r["width"], "height": r["height"], "data_type": r["data_type"], "nodata": r["nodata"],
            "valid_pixels": r["valid_pixels"], "sum": r["sum"],
            "source_url": r["source_url"], "source_last_modified": r["source_last_modified"],
            "release": r["release"], "version": r["version"], "doi": r["doi"],
        })  # fmt: skip
    return out


def main() -> int:
    import duckdb

    data = rows(json.loads(REFERENCE.read_text()))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json")
    tmp.write_text(json.dumps(data))
    con = duckdb.connect()
    con.execute(
        f"copy (select * from read_json('{tmp}', format = 'array') "
        "order by project, resolution, year, sex, age_from, level) "
        f"to '{OUT}' (format parquet, compression zstd, write_bloom_filter false)"
    )
    tmp.unlink()
    n = con.sql(f"select count(*) from '{OUT}'").fetchone()[0]
    print(f"{OUT.name}: {n} rows")
    return 0 if n == len(data) else 1


if __name__ == "__main__":
    sys.exit(main())
