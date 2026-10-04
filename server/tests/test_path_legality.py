"""Legality audit — the merged 2-zone ARG1 graph, queried for real.

Asserts what the product promise depends on, on the actual shipped
graph (not a fixture):

* mode legality is enforced on every edge of every returned path —
  motor modes never touch foot-scale classes, cycle/walk never touch
  motorway/motorway_link, and OSM oneway is honoured in the travelled
  direction (edge_reversed marks v->u traversal);
* the graph actually carries oneway metadata (a build that dropped the
  tag would silently route cars both ways down Delhi's one-way roads);
* via_names is ordered-unique — the corridor list reads like the turn
  sequence, not a name-mixing replay.

Turn restrictions: the build tool reads ways only — OSM `restriction`
relations are NOT carried into ARG1 (see tools/build_route_graph.py).
That is the documented limit of this audit: on-path turn legality
beyond oneway cannot be asserted from the shipped blob.
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

# realistic ODs across Delhi — long enough to cross motorway + one-way
# corridors, mixed sides of the merged (central+UP) graph
ODS = [
    (28.6315, 77.2167, 28.5479, 77.2511),   # CP → Nehru Place
    (28.6139, 77.2090, 28.7041, 77.1125),   # CP → Rohini
    (28.4595, 77.0266, 28.6315, 77.2167),   # Gurugram → CP
    (28.5708, 77.3260, 28.6139, 77.2090),   # Noida Sec 18 → CP
    (28.6860, 77.2210, 28.5960, 77.3310),   # North → East Delhi
]
MODES = ("car", "auto", "bike", "cycle", "walk")

MOTOR_DENY = {15, 16, 17, 18, 19, 20, 21}   # foot-scale classes
FOOT_DENY = {0, 1}                        # motorway + motorway_link


@pytest.fixture(scope="module")
def graph():
    if not os.path.exists(BLOB_PATH):
        pytest.skip("route_graph.bin.gz not shipped")
    with gzip.open(BLOB_PATH, "rb") as fh:
        blob = fh.read()
    g = routegraph.RouteGraph(blob)
    g.build_adj()
    return g, blob


@pytest.fixture(scope="module")
def py_eng(graph):
    _g, blob = graph
    eng = routegraph.PyPathEngine(blob)
    eng.reweight(lambda lat, lon: 42.0)   # uniform field — legality-only
    return eng


def _assert_legal(g, res, mode):
    rule = routegraph.MODE_RULES[mode]
    for e, rev in zip(res["edge_ids"], res["edge_reversed"]):
        hw = g.e_hw[e]
        assert hw not in rule["deny"], \
            f"{mode} used denied hw={routegraph.HW_NAMES[hw]}"
        ow = g.e_ow[e]
        if rule["oneway"]:
            assert not (ow == 1 and rev), \
                f"{mode} traversed oneway edge {e} backwards"
            assert not (ow == -1 and not rev), \
                f"{mode} traversed reverse-oneway edge {e} forwards"
        assert rule["spd"](g.e_sp[e]) > 0, \
            f"{mode} took zero-speed edge {e}"


def test_legality_every_path_edge(py_eng, graph):
    g, _blob = graph
    n_checked = 0
    for od in ODS:
        for mode in MODES:
            res = py_eng.query(*od, mode)
            if res.get("error"):
                continue
            assert res["edges"] == len(res["edge_ids"]) \
                == len(res["edge_reversed"])
            _assert_legal(g, res, mode)
            n_checked += 1
    assert n_checked > 0, "audit checked zero real paths"


def test_legality_motorway_foot_modes(py_eng, graph):
    """Walk/cycle corridors must never include a motorway edge — the
    classes ring roads + NH48/DND run on."""
    g, _blob = graph
    for od in ODS:
        for mode in ("cycle", "walk"):
            res = py_eng.query(*od, mode)
            if res.get("error"):
                continue
            for e in res["edge_ids"]:
                assert g.e_hw[e] not in FOOT_DENY, (
                    f"{mode} routed onto "
                    f"{routegraph.HW_NAMES[g.e_hw[e]]} on {od}")


def test_legality_foot_scale_denied_to_motor(py_eng, graph):
    """Cars/bikes/autos must never claim footways/cycleways/steps."""
    g, _blob = graph
    for od in ODS:
        for mode in ("car", "auto", "bike"):
            res = py_eng.query(*od, mode)
            if res.get("error"):
                continue
            for e in res["edge_ids"]:
                assert g.e_hw[e] not in MOTOR_DENY, (
                    f"{mode} routed onto "
                    f"{routegraph.HW_NAMES[g.e_hw[e]]} on {od}")


def test_graph_carries_oneway_metadata(graph):
    """The merged build must keep OSM oneway — a regression to all-zero
    would let motor paths drive both ways down one-way roads."""
    g, _blob = graph
    fwd = sum(1 for x in g.e_ow if x == 1)
    rev = sum(1 for x in g.e_ow if x == -1)
    assert fwd + rev > 1000, \
        f"only {fwd + rev} oneway edges — oneway likely dropped at build"


def test_oneway_actually_enforced(graph, py_eng):
    """Find a real oneway edge and prove its wrong direction is dead:
    the adjacency list exposes it to A* (it always will, for non-motor
    modes), but _legal must reject the backwards traversal for every
    motor-mode rule."""
    g, _blob = graph
    e = next(i for i, x in enumerate(g.e_ow) if x == 1)
    for mode in ("car", "auto", "bike"):
        rule = routegraph.MODE_RULES[mode]
        assert not py_eng._legal(e | 0x80000000, True, rule), \
            f"{mode}: reversed oneway edge {e} admitted"
        # forward traversal stays legal (unless the class is denied)
        if g.e_hw[e] not in rule["deny"]:
            assert py_eng._legal(e, False, rule)


def test_via_names_ordered_unique(py_eng):
    """via_names: first-appearance order, zero repeats — the corridor
    list must read like the turn sequence."""
    for od in ODS[:3]:
        res = py_eng.query(*od, "car")
        if res.get("error"):
            continue
        names = res["names"]
        assert len(names) == len(set(names)), \
            f"duplicate names in via_names for {od}: {names}"
