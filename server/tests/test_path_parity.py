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
    assert rc["edge_ids"] == rp["edge_ids"], f"edge ids {od} {mode}"
    assert rc["edge_reversed"] == rp["edge_reversed"], \
        f"edge dirs {od} {mode}"
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


def test_path_parity_alternatives(cpp_eng, py_eng):
    """Corridor diversity pass: same penalty schedule → the C++ and
    Python engines must accept/reject identical alternative sets —
    count, order, geometry, dose and edge ids."""
    for od in ODS:
        for mode in MODES:
            ra = cpp_eng.alternatives(*od, mode, 2)
            rb = py_eng.alternatives(*od, mode, 2)
            assert len(ra) == len(rb), (
                f"alt count {od} {mode}: {len(ra)} vs {len(rb)}")
            for rc, rp in zip(ra, rb):
                _cmp(rc, rp, od, mode)
            # A* optimality: every alternative's real dose ≥ the
            # primary's (reported float32 vs float64 tolerance)
            if len(ra) > 1 and "dose_ug" in ra[0]:
                for r in ra[1:]:
                    assert r["dose_ug"] >= ra[0]["dose_ug"] - 1e-6


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


# --- prod-shape pricing: live field, no snapshot file ---------------------

class _LiveOnlyField:
    """The shape prod actually runs: data/field/ is docker-ignored, so
    there is no serving snapshot and no _snap_fv — F.value is the live
    krige/IDW path. The engine must still price: through the /grid raster
    (real reads), never through ~1.25M live crossings, and never unpriced."""
    _snap_fv = None

    def _serving_snapshot(self):
        return False

    def value(self, lat, lon, pollutant="pm2_5"):
        if not (28.1 <= lat <= 29.0 and 76.7 <= lon <= 78.0):
            return None
        return 90.0 + 20.0 * (lon - 77.0)

    def nearest_sample_km(self, lat, lon):
        return 1.0


def test_engine_rows_carry_priced_objective(monkeypatch):
    """Wire surface: every engine row must expose engine_dose_ug —
    the µg the A* summed over priced edges — and keep its raster
    display band intact (two surfaces, one for rank, one for show)."""
    class _SigmaField(_LiveOnlyField):
        def sigma(self, lat, lon):
            return 3.0

    from v2 import plan as v2plan
    monkeypatch.setattr(v2plan.deps, "field", lambda: _SigmaField())
    opts = v2plan._engine_options(28.6315, 77.2167, 28.5479, 77.2511,
                                  "car", None)
    assert opts
    for o in opts:
        ed = o.get("engine_dose_ug")
        assert isinstance(ed, (int, float)) and ed > 0, \
            f"engine row missing priced dose: {ed}"
        assert (o.get("dose") or {}).get("mid") is not None, \
            "display dose band dropped from the engine row"


def test_engine_prices_from_live_raster(monkeypatch):
    """Reweight on a live-only field builds a real FieldView raster and
    returns engine options — the exact condition that left prod unpriced."""
    from v2 import plan as v2plan
    monkeypatch.setattr(v2plan.deps, "field", lambda: _LiveOnlyField())
    eng = routegraph.path_engine()
    v2plan._engine_reweight(eng)
    ep = getattr(eng, "edges_priced", None)
    ep = ep() if callable(ep) else (ep or 0)
    assert ep > 0, "live-field raster left the engine unpriced"
    opts = v2plan._engine_options(28.6315, 77.2167, 28.5479, 77.2511,
                                  "car", None)
    assert opts, "engine emitted nothing on a live-only field"
    assert all(o.get("engine") == "alive_core-path" for o in opts)


def test_live_callable_reweight_is_refused(monkeypatch):
    """If the raster can't be built either, the engine degrades to no
    rows — it must NOT start a ~10-minute live-callable reweight that
    starves the whole planner."""
    class _DeadRasterField(_LiveOnlyField):
        def value(self, lat, lon, pollutant="pm2_5"):
            return None   # field serves nothing — raster will be empty

    from v2 import plan as v2plan
    monkeypatch.setattr(v2plan.deps, "field", lambda: _DeadRasterField())
    eng = routegraph.PyPathEngine(routegraph.load_blob())
    v2plan._engine_reweight(eng)
    assert eng.edges_priced == 0


def test_fresh_field_reprices_inside_ttl(monkeypatch):
    """Field refresh must invalidate engine pricing promptly: a raster
    built before the field's own epoch is stale even inside the 10-min
    TTL — the arm must re-raster + reweight, not serve the old one."""
    import time as _t

    class _RefreshingField(_LiveOnlyField):
        def __init__(self):
            self._fetched_at = _t.time()

        def sigma(self, lat, lon):
            return 3.0

    f = _RefreshingField()
    from v2 import plan as v2plan
    monkeypatch.setattr(v2plan.deps, "field", lambda: f)
    old_t, old_pack = v2plan._ENG_T, v2plan._ENG_PACK
    try:
        eng = routegraph.PyPathEngine(routegraph.load_blob())
        v2plan._ENG_T = 0.0                # force the first reprice
        v2plan._engine_reweight(eng)
        assert eng.edges_priced > 0
        t1 = v2plan._ENG_T
        assert t1 > 0
        # inside TTL: field fetches newer data → epoch advances past
        # the last reweight → the next arm MUST reprice
        f._fetched_at = _t.time() + 1.0
        v2plan._engine_reweight(eng)
        assert v2plan._ENG_T > t1, \
            "field refresh inside TTL left engine pricing stale"
    finally:
        v2plan._ENG_T, v2plan._ENG_PACK = old_t, old_pack


def test_stale_epoch_does_not_reprice(monkeypatch):
    """Same field inside TTL → no reweight (the raster is still the
    field the last solve priced against)."""
    import time as _t
    f = _LiveOnlyField()
    f._fetched_at = _t.time() - 60.0       # older than the reweight
    from v2 import plan as v2plan
    monkeypatch.setattr(v2plan.deps, "field", lambda: f)
    old_t, old_pack = v2plan._ENG_T, v2plan._ENG_PACK
    try:
        v2plan._ENG_T = _t.time()
        t0 = v2plan._ENG_T
        v2plan._engine_reweight(None)
        assert v2plan._ENG_T == t0  # untouched (early-out)
    finally:
        v2plan._ENG_T, v2plan._ENG_PACK = old_t, old_pack


def test_engine_reroute_continuations(monkeypatch):
    """Mid-trip reroute shape: engine rows re-solve least-dose FROM the
    live position — snap must land near it, never a stored origin."""
    from v2 import plan as v2plan
    monkeypatch.setattr(v2plan.deps, "field", lambda: _LiveOnlyField())
    opts = v2plan._engine_options(28.5900, 77.2300,   # mid-corridor fix
                                  28.5479, 77.2511, "car", None)
    assert opts, "no engine continuations from live position"
    for o in opts:
        snap = o.get("snap_m") or {}
        assert snap.get("from_m", 1e9) < 1200.0
        first = o["geometry"]["coordinates"][0]
        assert abs(first[0] - 77.23) < 0.02 and abs(first[1] - 28.59) < 0.02, \
            "continuation did not start at the live position"


def test_reweight_releases_the_gil(blob):
    """A C++ sweep must not freeze the interpreter: while reweight runs
    on one thread, a pure-Python counter on another keeps ticking. The
    callable-field path re-acquires per edge so use a FieldView — the
    fully-released production fast path."""
    import threading
    import time

    cpp = pytest.importorskip(
        "alive_core", reason="C++ module not built (server/core/build)")
    rows = [(28.20 + 0.01 * i, 76.80 + 0.02 * j, 120.0, 90.0, 150.0, 8.0)
            for i in range(40) for j in range(30)]
    fv = cpp.FieldView(rows)
    eng = cpp.PathEngine(blob)

    ticks = [0]
    stop = threading.Event()

    def counter():
        while not stop.is_set():
            ticks[0] += 1

    t = threading.Thread(target=counter, daemon=True)
    t.start()
    try:
        eng.reweight(fv)                   # ~1.2M-edge C++ sweep
    finally:
        stop.set()
        t.join()
    assert ticks[0] > 0, "GIL held through the reweight sweep"


def test_concurrent_reweight_queries_see_one_epoch(blob):
    """Readers racing a live reprice must get ONE epoch's table, never a
    torn mix: alternate two fields, then every query result must equal
    the precomputed epoch-A or epoch-B answer exactly — or crash."""
    import threading

    cpp = pytest.importorskip(
        "alive_core", reason="C++ module not built (server/core/build)")
    # two epochs as FieldViews — pure-C++ sweeps (callable lambdas would
    # put ~7 min of per-edge Python crossings on the test clock)
    rows_a = [(28.20 + 0.01 * i, 76.80 + 0.02 * j, 80.0, 60.0, 100.0, 6.0)
              for i in range(40) for j in range(30)]
    rows_b = [(lat, lon, 200.0, 170.0, 230.0, 14.0)
              for lat, lon, *_ in rows_a]
    fa = cpp.FieldView(rows_a)
    fb = cpp.FieldView(rows_b)
    od = ODS[0]

    eng = cpp.PathEngine(blob)
    eng.reweight(fa)
    ans_a = eng.query(*od, "car")
    eng.reweight(fb)
    ans_b = eng.query(*od, "car")
    valid = {(ans_a["distance_m"], round(ans_a["dose_ug"], 3)),
             (ans_b["distance_m"], round(ans_b["dose_ug"], 3))}

    bad = []
    done = threading.Event()

    def reader():
        while not done.is_set():
            try:
                r = eng.query(*od, "car")
                if "error" in r:
                    bad.append(("err", r["error"]))
                elif (r["distance_m"], round(r["dose_ug"], 3)) not in valid:
                    bad.append(("mixed", r["distance_m"], r["dose_ug"]))
            except Exception as e:                          # pragma: no cover
                bad.append(("raise", repr(e)))

    def writer():
        for i in range(2):
            eng.reweight(fa if i % 2 == 0 else fb)
        done.set()

    readers = [threading.Thread(target=reader, daemon=True)
               for _ in range(3)]
    for t in readers:
        t.start()
    writer()
    for t in readers:
        t.join(timeout=30.0)
    assert not any(t.is_alive() for t in readers), "query hung vs reprice"
    assert bad == [], f"torn epoch reads: {bad[:3]}"
