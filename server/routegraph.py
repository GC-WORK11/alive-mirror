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
from bisect import bisect_right
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
MODE_RULES = {
    # motor: respect oneway, no foot-scale classes
    "car":      {"deny": {15, 16, 17, 18, 19, 20, 21}, "oneway": True,
                 "spd": lambda sp: sp},
    "car_open": {"deny": {15, 16, 17, 18, 19, 20, 21}, "oneway": True,
                 "spd": lambda sp: sp},
    "cab":      {"deny": {15, 16, 17, 18, 19, 20, 21}, "oneway": True,
                 "spd": lambda sp: sp},
    "auto":     {"deny": {0, 1, 15, 16, 17, 18, 19, 20, 21}, "oneway": True,
                 "spd": lambda sp: min(sp, 40)},
    "bike":     {"deny": {15, 16, 17, 18, 19, 20, 21}, "oneway": True,
                 "spd": lambda sp: min(sp, 30)},
    # non-motor: no motorways, oneway not applicable to legs
    "cycle":    {"deny": {0, 1}, "oneway": False,
                 "spd": lambda sp: min(sp, 16)},
    "walk":     {"deny": {0, 1}, "oneway": False,
                 "spd": lambda sp: 5.0},
}
MODE_VE = {"car": 7.5, "car_open": 7.5, "cab": 7.5, "auto": 8.5,
           "bike": 9.0, "cycle": 22.0, "walk": 14.0}
MODE_ME = {"car": 0.55, "car_open": 0.80, "cab": 0.80, "auto": 1.15,
           "bike": 1.10, "cycle": 1.10, "walk": 1.00}
# ROAD_UPLIFT keyed by hw code — exposure.py's published factors
HW_UPLIFT = {0: 1.35, 1: 1.35, 2: 1.30, 3: 1.30, 4: 1.20, 5: 1.20,
             6: 1.10, 7: 1.10, 8: 1.05, 9: 1.05}
MAX_SAMPLE_PTS = 5      # per-edge concentration sample count cap
SNAP_RADIUS_M = 1500.0  # furthest node-snap admitted for an endpoint

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
                 "e_field", "pts", "adj", "meta")

    def __init__(self, blob: bytes):
        magic, nn, ne, nname, npts = struct.unpack_from("<4s4I", blob, 0)
        if magic != b"ARG1":
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
        fmt = "<IIfIHBbBiB"
        sz = struct.calcsize(fmt)          # 26
        (self.e_u, self.e_v, self.e_len, self.e_pts_off, self.e_pts_n,
         self.e_hw, self.e_ow, self.e_sp, self.e_nm, self.e_field) = \
            ([] for _ in range(10))
        for i in range(ne):
            t = struct.unpack_from(fmt, blob, off + i * sz)
            self.e_u.append(t[0]); self.e_v.append(t[1])
            self.e_len.append(t[2]); self.e_pts_off.append(t[3])
            self.e_pts_n.append(t[4]); self.e_hw.append(t[5])
            self.e_ow.append(t[6]); self.e_sp.append(t[7])
            self.e_nm.append(t[8]); self.e_field.append(t[9])
        self.n_edges = ne
        off += sz * ne
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


def _pack_i16(dl: int, dp: int) -> int:
    return (dl & 0xFFFF) | ((dp & 0xFFFF) << 16)


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

    # ---- A* over dose cost ----
    def _legal(self, e_i, rev, rule):
        """can `mode` traverse edge e_i in direction rev? (access only —
        concentration does not gate legality)."""
        g = self.g
        e = e_i & 0x7FFFFFFF
        if g.e_hw[e] in rule["deny"]:
            return False
        if rule["oneway"]:
            ow = g.e_ow[e]
            if ow == 1 and rev:
                return False
            if ow == -1 and not rev:
                return False
        return rule["spd"](g.e_sp[e]) > 0

    def snap(self, lat, lon, mode="car"):
        """nearest node within SNAP_RADIUS_M that the mode can actually
        leave — a geometrically closer node sitting on footways only is
        a dead snap for a car."""
        g = self.g
        rule = MODE_RULES.get(mode) or MODE_RULES["car"]
        best, bd = None, SNAP_RADIUS_M
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
            if d >= bd:
                continue
            for ei in g.adj[n]:
                if self._legal(ei, bool(ei & 0x80000000), rule):
                    best, bd = n, d
                    break
        return (best, bd) if best is not None else (None, None)

    def query(self, olat, olon, dlat, dlon, mode="car"):
        """least-dose path → dict(geometry, distance_m, duration_s,
        dose_ug, edge_ids, names hit, snap warnings) or {'error': ...}."""
        g = self.g
        rule = MODE_RULES.get(mode) or MODE_RULES["car"]
        ve = MODE_VE.get(mode, 8.0)
        me = MODE_ME.get(mode, 1.0)
        s, sd = self.snap(olat, olon, mode)
        t, td = self.snap(dlat, dlon, mode)
        if s is None or t is None:
            return {"error": "no graph node near endpoint"}

        def cost(e_i, travel_rev):
            if not self._legal(e_i, travel_rev, rule):
                return None
            e = e_i & 0x7FFFFFFF
            sp = rule["spd"](g.e_sp[e])
            up = HW_UPLIFT.get(g.e_hw[e], 1.0)
            # dose rate per metre of travel on this edge for this mode
            return (self._conc(e) * me * up * (ve / 1000.0)
                    * (0.06 / sp))  # × len_m applied by caller

        # admissible heuristic: gc distance × cheapest achievable dose/m.
        # mn = min edge concentration (reweight stores it); fastest speed
        # 250 km/h keeps the rate a floor. me/ve/uplift≥1 are per-mode
        # constants — rate must be recomputed per mode (no shared cache).
        mn = getattr(self, "_min_conc", None)
        if self.field_mean is None or mn is None:
            h_rate = 0.0
        else:
            h_rate = mn * me * (ve / 1000.0) * (0.06 / 250.0)

        def h(n):
            return (_hav_m(g.node_lon[n] / 1e6, g.node_lat[n] / 1e6,
                           dlon, dlat) * h_rate)

        gscore = {s: 0.0}
        parent = {}
        pq = [(h(s), 0.0, s)]
        settled = set()
        while pq:
            f, gc, n = heapq.heappop(pq)
            if n in settled:
                continue
            settled.add(n)
            if n == t:
                break
            for ei in g.adj[n]:
                rev = bool(ei & 0x80000000)
                e = ei & 0x7FFFFFFF
                to = g.e_v[e] if not rev else g.e_u[e]
                rate = cost(e, rev)
                if rate is None:
                    continue
                w = rate * g.e_len[e]
                ng = gc + w
                if to not in gscore or ng < gscore[to] - 1e-9:
                    gscore[to] = ng
                    parent[to] = (n, e, rev)
                    heapq.heappush(pq, (ng + h(to), ng, to))
        if t not in gscore:
            return {"error": "no path in graph"}

        # unwind
        chain = []
        n = t
        while n != s:
            p, e, rev = parent[n]
            chain.append((e, rev))
            n = p
        chain.reverse()

        coords, dist, secs, dose = [], 0.0, 0.0, 0.0
        names_seen = []
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
            dose += (self._conc(e) * me * HW_UPLIFT.get(g.e_hw[e], 1.0)
                     * (ve / 1000.0) * t_min)
            dist += ln
            secs += t_min * 60.0
            nm = g.e_nm[e]
            if nm:
                nm -= 1  # stored as idx+1
                if 0 <= nm < len(g.names) and \
                        (not names_seen or names_seen[-1] != g.names[nm]):
                    names_seen.append(g.names[nm])
        return {
            "geometry": {"type": "LineString",
                         "coordinates": [[c[0], c[1]] for c in coords]},
            "distance_m": dist, "duration_s": secs,
            "dose_ug": dose, "edges": len(chain),
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
