"""Real-GTFS transit layer — DMRC metro journeys + DTC bus-stop hints.

Replaces transit.py's hand-rolled 62-station graph with the actual feeds:

  metro  DMRC GTFS embedded in the `dmrc-rs` crate tarball
         (static.crates.io — public, no key): 263 stations, 37 route
         directions, ~128k stop_times, real track shapes.
  bus    DTC + DIMTS cluster-bus GTFS via the Mobility Database mirror
         (transitland delhi-bus.zip): ~6.3k stops, ~2.9k routes,
         ~3.3M stop_times.

Feeds are cached under data/gtfs/<feed>/ and re-fetched when the cache is
older than REFRESH_DAYS (a background thread does the fetch — requests
keep serving the stale copy meanwhile). Parsed indexes are pickled next
to the txt files so restarts skip the CSV pass.

Journey math: nearest GTFS stop to each endpoint, then Dijkstra over the
directed stop graph where every consecutive-stop link carries the MEDIAN
of its scheduled stop_times deltas (all trips in the feed). A line change
at an interchange costs TRANSFER_PENALTY_S. Edges with no timetable
sample fall back to haversine x METRO_FALLBACK_KMH — the honesty rule the
task states. Everything here stays additive over the synthetic contract:
same option shape, plus real names/lines/via/transfers.

If anything is missing or fails, callers fall back to the synthetic
model — the API contract never depends on this module having loaded.
"""
import csv
import heapq
import io
import json
import math
import os
import pickle
import statistics
import tarfile
import threading
import time
import urllib.request
import zipfile
import re
from typing import Callable, Optional

import exposure

# --- tuning ---------------------------------------------------------------
REFRESH_DAYS = 7
ACCESS_WAIT_S = 5 * 60          # board wait + entry, same as synthetic
TRANSFER_PENALTY_S = 6 * 60     # DMRC interchange walk, incl. escalators
METRO_FALLBACK_KMH = 33.0       # DMRC commercial speed when no stop_times
WALK_KMH = 5.0                  # same as transit.py
WALK_LINK_M = 350               # footpath transfers between distinct stops
MAX_ACCESS_KM = 2.5             # same honesty gate as transit.py
BUS_ACCESS_KM = 1.5             # credible walk to a bus stop
BUS_DIRECT_MAX = 3              # direct-route names to surface

_HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(_HERE, "data", "gtfs")

_UA = {"User-Agent": "alive108-delhi-air (github.com/<owner>/Delhi-Air-108)"}

# download sources, tried in order per feed. A source is (kind, url):
#   zip    — plain GTFS zip
#   crate  — rust crate tarball; GTFS txts live under <pkg>/dmrc-gtfs/
#   cratesio-api — resolves the newest dmrc-rs version, then a crate URL
SOURCES = {
    "metro": [
        ("cratesio-api", "https://crates.io/api/v1/crates/dmrc-rs"),
        ("crate", "https://static.crates.io/crates/dmrc-rs/"
                  "dmrc-rs-0.1.0.crate"),
    ],
    "bus": [
        ("zip", "https://storage.googleapis.com/storage/v1/b/mdb-latest/o/"
                "in-delhi-delhi-transport-corporation-gtfs-3139.zip?alt=media"),
        ("zip", "https://raw.githubusercontent.com/transitland/"
                "gtfs-archives-not-hosted-elsewhere/"
                "3db26c0092b6efeb1886a99b4fc0765122b0282b/delhi-bus.zip"),
    ],
}

NEEDED = ("stops.txt", "routes.txt", "trips.txt", "stop_times.txt")

_LOCK = threading.Lock()
_STATE = {"metro": None, "bus": None, "loading": False, "errors": [],
          "next_retry": 0.0}
RETRY_S = 300  # don't hammer mirrors when a feed failed/offline


# --- small helpers --------------------------------------------------------
def _clean_name(name: str) -> str:
    """GTFS short-hands to display names: 'Noida Sec -18' -> 'Noida Sector 18'."""
    n = re.sub(r"\bSec(?:tor)?\s*-?\s*(\d+)", r"Sector \1", name)
    n = re.sub(r"\s{2,}", " ", n).strip()
    return n


def _sec(t: str) -> Optional[int]:
    try:
        h, m, s = t.split(":")
        return int(h) * 3600 + int(m) * 60 + int(s)
    except Exception:
        return None


def _km(a_lat, a_lon, b_lat, b_lon) -> float:
    return exposure._haversine_m((a_lon, a_lat), (b_lon, b_lat)) / 1000.0


def _meta_path(feed: str) -> str:
    return os.path.join(CACHE_DIR, feed, "meta.json")


def _feed_age_s(feed: str) -> Optional[float]:
    try:
        with open(_meta_path(feed)) as fh:
            meta = json.load(fh)
        return time.time() - float(meta.get("fetched_at", 0))
    except Exception:
        try:  # manually-seeded cache: use the newest txt mtime
            mt = max(os.path.getmtime(os.path.join(_feed_dir(feed), f))
                     for f in NEEDED)
            return time.time() - mt
        except OSError:
            return None


def _feed_dir(feed: str) -> str:
    return os.path.join(CACHE_DIR, feed)


def _feed_ok(feed: str) -> bool:
    d = _feed_dir(feed)
    return all(os.path.exists(os.path.join(d, f)) for f in NEEDED)


# --- fetch ----------------------------------------------------------------
def _fetch(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _extract_zip(blob: bytes, dest: str) -> bool:
    zf = zipfile.ZipFile(io.BytesIO(blob))
    wrote = False
    for name in zf.namelist():
        base = os.path.basename(name)
        if base in NEEDED or base in ("shapes.txt", "agency.txt"):
            with zf.open(name) as src, \
                    open(os.path.join(dest, base), "wb") as out:
                out.write(src.read())
            wrote = True
    return wrote


def _extract_crate(blob: bytes, dest: str) -> bool:
    tf = tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz")
    wrote = False
    for m in tf.getmembers():
        base = os.path.basename(m.name)
        if m.isfile() and ("dmrc-gtfs" in m.name) and \
                (base in NEEDED or base in ("shapes.txt", "agency.txt")):
            src = tf.extractfile(m)
            if src:
                with open(os.path.join(dest, base), "wb") as out:
                    out.write(src.read())
                wrote = True
    return wrote


def _download_feed(feed: str) -> Optional[str]:
    """Try every source for the feed; return the URL that worked."""
    dest = _feed_dir(feed)
    os.makedirs(dest, exist_ok=True)
    for kind, url in SOURCES.get(feed, []):
        try:
            if kind == "cratesio-api":
                meta = json.loads(_fetch(url, timeout=20))
                ver = meta["crate"]["max_stable_version"] or \
                    meta["crate"]["newest_version"]
                url = ("https://static.crates.io/crates/dmrc-rs/"
                       f"dmrc-rs-{ver}.crate")
                blob = _fetch(url)
                ok = _extract_crate(blob, dest)
            elif kind == "crate":
                blob = _fetch(url)
                ok = _extract_crate(blob, dest)
            else:  # zip
                blob = _fetch(url)
                ok = _extract_zip(blob, dest)
            if ok:
                with open(_meta_path(feed), "w") as f:
                    json.dump({"fetched_at": time.time(),
                               "source": url}, f)
                return url
        except Exception as e:
            _STATE["errors"].append(f"{feed}:{url} -> {e}")
    return None


# --- parse / index --------------------------------------------------------
def _pkl_path(feed: str) -> str:
    return os.path.join(_feed_dir(feed), "_index.pkl")


def _pkl_fresh(feed: str) -> bool:
    try:
        pkl_t = os.path.getmtime(_pkl_path(feed))
        return all(os.path.getmtime(os.path.join(_feed_dir(feed), f)) <= pkl_t
                   for f in NEEDED)
    except OSError:
        return False


def _load_metro() -> Optional[dict]:
    """Stop graph: stops, directed edges w/ median seconds, shapes."""
    from collections import defaultdict
    d = _feed_dir("metro")
    try:
        stops = {}
        with open(os.path.join(d, "stops.txt")) as fh:
            for r in csv.DictReader(fh):
                stops[r["stop_id"]] = {
                    "name": _clean_name(r["stop_name"]),
                    "lat": float(r["stop_lat"]), "lon": float(r["stop_lon"]),
                }
        routes = {}
        with open(os.path.join(d, "routes.txt")) as fh:
            for r in csv.DictReader(fh):
                long_name = r.get("route_long_name") or r.get("route_short_name") or ""
                routes[r["route_id"]] = long_name.split("_")[0].title() or "Metro"
        trips = {}
        with open(os.path.join(d, "trips.txt")) as fh:
            for r in csv.DictReader(fh):
                trips[r["trip_id"]] = (r["route_id"], r.get("shape_id") or "")

        per_trip = defaultdict(list)
        with open(os.path.join(d, "stop_times.txt")) as fh:
            for r in csv.DictReader(fh):
                per_trip[r["trip_id"]].append(r)
        edge_times, edge_lines, edge_shape = defaultdict(list), defaultdict(set), {}
        for tid, rows in per_trip.items():
            rows.sort(key=lambda r: int(r["stop_sequence"]))
            line = routes.get(trips.get(tid, ("", ""))[0], "Metro")
            shape_id = trips.get(tid, ("", ""))[1]
            for i in range(len(rows) - 1):
                a, b = rows[i], rows[i + 1]
                ta, tb = _sec(a["departure_time"]), _sec(b["arrival_time"])
                if ta is None or tb is None:
                    continue
                dt = tb - ta
                if not (0 < dt < 1800):
                    continue
                key = (a["stop_id"], b["stop_id"])
                edge_times[key].append(dt)
                edge_lines[key].add(line)
                da, db = a.get("shape_dist_traveled"), b.get("shape_dist_traveled")
                if shape_id and da and db and key not in edge_shape:
                    try:
                        edge_shape[key] = (shape_id, float(da), float(db))
                    except ValueError:
                        pass

        shapes = {}
        sp = os.path.join(d, "shapes.txt")
        if os.path.exists(sp):
            tmp = defaultdict(list)
            with open(sp) as fh:
                for r in csv.DictReader(fh):
                    try:
                        tmp[r["shape_id"]].append(
                            (float(r["shape_dist_traveled"]),
                             float(r["shape_pt_lat"]), float(r["shape_pt_lon"])))
                    except (KeyError, ValueError):
                        continue
            shapes = {k: sorted(v) for k, v in tmp.items()}

        adj = defaultdict(list)
        edge_sec = {k: statistics.median(v) for k, v in edge_times.items()}
        for (a, b) in edge_sec:
            adj[a].append(b)

        # street-level transfers the feed models as separate stops
        # (e.g. Noida Sec-52 Blue <-> Noida Sector 51 Aqua, Sikanderpur
        # Yellow <-> Sikanderpur Rapid): a short walk link each way.
        walk_edges = set()
        ids = list(stops)
        for i, a in enumerate(ids):
            sa = stops[a]
            for b in ids[i + 1:]:
                sb = stops[b]
                d = _km(sa["lat"], sa["lon"], sb["lat"], sb["lon"])
                if 0 < d * 1000 < WALK_LINK_M:
                    sec = d / WALK_KMH * 3600.0
                    for x, y in ((a, b), (b, a)):
                        if y not in adj[x]:
                            adj[x].append(y)
                            edge_sec[(x, y)] = sec
                            edge_lines[(x, y)] = ["walk"]
                            walk_edges.add((x, y))

        return {
            "stops": stops, "adj": dict(adj),
            "edge_sec": edge_sec,
            "edge_lines": {k: sorted(v) for k, v in edge_lines.items()},
            "edge_shape": edge_shape, "shapes": shapes,
            "walk_edges": walk_edges,
        }
    except Exception as e:
        _STATE["errors"].append(f"metro parse -> {e}")
        return None


def _load_bus() -> Optional[dict]:
    """Bus index: stop list for nearest-search + route -> stop sequences."""
    from collections import defaultdict
    d = _feed_dir("bus")
    try:
        stops = {}
        with open(os.path.join(d, "stops.txt")) as fh:
            for r in csv.DictReader(fh):
                try:
                    stops[r["stop_id"]] = {
                        "name": _clean_name(r["stop_name"]),
                        "lat": float(r["stop_lat"]), "lon": float(r["stop_lon"]),
                    }
                except (KeyError, ValueError):
                    continue
        routes = {}
        with open(os.path.join(d, "routes.txt")) as fh:
            for r in csv.DictReader(fh):
                nm = (r.get("route_short_name") or
                      r.get("route_long_name") or "?").strip()
                # DTC names encode direction: "347AUP", "764MSTLDOWN"
                nm = re.sub(r"(UP|DOWN)$", "", nm) or nm
                routes[r["route_id"]] = nm
        trips = {}
        with open(os.path.join(d, "trips.txt")) as fh:
            for r in csv.DictReader(fh):
                trips[r["trip_id"]] = r["route_id"]

        per_trip = defaultdict(list)
        with open(os.path.join(d, "stop_times.txt")) as fh:
            for r in csv.DictReader(fh):
                per_trip[r["trip_id"]].append(
                    (int(r["stop_sequence"]), r["stop_id"]))

        route_seqs = defaultdict(list)
        seen_seq = defaultdict(set)
        for tid, rows in per_trip.items():
            rid = trips.get(tid)
            if rid is None:
                continue
            seq = tuple(s for _, s in sorted(rows))
            if seq and seq not in seen_seq[rid]:
                seen_seq[rid].add(seq)
                route_seqs[rid].append(seq)

        return {
            "stops": stops,
            "route_names": routes,
            "route_seqs": dict(route_seqs),
        }
    except Exception as e:
        _STATE["errors"].append(f"bus parse -> {e}")
        return None


def _load_feed(feed: str) -> Optional[dict]:
    """Parse a cached feed into memory, via pickle when still fresh."""
    if not _feed_ok(feed):
        return None
    pkl = _pkl_path(feed)
    if _pkl_fresh(feed):
        try:
            with open(pkl, "rb") as f:
                return pickle.load(f)
        except Exception:
            pass
    data = _load_metro() if feed == "metro" else _load_bus()
    if data is not None:
        try:
            with open(pkl, "wb") as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception:
            pass
    return data


def _bg_load() -> None:
    for feed in ("metro", "bus"):
        if _STATE.get(feed) is None:
            _STATE[feed] = _load_feed(feed)
    # refresh stale or missing feeds, then reload indexes
    for feed in ("metro", "bus"):
        stale = _feed_ok(feed) and (_feed_age_s(feed) or 1e12) > REFRESH_DAYS * 86400
        if not _feed_ok(feed) or stale:
            if _download_feed(feed):
                fresh = _load_feed(feed)
                if fresh is not None:
                    _STATE[feed] = fresh
    with _LOCK:
        _STATE["loading"] = False


def ensure_loaded() -> None:
    """Kick off the background load. Safe to call every request."""
    with _LOCK:
        if _STATE["loading"] or time.time() < _STATE["next_retry"]:
            return
        if _STATE["metro"] is not None and _STATE["bus"] is not None:
            return
        _STATE["loading"] = True
        _STATE["next_retry"] = time.time() + RETRY_S
    threading.Thread(target=_bg_load, daemon=True).start()


def _metro() -> Optional[dict]:
    ensure_loaded()
    return _STATE["metro"]


def _bus() -> Optional[dict]:
    ensure_loaded()
    return _STATE["bus"]


def status() -> dict:
    """Ops/debug snapshot — which feeds are live and from where."""
    out = {}
    for feed in ("metro", "bus"):
        meta = {}
        try:
            with open(_meta_path(feed)) as fh:
                meta = json.load(fh)
        except Exception:
            pass
        idx = _STATE.get(feed)
        out[feed] = {
            "loaded": idx is not None,
            "stops": len(idx["stops"]) if idx else 0,
            "age_h": round((_feed_age_s(feed) or 0) / 3600, 1),
            "source": meta.get("source"),
        }
    out["errors"] = _STATE["errors"][-5:]
    return out


# --- metro journey --------------------------------------------------------
def _nearest(stopmap: dict, lat: float, lon: float):
    best_sid, best_d = None, 1e9
    for sid, s in stopmap.items():
        d = _km(lat, lon, s["lat"], s["lon"])
        if d < best_d:
            best_sid, best_d = sid, d
    if best_sid is None:
        return None
    s = stopmap[best_sid]
    return (best_sid, s["name"], s["lat"], s["lon"], round(best_d, 3))


def _edge_geom(metro: dict, a: str, b: str,
               sa: dict, sb: dict) -> tuple:
    """(coords [[lon,lat]..], km) real track shape when the feed has one."""
    shp = metro["edge_shape"].get((a, b))
    if shp and shp[0] in metro["shapes"]:
        shape_id, da, db = shp
        pts = metro["shapes"][shape_id]
        if db > da:
            seg = [[lon, lat] for d, lat, lon in pts if da <= d <= db]
            if len(seg) >= 2:
                km = (db - da) / 1000.0
                return seg, max(km, _km(sa["lat"], sa["lon"],
                                        sb["lat"], sb["lon"]) * 0.9)
    return [[sa["lon"], sa["lat"]], [sb["lon"], sb["lat"]]], \
        _km(sa["lat"], sa["lon"], sb["lat"], sb["lon"])


def _path(metro: dict, a_sid: str, b_sid: str):
    """Dijkstra over (stop, line): cost = median ride s + transfer penalty.
    Returns (secs, [stop_ids], [lines per edge]) or None."""
    adj, edge_sec = metro["adj"], metro["edge_sec"]
    edge_lines = metro["edge_lines"]
    stops = metro["stops"]

    dist = {(a_sid, None): 0.0}
    prev = {}
    pq = [(0.0, a_sid, None)]
    done = set()
    goal = None
    while pq:
        cost, u, uline = heapq.heappop(pq)
        if (u, uline) in done:
            continue
        done.add((u, uline))
        if u == b_sid:
            goal = (u, uline)
            break
        for v in adj.get(u, []):
            sec = edge_sec.get((u, v))
            if sec is None:  # no timetable sample — haversine fallback
                sec = _km(stops[u]["lat"], stops[u]["lon"],
                          stops[v]["lat"], stops[v]["lon"]) \
                    / METRO_FALLBACK_KMH * 3600.0
            for line in edge_lines.get((u, v), ["Metro"]):
                # walk links are the transfer itself: entering one is free,
                # boarding the next line after it costs the penalty
                pen = 0.0 if line == "walk" else (
                    TRANSFER_PENALTY_S if (uline and uline != line) else 0.0)
                nc = cost + sec + pen
                st = (v, line)
                if nc < dist.get(st, 1e18):
                    dist[st] = nc
                    prev[st] = (u, uline)
                    heapq.heappush(pq, (nc, v, line))
    if goal is None:
        return None
    chain, lines = [], []
    st = goal
    while st != (a_sid, None):
        chain.append(st)
        st = prev[st]
        lines.append(chain[-1][1])
    chain.append((a_sid, None))
    chain.reverse()
    lines.reverse()
    ride_s = dist[goal]
    return ride_s, [s for s, _ in chain], lines


def metro_journey(from_lat: float, from_lon: float,
                  to_lat: float, to_lon: float) -> Optional[dict]:
    """Real-GTFS metro path board->alight, or None when not credible.

    Same honesty gate as the synthetic model: > MAX_ACCESS_KM from a real
    station -> the metro isn't for this trip.
    """
    m = _metro()
    if not m:
        return None
    sa = _nearest(m["stops"], from_lat, from_lon)
    sb = _nearest(m["stops"], to_lat, to_lon)
    if not sa or not sb or sa[4] > MAX_ACCESS_KM or sb[4] > MAX_ACCESS_KM:
        return None
    if sa[0] == sb[0]:
        return None

    found = _path(m, sa[0], sb[0])
    if not found:
        return None
    ride_s, path, lines = found

    # real track geometry + distance along each edge
    coords, track_km = [], 0.0
    for i in range(len(path) - 1):
        seg, km = _edge_geom(m, path[i], path[i + 1],
                             m["stops"][path[i]], m["stops"][path[i + 1]])
        track_km += km
        for c in seg:
            if not coords or c != coords[-1]:  # feed shapes repeat vertices
                coords.append(c)

    via = []
    for i in range(1, len(path) - 1):
        if lines[i] == lines[i - 1]:
            continue
        if lines[i - 1] == "walk":
            continue  # the walk edge itself already lists its endpoints
        if lines[i] == "walk":
            via.append(f"{m['stops'][path[i]]['name']} ⇄ "
                       f"{m['stops'][path[i + 1]]['name']} (walk)")
        else:
            via.append(m["stops"][path[i]]["name"])
    transfers = len(via)
    line_names = [l for l in lines if l != "walk"]
    line_names = [l for i, l in enumerate(line_names)
                  if i == 0 or line_names[i - 1] != l]

    dur_s = ride_s + ACCESS_WAIT_S
    return {
        "board": sa[1], "alight": sb[1],
        "board_lat": sa[2], "board_lon": sa[3], "access_km": sa[4],
        "alight_lat": sb[2], "alight_lon": sb[3], "egress_km": sb[4],
        "lines": line_names, "transfers": transfers, "via": via,
        "stops_ridden": len(path) - 1,
        "ride_s": ride_s, "duration_s": dur_s,
        "distance_km": round(track_km, 2),
        "geometry": {"type": "LineString", "coordinates": coords},
        "time_source": "gtfs stop_times medians",
    }


def nearest_stop(lat: float, lon: float, feed: str = "metro") -> Optional[tuple]:
    """(name, lat, lon, km) of nearest real stop in a loaded feed."""
    idx = _metro() if feed == "metro" else _bus()
    if not idx:
        return None
    n = _nearest(idx["stops"], lat, lon)
    if not n:
        return None
    return (n[1], n[2], n[3], n[4])


# --- bus hints ------------------------------------------------------------
def _direct_bus_routes(bus: dict, a_sid: str, b_sid: str) -> list:
    """Route names where one scheduled sequence serves A before B."""
    hits = []
    for rid, seqs in bus["route_seqs"].items():
        for seq in seqs:
            try:
                ia, ib = seq.index(a_sid), seq.index(b_sid)
            except ValueError:
                continue
            if ia < ib:
                hits.append(bus["route_names"].get(rid, "?"))
                break
    return hits[:BUS_DIRECT_MAX]


def bus_hint(from_lat: float, from_lon: float,
             to_lat: float, to_lon: float) -> Optional[dict]:
    """Nearest DTC/cluster stops to both ends + direct-route names."""
    b = _bus()
    if not b:
        return None
    sa = _nearest(b["stops"], from_lat, from_lon)
    sb = _nearest(b["stops"], to_lat, to_lon)
    if not sa or not sb or sa[4] > BUS_ACCESS_KM or sb[4] > BUS_ACCESS_KM:
        return None
    routes = _direct_bus_routes(b, sa[0], sb[0])
    return {
        "board_stop": sa[1], "board_km": sa[4],
        "alight_stop": sb[1], "alight_km": sb[4],
        "direct_routes": routes,
        "source": "DTC/DIMTS GTFS (Mobility Database mirror)",
    }


# warm the cache at import — cheap when pickled; downloads happen off-thread
ensure_loaded()
