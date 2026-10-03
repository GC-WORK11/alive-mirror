"""OpenAQ v3 station-ingest adapter — the drop-in stations source for the
15-minute air index (docs/plan/05-backend-architecture.md §2 input 2).

Live-probe findings (2026-10-03, no/invalid key):
  * Every /v3 endpoint is key-gated — no key -> HTTP 401 served by
    CloudFront, body {"message": "Unauthorized. A valid API key must be
    provided in the X-API-Key header."}; an invalid key also 401s but the
    API layer itself replies {"detail": "Invalid credentials"}.
  * /v2/* is gone entirely (HTTP 410) — v3 is the only path.
  * Auth is the `X-API-Key` request header; free tier is 60 req/min and
    2000 req/hour, exceeded -> HTTP 429 with x-ratelimit-{used,limit,
    remaining,reset} headers (reset is an epoch-seconds timestamp).
  * Paging: `limit` (max 1000) + 1-based `page`; `meta.found`/`page`/`limit`
    in every response carry the totals.

Request shapes used here:
  GET /v3/locations?bbox=<minlon,minlat,maxlon,maxlat>&limit=200&page=<n>
    -> results[]: {id, name, coordinates{latitude,longitude},
       sensors[{id, name, parameter{id,name,units,displayName}}], ...}
  GET /v3/locations/{locations_id}/latest?limit=100
    -> results[]: {datetime{utc,local}, value, coordinates,
       sensorsId, locationsId}

Parameter ids (v3 canonical): pm10=1, pm25=2, no2=7, o3=10 — but sensors
are matched by parameter.name (robust to id drift), and units are taken
per-sensor from parameter.units.

Contract — fetch(api_key=None, client=None, bbox=..., sleep=...) -> dict:
  status   "ok" | "no key — owner blocker" | "unavailable: <reason>"
  obs      normalized readings: {station_id, sensor_id, name, lat, lon,
           parameter, value (µg/m³), unit ("µg/m³"), src_value, src_unit,
           ts (epoch), ts_utc}
  stations airindex station-obs schema for pm25 obs only —
           {lat, lon, name, pm25, ts, station_id}: feeds
           airindex.qc_stations() / build_field() inputs["stations"]
           directly. Freshest sensor wins when a site has several.
  skipped  counters for honest accounting: unsupported_unit, bad_value,
           bad_ts, bad_row
  secrets  the key is read from OPENAQ_API_KEY (or the api_key arg), put
           in the X-API-Key header, and never printed, logged, or echoed
           into any return value.
"""
import os
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

OPENAQ_V3 = "https://api.openaq.org/v3"
ENV_KEY = "OPENAQ_API_KEY"

# NCR bbox (lon_min, lat_min, lon_max, lat_max) — mirrors airindex.BBOX;
# duplicated so this module stays dependency-free / drop-in.
BBOX = (76.75, 28.15, 77.95, 28.98)

PAGE_LIMIT = 200          # locations per page (<= OpenAQ max 1000)
MAX_PAGES = 10            # safety cap: 2000 locations >> Delhi's ~130
LATEST_LIMIT = 100        # sensors-per-location cap on /latest
MAX_ATTEMPTS = 3          # initial try + 2 retries on 429
BACKOFF_BASE_S = 5.0      # exponential floor when x-ratelimit-reset absent
BACKOFF_MAX_S = 60.0      # never sleep longer than one rate window

# Pollutants we keep, keyed by v3 parameter.name. IDs are canonical v3
# (pm10=1, pm25=2, no2=7, o3=10) but kept only as documentation — matching
# is by name so an OpenAQ id remap can't silently drop us.
PARAMS = {
    "pm25": {"id": 2, "range": (0.0, 1500.0)},
    "pm10": {"id": 1, "range": (0.0, 3000.0)},
    "no2": {"id": 7, "range": (0.0, 3000.0)},
    "o3": {"id": 10, "range": (0.0, 2000.0)},
}

# Unit -> µg/m³. Mass units are exact; gas ppm/ppb use the standard
# 25 °C / 1 atm molar conversion (MW / 24.45 L·mol⁻¹), the convention
# OpenAQ itself uses when reporting µg/m³ equivalents.
_UGM3 = {"µg/m³", "µg/m3", "ug/m3", "ug/m³", "µg/m^3", "ug/m^3"}
_MGM3 = {"mg/m³", "mg/m3", "mg/m^3"}
_MOLAR_UGM3_PER_PPM = {"no2": 46.0055 / 24.45 * 1000.0,  # ~1882
                      "o3": 48.0 / 24.45 * 1000.0}        # ~1963


def to_ugm3(parameter: str, unit, value) -> Optional[float]:
    """Convert a raw sensor value to µg/m³.

    -> float, or None when the source unit has no defined conversion —
    callers must skip+count those (mission rule: convert only where the
    source unit allows). ppm/ppb convert only for gases in
    _MOLAR_UGM3_PER_PPM; ppm on a particulate is nonsense -> None."""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    u = str(unit or "").strip().lower()
    if u in _UGM3:
        return v
    if u in _MGM3:
        return v * 1000.0
    if u in ("ppm", "ppb"):
        factor = _MOLAR_UGM3_PER_PPM.get(parameter)
        if factor is None:
            return None
        return v * factor if u == "ppm" else v * factor / 1000.0
    return None


def _parse_ts(utc_str) -> Optional[float]:
    """'2024-09-25T22:00:00Z' -> epoch seconds, or None."""
    if not utc_str:
        return None
    try:
        return datetime.fromisoformat(
            str(utc_str).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _backoff_s(resp: Optional[httpx.Response], attempt: int,
               time_func) -> float:
    """Seconds to wait after a 429. Honor x-ratelimit-reset (an epoch-
    seconds timestamp per OpenAQ docs) when it parses ahead of now;
    else exponential 5s/10s/20s. Capped at BACKOFF_MAX_S."""
    reset = None
    if resp is not None:
        reset = (resp.headers or {}).get("x-ratelimit-reset")
    try:
        reset = float(reset)
    except (TypeError, ValueError):
        reset = None
    if reset is not None:
        if reset > 1e9:                    # epoch timestamp per docs
            return max(0.0, min(BACKOFF_MAX_S, reset - time_func()))
        return max(0.0, min(BACKOFF_MAX_S, reset))  # seconds-until form
    return min(BACKOFF_MAX_S, BACKOFF_BASE_S * (2 ** attempt))


class _RateLimited(Exception):
    """429 persisted through all retries — caller degrades honestly."""


def _get(client, url: str, headers: dict, params: dict,
         sleep, time_func, stats: dict) -> httpx.Response:
    """GET with bounded 429 backoff. stats['requests']/'retries_429' are
    counted here so the return bundle is auditable."""
    for attempt in range(MAX_ATTEMPTS):
        stats["requests"] += 1
        r = client.get(url, headers=headers, params=params, timeout=30)
        stats["responses"] += 1
        if r.status_code == 429:
            stats["retries_429"] += 1
            if attempt == MAX_ATTEMPTS - 1:
                raise _RateLimited(url)
            sleep(_backoff_s(r, attempt, time_func))
            continue
        r.raise_for_status()
        return r
    raise _RateLimited(url)  # unreachable; keeps type-checkers happy


def _fetch_locations(client, headers, bbox, sleep, time_func, stats):
    """All /v3/locations pages inside `bbox`. -> [location dicts]."""
    bbox_s = ",".join(f"{x:.4f}" for x in bbox)
    out, seen = [], set()
    for page in range(1, MAX_PAGES + 1):
        r = _get(client, f"{OPENAQ_V3}/locations", headers,
                 {"bbox": bbox_s, "limit": PAGE_LIMIT, "page": page},
                 sleep, time_func, stats)
        j = r.json()
        meta = j.get("meta") or {}
        results = j.get("results") or []
        for loc in results:
            if loc.get("id") not in seen:
                seen.add(loc.get("id"))
                out.append(loc)
        stats["pages"] += 1
        try:
            found = int(meta.get("found") or 0)
            lim = int(meta.get("limit") or PAGE_LIMIT)
        except (TypeError, ValueError):
            found, lim = 0, PAGE_LIMIT
        if not results or page * lim >= found:
            break
    return out


def _sensor_index(locations):
    """sensors_id -> {parameter, units, station meta} for PARAMS only."""
    idx = {}
    for loc in locations:
        coords = loc.get("coordinates") or {}
        lat, lon = coords.get("latitude"), coords.get("longitude")
        if lat is None or lon is None:
            continue
        for s in loc.get("sensors") or []:
            pname = ((s.get("parameter") or {}).get("name") or "").lower()
            if pname not in PARAMS:
                continue
            idx[s.get("id")] = {
                "parameter": pname,
                "src_unit": (s.get("parameter") or {}).get("units"),
                "station_id": loc.get("id"),
                "name": loc.get("name") or f"station {loc.get('id')}",
                "lat": float(lat), "lon": float(lon),
                "provider": (loc.get("provider") or {}).get("name"),
            }
    return idx


def _fetch_latest(client, headers, loc_id, sleep, time_func, stats):
    """-> latest-results list for one location, or [] on failure. A
    per-location failure is tolerated (counted), never fatal — matching
    airindex/airfield behavior."""
    try:
        r = _get(client, f"{OPENAQ_V3}/locations/{loc_id}/latest",
                 headers, {"limit": LATEST_LIMIT}, sleep, time_func, stats)
        return (r.json() or {}).get("results") or []
    except _RateLimited:
        stats["locations_rate_limited"] += 1
    except httpx.HTTPError:
        stats["locations_failed"] += 1
    except ValueError:                    # bad JSON body
        stats["locations_failed"] += 1
    return []


def normalize(locations, latest_by_loc, skipped):
    """Raw API payloads -> normalized obs rows (see module docstring)."""
    sensors = _sensor_index(locations)
    obs = []
    for loc in locations:
        for m in latest_by_loc.get(loc.get("id"), []):
            meta = sensors.get(m.get("sensorsId"))
            if meta is None:
                continue                  # sensor not a param we keep
            param = meta["parameter"]
            raw = m.get("value")
            try:
                float(raw)
            except (TypeError, ValueError):
                skipped["bad_value"] += 1
                continue
            v_ugm3 = to_ugm3(param, meta["src_unit"], raw)
            if v_ugm3 is None:
                skipped["unsupported_unit"] += 1
                continue
            lo, hi = PARAMS[param]["range"]
            if not (lo <= v_ugm3 <= hi):
                skipped["bad_value"] += 1
                continue
            ts_utc = (m.get("datetime") or {}).get("utc") or ""
            ts = _parse_ts(ts_utc)
            if ts is None:
                skipped["bad_ts"] += 1
                continue
            obs.append({
                "station_id": meta["station_id"],
                "sensor_id": m.get("sensorsId"),
                "name": meta["name"],
                "lat": meta["lat"], "lon": meta["lon"],
                "parameter": param,
                "value": round(v_ugm3, 3), "unit": "µg/m³",
                "src_value": m.get("value"), "src_unit": meta["src_unit"],
                "ts": ts, "ts_utc": ts_utc,
            })
    obs.sort(key=lambda o: (o["station_id"] or 0, o["parameter"],
                            o["sensor_id"] or 0))
    return obs


def to_station_obs(obs):
    """pm25 obs -> the airindex station-obs schema {lat, lon, name, pm25,
    ts} (station_id rides along; qc ignores extras). Freshest sensor per
    station, matching airfield's multi-instrument rule."""
    best = {}
    for o in obs:
        if o["parameter"] != "pm25":
            continue
        cur = best.get(o["station_id"])
        if cur is None or o["ts"] > cur["ts"]:
            best[o["station_id"]] = o
    return [{"lat": o["lat"], "lon": o["lon"], "name": o["name"],
             "pm25": o["value"], "ts": o["ts"],
             "station_id": o["station_id"]}
            for o in sorted(best.values(),
                            key=lambda o: o["station_id"] or 0)]


def _zero_skipped():
    return {"unsupported_unit": 0, "bad_value": 0, "bad_ts": 0,
            "bad_row": 0}


def fetch(api_key: Optional[str] = None, client=None, bbox=BBOX,
          sleep=None, time_func=None) -> dict:
    """Pull every PARAMS sensor in `bbox` -> normalized obs bundle.

    api_key: explicit key (tests); falls back to env OPENAQ_API_KEY.
             Falsy -> status "no key — owner blocker", obs/stations empty
             (empty-honest; the field builds on the model alone and the
             provenance block says so).
    client:  httpx.Client-compatible transport — injectable so tests
             never touch the network; created and closed internally
             when not supplied.
    sleep / time_func: injectable for tests (sleep recorder, frozen clock).
    """
    t = (time_func or time.time)()
    sleep = sleep or time.sleep
    time_func = time_func or time.time
    stats = {"requests": 0, "responses": 0, "retries_429": 0,
             "pages": 0, "locations_failed": 0, "locations_rate_limited": 0}
    skipped = _zero_skipped()
    bundle = {"status": "ok", "source": "openaq-v3", "fetched_at": t,
              "obs": [], "stations": [], "skipped": skipped, **stats}

    key = api_key or os.environ.get(ENV_KEY)
    if not key:
        bundle["status"] = "no key — owner blocker"
        return bundle

    own = client is None
    c = client or httpx.Client(
        timeout=httpx.Timeout(30.0, connect=8.0),
        headers={"User-Agent": "alive108-ingest-openaq/0.1"})
    headers = {"X-API-Key": key}
    try:
        locations = _fetch_locations(c, headers, bbox, sleep,
                                     time_func, stats)
        latest = {loc["id"]: _fetch_latest(c, headers, loc["id"], sleep,
                                           time_func, stats)
                  for loc in locations if loc.get("id") is not None}
        obs = normalize(locations, latest, skipped)
        bundle.update(obs=obs, stations=to_station_obs(obs), **stats)
        if stats["locations_rate_limited"] and not obs:
            bundle["status"] = "unavailable: rate-limited (429)"
    except _RateLimited:
        bundle.update(status="unavailable: rate-limited (429)", **stats)
    except httpx.HTTPStatusError as e:
        code = e.response.status_code if e.response is not None else "?"
        bundle.update(status=f"unavailable: HTTP {code}", **stats)
    except httpx.HTTPError as e:
        bundle.update(status=f"unavailable: {type(e).__name__}", **stats)
    finally:
        if own:
            c.close()
    return bundle


if __name__ == "__main__":
    import json
    # Smoke probe — reads the key from env; prints the bundle MINUS obs so
    # nothing sensitive or bulky leaves the terminal.
    out = fetch()
    out["obs"] = f"<{len(out['obs'])} rows>"
    print(json.dumps(out, indent=2, ensure_ascii=False))
