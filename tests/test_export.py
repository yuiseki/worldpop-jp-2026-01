import importlib.util
from pathlib import Path

import numpy as np
import pytest

_spec = importlib.util.spec_from_file_location(
    "export", Path(__file__).parents[1] / "scripts" / "03_export_cog.py"
)
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)

import rasterio  # noqa: E402  (after the module has cleaned the GDAL environment)
from rasterio.transform import from_origin  # noqa: E402


def _tif(path: Path, data: np.ndarray, nodata) -> Path:
    with rasterio.open(
        path, "w", driver="GTiff", width=data.shape[1], height=data.shape[0], count=1,
        dtype=data.dtype, nodata=nodata, crs="EPSG:4326",
        transform=from_origin(139.0, 36.0, 0.01, 0.01),
    ) as dst:  # fmt: skip
        dst.write(data, 1)
    return path


@pytest.mark.parametrize(
    ("options", "creation"),
    [
        (["-of", "COG", "-co", "COMPRESS=DEFLATE", "-co", "BLOCKSIZE=512"],
         {"COMPRESS": "DEFLATE", "BLOCKSIZE": "512"}),
        (["-of", "COG", "-co", "RESAMPLING=NEAREST"], {"RESAMPLING": "NEAREST"}),
    ],
)  # fmt: skip
def test_creation_options_from_the_recorded_gdal_translate_options(options, creation):
    assert m.creation_options(options) == creation


def test_cog_keeps_every_value_and_the_nodata(tmp_path):
    rng = np.random.default_rng(0)
    data = rng.random((700, 900), dtype=np.float32) * 100
    data[:50, :] = -99999.0
    src = _tif(tmp_path / "a.tif", data, -99999.0)
    cog = tmp_path / "a.cog.tif"
    m.to_cog(
        src,
        cog,
        ["-of", "COG", "-co", "COMPRESS=DEFLATE", "-co", "BLOCKSIZE=512", "-co", "OVERVIEWS=AUTO"],
    )
    with rasterio.open(cog) as c:
        assert c.nodata == -99999.0
        assert np.array_equal(c.read(1), data)
        assert c.overviews(1)
        assert c.tags(ns="IMAGE_STRUCTURE").get("LAYOUT") == "COG"
    assert m.same_pixels(src, cog)


def test_same_pixels_sees_one_changed_value(tmp_path):
    data = np.arange(600 * 600, dtype=np.float32).reshape(600, 600)
    a = _tif(tmp_path / "a.tif", data, None)
    data2 = data.copy()
    data2[300, 300] += 1
    b = _tif(tmp_path / "b.tif", data2, None)
    assert not m.same_pixels(a, b)


def test_stats_match_the_reference_definition(tmp_path):
    data = np.array([[1.5, -99999.0], [2.5, 3.0]], dtype=np.float32)
    src = _tif(tmp_path / "s.tif", data, -99999.0)
    valid, total = m.stats(src)
    assert valid == 3 and total == pytest.approx(7.0)


def test_catalog_describes_assets():
    spec = importlib.util.spec_from_file_location(
        "catalog", Path(__file__).parents[1] / "scripts" / "04_catalog.py"
    )
    c = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(c)
    assert c.describe({"asset": "female_80_2030"}) == {
        "sex": "female",
        "age_from": 80,
        "level": None,
    }
    assert c.describe({"asset": "grid_l2"}) == {"sex": None, "age_from": None, "level": 2}
    assert c.describe({"asset": "data"}) == {"sex": None, "age_from": None, "level": None}
