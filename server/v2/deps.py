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
async def osrm_route(profile: str, flon: float, flat: float,
                     tlon: float, tlat: float) -> Optional[dict]:
    """First route from the public OSRM demo — identical URL/params to
    main.py's _osrm so behavior matches the endpoints the app knows.
    Kept local because importing main from here would double-load it
    when the app runs as `server.main`."""
    url = (f"https://router.project-osrm.org/route/v1/{profile}/"
           f"{flon},{flat};{tlon},{tlat}")
    try:
        r = await http().get(url, params={
            "overview": "full", "geometries": "geojson",
            "alternatives": "false", "steps": "false",
        })
        r.raise_for_status()
        routes = r.json().get("routes", [])
        return routes[0] if routes else None
    except Exception:
        return None
