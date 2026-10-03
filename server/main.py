"""Delhi-Air-108 backend — geocoding search + routing for Delhi NCR.

Real data only: search proxies Photon (OpenStreetMap autocomplete),
routes come from OSRM on the real OSM road graph. No hardcoded places.
"""
import asyncio
import math
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

# Sibling modules are flat imports — put this file's dir on sys.path so
# `import server.main` works from the repo root too, not just `cd server`.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

# local dev keys live in server/.env (gitignored) — real env vars always win
load_dotenv()

from airfield import FIELD, grap_indicative
from fires import FIRES
from blackspots import geojson as blackspots_geojson
from forecast import FORECAST
import transit
import exposure
import history
import segments
import grid
import community
import decide

from contextlib import asynccontextmanager


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    _start_ingest_loop()
    yield


app = FastAPI(title="Delhi-Air-108 API", lifespan=_lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

PHOTON = "https://photon.komoot.io/api/"
OSRM = "https://router.project-osrm.org/route/v1/driving/"

# Delhi NCR bounding box (lon/lat): covers Delhi + Noida + Gurugram + Ghaziabad + Faridabad
DELHI_CENTER = {"lat": 28.6139, "lon": 77.2090}
NCR_BBOX = "76.80,28.20,77.90,28.95"

_http: Optional[httpx.AsyncClient] = None
_BOOT_TS = time.time()


def http() -> httpx.AsyncClient:
    global _http
    if _http is None or _http.is_closed:
        _http = httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=4.0),
                                  headers={"User-Agent": "delhi-air-108/0.1 (hackathon)"})
    return _http


_calib_cache: dict = {}


def _calibration() -> Optional[dict]:
    """LOO accuracy numbers produced by calibrate.py — honest field error,
    served next to the field itself so any reader can check our claims."""
    if not _calib_cache:
        try:
            import json, os
            p = os.path.join(os.path.dirname(__file__), "data", "field_calibration.json")
            _calib_cache.update(json.load(open(p)))
        except (OSError, ValueError):
            return None
    return _calib_cache or None


_BUILD_SHA_CACHE: Optional[str] = None


def _build_sha() -> str:
    """BUILD_SHA env (CodeBuild stamps it) else the worktree's git sha."""
    global _BUILD_SHA_CACHE
    if _BUILD_SHA_CACHE:
        return _BUILD_SHA_CACHE
    sha = os.environ.get("BUILD_SHA", "").strip()
    if not sha:
        try:
            out = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, timeout=3,
                cwd=os.path.dirname(os.path.abspath(__file__)))
            if out.returncode == 0:
                sha = out.stdout.strip()
        except Exception:
            pass
    _BUILD_SHA_CACHE = sha or "unknown"
    return _BUILD_SHA_CACHE


@app.get("/health")
async def health():
    """Liveness + provenance: build sha, field age, per-source up/down."""
    try:
        fstat = FIELD.status()
    except Exception:
        fstat = {}
    try:
        fires_stat = FIRES.status()
    except Exception:
        fires_stat = {}
    loc_up = False
    try:
        from v2 import deps as _v2deps
    except ImportError:
        try:
            from server.v2 import deps as _v2deps
        except Exception:
            _v2deps = None
    if _v2deps is not None:
        try:
            _loc = _v2deps.get_location()
            loc_up = bool(_loc is not None and getattr(_loc, "enabled", False))
        except Exception:
            pass
    return {
        "ok": True,
        "ts": time.time(),
        "version": "v2",
        "build_sha": _build_sha(),
        "field_age_s": fstat.get("age_s"),
        "sources": {
            "model": {"up": bool(fstat.get("samples")),
                      "samples": fstat.get("samples", 0),
                      "source": fstat.get("source")},
            "stations": {"up": bool(fstat.get("station_readings")),
                         "count": fstat.get("station_readings", 0)},
            "fires": {"up": bool(fires_stat.get("fires")),
                      "fires": fires_stat.get("fires", 0),
                      "age_s": fires_stat.get("age_s")},
            "location": {"up": loc_up,
                         "key": "ALIVE_LOCATION_KEY" if loc_up else "unset"},
        },
        "history": history.summary(),
    }


_LOCATION = None
PLACE_INDEX = "alive108-places"


def _loc():
    """AWS Location Service client — same region as the task (ap-south-1),
    so geocoding round-trips are LAN-fast instead of a hop to Europe."""
    global _LOCATION
    if _LOCATION is None:
        import boto3
        _LOCATION = boto3.client("location", region_name="ap-south-1")
    return _LOCATION


def _hav_km(lat1, lon1, lat2, lon2):
    from math import radians, sin, cos, asin, sqrt
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * 6371 * asin(sqrt(a))


def in_ncr(lat: float, lon: float) -> bool:
    lo, la, hi, la2 = (float(x) for x in NCR_BBOX.split(","))
    return la <= lat <= la2 and lo <= lon <= hi


async def _aws_suggest(q: str, lat: float, lon: float, limit: int):
    """Amazon Location Suggest (HERE data) → normalized result rows.
    Suggestions may carry an embedded Place; ones that don't need GetPlace,
    fanned out in parallel. Returns [] on any failure."""
    try:
        resp = await asyncio.to_thread(
            _loc().search_place_index_for_suggestions,
            IndexName=PLACE_INDEX, Text=q, MaxResults=limit,
            Language="en", FilterCountries=["IND"],
            BiasPosition=[lon, lat],
        )
    except Exception:
        return []
    suggs = resp.get("Results", [])

    async def resolve(s):
        place = s.get("Place")
        if place is None and s.get("PlaceId"):
            try:
                resp = await asyncio.to_thread(
                    _loc().get_place, IndexName=PLACE_INDEX,
                    PlaceId=s["PlaceId"], Language="en")
                place = (resp or {}).get("Place")
            except Exception:
                place = None
        if not place:
            return None
        pt = (place.get("Geometry") or {}).get("Point")
        if not pt:
            return None
        label = place.get("Label") or s.get("Text") or ""
        parts = [x.strip() for x in label.split(",") if x.strip()]
        name = parts[0] if parts else label
        return {
            "name": name,
            "subtitle": ", ".join(parts[1:]),
            "lat": pt[1], "lon": pt[0],
            "kind": place.get("SubUnitType") or "place",
            "outside_ncr": not in_ncr(pt[1], pt[0]),
        }

    rows = await asyncio.gather(*(resolve(s) for s in suggs))
    return [r for r in rows if r]


async def _aws_reverse(lat: float, lon: float):
    """Amazon Location reverse-geocode → best named place near a point.
    Prefers street/neighbourhood-level places over businesses, so a drop
    pin says 'Rajpath, Connaught Place' not 'Shoots Photography'."""
    try:
        resp = await asyncio.to_thread(
            _loc().search_place_index_for_position,
            IndexName=PLACE_INDEX, Position=[lon, lat],
            MaxResults=10, Language="en")
    except Exception:
        return []
    cands = []
    for r in resp.get("Results", []):
        place = r.get("Place") or {}
        pt = (place.get("Geometry") or {}).get("Point")
        if not pt:
            continue
        dist = _hav_km(lat, lon, pt[1], pt[0])
        street = place.get("Street")
        hood = place.get("Neighborhood") or place.get("Municipality")
        if street or hood:
            rank = 0 if street else 1
            name = ", ".join(x for x in [street, hood] if x)
        else:
            rank = 2
            name = (place.get("Label") or "").split(",")[0].strip()
        if not name:
            continue
        sub = ", ".join(x for x in [
            place.get("Neighborhood"), place.get("Municipality"),
            place.get("Region"), place.get("Country")] if x)
        cands.append((rank, dist, name, sub))
    cands.sort(key=lambda t: (t[0], t[1]))
    return cands


async def _photon_search(q: str, lat: float, lon: float, limit: int, extra: dict):
    try:
        r = await http().get(PHOTON, params={
            "q": q, "limit": limit, "lat": lat, "lon": lon,
            "lang": "en", **extra,
        })
        r.raise_for_status()
        feats = r.json().get("features", [])
    except httpx.HTTPError:
        return []
    out = []
    for f in feats:
        p = f.get("properties", {})
        c = f.get("geometry", {}).get("coordinates", [None, None])
        if c[0] is None:
            continue
        name = p.get("name") or p.get("street") or ""
        parts = [p.get(k) for k in ("street", "district", "city", "state") if p.get(k)]
        out.append({
            "name": name,
            "subtitle": ", ".join(dict.fromkeys(parts)),
            "lat": c[1], "lon": c[0],
            "kind": p.get("osm_value") or p.get("type") or "place",
            "outside_ncr": not in_ncr(c[1], c[0]),
        })
    return out


@app.get("/search")
async def search(q: str = Query(min_length=1, max_length=200),
                 lat: Optional[float] = None, lon: Optional[float] = None,
                 limit: int = Query(default=8, le=15)):
    """Search-as-you-type: AWS Location Suggest (in-region, HERE India data)
    races Photon for redundancy; NCR results always rank ahead of wider
    India matches so Delhi-first still finds the rest of the country."""
    bias_lat = lat if lat is not None else DELHI_CENTER["lat"]
    bias_lon = lon if lon is not None else DELHI_CENTER["lon"]

    aws_t = asyncio.create_task(_aws_suggest(q, bias_lat, bias_lon, limit))
    ph_ncr_t = asyncio.create_task(
        _photon_search(q, bias_lat, bias_lon, limit, {"bbox": NCR_BBOX}))
    ph_in_t = asyncio.create_task(
        _photon_search(q, bias_lat, bias_lon, limit, {"countrycode": "IN"}))

    aws_res = await aws_t
    # AWS in-region is fast; Photon (Europe) is the slow path — give it a
    # short grace window only when AWS coverage is thin.
    grace = 0.35 if len(aws_res) >= 2 else 8.0
    done, pending = await asyncio.wait({ph_ncr_t, ph_in_t}, timeout=grace)
    ph_ncr = ph_ncr_t.result() if ph_ncr_t in done else []
    ph_in = ph_in_t.result() if ph_in_t in done else []
    for t in pending:
        t.cancel()

    merged, seen = [], set()
    for x in aws_res + ph_ncr + ph_in:
        key = (round(x["lat"], 4), round(x["lon"], 4), x["name"][:24].lower())
        if key in seen:
            continue
        seen.add(key)
        x["outside_ncr"] = not in_ncr(x["lat"], x["lon"])
        merged.append(x)

    merged.sort(key=lambda x: x["outside_ncr"])
    if merged:
        return {"results": merged[:limit]}
    return {"results": [], "error": "no matches"}


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

    exposure.compare(options, FIELD.value, FIELD.nearest_sample_km, FIELD.sigma)
    _annotate_segments(options)
    return {"routes": options, "field": FIELD.status()}


def _annotate_segments(options: list) -> None:
    """Per-option hot-zone decomposition for the route's colour ramp."""
    for o in options:
        if not o.get("geometry"):
            continue
        segs = segments.segment_doses(
            o["geometry"], o.get("duration_s", 0), o.get("mode", ""),
            FIELD.value)
        o["segments"] = segs
        o["hotspots"] = segments.hotspots(segs)


async def _osrm(profile: str, flon: float, flat: float, tlon: float, tlat: float):
    url = f"https://router.project-osrm.org/route/v1/{profile}/{flon},{flat};{tlon},{tlat}"
    r = await http().get(url, params={
        "overview": "full", "geometries": "geojson",
        "alternatives": "false", "steps": "false",
    })
    r.raise_for_status()
    routes = r.json().get("routes", [])
    return routes[0] if routes else None


async def _osrm_via(profile: str, pts: list[tuple[float, float]]):
    """Route through explicit via-points — used to synthesize alternative
    geometries the public OSRM demo won't return (it ignores alternatives)."""
    coords = ";".join(f"{lon},{lat}" for lon, lat in pts)
    url = f"https://router.project-osrm.org/route/v1/{profile}/{coords}"
    r = await http().get(url, params={
        "overview": "full", "geometries": "geojson", "steps": "false",
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

    exposure.compare(options, FIELD.value, FIELD.nearest_sample_km, FIELD.sigma)

    # metro arrives already scored per-leg — appending after compare()
    # keeps its walk legs from being billed at the underground 0.45 rate
    metro = transit.metro_option(from_lat, from_lon, to_lat, to_lon, FIELD.value)
    if metro:
        options.append(metro)
        _rerank(options)

    # real DTC/cluster bus-stop context when the GTFS cache is loaded —
    # additive `transit` key on bus options, no contract change
    transit.annotate_bus_hints(options, from_lat, from_lon, to_lat, to_lon)

    # quieter-road lever: synthesize alternates by re-routing through
    # points offset perpendicular to the corridor's midpoint, then keep
    # the best one if it inhales meaningfully less (the real 5-20%
    # route-choice lever published for Delhi)
    if isinstance(geoms["driving"], dict):
        car = next((o for o in options if o["vehicle"] == "car"), None)
        if car and car.get("exposure") and car["exposure"].get("dose_ug"):
            alt = await _quieter_route(from_lon, from_lat, to_lon, to_lat,
                                       geoms["driving"], car)
            if alt:
                options.append(alt)
                _rerank(options)

    _annotate_segments(options)

    best = options[0] if options else None
    return {
        "options": options,
        "best": best.get("vehicle") if best else None,
        "field": FIELD.status(),
    }


async def _quieter_route(flon, flat, tlon, tlat, base_rt, car_opt):
    """Probe via-point routes perpendicular to the direct path; return a
    'quieter rd' option when one beats the fastest route's dose by >=8%
    for <=25% extra time."""
    coords = base_rt["geometry"].get("coordinates", [])
    if len(coords) < 4:
        return None
    mid = coords[len(coords) // 2]
    dx, dy = tlon - flon, tlat - flat
    norm = math.hypot(dx, dy) or 1
    px, py = -dy / norm, dx / norm  # unit perpendicular in deg-space
    vias = [(mid[0] + px * k, mid[1] + py * k)
            for k in (0.011, -0.011, 0.02, -0.02)]  # ~1.2km / ~2.2km
    rts = await asyncio.gather(
        *[_osrm_via("driving", [(flon, flat), v, (tlon, tlat)]) for v in vias],
        return_exceptions=True,
    )
    base_dose = car_opt["exposure"]["dose_ug"]
    best = None
    for rt in rts:
        if not isinstance(rt, dict):
            continue
        dur_s = _scaled_duration_s("car", "driving", rt)
        if dur_s > car_opt["duration_s"] * 1.25:
            continue
        e = exposure.dose(rt["geometry"], dur_s, VEHICLE_TO_EXPOSURE["car"],
                          FIELD.value, FIELD.nearest_sample_km)
        if e.get("dose_ug") and e["dose_ug"] <= base_dose * 0.92:
            if best is None or e["dose_ug"] < best["exposure"]["dose_ug"]:
                best = {
                    "vehicle": "car", "label": "Car (AC) · quieter rd",
                    "mode": VEHICLE_TO_EXPOSURE["car"],
                    "distance_km": round(rt["distance"] / 1000, 1),
                    "duration_min": round(dur_s / 60), "duration_s": dur_s,
                    "duration_model": "osrm",
                    "geometry": rt["geometry"], "exposure": e,
                }
    return best


def _rerank(options: list) -> None:
    """Re-sort by dose_ug and refresh best/worst annotations — same math
    as exposure.compare, for options that carry a precomputed exposure."""
    scored = [o for o in options if (o.get("exposure") or {}).get("dose_ug") is not None]
    if not scored:
        return
    best = min(o["exposure"]["dose_ug"] for o in scored)
    worst = max(o["exposure"]["dose_ug"] for o in scored)
    for o in scored:
        e = o["exposure"]
        e["dose_vs_best_pct"] = round((e["dose_ug"] - best) / best * 100, 1) if best else 0.0
        e["ug_saved_vs_worst"] = round(worst - e["dose_ug"], 1)
    options.sort(key=lambda o: (o.get("exposure") or {}).get("dose_ug") or float("inf"))


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
    """Interpolated PM2.5 field value at a point, with provenance and the
    decade-climatology context: what this point usually reads, this month,
    this hour, per 9M measured station-hours."""
    await asyncio.gather(FIELD.refresh(http()), FIRES.refresh(http()))
    mod = FIRES.smoke_modifier()
    v = FIELD.value(lat, lon, "pm2_5")
    if v is None:
        return {"pm25": None, "error": "field unavailable"}
    sd = FIELD.sigma(lat, lon)  # krige std-dev → honest band, None on IDW

    ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    band = history.typical_band(lat, lon, ist.month, ist.hour)
    typical = band.get("median")
    return {
        "pm25": round(v * mod, 1),
        "pm25_ambient": round(v, 1),
        "pm25_lo": round(max(0.0, v - sd) * mod, 1) if sd else None,
        "pm25_hi": round((v + sd) * mod, 1) if sd else None,
        "pm10": FIELD.value(lat, lon, "pm10"),
        "no2": FIELD.value(lat, lon, "nitrogen_dioxide"),
        "o3": FIELD.value(lat, lon, "ozone"),
        "co": FIELD.value(lat, lon, "carbon_monoxide"),
        "so2": FIELD.value(lat, lon, "sulphur_dioxide"),
        "nh3": FIELD.value(lat, lon, "ammonia"),
        "us_aqi": FIELD.value(lat, lon, "us_aqi"),
        "european_aqi": FIELD.value(lat, lon, "european_aqi"),
        "dust": FIELD.value(lat, lon, "dust"),
        "aod": FIELD.value(lat, lon, "aerosol_optical_depth"),
        "conditions": FIELD.weather(),
        "nearest_sample_km": round(FIELD.nearest_sample_km(lat, lon), 1),
        "smoke_modifier": mod,
        "fire": FIRES.status(),
        "wind": FIELD.wind(),
        "grap": grap_indicative(v * mod),
        "field": FIELD.status(),
        "calibration": _calibration(),
        "typical": {
            "month": ist.month, "hour_ist": ist.hour,
            "median": typical, "p25": band.get("p25"), "p75": band.get("p75"),
            "vs_now_pct": round((v * mod - typical) / typical * 100, 1)
            if typical else None,
        } if typical is not None else None,
    }


@app.get("/today")
async def today(lat: float, lon: float):
    """24 hourly decade-typical PM2.5 medians at a point (IST hours) —
    the ledger screen's background curve."""
    ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    curve = history.diurnal_curve(lat, lon)
    return {
        "month": ist.month,
        "hour_now_ist": ist.hour,
        "hours_ist": curve,
        "source": "openaq-s3-climatology",
    }


class _ForecastSurface:
    """Forecast-backed drop-in for grid.as_geojson — pm25() answers per
    (lat, lon) hours-ahead; confidence still tracks live-sample distance
    (it measures geographic monitoring density, which a model horizon
    doesn't change)."""

    def __init__(self, hours_ahead: int):
        self._h = hours_ahead

    def value(self, lat: float, lon: float, param: str = "pm2_5") -> Optional[float]:
        return FORECAST.pm25(lat, lon, self._h)

    def nearest_sample_km(self, lat: float, lon: float) -> float:
        return FIELD.nearest_sample_km(lat, lon)


@app.get("/grid")
async def field_grid(cells: int = Query(default=22, le=40),
                     h: Optional[int] = Query(default=None, ge=0, le=120)):
    """The live PM2.5 surface as GeoJSON cells — the map's colour layer.
    ?h=N (0..120) scrubs the surface into the forecast horizon so the app
    can animate where the plume goes. Confidence per cell degrades with
    distance to the nearest sample."""
    if h is not None:
        await FORECAST.refresh(http())
        return grid.as_geojson(_ForecastSurface(h), cells)
    await FIELD.refresh(http())
    return grid.as_geojson(FIELD, cells)


@app.post("/observe")
async def observe_trip(body: dict):
    """Donate an anonymized traversal — commuters as the sensor network."""
    return community.observe(
        vehicle=str(body.get("vehicle", "unknown")),
        coords=body.get("coords") or [],
        duration_s=body.get("duration_s") or 0,
        dose_ug=body.get("dose_ug"),
        avoided_ug=body.get("avoided_ug"),
        contributor=body.get("contributor"),
    )


@app.post("/report")
async def hazard_report(body: dict):
    """User-flagged air observation: dust | smoke | burning | clean, 6h TTL."""
    return community.report(
        kind=str(body.get("kind", "")),
        lat=float(body.get("lat", 0)),
        lon=float(body.get("lon", 0)),
        contributor=body.get("contributor"),
    )


@app.get("/reports")
async def reports():
    return community.reports_geojson()


@app.get("/blackspots")
async def blackspots():
    """Official Delhi crash-prone zones (black spots) as GeoJSON points —
    Delhi Traffic Police Crash Report 2021's full 87-zone list plus IIT
    TRiPC 'Data to Action' high-risk sites and the annual DTP top-10 lists.
    Static data; severity + subtype flags (night/pedestrian/two-wheeler)
    ride along per point."""
    return blackspots_geojson()


@app.get("/fires")
async def fires():
    """Recent satellite fire detections over NCR + ~150km ring, GeoJSON
    points with satellite + confidence. No FIRMS key needed: reads the
    public FIRMS daily CSV snapshots (Suomi-NPP / NOAA-20 / NOAA-21 VIIRS
    + Terra/Aqua MODIS, rolling 24h), cached 6h. With FIRMS_MAP_KEY set it
    uses the keyed area API for the NW fire belt instead."""
    await FIRES.refresh(http())
    return FIRES.fires_geojson()


@app.get("/community")
async def community_totals():
    return community.totals()


@app.get("/escape")
async def escape(lat: float, lon: float, limit: int = Query(default=5, le=10)):
    """'Where is the air best near me right now' — scan the live field over
    NCR, drop cells within 3km of the user (that's still 'here'), rank the
    rest by PM2.5, reverse-name the best. Each answer carries its own
    data-confidence so thin regions don't fake certainty."""
    await FIELD.refresh(http())
    home_v = FIELD.value(lat, lon, "pm2_5")
    x0, y0, x1, y1 = grid.BBOX
    cand = []
    NX, NY = 16, 12
    for ix in range(NX):
        for iy in range(NY):
            cx = x0 + (ix + 0.5) * (x1 - x0) / NX
            cy = y0 + (iy + 0.5) * (y1 - y0) / NY
            d_km = 111.3 * math.hypot(cx - lon, (cy - lat) * math.cos(math.radians(lat)))
            if d_km < 3:
                continue
            v = FIELD.value(cy, cx, "pm2_5")
            if v is None:
                continue
            cand.append({"lat": round(cy, 4), "lon": round(cx, 4), "pm25": round(v, 1),
                         "dist_km": round(d_km, 1),
                         "confidence": FIELD.nearest_sample_km(cy, cx)})
    cand.sort(key=lambda c: c["pm25"])
    # honest answers only — on a flat-field day the "best" cells can read
    # worse than home; better to say "nowhere nearby is cleaner" than lie
    if home_v is not None:
        cand = [c for c in cand if c["pm25"] < home_v - 0.05]
    best = cand[:limit]
    for c in best:
        try:
            r = await http().get("https://photon.komoot.io/reverse",
                                 params={"lat": c["lat"], "lon": c["lon"], "limit": 1})
            feats = r.json().get("features", [])
            if feats:
                p = feats[0]["properties"]
                c["name"] = p.get("name") or p.get("district") or p.get("street")
        except httpx.HTTPError:
            pass
        conf = c.pop("confidence", None)
        c["data_km"] = round(conf, 1) if conf is not None else None
    if home_v is not None:
        for c in best:
            c["pct_less_than_here"] = round(100 * (1 - c["pm25"] / home_v))
    return {"here_pm25": round(home_v, 1) if home_v else None,
            "best": best, "none_cleaner": home_v is not None and not best}


@app.get("/decide")
async def decide_route(from_lat: float, from_lon: float, to_lat: float, to_lon: float):
    """The recommendation endpoint: same options as /compare, each scored
    safety-first (mode crash-risk tier) then dose then time, with a
    plain-English reason per option."""
    base = await compare_modes(from_lat, from_lon, to_lat, to_lon)
    if not base.get("options"):
        return base
    ranked = decide.rank(base["options"], FIELD.weather())
    return {
        "options": ranked["options"],
        "pick": ranked["decision"].get("label") if ranked["decision"] else None,
        "best": base.get("best"),
        "field": base.get("field"),
    }


@app.get("/shift")
async def shift(lat: float, lon: float, hours: float = 8.0,
                start_hour: Optional[int] = None,
                vehicle: str = "driving_two_wheeler"):
    """Occupational dose: what a driver/rider actually inhales across a
    work shift. For every shift hour, concentration = live field (hour 0)
    or decade-typical median scaled by today's live-vs-typical delta.
    vs_desk = same hours at an indoor/desk exposure basis (~35% ambient,
    rest ventilation) — the avoidable gap a gig driver pays daily."""
    hours = max(0.5, min(12.0, hours))
    await FIELD.refresh(http())
    ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    start = ist.hour if start_hour is None else max(0, min(23, start_hour))

    live = FIELD.value(lat, lon, "pm2_5")
    band0 = history.typical_band(lat, lon, ist.month, ist.hour)
    typ0 = band0.get("median")
    # how today's field sits vs the decade norm — applied to future hours
    adj = (live / typ0) if (live and typ0) else 1.0

    micro = exposure.MICROENV.get(vehicle, 1.0)
    ve_m3h = exposure.VENTILATION_LPM.get(vehicle, 9.0) / 1000.0 * 60.0
    # desk baseline: indoor office ~35% of ambient, resting ventilation
    desk_ve = 7.5 / 1000.0 * 60.0

    per_hour = []
    dose = desk = 0.0
    for i in range(int(hours * 2)):  # half-hour steps for smooth dose
        h = (start + i * 0.5) % 24
        hh = int(h)
        if i == 0 and live is not None:
            c = live
        else:
            t = history.typical(lat, lon, ist.month, hh)
            c = (t * adj) if t else live
        if c is None:
            continue
        dose += c * micro * ve_m3h * 0.5
        desk += c * 0.35 * desk_ve * 0.5
        if i % 2 == 0:
            per_hour.append({"hour_ist": hh, "conc_ugm3": round(c, 1)})

    cig = dose / 316.0  # Berkeley Earth equivalence, same as app ledger
    return {
        "vehicle": vehicle,
        "shift_hours": hours,
        "start_hour_ist": start,
        "dose_ug": round(dose, 1),
        "cig_equiv": round(cig, 1),
        "desk_dose_ug": round(desk, 1),
        "vs_desk_pct": round((dose / desk - 1) * 100) if desk else None,
        "per_hour": per_hour,
        "live_adjust": round(adj, 2),
        "note": ("dose model: ambient field × breathing-zone microenv × "
                 "minute ventilation; future hours = decade climatology × "
                 "today's live delta"),
        "field": FIELD.status(),
    }


def _admin_guard(request: Request):
    """Gate for /admin/api* — the ops dashboard's data surface.

    `ALIVE_ADMIN_TOKEN` set  → require `Authorization: Bearer <token>`.
    Unset                  → loopback clients only (dev default); a real
    deployment sits behind a LB, so remote callers get 403 until the
    operator sets the token. The /admin HTML page itself is public —
    it carries no data; every fetch it makes goes through this guard.
    """
    token = os.environ.get("ALIVE_ADMIN_TOKEN")
    if token:
        auth = request.headers.get("authorization", "")
        if auth != f"Bearer {token}":
            raise HTTPException(401, "admin token required")
        return
    host = request.client.host if request.client else ""
    if host not in ("127.0.0.1", "::1", "localhost", "testclient"):
        raise HTTPException(
            403, "admin api is loopback-only until ALIVE_ADMIN_TOKEN is set")


@app.get("/admin/api", dependencies=[Depends(_admin_guard)])
async def admin_api():
    """Live ops snapshot for the admin dashboard — anon ids only."""
    thirty_min = 30
    contributors = community.contributors_detail()
    return {
        "ts": time.time(),
        "uptime_s": round(time.time() - _BOOT_TS),
        "live_users": sum(1 for c in contributors
                        if c["last_seen_min_ago"] <= thirty_min),
        "field": FIELD.status(),
        "fire": FIRES.status(),
        "community": community.totals(),
        "corridors": community.corridors(10),
        "contributors": contributors,
        "recent_journeys": community.recent_obs(20),
        "reports": community.live_reports(),
        "journeys_per_hour": community.journeys_per_hour(),
    }


@app.get("/admin")
async def admin_page():
    from fastapi.responses import FileResponse
    import os
    return FileResponse(os.path.join(os.path.dirname(__file__), "admin.html"))


@app.get("/city")
async def city_page():
    """'The City Breathes' — the dark editorial surface (docs/24 §8):
    kriged field as wind-advected particles, the city's cigarette strip,
    corridor measurements. Judges land here; commuters never need to."""
    from fastapi.responses import FileResponse
    import os
    return FileResponse(os.path.join(os.path.dirname(__file__), "city.html"))


@app.get("/reverse")
async def reverse(lat: float, lon: float):
    """Best-matching named place near a point — AWS Location primary, Photon
    fallback; honest ('near X') when the closest named thing is far away."""
    aws = await _aws_reverse(lat, lon)
    if aws:
        rank, dist, name, sub = aws[0]
        if dist > 0.25:
            name = f"near {name}"
        return {"name": name, "subtitle": sub}

    try:
        r = await http().get("https://photon.komoot.io/reverse", params={
            "lat": lat, "lon": lon, "limit": 10, "lang": "en"})
        r.raise_for_status()
        feats = r.json().get("features", [])
    except httpx.HTTPError:
        feats = []
    if not feats:
        return {"name": "Dropped pin", "subtitle": ""}

    PREF = {"locality": 0, "neighbourhood": 0, "suburb": 0, "district": 0,
            "street": 1, "house_number": 2}
    cands = []
    for f in feats:
        p = f.get("properties", {})
        c = (f.get("geometry") or {}).get("coordinates") or [None, None]
        if c[0] is None:
            continue
        dist = _hav_km(lat, lon, c[1], c[0])
        rank = PREF.get(p.get("osm_value"), 3)
        cands.append((rank, dist, p))
    cands.sort(key=lambda t: (t[0], t[1]))
    rank, dist, p = cands[0]
    name = p.get("name") or p.get("street") or "Dropped pin"
    if dist > 0.25:
        name = f"near {name}"
    return {"name": name, "subtitle": ", ".join(
        x for x in [p.get("district"), p.get("city"), p.get("state")] if x)}


_ORDINAL = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th", 6: "6th"}


def _instruction(step: dict) -> str:
    """OSRM maneuver → a plain-English sentence, GMaps style."""
    m = step.get("maneuver") or {}
    t, mod = m.get("type", ""), m.get("modifier", "") or ""
    named = step.get("name") or step.get("ref") or ""
    road = named or "the road"
    onto = f" onto {road}" if named else ""
    if mod == "uturn":
        return f"Make a U-turn{onto}"
    if t == "depart":
        return f"Head {mod} on {road}" if mod and named else f"Head out{onto or ''}"
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


@app.get("/directions")
async def directions(from_lat: float, from_lon: float, to_lat: float, to_lon: float,
                     profile: str = "driving", vehicle: Optional[str] = None):
    """Turn-by-turn: OSRM maneuver steps rendered as plain-English
    instructions — the Google-Maps directions list, for any mode.
    vehicle scales the OSRM duration the same way /route does."""
    prof = profile if profile in ("driving", "cycling", "walking") else "driving"
    try:
        r = await http().get(
            f"https://router.project-osrm.org/route/v1/{prof}/"
            f"{from_lon},{from_lat};{to_lon},{to_lat}",
            params={"overview": "full", "geometries": "geojson",
                    "steps": "true", "alternatives": "false"})
        r.raise_for_status()
        routes = r.json().get("routes", [])
    except httpx.HTTPError:
        return {"steps": [], "error": "router unavailable"}
    if not routes:
        return {"steps": [], "error": "no route"}
    rt = routes[0]
    dur_s = _scaled_duration_s(vehicle or "", prof, rt)

    steps = []
    for leg in rt.get("legs", []):
        for st in leg.get("steps", []):
            ins = _instruction(st)
            if not ins:
                continue
            steps.append({
                "instruction": ins,
                "street": st.get("name") or "",
                "type": (st.get("maneuver") or {}).get("type", ""),
                "modifier": (st.get("maneuver") or {}).get("modifier") or "",
                "distance_m": round(st.get("distance", 0)),
                "duration_s": round(st.get("duration", 0)),
            })
    # keep at most 12 instructions, in route order — depart/arrive always
    # survive (they carry ~0 distance), longest middle legs fill the rest
    steps = [s for s in steps if s["type"] != "notification"]
    if len(steps) > 12:
        terminal = [s for s in steps if s["type"] in ("depart", "arrive")]
        middle = [s for s in steps if s["type"] not in ("depart", "arrive")]
        keep = {id(s) for s in sorted(middle, key=lambda s: -s["distance_m"])[:12 - len(terminal)]}
        keep.update(id(s) for s in terminal)
        steps = [s for s in steps if id(s) in keep]
    return {
        "distance_km": round(rt["distance"] / 1000, 1),
        "duration_min": round(dur_s / 60),
        "duration_s": dur_s,
        "geometry": rt["geometry"],
        "steps": steps,
    }


# --- /v2 API (docs/plan/05 §3) — additive mount; nothing above changes ---
try:
    from v2 import router as _v2_router
except ImportError:  # when imported as a package (import server.main)
    try:
        from server.v2 import router as _v2_router
    except Exception:
        _v2_router = None
except Exception:
    _v2_router = None
if _v2_router is not None:
    app.include_router(_v2_router)

# --- additive mounts (each degrades honestly when its piece is absent) ---
try:  # local Delhi PMTiles vector tiles — 503s until the archive exists
    import tiles as _tiles
except ImportError:
    try:
        from server import tiles as _tiles
    except Exception:
        _tiles = None
except Exception:
    _tiles = None
if _tiles is not None:
    app.include_router(_tiles.router)

try:  # aggregate-only admin API (k>=3 enforced inside)
    import admin_agg as _admin_agg
except ImportError:
    try:
        from server import admin_agg as _admin_agg
    except Exception:
        _admin_agg = None
except Exception:
    _admin_agg = None
if _admin_agg is not None:
    app.include_router(_admin_agg.router,
                       dependencies=[Depends(_admin_guard)])

try:  # /metrics + request logging
    import observability as _obs
    _obs.install(app)
except Exception:
    pass

try:  # rate limit + body cap + security headers (all env-tunable)
    import middleware as _mw
    _mw.attach(app)
except Exception:
    pass


# --- in-app air-index ingest (keeps the field real-time with zero traffic) ---
# FIELD.refresh() is request-driven — idle >45 min => stale serving. The ECS
# deploy runs ingest_worker as its own 15-min task (doc 05 §1); on a single
# box that task doesn't exist, so we run the same run_index_once() loop in a
# daemon thread. ALIVE_INGEST_IN_APP=0 disables (e.g. a box that already runs
# the worker container against the same snapshot dir).
def _start_ingest_loop() -> None:
    if os.environ.get("ALIVE_INGEST_IN_APP", "1").strip() in ("0", "false", "no"):
        return
    import threading

    import ingest_worker as _ingest

    def _on_result(_res: dict) -> None:
        try:  # a fresh snapshot may now be the freshest field — pick it up
            FIELD.load_snapshot()
        except Exception:
            pass

    t = threading.Thread(
        target=_ingest.run_forever,
        kwargs={"interval_s": _ingest.INDEX_PERIOD_S,
                "on_result": _on_result},
        name="alive-ingest", daemon=True)
    t.start()
