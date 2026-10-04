"""Parity tests — C++ alive_core.PathEngine vs Python PyPathEngine.

Same packed ARG1 graph, same synthetic field: identical paths, doses
(1e-6 rel — C++ stores per-edge concentration as float32), geometry,
and error strings. Plus the honest error cases (far snap, no path).

Runs under the system Python that has the built .so; skips cleanly
when alive_core or the shipped graph is absent.
"""

import gzip
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "core", "build"))

import routegraph  # noqa: E402

BLOB_PATH = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "data", "route_graph.bin.gz")

# deterministic synthetic field — a west→east gradient
FIELD = lambda lat, lon: 90.0 + 20.0 * (lon - 77.0)  # noqa: E731

# OD pairs: (olat, olon, dlat, dlon) across Delhi + one NCR edge trip
ODS = [
    (28.6315, 77.2167, 28.5479, 77.2511),   # CP → Nehru Place
    (28.6139, 77.2090, 28.7041, 77.1125),   # CP → Rohini
    (28.4595, 77.0266, 28.6315, 77.2167),   # Gurugram → CP
    (28.5708, 77.3260, 28.6139, 77.2090),   # Noida Sec 18 → CP
]
MODES = ("car", "auto", "bike", "cycle", "walk")


@pytest.fixture(scope="module")
def blob():
    if not os.path.exists(BLOB_PATH):
        pytest.skip("route_graph.bin.gz not shipped")
    with gzip.open(BLOB_PATH, "rb") as fh:
        return fh.read()


@pytest.fixture(scope="module")
def py_eng(blob):
    eng = routegraph.PyPathEngine(blob)
    eng.reweight(FIELD)
    return eng


@pytest.fixture(scope="module")
def cpp_eng(blob):
    cpp = pytest.importorskip(
        "alive_core", reason="C++ module not built (server/core/build)")
    assert hasattr(cpp, "PathEngine"), "alive_core lacks PathEngine"
    eng = cpp.PathEngine(blob)
    eng.reweight(FIELD)
    return eng


def _cmp(rc, rp, od, mode):
    assert rc.get("error") == rp.get("error"), (
        f"error mismatch {od} {mode}: {rc.get('error')} vs {rp.get('error')}")
    if "error" in rp:
        return
    assert rc["edges"] == rp["edges"], f"edge count {od} {mode}"
    assert rc["geometry"]["coordinates"] == rp["geometry"]["coordinates"], \
        f"geometry {od} {mode}"
    assert abs(rc["distance_m"] - rp["distance_m"]) < 1e-6, \
        f"distance {od} {mode}: {rc['distance_m']} vs {rp['distance_m']}"
    assert abs(rc["duration_s"] - rp["duration_s"]) < 1e-6, \
        f"duration {od} {mode}"
    assert abs(rc["dose_ug"] - rp["dose_ug"]) <= max(
        1e-6, 1e-6 * abs(rp["dose_ug"])), \
        f"dose {od} {mode}: {rc['dose_ug']} vs {rp['dose_ug']}"
    assert rc["names"] == rp["names"], f"names {od} {mode}"
    # snap nodes may resolve to sub-mm-apart twins on a float tie — the
    # picked node and its distance must agree to 1 mm, not bit-exactly
    assert abs(rc["snap"]["from_m"] - rp["snap"]["from_m"]) < 1e-3, \
        f"snap from {od} {mode}"
    assert abs(rc["snap"]["to_m"] - rp["snap"]["to_m"]) < 1e-3, \
        f"snap to {od} {mode}"


def test_path_parity_all_modes(cpp_eng, py_eng):
    for od in ODS:
        for mode in MODES:
            rc = cpp_eng.query(*od, mode)
            rp = py_eng.query(*od, mode)
            _cmp(rc, rp, od, mode)


def test_path_parity_far_endpoint(cpp_eng, py_eng):
    """An OD whose endpoints sit beyond the snap radius — both engines
    must emit the same honest error."""
    for mode in ("car", "walk"):
        rc = cpp_eng.query(28.6139, 77.2090, 31.0, 77.0, mode)  # → Punjab
        rp = py_eng.query(28.6139, 77.2090, 31.0, 77.0, mode)
        assert rc.get("error") == rp.get("error") == \
            "no graph node near endpoint"


def test_path_parity_unweighted(blob):
    """Before reweight: edges unpriced — C++ falls back to field_mean=0,
    same as the Python oracle."""
    cpp = pytest.importorskip("alive_core")
    ce = cpp.PathEngine(blob)
    py = routegraph.PyPathEngine(blob)
    rc = ce.query(*ODS[0], "car")
    rp = py.query(*ODS[0], "car")
    assert rc.get("error") == rp.get("error")
    if "error" not in rp:
        assert rc["geometry"]["coordinates"] == \
            rp["geometry"]["coordinates"]
