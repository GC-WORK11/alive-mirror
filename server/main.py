"""Delhi-Air-108 backend — geocoding search + routing for Delhi NCR.

Real data only: search proxies Photon (OpenStreetMap autocomplete),
routes come from OSRM on the real OSM road graph. No hardcoded places.
"""
import asyncio
import time
from typing import Optional

import httpx
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from airfield import FIELD
from fires import FIRES
from forecast import FORECAST
import exposure

app = FastAPI(title="Delhi-Air-108 API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

PHOTON = "https://photon.komoot.io/api/"
OSRM = "https://router.project-osrm.org/route/v1/driving/"

# Delhi NCR bounding box (lon/lat): covers Delhi + Noida + Gurugram + Ghaziabad + Faridabad
DELHI_CENTER = {"lat": 28.6139, "lon": 77.2090}
NCR_BBOX = "76.80,28.20,77.90,28.95"

_http: Optional[httpx.AsyncClient] = None


def http() -> httpx.AsyncClient:
    global _http
    if _http is None or _http.is_closed:
        _http = httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=4.0),
                                  headers={"User-Agent": "delhi-air-108/0.1 (hackathon)"})
    return _http


@app.get("/health")
async def health():
    return {"ok": True, "ts": time.time()}


@app.get("/search")
async def search(q: str = Query(min_length=1, max_length=200),
                 lat: Optional[float] = None, lon: Optional[float] = None,
                 limit: int = Query(default=8, le=15)):
    """Search-as-you-type over real OSM data, biased to Delhi NCR."""
    bias_lat = lat if lat is not None else DELHI_CENTER["lat"]
    bias_lon = lon if lon is not None else DELHI_CENTER["lon"]
    params = {
        "q": q, "limit": limit,
        "lat": bias_lat, "lon": bias_lon,
        "bbox": NCR_BBOX,
        "lang": "en",
    }
    try:
        r = await http().get(PHOTON, params=params)
        r.raise_for_status()
        feats = r.json().get("features", [])
    except httpx.HTTPError:
        return {"results": [], "error": "geocoder unavailable"}

    results = []
    for f in feats:
        p = f.get("properties", {})
        c = f.get("geometry", {}).get("coordinates", [None, None])
        if c[0] is None:
            continue
        name = p.get("name") or p.get("street") or ""
        parts = [p.get(k) for k in ("street", "district", "city", "state") if p.get(k)]
        subtitle = ", ".join(dict.fromkeys(parts))  # dedupe, keep order
        results.append({
            "name": name,
            "subtitle": subtitle,
            "lat": c[1], "lon": c[0],
            "kind": p.get("osm_value") or p.get("type") or "place",
        })
    return {"results": results}


# exposure microenv keys the scorer understands (exposure.py MICROENV)
VEHICLE_TO_EXPOSURE = {
    "car": "driving_car_ac", "car_ac": "driving_car_ac",
    "car_open": "driving_car_open", "bike": "driving_two_wheeler",
    "two_wheeler": "driving_two_wheeler", "scooter": "driving_two_wheeler",
    "auto": "auto_rickshaw", "rickshaw": "auto_rickshaw",
    "bus": "bus", "cycle": "cycling", "walk": "walking",
}


@app.get("/route")
async def route(from_lat: float, from_lon: float, to_lat: float, to_lon: float,
                profile: str = "driving", vehicle: Optional[str] = None):
    """Real route over the OSM road graph + inhaled-PM2.5 dose per option.

    profile: driving|cycling|walking (OSRM). vehicle refines the
    microenvironment for dose math: car|car_open|bike|auto|bus|cycle|walk.
    """
    prof = profile if profile in ("driving", "cycling", "walking") else "driving"
    exposure_mode = VEHICLE_TO_EXPOSURE.get((vehicle or "").lower()) or \
        ("driving_car_ac" if prof == "driving" else prof)
    url = f"https://router.project-osrm.org/route/v1/{prof}/{from_lon},{from_lat};{to_lon},{to_lat}"
    try:
        r = await http().get(url, params={
            "overview": "full", "geometries": "geojson",
            "alternatives": "true", "steps": "false",
        })
        r.raise_for_status()
        data = r.json()
    except httpx.HTTPError:
        return {"routes": [], "error": "router unavailable"}

    await FIELD.refresh(http())

    options = []
    for rt in data.get("routes", [])[:3]:
        dur_s = _scaled_duration_s(vehicle or "", prof, rt)
        options.append({
            "mode": exposure_mode,
            "distance_km": round(rt["distance"] / 1000, 1),
            "duration_min": round(dur_s / 60),
            "duration_s": dur_s,
            "duration_model": "osrm" if prof == "driving" and VEHICLE_TIME_FACTOR.get(vehicle or "", 1.0) == 1.0 else "estimated",
            "geometry": rt["geometry"],
        })

    exposure.compare(options, FIELD.value, FIELD.nearest_sample_km)
    return {"routes": options, "field": FIELD.status()}


async def _osrm(profile: str, flon: float, flat: float, tlon: float, tlat: float):
    url = f"https://router.project-osrm.org/route/v1/{profile}/{flon},{flat};{tlon},{tlat}"
    r = await http().get(url, params={
        "overview": "full", "geometries": "geojson",
        "alternatives": "false", "steps": "false",
    })
    r.raise_for_status()
    routes = r.json().get("routes", [])
    return routes[0] if routes else None


# every consumer mode, scored on the geometry that mode actually travels
COMPARE_MODES = [
    ("driving", "car", "Car (AC)"),
    ("driving", "car_open", "Car (windows down)"),
    ("driving", "bike", "Bike / scooter"),
    ("driving", "auto", "Auto-rickshaw"),
    ("driving", "bus", "Bus"),
    ("cycling", "cycle", "Bicycle"),
    ("walking", "walk", "On foot"),
]


@app.get("/compare")
async def compare_modes(from_lat: float, from_lon: float, to_lat: float, to_lon: float):
    """Inhaled-PM2.5 dose for the SAME trip across every travel mode.

    The screen the product exists for: one from→to, every option ranked
    by what you actually breathe, with the same honesty envelope.
    """
    drive, cycle, walk = await asyncio.gather(
        _osrm("driving", from_lon, from_lat, to_lon, to_lat),
        _osrm("cycling", from_lon, from_lat, to_lon, to_lat),
        _osrm("walking", from_lon, from_lat, to_lon, to_lat),
        return_exceptions=True,
    )
    geoms = {"driving": drive, "cycling": cycle, "walking": walk}
    if isinstance(geoms["driving"], BaseException):
        return {"options": [], "error": "router unavailable"}

    await FIELD.refresh(http())
    options = []
    for profile, vehicle, label in COMPARE_MODES:
        rt = geoms[profile]
        if rt is None or isinstance(rt, BaseException):
            continue
        dur_s = _scaled_duration_s(vehicle, profile, rt)
        options.append({
            "vehicle": vehicle,
            "label": label,
            "mode": VEHICLE_TO_EXPOSURE[vehicle],
            "distance_km": round(rt["distance"] / 1000, 1),
            "duration_min": round(dur_s / 60),
            "duration_s": dur_s,
            "duration_model": "osrm" if profile == "driving" and VEHICLE_TIME_FACTOR.get(vehicle, 1.0) == 1.0 else "estimated",
            "geometry": rt["geometry"],
        })

    exposure.compare(options, FIELD.value, FIELD.nearest_sample_km)
    best = options[0] if options else None
    return {
        "options": options,
        "best": best.get("vehicle") if best else None,
        "field": FIELD.status(),
    }


VEHICLE_PROFILE = {"car": "driving", "car_open": "driving", "bike": "driving",
                   "auto": "driving", "bus": "driving",
                   "cycle": "cycling", "walk": "walking"}

# The public OSRM demo server only computes the driving graph — cycling
# and walking come back with car durations/geometry. Real durations are
# therefore distance/speed estimates with typical Delhi urban speeds;
# riding-mode factors scale the car time (signals, stops, weaving).
# These are stated assumptions, reported as duration_model="estimated".
MODE_SPEED_KMH = {"cycling": 15.0, "walking": 5.0}
VEHICLE_TIME_FACTOR = {"car": 1.0, "car_open": 1.0, "bike": 0.9,
                       "auto": 1.25, "bus": 1.6}


def _scaled_duration_s(vehicle: str, profile: str, rt: dict) -> float:
    if profile in MODE_SPEED_KMH:
        return rt["distance"] / 1000 / MODE_SPEED_KMH[profile] * 3600
    return rt["duration"] * VEHICLE_TIME_FACTOR.get(vehicle, 1.0)


@app.get("/depart")
async def depart(from_lat: float, from_lon: float, to_lat: float, to_lon: float,
                 vehicle: str = "auto", hours: int = Query(default=24, le=120)):
    """Leave-later optimizer: the same trip's inhaled dose per departure hour.

    Scores the route against the hourly forecast field (CAMS + stagnation
    physics). Assumes the trip completes within the departure hour —
    flagged honest in `window`.
    """
    exposure_mode = VEHICLE_TO_EXPOSURE.get(vehicle.lower())
    profile = VEHICLE_PROFILE.get(vehicle.lower())
    if not exposure_mode or not profile:
        return {"error": "unknown vehicle", "options": []}

    rt = await _osrm(profile, from_lon, from_lat, to_lon, to_lat)
    if rt is None or isinstance(rt, BaseException):
        return {"options": [], "error": "router unavailable"}

    await FORECAST.refresh(http())
    dur_s = _scaled_duration_s(vehicle, profile, rt)

    slots = []
    for h in range(hours):
        e = exposure.dose(rt["geometry"], dur_s, exposure_mode,
                          lambda la, lo, _h=h: FORECAST.pm25(la, lo, _h))
        if e["avg_conc_ugm3"] is None:
            continue
        idx = FORECAST.hour_index(h)
        slots.append({
            "hours_ahead": h,
            "start": FORECAST.time_at(idx) if idx is not None else None,
            "dose_ug": e["dose_ug"],
            "avg_conc_ugm3": e["avg_conc_ugm3"],
        })

    if not slots:
        return {"options": [], "error": "forecast unavailable", "forecast": FORECAST.status()}
    ordered = sorted(slots, key=lambda s: s["dose_ug"])
    now_slot = slots[0]
    best = ordered[0]
    saved = round(100 * (1 - best["dose_ug"] / now_slot["dose_ug"])) if now_slot["dose_ug"] else None
    return {
        "vehicle": vehicle, "mode": exposure_mode,
        "duration_min": round(dur_s / 60),
        "distance_km": round(rt["distance"] / 1000, 1),
        "now": now_slot,
        "best": best,
        "worst": ordered[-1],
        "ug_saved_vs_now": saved,
        "slots": slots,
        "forecast": FORECAST.status(),
    }


@app.get("/aqi")
async def aqi(lat: float, lon: float):
    """Interpolated PM2.5 field value at a point, with provenance."""
    await asyncio.gather(FIELD.refresh(http()), FIRES.refresh(http()))
    mod = FIRES.smoke_modifier()
    v = FIELD.value(lat, lon, "pm2_5")
    if v is None:
        return {"pm25": None, "error": "field unavailable"}
    return {
        "pm25": round(v * mod, 1),
        "pm25_ambient": round(v, 1),
        "pm10": FIELD.value(lat, lon, "pm10"),
        "no2": FIELD.value(lat, lon, "nitrogen_dioxide"),
        "nearest_sample_km": round(FIELD.nearest_sample_km(lat, lon), 1),
        "smoke_modifier": mod,
        "fire": FIRES.status(),
        "field": FIELD.status(),
    }


@app.get("/reverse")
async def reverse(lat: float, lon: float):
    try:
        r = await http().get("https://photon.komoot.io/reverse", params={"lat": lat, "lon": lon, "limit": 1})
        r.raise_for_status()
        feats = r.json().get("features", [])
        if feats:
            p = feats[0]["properties"]
            return {"name": p.get("name") or p.get("street") or "Dropped pin",
                    "subtitle": ", ".join(x for x in [p.get("district"), p.get("city")] if x)}
    except httpx.HTTPError:
        pass
    return {"name": "Dropped pin", "subtitle": ""}
