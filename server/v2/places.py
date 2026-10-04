"""GET /v2/place/{id} and GET /v2/reverse — resolve + reverse-geocode.

/v2/reverse answers from the bundled gazetteer+corpus first (zero-key,
offline-capable): the nearest named place/address/street within
REV_MAX_M metres, distance reported honestly. Amazon Location is the
second path when ALIVE_LOCATION_KEY is configured; a 404 naming the
searched radius is the third — never a fabricated "Dropped pin" label.
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


# reverse-geocode radius: a named thing further away than this is not
# the pin's place — "no named place within 150m" beats guessing.
REV_MAX_M = 150.0

_ADDR_KINDS = {"addr:address", "addr:interpolation", "addr:place",
               "addr:subdistrict", "addr:city"}
_LOCALITY_KINDS = {"locality", "neighbourhood", "neighborhood",
                   "suburb", "village", "district", "quarter",
                   "landuse:residential"}
_LOCALITY_TOPS = ("place", "boundary", "landuse")


def _rev_rank(kind: str) -> int:
    """Street/address-level answers beat business names for a dropped
    pin (same convention as _name_reverse over Amazon items)."""
    if kind in _ADDR_KINDS or kind.startswith("highway:"):
        return 0
    if kind in _LOCALITY_KINDS or kind.split(":", 1)[0] in _LOCALITY_TOPS:
        return 1
    return 2


def _rev_subtitle(kind: str) -> str:
    if kind.startswith("addr:"):
        return "address"
    if kind.startswith("highway:"):
        return "street"
    return kind.split(":", 1)[-1].replace("_", " ")


def _gaz_reverse(lat: float, lon: float):
    """Nearest named corpus/gazetteer entry within REV_MAX_M, or None."""
    try:
        import core_engine
        hits = core_engine.nearest(lat, lon, REV_MAX_M)
    except Exception:
        hits = None
    if not hits:
        return None
    best = None  # (rank, dist) — class first, then distance
    for e, d in hits:
        cand = (_rev_rank(e.get("category") or ""), d)
        if best is None or cand < best[:2]:
            best = cand + (e,)
    if best is None:
        return None
    rank, d, e = best
    name = e["display"]
    if rank == 2:
        # a pin is never AT the poi — "near X" is the honest phrasing
        name = f"near {name}"
    return {"name": name,
            "subtitle": _rev_subtitle(e.get("category") or ""),
            "lat": e["lat"], "lon": e["lon"],
            "distance_m": round(d, 1),
            "kind": e.get("category") or "",
            "source": "gazetteer"}


@router.get("/reverse")
async def reverse(lat: float, lon: float):
    ckey = (round(float(lat), 4), round(float(lon), 4))
    cached = _cache_get(_rev_cache, ckey)
    if cached is not None:
        return cached

    # gazetteer first: the committed corpus names the nearest real
    # place with no credentials and no network dependency at all
    out = _gaz_reverse(lat, lon)

    # Amazon second — richer street-level addresses where configured
    if out is None:
        loc = deps.get_location()
        if loc is not None and getattr(loc, "enabled", False):
            try:
                items = await loc.reverse_geocode(lat, lon, limit=10)
            except Exception:
                items = None
            if items:
                out = (_name_reverse(items, lat, lon)
                       or {"name": "Dropped pin", "subtitle": "",
                           "dropped_pin": True})

    if out is None:
        return JSONResponse(status_code=404, content={
            "error": f"no named place within {int(REV_MAX_M)}m",
            "lat": lat, "lon": lon, "dropped_pin": True})
    _cache_put(_rev_cache, ckey, out)
    return out
