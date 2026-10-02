#!/usr/bin/env python3
"""Make a Cloud Optimized GeoTIFF of every frozen WorldPop raster.

data.worldpop.org does not honour Range requests, and the published GeoTIFFs
are striped rather than tiled, so a reader that wants one city has to fetch a
whole country. The COG under data/cog/ is the same raster tiled at 512, with
overviews, so that /vsicurl/ and other range readers can take a window.

The creation options are those recorded with each file in
scripts/REFERENCE.json: DEFLATE with a predictor, 512 blocks, overviews made
automatically, and for the degree of urbanisation, whose values are class
codes, nearest-neighbour overviews so that no overview shows a code the data
does not have. Every value at full resolution is compared with the original
before the COG is kept.

    uv run python scripts/03_export_cog.py
"""

import os
import sys

# Anaconda's GDAL_DRIVER_PATH and PROJ_DATA point rasterio's own GDAL at the
# wrong plugins and the wrong PROJ database: nodata reads as None and EPSG
# codes fail. They are dropped before rasterio is imported.
for _var in ("GDAL_DRIVER_PATH", "GDAL_DATA", "PROJ_DATA", "PROJ_LIB"):
    os.environ.pop(_var, None)

import json  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import rasterio  # noqa: E402
import rasterio.shutil  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "cog"
REFERENCE = ROOT / "scripts" / "REFERENCE.json"


def creation_options(gdal_translate_options: list[str]) -> dict[str, str]:
    """The -co KEY=VALUE pairs of a recorded gdal_translate command line."""
    opts = {}
    for flag, value in zip(gdal_translate_options, gdal_translate_options[1:], strict=False):
        if flag == "-co":
            k, v = value.split("=", 1)
            opts[k] = v
    return opts


def to_cog(src: Path, dst: Path, gdal_translate_options: list[str]) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".part")
    rasterio.shutil.copy(src, tmp, driver="COG", **creation_options(gdal_translate_options))
    tmp.replace(dst)


def same_pixels(a: Path, b: Path) -> bool:
    """Every value at full resolution equal, block by block, and the same nodata."""
    with rasterio.open(a) as x, rasterio.open(b) as y:
        if (x.width, x.height, x.count, x.dtypes, x.nodata) != (
            y.width,
            y.height,
            y.count,
            y.dtypes,
            y.nodata,
        ):
            return False
        step = 2048
        for row in range(0, x.height, step):
            w = rasterio.windows.Window(0, row, x.width, min(step, x.height - row))
            if not np.array_equal(x.read(window=w), y.read(window=w), equal_nan=True):
                return False
    return True


def stats(path: Path) -> tuple[int, float]:
    """(valid pixels, their sum), the two figures recorded for every file."""
    valid, total = 0, 0.0
    with rasterio.open(path) as r:
        for _, w in r.block_windows(1):
            a = r.read(1, window=w)
            ok = a != r.nodata if r.nodata is not None else np.ones(a.shape, bool)
            ok &= ~np.isnan(a) if a.dtype.kind == "f" else True
            valid += int(ok.sum())
            total += float(a[ok].sum(dtype=np.float64))
    return valid, total


def main() -> int:
    ref = json.loads(REFERENCE.read_text())
    done = 0
    for rel, r in ref.items():
        src, dst = RAW / rel, OUT / rel
        if not src.exists():
            raise SystemExit(f"missing {rel}; run scripts/01 first")
        if not dst.exists():
            to_cog(src, dst, r["gdal_translate_options"])
        if not same_pixels(src, dst):
            dst.unlink()
            raise SystemExit(f"{rel}: the COG's values differ from the original")
        done += 1
        if done % 100 == 0:
            print(f"{done}/{len(ref)}", flush=True)
    print(f"{done} COGs, every value equal to its original")
    return 0


if __name__ == "__main__":
    sys.exit(main())
