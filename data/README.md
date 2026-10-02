---
license: cc-by-4.0
language:
- en
task_categories:
- tabular-regression
tags:
- japan
- population
- demographics
- raster
- geotiff
- cog
- worldpop
- frozen-snapshot
size_categories:
- 1K<n<10K
configs:
- config_name: files
  data_files: parquet/files.parquet
  default: true
---

# worldpop-jp-2026-01

WorldPop's gridded population of Japan, 2015 to 2030, release R2025A: how
many people live in every 100 m and every 1 km cell, by sex and five-year age
band at 1 km, and the degree of urbanisation of every cell. 1,024 rasters as
WorldPop published them, and the same rasters as Cloud Optimized GeoTIFF.

CC BY 4.0. Cite each product by its DOI (see Licence).

## Why this exists

WorldPop's server sends whole files and ignores HTTP Range requests, at about
400 KB/s a connection, and its GeoTIFFs are striped. To look at one city you
fetch the country. The COGs here are tiled at 512 with overviews, and the Hub
answers Range requests, so GDAL's `/vsicurl/` or rasterio can read a window.

The files of a release are not frozen: within R2025A v1 the population
rasters carry dates from July and August 2025 and the degree of urbanisation
from January 2026. The month in the name is the latest of them. Every file
here has the sha256 recorded for it when it was first fetched, on 2026-09-28.

## What is here

| product | resolution | files | per year | originals | COGs |
|---|---|---:|---|---:|---:|
| total population | 100 m | 16 | 1 | 1.74 GB | 2.11 GB |
| total population | 1 km | 16 | 1 | 0.04 GB | 0.04 GB |
| age and sex structures | 1 km | 960 | 60: female, male, total x 20 bands | 2.08 GB | 2.40 GB |
| degree of urbanisation | 1 km grid | 32 | 2: level 1 and level 2 | 3 MB | 4 MB |

`raw/GIS/...` holds WorldPop's files under WorldPop's own paths; `cog/GIS/...`
the COGs under the same paths. The age bands start at 0 (under 1), 1 (1 to 4),
then 5, 10, ... 85, and 90 for 90 and over.

The `files` config, `parquet/files.parquet`, lists all 1,024 with their
product, year, sex, age band and level, both paths, sizes, sha256, and the
count and sum of their valid pixels. The sum of a population raster is the
number of people it places, so the table answers questions without opening a
raster:

```sql
-- DuckDB, straight off the Hub: people of 80 and over, by year
SELECT year, round(sum("sum")) AS people
FROM 'hf://datasets/yuiseki/worldpop-jp-2026-01/parquet/files.parquet'
WHERE project = 'Age and Sex Structures' AND sex = 'total' AND age_from >= 80
GROUP BY year ORDER BY year;
-- 2015  9,807,304   ...   2030  15,422,003
```

| year | 100 m total population |
|---|---:|
| 2015 | 127,358,353 |
| 2020 | 126,574,853 |
| 2025 | 123,434,903 |
| 2030 | 119,948,756 |

These are WorldPop's estimates and projections, not the census. The sexes
and ages of a year do not add up to its total exactly: in 2020 the 60 age and
sex rasters place 126,475,186 people and the 1 km total 126,574,853, a
difference of 0.08%. They are separate models.

Reading a window of a COG over HTTP:

```python
import rasterio
from rasterio.windows import from_bounds

url = ("https://huggingface.co/datasets/yuiseki/worldpop-jp-2026-01/resolve/main/"
       "cog/GIS/Population/Global_2015_2030/R2025A/2020/JPN/v1/100m/constrained/"
       "jpn_pop_2020_CN_100m_R2025A_v1.tif")
with rasterio.open(url) as r:
    taito = r.read(1, window=from_bounds(139.76, 35.69, 139.81, 35.73, r.transform))
```

## How the COGs were made

DEFLATE with a predictor, 512 by 512 tiles, overviews made automatically. The
degree of urbanisation holds class codes, so its overviews use nearest
neighbour; averaging would show codes that do not exist. Every value at full
resolution was compared with the original and is equal. The overviews are
new and are the only thing in a COG that is not in its original.

## Reproducing it

```bash
git clone https://github.com/yuiseki/worldpop-jp-2026-01
cd worldpop-jp-2026-01
uv run python scripts/01_download.py      # 1,024 files, each against its recorded sha256
uv run python scripts/02_verify.py        # bytes, pixels and people; 16 years of each product
uv run python scripts/03_export_cog.py    # COGs, every value compared
uv run python scripts/04_catalog.py
```

The download took two hours on 2026-10-02, most of it the sixteen 100 m
rasters at 15 to 20 minutes each.

## Licence

CC BY 4.0, as WorldPop publishes these datasets. Cite each product as
WorldPop gives it; `LICENSE` beside this file has the four citations in
full:

| product | DOI |
|---|---|
| total population, 100 m | 10.5258/SOTON/WP00839 |
| total population, 1 km | 10.5258/SOTON/WP00840 |
| age and sex structures, 1 km | 10.5258/SOTON/WP00842 |
| degree of urbanisation | 10.5258/SOTON/WP00879 |

The originals under `raw/` are WorldPop's bytes. The COGs under `cog/` change
the form, not the values, and `LICENSE` says so.
