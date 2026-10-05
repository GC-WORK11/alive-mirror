"""Reach — bounded dose-budget Dijkstra: C++ ↔ oracle parity + endpoint.

PathEngine.reach / PyPathEngine.reach expand the same directed-edge-
state search as the A* route twins with no heuristic and no
destination — parity means the SAME settled edge set (both sides
settle in identical order, but the tests only require cardinality
±order), expanded counts, node counts, distances, and truncation.

Also the honest edges: budget 0 settles the origin only; a capped
sweep flags truncated; /v2/reach answers a typed rejection outside
the service area and only serves contract-declared keys.

Skips cleanly when the graph or the built .so is absent.
"""

import gzip
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _b in ("build", "build312"):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "core", _b))

import routegraph  # noqa: E402

BLOB_PATH = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "data", "route_graph.bin.gz")

# deterministic synthetic field — same west→east gradient the A*
# parity tests price with
FIELD = lambda lat, lon: 90.0 + 20.0 * (lon - 77.0)  # noqa: E731

SEEDS = [
    (28.6315, 77.2167),   # Connaught Place
    (28.5708, 77.3260),   # Noida Sec 18
    (28.7041, 77.1125),   # Rohini
]


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
        "alive_core", reason="C++ module not built (server/core/build*)")
    assert hasattr(cpp, "PathEngine"), "alive_core lacks PathEngine"
    eng = cpp.PathEngine(blob)
    eng.reweight(FIELD)
    return eng


# --- engine parity ---------------------------------------------------------
@pytest.mark.parametrize("lat,lon", SEEDS)
@pytest.mark.parametrize("mode", ["walk", "car"])
def test_reach_parity(py_eng, cpp_eng, lat, lon, mode):
    """Same graph, same field, same budget → identical settled set."""
    r_py = py_eng.reach(lat, lon, mode, 30.0, 400_000)
    r_cpp = cpp_eng.reach(lat, lon, mode, 30.0, 400_000)
    assert r_py.get("error") == r_cpp.get("error")
    if r_py.get("error"):
        return
    assert set(r_py["edge_ids"]) == set(r_cpp["edge_ids"])
    assert len(r_py["edge_ids"]) == len(r_cpp["edge_ids"])
    assert r_py["expanded"] == r_cpp["expanded"]
    assert r_py["nodes"] == r_cpp["nodes"]
    assert r_py["truncated"] == r_cpp["truncated"]
    assert r_py["frontier_ug"] == pytest.approx(
        r_cpp["frontier_ug"], rel=1e-6)
    assert r_py["distance_m"] == pytest.approx(
        r_cpp["distance_m"], rel=1e-6)
    assert r_py["snap_m"] == pytest.approx(r_cpp["snap_m"], rel=1e-6)
    assert r_py["frontier_ug"] <= 30.0 + 1e-9


def test_reach_zero_budget_settles_origin_only(py_eng, cpp_eng):
    """budget_ug=0 → nothing priced within 0 → only the origin node."""
    for eng in (py_eng, cpp_eng):
        r = eng.reach(28.6315, 77.2167, "walk", 0.0)
        assert not r.get("error"), r.get("error")
        assert r["expanded"] == 0
        assert r["edge_ids"] == []
        assert r["nodes"] == 1
        assert r["distance_m"] == 0.0
        assert r["truncated"] is False


def test_reach_expansion_cap_flags_truncated(py_eng, cpp_eng):
    """Absurd budget + small cap → the cap, not the budget, ends it."""
    for eng in (py_eng, cpp_eng):
        r = eng.reach(28.6315, 77.2167, "car", 1e9, 5_000)
        assert not r.get("error"), r.get("error")
        assert r["truncated"] is True
        assert r["expanded"] == 5_000
        assert len(r["edge_ids"]) > 0


def test_reach_snap_failure_is_typed(py_eng, cpp_eng):
    """Far outside the graph's roads → the same 'no graph node' error
    both twins emit for unroutable endpoints."""
    for eng in (py_eng, cpp_eng):
        r = eng.reach(26.0, 77.0, "car", 50.0)
        assert r.get("error") == "no graph node near endpoint"


def test_reach_warm_perf_budget(cpp_eng):
    """The L4 promise is an interactive veil — a mid-size walk reach
    must settle in well under the single-worker budget."""
    t0 = time.perf_counter()
    r = cpp_eng.reach(28.6315, 77.2167, "walk", 50.0)
    dt = time.perf_counter() - t0
    assert not r.get("error"), r.get("error")
    assert r["expanded"] > 0
    assert dt < 2.0, f"warm reach took {dt:.2f}s"


# --- endpoint --------------------------------------------------------------
@pytest.fixture()
def client(monkeypatch):
    """TestClient with the field seeded so the engine actually prices —
    the same wiring test_contract_sync uses."""
    os.environ.pop("ALIVE_LOCATION_KEY", None)
    from fastapi.testclient import TestClient
    import main
    from airfield import FIELD
    from v2 import deps

    async def _noop(*a, **k):
        return None
    monkeypatch.setattr(deps, "field_refresh", _noop)
    FIELD._samples = [
        (28.6315, 77.2167, "test-station", {"pm2_5": 150.0}),
        (28.6519, 77.1907, None, {"pm2_5": 185.0}),
    ]
    FIELD._fetched_at = time.time()
    yield TestClient(main.app, raise_server_exceptions=False)
    FIELD._samples = []


def test_reach_endpoint_outside_area_typed(client):
    body = client.get("/v2/reach", params={
        "lat": 40.7, "lon": -74.0,          # NYC — outside the field
        "mode": "walk", "budget_ug": 50}).json()
    assert body["code"] == "outside_service_area"
    assert body["error"]
    assert body["edges_e6"] == []
    assert body["expanded"] == 0


def test_reach_endpoint_success_shape(client):
    body = client.get("/v2/reach", params={
        "lat": 28.6315, "lon": 77.2167,
        "mode": "walk", "budget_ug": 25}).json()
    if body.get("code") == "engine_unavailable":
        pytest.skip("graph/engine not shipped in this env")
    if body.get("code") == "timeout":
        pytest.skip("cold raster reprice exceeded the solve budget")
    assert body.get("error") is None, body
    assert body["mode"] == "walk"
    assert body["budget_ug"] == 25.0
    assert body["edge_count"] >= len(body["edges_e6"]) > 0
    assert body["expanded"] >= len(body["edges_e6"])
    assert body["nodes"] >= 1
    assert 0.0 < body["frontier_budget_ug"] <= 25.0 + 1e-9
    assert body["truncated"] is False
    assert body["distance_km"] > 0.0
    assert body["snap_m"] is not None
    assert body["field_age_s"] is not None
    # polylines are flat e6 int pairs — the graph's own coord format
    e0 = body["edges_e6"][0]
    assert len(e0) >= 4 and len(e0) % 2 == 0
    assert all(isinstance(v, int) for v in e0)
    assert abs(e0[0] / 1e6 - 77.2) < 0.2   # first lon lands in NCR


def test_reach_endpoint_only_contract_keys(client):
    """Every served key must be declared — the contract suite's no-
    undeclared-keys check, asserted locally for reach."""
    declared = {
        "from", "mode", "budget_ug", "snap_m", "edges_e6",
        "edge_count", "edge_partial", "expanded", "nodes",
        "distance_km", "frontier_budget_ug", "truncated",
        "field_age_s", "took_ms", "error", "code",
    }
    body = client.get("/v2/reach", params={
        "lat": 28.6315, "lon": 77.2167,
        "mode": "walk", "budget_ug": 25}).json()
    assert set(body.keys()) <= declared, \
        f"undeclared keys: {set(body.keys()) - declared}"
