"""Shared plumbing for /v2 endpoints — one seam for the outside world.

Keeps coupling lazy and injectable so tests run fully offline:
`set_location()` swaps the Amazon client, `osrm_route` and
`field_refresh` are module attrs that monkeypatch cleanly.
"""
import os
import sys
from typing import Optional

import httpx

_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)

DELHI_CENTER = {"lat": 28.6139, "lon": 77.2090}
NCR_BBOX = (76.80, 28.20, 77.90, 28.95)  # lon/lat, same as airfield.BBOX

_http: Optional[httpx.AsyncClient] = None


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
    """First route from the public OSRM demo — identical URL/params to
    main.py's _osrm plus steps=true, so /v2 options carry a real turn
    list and the client never needs legacy /directions. The returned
    dict gains a normalized `steps` list (possibly empty — callers
    degrade honestly)."""
    url = (f"https://router.project-osrm.org/route/v1/{profile}/"
           f"{flon},{flat};{tlon},{tlat}")
    try:
        r = await http().get(url, params={
            "overview": "full", "geometries": "geojson",
            "alternatives": "false", "steps": "true",
        })
        r.raise_for_status()
        routes = r.json().get("routes", [])
        if not routes:
            return None
        rt = routes[0]
        rt["steps"] = osrm_steps(rt)
        return rt
    except Exception:
        return None
