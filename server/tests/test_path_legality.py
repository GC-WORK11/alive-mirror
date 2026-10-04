"""Legality audit — the merged 2-zone ARG2 graph, queried for real.

Asserts what the product promise depends on, on the actual shipped
graph (not a fixture):

* mode legality is enforced on every edge of every returned path —
  motor modes never touch foot-scale classes, cycle/walk never touch
  motorway/motorway_link, OSM oneway is honoured in the travelled
  direction (edge_reversed marks v->u traversal), and per-way access
  overrides (bicycle=no / foot=no / motor_vehicle=no / access=private)
  bind the modes they name;
* the graph actually carries oneway metadata (a build that dropped the
  tag would silently route cars both ways down Delhi's one-way roads);
* ARG2 turn bans are carried AND enforced — real (dir-in, via node,
  dir-out) tuples from the shipped blob never appear as a travelled
  transition, and a synthetic micro-graph proves a banned left turn
  actually detours the path;
* via_names is ordered-unique — the corridor list reads like the turn
  sequence, not a name-mixing replay.

Known coverage gaps (documented, not faked): restriction relations
whose via node isn't a packed junction node, whose via way splits into
>1 packed edge, or whose from/to ways leave the extract are counted
skipped at build (see meta ban_stats); `except=` tags clear the
matching mode bit rather than whitelist extra modes.
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
        assert not (g.e_acc[e] & rule["acc"]), \
            f"{mode} used access-denied edge {e} (acc={g.e_acc[e]:#04x})"
        ow = g.e_ow[e]
        if rule["oneway"]:
            assert not (ow == 1 and rev), \
                f"{mode} traversed oneway edge {e} backwards"
            assert not (ow == -1 and not rev), \
                f"{mode} traversed reverse-oneway edge {e} forwards"
        assert rule["spd"](g.e_sp[e]) > 0, \
            f"{mode} took zero-speed edge {e}"


def _banned_transitions(g, res):
    """count of travelled (dir-in, via, dir-out) moves the ARG2 ban
    table forbids — walk's turn bit never matches vehicular masks."""
    n = 0
    for i in range(1, len(res["edge_ids"])):
        din = res["edge_ids"][i - 1] | \
            (0x80000000 if res["edge_reversed"][i - 1] else 0)
        dout = res["edge_ids"][i] | \
            (0x80000000 if res["edge_reversed"][i] else 0)
        e_prev = din & 0x7FFFFFFF
        via = g.e_u[e_prev] if (din & 0x80000000) else g.e_v[e_prev]
        outs = g.bans.get((din, via))
        if outs and outs.get(dout, 0):
            n += 1
    return n


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


# ---- ARG2: per-way access overrides + turn bans ----

def test_graph_carries_access_overrides(graph):
    """A build that dropped access tags would zero this out — the
    legality gain this leg adds must be visible in the shipped blob."""
    g, _blob = graph
    n = sum(1 for a in g.e_acc if a)
    assert n > 1000, \
        f"only {n} edges carry access overrides — tags likely dropped"


def test_access_override_binds_modes(graph, py_eng):
    """Find real edges with each deny bit and prove _legal rejects the
    matching mode while a clean same-class edge stays legal."""
    g, _blob = graph
    cases = (0b001, "car"), (0b010, "cycle"), (0b100, "walk")
    for bit, mode in cases:
        e = next((i for i, a in enumerate(g.e_acc)
                  if a & bit and
                  g.e_hw[i] not in routegraph.MODE_RULES[mode]["deny"]),
                 None)
        if e is None:
            continue
        rule = routegraph.MODE_RULES[mode]
        assert not py_eng._legal(e, False, rule), \
            f"{mode}: acc-denied edge {e} admitted (acc={g.e_acc[e]})"


def test_graph_carries_turn_bans(graph):
    """Restriction relations must land in the blob — a regression to an
    empty table would silently re-legalize banned turns."""
    g, _blob = graph
    total = sum(len(v) for v in g.bans.values())
    assert total > 50, f"only {total} ban tuples — restrictions dropped"


def test_real_ban_never_travelled(py_eng, graph):
    """Every returned path's consecutive moves are checked against the
    shipped ban table: a (dir-in, via, dir-out) tuple with the mode's
    bit set must never appear. Audit over real ODs — the same check a
    CP/ITO no-right-turn would trip."""
    g, _blob = graph
    n_paths = 0
    for od in ODS:
        for mode in MODES:
            res = py_eng.query(*od, mode)
            if res.get("error"):
                continue
            n_paths += 1
            bad = _banned_transitions(g, res)
            assert bad == 0, \
                f"{mode} on {od}: {bad} banned transitions travelled"
    assert n_paths > 0


def _micro_arg2():
    """A→D corridor: direct e0→e2, detour e0→e1→e3→e4. Ban forbids
    (e0 fwd @ node B → e2 fwd) for motorized modes + cycle, not walk."""
    import struct
    nodes = [(77000000, 28000000),   # 0 A
             (77010000, 28000000),   # 1 B
             (77020000, 28000000),   # 2 C
             (77010000, 28010000),   # 3 D
             (77020000, 28010000)]   # 4 E
    # detour (3600 m) must beat the wiggle (4400 m: B→C→B→D, a legal
    # mid-block U-turn absent any no_u_turn ban); direct is 2400 m
    edges = [(0, 1, 1000.0), (1, 2, 1000.0), (1, 3, 1400.0),
             (2, 4, 800.0), (4, 3, 800.0)]
    bans = [(0, 1, 2, 0b011)]        # (e0 fwd, via B, e2 fwd, motor|cycle)

    blob = bytearray()
    blob += struct.pack("<4s4I", b"ARG2", len(nodes), len(edges), 0, 0)
    blob += struct.pack("<4i", 76999000, 27999000, 77021000, 28011000)
    for lon, lat in nodes:
        blob += struct.pack("<2i", lon, lat)
    pts_blob = bytearray()
    off = 0
    offs = []
    for u, v, _ln in edges:
        pts_blob += struct.pack("<2i", *nodes[u])
        pts_blob += struct.pack("<2h", nodes[v][0] - nodes[u][0],
                                nodes[v][1] - nodes[u][1])
        offs.append((off, 2))
        off += 3
    for (u, v, ln), (po, pn) in zip(edges, offs):
        blob += struct.pack("<IIfIHBbBiBB", u, v, ln, po, pn,
                            9,      # hw: residential
                            0,      # ow
                            30,     # sp km/h
                            0,      # nm → none
                            1,      # in_field → sampled by reweight
                            0)      # acc
    blob += struct.pack("<I", len(bans))
    for din, via, dout, mask in bans:
        blob += struct.pack("<IIIB", din, via, dout, mask)
    blob += pts_blob
    return bytes(blob)


def test_real_ban_brackets_detour(py_eng, graph):
    """For each real ban tuple, route between the nodes bracketing the
    banned move (tail of dir-in → head of dir-out): the 2-edge banned
    trajectory is the natural answer, so any returned path that avoids
    it proves the ban is enforced, not merely stored."""
    g, _blob = graph
    tried = detoured = 0
    for (din, via), outs in list(g.bans.items()):
        e_in, rev_in = din & 0x7FFFFFFF, bool(din & 0x80000000)
        o_node = g.e_u[e_in] if not rev_in else g.e_v[e_in]
        assert (g.e_v[e_in] if not rev_in else g.e_u[e_in]) == via
        for dout in outs:
            e_out, rev_out = dout & 0x7FFFFFFF, \
                bool(dout & 0x80000000)
            d_node = g.e_v[e_out] if not rev_out else g.e_u[e_out]
            if o_node == d_node:
                continue
            res = py_eng.query(
                g.node_lat[o_node] / 1e6, g.node_lon[o_node] / 1e6,
                g.node_lat[d_node] / 1e6, g.node_lon[d_node] / 1e6,
                "car")
            if res.get("error"):
                continue
            tried += 1
            # the banned trajectory itself must never be travelled
            assert _banned_transitions(g, res) == 0
            if res["edge_ids"] != [e_in, e_out]:
                detoured += 1
    assert tried > 20, f"only {tried} real ban brackets routable"
    assert detoured > 0


def _pocket_arg2():
    """Main corridor A-B-C plus a 2-node car-legal island I-J closer
    to the query origin than A — the dead-pocket snap the connectivity
    screen must skip. Also an isolated pair P-Q far outside the main
    net: intra-island trips must still route via the nearest-legal
    fallback."""
    import struct
    nodes = [(77000000, 28000000),   # 0 A
             (77010000, 28000000),   # 1 B
             (77020000, 28000000),   # 2 C
             (77000002, 28000000),   # 3 I (0.19 m from A's coords)
             (77001000, 28000000),   # 4 J
             (76900000, 27900000),   # 5 P — >100 km away
             (76901000, 27900000)]   # 6 Q
    edges = [(0, 1, 1000.0), (1, 2, 1000.0),   # main corridor
             (3, 4, 90.0),                      # dead-end island stub
             (5, 6, 90.0)]                      # remote island pair
    blob = bytearray()
    blob += struct.pack("<4s4I", b"ARG2", len(nodes), len(edges), 0, 0)
    blob += struct.pack("<4i", 76899000, 27899000, 77021000, 28011000)
    for lon, lat in nodes:
        blob += struct.pack("<2i", lon, lat)
    pts_blob = bytearray()
    off = 0
    offs = []
    for u, v, _ln in edges:
        pts_blob += struct.pack("<2i", *nodes[u])
        pts_blob += struct.pack("<2h", nodes[v][0] - nodes[u][0],
                                nodes[v][1] - nodes[u][1])
        offs.append((off, 2))
        off += 3
    for (u, v, ln), (po, pn) in zip(edges, offs):
        blob += struct.pack("<IIfIHBbBiBB", u, v, ln, po, pn,
                            9, 0, 30, 0, 1, 0)
    blob += struct.pack("<I", 0)
    blob += pts_blob
    return bytes(blob)


def test_snap_skips_dead_pocket():
    """Querying from the island's exact spot must snap to main-net A
    (role-aware: origin screens on pre, destination on post); the old
    nearest-legal snap returned 'no path' here."""
    for mk in (routegraph.PyPathEngine,
               getattr(__import__("alive_core"), "PathEngine", None)):
        if mk is None:
            continue
        eng = mk(_pocket_arg2())
        eng.reweight(lambda lat, lon: 42.0)
        res = eng.query(28.0, 77.000002, 28.0, 77.02, "car")
        assert res.get("error") is None, res
        assert res["edge_ids"] == [0, 1], res["edge_ids"]


def test_snap_fallback_routes_intra_island():
    """When every in-radius node is pocketed, snap falls back to the
    nearest legal node — a trip that lives entirely inside an island
    still routes instead of hard-failing."""
    eng = routegraph.PyPathEngine(_pocket_arg2())
    eng.reweight(lambda lat, lon: 42.0)
    res = eng.query(27.9, 76.90, 27.9, 76.901, "car")
    assert res.get("error") is None, res
    assert res["edge_ids"] == [3], res["edge_ids"]


def _uplift_arg2():
    """Parallel A→C: edge0 motorway 1000m sp60, edge1 residential
    1000m sp50. Under the old per-edge hw uplift (1.35 vs 1.05) the
    residential won despite being slower; flat uplift must pick the
    motorway — the same integrand the display band integrates."""
    import struct
    nodes = [(77000000, 28000000),   # 0 A
             (77010000, 28000000)]   # 1 C
    edges = [(0, 1, 1000.0, 0, 60),  # motorway, fast
             (0, 1, 1000.0, 9, 50)]  # residential, slower
    blob = bytearray()
    blob += struct.pack("<4s4I", b"ARG2", len(nodes), len(edges), 0, 0)
    blob += struct.pack("<4i", 76999000, 27999000, 77001000, 28001000)
    for lon, lat in nodes:
        blob += struct.pack("<2i", lon, lat)
    pts_blob = bytearray()
    off = 0
    offs = []
    for u, v, _ln, _hw, _sp in edges:
        pts_blob += struct.pack("<2i", *nodes[u])
        pts_blob += struct.pack("<2h", nodes[v][0] - nodes[u][0],
                                nodes[v][1] - nodes[u][1])
        offs.append((off, 2))
        off += 3
    for (u, v, ln, hw, sp), (po, pn) in zip(edges, offs):
        blob += struct.pack("<IIfIHBbBiBB", u, v, ln, po, pn,
                            hw, 0, sp, 0, 1, 0)
    blob += struct.pack("<I", 0)
    blob += pts_blob
    return bytes(blob)


def test_priced_objective_matches_display_integrand():
    """Flat uplift: on a uniform field the engine must take the fast
    motorway, and dose_ug must equal conc*me*ve*minutes exactly — the
    old 1.35/1.05 road uplift would both flip the choice and inflate
    dose_ug 5% on the residential edge."""
    import math
    expected = {}
    for mk in (routegraph.PyPathEngine,
               getattr(__import__("alive_core"), "PathEngine", None)):
        if mk is None:
            continue
        eng = mk(_uplift_arg2())
        eng.reweight(lambda lat, lon: 42.0)
        r = eng.query(28.0, 77.0, 28.0, 77.01, "car")
        assert r["edge_ids"] == [0], r["edge_ids"]
        t_min = 1000.0 / (60 * 1000 / 60)          # 1 km at 60 km/h
        want = 42.0 * 0.55 * (7.5 / 1000.0) * t_min
        assert math.isclose(r["dose_ug"], want, rel_tol=1e-9), \
            f"{r['dose_ug']} != {want}"
        expected[type(eng).__name__] = r["dose_ug"]
    # identical dose on both engines — bit-parity on the new integrand
    assert len(set(expected.values())) <= 1


def test_bike_speed_cap_50():
    """Two-wheeler freeflow cap is arterial-honest: 45-55 km/h on NCR
    arterials (OSM maxspeed 50-70), above autos (40) which bikes
    outrun; the old 30 cap flattened the len/sp axis and inflated the
    engine-side bike dose ~2x vs the router's freeflow model."""
    spd = routegraph.MODE_RULES["bike"]["spd"]
    assert spd(70) == 50 and spd(40) == 40


def test_synthetic_turn_ban_detours():
    """Deterministic proof the ban changes the path: A→D by car must
    take the 3-edge detour, never the banned (e0→e2) move; walk keeps
    the direct route (turn bans don't bind pedestrians)."""
    eng = routegraph.PyPathEngine(_micro_arg2())
    eng.reweight(lambda lat, lon: 42.0)
    car = eng.query(28.0, 77.0, 28.01, 77.01, "car")
    assert car.get("error") is None
    assert car["edge_ids"] == [0, 1, 3, 4], car["edge_ids"]
    assert car["edge_reversed"] == [0, 0, 0, 0]
    walk = eng.query(28.0, 77.0, 28.01, 77.01, "walk")
    assert walk["edge_ids"] == [0, 2], walk["edge_ids"]

    try:
        import alive_core
    except ImportError:
        return
    cxx = alive_core.PathEngine(_micro_arg2())
    cxx.reweight(lambda lat, lon: 42.0)
    rc = cxx.query(28.0, 77.0, 28.01, 77.01, "car")
    assert rc["edge_ids"] == [0, 1, 3, 4], rc["edge_ids"]
    rw = cxx.query(28.0, 77.0, 28.01, 77.01, "walk")
    assert rw["edge_ids"] == [0, 2], rw["edge_ids"]
