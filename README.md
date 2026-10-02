# worldpop-jp-2026-01

Dataset: https://huggingface.co/datasets/yuiseki/worldpop-jp-2026-01

WorldPop's R2025A rasters for Japan, 2015 to 2030: total population at 100 m
and 1 km, population by sex and five-year age band at 1 km, and the degree of
urbanisation. 1,024 GeoTIFFs as WorldPop published them, the same rasters as
Cloud Optimized GeoTIFF, and the code that fetches, checks and converts them.
This repository holds the code; the data is on the Hub.

## Where things are

```
scripts/REFERENCE.json        the 1,024 files: URL, size, sha256, pixel count and sum
scripts/01_download.py        every file over HTTP, four at a time, each checked against REFERENCE
scripts/02_verify.py          bytes, pixels and people of every file; 16 years of each product
scripts/03_export_cog.py      GeoTIFF -> COG with the recorded options; every value compared
scripts/04_catalog.py         parquet/files.parquet, one row per raster
src/publish.py                pushes the data and its card to the Hub
tests/                        COG options, value comparison, pixel statistics, asset names

data/README.md                the dataset card. Uploaded as-is
data/LICENSE                  CC BY 4.0 and the four citations WorldPop asks for
data/provenance.yaml          the release, the dates, the counts, and what was done
data/raw/                     generated, 3.9 GB, WorldPop's own files
data/cog/                     generated, 4.6 GB
```

## Running it

```sh
uv run python scripts/01_download.py      # an hour or more; restartable
uv run python scripts/02_verify.py
uv run python scripts/03_export_cog.py
uv run python scripts/04_catalog.py
uv run python src/publish.py              # dry run; --push to upload
uv run pytest
```

## Why the month is 2026-01

The release is R2025A version v1, but the files of a release are not frozen:
the population rasters carry Last-Modified dates in July and August 2025 and
the degree of urbanisation in January 2026. The month in the name is the
latest of them. `REFERENCE.json` holds the sha256 of every file as it was on
2026-09-28, and `01_download.py` keeps a file only if it has those bytes.

## Three traps

**The server ignores Range.** data.worldpop.org advertises `Accept-Ranges` and
sends the whole file with 200, at about 400 KB/s a connection. GDAL's
`/vsicurl/` cannot open the originals there, which is what the COGs are for.

**rasterio reads the wrong GDAL plugins under Anaconda.** `GDAL_DRIVER_PATH`
and `PROJ_DATA` from an Anaconda install make rasterio's bundled GDAL read
nodata as None and fail on EPSG codes. The scripts drop them before importing
rasterio.

**Overviews of class codes need nearest neighbour.** The degree of
urbanisation holds codes, not quantities. Averaged overviews would show codes
that do not exist, so those COGs use `RESAMPLING=NEAREST`.

## Licence

The code here is MIT. The data it fetches is CC BY 4.0, from WorldPop; cite
each product by its DOI as `data/LICENSE` lists them.
