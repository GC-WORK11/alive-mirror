"""GET /v2/place/{id} and GET /v2/reverse — resolve + reverse-geocode.

Amazon-backed (geo-places GetPlace / ReverseGeocode) with small
in-memory caches; gazetteer ids resolve locally. Without
ALIVE_LOCATION_KEY the Amazon paths return 503 with an honest body —
never a silent empty result.
"""
import time
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from . import deps
from .gazetteer import GAZ

router = APIRouter()

_CACHE_TTL_S = 900.0
_CACHE_MAX = 512
_place_cache: dict = {}
_rev_cache: dict = {}


def _cache_get(cache: dict, key):
    hit = cache.get(key)
    if hit and time.time() - hit[0] < _CACHE_TTL_S:
        return hit[1]
    cache.pop(key, None)
    return None


def _cache_put(cache: dict, key, val) -> None:
    if len(cache) >= _CACHE_MAX:
        for k, _ in sorted(cache.items(), key=lambda kv: kv[1][0])[:64]:
            cache.pop(k, None)
    cache[key] = (time.time(), val)


def _loc_or_503():
    loc = deps.get_location()
    if loc is None or not getattr(loc, "enabled", False):
        return None, JSONResponse(status_code=503, content={
            "error": "amazon_location_disabled",
            "detail": "ALIVE_LOCATION_KEY is not configured on the server",
            "hint": "search results without an 'amz:' id resolve locally",
        })
    return loc, None


@router.get("/place/{pid}")
async def place(pid: str):
    """Resolve a suggestion id: `amz:<PlaceId>` via GetPlace (cached),
    `gaz:<idx>` from the bundled gazetteer."""
    if pid.startswith("gaz:"):
        try:
            idx = int(pid.split(":", 1)[1])
        except ValueError:
            return JSONResponse(status_code=404,
                                content={"error": "unknown place id"})
        row = GAZ.by_index(idx)
        if row is None:
            return JSONResponse(status_code=404,
                                content={"error": "unknown place id"})
        return {"id": pid, "name": row["name"], "subtitle": row["kind"],
                "lat": row["lat"], "lon": row["lon"],
                "kind": row["kind"], "source": "gazetteer"}

    if not pid.startswith("amz:"):
        return JSONResponse(status_code=404,
                            content={"error": "unknown place id scheme"})

    loc, err = _loc_or_503()
    if err is not None:
        return err
    key = pid.split(":", 1)[1]
    cached = _cache_get(_place_cache, key)
    if cached is not None:
        return cached
    try:
        p = await loc.get_place(key)
    except Exception:
        p = None
    if not p or p.get("lat") is None:
        return JSONResponse(status_code=404,
                            content={"error": "place not found", "id": pid})
    _cache_put(_place_cache, key, p)
    return p


def _name_reverse(items: list, lat: float, lon: float) -> Optional[dict]:
    """Pick the most useful name near a point: street/locality level
    over business names, 'near X' when the closest thing is >250 m away
    (same convention as /reverse in main.py)."""
    best = None
    for it in items:
        street, hood = it.get("street"), it.get("locality")
        if street or hood:
            name = ", ".join(x for x in [street, hood] if x)
            rank = 0 if street else 1
        else:
            name = (it.get("label") or it.get("title") or "").split(",")[0].strip()
            rank = 2
        if not name:
            continue
        d = it.get("distance_m")
        cand = (rank, d if d is not None else 9e9, name,
                it.get("label") or "", it)
        if best is None or cand[:2] < best[:2]:
            best = cand
    if best is None:
        return None
    rank, dist, name, label, it = best
    if dist and dist > 250:
        name = f"near {name}"
    return {"name": name, "subtitle": label if label != name else "",
            "lat": it.get("lat"), "lon": it.get("lon"),
            "distance_m": dist, "source": "amazon"}


@router.get("/reverse")
async def reverse(lat: float, lon: float):
    loc, err = _loc_or_503()
    if err is not None:
        return err
    ckey = (round(float(lat), 4), round(float(lon), 4))
    cached = _cache_get(_rev_cache, ckey)
    if cached is not None:
        return cached
    try:
        items = await loc.reverse_geocode(lat, lon, limit=10)
    except Exception:
        items = None
    if not items:
        return JSONResponse(status_code=404, content={
            "error": "no address found", "lat": lat, "lon": lon})
    out = _name_reverse(items, lat, lon) or {"name": "Dropped pin",
                                             "subtitle": ""}
    _cache_put(_rev_cache, ckey, out)
    return out
