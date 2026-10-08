"""Alive backend — geocoding search + routing for Delhi NCR.

Real data only: search proxies Photon (OpenStreetMap autocomplete),
routes come from OSRM on the real OSM road graph. No hardcoded places.
"""
import asyncio
import concurrent.futures
import functools
import hashlib
import hmac
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
from fastapi.middleware.gzip import GZipMiddleware

# local dev keys live in server/.env (gitignored) — real env vars always win
load_dotenv()

from airfield import FIELD, grap_indicative, in_service_area, OUT_OF_AREA, \
    MAX_ROUTE_KM
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
import ingest_waqi

from contextlib import asynccontextmanager


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    _start_ingest_loop()
    _start_rollup_loop()
    _start_rollup_mirror()

    # Fires fetch lazily on the first /fires or /aqi hit — until then
    # /health honestly reports 0 and the ops board reads "no fires".
    # Warm the cache once at boot so the first dashboard view is real.
    async def _warm_fires():
        try:
            await FIRES.refresh(http())
        except Exception:
            pass
    asyncio.create_task(_warm_fires())
    # Same gap for the field itself: FIELD.refresh is request-driven,
    # so on a cold task no samples exist until the first /aqi — the
    # engine warm loop meanwhile logs "field serves no reads". A fresh
    # Fargate task measured graph-ready ~36 s vs field-ready ~96 s
    # (/ecs/alive108 2026-10-04): the gap was ~60 s of waiting for a
    # request to start the Open-Meteo fetch. Starting the same real
    # fetch at boot removes it — nothing fabricated, just earlier.
    async def _warm_field():
        try:
            await FIELD.refresh(http())
        except Exception:
            pass
    asyncio.create_task(_warm_field())
    # Same honesty gap for the forecast horizon: until the first
    # /depart or /v2/city refreshes it, /status reports a cold pipeline.
    async def _warm_forecast():
        try:
            await asyncio.wait_for(FORECAST.refresh(http()), timeout=15.0)
        except Exception:
            pass
    asyncio.create_task(_warm_forecast())
    # The transit graph has the same request-driven gap — and the worst
    # version of it: an image without feeds downloads ~120 MB of GTFS and
    # parses ~3.3M stop_times on first use (~1 min on a 1-vCPU task),
    # past the 12 s transit arm, so cold tasks answered
    # degraded:["transit"] until the pipeline landed (~60 min observed).
    # The deploy image now bakes data/gtfs (Dockerfile ->
    # tools/bake_gtfs.py), so this warm is a bounded index load. ensure_
    # loaded starts the fetch+parse at boot rather than on the first
    # request; when feeds are already on disk we finish the compile
    # BEFORE the service reports healthy. Nothing about readiness is
    # fabricated: with feeds still absent the plan arm degrades exactly
    # as before, and the retry loop below compiles them off-request as
    # soon as they land.
    try:
        import transit_real
        transit_real.ensure_loaded()
        if transit_real.feeds_on_disk():
            from transit_v2 import default_feeds
            await asyncio.wait_for(asyncio.to_thread(default_feeds),
                                   timeout=45.0)
    except Exception:
        pass

    async def _warm_transit():
        try:
            from transit_v2 import default_feeds
            for _ in range(36):      # ~6 min ceiling, same as _warm_engine
                feeds = await asyncio.to_thread(default_feeds)
                if {"metro", "bus"} <= set(feeds):
                    break
                await asyncio.sleep(10)
        except Exception:
            pass
    asyncio.create_task(_warm_transit())
    # Same request-driven gap for the community layer: _load() reads
    # the donated-trips state (S3 get_object, or the local file) on the
    # first /reports, /v2/trip or /v2/city call — that request pays the
    # fetch+parse inside its own budget. Warm it off-loop at boot.
    async def _warm_community():
        try:
            await asyncio.to_thread(community._load)
        except Exception:
            pass
    asyncio.create_task(_warm_community())
    # Same gap for the static data files: the gazetteer JSON (119k rows,
    # measured 2.5 s on a warm desktop — slower on a 0.5-vCPU task) is
    # parsed on the first /search·/v2/city, and the climatology gz on the
    # first /aqi·/shift·/city. Parse them off-loop at boot; the loaders
    # are unchanged — this only moves existing work earlier.
    async def _warm_static():
        try:
            from v2.gazetteer import GAZ
            import history
            await asyncio.to_thread(GAZ._load)
            await asyncio.to_thread(history._load)
            await asyncio.to_thread(community._name_rows)
            # The first-plan transit wart: compiled feeds still left the
            # very first CSA scan (+ lazy _Grid rebuild on pickled feeds)
            # to whoever's request arrived first. Run the plan arm's real
            # callable once on a canonical metro OD (India Gate→Gurugram)
            # on the transit pool — same work, just earlier; it fabricates
            # nothing a request wouldn't compute itself.
            from v2 import plan as _v2plan
            await asyncio.get_running_loop().run_in_executor(
                _v2plan._TRANSIT_EXEC,
                lambda: _v2plan._transit_options(
                    28.6129, 77.2295, 28.4593, 77.0724,
                    "car", None, None))
        except Exception:
            pass
    asyncio.create_task(_warm_static())
    # The exposure path engine prices itself lazily on the first
    # /v2/plan — and a cold field makes that first reweight find no
    # raster cells, so the first minute or two of plans honestly serve
    # no engine rows. Build the graph at boot and keep retrying the
    # reweight until the field serves (bounded; plans still degrade
    # honestly either way — never a fabricated row).
    async def _warm_engine():
        try:
            import routegraph
            from v2 import plan as _v2plan
            eng = await asyncio.to_thread(routegraph.path_engine)
            for _ in range(36):  # ~6 min ceiling
                await asyncio.to_thread(_v2plan._engine_reweight, eng)
                ep = getattr(eng, "edges_priced", 0)
                ep = ep() if callable(ep) else (ep or 0)
                if ep > 0:
                    break
                await asyncio.sleep(10)
            else:
                return
            # Priced isn't solved: the first real A* query lazy-builds its
            # traversal structures (~9 s on this box) and used to blow the
            # 8 s arm budget → degraded:["engine"] on the first request.
            # Burn the cold solve here instead — all five modes on a tiny
            # OD so no per-mode structure stays cold.
            def _warm_solve():
                for mode, _ in _v2plan.ENGINE_MODES:
                    try:
                        eng.query(28.6315, 77.2167, 28.6519, 77.1907, mode)
                    except Exception:
                        pass
            await asyncio.to_thread(_warm_solve)
        except Exception:
            pass
    asyncio.create_task(_warm_engine())
    # The landing page's aether + admin's field map both read /grid?cells=40
    # — a cold build costs ~7 s of krige on this box, paid by whoever asks
    # first each epoch. Re-prime the epoch-keyed cache in the background
    # whenever the epoch moves (field refresh or a new donation), so the
    # interp cost is amortized off the request path. Threaded — the GIL-free
    # krige work must not starve the health check.
    async def _warm_grid():
        last_ep = None
        while True:
            try:
                if getattr(FIELD, "_fetched_at", None):
                    ep = (FIELD._fetched_at, community._OBS_VERSION)
                    if ep != last_ep:
                        await asyncio.to_thread(
                            _grid_cached, ("l", 40, "pm2_5"), ep,
                            lambda ep=ep: _epoch_tagged(
                                grid.as_geojson(FIELD, 40, "pm2_5"), ep))
                        last_ep = ep
            except Exception:
                pass
            await asyncio.sleep(60)
    asyncio.create_task(_warm_grid())
    # The archive: the served field, recorded once per IST hour into
    # durable storage (archive.py — s3://{ALIVE_AIR_BUCKET}/archive/ +
    # data/archive/ mirror). 'Delhi breathes' becomes history, not just
    # forecast — /v2/archive replays it, basis:recorded. Each tick runs
    # the same request-driven FIELD.refresh a visitor would trigger, so
    # the snapshot stays aligned to the field's own 15-min cadence.
    # ALIVE_ARCHIVE=0 disables (tests; a box that archives elsewhere).
    async def _archive_loop():
        if os.environ.get("ALIVE_ARCHIVE", "1").strip() in \
                ("0", "false", "no"):
            return
        try:
            import archive as _archive
            await _archive.run_forever(FIELD, http)
        except Exception:
            pass
    asyncio.create_task(_archive_loop())
    yield


app = FastAPI(title="Alive API", lifespan=_lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
# the field layer is the fattest payload on the service — 784-cell
# GeoJSON compresses ~10x and every client sends Accept-Encoding.
# compresslevel 4 not 9: on a 1-vCPU task, level-9 costs ~800 ms of
# event-loop CPU per /v2/reach veil (3.5 MB) for 1.03 MB wire; level 4
# is ~11x cheaper CPU-side for ~1.14 MB — the wire is already >=1 MB,
# the loop time is what starves concurrent judges (measured Oct 5).
app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=4)

from upstreams import (OSRM_PUBLIC, PHOTON_API as PHOTON,
                       PHOTON_REVERSE)

# Delhi NCR bounding box (lon/lat): covers Delhi + Noida + Gurugram + Ghaziabad + Faridabad
DELHI_CENTER = {"lat": 28.6139, "lon": 77.2090}
NCR_BBOX = "76.80,28.20,77.90,28.95"

_http: Optional[httpx.AsyncClient] = None
_BOOT_TS = time.time()


def http() -> httpx.AsyncClient:
    global _http
    if _http is None or _http.is_closed:
        _http = httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=4.0),
                                  headers={"User-Agent": "alive/0.1 (hackathon)"})
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
    # GTFS readiness for the ops eye — feeds on disk + compiled indexes;
    # guarded like every other block here, None when the layer is absent.
    try:
        import health as _health
        transit_stat = _health.live_transit()
    except Exception:
        transit_stat = None
    # public-safe engine size — the landing's "edges priced" claim reads
    # the real graph instead of a frozen number (admin_agg does the same
    # read, this one ships no internals beyond counts)
    routing = {}
    try:
        import routegraph as _rg
        _eng = getattr(_rg, "_ENGINE", None)
        if _eng is not None:
            def _en(name):
                v = getattr(_eng, name, None)
                if v is None:
                    v = getattr(getattr(_eng, "g", None), name, None)
                return v() if callable(v) else v
            routing = {"loaded": True,
                       "edges": _en("n_edges"),
                       "edges_priced": _en("edges_priced")}
    except Exception:
        routing = {}
    return {
        "ok": True,
        "ts": time.time(),
        "version": "v2",
        "build_sha": _build_sha(),
        "routing": routing,
        "field_age_s": fstat.get("age_s"),
        "field_refresh_in_s": fstat.get("refresh_in_s"),
        "field_stale": fstat.get("stale"),
        "engine": fstat.get("engine"),
        "wind": fstat.get("wind"),
        "transit": transit_stat,
        "sources": {
            "model": {"up": bool(fstat.get("samples")),
                      "samples": fstat.get("samples", 0),
                      "source": fstat.get("source")},
            "stations": {"up": bool(fstat.get("station_readings")),
                         "count": fstat.get("station_readings", 0),
                         "source": fstat.get("stations_src"),
                         "feeds": fstat.get("stations_status")},
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

# boto3's location client is sync — request paths run it off the event
# loop via an executor, but NOT the shared default one: the cold-boot
# warm fleet squats that pool for the first minutes of a task, and
# /search + /reverse — the surfaces a judge touches first — would queue
# behind it for the whole window (executor-audit lane). Four workers
# cover the suggest + get_place fan-out + a concurrent reverse.
_AWS_EXEC = concurrent.futures.ThreadPoolExecutor(
    max_workers=4, thread_name_prefix="alive-aws")


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


def _finite_coords(*pts) -> bool:
    """FastAPI `x: float` happily coerces nan/inf query strings —
    non-finite coords crash inside the field/history lookups (int(nan)),
    so the lat/lon endpoints guard up front instead of 500ing."""
    return all(math.isfinite(v) for v in pts)


def in_ncr(lat: float, lon: float) -> bool:
    lo, la, hi, la2 = (float(x) for x in NCR_BBOX.split(","))
    return la <= lat <= la2 and lo <= lon <= hi


async def _aws_suggest(q: str, lat: float, lon: float, limit: int):
    """Amazon Location Suggest (HERE data) → normalized result rows.
    Suggestions may carry an embedded Place; ones that don't need GetPlace,
    fanned out in parallel. Returns [] on any failure."""
    try:
        resp = await asyncio.get_running_loop().run_in_executor(
            _AWS_EXEC, functools.partial(
                _loc().search_place_index_for_suggestions,
                IndexName=PLACE_INDEX, Text=q, MaxResults=limit,
                Language="en", FilterCountries=["IND"],
                BiasPosition=[lon, lat]))
    except Exception:
        return []
    suggs = resp.get("Results", [])

    async def resolve(s):
        place = s.get("Place")
        if place is None and s.get("PlaceId"):
            try:
                resp = await asyncio.get_running_loop(
                    ).run_in_executor(
                    _AWS_EXEC, functools.partial(
                        _loc().get_place, IndexName=PLACE_INDEX,
                        PlaceId=s["PlaceId"], Language="en"))
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
        resp = await asyncio.get_running_loop().run_in_executor(
            _AWS_EXEC, functools.partial(
                _loc().search_place_index_for_position,
                IndexName=PLACE_INDEX, Position=[lon, lat],
                MaxResults=10, Language="en"))
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
    if not (in_service_area(from_lat, from_lon)
            and in_service_area(to_lat, to_lon)):
        return {"routes": [], "error": OUT_OF_AREA}
    routes, backend = await _osrm_get(
        prof, f"{from_lon},{from_lat};{to_lon},{to_lat}",
        {"overview": "full", "geometries": "geojson",
         "alternatives": "true", "steps": "false"})
    if routes is None:
        return {"routes": [], "error": "router unavailable"}

    await _field_refresh_bounded()

    options = []
    for rt in routes[:3]:
        if float(rt.get("distance") or 0.0) / 1000.0 > MAX_ROUTE_KM:
            continue  # ocean-spanning "route" — not a servable option
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
    return {"routes": options, "field": FIELD.status(),
            "router_backend": backend}


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


OSRM_LOCAL = os.environ.get("OSRM_URL", "http://127.0.0.1:5001").rstrip("/")


def _osrm_base(profile: str) -> str:
    """Self-hosted Delhi daemon for this profile — per-profile env like
    routing_local (a self-hosted osrm-routed serves ONE profile and the
    port picks it), else OSRM_URL, else the conventional local port."""
    env = {"driving": "OSRM_URL_DRIVING", "cycling": "OSRM_URL_CYCLING",
           "walking": "OSRM_URL_WALKING"}.get(profile)
    override = os.environ.get(env) if env else None
    return (override or OSRM_LOCAL).rstrip("/")


async def _osrm_get(profile: str, coords: str, params: dict):
    """Self-hosted Delhi daemon first (task sidecar / scripts/geo
    run_stack.sh — ~ms local vs ~600 ms + rate limits on the public
    demo), public demo as the flagged fallback.
    Returns (routes, backend) or (None, err): backend is the honesty tag
    written to OSRM_LAST, never silently demo."""
    last_err = None
    for base, backend in ((_osrm_base(profile), "osrm-local"),
                          (OSRM_PUBLIC, "osrm-public-demo")):
        try:
            kw = {"timeout": float(os.environ.get(
                "OSRM_LOCAL_TIMEOUT", "3.0"))} if backend == "osrm-local" else {}
            r = await http().get(f"{base}/route/v1/{profile}/{coords}",
                                 params=params, **kw)
            r.raise_for_status()
            routes = r.json().get("routes", [])
            if not routes:
                last_err = "no routes"
                continue
            return routes, backend
        except Exception as e:
            last_err = type(e).__name__
            continue
    return None, last_err


def _osrm_note(ok: bool, ms: float, err: Optional[str] = None,
               backend: str = "osrm-public-demo") -> None:
    """Write into v2.deps' shared observation — one record for every
    real routing call across the API surface."""
    try:
        from v2 import deps as _d
    except Exception:
        try:
            from server.v2 import deps as _d
        except Exception:
            return
    _d.OSRM_LAST.update({"at": time.time(), "ok": ok,
                         "ms": round(ms), "err": err,
                         "backend": backend})


async def _osrm(profile: str, flon: float, flat: float, tlon: float, tlat: float):
    # OD outside the field's service area → no fetch at all: public OSRM
    # happily returns a 10,000 km / 95k-vertex SF→Delhi "route", and the
    # dose loop over it is what wedged the ECS task on E2E.
    if not (in_service_area(flat, flon) and in_service_area(tlat, tlon)):
        return None
    t0 = time.monotonic()
    routes, backend = await _osrm_get(
        profile, f"{flon},{flat};{tlon},{tlat}",
        {"overview": "full", "geometries": "geojson",
         "alternatives": "false", "steps": "false"})
    if routes is None:
        _osrm_note(False, (time.monotonic() - t0) * 1000, backend)
        raise ConnectionError(backend or "router unavailable")
    rt = routes[0]
    if float(rt.get("distance") or 0.0) / 1000.0 > MAX_ROUTE_KM:
        _osrm_note(True, (time.monotonic() - t0) * 1000, "over cap", backend)
        return None
    _osrm_note(True, (time.monotonic() - t0) * 1000, backend=backend)
    rt["source"] = backend
    return rt


async def _osrm_via(profile: str, pts: list[tuple[float, float]]):
    """Route through explicit via-points — used to synthesize alternative
    geometries the public OSRM demo won't return (it ignores alternatives)."""
    if pts and not (in_service_area(pts[0][1], pts[0][0])
                    and in_service_area(pts[-1][1], pts[-1][0])):
        return None
    coords = ";".join(f"{lon},{lat}" for lon, lat in pts)
    t0 = time.monotonic()
    routes, backend = await _osrm_get(
        profile, coords,
        {"overview": "full", "geometries": "geojson", "steps": "false"})
    if routes is None:
        _osrm_note(False, (time.monotonic() - t0) * 1000, backend)
        raise ConnectionError(backend or "router unavailable")
    rt = routes[0]
    if float(rt.get("distance") or 0.0) / 1000.0 > MAX_ROUTE_KM:
        return None
    _osrm_note(True, (time.monotonic() - t0) * 1000, backend=backend)
    rt["source"] = backend
    return rt


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
    if not (in_service_area(from_lat, from_lon)
            and in_service_area(to_lat, to_lon)):
        return {"options": [], "error": OUT_OF_AREA}
    drive, cycle, walk = await asyncio.gather(
        _osrm("driving", from_lon, from_lat, to_lon, to_lat),
        _osrm("cycling", from_lon, from_lat, to_lon, to_lat),
        _osrm("walking", from_lon, from_lat, to_lon, to_lat),
        return_exceptions=True,
    )
    geoms = {"driving": drive, "cycling": cycle, "walking": walk}
    if isinstance(geoms["driving"], BaseException):
        return {"options": [], "error": "router unavailable"}

    await _field_refresh_bounded()
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
        "router_backend": {
            p: (g.get("source") if isinstance(g, dict) else None)
            for p, g in geoms.items()},
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


_field_task: Optional[asyncio.Task] = None
_fires_task: Optional[asyncio.Task] = None
_forecast_task: Optional[asyncio.Task] = None


async def _bounded_refresh(coro_fn, task_name: str, timeout: float) -> None:
    """Await a shared refresh task, bounded, never cancel it.

    FIELD/FIRES/FORECAST refresh is best-effort — a stale-field window
    plus a slow upstream (OpenAQ retries sleep up to ~40 s) serializes
    every request behind refresh's lock; cap the wait so no request
    holds the event loop hostage. Two properties beyond a bare
    wait_for: concurrent requests share ONE task (no stacked fetches),
    and the task is shielded — a timed-out call leaves the fetch
    running so it lands the data for the next request instead of
    dying mid-flight and re-stalling the next call."""
    global _field_task, _fires_task, _forecast_task
    task = globals()[task_name]
    if task is None or task.done():
        task = asyncio.ensure_future(coro_fn())
        globals()[task_name] = task
        # swallow stray failures on the detached tail so an upstream
        # error never surfaces as an unhandled task exception
        task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
    except Exception:
        pass


async def _field_refresh_bounded(timeout: float = 10.0) -> None:
    await _bounded_refresh(lambda: FIELD.refresh(http()), "_field_task", timeout)


async def _fires_refresh_bounded(timeout: float = 6.0) -> None:
    await _bounded_refresh(lambda: FIRES.refresh(http()), "_fires_task", timeout)


async def _forecast_refresh_bounded(timeout: float = 12.0) -> None:
    await _bounded_refresh(lambda: FORECAST.refresh(http()), "_forecast_task", timeout)


def _scaled_duration_s(vehicle: str, profile: str, rt: dict) -> float:
    if profile in MODE_SPEED_KMH:
        return rt["distance"] / 1000 / MODE_SPEED_KMH[profile] * 3600
    return rt["duration"] * VEHICLE_TIME_FACTOR.get(vehicle, 1.0)


# /depart horizon answers per (OD, vehicle, hours) — keyed on the forecast
# fetch timestamp so a forecast refresh invalidates them all.
_DEPART_CACHE: dict = {}
_DEPART_CACHE_MAX = 64


@app.get("/depart")
@app.get("/v2/depart")
async def depart(from_lat: float, from_lon: float, to_lat: float, to_lon: float,
                 vehicle: str = "auto", hours: int = Query(default=24, le=120)):
    """Leave-later optimizer: the same trip's inhaled dose per departure hour.

    Scores the route against the hourly forecast field (CAMS + stagnation
    physics). Assumes the trip completes within the departure hour —
    every slot is priced on that hour's field alone.
    """
    exposure_mode = VEHICLE_TO_EXPOSURE.get(vehicle.lower())
    profile = VEHICLE_PROFILE.get(vehicle.lower())
    if not exposure_mode or not profile:
        return {"error": "unknown vehicle", "options": []}

    if hours < 1:
        # zero slots asked for ≠ forecast missing — the audit read this
        # honest-empty as an asymmetry bug because the label lied.
        return {"options": [], "error": "hours must be >= 1"}

    if not (in_service_area(from_lat, from_lon)
            and in_service_area(to_lat, to_lon)):
        return {"options": [], "error": OUT_OF_AREA}

    await _forecast_refresh_bounded()
    # horizon re-solve is ~24 dose evaluations — cache per OD+vehicle for
    # the life of one forecast fetch. Numbers inside an epoch are
    # identical to a recompute; the marker keeps the honesty explicit.
    ck = (round(from_lat, 3), round(from_lon, 3),
          round(to_lat, 3), round(to_lon, 3), vehicle.lower(), hours)
    epoch = getattr(FORECAST, "_fetched_at", None)
    ent = _DEPART_CACHE.get(ck) if epoch is not None else None
    if ent and ent[0] == epoch:
        body = dict(ent[1])
        body["served_from_cache"] = True
        # freshness stamps are served live, not cached — a hit must not
        # freeze 'as of' at cache-write time
        body["forecast"] = FORECAST.status()
        body["field"] = FIELD.status()
        body["field_age_s"] = (body["field"] or {}).get("age_s")
        return body

    rt = await _osrm(profile, from_lon, from_lat, to_lon, to_lat)
    if rt is None or isinstance(rt, BaseException):
        return {"options": [], "error": "router unavailable"}

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
    # 'now' is the leave-now hour specifically: slots[0] is only that
    # when hour 0 survived the coverage filter — a forecast gap at the
    # current slot would compare best against hour 1+ and still label
    # the percent 'vs now'. No now-slot -> no percent, never a shifted
    # base (daycount caveat, deploy-8 audit).
    now_slot = next((s for s in slots if s["hours_ahead"] == 0), None)
    best = ordered[0]
    saved = (round(100 * (1 - best["dose_ug"] / now_slot["dose_ug"]))
             if now_slot and now_slot["dose_ug"] else None)
    fstat = FIELD.status() or {}
    body = {
        "vehicle": vehicle, "mode": exposure_mode,
        "duration_min": round(dur_s / 60),
        "distance_km": round(rt["distance"] / 1000, 1),
        "now": now_slot,
        "best": best,
        "worst": ordered[-1],
        # percent, not µg — the ug_* name lies (claims-audit §4).
        # pct_less_vs_now is the honest key; ug_saved_vs_now stays for
        # clients on older builds until the app moves.
        "pct_less_vs_now": saved,
        "ug_saved_vs_now": saved,
        "slots": slots,
        "forecast": FORECAST.status(),
        # the live field the horizon anchors to — same block /v2/day
        # and /v2/outlook carry, so 'as of' reads one way everywhere
        "field": fstat,
        "field_age_s": fstat.get("age_s"),
    }
    if epoch is not None:
        if len(_DEPART_CACHE) >= _DEPART_CACHE_MAX:
            _DEPART_CACHE.pop(next(iter(_DEPART_CACHE)))
        _DEPART_CACHE[ck] = (epoch, body)
    return body


@app.get("/aqi")
async def aqi(lat: float, lon: float):
    """Interpolated PM2.5 field value at a point, with provenance and the
    decade-climatology context: what this point usually reads, this month,
    this hour, per 9M measured station-hours."""
    if not _finite_coords(lat, lon):
        return {"pm25": None, "error": "non-finite coordinate"}
    if not in_service_area(lat, lon):
        # the field clamps to its nearest edge — without this gate a query
        # for London gets Delhi air presented as its own (found in the
        # malformed-input sweep: lat=51.5/lon=-0.12 answered 69.2µg)
        return {"pm25": None, "error": OUT_OF_AREA}
    await asyncio.gather(_field_refresh_bounded(), _fires_refresh_bounded())
    mod = FIRES.smoke_modifier()
    v = FIELD.value(lat, lon, "pm2_5")
    if v is None:
        return {"pm25": None, "error": "field unavailable"}
    sd = FIELD.sigma(lat, lon)  # krige std-dev → honest band, None on IDW

    ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    band = history.typical_band(lat, lon, ist.month, ist.hour)
    typical = band.get("median")
    species = {
        "pm25": round(v * mod, 1),
        "pm10": FIELD.value(lat, lon, "pm10"),
        "no2": FIELD.value(lat, lon, "nitrogen_dioxide"),
        "o3": FIELD.value(lat, lon, "ozone"),
        "co": FIELD.value(lat, lon, "carbon_monoxide"),
        "so2": FIELD.value(lat, lon, "sulphur_dioxide"),
    }
    # US AQI = max EPA sub-index over the species this response actually
    # serves (station-grounded where instruments measure them) — not
    # CAMS's own us_aqi cell, which runs on raw model pm10 and reported
    # ~230 tonight vs every public source's ~160. us_aqi_model keeps the
    # raw model value for provenance. pm25 enters at AMBIENT v — us_aqi is
    # a public-facing ambient index; the smoke-breathing multiplier would
    # put ~180 where public instruments read ~160.
    subs = {}
    for k, val in species.items():
        ambient = v if k == "pm25" else val
        s = ingest_waqi.us_aqi_sub_index(k, ambient) if ambient is not None else None
        if s is not None:
            subs[k] = s
    us_aqi_v = round(max(subs.values())) if subs else None
    us_aqi_basis = max(subs, key=subs.get) if subs else None
    # both distances report None rather than emitting JSON `Infinity`
    # (invalid JSON — a cold-start poll would parse-fail whole)
    _ns_km = FIELD.nearest_sample_km(lat, lon)
    _nst_km = FIELD.nearest_station_km(lat, lon)
    return {
        "pm25": species["pm25"],
        "pm25_ambient": round(v, 1),
        "pm25_lo": round(max(0.0, v - sd) * mod, 1) if sd else None,
        "pm25_hi": round((v + sd) * mod, 1) if sd else None,
        "pm10": species["pm10"],
        "no2": species["no2"],
        "o3": species["o3"],
        "co": species["co"],
        "so2": species["so2"],
        "nh3": FIELD.value(lat, lon, "ammonia"),
        "us_aqi": us_aqi_v,
        "us_aqi_basis": us_aqi_basis,
        "us_aqi_model": FIELD.value(lat, lon, "us_aqi"),
        "european_aqi": FIELD.value(lat, lon, "european_aqi"),
        "dust": FIELD.value(lat, lon, "dust"),
        "aod": FIELD.value(lat, lon, "aerosol_optical_depth"),
        "conditions": FIELD.weather(),
        "nearest_sample_km": round(_ns_km, 1) if math.isfinite(_ns_km) else None,
        # km to the nearest NAMED live instrument — the only distance a
        # 'nearest live monitor' caption may print (samples incl. model
        # fill points; snapshot cells' own station km when feed is dark)
        "nearest_station_km": round(_nst_km, 1) if math.isfinite(_nst_km) else None,
        # inside the service margin but past the field's own extent the
        # value above is the nearest edge evidence extrapolated, not a
        # local read — disclosed before only by ns_km + a huge band a
        # consumer can ignore. Same spirit as /v2/plan's basis string.
        "beyond_field_edge": FIELD.beyond_field_edge(lat, lon),
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
@app.get("/v2/today")
async def today(lat: float, lon: float):
    """24 hourly decade-typical PM2.5 medians at a point (IST hours) —
    the ledger screen's background curve."""
    if not _finite_coords(lat, lon):
        raise HTTPException(422, "non-finite coordinate")
    if not in_service_area(lat, lon):
        return {"hours_ist": [], "error": OUT_OF_AREA}
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
        # the forecast horizon is PM2.5-only — another species gets an
        # honest empty layer, not pm2.5 wearing the wrong label
        if param != "pm2_5":
            return None
        return FORECAST.pm25(lat, lon, self._h)

    def nearest_sample_km(self, lat: float, lon: float) -> float:
        return FIELD.nearest_sample_km(lat, lon)


# /grid answers are deterministic functions of (cells, param, h) plus
# the epoch of the field/forecast data underneath — the surface only
# changes when a refresh lands, so repeated paints for the same source
# epoch replay the identical collection instead of paying O(cells)
# interpolation each time. Keyed on the real fetch timestamps: a fresh
# refresh produces a fresh collection; the cache can never serve data
# older than the data itself.
_GRID_CACHE: dict = {}


def _epoch_tagged(gj: dict, epoch, basis: str = "recorded") -> dict:
    """Stamp the freshness tuple onto the collection so a client can
    skip re-painting an identical epoch — honest replay detection.
    `basis` separates the archive replay (recorded) from the timelapse
    (forecast): /grid?h=N scrubs the FORECAST surface, /grid serves the
    recorded-now field."""
    if isinstance(gj, dict):
        props = gj.setdefault("properties", {})
        props["cell_epoch"] = list(epoch)
        props["basis"] = basis
    return gj


def _grid_cached(key: tuple, epoch: float, build) -> dict:
    hit = _GRID_CACHE.get(key)
    if hit and hit[0] == epoch:
        return hit[1]
    out = build()
    if len(_GRID_CACHE) >= 24:
        _GRID_CACHE.clear()
    _GRID_CACHE[key] = (epoch, out)
    return out


@app.get("/grid")
async def field_grid(cells: int = Query(default=22, ge=1, le=40),
                     h: Optional[int] = Query(default=None, ge=0, le=120),
                     param: str = Query(default="pm2_5")):
    """The live surface as GeoJSON cells — the map's colour layer.
    ?h=N (0..120) scrubs PM2.5 into the forecast horizon so the app can
    animate where the plume goes; ?param= serves another species layer
    (whitelisted to the pollutants the field actually ingests — a name
    it doesn't serve returns an honest empty collection). Confidence
    per cell degrades with distance to the nearest sample."""
    from airfield import POLLUTANTS
    species = [p.strip() for p in POLLUTANTS.split(",")]
    if param not in species:
        # honest empty collection per the docstring — a silent pm2_5
        # fallback would answer "pm10" misspelled with pm2.5 data
        return {"type": "FeatureCollection", "features": [],
                "properties": {"param": param,
                               "served": species,
                               "empty": "unknown pollutant param"}}
    if param == "us_aqi":
        # the index is a projection of our own pm2.5 surface, not a
        # second model layer — the model's native index field read
        # ~3× our station-grounded pm2.5 and the two maps told
        # different stories. Delhi's index is pm2.5-driven (public
        # PM2.5-AQI ≈ city AQI; other species' sub-indices stay <25),
        # so EPA-projecting our real field is both consistent and
        # honest. conf inherits the pm2.5 surface's — stronger than
        # the model layer's ever was.
        import districts as _d

        def _aqi_gj(field, cells):
            base = grid.as_geojson(field, cells, "pm2_5")
            feats = []
            for f in base.get("features", []):
                p = dict(f["properties"])
                p["us_aqi"] = _d.us_aqi(p.pop("pm25", None))
                p["param"] = "us_aqi"
                p["derived"] = "pm2_5 via US-EPA breakpoints"
                feats.append({**f, "properties": p})
            return {**base, "features": feats}

        if h is not None:
            await _forecast_refresh_bounded()
            ep = (FORECAST._fetched_at, FIELD._fetched_at,
                  community._OBS_VERSION)
            return _grid_cached(
                ("f", cells, param, h), ep,
                lambda: _epoch_tagged(_aqi_gj(_ForecastSurface(h), cells),
                                      ep, "forecast"))
        await _field_refresh_bounded()
        ep = (FIELD._fetched_at, community._OBS_VERSION)
        return _grid_cached(
            ("l", cells, param), ep,
            lambda: _epoch_tagged(_aqi_gj(FIELD, cells), ep))
    if h is not None:
        await _forecast_refresh_bounded()
        # the horizon anchors to the live field too — all three epochs
        ep = (FORECAST._fetched_at, FIELD._fetched_at,
              community._OBS_VERSION)
        return _grid_cached(
            ("f", cells, param, h), ep,
            lambda: _epoch_tagged(
                grid.as_geojson(_ForecastSurface(h), cells, param), ep,
                "forecast"))
    await _field_refresh_bounded()
    # the served surface is field×corridor-posterior — a donated trip
    # shifts cells between refreshes, so the obs version rides the epoch
    ep = (FIELD._fetched_at, community._OBS_VERSION)
    return _grid_cached(
        ("l", cells, param), ep,
        lambda: _epoch_tagged(
            grid.as_geojson(FIELD, cells, param), ep))


@app.post("/observe")
async def observe_trip(body: dict):
    """Retired donation path — 410 Gone.

    /v2/trip is the only trip-donation surface (it runs the privacy
    pipeline server-side: trim ends, thin, round, fold to cells). This
    endpoint predated that pipeline and no shipped client calls it —
    leaving a second raw-coords write surface open was a hole the
    privacy audit closed rather than patched."""
    raise HTTPException(
        410,
        "retired: donate via POST /v2/trip — it trims and aggregates "
        "server-side; raw observation posts are no longer accepted")


@app.post("/report")
async def hazard_report(body: dict):
    """User-flagged air observation: dust | smoke | burning | clean, 6h TTL."""
    try:
        lat, lon = float(body["lat"]), float(body["lon"])
    except (KeyError, TypeError, ValueError):
        return {"stored": False, "error": "need numeric lat/lon"}
    if not (_finite_coords(lat, lon) and in_ncr(lat, lon)):
        # missing coords used to default to (0,0) — a real point off
        # Ghana landing in the Delhi report layer
        return {"stored": False, "error": "reports cover Delhi/NCR only"}
    return community.report(
        kind=str(body.get("kind", "")),
        lat=lat,
        lon=lon,
        contributor=body.get("contributor"),
    )


_review_rate: dict = {}
_REVIEW_MAX_PER_HOUR = 10


@app.post("/v2/feedback")
async def leave_feedback(body: dict, request: Request):
    """A review: stars 1–5 + optional ≤240-char note. Stored with no token,
    no device id — authored content only. Per-IP hour cap keeps the public
    endpoint from becoming a billboard."""
    host = request.client.host if request.client else "?"
    now = time.time()
    hits = [t for t in _review_rate.get(host, []) if now - t < 3600]
    if len(hits) >= _REVIEW_MAX_PER_HOUR:
        raise HTTPException(429, "feedback rate limit — try later")
    hits.append(now)
    _review_rate[host] = hits
    # the limiter map itself must stay bounded — a public endpoint would
    # otherwise grow one entry per source IP forever on a 2 GB task
    if len(_review_rate) > 5000:
        stale = [h for h, ts in _review_rate.items()
                 if now - ts[-1] > 3600]
        for h in stale:
            del _review_rate[h]
        # still over the cap → evict the least-recently-active hosts;
        # never let a flood of fresh IPs grow the map unboundedly
        if len(_review_rate) > 5000:
            for h, _ts in sorted(
                    _review_rate.items(),
                    key=lambda kv: kv[1][-1])[:len(_review_rate) - 5000]:
                del _review_rate[h]
    out = community.add_review(
        stars=body.get("stars"),
        note=body.get("note"),
        build=body.get("build"),
    )
    if not out.get("stored"):
        raise HTTPException(422, out.get("error") or "invalid review")
    return out


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
    await _fires_refresh_bounded()
    return FIRES.fires_geojson()


_UNFURL_UAS = ("slackbot", "twitterbot", "facebookexternalhit",
               "discordbot", "whatsapp", "linkedinbot", "telegrambot",
               "googlebot", "bingbot", "duckduckbot", "embedly",
               "redditbot", "pinterest", "vkshare")


@app.get("/community")
async def community_totals(request: Request):
    """Browsers get the community page; API clients (fetch's `*/*`, the
    app) keep the JSON totals. Link unfurlers also send `*/*` — without
    the UA check a shared link expanded to raw JSON, so crawlers get the
    HTML (its og:/twitter: meta is what renders the card)."""
    ua = request.headers.get("user-agent", "").lower()
    if "text/html" in request.headers.get("accept", "") or \
            any(b in ua for b in _UNFURL_UAS):
        from fastapi.responses import FileResponse
        return FileResponse(os.path.join(os.path.dirname(__file__), "community.html"))
    return community.totals()


@app.get("/escape")
async def escape(lat: float, lon: float,
                 limit: int = Query(default=5, ge=0, le=10)):
    """'Where is the air best near me right now' — scan the live field over
    NCR, drop cells within 3km of the user (that's still 'here'), rank the
    rest by PM2.5, reverse-name the best. Each answer carries its own
    data-confidence so thin regions don't fake certainty."""
    if not _finite_coords(lat, lon):
        raise HTTPException(422, "non-finite coordinate")
    if not in_service_area(lat, lon):
        return {"best": [], "error": OUT_OF_AREA}
    await _field_refresh_bounded()
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
    async def _name(c):
        try:
            r = await http().get(PHOTON_REVERSE,
                                 params={"lat": c["lat"], "lon": c["lon"], "limit": 1},
                                 timeout=6.0)
            feats = r.json().get("features", [])
            if feats:
                p = feats[0]["properties"]
                c["name"] = (p.get("name") or p.get("district")
                             or p.get("street") or "unnamed area")
        except httpx.HTTPError:
            pass
    if best:
        # parallel + bounded: sequential Photon round-trips from ap-south-1
        # ran ~5s each — ~24s a request on one worker
        await asyncio.gather(*[_name(c) for c in best])
    for c in best:
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
    if not _finite_coords(lat, lon):
        raise HTTPException(422, "non-finite coordinate")
    if not in_service_area(lat, lon):
        return {"dose_ug": None, "error": OUT_OF_AREA}
    hours = max(0.5, min(12.0, hours))
    await _field_refresh_bounded()
    ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    start = ist.hour if start_hour is None else max(0, min(23, start_hour))

    live = FIELD.value(lat, lon, "pm2_5")
    band0 = history.typical_band(lat, lon, ist.month, ist.hour)
    typ0 = band0.get("median")
    # how today's field sits vs the decade norm — applied to future hours
    adj = (live / typ0) if (live and typ0) else 1.0

    micro = exposure.MICROENV.get(vehicle, 1.0)
    # unknown-vehicle fallback matches the canonical table's seated
    # tier (10.0 L/min) — the audits' one fallback, never a quieter one
    ve_m3h = exposure.VENTILATION_LPM.get(vehicle, 10.0) / 1000.0 * 60.0
    # desk baseline: indoor office ~35% of ambient; 7.5 L/min is resting
    # minute ventilation (EPA EFH sedentary) — deliberately below every
    # transit-tier VE since the alternative is staying indoors
    desk_ve = 7.5 / 1000.0 * 60.0

    per_hour = []
    dose = desk = dose_lo = dose_hi = 0.0
    sd0 = FIELD.sigma(lat, lon) if live is not None else None
    for i in range(int(hours * 2)):  # half-hour steps for smooth dose
        h = (start + i * 0.5) % 24
        hh = int(h)
        c_lo = c_hi = None
        if i == 0 and live is not None:
            c = live
            # live hour: krige σ band when serving; else the decade
            # quartiles for this hour stand in
            if sd0:
                c_lo, c_hi = max(0.0, live - sd0), live + sd0
            elif band0.get("p25") and band0.get("p75"):
                c_lo, c_hi = band0["p25"] * adj, band0["p75"] * adj
        else:
            t = history.typical(lat, lon, ist.month, hh)
            c = (t * adj) if t else live
            # future hours: the real interquartile range of that
            # month-hour, scaled by the same live delta as the median
            band_h = history.typical_band(lat, lon, ist.month, hh)
            if band_h.get("p25") and band_h.get("p75"):
                c_lo, c_hi = band_h["p25"] * adj, band_h["p75"] * adj
        if c is None:
            continue
        dose += c * micro * ve_m3h * 0.5
        desk += c * 0.35 * desk_ve * 0.5
        dose_lo += (c_lo if c_lo is not None else c) * micro * ve_m3h * 0.5
        dose_hi += (c_hi if c_hi is not None else c) * micro * ve_m3h * 0.5
        if i % 2 == 0:
            per_hour.append({"hour_ist": hh, "conc_ugm3": round(c, 1)})

    cig = dose / 316.0  # Berkeley Earth equivalence, same as app ledger
    return {
        "vehicle": vehicle,
        "shift_hours": hours,
        "start_hour_ist": start,
        "dose_ug": round(dose, 1),
        "dose_ug_lo": round(dose_lo, 1),
        "dose_ug_hi": round(dose_hi, 1),
        "cig_equiv": round(cig, 1),
        "cig_equiv_lo": round(dose_lo / 316.0, 1),
        "cig_equiv_hi": round(dose_hi / 316.0, 1),
        "desk_dose_ug": round(desk, 1),
        "vs_desk_pct": round((dose / desk - 1) * 100) if desk else None,
        "per_hour": per_hour,
        "live_adjust": round(adj, 2),
        "note": ("dose model: ambient field × breathing-zone microenv × "
                 "minute ventilation; future hours = decade climatology × "
                 "today's live delta"),
        "field": FIELD.status(),
    }


# --- operator session: HMAC-signed cookie, minted by <mount>/login ----------
#
# No server-side session store (zero-infra constraint): the cookie is a
# stateless "expiry + signature" pair signed with ALIVE_ADMIN_TOKEN, so it
# can only be minted by someone holding the token and every issued cookie
# dies the moment the token rotates. HttpOnly keeps it out of JS reach
# (the old sessionStorage token was one XSS away from theft);
# SameSite=Strict means a cross-site request never carries it, which also
# kills the CSRF surface without a token dance.
#
# The whole console — page, api, session endpoints — lives under one
# un-guessable mount (server/admin_mount.py); /admin and friends answer
# an honest 404 so path scans learn nothing. Obscurity is additive: the
# token + cookie + rate bucket below stay the real gate.
try:
    from admin_mount import ADMIN_MOUNT
except ImportError:                        # package-mode import
    from server.admin_mount import ADMIN_MOUNT

_ADMIN_COOKIE = "alive_admin"
_ADMIN_SESSION_S = 8 * 3600   # ~one demo day; ALIVE_ADMIN_SESSION_S overrides


def _admin_session_s() -> int:
    try:
        return int(os.environ.get("ALIVE_ADMIN_SESSION_S",
                                  _ADMIN_SESSION_S))
    except ValueError:
        return _ADMIN_SESSION_S


def _session_sign(exp: int) -> str:
    key = os.environ.get("ALIVE_ADMIN_TOKEN", "").encode()
    return hmac.new(key, f"alive-admin-v1:{exp}".encode(),
                    hashlib.sha256).hexdigest()[:32]


def _session_value(exp: int) -> str:
    return f"v1.{exp}.{_session_sign(exp)}"


def _session_ok(request: Request) -> bool:
    """True when the request carries a well-formed, unexpired session
    cookie signed under the CURRENT ALIVE_ADMIN_TOKEN."""
    raw = request.cookies.get(_ADMIN_COOKIE, "")
    try:
        ver, exp_s, sig = raw.split(".")
        exp = int(exp_s)
    except (AttributeError, ValueError):
        return False
    if ver != "v1" or exp <= time.time():
        return False
    return hmac.compare_digest(sig, _session_sign(exp))


def _admin_guard(request: Request):
    """Gate for <mount>/api* — the ops dashboard's data surface.

    `ALIVE_ADMIN_TOKEN` set  → require the signed session cookie (minted
    by POST <mount>/login) or `Authorization: Bearer <token>` — Bearer
    is kept for ops curl/health-checks, the browser only ever sees the
    cookie. Unset → loopback clients only (dev default); a real
    deployment sits behind a LB, so remote callers get 403 until the
    operator sets the token. The console HTML page itself is public —
    it carries no data; every fetch it makes goes through this guard.
    """
    token = os.environ.get("ALIVE_ADMIN_TOKEN")
    if token:
        if _session_ok(request):
            return
        auth = request.headers.get("authorization", "")
        if hmac.compare_digest(auth, f"Bearer {token}"):
            return
        raise HTTPException(401, "admin sign-in required")
    host = request.client.host if request.client else ""
    if host not in ("127.0.0.1", "::1", "localhost", "testclient"):
        raise HTTPException(
            403, "admin api is loopback-only until ALIVE_ADMIN_TOKEN is set")


@app.post(ADMIN_MOUNT + "/login", include_in_schema=False)
async def admin_login(request: Request):
    """Trade the operator token for a signed session cookie.

    Rate-limited hard by middleware's <mount>/login bucket (5 tries
    then ~1 per 5 s per socket peer) — brute force is a dead end against
    a 256-bit token; the brake is what keeps an attempt cheap and loud.
    """
    token = os.environ.get("ALIVE_ADMIN_TOKEN")
    if not token:
        raise HTTPException(503, "admin auth is not configured")
    try:
        body = await request.json()
        supplied = str((body or {}).get("token", ""))[:512]
    except Exception:
        supplied = ""
    if not supplied or not hmac.compare_digest(supplied, token):
        raise HTTPException(401, "bad operator token")
    ttl = _admin_session_s()
    exp = int(time.time()) + ttl
    from fastapi.responses import JSONResponse
    r = JSONResponse({"ok": True, "expires_in": ttl})
    # Secure only when the request itself arrived over TLS — the NLB still
    # serves plain :80 (pentest flagged; owner decision), so pinning
    # Secure now would brick demo-morning sign-in. Strict+HttpOnly hold.
    secure = (request.url.scheme == "https"
              or request.headers.get("x-forwarded-proto") == "https")
    r.set_cookie(_ADMIN_COOKIE, _session_value(exp), max_age=ttl,
                 httponly=True, samesite="strict", secure=secure, path="/")
    return r


@app.post(ADMIN_MOUNT + "/logout", include_in_schema=False)
async def admin_logout():
    """Drop the session cookie. Stateless — a copied cookie stays valid
    until its signed expiry (≤8h worst case); the report owns that."""
    from fastapi.responses import JSONResponse
    r = JSONResponse({"ok": True})
    r.delete_cookie(_ADMIN_COOKIE, path="/")
    return r


@app.get(ADMIN_MOUNT + "/session", include_in_schema=False)
async def admin_session(request: Request):
    """The gate screen's probe — is this browser signed in right now?
    Answers the cookie path of _admin_guard (loopback dev included)."""
    if os.environ.get("ALIVE_ADMIN_TOKEN"):
        return {"authenticated": _session_ok(request)}
    host = request.client.host if request.client else ""
    return {"authenticated": host in ("127.0.0.1", "::1", "localhost",
                                      "testclient")}


@app.get(ADMIN_MOUNT + "/in/{secret}", include_in_schema=False)
async def admin_in(secret: str, request: Request):
    """One-link sign-in — the token rides the URL exactly once.

    The path segment is verified against the same ALIVE_ADMIN_TOKEN the
    form checks, same constant-time compare; on a match the SAME
    session cookie is minted and the browser is 303'd to the bare
    mount — the page that loads carries a clean URL, so the credential
    never sits in an address bar past the landing. A wrong guess gets
    the identical 404 every unknown path gets: the endpoint's existence
    is committed, but whether a guess was RIGHT never leaks. The
    middleware bucket for <mount>/in/ holds attempts to ~1 per 5 s —
    a credential in a URL needs the same brake as the form, and the
    request logger renders the path as /in/<redacted> so the token
    can't land in CloudWatch.
    """
    token = os.environ.get("ALIVE_ADMIN_TOKEN")
    if not token or not hmac.compare_digest(secret, token):
        raise HTTPException(404)
    ttl = _admin_session_s()
    exp = int(time.time()) + ttl
    from fastapi.responses import RedirectResponse
    r = RedirectResponse(ADMIN_MOUNT, status_code=303)
    secure = (request.url.scheme == "https"
              or request.headers.get("x-forwarded-proto") == "https")
    r.set_cookie(_ADMIN_COOKIE, _session_value(exp), max_age=ttl,
                 httponly=True, samesite="strict", secure=secure, path="/")
    # a credential-minting response must never be replayed from a cache
    r.headers["cache-control"] = "no-store"
    r.headers["x-robots-tag"] = "noindex, nofollow"
    return r


@app.get(ADMIN_MOUNT + "/api", dependencies=[Depends(_admin_guard)],
         include_in_schema=False)
async def admin_api():
    """Live ops snapshot for the admin dashboard — anon ids only."""
    thirty_min = 30
    detail = community.contributors_detail()
    contributors = detail["days"]
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
        # k>=3 gate mirrors corridors/global: sub-k UTC day rows are a
        # one-person slice — counted here, never served above.
        "contributors_suppressed": detail["suppressed"],
        "contributors_days_tracked": detail["days_tracked"],
        "recent_journeys": community.recent_obs(20),
        "reports": community.live_reports(),
        "journeys_per_hour": community.journeys_per_hour(),
        "reviews": community.reviews_summary(),
    }


@app.get(ADMIN_MOUNT + "/api/reviews", include_in_schema=False,
         dependencies=[Depends(_admin_guard)])
async def admin_reviews():
    """'Their reviews' as an aggregate: star histogram + mean; note bodies
    publish only at k>=3 reviews, hour-bucketed, ≤140 chars each."""
    return community.reviews_summary()


# explicit lifetimes: the pages ship an etag already, so a revisit
# revalidates cheap — but a judge's second load inside the TTL skips
# the round trip entirely. Baked statics (geojson, the hero shot)
# change only with a bake/deploy, so they can sit in cache an hour.
_PAGE_CACHE = {"cache-control": "public, max-age=300"}
_STATIC_CACHE = {"cache-control": "public, max-age=3600"}


@app.get("/")
async def root_page():
    """The pitch door: a judge hitting the NLB root lands on the landing
    page — the few-line pitch + the live ASCII field — which leads into
    /city for the raw choropleth."""
    from fastapi.responses import FileResponse
    import os
    return FileResponse(os.path.join(os.path.dirname(__file__), "landing.html"),
                        headers=_PAGE_CACHE)


@app.get("/landing")
async def landing_page():
    """Explicit alias for the marketing surface (same file as /)."""
    from fastapi.responses import FileResponse
    import os
    return FileResponse(os.path.join(os.path.dirname(__file__), "landing.html"),
                        headers=_PAGE_CACHE)


@app.get(ADMIN_MOUNT, include_in_schema=False)
@app.get(ADMIN_MOUNT + "/", include_in_schema=False)
async def admin_page():
    """The engine room — served under one un-guessable mount only
    (server/admin_mount.py); /admin + friends answer an honest 404 so
    path scans learn nothing. x-robots-tag keeps crawlers off — the
    path must never appear in a public robots.txt, so the header (plus
    a meta in the page) is the whole noindex mechanism."""
    from fastapi.responses import FileResponse
    import os
    return FileResponse(os.path.join(os.path.dirname(__file__), "admin.html"),
                        headers={"x-robots-tag": "noindex, nofollow"})


@app.get("/city")
async def city_page():
    """Delhi NCR air, district by district — light ops-family surface:
    the live CPCB choropleth over baked OSM boundaries, the pixel field
    underneath, corridor measurements. Judges land here."""
    from fastapi.responses import FileResponse
    import os
    return FileResponse(os.path.join(os.path.dirname(__file__), "city.html"))


@app.get("/ncr.geojson")
async def ncr_districts_geojson():
    """The baked NCR district boundaries the /city choropleth paints —
    static asset (server/static/ncr_districts.geojson), cached at the
    edge; /v2/districts carries the live numbers."""
    from fastapi.responses import FileResponse
    import os
    return FileResponse(
        os.path.join(os.path.dirname(__file__), "static",
                     "ncr_districts.geojson"),
        media_type="application/geo+json", headers=_STATIC_CACHE)


@app.get("/app-hero.png")
async def app_hero_png():
    """The landing's hero product shot — a REAL app screen capture
    (compare surface: dose-tinted options + depart strip), not a mockup.
    Captured from the running build, regenerated when the app's compare
    UI changes."""
    from fastapi.responses import FileResponse
    import os
    return FileResponse(
        os.path.join(os.path.dirname(__file__), "static", "app-hero.png"),
        headers=_STATIC_CACHE)


@app.get("/app-hero-472.webp")
async def app_hero_472_webp():
    """2×-density WebP of the landing's hero shot — served bytes, not a
    mockup. Derivative of app-hero.png, regenerated with it."""
    from fastapi.responses import FileResponse
    import os
    return FileResponse(
        os.path.join(os.path.dirname(__file__), "static",
                     "app-hero-472.webp"),
        media_type="image/webp", headers=_STATIC_CACHE)


@app.get("/app-hero-708.webp")
async def app_hero_708_webp():
    """3×-density WebP — the landing's picture source on every modern
    browser; app-hero.png stays the capture + the fallback."""
    from fastapi.responses import FileResponse
    import os
    return FileResponse(
        os.path.join(os.path.dirname(__file__), "static",
                     "app-hero-708.webp"),
        media_type="image/webp", headers=_STATIC_CACHE)


@app.get("/app-hero-708.png")
async def app_hero_708_png():
    """Right-sized PNG fallback for the pre-WebP browser — still the
    real capture, just resized to the box it renders in."""
    from fastapi.responses import FileResponse
    import os
    return FileResponse(
        os.path.join(os.path.dirname(__file__), "static",
                     "app-hero-708.png"),
        headers=_STATIC_CACHE)


@app.get("/app-choose-strip-848.webp")
async def app_choose_strip_848_webp():
    """The landing's chooser strip — three REAL frames from one run on
    the shipped build (priced candidates → verdict pill → settled
    winner), composed into a single asset with alpha gaps. 848w tier."""
    from fastapi.responses import FileResponse
    import os
    return FileResponse(
        os.path.join(os.path.dirname(__file__), "static",
                     "app-choose-strip-848.webp"),
        media_type="image/webp", headers=_STATIC_CACHE)


@app.get("/app-choose-strip-1360.webp")
async def app_choose_strip_1360_webp():
    """1360w tier of the chooser strip — served bytes, not a mockup."""
    from fastapi.responses import FileResponse
    import os
    return FileResponse(
        os.path.join(os.path.dirname(__file__), "static",
                     "app-choose-strip-1360.webp"),
        media_type="image/webp", headers=_STATIC_CACHE)


@app.get("/app-choose-strip-1520.webp")
async def app_choose_strip_1520_webp():
    """1520w tier of the chooser strip — ~1.7× for the 896px-wide figure;
    the top rung — keeps the whole page near the ~200KB wire line."""
    from fastapi.responses import FileResponse
    import os
    return FileResponse(
        os.path.join(os.path.dirname(__file__), "static",
                     "app-choose-strip-1520.webp"),
        media_type="image/webp", headers=_STATIC_CACHE)


@app.get("/app-choose-strip-848.png")
async def app_choose_strip_848_png():
    """PNG fallback of the chooser strip for the pre-WebP browser —
    still the real frames, just resized to the box it renders in."""
    from fastapi.responses import FileResponse
    import os
    return FileResponse(
        os.path.join(os.path.dirname(__file__), "static",
                     "app-choose-strip-848.png"),
        headers=_STATIC_CACHE)


@app.get("/delhi_subdistricts.geojson")
async def delhi_subdistricts_geojson():
    """Delhi NCT's 13 OSM admin_level=5 sub-areas (server/static/
    delhi_subdistricts.geojson) — the boundaries /v2/districts level
    'osm_admin_5' rows describe. Static baked asset; 404 when the bake
    never ran rather than a fabricated shape."""
    from fastapi.responses import FileResponse
    import os
    path = os.path.join(os.path.dirname(__file__), "static",
                        "delhi_subdistricts.geojson")
    if not os.path.exists(path):
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "sub-district boundaries not baked"},
                            status_code=404)
    return FileResponse(path, media_type="application/geo+json",
                        headers=_STATIC_CACHE)


@app.get("/v2-light.json")
async def v2_light_style():
    """The app's bundled basemap style (server/static/v2-light.json), served
    so the mobile offline pack can pass an http(s) style_url to
    OfflineManager.createPack — MapLibre Native's fetcher can't load the
    file:// URL the app used to hand it, so the region never downloaded.
    Byte-identical copy of Mobile/src/map/v2-light.json; the parity test
    keeps the two from drifting."""
    from fastapi.responses import FileResponse
    import os
    path = os.path.join(os.path.dirname(__file__), "static", "v2-light.json")
    if not os.path.exists(path):
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "basemap style not bundled"},
                            status_code=404)
    return FileResponse(path, media_type="application/json",
                        headers=_STATIC_CACHE)


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
        r = await http().get(PHOTON_REVERSE, params={
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
    if not (in_service_area(from_lat, from_lon)
            and in_service_area(to_lat, to_lon)):
        return {"steps": [], "error": OUT_OF_AREA}
    t0 = time.monotonic()
    routes, backend = await _osrm_get(
        prof, f"{from_lon},{from_lat};{to_lon},{to_lat}",
        {"overview": "full", "geometries": "geojson",
         "steps": "true", "alternatives": "false"})
    _osrm_note(routes is not None, (time.monotonic() - t0) * 1000,
               backend=backend)
    if routes is None:
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
        "router_backend": backend,
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
                       dependencies=[Depends(_admin_guard)],
                       include_in_schema=False)
    # <mount>/api/usage — the console 'usage' tab's aggregate rollup;
    # same gate as the rest of the mount's api (Bearer token when set,
    # loopback-only otherwise)
    app.include_router(_admin_agg.usage_router,
                       dependencies=[Depends(_admin_guard)],
                       include_in_schema=False)

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


# The rollup/validate jobs run as separate one-shot Fargate tasks — the
# API never sees their disk. They publish under
# s3://{ALIVE_AIR_BUCKET}/{daily,validation}/ and this mirror pulls that
# onto the local mirror admin_agg reads. First pull at boot so an older
# task still serves the newest rollup; then hourly (the jobs are
# daily/weekly — a fired job's output lands within one tick).
# The same shelf also carries geo/ build artifacts (delhi.pmtiles from
# the CodeBuild tiles lane): sync_geo_artifacts hot-swaps the archive
# under tiles.py — a rebuilt pmtiles goes live without a redeploy.
_ROLLUP_MIRROR_PERIOD_S = 1800


def _start_rollup_mirror() -> None:
    if os.environ.get("ALIVE_ROLLUP_MIRROR", "1").strip() in \
            ("0", "false", "no"):
        return
    import threading

    import ingest_worker as _ingest

    def _loop():
        while True:
            try:
                res = _ingest.sync_rollup_outputs()
                if res.get("downloaded"):
                    _ingest.log.info("rollup mirror: pulled %s",
                                     res["downloaded"])
            except Exception:
                pass
            try:
                geo = _ingest.sync_geo_artifacts()
                if geo.get("downloaded"):
                    _ingest.log.info("geo mirror: pulled %s",
                                     geo["downloaded"])
            except Exception:
                pass
            time.sleep(_ROLLUP_MIRROR_PERIOD_S)

    t = threading.Thread(target=_loop, name="alive-rollup-mirror",
                         daemon=True)
    t.start()


def _start_rollup_loop() -> None:
    """Daily/weekly rollups as an in-app daemon — DISABLED by default:
    the EventBridge schedules (rollup-daily 00:30 IST, validate-weekly
    Sun 20:00 IST) run them on separate one-off Fargate tasks now, and
    the compute is heavy — a weekly validation rebuilds ~168 hourly
    krige surfaces on the same 1 vCPU as the serving API, GIL-starving
    the event loop until health checks die and the ALB drains the task
    (the observed "service wedged" flap pattern). The 30-min S3→local
    mirror (_start_rollup_mirror) stays on — it only pulls the files
    the scheduled jobs wrote. ALIVE_ROLLUP_IN_APP=1 re-enables for
    local dev where no scheduler exists."""
    if os.environ.get("ALIVE_ROLLUP_IN_APP", "0").strip() in ("0", "false", "no"):
        return
    import logging
    import threading

    log = logging.getLogger("alive.rollup")

    def _loop():
        import rollup_lambda
        while True:
            try:
                r = rollup_lambda.rollup_tick()
                if r.get("daily") != "present" or r.get("weekly") != "present":
                    log.warning("rollup tick: %s", r)
            except Exception as e:  # noqa: BLE001
                log.warning("rollup tick failed: %r", e)
            time.sleep(3600)

    threading.Thread(target=_loop, name="alive-rollup",
                     daemon=True).start()

