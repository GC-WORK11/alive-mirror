"""Shared plumbing for /v2 endpoints — one seam for the outside world.

Keeps coupling lazy and injectable so tests run fully offline:
`set_location()` swaps the Amazon client, `osrm_route` and
`field_refresh` are module attrs that monkeypatch cleanly.
"""
import os
import sys
import time
from typing import Optional

import httpx

_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)

import upstreams  # noqa: E402

DELHI_CENTER = {"lat": 28.6139, "lon": 77.2090}
NCR_BBOX = (76.80, 28.20, 77.90, 28.95)  # lon/lat, same as airfield.BBOX

_http: Optional[httpx.AsyncClient] = None


# last observed routing-engine call — ops reads this instead of firing
# synthetic probes at the public demo server; written by every real call
OSRM_LAST: dict = {"at": None, "ok": None, "ms": None,
                   "err": None, "backend": None}


def _osrm_note(ok: bool, ms: float, err: Optional[str] = None,
               backend: Optional[str] = None) -> None:
    import time as _t
    OSRM_LAST.update({"at": _t.time(), "ok": ok, "ms": round(ms),
                      "err": err, "backend": backend})


def http() -> httpx.AsyncClient:
    global _http
    if _http is None or _http.is_closed:
        _http = httpx.AsyncClient(
            timeout=httpx.Timeout(8.0, connect=4.0),
            headers={"User-Agent": "alive108-v2/0.1"})
    return _http


# --- Amazon Location client (injectable seam) -------------------------------
_loc = None
_loc_loaded = False


def get_location():
    """The shared LocationClient, or None when the module can't load.
    Tests inject a fake via set_location()."""
    global _loc, _loc_loaded
    if not _loc_loaded:
        _loc_loaded = True
        try:
            import location_client
            _loc = location_client.LocationClient()
        except Exception:
            _loc = None
    return _loc


def set_location(client) -> None:
    """Inject a location client (or a fake with the same methods)."""
    global _loc, _loc_loaded
    _loc = client
    _loc_loaded = True


def location_enabled() -> bool:
    loc = get_location()
    return bool(loc is not None and getattr(loc, "enabled", False))


# --- live field ---------------------------------------------------------------
def field():
    from airfield import FIELD
    return FIELD


async def field_refresh() -> None:
    """Best-effort field refresh — never raises into a request path."""
    try:
        await field().refresh(http())
    except Exception:
        pass


def data_epoch() -> float:
    """Wall-clock stamp of the freshest field/forecast data a /v2
    payload would read right now. Fold it into response-cache keys: a
    mid-TTL refresh moves the epoch, so stale payloads invalidate on
    the refresh itself rather than outliving the cache TTL. 0.0 when
    no data has landed yet."""
    epoch = 0.0
    try:
        F = field()
        for attr in ("_fetched_at", "_snap_epoch"):
            v = float(getattr(F, attr, 0.0) or 0.0)
            if v > epoch:
                epoch = v
    except Exception:
        pass
    try:
        from forecast import FORECAST
        v = float(getattr(FORECAST, "_fetched_at", 0.0) or 0.0)
        if v > epoch:
            epoch = v
    except Exception:
        pass
    return epoch


class TTLCache:
    """Tiny expiring dict for /v2 response payloads.

    Every caller touches it from inside an async handler — plain dict
    ops on the event-loop thread, so no locking. Staleness is bounded
    by the TTL; callers that must invalidate sooner fold a data epoch
    into the key (see data_epoch()). Eviction: expired entries first,
    then insertion order — a cache that never grows past max_entries.
    """
    __slots__ = ("ttl_s", "max_entries", "_d")

    def __init__(self, ttl_s: float, max_entries: int = 64):
        self.ttl_s = float(ttl_s)
        self.max_entries = int(max_entries)
        self._d = {}

    def get(self, key):
        e = self._d.get(key)
        if e is None:
            return None
        exp, val = e
        if time.monotonic() > exp:
            self._d.pop(key, None)
            return None
        return val

    def put(self, key, val) -> None:
        if len(self._d) >= self.max_entries:
            now = time.monotonic()
            for k in [k for k, (x, _) in self._d.items() if now > x]:
                self._d.pop(k, None)
            while len(self._d) >= self.max_entries:
                self._d.pop(next(iter(self._d)))
        self._d[key] = (time.monotonic() + self.ttl_s, val)

    def clear(self) -> None:
        self._d.clear()


# --- routing (same upstream main.py uses) --------------------------------------
_ORDINAL = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th", 6: "6th"}


def _osrm_instruction(step: dict) -> str:
    """OSRM maneuver → a plain-English sentence (same rendering as
    main.py's _instruction — kept local so importing main never
    double-loads it)."""
    m = step.get("maneuver") or {}
    t, mod = m.get("type", ""), m.get("modifier", "") or ""
    named = step.get("name") or step.get("ref") or ""
    road = named or "the road"
    onto = f" onto {road}" if named else ""
    if mod == "uturn":
        return f"Make a U-turn{onto}"
    if t == "depart":
        return f"Head {mod} on {road}" if mod and named \
            else f"Head out{onto or ''}"
    if t == "arrive":
        return "You'll arrive"
    if t in ("roundabout", "rotary", "roundabout turn"):
        ex = _ORDINAL.get(m.get("exit") or 1, f"{m.get('exit')}th")
        return f"At the roundabout, take the {ex} exit{onto}"
    if t in ("on ramp", "off ramp"):
        return f"Take the {'ramp' if t == 'on ramp' else 'exit'}{onto}"
    if t == "merge":
        return f"Merge{onto}" if named else "Merge"
    if t == "continue":
        return f"Continue on {road}" if named else "Continue straight"
    if t == "fork":
        side = mod.replace("slight ", "") if mod else ""
        return f"Keep {side}{onto}" if side else f"Continue{onto}"
    if mod:
        if mod == "straight":
            return f"Continue{onto}" if named else "Continue straight"
        verb = "Bear" if mod.startswith("slight") else "Turn"
        return f"{verb} {mod.replace('slight ', '')}{onto}"
    return f"Continue{onto}" if named else "Continue"


def osrm_steps(rt: dict) -> list:
    """Route dict → normalized turn list for the client nav engine:
    [{instruction, distance_m, duration_s, lat, lon, type, modifier,
    street}]. Empty when the upstream reply carries no legs (then the
    caller emits honest endpoint-only steps)."""
    steps = []
    for leg in (rt or {}).get("legs") or []:
        for st in leg.get("steps") or []:
            ins = _osrm_instruction(st)
            if not ins:
                continue
            m = st.get("maneuver") or {}
            loc = m.get("location") or [None, None]
            steps.append({
                "instruction": ins,
                "street": st.get("name") or "",
                "type": m.get("type", ""),
                "modifier": m.get("modifier") or "",
                "distance_m": round(st.get("distance") or 0),
                "duration_s": round(st.get("duration") or 0),
                "lat": loc[1] if len(loc) >= 2 else None,
                "lon": loc[0] if len(loc) >= 2 else None,
            })
    return [s for s in steps if s["type"] != "notification"]


async def osrm_route(profile: str, flon: float, flat: float,
                     tlon: float, tlat: float) -> Optional[dict]:
    """OSRM route — self-hosted Delhi daemon first (geo lane:
    scripts/geo/run_stack.sh, ~2 ms local vs ~600 ms + rate limits on
    the public demo), public demo as the flagged fallback. steps=true
    always so /v2 options carry a real turn list. `source` says which
    backend answered — never silently.

    Bounds that keep a request from wedging the single worker: an OD
    outside the field's service area returns None WITHOUT fetching
    (public OSRM happily "routes" San Francisco→Delhi as 10,000 km /
    95k vertices — the dose loop over it is what killed the task), and
    any route longer than airfield.MAX_ROUTE_KM is discarded as
    unroutable for this product."""
    from airfield import in_service_area, MAX_ROUTE_KM
    if not (in_service_area(flat, flon) and in_service_area(tlat, tlon)):
        return None
    bases = []
    try:
        import routing_local as _rl
        bases.append((_rl._default._url_for(profile), "osrm-local"))
    except Exception:
        pass
    bases.append((upstreams.OSRM_PUBLIC, "osrm-public-demo"))
    import time as _t
    t0 = _t.monotonic()
    last_err = None
    for base, source in dict.fromkeys(bases):
        url = f"{base}/route/v1/{profile}/{flon},{flat};{tlon},{tlat}"
        try:
            r = await http().get(url, params={
                "overview": "full", "geometries": "geojson",
                "alternatives": "false", "steps": "true",
            }, **({"timeout": 3.0} if "local" in source else {}))
            r.raise_for_status()
            routes = r.json().get("routes", [])
            if not routes:
                last_err = "no routes"
                continue
            rt = routes[0]
            if float(rt.get("distance") or 0.0) / 1000.0 > MAX_ROUTE_KM:
                last_err = "over cap"
                continue  # path through oceans/ferries — not servable
            rt["steps"] = osrm_steps(rt)
            rt["source"] = source
            _osrm_note(True, (_t.monotonic() - t0) * 1000, backend=source)
            return rt
        except Exception as e:
            last_err = type(e).__name__
            continue
    _osrm_note(False, (_t.monotonic() - t0) * 1000, err=last_err)
    return None
