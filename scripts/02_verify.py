#!/usr/bin/env python3
"""Check that the frozen rasters are the 1,024 recorded and that each holds its people.

Every file must have the recorded size and sha256, and the count and sum of
its valid pixels must be the recorded ones: the sum of a population raster
is the number of people it places, so a raster that lost a tile would show
here even if its header were intact. The set must be complete: 16 years of
each product, 60 age and sex rasters a year, two urbanisation grids a year.
"""

import collections
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
REFERENCE = ROOT / "scripts" / "REFERENCE.json"

_spec = importlib.util.spec_from_file_location("export", ROOT / "scripts" / "03_export_cog.py")
export = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(export)

PER_YEAR = {
    ("Population", "100m"): 1,
    ("Population", "1km"): 1,
    ("Age and Sex Structures", "1km"): 60,
    ("Degree of Urbanisation", None): 2,
}
YEARS = range(2015, 2031)


def main() -> int:
    ref = json.loads(REFERENCE.read_text())
    failures = []

    def check(ok: bool, what: str) -> None:
        print(("ok    " if ok else "FAIL  ") + what)
        if not ok:
            failures.append(what)

    counts = collections.Counter((r["project"], r["resolution"], r["year"]) for r in ref.values())
    for (project, res), n in PER_YEAR.items():
        got = {y: counts[(project, res, y)] for y in YEARS}
        check(
            all(v == n for v in got.values()), f"{project} {res or ''}: {n} a year for 2015 to 2030"
        )

    bad_bytes, bad_stats = [], []
    for rel, r in ref.items():
        p = RAW / rel
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                h.update(block)
        if p.stat().st_size != r["source_bytes"] or h.hexdigest() != r["source_sha256"]:
            bad_bytes.append(rel)
            continue
        valid, total = export.stats(p)
        if valid != r["valid_pixels"] or abs(total - r["sum"]) > 1e-6 * max(1.0, abs(r["sum"])):
            bad_stats.append((rel, valid, total))
    check(not bad_bytes, f"every file is the recorded bytes ({len(bad_bytes)} are not)")
    check(
        not bad_stats, f"every file holds the recorded pixels and people ({len(bad_stats)} do not)"
    )
    for x in (bad_bytes + bad_stats)[:5]:
        print("      ", x)

    people = {
        y: sum(
            r["sum"]
            for r in ref.values()
            if r["project"] == "Population" and r["resolution"] == "100m" and r["year"] == y
        )
        for y in (2015, 2020, 2025, 2030)
    }
    print("Japan, 100 m total population:", ", ".join(f"{y} {v:,.0f}" for y, v in people.items()))

    if failures:
        print(f"\n{len(failures)} checks failed")
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
