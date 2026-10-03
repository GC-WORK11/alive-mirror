"""WAQI (aqicn.org) station-ingest adapter — the drop-in measured-stations
source when OpenAQ is unavailable (key dead/banned) or alongside it.

WAQI republishes the CPCB/DPCC CAAQMS network — the same government
instruments OpenAQ mirrored, so Delhi coverage is comparable (~40 stations
inside the NCR bbox). Token is free (aqicn.org/data-platform/token/) and
keyed via WAQI_API_KEY; a missing key degrades to
'no key — owner blocker', never silently.

API shapes used here (api.waqi.info):
  GET /map/bounds/?latlng=<s><w>,<n><e>&token=<t>
      -> {"status":"ok","data":[{lat,lon,uid,aqi("151"|"-"),
          station:{name,time,geo}}]} — note `aqi` is a STRING and may be
          the dominant pollutant (pm10/o3), NOT necessarily pm2.5 — so
          this endpoint is used only for discovery; real readings come
          from the per-station feed.
  GET /feed/@<uid>/?token=<t>
      -> {"status":"ok","data":{aqi, time:{s,tz,v(epoch)},
          city:{name,geo}, iaqi:{pm25:{v},pm10:{v},no2:{v},o3:{v},
          co:{v},so2:{v}}, station:{name}}} — iaqi v is µg/m³ already.
  Body `status` is "ok"|"error"; error payloads carry data.message
  verbatim ("Invalid key", "Over quota", ...) into our status reason.

Contract — fetch(api_key=None, client=None, bbox=..., sleep=...) -> dict:
  status    "ok" | "no key — owner blocker" | "unavailable: <reason>"
  obs       normalized readings: {station_id (waqi uid), name, lat, lon,
            parameter, value (µg/m³), unit, src_value, src_unit, ts}
  stations  airindex station-obs schema for pm25 obs only —
            {lat, lon, name, pm25, ts, station_id}: feeds
            airindex.qc_stations() / build_field() inputs["stations"]
            directly.
  skipped   counters for honest accounting: no_pm25, bad_value, bad_ts,
            http_error (verbatim reason)
  secrets   the token travels as the `token` query param and is never
            printed, logged, or echoed into any return value.

grab_async(client, api_key=None, bbox=...) -> list is the airfield
variant — same stations, shaped (lat, lon, name, {"pm2_5": v}) to slot
into AirField._debias exactly like _grab_openaq's rows.
"""
import asyncio
import os
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

WAQI = "https://api.waqi.info"
ENV_KEY = "WAQI_API_KEY"
SOURCE = "waqi"

# NCR bbox (lon_min, lat_min, lon_max, lat_max) — mirrors airindex.BBOX.
BBOX = (76.75, 28.15, 77.95, 28.98)

MAX_FEED = 64              # per-refresh cap on /feed/@uid calls (~40 real)
MAX_ATTEMPTS = 3           # initial try + 2 retries on 429/over-quota
BACKOFF_BASE_S = 5.0
BACKOFF_CAP_S = 60.0
FEED_SEM = 12              # concurrent feeds in grab_async

# Pollutants we keep — WAQI iaqi names. All are already µg/m³; the
# plausibility ranges mirror ingest_openaq.PARAMS so a sensor glitch
# reports honestly instead of contaminating the blend.
PARAMS = {
    "pm25": {"range": (0.0, 1500.0)},
    "pm10": {"range": (0.0, 3000.0)},
    "no2": {"range": (0.0, 3000.0)},
    "o3": {"range": (0.0, 2000.0)},
    "co": {"range": (0.0, 60000.0)},
    "so2": {"range": (0.0, 3000.0)},
}


class _SourceDown(Exception):
    """The whole source failed — caller degrades to status unavailable."""


def _iso_to_epoch(s) -> Optional[float]:
    """'2026-10-03 12:00:00' / ISO strings -> epoch, or None."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(
            str(s).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _bounds(bbox):
    """airindex (lon_min, lat_min, lon_max, lat_max) -> WAQI latlng string."""
    lon0, lat0, lon1, lat1 = bbox
    return f"{lat0},{lon0},{lat1},{lon1}"


def _check_status(j: dict) -> None:
    """WAQI reports errors in-body: {'status':'error','data':'Invalid key'}
    or {'data':{'message': 'Over quota'}} — surface it verbatim."""
    if not isinstance(j, dict):
        raise _SourceDown("unexpected body type")
    if j.get("status") != "ok":
        data = j.get("data")
        if isinstance(data, dict):
            reason = data.get("message") or str(data)
        else:
            reason = str(data)
        raise _SourceDown(f"api error: {reason}")


def _get(client, url: str, params: dict, sleep, stats) -> httpx.Response:
    """GET with bounded 429 backoff; every call/response/retry counted."""
    for attempt in range(MAX_ATTEMPTS):
        stats["requests"] += 1
        r = client.get(url, params=params, timeout=30)
        stats["responses"] += 1
        if r.status_code == 429:
            stats["retries_429"] += 1
            if attempt == MAX_ATTEMPTS - 1:
                raise _SourceDown("HTTP 429 (rate limit persisted)")
            sleep(min(BACKOFF_CAP_S, BACKOFF_BASE_S * (2 ** attempt)))
            continue
        r.raise_for_status()
        return r
    raise _SourceDown("unreachable")


def _stations_from_bounds(j: dict) -> list:
    out = []
    for row in j.get("data") or []:
        st = row.get("station") or {}
        geo = st.get("geo") or []
        lat = geo[0] if len(geo) == 2 else row.get("lat")
        lon = geo[1] if len(geo) == 2 else row.get("lon")
        uid = row.get("uid")
        if uid is None or lat is None or lon is None:
            continue
        try:
            out.append({"uid": int(uid), "lat": float(lat),
                        "lon": float(lon),
                        "name": st.get("name") or f"waqi:{uid}"})
        except (TypeError, ValueError):
            continue
    return out


def _obs_from_feed(uid: int, meta: dict, j: dict,
                   skipped: dict) -> list:
    """One /feed/@uid body -> normalized obs rows (all PARAMS present)."""
    data = j.get("data") or {}
    t = data.get("time") or {}
    ts = t.get("v") if t.get("v") else _iso_to_epoch(t.get("s"))
    try:
        ts = float(ts)
    except (TypeError, ValueError):
        ts = None
    if ts is None:
        skipped["bad_ts"] += 1
        return []
    iaqi = data.get("iaqi") or {}
    name = ((data.get("station") or {}).get("name")) or meta["name"]
    obs = []
    for pname, rule in PARAMS.items():
        cell = iaqi.get(pname)
        if not isinstance(cell, dict):
            continue
        v = cell.get("v")
        try:
            v = float(v)
        except (TypeError, ValueError):
            continue
        lo, hi = rule["range"]
        if not lo <= v <= hi:
            skipped["bad_value"] += 1
            continue
        obs.append({
            "station_id": uid, "name": name,
            "lat": meta["lat"], "lon": meta["lon"],
            "parameter": pname, "value": v, "unit": "µg/m³",
            "src_value": v, "src_unit": "µg/m³",
            "ts": ts,
            "ts_utc": datetime.fromtimestamp(
                ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    if not any(o["parameter"] == "pm25" for o in obs):
        skipped["no_pm25"] += 1
    return obs


def fetch(api_key=None, client=None, bbox=BBOX, sleep=time.sleep) -> dict:
    """Pull live WAQI station obs into the airindex stations bundle."""
    t0 = time.time()
    key = api_key or os.environ.get(ENV_KEY)
    skipped = {"no_pm25": 0, "bad_value": 0, "bad_ts": 0, "http_error": 0}
    if not key:
        return {"status": "no key — owner blocker", "source": SOURCE,
                "fetched_at": t0, "stations": [], "obs": [],
                "skipped": skipped}
    own = client is None
    c = client or httpx.Client(
        timeout=httpx.Timeout(30.0, connect=8.0),
        headers={"User-Agent": "alive108-ingest/0.1"})
    stats = {"requests": 0, "responses": 0, "retries_429": 0}
    try:
        try:
            r = _get(c, f"{WAQI}/map/bounds/",
                     {"latlng": _bounds(bbox), "token": key},
                     sleep, stats)
            _check_status(r.json())
            metas = _stations_from_bounds(r.json())
        except (_SourceDown, httpx.HTTPError, ValueError) as e:
            return {"status": f"unavailable: {e}", "source": SOURCE,
                    "fetched_at": time.time(), "stations": [], "obs": [],
                    "skipped": skipped, "requests": stats["requests"]}
        obs, errs = [], []
        for meta in sorted(metas, key=lambda m: m["uid"])[:MAX_FEED]:
            try:
                r = _get(c, f"{WAQI}/feed/@{meta['uid']}/",
                         {"token": key}, sleep, stats)
                j = r.json()
                _check_status(j)
                obs.extend(_obs_from_feed(meta["uid"], meta, j, skipped))
            except (_SourceDown, httpx.HTTPError, ValueError) as e:
                skipped["http_error"] += 1
                errs.append(str(e)[:120])
                continue
        if metas and not obs and errs:
            return {"status": f"unavailable: {errs[0]} "
                    f"(all {len(errs)} station feeds failed)",
                    "source": SOURCE, "fetched_at": time.time(),
                    "stations": [], "obs": [], "skipped": skipped,
                    "requests": stats["requests"]}
        # freshest pm25 per station -> airindex stations schema
        best = {}
        for o in obs:
            if o["parameter"] != "pm25":
                continue
            prev = best.get(o["station_id"])
            if prev is None or o["ts"] > prev["ts"]:
                best[o["station_id"]] = o
        stations = [{"lat": o["lat"], "lon": o["lon"], "name": o["name"],
                     "pm25": o["value"], "ts": o["ts"],
                     "station_id": o["station_id"]}
                    for o in best.values()]
        out = {"status": "ok", "source": SOURCE, "fetched_at": time.time(),
               "stations": stations, "obs": obs, "skipped": skipped,
               "n_stations": len(metas), "requests": stats["requests"],
               "retries_429": stats["retries_429"]}
        if errs:
            out["feeds_failed"] = len(errs)
            out["feed_errors"] = sorted(set(errs))[:4]
        return out
    finally:
        if own:
            c.close()


async def grab_async(client: httpx.AsyncClient, api_key=None,
                     bbox=BBOX) -> list:
    """airfield._grab_openaq sibling — live stations as
    (lat, lon, name, {"pm2_5": v}) rows for the IDW/_debias blend.
    Returns [] without a key or on any upstream failure — the modelled
    field stands alone, exactly like the OpenAQ path."""
    key = api_key or os.environ.get(ENV_KEY)
    if not key:
        return []
    try:
        r = await client.get(f"{WAQI}/map/bounds/",
                             params={"latlng": _bounds(bbox),
                                     "token": key})
        r.raise_for_status()
        _check_status(r.json())
        metas = _stations_from_bounds(r.json())
    except (httpx.HTTPError, _SourceDown, ValueError):
        return []
    if not metas:
        return []

    sem = asyncio.Semaphore(FEED_SEM)
    out = []

    async def feed(meta):
        async with sem:
            try:
                r = await client.get(f"{WAQI}/feed/@{meta['uid']}/",
                                     params={"token": key})
                if r.status_code == 429:
                    await asyncio.sleep(6)
                    r = await client.get(f"{WAQI}/feed/@{meta['uid']}/",
                                         params={"token": key})
                r.raise_for_status()
                j = r.json()
                _check_status(j)
                skipped = {"no_pm25": 0, "bad_value": 0,
                           "bad_ts": 0, "http_error": 0}
                obs = _obs_from_feed(meta["uid"], meta, j, skipped)
                pm = [o for o in obs if o["parameter"] == "pm25"]
                if pm:
                    best = max(pm, key=lambda o: o["ts"])
                    out.append((meta["lat"], meta["lon"],
                                best["name"],
                                {"pm2_5": round(best["value"], 1)}))
            except (httpx.HTTPError, _SourceDown, ValueError):
                pass

    await asyncio.gather(*(feed(m) for m in metas[:MAX_FEED]))
    return out
