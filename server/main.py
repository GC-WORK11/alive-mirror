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


@app.get("/route")
async def route(from_lat: float, from_lon: float, to_lat: float, to_lon: float,
                profile: str = "driving"):
    """Real route over the OSM road graph. profile: driving|cycling|walking."""
    prof = profile if profile in ("driving", "cycling", "walking") else "driving"
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
        options.append({
            "mode": prof,
            "distance_km": round(rt["distance"] / 1000, 1),
            "duration_min": round(rt["duration"] / 60),
            "duration_s": rt["duration"],
            "geometry": rt["geometry"],
        })

    exposure.compare(options, FIELD.value, FIELD.nearest_sample_km)
    return {"routes": options, "field": FIELD.status()}


@app.get("/aqi")
async def aqi(lat: float, lon: float):
    """Interpolated PM2.5 field value at a point, with provenance."""
    await FIELD.refresh(http())
    v = FIELD.value(lat, lon, "pm2_5")
    if v is None:
        return {"pm25": None, "error": "field unavailable"}
    return {
        "pm25": round(v, 1),
        "pm10": FIELD.value(lat, lon, "pm10"),
        "no2": FIELD.value(lat, lon, "nitrogen_dioxide"),
        "nearest_sample_km": round(FIELD.nearest_sample_km(lat, lon), 1),
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
