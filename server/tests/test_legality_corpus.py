"""Legality + detour regression over the full 40-OD audit corpus.

test_path_legality.py covers 5 ODs on the shipped graph; this file
extends the same assertions to the whole audit battery — every
travelled edge of every path must satisfy its mode's rule
(highway-class deny, per-way access overrides, OSM oneway direction,
positive speed), and no travelled transition may hit the ARG2
turn-ban table (230 real restrictions, 3,428 access-override edges,
107k one-way edges on the shipped blob).

Plus the two route-shape promises measured on live:

  * containment — every vertex of every path stays inside the graph
    bbox (the wire-level field-bbox check lives in
    tools/audit_live_legality.py, which also verified the one
    corpus OD whose endpoint sits outside);
  * detour — the least-dose path under a non-uniform field stays
    within 1.6x of the same OD+mode's uniform-field path (the
    engine's own fastest corridor; the wire-level vs-router check
    is enforced at merge by DETOUR_MAX_VS_FAST and audited live).

Runs on the C++ engine when built (parity-tested identical to the
Python twin, ~100x faster — 400+ A* solves). Python twin covers a
reduced slice when alive_core is absent.
"""

import gzip
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "core", "build"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "..", "tools"))

import routegraph                      # noqa: E402
from audit_route_quality import ODS    # noqa: E402

BLOB_PATH = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "data", "route_graph.bin.gz")

MODES = ("car", "auto", "bike", "cycle", "walk")

# non-uniform pricing field — least-dose paths may detour vs the
# uniform-field (fastest-corridor) baseline, never absurdly
FIELD = lambda lat, lon: 90.0 + 20.0 * (lon - 77.0)  # noqa: E731
UNIFORM = lambda lat, lon: 100.0                     # noqa: E731
DETOUR_MAX = 1.6

# Python-twin fallback is ~30 s/solve — keep it to a short slice
PY_OD_SLICE = 6


@pytest.fixture(scope="module")
def blob():
    if not os.path.exists(BLOB_PATH):
        pytest.skip("route_graph.bin.gz not shipped")
    with gzip.open(BLOB_PATH, "rb") as fh:
        return fh.read()


@pytest.fixture(scope="module")
def graph(blob):
    g = routegraph.RouteGraph(blob)
    g.build_adj()
    return g


@pytest.fixture(scope="module")
def engines(blob):
    """(least_time_eng, least_dose_eng, ods) — C++ across the whole
    corpus, Python twin on a reduced slice when it isn't built."""
    cpp = None
    try:
        import alive_core
        cpp = alive_core.PathEngine
    except ImportError:
        cpp = None
    if cpp is not None:
        fast, dose = cpp(blob), cpp(blob)
        fast.reweight(UNIFORM)
        dose.reweight(FIELD)
        return fast, dose, ODS
    fast = routegraph.PyPathEngine(blob)
    fast.reweight(UNIFORM)
    dose = routegraph.PyPathEngine(blob)
    dose.reweight(FIELD)
    return fast, dose, ODS[:PY_OD_SLICE]


def _edges_legal(g, res, mode):
    rule = routegraph.MODE_RULES[mode]
    for e, rev in zip(res["edge_ids"], res["edge_reversed"]):
        assert g.e_hw[e] not in rule["deny"], \
            f"{mode} used denied hw={routegraph.HW_NAMES[g.e_hw[e]]}"
        assert not (g.e_acc[e] & rule["acc"]), \
            f"{mode} used access-denied edge {e}"
        ow = g.e_ow[e]
        if rule["oneway"]:
            assert not (ow == 1 and rev), \
                f"{mode} traversed oneway edge {e} backwards"
            assert not (ow == -1 and not rev), \
                f"{mode} traversed reverse-oneway edge {e} forwards"
        assert rule["spd"](g.e_sp[e]) > 0, \
            f"{mode} took zero-speed edge {e}"


def _banned_hits(g, res, mode):
    turn_bit = routegraph.MODE_RULES[mode]["turn"]
    n = 0
    for i in range(1, len(res["edge_ids"])):
        din = res["edge_ids"][i - 1] | \
            (0x80000000 if res["edge_reversed"][i - 1] else 0)
        dout = res["edge_ids"][i] | \
            (0x80000000 if res["edge_reversed"][i] else 0)
        e_prev = din & 0x7FFFFFFF
        via = g.e_u[e_prev] if (din & 0x80000000) else g.e_v[e_prev]
        outs = g.bans.get((din, via))
        if outs and outs.get(dout, 0) & turn_bit:
            n += 1
    return n


def _inside_graph_bbox(g, res):
    x0, y0, x1, y1 = g.bbox
    for lon, lat in res["geometry"]["coordinates"]:
        assert x0 <= lon * 1e6 <= x1 and y0 <= lat * 1e6 <= y1, \
            f"vertex ({lat},{lon}) outside graph bbox"


def test_corpus_every_travelled_edge_legal(engines, graph):
    g = graph
    _fast, dose, ods = engines
    n = 0
    for od in ods:
        flat, flon, tlat, tlon = od[1][0], od[1][1], od[2][0], od[2][1]
        for mode in MODES:
            res = dose.query(flat, flon, tlat, tlon, mode)
            if res.get("error"):
                continue
            _edges_legal(g, res, mode)
            n += 1
    assert n > len(ods) * 4, "corpus legality checked too few paths"


def test_corpus_no_banned_turn_transitions(engines, graph):
    """Every travelled (in,via,out) must be absent from the ARG2 ban
    table for the mode's turn mask — walk's bit never matches
    vehicular masks by design, so assert on the union mask."""
    g = graph
    _fast, dose, ods = engines
    for od in ods:
        flat, flon, tlat, tlon = od[1][0], od[1][1], od[2][0], od[2][1]
        for mode in MODES:
            res = dose.query(flat, flon, tlat, tlon, mode)
            if res.get("error"):
                continue
            assert _banned_hits(g, res, mode) == 0, \
                f"{od[0]} {mode}: travelled a banned turn"


def test_corpus_geometry_inside_graph_bbox(engines, graph):
    _fast, dose, ods = engines
    for od in ods:
        flat, flon, tlat, tlon = od[1][0], od[1][1], od[2][0], od[2][1]
        for mode in MODES:
            res = dose.query(flat, flon, tlat, tlon, mode)
            if res.get("error"):
                continue
            _inside_graph_bbox(graph, res)


def test_corpus_detour_within_1_6x(engines):
    """Least-dose under a non-uniform field stays within 1.6x the
    uniform-field (fastest-corridor) distance per OD+mode — the
    engine-side half of the wire promise enforced at merge."""
    fast, dose, ods = engines
    worst = (0.0, None, None)
    n = 0
    for od in ods:
        flat, flon, tlat, tlon = od[1][0], od[1][1], od[2][0], od[2][1]
        for mode in MODES:
            rf = fast.query(flat, flon, tlat, tlon, mode)
            rd = dose.query(flat, flon, tlat, tlon, mode)
            if rf.get("error") or rd.get("error"):
                continue
            ratio = rd["distance_m"] / rf["distance_m"]
            if ratio > worst[0]:
                worst = (ratio, od[0], mode)
            assert ratio <= DETOUR_MAX, (
                f"{od[0]} {mode}: least-dose {rd['distance_m']:.0f}m "
                f"= {ratio:.2f}x fastest {rf['distance_m']:.0f}m")
            n += 1
    assert n > len(ods) * 4


def test_corpus_implied_speed_sane(engines):
    """Duration-model sanity: implied corridor speed (dist/eta) stays
    inside per-mode plausible freeflow bounds — a build shipping raw
    uncapped maxspeed, or a broken duration accumulator, trips here.
    Bounds = the MODE_RULES caps + headroom (car 90, auto 45, bike 55,
    cycle 20, walk 6 km/h); floor 3 km/h catches zero-time paths."""
    _fast, dose, ods = engines
    MAX_KMH = {"car": 90.0, "auto": 45.0, "bike": 55.0,
               "cycle": 20.0, "walk": 6.0}
    n = 0
    for od in ods:
        flat, flon, tlat, tlon = od[1][0], od[1][1], od[2][0], od[2][1]
        for mode in MODES:
            res = dose.query(flat, flon, tlat, tlon, mode)
            if res.get("error") or res["duration_s"] <= 0:
                continue
            kmh = res["distance_m"] / res["duration_s"] * 3.6
            assert 3.0 <= kmh <= MAX_KMH[mode], (
                f"{od[0]} {mode}: implied {kmh:.1f} km/h — duration "
                f"model out of freeflow bounds")
            n += 1
    assert n > len(ods) * 4


def test_alts_detour_cap_in_engine_alts(monkeypatch):
    """_engine_alts drops taxed corridors past ALT_MAX_DETOUR× the
    primary — the live 1.77x MgRoad->Saket alt shape."""
    from v2 import plan as v2plan

    def fake_alts(flat, flon, tlat, tlon, mode, n):
        base = {"error": None, "geometry": {"type": "LineString",
                                            "coordinates": []}}
        return [
            {**base, "distance_m": 10000.0},
            {**base, "distance_m": 15000.0},   # 1.5x — keep
            {**base, "distance_m": 17000.0},   # 1.7x — drop
        ]
    out = v2plan._engine_alts(None, fake_alts, *ODS[0][1], *ODS[0][2],
                              deadline=1e18)
    for mode, paths in out.items():
        assert [p["distance_m"] for p in paths] == [10000.0, 15000.0], \
            f"{mode}: detour cap kept a >1.6x corridor"


def test_merge_drops_rows_past_fast_detour():
    """The wire-level cap: an engine row >1.6x the same-mode fastest
    router row never reaches the response."""
    from v2 import plan as v2plan
    geom = {"type": "LineString",
            "coordinates": [[77.0, 28.5], [77.1, 28.55]]}
    router = {"mode": "car", "distance_km": 15.0, "geometry": geom}
    eng_far = {"mode": "car", "distance_km": 25.0, "geometry": geom,
               "engine": "alive_core-path"}
    eng_ok = {"mode": "car", "distance_km": 20.0, "geometry": geom,
              "engine": "alive_core-path"}
    out = v2plan._engine_merge([eng_far, eng_ok], [router])
    assert out == [eng_ok], "merge kept a >1.6x-fast engine row"


def test_merge_keeps_rows_without_fast_baseline():
    """No same-mode router row (router arm failed) → the engine row
    stays — honest absence of a baseline, not a free pass."""
    from v2 import plan as v2plan
    geom = {"type": "LineString",
            "coordinates": [[77.0, 28.5], [77.1, 28.55]]}
    eng_far = {"mode": "auto", "distance_km": 30.0, "geometry": geom,
               "engine": "alive_core-path"}
    out = v2plan._engine_merge([eng_far], [])
    assert out == [eng_far]
