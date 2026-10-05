"""The 15-minute Delhi air index — an H3 res-8 field over NCR.

Implements the pipeline contract in docs/plan/05-backend-architecture.md §2:
every ~15 min an EventBridge-triggered worker (ingest_worker.py) calls
build_field() and stores the gzip snapshot.

Pipeline:
  1. Pull inputs, each stamped with provenance + age:
       model    — Open-Meteo/CAMS pm2_5 over the NCR sample grid (no key)
       stations — CPCB/DPCC instruments via the WAQI → CPCB → OpenAQ
       chain (WAQI_API_KEY / CPCB_API_KEY / OPENAQ_API_KEY;
                  optional — the field builds without it and the provenance
                  block says so explicitly, never silently)
       fires    — NASA FIRMS public 24h CSVs (no key) -> NW-belt smoke
                  modifier, applied to the MODEL PRIOR ONLY (stations then
                  correct it where they measure; reuses fires.py's own
                  smoke_modifier logic)
       met      — Open-Meteo 10 m wind + boundary-layer height ->
                  ventilation coefficient VC = BLH x U (m2/s)
  2. Station QC: drop >3 h stale, flatlines (>=3 identical readings), and
     >5-sigma spikes vs neighbour-blend expectation (robust sigma = MAD).
  3. Kalman-smooth each surviving station (same scalar filter + Q/R as
     airfield.AirField._smooth — we reuse the class, not a copy).
  4. Regression kriging: residuals = smoothed_obs - fire-adjusted model at
     each station, kriged onto the grid WITH variance via krige.KrigeField
     (falls back to an IDW residual blend with a distance-grown sigma when
     too few stations to fit a variogram). pm25 = model_prior + residual.
  5. Per cell: pm25, lo, hi (±1.96 sigma), n_stations_within_10km,
     nearest_station_km, src in {station, model, inferred}.

Grid: H3 resolution 8 when `h3` is installed (h3>=4 preferred — needed in
requirements.txt, owned by another lane). Without it we fall back to a
~0.74 km² lat/lon grid on the same bbox, cell ids "g8:<lat>:<lon>" — the
schema is identical and field.grid.system says which produced it.

Cell values are never invented: a cell is dropped only when there is no
model value AND no station to interpolate from.

Hardening contract (r3): each source is fetched with per-source
retry/backoff (RETRY_ATTEMPTS); a source that stays down degrades to an
"unavailable" bundle and only its contribution is lost — the field still
builds. Every field carries a `build` block (duration_ms, sources_used,
sources_degraded), per-source `attempts` in provenance, and QC reject
counts (qc.dropped_counts / dropped_total) so ingest health is
self-describing.

Realtime-honesty contract (r5): a degraded status carries the upstream
verdict verbatim — HTTP status codes survive ("unavailable: HTTP 401"
auth, "unavailable: HTTP 429" quota) rather than flattening to the
exception class; a source whose every read failed says so, never "ok"
with an empty list. Every bundle + provenance entry carries fetched_at,
n (observations contributed) and age so /health can render
"model: 48 pts, 42s old" per source.
"""
import concurrent.futures
import gzip
import json
import logging
import math
import os
import random
import sys
import time
from datetime import datetime, timezone
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import httpx  # noqa: E402

import airfield          # noqa: E402  sample grid, station coords, endpoints, Kalman
import fires as fires_mod  # noqa: E402  FIRMS CSV parsing + smoke_modifier
from core_engine import KrigeField  # noqa: E402  C++ where it loads (core_engine), krige.py otherwise

log = logging.getLogger("alive.airindex")

# Bounded fetch fan-out. The four sources are independent pulls and the
# per-station/per-satellite legs inside them are independent too — they
# ran strictly serial (the observed source of multi-minute build tails).
# executor.map preserves submission order, so bundles keep the exact row
# order the serial loops produced; concurrency stays under ingest_waqi's
# already-shipped FEED_SEM=12 burst precedent.
FETCH_WORKERS = 4   # source-level parallelism inside fetch_inputs
LEG_WORKERS = 8     # per-station (OpenAQ /latest) and per-CSV legs

try:
    import h3  # h3>=4 wanted; see report — requirements.txt owned elsewhere
except ImportError:
    h3 = None
try:
    import numpy as np
except ImportError:
    np = None

# NCR bbox for the index (doc 05 §2): lon_min, lat_min, lon_max, lat_max.
BBOX = (76.75, 28.15, 77.95, 28.98)
H3_RES = 8

# Fallback lat/lon grid sized to H3 res-8's ~0.74 km² (~0.86 km edge):
# 0.86 km / 110.6 km-per-deg-lat, 0.86 km / 99.4 km-per-deg-lon @28.6N.
_FB_DLAT = 0.0078
_FB_DLON = 0.0087

STALE_S = 3 * 3600          # QC: station readings older than 3 h are dropped
FLATLINE_MIN = 3            # QC: >=3 identical recent readings = dead sensor
FLATLINE_EPS = 0.5          # µg/m³ spread below which a series is "flat"
SPIKE_Z = 5.0               # QC: residual > 5 sigma vs neighbours is a spike
SPIKE_SIGMA_FLOOR = 8.0     # µg/m³ — MAD can be ~0 on a uniform field
OPENAQ_V3 = "https://api.openaq.org/v3"

# Per-source retry policy (doc 05 §2 ingest). A source that exhausts its
# attempts degrades to status "unavailable: ..." — the field still builds
# on whatever arrived; a failed source never kills a build.
#   model/met : cheap single HTTPS calls        -> 3 tries
#   fires     : each try pulls 4 multi-MB CSVs   -> 2 tries
#   stations  : each try paginates per-location  -> 2 tries
RETRY_ATTEMPTS = {"model": 3, "met": 3, "fires": 2, "stations": 2}
RETRY_BASE_S = 0.5          # backoff(k) = base * 2**(k-1), capped + jitter
RETRY_CAP_S = 8.0
RETRY_JITTER_S = 0.25


# ---------------------------------------------------------------- grid

def _h3_cells() -> list:
    """H3 res-8 cells covering the bbox polygon. h3-py 4.x: LatLngPoly +
    polygon_to_cells (h3.Polygon/h3shape_to_cells/polyfill are all gone)."""
    w, s, e, n = BBOX
    if hasattr(h3, "LatLngPoly"):
        poly = h3.LatLngPoly([(s, w), (s, e), (n, e), (n, w)])
        return list(h3.polygon_to_cells(poly, H3_RES))
    if hasattr(h3, "Polygon"):
        poly = h3.Polygon([(s, w), (s, e), (n, e), (n, w)])
        return list(h3.h3shape_to_cells(poly, H3_RES))
    geo = {"type": "Polygon", "coordinates": [[
        [w, s], [e, s], [e, n], [w, n], [w, s]]]}
    return list(h3.polyfill(geo, H3_RES, True))


def _fallback_cells() -> list:
    """~0.74 km² lat/lon stand-in grid when h3 is absent."""
    w, s, e, n = BBOX
    cells = []
    lat = s + _FB_DLAT / 2
    while lat <= n - _FB_DLAT / 4:
        lon = w + _FB_DLON / 2
        while lon <= e - _FB_DLON / 4:
            cells.append(f"g8:{lat:.5f}:{lon:.5f}")
            lon += _FB_DLON
        lat += _FB_DLAT
    return cells


def grid_cells() -> tuple:
    """-> (system_name, [cell_id]). system_name is 'h3' or 'latlon-fallback'."""
    if h3 is not None:
        try:
            return "h3", _h3_cells()
        except Exception:  # noqa: BLE001 - any h3 API drift -> fallback grid
            pass
    return "latlon-fallback", _fallback_cells()


def cell_center(cell: str) -> tuple:
    """-> (lat, lon) for either grid system."""
    if cell.startswith("g8:"):
        _, la, lo = cell.split(":")
        return float(la), float(lo)
    fn = getattr(h3, "cell_to_latlng", None) or getattr(h3, "h3_to_geo")
    lat, lon = fn(cell)
    return float(lat), float(lon)


# ---------------------------------------------------------------- helpers

_KY = 110.6   # km per degree latitude (matches krige.py)
_KX = 99.4    # km per degree longitude at 28.6N (matches krige.py)


def _km(lat1, lon1, lat2, lon2) -> float:
    return math.hypot((lat1 - lat2) * _KY, (lon1 - lon2) * _KX)


def _idw(pts: list, lat: float, lon: float) -> Optional[float]:
    """Inverse-distance (p=2) blend; pts are (lat, lon, value)."""
    num = den = 0.0
    for slat, slon, v in pts:
        d = _km(slat, slon, lat, lon)
        if d < 1e-4:
            return float(v)
        w = 1.0 / (d * d)
        num += w * float(v)
        den += w
    return num / den if den else None


def _pairwise_km(centers: list, pts: list):
    """(N,M) km distances; numpy when present, else list-of-lists."""
    if np is not None:
        C = np.asarray(centers, dtype=float)
        P = np.asarray(pts, dtype=float)
        dy = (C[:, 0][:, None] - P[:, 0][None, :]) * _KY
        dx = (C[:, 1][:, None] - P[:, 1][None, :]) * _KX
        return np.sqrt(dx * dx + dy * dy)
    return [[_km(c[0], c[1], p[0], p[1]) for p in pts] for c in centers]


def _idw_np(D, vals):
    """Vectorised IDW over columns of a precomputed (N,M) distance matrix."""
    D = np.maximum(D, 1e-4)
    w = 1.0 / (D * D)
    return (w * vals[None, :]).sum(axis=1) / w.sum(axis=1)


def _epoch(now) -> float:
    """build_field's `now`: float epoch, int epoch, or datetime."""
    if now is None:
        return time.time()
    if isinstance(now, datetime):
        return now.timestamp()
    return float(now)


def _iso(epoch_s: float) -> str:
    return datetime.fromtimestamp(epoch_s, tz=timezone.utc).isoformat(
        timespec="seconds")


# ---------------------------------------------------------------- QC

def qc_stations(stations: list, model_est=None, now: Optional[float] = None):
    """Station QC per doc 05 §2. -> (survivors, dropped_report).

    stations: [{lat, lon, name, pm25, ts(epoch), series?(recent values)}]
    Drops, in order:
      malformed — lat/lon/pm25 missing or non-numeric (bad upstream row;
                  it must not crash the build)
      stale    — reading older than 3 h
      flatline — >=FLATLINE_MIN identical recent readings (series needed;
                 single-shot sources can't flatline-check and are kept)
      spike    — |value - neighbour expectation| > 5 sigma, sigma a
                 floored MAD over all residuals. The expectation is the
                 MEDIAN of other stations within 40 km (median of all
                 others when <3 in range, else the model prior) — median,
                 not mean, so a planted spike can't mask itself by
                 dragging its neighbours' expectations with it.
    """
    now = _epoch(now)
    dropped = {"malformed": [], "stale": [], "flatline": [], "spike": []}
    kept = []
    for s in stations:
        try:
            float(s["lat"]), float(s["lon"]), float(s["pm25"])
        except (KeyError, TypeError, ValueError):
            dropped["malformed"].append(
                s.get("name") if isinstance(s, dict) else repr(s)[:40])
            continue
        try:
            stale = s.get("ts") is None or now - float(s["ts"]) > STALE_S
        except (TypeError, ValueError):
            stale = True  # unreadable timestamp -> treat as stale
        if stale:
            dropped["stale"].append(s.get("name"))
            continue
        try:
            ser = [float(x) for x in (s.get("series") or [])
                   if x is not None]
        except (TypeError, ValueError):
            ser = []  # unreadable series: no flatline evidence -> keep
        if len(ser) >= FLATLINE_MIN and max(ser) - min(ser) < FLATLINE_EPS:
            dropped["flatline"].append(s.get("name"))
            continue
        s2 = dict(s)
        s2["lat"], s2["lon"] = float(s["lat"]), float(s["lon"])
        s2["pm25"] = float(s["pm25"])
        kept.append(s2)

    residuals = []
    for i, s in enumerate(kept):
        near = sorted(o["pm25"] for j, o in enumerate(kept)
                      if j != i and _km(o["lat"], o["lon"],
                                        s["lat"], s["lon"]) <= 40.0)
        pool = near if len(near) >= 3 else \
            sorted(o["pm25"] for j, o in enumerate(kept) if j != i)
        pred = None
        if len(pool) >= 3:
            pred = pool[len(pool) // 2] if len(pool) % 2 else \
                (pool[len(pool) // 2 - 1] + pool[len(pool) // 2]) / 2
        elif model_est is not None:
            pred = model_est(s["lat"], s["lon"])
        s["_qc_resid"] = 0.0 if pred is None else float(s["pm25"]) - pred
        residuals.append(s["_qc_resid"])
    if residuals:
        med = sorted(residuals)[len(residuals) // 2]
        mad = sorted(abs(r - med) for r in residuals)[len(residuals) // 2]
        sigma = max(SPIKE_SIGMA_FLOOR, 1.4826 * mad)
    else:
        sigma = SPIKE_SIGMA_FLOOR
    out = []
    for s in kept:
        if abs(s["_qc_resid"]) > SPIKE_Z * sigma:
            dropped["spike"].append(s.get("name"))
        else:
            s.pop("_qc_resid", None)
            out.append(s)
    return out, dropped


# ---------------------------------------------------------------- inputs

class UpstreamError(Exception):
    """A source fetch failed in a retryable way; the class name lands in
    the bundle's status string ('unavailable: UpstreamError')."""


class _SourceDown(Exception):
    """Raised by a fetcher when the whole source answered but is unusable
    (e.g. every per-location read failed). str(e) is the verbatim
    upstream reason and lands in the status string via _describe_error —
    a quota/auth HTTP code stays visible instead of flattening to
    'unavailable: HTTPStatusError'."""


def _describe_error(err) -> str:
    """Status suffix for a failed fetch — carries the real upstream
    verdict so /health can say *why*, not just *that*:

      _SourceDown        -> its own verbatim reason ("HTTP 401 (all 3
                            location reads failed)")
      HTTPStatusError    -> "HTTP 429" — the status code is the story
                            for quota (429) and auth (401/403) failures
      anything else      -> "<ExcType>: <msg>" verbatim, e.g.
                            "ConnectError: [Errno 111] Connection refused"

    Truncated so a stack fragment can't balloon a health payload."""
    if isinstance(err, _SourceDown):
        return str(err).strip() or "source down"
    if isinstance(err, httpx.HTTPStatusError):
        resp = getattr(err, "response", None)
        code = getattr(resp, "status_code", None)
        if code:
            return f"HTTP {code}"
        # fakes may raise without a Response — keep the message
        msg = str(err).strip()
        return f"HTTPStatusError: {msg}" if msg else "HTTPStatusError"
    name = type(err).__name__
    msg = str(err).strip()
    if msg and msg != name:
        return f"{name}: {msg[:120]}"
    return name


# Empty bundle skeletons: what a source contributes while it is down. A
# failed fetch NEVER raises out of fetch_inputs — it degrades to this
# shape with status "unavailable: ..." so the field still builds.
_EMPTY = {
    "model": {"source": "open-meteo/cams", "samples": []},
    "met": {"source": "open-meteo", "wind_ms": None, "wind_deg": None,
            "blh_m": None, "vc_m2s": None},
    "fires": {"source": "nasa-firms-public-csv", "modifier": 1.0,
              "n_fires": 0, "belt_fires": 0},
    "stations": {"source": "openaq-v3", "stations": []},
}


def _bundle_n(name: str, bundle: dict):
    """Observations a source bundle contributed (the 'N pts' in
    /health's 'model: 48 pts, 42s old'):

      model    -> len(samples)  — CAMS grid points fetched
      stations -> len(stations) — instrument readings fetched
      fires    -> n_fires       — FIRMS rows in the 24 h CSVs
      met      -> 1 when a wind/BLH reading landed, else 0 (it is a
                  single point read, not a sample set)

    0 for a degraded/empty bundle — never invented."""
    try:
        if name == "model":
            return len(bundle.get("samples") or [])
        if name == "stations":
            return len(bundle.get("stations") or [])
        if name == "fires":
            return int(bundle.get("n_fires") or 0)
        if name == "met":
            return 1 if any(bundle.get(k) is not None for k in
                            ("wind_ms", "blh_m", "vc_m2s")) else 0
    except (TypeError, ValueError):
        pass
    return 0


def _retry(call, attempts, sleep) -> tuple:
    """Run call() up to `attempts` times, exponential backoff + jitter.

    -> (result_or_None, tries, last_exc_or_None). Only raised exceptions
    retry; a returned "unavailable: ..." bundle is a definitive answer
    (e.g. no API key configured) and is NOT retried."""
    tries = max(1, int(attempts))
    err = None
    for k in range(1, tries + 1):
        try:
            return call(), k, None
        except Exception as e:  # noqa: BLE001 - upstream flake -> retry
            err = e
            if k < tries:
                sleep(min(RETRY_CAP_S, RETRY_BASE_S * (2 ** (k - 1)))
                      + random.uniform(0.0, RETRY_JITTER_S))
    return None, tries, err


def _run_source(name, call, *, attempts=None, sleep=None) -> dict:
    """Retry `call` per RETRY_ATTEMPTS[name]; on exhaustion return the
    empty bundle marked 'unavailable: <verbatim reason>' (HTTP codes
    survive — 'HTTP 429' for quota, 'HTTP 401' for auth). The returned
    bundle always carries 'attempts' + 'n' so provenance shows both
    source flakiness and how much each source actually contributed;
    fetched_at stamps the LAST attempt, not the first."""
    out, tries, err = _retry(call, attempts or RETRY_ATTEMPTS[name],
                             sleep or time.sleep)
    if out is None:
        out = dict(_EMPTY[name])
        out["status"] = f"unavailable: {_describe_error(err)}"
        out["fetched_at"] = time.time()   # last contact attempt, honestly
    out["attempts"] = tries
    out["n"] = _bundle_n(name, out)
    return out


def _safe_source(name, call) -> dict:
    """Last-resort guard inside fetch_inputs: even if a fetcher itself is
    broken — or a test double raises straight through — the bundle comes
    back well-formed and marked unavailable. One source's bug can never
    abort the other three or the field build."""
    t = time.time()
    try:
        out = call()
        if not isinstance(out, dict):
            raise TypeError(f"fetcher returned {type(out).__name__}")
        merged = dict(_EMPTY[name])
        merged.update(out)
        merged.setdefault("status", "ok")
        merged.setdefault("fetched_at", t)
        merged.setdefault("attempts", 1)
        merged["n"] = _bundle_n(name, merged)
        return merged
    except Exception as e:  # noqa: BLE001 - degrade this source only
        out = dict(_EMPTY[name])
        out.update({"status": f"unavailable: {_describe_error(e)}",
                    "fetched_at": t, "attempts": 1, "n": 0})
        return out


def _fetch_model_once(client) -> dict:
    """CAMS pm2_5 at the NCR sample grid — one multi-point request.
    Raises on failure; _fetch_model owns retry + degradation."""
    pts = airfield._grid_points()
    r = client.get(airfield.OPEN_METEO, params={
        "latitude": ",".join(f"{p[0]}" for p in pts),
        "longitude": ",".join(f"{p[1]}" for p in pts),
        "current": "pm2_5",
    }, timeout=30)
    r.raise_for_status()
    payload = r.json()
    if isinstance(payload, dict):
        payload = [payload]
    samples = []
    for (lat, lon, name), blk in zip(pts, payload):
        v = (blk.get("current") or {}).get("pm2_5")
        if v is not None:
            samples.append({"lat": lat, "lon": lon, "name": name,
                            "pm25": float(v)})
    return {"status": "ok", "source": "open-meteo/cams",
            "fetched_at": time.time(), "samples": samples}


def _fetch_model(client, *, attempts=None, sleep=None) -> dict:
    return _run_source("model", lambda: _fetch_model_once(client),
                       attempts=attempts, sleep=sleep)


def _fetch_met_once(client) -> dict:
    """10 m wind + boundary-layer height at NCR centre -> ventilation VC.
    Raises on failure; _fetch_met owns retry + degradation."""
    r = client.get(airfield.METEO, params={
        "latitude": 28.61, "longitude": 77.21,
        "current": "wind_speed_10m,wind_direction_10m",
        "hourly": "boundary_layer_height",
        "forecast_days": 1, "wind_speed_unit": "ms", "timezone": "UTC",
    }, timeout=30)
    r.raise_for_status()
    j = r.json()
    cur = j.get("current") or {}
    wind_ms = cur.get("wind_speed_10m")
    wind_deg = cur.get("wind_direction_10m")
    blh = None
    hourly = j.get("hourly") or {}
    times, blhs = hourly.get("time") or [], hourly.get(
        "boundary_layer_height") or []
    if times and blhs:
        # nearest hourly slot to now
        now = time.time()
        best_i, best_d = None, 9e18
        for i, ts in enumerate(times):
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                d = abs(dt.timestamp() - now)
                if d < best_d and blhs[i] is not None:
                    best_i, best_d = i, d
            except ValueError:
                continue
        if best_i is not None:
            blh = float(blhs[best_i])
    vc = blh * wind_ms if (blh is not None and wind_ms is not None) else None
    return {"status": "ok", "source": "open-meteo",
            "fetched_at": time.time(),
            "wind_ms": wind_ms, "wind_deg": wind_deg,
            "blh_m": blh, "vc_m2s": vc}


def _fetch_met(client, *, attempts=None, sleep=None) -> dict:
    return _run_source("met", lambda: _fetch_met_once(client),
                       attempts=attempts, sleep=sleep)


def _fetch_fires_once(client, wind_deg) -> dict:
    """NASA FIRMS public CSVs -> belt fire count + smoke modifier.

    Reuses fires._parse_rows (same bbox + confidence normalisation) and
    FireField.smoke_modifier on a detached instance — no async needed and
    the modifier math stays single-sourced. One missing satellite CSV is
    fine; ALL of them failing raises UpstreamError (retried upstream)."""
    def _one(path, instrument):
        try:
            r = client.get(fires_mod.CSV_BASE + path, timeout=45)
            r.raise_for_status()
            return fires_mod._parse_rows(r.text, instrument), True
        except httpx.HTTPError:
            # one missing snapshot must not kill the layer
            return [], False
    # The four satellite CSVs are independent multi-MB pulls — fetched in
    # parallel via map (order preserved -> same rows in the same order).
    workers = min(4, len(fires_mod.PUBLIC_CSVS))
    if workers > 1:
        with concurrent.futures.ThreadPoolExecutor(
                max_workers=workers) as ex:
            results = list(ex.map(lambda pi: _one(*pi),
                                  fires_mod.PUBLIC_CSVS))
    else:
        results = [_one(*pi) for pi in fires_mod.PUBLIC_CSVS]
    rows, ok = [], 0
    for parsed, good in results:
        rows += parsed
        ok += int(good)
    if not ok:
        raise UpstreamError("all FIRMS CSVs failed")
    ff = fires_mod.FireField()
    ff._fires = rows
    ff._status = "live"
    ff._wind_deg = wind_deg
    return {"status": "ok", "source": "nasa-firms-public-csv",
            "fetched_at": time.time(), "modifier": ff.smoke_modifier(),
            "n_fires": len(rows),
            "belt_fires": len([f for f in rows if f.get("belt")])}


def _fetch_fires(client, wind_deg, *, attempts=None, sleep=None) -> dict:
    return _run_source("fires",
                       lambda: _fetch_fires_once(client, wind_deg),
                       attempts=attempts, sleep=sleep)


def _fetch_stations_once(client) -> dict:
    """CPCB/DPCC instruments via OpenAQ v3 — sync variant of
    airfield.AirField._grab_stations' OpenAQ leg that also keeps each
    reading's UTC
    timestamp so QC can enforce the 3 h staleness rule. Without
    OPENAQ_API_KEY the source is marked 'unavailable: no key' — explicit,
    never silent (00-README open item #1); that is a returned bundle,
    not an exception, so it is NOT retried."""
    t = time.time()
    key = os.environ.get("OPENAQ_API_KEY")
    if not key:
        return {"status": "unavailable: no key", "source": "openaq-v3",
                "fetched_at": t, "stations": []}
    headers = {"X-API-Key": key}
    r = client.get(f"{OPENAQ_V3}/locations", headers=headers, params={
        "bbox": f"{BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]}",
        "parameters_id": 2, "limit": 200,
    }, timeout=30)
    r.raise_for_status()
    sensors = {}
    for loc in r.json().get("results", []):
        coords = loc.get("coordinates") or {}
        for s in loc.get("sensors", []):
            if (s.get("parameter") or {}).get("id") == 2:
                sensors[s["id"]] = {
                    "lat": coords.get("latitude"),
                    "lon": coords.get("longitude"),
                    "name": loc.get("name") or f"station {loc.get('id')}",
                    "loc_id": loc["id"],
                }
    # Per-location reads stay individually tolerant (one sick location
    # must not sink the layer — same rule as airfield._grab_stations), but
    # failures are COUNTED: when every read fails the source is down, not
    # "reporting zero stations". _SourceDown carries the verbatim reason
    # (HTTP 401/403 auth, HTTP 429 quota) into the bundle status — a
    # stations bundle that is really a quota error must never say "ok".
    stations, loc_errs = [], []
    loc_ids = sorted({v["loc_id"] for v in sensors.values()})

    def _one_loc(loc_id):
        """-> (station_row_or_None, error_or_None)."""
        try:
            r = client.get(f"{OPENAQ_V3}/locations/{loc_id}/latest",
                           headers=headers,
                           params={"limit": 100}, timeout=30)
            r.raise_for_status()
            best = {}
            for m in r.json().get("results", []):
                meta = sensors.get(m.get("sensorsId"))
                v = m.get("value")
                if meta and v is not None and 0 <= v <= 1500:
                    ts = (m.get("datetime") or {}).get("utc") or ""
                    if not best or ts > best["ts"]:
                        best = {"ts": ts, "meta": meta, "v": float(v)}
            if not best:
                return None, None
            try:
                ts = datetime.fromisoformat(
                    best["ts"].replace("Z", "+00:00")).timestamp()
            except ValueError:
                ts = None
            meta = best["meta"]
            return {"lat": meta["lat"], "lon": meta["lon"],
                    "name": meta["name"], "pm25": best["v"],
                    "ts": ts}, None
        except (httpx.HTTPError, ValueError) as e:
            return None, _describe_error(e)

    # Per-location reads were serial (up to ~50 x 30s-timeout calls — the
    # dominant tail on a slow upstream); map over them with a bounded pool.
    # map preserves loc_ids order -> same station + error ordering.
    workers = min(LEG_WORKERS, len(loc_ids))
    if workers > 1:
        with concurrent.futures.ThreadPoolExecutor(
                max_workers=workers) as ex:
            loc_results = list(ex.map(_one_loc, loc_ids))
    else:
        loc_results = [_one_loc(l) for l in loc_ids]
    for st_row, err in loc_results:
        if st_row is not None:
            stations.append(st_row)
        if err is not None:
            loc_errs.append(err)
    if loc_errs and len(loc_errs) == len(loc_ids):
        raise _SourceDown(
            f"{loc_errs[0]} (all {len(loc_ids)} location reads failed)")
    out = {"status": "ok", "source": "openaq-v3",
           "fetched_at": time.time(), "stations": stations,
           "n_locations": len(loc_ids)}
    if loc_errs:  # partial loss is reported, never hidden
        out["locations_failed"] = len(loc_errs)
        out["location_errors"] = sorted(set(loc_errs))[:4]
    return out


def _fetch_stations(client, *, attempts=None, sleep=None) -> dict:
    """WAQI first (api.waqi.info republishes the same CPCB/DPCC CAAQMS
    instruments and is the only live route from prod — verified by a
    Fargate probe 2026-10-04: api.data.gov.in is TCP-refused even from
    ap-south-1), then CPCB data.gov.in keyed-attempt (adapter kept for
    an India-reachable egress later), then OpenAQ last — the owner's
    key is revoked but the path stays for anyone else's.

    A feed wins only when it answers 'ok' AND yields stations; the
    winner stamps the bundle `source` and the losers' statuses ride
    along as waqi_status/cpcb_status/openaq_status so the degradation
    is visible, not hidden. When every feed loses, the headline is the
    first REAL upstream verdict (a 'no key' placeholder never masks a
    refused/401 behind it); with no keys at all it is the primary's own
    'no key — owner blocker'. The loser statuses also survive a raising
    leg: `tried` outlives `_try`, so even the degraded bundle from
    _run_source names what the earlier feeds did."""
    tried = {}

    def _try():
        wb = None
        if os.environ.get("WAQI_API_KEY"):
            try:
                import ingest_waqi
                wb = ingest_waqi.fetch(client=client)
            except Exception as e:  # noqa: BLE001 — surface, never crash
                wb = {"status": f"unavailable: {_describe_error(e)}",
                      "source": "waqi", "fetched_at": time.time(),
                      "stations": []}
            tried["waqi_status"] = wb.get("status")
            if wb.get("status") == "ok" and wb.get("stations"):
                return wb
        else:
            tried["waqi_status"] = "skipped: no key"
        # keyed attempt only — api.data.gov.in is refused from this
        # egress today; the adapter returns fast-bounded bundles, never
        # raises on upstream failure.
        import ingest_cpcb
        cb = ingest_cpcb.fetch(client=client)
        tried["cpcb_status"] = cb.get("status")
        if cb.get("status") == "ok" and cb.get("stations"):
            cb["waqi_status"] = tried["waqi_status"]
            return cb
        try:
            ob = _fetch_stations_once(client)
        except Exception as e:
            tried["openaq_status"] = f"raised: {_describe_error(e)}"
            raise           # retryable — _run_source owns the backoff
        tried["openaq_status"] = ob.get("status")
        if ob.get("status") == "ok" and ob.get("stations"):
            ob["waqi_status"] = tried["waqi_status"]
            ob["cpcb_status"] = tried["cpcb_status"]
            return ob
        # All three lost. Headline the first bundle whose status is a
        # real upstream verdict (not a 'no key' placeholder) — in chain
        # order that's the primary's own reason; a later real verdict
        # (e.g. OpenAQ's HTTP 401) beats an earlier placeholder so the
        # status names the actual failure.
        headline = cb
        for b in (wb, cb, ob):
            if b and "no key" not in (b.get("status") or ""):
                headline = b
                break
        for k, v in tried.items():
            headline.setdefault(k, v)
        return headline
    out = _run_source("stations", _try, attempts=attempts, sleep=sleep)
    for k, v in tried.items():
        out.setdefault(k, v)
    return out


def fetch_inputs(now=None, client=None) -> dict:
    """Pull all four upstreams. Every bundle carries status + fetched_at
    + attempts + n (observations contributed) + age_s (staleness vs the
    `now` reference — 'model: 48 pts, 42s old' for /health); each source
    is retried per RETRY_ATTEMPTS and a failed source degrades to status
    'unavailable: <verbatim reason>' — HTTP status codes survive
    ('unavailable: HTTP 429' for quota, 'HTTP 401' for auth), never a
    bare 'unavailable'. The field still builds on what arrived
    (offline-ish by contract). _safe_source is the belt-and-suspenders:
    even a raising fetcher cannot abort the other three sources."""
    now = _epoch(now)
    own = client is None
    c = client or httpx.Client(
        timeout=httpx.Timeout(30.0, connect=8.0),
        headers={"User-Agent": "alive108-airindex/0.1"})
    t_fetch = time.time()
    # Per-source wall time — every bundle is returned, never raised, so a
    # slow leg used to hide inside one opaque multi-minute fetch block.
    src_ms = {}

    def _timed(name, call):
        t = time.time()
        out = _safe_source(name, call)
        src_ms[name] = round((time.time() - t) * 1000)
        return out
    # The four sources are independent network pulls — run them in a
    # bounded pool so wall time is the SLOWEST source, not their sum
    # (serial legs were the multi-minute tail). fires still waits for met
    # because its smoke_modifier needs the real wind direction; only the
    # fires worker idles on met_f, met itself is a single cheap call.
    try:
        with concurrent.futures.ThreadPoolExecutor(
                max_workers=FETCH_WORKERS) as ex:
            met_f = ex.submit(_timed, "met", lambda: _fetch_met(c))
            model_f = ex.submit(_timed, "model", lambda: _fetch_model(c))
            stations_f = ex.submit(_timed, "stations",
                                   lambda: _fetch_stations(c))
            fires_f = ex.submit(
                _timed, "fires",
                lambda: _fetch_fires(c, met_f.result().get("wind_deg")))
            met, model = met_f.result(), model_f.result()
            fires, stations = fires_f.result(), stations_f.result()
    finally:
        if own:
            c.close()
    fetch_ms = round((time.time() - t_fetch) * 1000)
    for b in (model, met, fires, stations):
        fa = b.get("fetched_at")
        try:
            # just-fetched -> ~0 s; injected/older fetched_at -> honest
            # staleness. Clamped: a fetched_at a hair after `now` is
            # clock slop, not time travel.
            b["age_s"] = round(max(0.0, now - float(fa)), 1) \
                if fa is not None else None
        except (TypeError, ValueError):
            b["age_s"] = None
    # Stage visibility (log.warning — the app's CloudWatch-visible level;
    # INFO never reaches the log group): one line per fetch wall-clock
    # with each source's ms + status + contribution. A degraded source
    # names itself here instead of only on the next /health render.
    log.warning(
        "ingest fetch wall=%dms met=%dms[%s] model=%dms[%s] "
        "fires=%dms[%s] stations=%dms[%s]",
        fetch_ms,
        src_ms.get("met", -1), met.get("status"),
        src_ms.get("model", -1), model.get("status"),
        src_ms.get("fires", -1), fires.get("status"),
        src_ms.get("stations", -1), stations.get("status"))
    return {"model": model, "met": met, "fires": fires,
            "stations": stations}


# ---------------------------------------------------------------- build

def build_field(now=None, *, inputs: Optional[dict] = None,
                client=None) -> dict:
    """-> the field dict (see module docstring). `inputs` may be injected
    wholesale (tests, replay) — then nothing touches the network."""
    t0 = time.time()
    now = _epoch(now)
    injected = inputs is not None
    if inputs is None:
        inputs = fetch_inputs(now, client=client)
    if not isinstance(inputs, dict):
        inputs = {}
    t_inputs = time.time()  # live fetch wall time ends here

    def _bundle(key):
        b = inputs.get(key)
        return b if isinstance(b, dict) else {}

    model_in = _bundle("model")
    met_in = _bundle("met")
    fires_in = _bundle("fires")
    st_in = _bundle("stations")

    # --- model prior, fire-adjusted -------------------------------------
    modifier = fires_in.get("modifier")
    try:
        modifier = min(fires_mod.MAX_MODIFIER,
                       max(1.0, float(modifier)))
    except (TypeError, ValueError):
        modifier = 1.0
    model_pts = []  # (lat, lon, adjusted pm25)
    _samples = model_in.get("samples")
    if not isinstance(_samples, list):
        _samples = []
    for s in _samples:
        try:
            v = s.get("pm25")
            if v is None:
                continue
            model_pts.append((float(s["lat"]), float(s["lon"]),
                              float(v) * modifier))
        except (AttributeError, KeyError, TypeError, ValueError):
            continue  # one bad model row must not sink the prior

    def model_est(lat, lon):
        return _idw(model_pts, lat, lon) if model_pts else None

    t_prior = time.time()
    # --- station QC + Kalman smoothing ----------------------------------
    raw_st = st_in.get("stations")
    if not isinstance(raw_st, list):
        raw_st = []
    survivors, dropped = qc_stations(raw_st, model_est, now)
    smoother = airfield.AirField()  # reuse production scalar Kalman (Q=12, R=60)
    for s in survivors:
        try:
            s["pm25"] = round(float(smoother._smooth(
                "pm2_5", s["lat"], s["lon"], float(s["pm25"]))), 2)
        except (TypeError, ValueError):
            s["pm25"] = None  # smoothed value unusable -> IDW skips it

    # --- residuals = smoothed obs - adjusted model ----------------------
    resids = []  # (lat, lon, name, resid)
    for s in survivors:
        if s.get("pm25") is None:
            continue
        base = model_est(s["lat"], s["lon"])
        if base is None:
            continue
        s["residual"] = round(float(s["pm25"]) - base, 2)
        resids.append((s["lat"], s["lon"], s.get("name"), s["residual"]))
    rk = KrigeField().fit(
        [(la, lo, nm, {"pm2_5": r}) for la, lo, nm, r in resids])
    t_qc = time.time()

    # --- grid -----------------------------------------------------------
    system, cells = grid_cells()
    centers = [cell_center(c) for c in cells]
    st_locs = [(s["lat"], s["lon"]) for s in survivors]

    # precomputed (N,M) distance matrices: cells x model pts, cells x stations
    # (numpy path only — the pure-python fallback loop computes per cell)
    Dm = Ds = None
    if np is not None:
        if model_pts:
            Dm = _pairwise_km(centers, [(p[0], p[1]) for p in model_pts])
        if st_locs:
            Ds = _pairwise_km(centers, st_locs)
        mv = np.asarray([p[2] for p in model_pts]) if model_pts else None
        base_arr = _idw_np(Dm, mv) if Dm is not None else None
        if Ds is not None:
            n10_arr = (Ds <= 10.0).sum(axis=1)
            nearest_arr = Ds.min(axis=1)
            rv = np.asarray([r[3] for r in resids]) if resids else None
            resid_arr = _idw_np(Ds, rv) if rv is not None else None
        else:
            n10_arr = np.zeros(len(cells), dtype=int)
            nearest_arr = np.full(len(cells), np.inf)
            resid_arr = None
    else:
        base_arr = resid_arr = n10_arr = nearest_arr = None

    resid_spread = 0.0
    if len(resids) >= 2:
        vs = sorted(r[3] for r in resids)
        mu = sum(vs) / len(vs)
        resid_spread = math.sqrt(
            sum((v - mu) ** 2 for v in vs) / len(vs))

    out_cells = {}
    sig_sum = 0.0
    pm_sum = 0.0
    for i, cid in enumerate(cells):
        lat, lon = centers[i]
        if np is not None:
            base = float(base_arr[i]) if base_arr is not None else None
            n10 = int(n10_arr[i])
            near = (float(nearest_arr[i])
                    if math.isfinite(float(nearest_arr[i])) else None)
        else:
            base = model_est(lat, lon)
            if st_locs:
                ds = [_km(lat, lon, a, b) for a, b in st_locs]
                near = min(ds)
                n10 = sum(1 for d in ds if d <= 10.0)
            else:
                near, n10 = None, 0
        if base is None and not survivors:
            continue  # nothing at all to estimate from — drop, don't invent

        kr = rk.estimate(lat, lon) if rk.on else None
        if base is None:
            # no model coverage: pure station IDW
            pm = _idw([(s["lat"], s["lon"], s["pm25"]) for s in survivors
                       if s.get("pm25") is not None], lat, lon)
            sd = max(0.15 * pm, 5.0) if pm is not None else None
        elif kr is not None:
            mu_r, sd_r = kr
            pm = base + mu_r
            # krige sigma covers interpolation error only — carry the same
            # 12% instrument/model-error floor as airfield plus the measured
            # SIGMA_CAL total-error inflation, so snapshot bands mean what
            # the per-query band means (coverage measured in
            # data/field_validation.md)
            sd = math.sqrt(sd_r * sd_r + (0.12 * pm) ** 2) \
                * airfield.SIGMA_CAL
        else:
            # krige off (too few/non-constant residuals): IDW residual blend
            if np is not None and resid_arr is not None:
                r = float(resid_arr[i])
            else:
                r = _idw([(a, b, rr) for a, b, _n, rr in resids],
                         lat, lon) if resids else 0.0
            pm = base + (r or 0.0)
            # sigma grows from the instrument floor toward the observed
            # residual spread with distance from the nearest station —
            # then the same measured total-error inflation as the krige
            # path (residual spread alone still undercovers station truth)
            decay = 1.0 - math.exp(-(near or 30.0) / 15.0)
            sd = math.sqrt((0.12 * pm) ** 2
                           + (min(resid_spread, 60.0) * decay) ** 2
                           + (0.05 * pm) ** 2) * airfield.SIGMA_CAL \
                if survivors else max(0.15 * pm, 3.0) * airfield.SIGMA_CAL
        if pm is None or sd is None:
            continue
        pm = max(0.0, pm)
        lo = max(0.0, pm - 1.96 * sd)
        hi = pm + 1.96 * sd
        out_cells[cid] = {
            "pm25": round(pm, 2),
            "lo": round(lo, 2),
            "hi": round(hi, 2),
            "sigma": round(sd, 3),
            "n_stations_within_10km": n10,
            "nearest_station_km": round(near, 2) if near is not None else None,
            "src": ("station" if n10 >= 1 else
                    "model" if base is not None else "inferred"),
        }
        sig_sum += sd
        pm_sum += pm
    t_cells = time.time()

    n_cells = len(out_cells)
    stats = {"mean_sigma": round(sig_sum / n_cells, 3) if n_cells else None,
             "mean_pm25": round(pm_sum / n_cells, 2) if n_cells else None}

    def prov_entry(name, bundle, label, extra=None):
        fa = bundle.get("fetched_at")
        n = bundle.get("n")
        e = {"label": label,
             "source": bundle.get("source"),
             "status": bundle.get("status", "ok"),
             "fetched_at": _iso(float(fa)) if fa else None,
             # clamped: `now` was taken before the fetch ran, so a just-
             # landed fetched_at is clock slop (0 s), never negative
             "age_s": max(0, int(now - float(fa))) if fa else None,
             "attempts": bundle.get("attempts"),
             # observations the source contributed — 'model: 48 pts'
             # for /health; falls back to a recount for injected inputs
             "n": _bundle_n(name, bundle) if n is None else n}
        if extra:
            e.update(extra)
        return e

    provenance = {
        "model": prov_entry("model", model_in, "model",
                            {"n_points": len(model_pts),
                             "fire_modifier_applied": round(modifier, 3)}),
        "stations": prov_entry("stations", st_in, "station",
                               {"n_raw": len(raw_st),
                                "n_used": len(survivors)}),
        "fires": prov_entry("fires", fires_in, "model",
                            {"belt_fires": fires_in.get("belt_fires"),
                             "n_fires": fires_in.get("n_fires"),
                             "modifier": round(modifier, 3)}),
        "met": prov_entry("met", met_in, "model",
                          {"wind_ms": met_in.get("wind_ms"),
                           "wind_deg": met_in.get("wind_deg"),
                           "blh_m": met_in.get("blh_m"),
                           "vc_m2s": met_in.get("vc_m2s")}),
    }

    # --- build metadata: sources-used, QC reject counts, duration ------
    # (doc 05 §2 + doc 07 admin "ingest health" — every built field must
    # be able to say what went into it and how long it took)
    sources_used = sorted(k for k, p in provenance.items()
                          if p.get("status") == "ok")
    sources_degraded = sorted(k for k, p in provenance.items()
                              if p.get("status") != "ok")
    dropped_counts = {k: len(v) for k, v in dropped.items()}
    build_meta = {
        "duration_ms": round((time.time() - t0) * 1000, 1),
        "inputs": "injected" if injected else "live",
        "sources_used": sources_used,
        "sources_degraded": sources_degraded,
    }
    # Stage attribution for the cold-build hole (docs/lanes/
    # ingest-coldbuild): inputs+model-prior, station QC+Kalman+krige fit,
    # grid+cell loop. Fetch internals are broken out in the 'ingest
    # fetch' line emitted by fetch_inputs. log.warning = the level that
    # reaches /ecs/alive108 today (INFO is dropped).
    log.warning(
        "ingest build: fetch=%dms prior=%dms qc_kalman_krige=%dms "
        "cells=%dms total=%dms n_cells=%d stations=%d grid=%s",
        round((t_inputs - t0) * 1000),
        round((t_prior - t_inputs) * 1000),
        round((t_qc - t_prior) * 1000),
        round((t_cells - t_qc) * 1000),
        round((time.time() - t0) * 1000),
        n_cells, len(survivors), system)

    grid_note = None
    if system != "h3":
        grid_note = ("h3 not installed — emitting ~0.74 km² lat/lon fallback "
                     "grid; add h3>=4 to requirements for H3 res-8 cells")

    return {
        "schema": "alive-airindex/1",
        "built_at": _iso(now),
        "built_epoch": round(now, 3),
        "build": build_meta,
        "grid": {"system": system, "res": H3_RES, "bbox": list(BBOX),
                 "n_cells": n_cells, "note": grid_note},
        "provenance": provenance,
        "met": {"wind_ms": met_in.get("wind_ms"),
                "wind_deg": met_in.get("wind_deg"),
                "blh_m": met_in.get("blh_m"),
                "vc_m2s": met_in.get("vc_m2s")},
        "qc": {"stations_raw": len(raw_st),
               "stations_used": len(survivors),
               "dropped": dropped,
               "dropped_counts": dropped_counts,
               "dropped_total": sum(dropped_counts.values()),
               "kriging": "on" if rk.on else "residual-idw"},
        "stations": [{"name": s.get("name"), "lat": s["lat"],
                      "lon": s["lon"], "pm25": s["pm25"],
                      "residual": s.get("residual")}
                     for s in survivors],
        "stats": stats,
        "cells": out_cells,
    }


# ---------------------------------------------------------------- codec

def serialize(field: dict) -> bytes:
    """Deterministic gzip JSON: sorted keys, fixed mtime — byte-stable
    round-trips (serialize(deserialize(x)) == x after gunzip)."""
    payload = json.dumps(field, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True).encode("utf-8")
    return gzip.compress(payload, mtime=0)


def deserialize(blob: bytes) -> dict:
    return json.loads(gzip.decompress(blob).decode("utf-8"))
