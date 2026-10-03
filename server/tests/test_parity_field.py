"""Parity tests — C++ alive_core.FieldView vs Python reference.

Asserts identical results over:
  - every cell center of the real snapshot in data/field/snapshots
    (exact-hit: value == cell pm25)
  - 5k uniform-random points inside the NCR bbox
  - points outside the bbox (coverage fallback -> None)
  - grid-diagonal midpoint ties (deterministic tie-break)
Tolerance convention matches test_core_parity.py: bit-exact for values
(identical doubles), since both sides read the same cell numbers.
"""
import glob
import gzip
import json
import math
import os
import random
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "core", "build"))

import alive_core_ref as ref  # noqa: E402

SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP_DIR = os.path.join(SERVER_DIR, "data", "field", "snapshots")
# snapshot grid.bbox (airindex.BBOX): lon_min, lat_min, lon_max, lat_max
BBOX = (76.75, 28.15, 77.95, 28.98)
TOL = 1e-9  # matches test_core_parity.py's convention


def _latest_snapshot() -> dict:
    files = sorted(glob.glob(os.path.join(SNAP_DIR, "**", "*.json.gz"),
                             recursive=True))
    assert files, f"no field snapshots under {SNAP_DIR}"
    with gzip.open(files[-1], "rt", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def snapshot():
    return _latest_snapshot()


@pytest.fixture(scope="module")
def rows(snapshot):
    r = ref.field_rows(snapshot)
    assert len(r) > 1000, "expected the full snapshot grid"
    return r


@pytest.fixture(scope="module")
def py_fv(rows):
    return ref.PyFieldView(rows)


@pytest.fixture(scope="module")
def cpp_fv(rows):
    cpp = pytest.importorskip(
        "alive_core", reason="C++ module not built (server/core/build)")
    return cpp.FieldView(rows)


def _points(n, pad=0.0, seed=108):
    rng = random.Random(seed)
    w, s, e, nn = BBOX
    return [(s - pad + rng.random() * (nn - s + 2 * pad),
             w - pad + rng.random() * (e - w + 2 * pad))
            for _ in range(n)]


def _assert_same_point(cpp_fv, py_fv, lat, lon):
    cv = cpp_fv.value(lat, lon)
    pv = py_fv.value(lat, lon)
    assert cv == pv, f"value mismatch at {lat},{lon}: {cv} vs {pv}"
    assert cpp_fv.sigma(lat, lon) == py_fv.sigma(lat, lon)
    cb, pb = cpp_fv.band(lat, lon), py_fv.band(lat, lon)
    assert (cb is None) == (pb is None)
    if cb is not None:
        assert tuple(cb) == tuple(pb), f"band mismatch {cb} vs {pb}"
    cn, pn = cpp_fv.nearest_cell(lat, lon), py_fv.nearest_cell(lat, lon)
    assert (cn is None) == (pn is None)
    if cn is not None:
        assert cn["lat"] == pn["lat"] and cn["lon"] == pn["lon"]
        assert abs(cn["dist_km"] - pn["dist_km"]) < TOL


def test_cell_centers_exact(cpp_fv, py_fv, rows):
    """Every real cell center resolves to itself — exact pm25."""
    for lat, lon, pm, lo, hi, sg in rows:
        assert cpp_fv.value(lat, lon) == py_fv.value(lat, lon) == pm
        assert cpp_fv.band(lat, lon) == (lo, pm, hi)
        assert cpp_fv.sigma(lat, lon) == sg


def test_random_points_inside(cpp_fv, py_fv):
    for lat, lon in _points(5000):
        _assert_same_point(cpp_fv, py_fv, lat, lon)


def test_points_outside_coverage(cpp_fv, py_fv):
    """Beyond coverage_km of every cell -> None on both sides."""
    far = [(27.0, 77.0), (29.5, 77.5), (28.6, 76.0), (28.6, 79.0),
           (0.0, 0.0), (90.0, 77.2)]
    for lat, lon in far:
        assert cpp_fv.value(lat, lon) is None
        assert py_fv.value(lat, lon) is None
        assert cpp_fv.band(lat, lon) is None
        assert cpp_fv.sigma(lat, lon) is None
    # fringe band just outside the bbox: some hit, some miss — both agree
    for lat, lon in _points(2000, pad=0.10, seed=7):
        _assert_same_point(cpp_fv, py_fv, lat, lon)


def test_grid_diagonal_tie(cpp_fv, py_fv, rows):
    """Query exactly between four cell centers — deterministic tie-break."""
    lats = sorted({r[0] for r in rows})
    lons = sorted({r[1] for r in rows})
    # exact midpoint is representable when the spacing is a multiple of a
    # binary fraction — pick a few midpoints and let parity itself decide
    n = 0
    for i in range(0, len(lats) - 1, 13):
        for j in range(0, len(lons) - 1, 17):
            lat = (lats[i] + lats[i + 1]) / 2
            lon = (lons[j] + lons[j + 1]) / 2
            cn = cpp_fv.nearest_cell(lat, lon)
            pn = py_fv.nearest_cell(lat, lon)
            assert (cn is None) == (pn is None)
            if cn is not None:
                assert cn["lat"] == pn["lat"] and cn["lon"] == pn["lon"]
            n += 1
    assert n > 50


def test_fallback_when_cpp_absent(rows, monkeypatch):
    monkeypatch.setattr(ref, "HAVE_CPP", False)
    fv = ref.get_field_view(rows)
    assert isinstance(fv, ref.PyFieldView)
    assert fv.value(rows[0][0], rows[0][1]) == rows[0][2]


def test_factory_prefers_cpp(rows):
    if not ref.HAVE_CPP:
        pytest.skip("alive_core not built")
    import alive_core
    fv = ref.get_field_view(rows)
    assert isinstance(fv, alive_core.FieldView)
    assert len(fv) == len(rows)


def test_empty_field(cpp_fv):
    import alive_core
    fv = alive_core.FieldView([])
    assert fv.value(28.6, 77.2) is None
    assert fv.band(28.6, 77.2) is None
    assert len(fv) == 0
