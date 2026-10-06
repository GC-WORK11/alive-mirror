"""route graph for the exposure pathfinder — loader + Python reference.

`route_graph.bin.gz` (built by tools/build_route_graph.py from the same
northern-zone OSM PBF that feeds the gazetteer) holds the NCR street
graph: junction nodes, directed-capable edges with real polyline
geometry, highway class, oneway, plausible speed, street name.

Two engines share identical semantics (parity-tested):

* `alive_core.PathEngine` — C++ A* over the graph (ms per query)
* `PyPathEngine` here — the readable reference; serves when the
  extension can't load (same contract as krige/search twins)

Objective: dose, not time. Edge dose for mode m is the same physics as
exposure.dose():

    dose_e = C_e · me_m · up_hw · (VE_m / 1000) · (len_m / (sp_e·1000/60))

C_e = mean field concentration sampled at ≤5 arc-length-even points
along the edge polyline; edges outside the dose-field bbox take the
field MEAN (honest: unknown air isn't free air — keeps paths inside
coverage without pretending outside edges are clean). A* over that cost
is already detour-aware: a longer path buys dose savings only if the
concentration drop beats the extra minutes of breathing.
"""

import gzip
import heapq
import math
import os
import struct
from typing import Callable, Optional

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
GRAPH_FILE = os.path.join(DATA, "route_graph.bin.gz")

# highway codes — must match HW_CODES in tools/build_route_graph.py
HW_NAMES = ["motorway", "motorway_link", "trunk", "trunk_link", "primary",
            "primary_link", "secondary", "secondary_link", "tertiary",
            "tertiary_link", "unclassified", "residential", "living_street",
            "service", "track", "cycleway", "footway", "pedestrian", "path",
            "steps", "bridleway", "corridor", "road"]

# per-mode road access + speed model (km/h). Edge sp is the plausible
# free-flow speed stored at build; modes clamp it.
# `acc` = per-edge access-deny bits matching build_route_graph.py:
# 1 motor_vehicle | 2 bicycle | 4 foot | 8 motorcar-class | 16 motorcycle.
# `turn` = which bit of a turn-ban mode mask applies to this mode
# (1 motor | 2 cycle | 4 walk — walking ignores vehicular turn bans).
MODE_RULES = {
    # motor: respect oneway, no foot-scale classes
    "car":      {"deny": {15, 16, 17, 18, 19, 20, 21}, "oneway": True,
                 "acc": 0b001 | 0b1000, "turn": 1,
                 "spd": lambda sp: sp},
    "car_open": {"deny": {15, 16, 17, 18, 19, 20, 21}, "oneway": True,
                 "acc": 0b001 | 0b1000, "turn": 1,
                 "spd": lambda sp: sp},
    "cab":      {"deny": {15, 16, 17, 18, 19, 20, 21}, "oneway": True,
                 "acc": 0b001 | 0b1000, "turn": 1,
                 "spd": lambda sp: sp},
    "auto":     {"deny": {0, 1, 15, 16, 17, 18, 19, 20, 21}, "oneway": True,
                 "acc": 0b001, "turn": 1,
                 "spd": lambda sp: min(sp, 40)},
    "bike":     {"deny": {15, 16, 17, 18, 19, 20, 21}, "oneway": True,
                 "acc": 0b001 | 0b10000, "turn": 1,
                 # cap 50: two-wheelers cruise 45-55 km/h on NCR
                 # arterials freeflow (OSM maxspeed 50-70 there) and
                 # outrun autos (cap 40) in Delhi traffic; 30 flattened
                 # the len/sp axis the dose objective optimizes
                 "spd": lambda sp: min(sp, 50)},
    # non-motor: no motorways, oneway not applicable to legs
    "cycle":    {"deny": {0, 1}, "oneway": False,
                 "acc": 0b010, "turn": 2,
                 "spd": lambda sp: min(sp, 16)},
    "walk":     {"deny": {0, 1}, "oneway": False,
                 "acc": 0b100, "turn": 4,
                 "spd": lambda sp: 5.0},
}
# Priced-table mirror of exposure.MICROENV/VENTILATION_LPM (Oct-2026
# re-audit values — Goel 2015 / Apte 2011 / Zuurbier 2009 anchors).
# tests/test_priced_displayed.py asserts these stay equal: pricing a
# different factor than the UI displays would be a silent dose lie.
MODE_VE = {"car": 10.0, "car_open": 10.0, "cab": 10.0, "auto": 10.0,
           "bike": 10.5, "cycle": 22.0, "walk": 14.0}
MODE_ME = {"car": 0.55, "car_open": 1.00, "cab": 1.00, "auto": 1.30,
           "bike": 1.20, "cycle": 1.10, "walk": 1.30}
# NOTE: the priced objective deliberately uses a FLAT uplift (1.0 on
# every edge), matching the display integrator — exposure.dose via
# _dose_band never sees road_class, so a path that 'won' on priced
# near-road uplift lost it right back on the displayed dose (the audit
# showed engine corridors systematically slower AND worse-displayed).
# Pricing the same term the UI shows makes the least-dose claim
# provable on one integrator; near-road plume physics returns only
# when the display band can credit road class.
MAX_SAMPLE_PTS = 5      # per-edge concentration sample count cap
SNAP_RADIUS_M = 1500.0  # furthest node-snap admitted for an endpoint
# snap connectivity screen: a candidate endpoint must sit in the
# main network — `pre` (can reach the giant component, origin side) or
# `post` (reachable from it, destination side). Micro-islands exist on
# real NCR extracts (clipped stubs, ped-precinct clusters); snapping to
# one returned 'no path in graph' on every OD touching it. Floods are
# per-mode (mode legality shapes reachability) and lazy per engine.
MAIN_MIN_FRAC = 0.30    # a flood must cover ≥30% of nodes to be 'main'
SEED_CANDIDATES = 8     # highest-degree nodes tried as flood seeds
# floods cost a full edge sweep per mode; engines rebuilt per test
# would otherwise re-flood the identical graph — cache sets per
# (blob length, mode); the route graph is immutable on disk
_REACH_CACHE = {}

# alternative-corridor search (alternatives()): after the optimal path,
# re-run A* with every found path's edges taxed by ALT_TAX, up to
# ALT_MAX_ATTEMPTS rounds; a candidate sharing >= ALT_MAX_SHARED of its
# length with an already-accepted corridor is a variant, not an
# alternative — rejected (its edges still join the tax set).
ALT_TAX = 1.5
ALT_MAX_ATTEMPTS = 4
ALT_MAX_SHARED = 0.85

R_M = 6371000.0


def _hav_m(lon1, lat1, lon2, lat2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_M * math.asin(math.sqrt(a))


def load_blob(path: str = GRAPH_FILE) -> bytes:
    with gzip.open(path, "rb") as fh:
        return fh.read()


class RouteGraph:
    """Decoded blob → flat arrays (shared layout with the C++ engine)."""

    __slots__ = ("n_nodes", "n_edges", "n_names", "n_pts", "bbox",
                 "node_lon", "node_lat", "names", "e_u", "e_v", "e_len",
                 "e_pts_off", "e_pts_n", "e_hw", "e_ow", "e_sp", "e_nm",
                 "e_field", "e_acc", "bans", "pts", "adj", "meta")

    def __init__(self, blob: bytes):
        magic, nn, ne, nname, npts = struct.unpack_from("<4s4I", blob, 0)
        if magic not in (b"ARG1", b"ARG2"):
            raise ValueError("route_graph: bad magic")
        off = 20
        self.bbox = struct.unpack_from("<4i", blob, off)
        off += 16
        nd = struct.unpack_from("<%di" % (2 * nn), blob, off)
        self.node_lon, self.node_lat = nd[0::2], nd[1::2]
        self.n_nodes = nn
        off += 8 * nn
        self.names = []
        for _ in range(nname):
            (ln,) = struct.unpack_from("<H", blob, off)
            off += 2
            self.names.append(blob[off:off + ln].decode("utf-8"))
            off += ln
        self.n_names = nname
        if magic == b"ARG2":
            fmt = "<IIfIHBbBiBB"   # + u8 access-deny byte
            sz = struct.calcsize(fmt)          # 27
        else:
            fmt = "<IIfIHBbBiB"
            sz = struct.calcsize(fmt)          # 26
        (self.e_u, self.e_v, self.e_len, self.e_pts_off, self.e_pts_n,
         self.e_hw, self.e_ow, self.e_sp, self.e_nm, self.e_field,
         self.e_acc) = ([] for _ in range(11))
        for i in range(ne):
            t = struct.unpack_from(fmt, blob, off + i * sz)
            self.e_u.append(t[0]); self.e_v.append(t[1])
            self.e_len.append(t[2]); self.e_pts_off.append(t[3])
            self.e_pts_n.append(t[4]); self.e_hw.append(t[5])
            self.e_ow.append(t[6]); self.e_sp.append(t[7])
            self.e_nm.append(t[8]); self.e_field.append(t[9])
            self.e_acc.append(t[10] if magic == b"ARG2" else 0)
        self.n_edges = ne
        off += sz * ne
        # ARG2 turn-ban table: (dir-in raw id | via node | dir-out raw id
        # | u8 mode mask) — engines key lookups on (in_dir << 32 | via)
        self.bans = {}
        if magic == b"ARG2":
            (nb,) = struct.unpack_from("<I", blob, off)
            off += 4
            for _ in range(nb):
                din, via, dout, mask = struct.unpack_from("<IIIB",
                                                          blob, off)
                off += 13
                self.bans.setdefault((din, via), {})[dout] = mask
        # points blob — int32 stream to EOF: each edge contributes
        # 2 abs ints + (pts_n-1) packed i16-delta ints ⇒ n_pts + n_edges
        # int32s total. pts_off indexes this stream directly.
        self.n_pts = npts
        self.pts = struct.unpack_from("<%di" % ((len(blob) - off) // 4),
                                      blob, off)
        self.adj = None

    def edge_pts(self, i):
        """Decode edge i's polyline → [(lon, lat), ...].
        pts_off counts 4-byte slots = int32 indices into self.pts;
        first point = 2 slots (abs e6), each delta = 1 slot."""
        off = self.e_pts_off[i]
        n = self.e_pts_n[i]
        lon, lat = self.pts[off], self.pts[off + 1]
        out = [(lon / 1e6, lat / 1e6)]
        k = off + 2
        for _ in range(n - 1):
            packed = self.pts[k]
            dl, dp = _unpack_i16(packed)
            lon += dl
            lat += dp
            out.append((lon / 1e6, lat / 1e6))
            k += 1
        return out

    def build_adj(self):
        """CSR adjacency: for node n, edge ids leaving n. Directed edges
        added both ways unless oneway; ow=-1 means u←v legal, not u→v."""
        adj = [[] for _ in range(self.n_nodes)]
        for i in range(self.n_edges):
            u, v, ow = self.e_u[i], self.e_v[i], self.e_ow[i]
            if ow >= 0:
                adj[u].append(i)
            if ow <= 0:
                adj[v].append(i | 0x80000000)  # high bit = reversed travel
        self.adj = adj
        return adj


def _unpack_i16(packed: int):
    """one i32 slot → two signed i16 deltas (lon_delta, lat_delta)."""
    if packed & 0x8000:
        lo = (packed & 0xFFFF) - 0x10000
    else:
        lo = packed & 0xFFFF
    hi = packed >> 16
    if hi >= 0x8000:
        hi -= 0x10000
    return lo, hi


class PyPathEngine:
    """Reference pathfinder. Same semantics as alive_core.PathEngine;
    slower (pure-Python A*) but parity-checked bit-for-bit on fixtures."""

    def __init__(self, blob: bytes):
        g = RouteGraph(blob)
        g.build_adj()
        self.g = g
        self.conc = [None] * g.n_edges   # per-edge field mean (reweight)
        self.field_mean = None
        self.edges_priced = 0            # count priced — parity w/ C++ twin
        self._radj = None                # reverse CSR, built lazily
        self._reach = {}                 # mode -> (pre, post) bytearrays
        self._blob_key = hash(blob)      # _REACH_CACHE key part

    # ---- reweight: per-edge concentration from the live field ----
    def _sample_pts(self, i):
        """≤MAX_SAMPLE_PTS points evenly spaced over the edge polyline."""
        pts = self.g.edge_pts(i)
        n = len(pts)
        k = min(MAX_SAMPLE_PTS, 1 + math.ceil(self.g.e_len[i] / 200.0))
        if k <= 1:
            return [pts[0]]
        idx = [round(t * (n - 1) / (k - 1)) if k > 1 else 0
               for t in range(k)]
        return [pts[j] for j in sorted(set(idx))]

    def reweight(self, field_value: Callable[[float, float],
                                             Optional[float]]) -> dict:
        vals = []
        for i in range(self.g.n_edges):
            if not self.g.e_field[i]:
                continue
            acc, got = 0.0, 0
            for lon, lat in self._sample_pts(i):
                c = field_value(lat, lon)
                if c is not None and math.isfinite(c) and c >= 0:
                    acc += c
                    got += 1
            if got:
                self.conc[i] = acc / got
                vals.append(self.conc[i])
            else:
                self.conc[i] = None
        self.field_mean = (sum(vals) / len(vals)) if vals else None
        self._min_conc = min(vals) if vals else None
        self.edges_priced = len(vals)
        return {"edges_priced": len(vals), "field_mean": self.field_mean}

    def _conc(self, i):
        c = self.conc[i]
        if c is not None:
            return c
        return self.field_mean if self.field_mean is not None else 0.0

    def _conc32(self, i):
        """_conc through the C++ storage type. The engine keeps per-edge
        concentration in float32 while Python holds float64 — quantizing
        keeps the bounded-Dijkstra inputs (and so the settled sets)
        bit-identical between twins in the parity tests."""
        c = self.conc[i]
        if c is not None:
            return struct.unpack("<f", struct.pack("<f", c))[0]
        return self.field_mean if self.field_mean is not None else 0.0

    # ---- A* over dose cost ----
    def _legal(self, e_i, rev, rule):
        """can `mode` traverse edge e_i in direction rev? (access only —
        concentration does not gate legality)."""
        g = self.g
        e = e_i & 0x7FFFFFFF
        if g.e_hw[e] in rule["deny"]:
            return False
        if g.e_acc[e] & rule["acc"]:
            return False          # per-way access override (bicycle=no,
                                  # foot=no, motor_vehicle=no, ...)
        if rule["oneway"]:
            ow = g.e_ow[e]
            if ow == 1 and rev:
                return False
            if ow == -1 and not rev:
                return False
        return rule["spd"](g.e_sp[e]) > 0

    # ---- connectivity screen: lazy per-mode main-net floods ----------
    def _rev_adj(self):
        """Reverse CSR: radj[x] lists travel directions whose head is x
        — fwd dir i (u->v) enters v when ow>=0; reversed dir i|REV
        (v->u) enters u when ow<=0. Mirrors build_adj exactly."""
        if self._radj is None:
            g = self.g
            radj = [[] for _ in range(g.n_nodes)]
            for i in range(g.n_edges):
                u, v, ow = g.e_u[i], g.e_v[i], g.e_ow[i]
                if ow >= 0:
                    radj[v].append(i)
                if ow <= 0:
                    radj[u].append(i | 0x80000000)
            self._radj = radj
        return self._radj

    def _flood(self, seed, rule, adj, reverse):
        """Mode-legal BFS over adj (forward: node -> successors) or
        radj (reverse: node -> predecessors). Returns bytearray set."""
        g = self.g
        seen = bytearray(g.n_nodes)
        seen[seed] = 1
        fr = [seed]
        while fr:
            n = fr.pop()
            for ei in adj[n]:
                e = ei & 0x7FFFFFFF
                rev = bool(ei & 0x80000000)
                if not self._legal(e, rev, rule):
                    continue
                # forward: successor = head of the travelled dir;
                # reverse: predecessor = tail of the travelled dir
                if reverse:
                    w = g.e_u[e] if not rev else g.e_v[e]
                else:
                    w = g.e_v[e] if not rev else g.e_u[e]
                if not seen[w]:
                    seen[w] = 1
                    fr.append(w)
        return seen

    def _reach_sets(self, mode):
        """(pre, post) main-net membership for `mode`, built lazily.
        post = nodes reachable FROM the main seed (destination side);
        pre = nodes that can reach it (origin side, via reverse BFS).
        Seed = first of the 8 highest-degree nodes whose forward flood
        covers >=MAIN_MIN_FRAC of the graph — junctions sit on the
        main net almost surely; keeps the largest flood otherwise."""
        sets = self._reach.get(mode)
        if sets is not None:
            return sets
        g = self.g
        cache_key = (self._blob_key, mode)
        sets = _REACH_CACHE.get(cache_key)
        if sets is not None:
            self._reach[mode] = sets
            return sets
        rule = MODE_RULES.get(mode) or MODE_RULES["car"]
        seeds = sorted(range(g.n_nodes),
                       key=lambda n: (-len(g.adj[n]), n))[:SEED_CANDIDATES]
        post, seed, best = None, seeds[0], -1
        for s in seeds:
            f = self._flood(s, rule, g.adj, False)
            c = sum(f)
            if c > best:
                post, seed, best = f, s, c
            if c >= g.n_nodes * MAIN_MIN_FRAC:
                break
        pre = self._flood(seed, rule, self._rev_adj(), True)
        sets = (pre, post)
        self._reach[mode] = sets
        return sets

    def snap(self, lat, lon, mode="car", role="from"):
        """nearest node within SNAP_RADIUS_M that the mode can actually
        leave AND that connects to the main network in the trip's
        direction (role 'from' → pre, 'to' → post). Falls back to the
        plain nearest legal node when every in-radius candidate is
        pocketed, preserving intra-island trips."""
        g = self.g
        rule = MODE_RULES.get(mode) or MODE_RULES["car"]
        cands = []               # legal exits in radius, nearest-first
        # narrow by a ~SNAP_RADIUS_M box before haversine
        dlat = SNAP_RADIUS_M / 111320.0
        dlon = dlat / max(0.2, math.cos(math.radians(lat)))
        for n in range(g.n_nodes):
            y = g.node_lat[n] / 1e6
            if not (lat - dlat <= y <= lat + dlat):
                continue
            x = g.node_lon[n] / 1e6
            if not (lon - dlon <= x <= lon + dlon):
                continue
            d = _hav_m(lon, lat, x, y)
            if d >= SNAP_RADIUS_M:
                continue
            for ei in g.adj[n]:
                if self._legal(ei, bool(ei & 0x80000000), rule):
                    cands.append((d, n))
                    break
        if not cands:
            return None, None
        cands.sort()
        pre, post = self._reach_sets(mode)
        screen = pre if role == "from" else post
        for d, n in cands:
            if screen[n]:
                return n, d
        return cands[0][1], cands[0][0]

    def query(self, olat, olon, dlat, dlon, mode="car"):
        """least-dose path → dict(geometry, distance_m, duration_s,
        dose_ug, edge_ids, names hit, snap warnings) or {'error': ...}."""
        return self._route(olat, olon, dlat, dlon, mode, None)

    def alternatives(self, olat, olon, dlat, dlon, mode="car",
                     max_alts=2):
        """Least-dose corridor plus up to `max_alts` honest alternatives.

        After the optimum, each subsequent A* run taxes every edge of
        every corridor found so far by ALT_TAX — the standard
        edge-penalty diversity pass. A candidate sharing >=
        ALT_MAX_SHARED of its length with the accepted corridors is a
        variant of them, not an alternative, and is rejected (its edges
        join the tax set so the next round must go wider). Every
        returned path carries its real dose — nothing is synthesized.
        """
        first = self._route(olat, olon, dlat, dlon, mode, None)
        if first.get("error") or max_alts <= 0:
            return [first]
        g = self.g
        out = [first]
        accepted_edges = set(first["edge_ids"])     # 31-bit ids
        taxed = set(accepted_edges)
        tax = {}
        attempts = 0
        while len(out) < 1 + max_alts and attempts < ALT_MAX_ATTEMPTS:
            for e in taxed:
                tax[e] = ALT_TAX
            attempts += 1
            cand = self._route(olat, olon, dlat, dlon, mode, tax)
            if cand.get("error"):
                break
            cids = set(cand["edge_ids"])
            if cids and cids <= taxed:
                break               # penalty moved nothing — no alt exists
            shared = sum(g.e_len[e] for e in cids & accepted_edges)
            if cand["distance_m"] > 0 and \
                    shared / cand["distance_m"] < ALT_MAX_SHARED:
                out.append(cand)
                accepted_edges |= cids
            taxed |= cids
        return out

    def reach(self, lat, lon, mode="car", budget_ug=0.0,
              max_states=2_000_000):
        """Dose-budget reachable region — parity oracle for
        alive_core.PathEngine.reach (same keys the binding emits).

        The _route expansion run as plain bounded Dijkstra: directed
        edge states sid = (e << 1) | rev, same legality/turn-ban/dose
        pricing, no heuristic, no destination — settles every state
        whose dose stays <= budget_ug, in settle order, until the queue
        drains or max_states pops. States priced over budget never enter
        the queue; pop order is non-decreasing g so the last settled g
        is the honest frontier dose."""
        g = self.g
        rule = MODE_RULES.get(mode) or MODE_RULES["car"]
        ve = MODE_VE.get(mode, 10.0)
        me = MODE_ME.get(mode, 1.0)
        s, sd = self.snap(lat, lon, mode, "from")
        if s is None:
            return {"error": "no graph node near endpoint"}

        def cost(e_i, travel_rev):
            if not self._legal(e_i, travel_rev, rule):
                return None
            e = e_i & 0x7FFFFFFF
            sp = rule["spd"](g.e_sp[e])
            # identical integrand to _route — through the float32 the
            # C++ twin actually stores (see _conc32)
            return (self._conc32(e) * me * (ve / 1000.0)
                    * (0.06 / sp))

        turn_bit = rule["turn"]
        gscore = {}
        pq = []
        settled = set()
        edges_seen = set()
        edge_ids = []
        seen_node = bytearray(g.n_nodes)
        seen_node[s] = 1
        nodes, expanded = 1, 0
        frontier_ug, distance_m = 0.0, 0.0
        truncated = False
        for ei in g.adj[s]:
            e = ei & 0x7FFFFFFF
            rev = bool(ei & 0x80000000)
            rate = cost(ei, rev)
            if rate is None:
                continue
            ng = rate * g.e_len[e]
            if ng > budget_ug:
                continue
            sid = (e << 1) | (1 if rev else 0)
            gscore[sid] = ng
            heapq.heappush(pq, (ng, sid))
        while pq:
            gc, sid = heapq.heappop(pq)
            if sid in settled:
                continue
            settled.add(sid)
            expanded += 1
            frontier_ug = gc          # pops are non-decreasing in g
            e = sid >> 1
            rev = bool(sid & 1)
            if e not in edges_seen:
                edges_seen.add(e)
                edge_ids.append(e)
                distance_m += g.e_len[e]
            n = g.e_v[e] if not rev else g.e_u[e]
            if not seen_node[n]:
                seen_node[n] = 1
                nodes += 1
            if expanded >= max_states:
                truncated = True
                break
            d_raw = e | 0x80000000 if rev else e
            bans = g.bans.get((d_raw, n))
            for ei in g.adj[n]:
                rev2 = bool(ei & 0x80000000)
                e2 = ei & 0x7FFFFFFF
                if bans is not None and \
                        bans.get(ei, 0) & turn_bit:
                    continue          # restricted turn
                rate = cost(ei, rev2)
                if rate is None:
                    continue
                ng = gc + rate * g.e_len[e2]
                if ng > budget_ug:
                    continue
                sid2 = (e2 << 1) | (1 if rev2 else 0)
                if sid2 not in gscore or ng < gscore[sid2] - 1e-9:
                    gscore[sid2] = ng
                    heapq.heappush(pq, (ng, sid2))
        return {
            "edge_ids": edge_ids,
            "expanded": expanded,
            "nodes": nodes,
            "frontier_ug": frontier_ug,
            "distance_m": distance_m,
            "snap_m": sd,
            "truncated": truncated,
        }

    def _route(self, olat, olon, dlat, dlon, mode, tax):
        """One least-dose A* solve; `tax` optionally maps edge id →
        cost multiplier (diversity pass — never a legality override)."""
        g = self.g
        rule = MODE_RULES.get(mode) or MODE_RULES["car"]
        ve = MODE_VE.get(mode, 10.0)
        me = MODE_ME.get(mode, 1.0)
        s, sd = self.snap(olat, olon, mode, "from")
        t, td = self.snap(dlat, dlon, mode, "to")
        if s is None or t is None:
            return {"error": "no graph node near endpoint"}

        def cost(e_i, travel_rev):
            if not self._legal(e_i, travel_rev, rule):
                return None
            e = e_i & 0x7FFFFFFF
            sp = rule["spd"](g.e_sp[e])
            # dose rate per metre of travel on this edge for this mode
            # — same integrand the display band integrates (flat uplift)
            return (self._conc(e) * me * (ve / 1000.0)
                    * (0.06 / sp))  # × len_m applied by caller

        # admissible heuristic: gc distance × cheapest achievable dose/m.
        # mn = min edge concentration (reweight stores it); fastest speed
        # 250 km/h keeps the rate a floor. me/ve are per-mode constants —
        # rate must be recomputed per mode (no shared cache).
        # The ALT_TAX pass multiplies only real edge costs — the bound
        # stays valid (tax can only raise costs, never below h_rate).
        mn = getattr(self, "_min_conc", None)
        if self.field_mean is None or mn is None:
            h_rate = 0.0
        else:
            h_rate = mn * me * (ve / 1000.0) * (0.06 / 250.0)

        def h(n):
            return (_hav_m(g.node_lon[n] / 1e6, g.node_lat[n] / 1e6,
                           dlon, dlat) * h_rate)

        # s == t leaves the search empty — the chain unwinds to [] and
        # the caller gets the (degenerate but legal) zero-edge path.
        # directed-edge-state A*: state id sid = (e << 1) | rev. Turn
        # bans key on the ARRIVAL edge — a node-settled A* would let the
        # cheapest incoming edge own the node and strand continuations
        # the ban check needs (the parity twin does the same).
        turn_bit = rule["turn"]
        gscore = {}
        parent = {}
        pq = []
        settled = set()
        for ei in (g.adj[s] if s != t else ()):
            e = ei & 0x7FFFFFFF
            rev = bool(ei & 0x80000000)
            rate = cost(ei, rev)
            if rate is None:
                continue
            sid = (e << 1) | (1 if rev else 0)
            ng = (rate * g.e_len[e]
                  * (tax.get(e, 1.0) if tax else 1.0))
            gscore[sid] = ng
            parent[sid] = -1
            w0 = g.e_v[e] if not rev else g.e_u[e]
            heapq.heappush(pq, (ng + h(w0), ng, sid))
        end_sid = -1
        while pq:
            f, gc, sid = heapq.heappop(pq)
            if sid in settled:
                continue
            settled.add(sid)
            e = sid >> 1
            rev = bool(sid & 1)
            n = g.e_v[e] if not rev else g.e_u[e]
            if n == t:
                end_sid = sid
                break
            d_raw = e | 0x80000000 if rev else e
            bans = g.bans.get((d_raw, n))
            for ei in g.adj[n]:
                rev2 = bool(ei & 0x80000000)
                e2 = ei & 0x7FFFFFFF
                if bans is not None and \
                        bans.get(ei, 0) & turn_bit:
                    continue      # restricted turn
                rate = cost(ei, rev2)
                if rate is None:
                    continue
                ng = (gc + rate * g.e_len[e2]
                      * (tax.get(e2, 1.0) if tax else 1.0))
                sid2 = (e2 << 1) | (1 if rev2 else 0)
                if sid2 not in gscore or ng < gscore[sid2] - 1e-9:
                    gscore[sid2] = ng
                    parent[sid2] = sid
                    w = g.e_v[e2] if not rev2 else g.e_u[e2]
                    heapq.heappush(pq, (ng + h(w), ng, sid2))
        if end_sid < 0 and s != t:
            return {"error": "no path in graph"}

        # unwind the directed-edge chain
        chain = []
        sid = end_sid
        while sid >= 0:
            chain.append((sid >> 1, bool(sid & 1)))
            sid = parent[sid]
        chain.reverse()

        coords, dist, secs, dose = [], 0.0, 0.0, 0.0
        names_seen, name_set = [], set()
        for e, rev in chain:
            pts = g.edge_pts(e)
            if rev:
                pts = pts[::-1]
            if coords:
                coords.extend(pts[1:])
            else:
                coords.extend(pts)
            ln = g.e_len[e]
            sp = rule["spd"](g.e_sp[e])
            t_min = ln / (sp * 1000 / 60)
            dose += (self._conc(e) * me * (ve / 1000.0) * t_min)
            dist += ln
            secs += t_min * 60.0
            nm = g.e_nm[e]
            if nm:
                nm -= 1  # stored as idx+1
                # ordered-unique: first-appearance order, repeats skipped —
                # the corridor list reads like the turn sequence, not a
                # name-mixing replay of leave/rejoin oscillations
                if 0 <= nm < len(g.names) and g.names[nm] not in name_set:
                    name_set.add(g.names[nm])
                    names_seen.append(g.names[nm])
        return {
            "geometry": {"type": "LineString",
                         "coordinates": [[c[0], c[1]] for c in coords]},
            "distance_m": dist, "duration_s": secs,
            "dose_ug": dose, "edges": len(chain),
            # travelled edge ids (31-bit; direction in edge_reversed) —
            # audit/diversity bookkeeping, same ids the C++ twin emits
            "edge_ids": [e for e, _ in chain],
            "edge_reversed": [rev for _, rev in chain],
            "names": names_seen[:12],
            "snap": {"from_m": sd, "to_m": td},
            "engine": "alive_core-path",
        }


_ENGINE = None


def path_engine():
    """lazy singleton — alive_core.PathEngine when built, else Python."""
    global _ENGINE
    if _ENGINE is None:
        blob = load_blob()
        try:
            import alive_core as _ac
            if hasattr(_ac, "PathEngine"):
                _ENGINE = _ac.PathEngine(blob)
                return _ENGINE
        except Exception:
            pass
        _ENGINE = PyPathEngine(blob)
    return _ENGINE
