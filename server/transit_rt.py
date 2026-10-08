"""Realtime transit adapter — honest edition.

What Delhi actually publishes (probed 2026-10-03 from this box; full
evidence in docs/plan/transit-realtime.md):

  * OTD Delhi (Transport Dept + IIIT-D) serves one GTFS-RT feed,
    VehiclePositions for DTC + DIMTS cluster buses:
        GET https://otd.delhi.gov.in/api/realtime/VehiclePositions.pb?key=KEY
    -> 401 without a key. Keys are issued via the request form at
    https://otd.delhi.gov.in/data/realtime/ . Ours goes in env var
    ALIVE_OTD_API_KEY.
  * OTD offers NO TripUpdates feed   -> curl: 404
  * OTD offers NO ServiceAlerts feed (not documented; undocumented
    guesses 404 as well).
  * The 2020 community mirror (server.nikhilvj.co.in/delhirt) -> 404,
    host alive, archive gone.
  * Mobility Database worldwide catalog: zero realtime feeds in India.
  * DMRC publishes no public realtime feed of any kind.

So without an API key there is no usable realtime transit data for
Delhi — and this module says so. feed_status() reports every probed
source with its evidence; delays() / vehicle_positions() / alerts()
return honest empties; nothing fabricates a delay.

With a key, the pipeline is complete: refresh() polls the feed,
parse_feed() decodes GTFS-RT (a self-contained protobuf wire reader —
google.transit.gtfs_realtime_pb2 is used if installed, otherwise the
built-in decoder covers every field we surface), and the query
functions return real entities stamped with their source.

No network at import and none inside query functions: only refresh()
and feed_status(live=True) touch the wire.
"""
import os
import struct
import threading
import time
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(_HERE, "data", "gtfs")   # same cache transit_real fills
_UA = {"User-Agent": "alive-delhi-air (github.com/<owner>/Delhi-Air-108)"}

POLL_MIN_S = 15          # OTD regenerates the snapshot ~every 10 s
FETCH_TIMEOUT_S = 10
PROBE_TIMEOUT_S = 8
ENTITY_TTL_S = 120       # drop cached entities older than this

# --- sources ---------------------------------------------------------------
# Every row is a claim backed by a curl probe; `evidence` is what we saw,
# not what the internet says ought to be there.
SOURCES = {
    "otd_bus_vehicle_positions": {
        "url": "https://otd.delhi.gov.in/api/realtime/VehiclePositions.pb",
        "kind": "vehicle_positions",
        "operator": "DTC + DIMTS cluster buses (OTD Delhi, IIIT-D)",
        "auth": "query param 'key' — request form at "
                "https://otd.delhi.gov.in/data/realtime/",
        "env_key": "ALIVE_OTD_API_KEY",
        "recorded": {"status": "key-gated", "http_status": 401,
                     "checked_at": "2026-10-03"},
        "evidence": "2026-10-03 curl: HTTP 401 without key (nginx/1.18.0); "
                    "portal + request form return 200",
    },
    "otd_bus_trip_updates": {
        "url": "https://otd.delhi.gov.in/api/realtime/TripUpdates.pb",
        "kind": "trip_updates",
        "operator": "OTD Delhi",
        "auth": None,
        "env_key": "ALIVE_OTD_API_KEY",
        "recorded": {"status": "dead", "http_status": 404,
                     "checked_at": "2026-10-03"},
        "evidence": "2026-10-03 curl: HTTP 404 — OTD documents only "
                    "VehiclePositions.pb",
    },
    "community_mirror_nikhilvj": {
        "url": "https://server.nikhilvj.co.in/delhirt/VehiclePositions.pb",
        "kind": "vehicle_positions",
        "operator": "community mirror announced 2020, gtfs-realtime group",
        "auth": None,
        "env_key": None,
        "recorded": {"status": "dead", "http_status": 404,
                     "checked_at": "2026-10-03"},
        "evidence": "2026-10-03 curl: HTTP 404 — host alive, archive gone",
    },
    "dmrc_metro": {
        "url": None,
        "kind": "metro realtime",
        "operator": "DMRC",
        "auth": None,
        "env_key": None,
        "recorded": {"status": "dead", "http_status": None,
                     "checked_at": "2026-10-03"},
        "evidence": "DMRC publishes no public GTFS-RT; Mobility Database "
                    "catalog (1.18 MB CSV, 2026-10-03) lists zero realtime "
                    "feeds in India",
    },
}

_LOCK = threading.Lock()
_STATE = {
    "vehicles": [],        # parsed rows, each tagged with its feed
    "trip_updates": [],
    "alerts": [],
    "updated_at": 0.0,
    "last_poll": {},       # source -> epoch
    "probes": {},          # source -> live probe result (feed_status(live=True))
    "errors": [],
}


def _api_key(source: dict):
    env = source.get("env_key")
    return os.environ.get(env) if env else None


# --- protobuf wire reader ---------------------------------------------------
# GTFS-RT is plain protobuf; we only need a handful of fields, so a small
# wire-level decoder is enough and keeps the module dependency-free.

def _varint(buf, i):
    out, shift = 0, 0
    while True:
        if i >= len(buf):
            raise ValueError("truncated varint")
        b = buf[i]
        i += 1
        out |= (b & 0x7F) << shift
        if not b & 0x80:
            return out, i
        shift += 7
        if shift > 70:
            raise ValueError("varint too long")


def _fields(buf):
    """Yield (field_no, wire_type, value): int for varint, bytes for
    length-delimited, float for fixed32/64."""
    i, n = 0, len(buf)
    while i < n:
        tag, i = _varint(buf, i)
        fno, wt = tag >> 3, tag & 7
        if wt == 0:
            v, i = _varint(buf, i)
        elif wt == 1:
            v = struct.unpack_from("<d", buf, i)[0]
            i += 8
        elif wt == 2:
            ln, i = _varint(buf, i)
            if i + ln > n:
                raise ValueError("truncated field")
            v = bytes(buf[i:i + ln])
            i += ln
        elif wt == 5:
            v = struct.unpack_from("<f", buf, i)[0]
            i += 4
        else:
            raise ValueError(f"unsupported wire type {wt}")
        yield fno, wt, v


def _msg(buf):
    """field_no -> [values] for one embedded message. Non-bytes input
    (a field sent with the wrong wire type) decodes as empty — malformed
    structure is skipped, never fatal."""
    m = {}
    if not isinstance(buf, (bytes, bytearray)):
        return m
    for fno, wt, v in _fields(buf):
        m.setdefault(fno, []).append(v)
    return m


def _signed(v):
    """Negative int32/int64 arrive sign-extended to 64-bit varints."""
    return v - (1 << 64) if isinstance(v, int) and v >= 1 << 63 else v


def _s(m, fno):
    v = m.get(fno)
    if not v:
        return None
    try:
        return v[-1].decode("utf-8", "replace")
    except (UnicodeDecodeError, AttributeError):
        return None


def _last(m, fno):
    v = m.get(fno)
    return _signed(v[-1]) if v else None


def _trip_descriptor(buf):
    m = _msg(buf)
    return {
        "trip_id": _s(m, 1),
        "route_id": _s(m, 5),
        "direction_id": _last(m, 6),
        "start_time": _s(m, 2),
        "start_date": _s(m, 3),
    }


def _vehicle_descriptor(buf):
    m = _msg(buf)
    return {"id": _s(m, 1), "label": _s(m, 2), "license_plate": _s(m, 3)}


def _position(buf):
    m = _msg(buf)
    return {
        "lat": m[1][-1] if m.get(1) else None,
        "lon": m[2][-1] if m.get(2) else None,
        "bearing": m[3][-1] if m.get(3) else None,
        "speed": m[5][-1] if m.get(5) else None,
    }


def _stop_time_event(buf):
    m = _msg(buf)
    return {"delay_s": _last(m, 1), "time": _last(m, 2),
            "uncertainty": _last(m, 3)}


def _translated_text(buf):
    """First translation's text (TranslatedString)."""
    m = _msg(buf)
    for tr in m.get(1, []):
        tm = _msg(tr)
        t = _s(tm, 1)
        if t:
            return t
    return None


def _entity(m):
    """Flatten one FeedEntity into our row shapes; returns (kind, row)."""
    if m.get(4):                       # VehiclePosition
        vm = _msg(m[4][-1])
        trip = _trip_descriptor(vm[1][-1]) if vm.get(1) else {}
        veh = _vehicle_descriptor(vm[8][-1]) if vm.get(8) else {}
        pos = _position(vm[2][-1]) if vm.get(2) else {}
        return "vehicles", {
            "entity_id": _s(m, 1),
            "trip_id": trip.get("trip_id"),
            "route_id": trip.get("route_id"),
            "vehicle_id": veh.get("id"),
            "vehicle_label": veh.get("label") or veh.get("license_plate"),
            "lat": pos.get("lat"), "lon": pos.get("lon"),
            "bearing": pos.get("bearing"), "speed_mps": pos.get("speed"),
            "stop_id": _s(vm, 7),
            "timestamp": _last(vm, 5),
        }
    if m.get(3):                       # TripUpdate
        tm = _msg(m[3][-1])
        trip = _trip_descriptor(tm[1][-1]) if tm.get(1) else {}
        stops = []
        for stu in tm.get(2, []):
            sm = _msg(stu)
            stops.append({
                "stop_sequence": _last(sm, 1),
                "stop_id": _s(sm, 4),
                "arrival": _stop_time_event(sm[2][-1]) if sm.get(2) else None,
                "departure": _stop_time_event(sm[3][-1]) if sm.get(3) else None,
            })
        return "trip_updates", {
            "entity_id": _s(m, 1),
            "trip_id": trip.get("trip_id"),
            "route_id": trip.get("route_id"),
            "stop_time_updates": stops,
            "delay_s": _last(tm, 5),
            "timestamp": _last(tm, 4),
        }
    if m.get(5):                       # Alert
        am = _msg(m[5][-1])
        period = []
        for tr in am.get(1, []):
            rm = _msg(tr)
            period.append({"start": _last(rm, 1), "end": _last(rm, 2)})
        route_ids, stop_ids = [], []
        for sel in am.get(5, []):
            em = _msg(sel)
            r, st = _s(em, 2), _s(em, 5)
            if r:
                route_ids.append(r)
            if st:
                stop_ids.append(st)
        return "alerts", {
            "entity_id": _s(m, 1),
            "route_ids": route_ids, "stop_ids": stop_ids,
            "active_period": period,
            "header": _translated_text(am[10][-1]) if am.get(10) else None,
            "description": _translated_text(am[11][-1]) if am.get(11) else None,
        }
    return None, None


def _parse_wire(blob: bytes) -> dict:
    """Hand-rolled FeedMessage decode — the default backend."""
    top = _msg(blob)
    header = {}
    if top.get(1):
        hm = _msg(top[1][-1])
        header = {
            "version": _s(hm, 1),
            "incrementality": _last(hm, 2),
            "timestamp": _last(hm, 3),
        }
    out = {"header": header, "vehicles": [], "trip_updates": [], "alerts": []}
    for ent in top.get(2, []):
        kind, row = _entity(_msg(ent))
        if kind:
            out[kind].append(row)
    return out


def _parse_bindings(blob: bytes) -> dict:
    """Same output via google.transit.gtfs_realtime_pb2 when installed."""
    from google.transit import gtfs_realtime_pb2 as g
    fm = g.FeedMessage()
    fm.ParseFromString(blob)
    out = {"header": {
        "version": fm.header.gtfs_realtime_version or None,
        "incrementality": int(fm.header.incrementality),
        "timestamp": fm.header.timestamp or None,
    }, "vehicles": [], "trip_updates": [], "alerts": []}
    for e in fm.entity:
        if e.HasField("vehicle"):
            v = e.vehicle
            out["vehicles"].append({
                "entity_id": e.id or None,
                "trip_id": v.trip.trip_id or None,
                "route_id": v.trip.route_id or None,
                "vehicle_id": v.vehicle.id or None,
                "vehicle_label": v.vehicle.label or v.vehicle.license_plate or None,
                "lat": v.position.latitude if v.HasField("position") else None,
                "lon": v.position.longitude if v.HasField("position") else None,
                "bearing": v.position.bearing if v.HasField("position") else None,
                "speed_mps": v.position.speed if v.HasField("position") else None,
                "stop_id": v.stop_id or None,
                "timestamp": v.timestamp or None,
            })
        elif e.HasField("trip_update"):
            tu = e.trip_update
            stops = [{
                "stop_sequence": s.stop_sequence or None,
                "stop_id": s.stop_id or None,
                "arrival": {"delay_s": s.arrival.delay, "time": s.arrival.time or None,
                            "uncertainty": s.arrival.uncertainty}
                if s.HasField("arrival") else None,
                "departure": {"delay_s": s.departure.delay, "time": s.departure.time or None,
                              "uncertainty": s.departure.uncertainty}
                if s.HasField("departure") else None,
            } for s in tu.stop_time_update]
            out["trip_updates"].append({
                "entity_id": e.id or None,
                "trip_id": tu.trip.trip_id or None,
                "route_id": tu.trip.route_id or None,
                "stop_time_updates": stops,
                "delay_s": tu.delay or None,
                "timestamp": tu.timestamp or None,
            })
        elif e.HasField("alert"):
            a = e.alert
            out["alerts"].append({
                "entity_id": e.id or None,
                "route_ids": [s.route_id for s in a.informed_entity if s.route_id],
                "stop_ids": [s.stop_id for s in a.informed_entity if s.stop_id],
                "active_period": [{"start": p.start or None, "end": p.end or None}
                                  for p in a.active_period],
                "header": (a.header_text.translation[0].text
                           if a.header_text.translation else None),
                "description": (a.description_text.translation[0].text
                                if a.description_text.translation else None),
            })
    return out


def parse_feed(blob: bytes) -> dict:
    """GTFS-RT bytes -> {"header", "vehicles", "trip_updates", "alerts"}.

    Uses the official protobuf bindings when importable, otherwise the
    built-in wire decoder. Raises ValueError on malformed input; unknown
    fields are skipped.
    """
    if not isinstance(blob, (bytes, bytearray)) or not blob:
        raise ValueError("empty feed body")
    try:
        return _parse_bindings(bytes(blob))
    except ImportError:
        return _parse_wire(bytes(blob))
    except Exception as e:                    # protobuf DecodeError etc.
        raise ValueError(f"malformed feed: {e}") from e


# --- fetch / refresh --------------------------------------------------------
def _fetch(url: str, timeout: int = FETCH_TIMEOUT_S) -> bytes:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _source_url(name: str, source: dict):
    """URL to poll, or None when the source can't be used right now."""
    if not source.get("url"):
        return None, "no public feed URL exists"
    key = _api_key(source)
    if source.get("env_key") and source.get("auth") and not key:
        return None, "key-gated (set %s)" % source["env_key"]
    url = source["url"]
    if key:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}key={key}"
    return url, None


def probe_source(name: str, timeout: int = PROBE_TIMEOUT_S) -> dict:
    """One live check of a source. Records into _STATE['probes'].

    Key-gated sources are still GET unauthenticated: a live 401/403
    confirms the gate; anything else (404, 5xx, dead host) is real news."""
    source = SOURCES.get(name)
    if source is None:
        return {"status": "unknown", "detail": "not a declared source"}
    rec = {"checked_at": int(time.time()), "http_status": None}
    if not source.get("url"):
        rec.update(status="dead", detail="no public feed URL exists")
    else:
        url = source["url"]
        key = _api_key(source)
        if key:
            url += ("&" if "?" in url else "?") + "key=" + key
        try:
            req = urllib.request.Request(url, headers=_UA, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read(64)
                rec["http_status"] = r.status
            rec.update(status="reachable",
                       detail=f"HTTP {rec['http_status']}, "
                              f"{len(body)}+ bytes")
        except urllib.error.HTTPError as e:
            rec["http_status"] = e.code
            rec.update(status="key-gated" if e.code in (401, 403) else "dead",
                       detail=f"HTTP {e.code}")
        except Exception as e:
            rec.update(status="dead", detail=str(e)[:120])
    with _LOCK:
        _STATE["probes"][name] = rec
    return rec


def feed_status(live: bool = False, timeout: int = PROBE_TIMEOUT_S) -> dict:
    """{source: {status, evidence, http_status?, checked_at?, ...}}.

    live=False returns the recorded probe evidence (offline, instant).
    live=True re-checks every URL with a short timeout. Status words:
    reachable / key-gated / dead / unknown.
    """
    out = {}
    for name, src in SOURCES.items():
        rec = src["recorded"]
        row = {
            "kind": src["kind"],
            "operator": src["operator"],
            "auth": src["auth"],
            "evidence": src["evidence"],
            "status": rec["status"],
            "http_status": rec["http_status"],
            "checked_at": rec["checked_at"],
        }
        if _api_key(src) and src.get("url"):
            row["status"] = "unknown"        # key present: go look
            row["key_configured"] = True
        probe = _STATE["probes"].get(name) or (probe_source(name, timeout)
                                              if live else None)
        if probe:
            row.update(status=probe["status"],
                       http_status=probe.get("http_status"),
                       checked_at=probe.get("checked_at"),
                       detail=probe.get("detail"))
        out[name] = row
    return out


def refresh(timeout: int = FETCH_TIMEOUT_S) -> dict:
    """Poll every usable source, parse, replace the cache.

    Sources with no URL or no key are skipped with a recorded reason —
    never an error. Returns a per-source report for ops logging."""
    report = {}
    new = {"vehicles": [], "trip_updates": [], "alerts": []}
    now = time.time()
    for name, src in SOURCES.items():
        url, why = _source_url(name, src)
        if url is None:
            report[name] = {"skipped": why}
            continue
        # recorded-dead endpoints aren't polled every cycle; a live
        # re-probe (feed_status(live=True)) is how a revival is noticed
        if src["recorded"]["status"] == "dead" and not _api_key(src):
            report[name] = {"skipped": "recorded dead; re-probe via "
                                       "feed_status(live=True)"}
            continue
        last = _STATE["last_poll"].get(name, 0)
        if now - last < POLL_MIN_S:
            report[name] = {"skipped": "polled < %ds ago" % POLL_MIN_S}
            continue
        _STATE["last_poll"][name] = now
        try:
            blob = _fetch(url, timeout)
            parsed = parse_feed(blob)
        except Exception as e:
            report[name] = {"error": str(e)[:160]}
            _STATE["errors"].append(f"{name} -> {e}")
            continue
        for kind in new:
            for row in parsed[kind]:
                row["feed"] = name
                new[kind].append(row)
        report[name] = {"parsed": {k: len(parsed[k]) for k in new},
                        "header_timestamp": parsed["header"].get("timestamp")}
    with _LOCK:
        if any(r.get("parsed") for r in report.values()):
            _STATE.update(new, updated_at=now)
        _STATE["errors"] = _STATE["errors"][-10:]
    report["updated_at"] = _STATE["updated_at"]
    return report


def _fresh(rows):
    """Cached rows, dropped after ENTITY_TTL_S so stale positions die."""
    if time.time() - _STATE["updated_at"] > ENTITY_TTL_S:
        return []
    return rows


# --- queries (honest: empty means empty) ------------------------------------
def vehicle_positions(route_id: str = None) -> list:
    """Live bus positions. [] when no feed has supplied any — check
    feed_status() for why."""
    rows = _fresh(_STATE["vehicles"])
    if route_id:
        rows = [r for r in rows if r.get("route_id") == route_id]
    return [dict(r) for r in rows]


def delays(route_id: str = None) -> list:
    """Per-trip schedule delays from TripUpdates feeds.

    [] almost always today: OTD Delhi exposes no TripUpdates endpoint
    and DMRC has none — the basis is in status()["delays_basis"]. Rows
    carry delay_s per stop when a feed ever supplies them."""
    out = []
    for tu in _fresh(_STATE["trip_updates"]):
        if route_id and tu.get("route_id") != route_id:
            continue
        for stu in tu.get("stop_time_updates") or []:
            d = (stu.get("arrival") or {}).get("delay_s")
            if d is None:
                d = (stu.get("departure") or {}).get("delay_s")
            out.append({
                "trip_id": tu.get("trip_id"),
                "route_id": tu.get("route_id"),
                "stop_id": stu.get("stop_id"),
                "stop_sequence": stu.get("stop_sequence"),
                "delay_s": d,
                "feed": tu.get("feed"),
            })
        if not tu.get("stop_time_updates") and tu.get("delay_s") is not None:
            out.append({"trip_id": tu.get("trip_id"),
                        "route_id": tu.get("route_id"),
                        "stop_id": None, "stop_sequence": None,
                        "delay_s": tu["delay_s"], "feed": tu.get("feed")})
    return out


def alerts(route_id: str = None) -> list:
    """Service alerts. Same honesty rule as delays()."""
    rows = _fresh(_STATE["alerts"])
    if route_id:
        rows = [r for r in rows if route_id in r.get("route_ids", [])]
    return [dict(r) for r in rows]


def status() -> dict:
    """/health snapshot: what's real, what's missing, why it's empty."""
    feeds = feed_status(live=False)
    gated = [n for n, f in feeds.items() if f["status"] == "key-gated"]
    if gated:
        basis = ("no public feed usable: %s need an API key "
                 "(request at https://otd.delhi.gov.in/data/realtime/); "
                 "Delhi has no TripUpdates or DMRC realtime feed at all"
                 % ", ".join(gated))
    else:
        basis = "no public feed reachable"
    return {
        "sources": feeds,
        "cached": {"vehicles": len(_fresh(_STATE["vehicles"])),
                   "trip_updates": len(_fresh(_STATE["trip_updates"])),
                   "alerts": len(_fresh(_STATE["alerts"]))},
        "updated_at": _STATE["updated_at"],
        "delays_basis": basis,
        "errors": _STATE["errors"][-5:],
    }
