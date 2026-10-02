"""Delhi-Air-108 backend — geocoding search + routing for Delhi NCR.

Real data only: search proxies Photon (OpenStreetMap autocomplete),
routes come from OSRM on the real OSM road graph. No hardcoded places.
"""
import asyncio
import math
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from airfield import FIELD, grap_indicative
from fires import FIRES
from forecast import FORECAST
import transit
import exposure
import history
import segments
import grid
import community
import decide

app = FastAPI(title="Delhi-Air-108 API")
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


@app.get("/health")
async def health():
    return {"ok": True, "ts": time.time(), "history": history.summary()}


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

    exposure.compare(options, FIELD.value, FIELD.nearest_sample_km)

    # metro arrives already scored per-leg — appending after compare()
    # keeps its walk legs from being billed at the underground 0.45 rate
    metro = transit.metro_option(from_lat, from_lon, to_lat, to_lon, FIELD.value)
    if metro:
        options.append(metro)
        _rerank(options)

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

    ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    band = history.typical_band(lat, lon, ist.month, ist.hour)
    typical = band.get("median")
    return {
        "pm25": round(v * mod, 1),
        "pm25_ambient": round(v, 1),
        "pm10": FIELD.value(lat, lon, "pm10"),
        "no2": FIELD.value(lat, lon, "nitrogen_dioxide"),
        "us_aqi": FIELD.value(lat, lon, "us_aqi"),
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


@app.get("/community")
async def community_totals():
    return community.totals()


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


@app.get("/admin/api")
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
    }


@app.get("/admin")
async def admin_page():
    from fastapi.responses import FileResponse
    import os
    return FileResponse(os.path.join(os.path.dirname(__file__), "admin.html"))


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
