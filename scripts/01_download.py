#!/usr/bin/env python3
"""Fetch the 1,024 WorldPop GeoTIFFs for Japan and freeze exactly what arrived.

The files are R2025A v1 of three WorldPop products for Japan, 2015 to 2030:
total population at 100 m and 1 km, age and sex structures at 1 km (60
rasters a year), and the degree of urbanisation (two grids a year).
scripts/REFERENCE.json lists each one with its URL, size and sha256 as
recorded on 2026-09-28, when the latest Last-Modified among them was
2026-01-18. A file is kept only if it has those bytes; the month in the name
of this dataset rests on that, not on the server's dates.

data.worldpop.org answers Range requests with the whole file and sends about
400 KB/s per connection, so four files are fetched at a time. A file already
present with the recorded sha256 is not fetched again, and a run that stops
can be started again.

    uv run python scripts/01_download.py
    uv run python scripts/01_download.py --project Population
"""

import argparse
import concurrent.futures as cf
import hashlib
import json
import shutil
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "raw"
REFERENCE = ROOT / "scripts" / "REFERENCE.json"
UA = "worldpop-jp-2026-01/1 (+https://github.com/yuiseki/worldpop-jp-2026-01)"
LOCK = threading.Lock()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def fetch(rel: str, ref: dict, attempts: int = 5) -> tuple[str, str, float]:
    """(rel, Last-Modified, seconds) once rel holds the recorded bytes."""
    dest = OUT / rel
    if (
        dest.exists()
        and dest.stat().st_size == ref["source_bytes"]
        and sha256(dest) == ref["source_sha256"]
    ):
        return rel, "", 0.0
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(ref["source_url"], headers={"User-Agent": UA})
    for attempt in range(attempts):
        t = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=600) as r, open(tmp, "wb") as f:
                shutil.copyfileobj(r, f, 1 << 20)
                lm = r.headers.get("Last-Modified", "")
        except OSError as e:
            with LOCK:
                print(f"retry {rel}: {e}", flush=True)
            time.sleep(10 * (attempt + 1))
            continue
        took = time.monotonic() - t
        if tmp.stat().st_size == ref["source_bytes"] and sha256(tmp) == ref["source_sha256"]:
            tmp.replace(dest)
            return rel, lm, took
        with LOCK:
            print(f"retry {rel}: {tmp.stat().st_size} bytes, not the recorded file", flush=True)
    tmp.unlink(missing_ok=True)
    raise SystemExit(f"{rel}: not the recorded file after {attempts} attempts")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", help="only this project, e.g. Population")
    ap.add_argument("--jobs", type=int, default=4)
    a = ap.parse_args()

    ref = json.loads(REFERENCE.read_text())
    todo = {k: v for k, v in ref.items() if not a.project or v["project"] == a.project}
    print(f"{len(todo)} files, {sum(v['source_bytes'] for v in todo.values()):,} bytes", flush=True)
    seen: dict[str, str] = {}
    done = 0
    with cf.ThreadPoolExecutor(a.jobs) as pool:
        for rel, lm, took in pool.map(lambda kv: fetch(*kv), todo.items()):
            done += 1
            seen[rel] = lm
            if took:
                mb = todo[rel]["source_bytes"] / 1e6
                print(
                    f"[{done}/{len(todo)}] {rel.rsplit('/', 1)[1]} {mb:.1f} MB in {took:.0f} s",
                    flush=True,
                )

    # Record what the server said now beside what was recorded, for every file
    # fetched in this run. A changed date with the same bytes is a re-put.
    log = OUT / "LAST_MODIFIED.json"
    old = json.loads(log.read_text()) if log.exists() else {}
    old.update({k: v for k, v in seen.items() if v})
    log.write_text(json.dumps(dict(sorted(old.items())), indent=1))
    moved = [k for k, v in old.items() if v and v != ref[k]["source_last_modified"]]
    print(
        f"done; {len(moved)} files carry a Last-Modified other than the recorded one, with the same bytes"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
