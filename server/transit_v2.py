"""Transit planner v2 — timetable-exact metro + bus trips from GTFS.

Clean extraction of the routing that lives in transit_real.py, rebuilt
around one public call:

    plan_transit(from_lat, from_lon, to_lat, to_lon, depart_at=None)
        -> [ {mode, legs, duration_s, walk_m, transfers, ...}, ... ]

What changed vs transit_real.py
  * Time-dependent: a Connection Scan (CSA) over every scheduled
    stop_times hop, so `depart_at` matters — waits are the real gap to the
    next scheduled departure, not a flat ACCESS_WAIT constant.
  * Bus is routed, not hinted: same CSA over the DTC/DIMTS feed, with
    transfers, instead of "direct route names" only.
  * Multi-stop access: every stop within the access radius is a candidate
    board/alight point (transit_real used only the single nearest).
  * Transfer-bounded labels (max_rides rounds), so the chosen journey
    trades arrival time against changes: score = arrive + transfers *
    TRANSFER_PENALTY_S.
  * Pure + injectable: feeds are plain GTFS directories parsed by
    load_feed(); tests pass tiny fixture feeds, production reads the
    cache transit_real.py downloads (data/gtfs/{metro,bus}). Nothing here
    touches the network.

Stated assumptions
  * Walk legs are straight-line at WALK_KMH (same convention as
    transit.py / transit_real.py), footpath transfers < WALK_LINK_M.
  * Without calendar.txt every trip in the feed is assumed to run (DMRC
    feed ships only service_id names: weekday / saturday).
  * Ride geometry = polyline through the stops actually ridden.

Mode labels: bus feed -> "bus"; metro feed -> "metro" when total walking
is <= METRO_WALK_M, else "metro+walk".
"""
import array
import bisect
import csv
import datetime as dt
import math
import os
import pickle
import re
import threading
from collections import defaultdict
from typing import Iterable, Optional, Union

# --- tuning ---------------------------------------------------------------
WALK_KMH = 5.0
WALK_LINK_M = 350.0            # footpath transfer between distinct stops
TRANSFER_PENALTY_S = 5 * 60    # generalized cost per change (not clock time)
MAX_JOURNEY_S = 3 * 3600       # stop scanning this long after departure
METRO_WALK_M = 500.0           # "metro" vs "metro+walk" label threshold

FEEDS = {
    #         access radius, max candidates, entry (security), exit, change
    "metro": {"access_m": 2500.0, "max_access": 10, "entry_s": 180,
              "exit_s": 60, "change_s": 180, "max_rides": 4},
    "bus":   {"access_m": 1200.0, "max_access": 20, "entry_s": 0,
              "exit_s": 0, "change_s": 120, "max_rides": 3},
}

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
_HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(_HERE, "data", "gtfs")   # filled by transit_real
INDEX_NAME = "_v2_index.pkl"
INDEX_VERSION = 1
INF = 1 << 40
_DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday",
         "saturday", "sunday")


# --- helpers --------------------------------------------------------------
def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def walk_s(m: float) -> float:
    return m / (WALK_KMH / 3.6)


def _sec(t: str) -> Optional[int]:
    try:
        h, m, s = t.strip().split(":")
        return int(h) * 3600 + int(m) * 60 + int(s)
    except Exception:
        return None


def clean_stop_name(name: str) -> str:
    """'Noida Sec -18' -> 'Noida Sector 18'."""
    n = re.sub(r"\bSec(?:tor)?\s*-?\s*(\d+)", r"Sector \1", name)
    return re.sub(r"\s{2,}", " ", n).strip()


def line_name(kind: str, short: str, long: str) -> str:
    if kind == "metro":
        # DMRC long names: "BLUE_Dwarka to Noida" -> "Blue"
        return (long or short or "").split("_")[0].title() or "Metro"
    nm = (short or long or "?").strip()
    return re.sub(r"(UP|DOWN)$", "", nm) or nm   # DTC "347AUP" -> "347A"


def _read(path: str) -> Iterable[dict]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        yield from csv.DictReader(fh)


class _Grid:
    """Bucketed point index for radius queries (cell ~= radius)."""

    def __init__(self, lats, lons, cell_deg: float = 0.01):
        self.cell = cell_deg
        self.lats, self.lons = lats, lons
        self.b = defaultdict(list)
        for i, (la, lo) in enumerate(zip(lats, lons)):
            self.b[(int(la // cell_deg), int(lo // cell_deg))].append(i)

    def within(self, lat: float, lon: float, radius_m: float):
        r = int(radius_m / (111000.0 * self.cell)) + 1
        cx, cy = int(lat // self.cell), int(lon // self.cell)
        out = []
        for x in range(cx - r, cx + r + 1):
            for y in range(cy - r, cy + r + 1):
                for i in self.b.get((x, y), ()):
                    d = haversine_m(lat, lon, self.lats[i], self.lons[i])
                    if d <= radius_m:
                        out.append((d, i))
        out.sort()
        return out


# --- feed ----------------------------------------------------------------
class Feed:
    """One GTFS feed compiled for CSA: connections sorted by departure."""

    def __init__(self, kind: str):
        self.kind = kind
        self.stop_ids, self.names, self.lats, self.lons = [], [], [], []
        self.trip_line, self.trip_head, self.trip_ids = [], [], []
        self.c_dep = array.array("i")
        self.c_arr = array.array("i")
        self.c_from = array.array("i")
        self.c_to = array.array("i")
        self.c_trip = array.array("i")
        self.footpaths = []          # per stop: [(other, seconds, metres)]
        self.calendar = {}           # service_id -> (days set, start, end)
        self.trip_service = []
        self._grid = None

    @property
    def grid(self) -> _Grid:
        if self._grid is None:
            self._grid = _Grid(self.lats, self.lons)
        return self._grid

    def __getstate__(self):
        s = dict(self.__dict__)
        s["_grid"] = None
        return s


def load_feed(feed_dir: str, kind: str, use_cache: bool = True) -> Feed:
    """Compile a GTFS dir (stops/routes/trips/stop_times[/calendar]).

    A pickled index is kept next to the txts and reused while it is newer
    than every source file."""
    if kind not in FEEDS:
        raise ValueError(f"unknown feed kind {kind!r}")
    pkl = os.path.join(feed_dir, INDEX_NAME)
    srcs = [os.path.join(feed_dir, f) for f in
            ("stops.txt", "routes.txt", "trips.txt", "stop_times.txt")]
    if use_cache and os.path.exists(pkl):
        try:
            if all(os.path.getmtime(p) <= os.path.getmtime(pkl) for p in srcs):
                with open(pkl, "rb") as fh:
                    ver, f = pickle.load(fh)
                if ver == INDEX_VERSION and f.kind == kind:
                    return f
        except Exception:
            pass

    f = Feed(kind)
    sidx = {}
    for r in _read(srcs[0]):
        try:
            la, lo = float(r["stop_lat"]), float(r["stop_lon"])
        except (KeyError, ValueError):
            continue
        sidx[r["stop_id"]] = len(f.stop_ids)
        f.stop_ids.append(r["stop_id"])
        f.names.append(clean_stop_name(r.get("stop_name") or r["stop_id"]))
        f.lats.append(la)
        f.lons.append(lo)

    routes = {r["route_id"]: line_name(kind, r.get("route_short_name", ""),
                                       r.get("route_long_name", ""))
              for r in _read(srcs[1])}
    tidx = {}
    for r in _read(srcs[2]):
        tidx[r["trip_id"]] = len(f.trip_ids)
        f.trip_ids.append(r["trip_id"])
        f.trip_line.append(routes.get(r["route_id"], "?"))
        f.trip_head.append((r.get("trip_headsign") or "").strip())
        f.trip_service.append(r.get("service_id", ""))

    cal = os.path.join(feed_dir, "calendar.txt")
    if os.path.exists(cal):
        for r in _read(cal):
            days = {i for i, d in enumerate(_DAYS) if r.get(d, "0").strip() == "1"}
            f.calendar[r["service_id"]] = (days, r.get("start_date", "0"),
                                           r.get("end_date", "99999999"))

    per_trip = defaultdict(list)
    for r in _read(srcs[3]):
        t, s = tidx.get(r["trip_id"]), sidx.get(r["stop_id"])
        if t is None or s is None:
            continue
        a = _sec(r.get("arrival_time") or r.get("departure_time") or "")
        d = _sec(r.get("departure_time") or r.get("arrival_time") or "")
        if a is None or d is None:
            continue
        per_trip[t].append((int(r["stop_sequence"]), a, d, s))

    conns = []
    for t, rows in per_trip.items():
        rows.sort()
        for (_, _, d0, s0), (_, a1, _, s1) in zip(rows, rows[1:]):
            if s0 != s1 and 0 <= a1 - d0 < 3600:
                conns.append((d0, a1, s0, s1, t))
    conns.sort()
    for d0, a1, s0, s1, t in conns:
        f.c_dep.append(d0)
        f.c_arr.append(a1)
        f.c_from.append(s0)
        f.c_to.append(s1)
        f.c_trip.append(t)

    f.footpaths = [[] for _ in f.stop_ids]
    g = f.grid
    for i in range(len(f.stop_ids)):
        for d, j in g.within(f.lats[i], f.lons[i], WALK_LINK_M):
            if j != i and d > 0:
                f.footpaths[i].append((j, walk_s(d), d))

    if use_cache:
        try:
            with open(pkl, "wb") as fh:
                pickle.dump((INDEX_VERSION, f), fh, protocol=pickle.HIGHEST_PROTOCOL)
        except OSError:
            pass
    return f


# --- default feeds (cache written by transit_real.py) ---------------------
_FEEDS = {}
_FEEDS_LOCK = threading.Lock()


def default_feeds() -> dict:
    """{kind: Feed} for every cached feed on disk; parsed once per process."""
    with _FEEDS_LOCK:
        for kind in FEEDS:
            if kind in _FEEDS:
                continue
            d = os.path.join(CACHE_DIR, kind)
            if os.path.exists(os.path.join(d, "stop_times.txt")):
                try:
                    _FEEDS[kind] = load_feed(d, kind)
                except Exception:
                    pass
        return dict(_FEEDS)


# --- time -----------------------------------------------------------------
def _to_ist(depart_at) -> dt.datetime:
    if depart_at is None:
        return dt.datetime.now(IST)
    if isinstance(depart_at, (int, float)):
        return dt.datetime.fromtimestamp(depart_at, IST)
    if isinstance(depart_at, str):
        depart_at = dt.datetime.fromisoformat(depart_at.replace("Z", "+00:00"))
    if depart_at.tzinfo is None:          # naive = Delhi wall clock
        return depart_at.replace(tzinfo=IST)
    return depart_at.astimezone(IST)


def _active_trips(feed: Feed, day: dt.date) -> Optional[bytearray]:
    """Trip mask from calendar.txt, or None = every trip runs."""
    if not feed.calendar:
        return None
    ymd, wd = day.strftime("%Y%m%d"), day.weekday()
    ok = {sid for sid, (days, a, b) in feed.calendar.items()
          if wd in days and a <= ymd <= b}
    return bytearray(1 if s in ok else 0 for s in feed.trip_service)


# --- connection scan ------------------------------------------------------
def _csa(feed: Feed, cfg: dict, access: dict, egress: dict, t0: int,
         mask: Optional[bytearray]):
    """Transfer-bounded earliest-arrival CSA.

    access/egress: {stop: walk metres}. Returns list of journeys per ride
    count k (1..R): (arrive_s, chain) where chain = [(kind, ...)] in order.
    """
    R = cfg["max_rides"]
    n = len(feed.stop_ids)
    change_s, entry_s, exit_s = cfg["change_s"], cfg["entry_s"], cfg["exit_s"]
    ready = [[INF] * n for _ in range(R + 1)]      # can board, k rides done
    rptr = [dict() for _ in range(R + 1)]
    arrive = [[INF] * n for _ in range(R + 1)]     # alighted, k rides done
    aptr = [dict() for _ in range(R + 1)]
    for s, m in access.items():
        ready[0][s] = t0 + int(walk_s(m)) + entry_s
        rptr[0][s] = ("origin", m)

    trip_k = {}       # trip -> rides count while aboard
    trip_board = {}   # trip -> (board stop, board dep, prev level)
    best_target = INF
    c_dep, c_arr, c_from, c_to, c_trip = (feed.c_dep, feed.c_arr,
                                          feed.c_from, feed.c_to, feed.c_trip)
    fps = feed.footpaths
    horizon = t0 + MAX_JOURNEY_S
    i = bisect.bisect_left(c_dep, t0)
    nc = len(c_dep)
    while i < nc:
        dep = c_dep[i]
        if dep > horizon or dep > best_target:
            break
        t = c_trip[i]
        if mask is not None and not mask[t]:
            i += 1
            continue
        s = c_from[i]
        k = trip_k.get(t, INF)
        # board (or re-board with fewer rides) from the best ready level
        for lvl in range(0, min(k - 1, R)):
            if ready[lvl][s] <= dep:
                k = lvl + 1
                trip_k[t] = k
                trip_board[t] = (s, dep, lvl)
                break
        if k > R:
            i += 1
            continue
        u, a = c_to[i], c_arr[i]
        if a < arrive[k][u]:
            bs, bdep, blvl = trip_board[t]
            ptr = ("ride", t, bs, bdep, u, a, blvl)
            for lvl in range(k, R + 1):
                if a >= arrive[lvl][u]:
                    break
                arrive[lvl][u] = a
                aptr[lvl][u] = ptr
                if a + change_s < ready[lvl][u]:
                    ready[lvl][u] = a + change_s
                    rptr[lvl][u] = ("alight", u)
                for v, ws, wm in fps[u]:
                    tv = a + int(ws)
                    if tv < ready[lvl][v]:
                        ready[lvl][v] = tv
                        rptr[lvl][v] = ("walk", u, wm)
            if u in egress:
                tt = a + exit_s + int(walk_s(egress[u]))
                if tt < best_target:
                    best_target = tt
        i += 1

    out = []
    for k in range(1, R + 1):
        best = None
        for u, m in egress.items():
            a = arrive[k][u]
            if a >= INF:
                continue
            tt = a + exit_s + int(walk_s(m))
            if best is None or tt < best[0]:
                best = (tt, u)
        if best is None:
            continue
        chain = _unwind(k, best[1], aptr, rptr)
        if chain is not None:
            out.append((best[0], best[1], chain))
    return out


def _unwind(k: int, u: int, aptr, rptr):
    """Follow pointers back from alighting at u with <=k rides."""
    chain, guard = [], 0
    lvl, kind, stop = k, "alight", u
    while guard < 64:
        guard += 1
        if kind == "alight":
            p = aptr[lvl].get(stop)
            if p is None:
                return None
            _, t, bs, bdep, au, a, blvl = p
            chain.append(("ride", t, bs, bdep, au, a))
            lvl, stop = blvl, bs
            kind = "ready"
        else:
            p = rptr[lvl].get(stop)
            if p is None:
                return None
            if p[0] == "origin":
                chain.append(("access", stop, p[1]))
                chain.reverse()
                return chain
            if p[0] == "walk":
                chain.append(("xfer", p[1], stop, p[2]))
                stop = p[1]
            kind = "alight"
    return None


# --- leg / option assembly ------------------------------------------------
def _pt(feed: Feed, s: int) -> dict:
    return {"name": feed.names[s], "lat": feed.lats[s], "lon": feed.lons[s],
            "stop_id": feed.stop_ids[s]}


def _iso(day0: dt.datetime, sec: float) -> str:
    return (day0 + dt.timedelta(seconds=int(sec))).isoformat()


def _ride_stops(feed: Feed, t: int, bs: int, bdep: int, au: int, a: int):
    """Stops ridden on trip t from bs@bdep to au@a (connections are sorted
    by departure, so scan the trip's hops inside [bdep, a])."""
    lo = bisect.bisect_left(feed.c_dep, bdep)
    hi = bisect.bisect_right(feed.c_dep, a)
    hops = sorted((feed.c_dep[j], feed.c_from[j], feed.c_to[j])
                  for j in range(lo, hi) if feed.c_trip[j] == t)
    seq, started = [], False
    for d, s0, s1 in hops:
        if not started and s0 == bs and d == bdep:
            started = True
            seq.append(s0)
        if started:
            seq.append(s1)
            if s1 == au:
                break
    return seq or [bs, au]


def _build_option(feed: Feed, cfg: dict, chain: list, arrive_s: int,
                  alight: int, egress_m: float, o: tuple, d: tuple,
                  t0: int, day0: dt.datetime) -> dict:
    legs, walk_m, clock, rides = [], 0.0, t0, 0
    for step in chain:
        if step[0] == "access":
            s, m = step[1], step[2]
            ws = walk_s(m)
            legs.append({
                "type": "walk", "from": {"name": "Start", "lat": o[0], "lon": o[1]},
                "to": _pt(feed, s), "distance_m": round(m), "duration_s": round(ws),
                "geometry": {"type": "LineString",
                             "coordinates": [[o[1], o[0]], [feed.lons[s], feed.lats[s]]]}})
            walk_m += m
            clock = t0 + ws + cfg["entry_s"]
        elif step[0] == "xfer":
            a, b, m = step[1], step[2], step[3]
            legs.append({
                "type": "walk", "from": _pt(feed, a), "to": _pt(feed, b),
                "distance_m": round(m), "duration_s": round(walk_s(m)),
                "transfer": True,
                "geometry": {"type": "LineString",
                             "coordinates": [[feed.lons[a], feed.lats[a]],
                                             [feed.lons[b], feed.lats[b]]]}})
            walk_m += m
            clock += walk_s(m)
        else:
            _, t, bs, bdep, au, a = step
            seq = _ride_stops(feed, t, bs, bdep, au, a)
            dist = sum(haversine_m(feed.lats[x], feed.lons[x],
                                   feed.lats[y], feed.lons[y])
                       for x, y in zip(seq, seq[1:]))
            legs.append({
                "type": feed.kind, "line": feed.trip_line[t],
                "headsign": feed.trip_head[t] or feed.names[seq[-1]],
                "trip_id": feed.trip_ids[t],
                "from": _pt(feed, bs), "to": _pt(feed, au),
                "depart_at": _iso(day0, bdep), "arrive_at": _iso(day0, a),
                "wait_s": max(0, round(bdep - clock)),
                "duration_s": a - bdep, "stops": len(seq) - 1,
                "distance_m": round(dist),
                "geometry": {"type": "LineString",
                             "coordinates": [[feed.lons[x], feed.lats[x]] for x in seq]}})
            rides += 1
            clock = a
    legs.append({
        "type": "walk", "from": _pt(feed, alight),
        "to": {"name": "Destination", "lat": d[0], "lon": d[1]},
        "distance_m": round(egress_m), "duration_s": round(walk_s(egress_m)),
        "geometry": {"type": "LineString",
                     "coordinates": [[feed.lons[alight], feed.lats[alight]], [d[1], d[0]]]}})
    walk_m += egress_m

    if feed.kind == "bus":
        mode = "bus"
    else:
        mode = "metro" if walk_m <= METRO_WALK_M else "metro+walk"
    return {
        "mode": mode,
        "legs": legs,
        "duration_s": int(arrive_s - t0),
        "walk_m": round(walk_m),
        "transfers": rides - 1,
        "lines": [l["line"] for l in legs if l["type"] != "walk"],
        "depart_at": _iso(day0, t0),
        "arrive_at": _iso(day0, arrive_s),
        "duration_model": "gtfs",
        "source": "gtfs connection scan",
    }


def plan_feed(feed: Feed, from_lat: float, from_lon: float,
              to_lat: float, to_lon: float, depart_at=None) -> Optional[dict]:
    """Best journey on one feed, or None when it isn't credible."""
    cfg = FEEDS[feed.kind]
    when = _to_ist(depart_at)
    access = {i: m for m, i in feed.grid.within(from_lat, from_lon, cfg["access_m"])
              [:cfg["max_access"]]}
    egress = {i: m for m, i in feed.grid.within(to_lat, to_lon, cfg["access_m"])
              [:cfg["max_access"]]}
    if not access or not egress:
        return None

    midnight = when.replace(hour=0, minute=0, second=0, microsecond=0)
    t_now = int((when - midnight).total_seconds())
    # GTFS service days run past 24:00 — a 00:30 trip may be "24:30"
    # on yesterday's service day.
    tries = [(t_now, midnight)]
    if t_now < 4 * 3600:
        tries.insert(0, (t_now + 86400, midnight - dt.timedelta(days=1)))

    direct_walk_s = walk_s(haversine_m(from_lat, from_lon, to_lat, to_lon))
    for t0, day0 in tries:
        mask = _active_trips(feed, day0.date())
        found = _csa(feed, cfg, access, egress, t0, mask)
        if not found:
            continue
        arrive_s, alight, chain = min(
            found, key=lambda j: j[0] + TRANSFER_PENALTY_S *
            (sum(1 for c in j[2] if c[0] == "ride") - 1))
        if arrive_s - t0 >= direct_walk_s:
            return None           # walking the whole way is faster
        return _build_option(feed, cfg, chain, arrive_s, alight,
                             egress[alight], (from_lat, from_lon),
                             (to_lat, to_lon), t0, day0)
    return None


def plan_transit(from_lat: float, from_lon: float, to_lat: float,
                 to_lon: float, depart_at: Union[None, str, float,
                                                 dt.datetime] = None,
                 feeds: Optional[dict] = None) -> list:
    """Metro + bus options FROM -> TO leaving at `depart_at`.

    depart_at: aware/naive datetime (naive = IST), ISO string, epoch
    seconds, or None (now). Each option:
        {mode: 'metro'|'bus'|'metro+walk', legs: [...], duration_s,
         walk_m, transfers, lines, depart_at, arrive_at, ...}
    sorted fastest first; empty when no feed offers a credible trip.
    JSON-serialisable as-is (mount under /v2/plan).
    """
    feeds = default_feeds() if feeds is None else feeds
    out = []
    for kind in ("metro", "bus"):
        f = feeds.get(kind)
        if f is None:
            continue
        opt = plan_feed(f, from_lat, from_lon, to_lat, to_lon, depart_at)
        if opt is not None:
            out.append(opt)
    out.sort(key=lambda o: o["duration_s"])
    return out
