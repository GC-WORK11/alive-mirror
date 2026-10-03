"""The 15-minute Delhi air index — an H3 res-8 field over NCR.

Implements the pipeline contract in docs/plan/05-backend-architecture.md §2:
every ~15 min an EventBridge-triggered worker (ingest_worker.py) calls
build_field() and stores the gzip snapshot.

Pipeline:
  1. Pull inputs, each stamped with provenance + age:
       model    — Open-Meteo/CAMS pm2_5 over the NCR sample grid (no key)
       stations — CPCB/DPCC instruments via OpenAQ v3 (needs OPENAQ_API_KEY;
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
"""
import gzip
import json
import math
import os
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
from krige import KrigeField  # noqa: E402

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


# ---------------------------------------------------------------- grid

def _h3_cells() -> list:
    """H3 res-8 cells covering the bbox polygon (h3-py >=4 API first)."""
    w, s, e, n = BBOX
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
    dropped = {"stale": [], "flatline": [], "spike": []}
    kept = []
    for s in stations:
        ts = s.get("ts")
        if ts is None or now - float(ts) > STALE_S:
            dropped["stale"].append(s.get("name"))
            continue
        ser = [x for x in (s.get("series") or []) if x is not None]
        if len(ser) >= FLATLINE_MIN and max(ser) - min(ser) < FLATLINE_EPS:
            dropped["flatline"].append(s.get("name"))
            continue
        kept.append(dict(s))

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

def _fetch_model(client) -> dict:
    """CAMS pm2_5 at the NCR sample grid — one multi-point request."""
    t = time.time()
    try:
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
    except Exception as e:  # noqa: BLE001 - upstream failure, not a crash
        return {"status": f"unavailable: {type(e).__name__}",
                "source": "open-meteo/cams", "fetched_at": t, "samples": []}


def _fetch_met(client) -> dict:
    """10 m wind + boundary-layer height at NCR centre -> ventilation VC."""
    t = time.time()
    try:
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
    except Exception as e:  # noqa: BLE001
        return {"status": f"unavailable: {type(e).__name__}",
                "source": "open-meteo", "fetched_at": t,
                "wind_ms": None, "wind_deg": None, "blh_m": None,
                "vc_m2s": None}


def _fetch_fires(client, wind_deg) -> dict:
    """NASA FIRMS public CSVs -> belt fire count + smoke modifier.

    Reuses fires._parse_rows (same bbox + confidence normalisation) and
    FireField.smoke_modifier on a detached instance — no async needed and
    the modifier math stays single-sourced."""
    t = time.time()
    rows, ok = [], 0
    for path, instrument in fires_mod.PUBLIC_CSVS:
        try:
            r = client.get(fires_mod.CSV_BASE + path, timeout=45)
            r.raise_for_status()
            rows += fires_mod._parse_rows(r.text, instrument)
            ok += 1
        except httpx.HTTPError:
            continue  # one missing snapshot must not kill the layer
    if not ok:
        return {"status": "unavailable: upstream-error",
                "source": "nasa-firms-public-csv", "fetched_at": t,
                "modifier": 1.0, "n_fires": 0, "belt_fires": 0}
    ff = fires_mod.FireField()
    ff._fires = rows
    ff._status = "live"
    ff._wind_deg = wind_deg
    return {"status": "ok", "source": "nasa-firms-public-csv",
            "fetched_at": time.time(), "modifier": ff.smoke_modifier(),
            "n_fires": len(rows),
            "belt_fires": len([f for f in rows if f.get("belt")])}


def _fetch_stations(client) -> dict:
    """CPCB/DPCC instruments via OpenAQ v3 — sync variant of
    airfield.AirField._grab_openaq that also keeps each reading's UTC
    timestamp so QC can enforce the 3 h staleness rule. Without
    OPENAQ_API_KEY the source is marked 'unavailable: no key' — explicit,
    never silent (00-README open item #1)."""
    t = time.time()
    key = os.environ.get("OPENAQ_API_KEY")
    if not key:
        return {"status": "unavailable: no key", "source": "openaq-v3",
                "fetched_at": t, "stations": []}
    try:
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
        stations = []
        for loc_id in sorted({v["loc_id"] for v in sensors.values()}):
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
                if best:
                    try:
                        ts = datetime.fromisoformat(
                            best["ts"].replace("Z", "+00:00")).timestamp()
                    except ValueError:
                        ts = None
                    meta = best["meta"]
                    stations.append({"lat": meta["lat"], "lon": meta["lon"],
                                     "name": meta["name"], "pm25": best["v"],
                                     "ts": ts})
            except httpx.HTTPError:
                continue
        return {"status": "ok", "source": "openaq-v3",
                "fetched_at": time.time(), "stations": stations}
    except Exception as e:  # noqa: BLE001
        return {"status": f"unavailable: {type(e).__name__}",
                "source": "openaq-v3", "fetched_at": t, "stations": []}


def fetch_inputs(now=None, client=None) -> dict:
    """Pull all four upstreams. Every bundle carries status + fetched_at;
    a failed source degrades to status 'unavailable: ...' — the field
    still builds on what arrived (offline-ish by contract)."""
    now = _epoch(now)
    own = client is None
    c = client or httpx.Client(
        timeout=httpx.Timeout(30.0, connect=8.0),
        headers={"User-Agent": "alive108-airindex/0.1"})
    try:
        met = _fetch_met(c)
        model = _fetch_model(c)
        fires = _fetch_fires(c, met.get("wind_deg"))
        stations = _fetch_stations(c)
    finally:
        if own:
            c.close()
    return {"model": model, "met": met, "fires": fires,
            "stations": stations}


# ---------------------------------------------------------------- build

def build_field(now=None, *, inputs: Optional[dict] = None,
                client=None) -> dict:
    """-> the field dict (see module docstring). `inputs` may be injected
    wholesale (tests, replay) — then nothing touches the network."""
    now = _epoch(now)
    if inputs is None:
        inputs = fetch_inputs(now, client=client)

    model_in = inputs.get("model") or {}
    met_in = inputs.get("met") or {}
    fires_in = inputs.get("fires") or {}
    st_in = inputs.get("stations") or {}

    # --- model prior, fire-adjusted -------------------------------------
    modifier = fires_in.get("modifier")
    try:
        modifier = min(fires_mod.MAX_MODIFIER,
                       max(1.0, float(modifier)))
    except (TypeError, ValueError):
        modifier = 1.0
    model_pts = []  # (lat, lon, adjusted pm25)
    for s in model_in.get("samples") or []:
        v = s.get("pm25")
        if v is None:
            continue
        model_pts.append((float(s["lat"]), float(s["lon"]),
                          float(v) * modifier))

    def model_est(lat, lon):
        return _idw(model_pts, lat, lon) if model_pts else None

    # --- station QC + Kalman smoothing ----------------------------------
    raw_st = st_in.get("stations") or []
    survivors, dropped = qc_stations(raw_st, model_est, now)
    smoother = airfield.AirField()  # reuse production scalar Kalman (Q=12, R=60)
    for s in survivors:
        s["pm25"] = round(float(smoother._smooth(
            "pm2_5", s["lat"], s["lon"], float(s["pm25"]))), 2)

    # --- residuals = smoothed obs - adjusted model ----------------------
    resids = []  # (lat, lon, name, resid)
    for s in survivors:
        base = model_est(s["lat"], s["lon"])
        if base is None:
            continue
        s["residual"] = round(float(s["pm25"]) - base, 2)
        resids.append((s["lat"], s["lon"], s["name"], s["residual"]))
    rk = KrigeField().fit(
        [(la, lo, nm, {"pm2_5": r}) for la, lo, nm, r in resids])

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
            pm = _idw([(s["lat"], s["lon"], s["pm25"]) for s in survivors],
                      lat, lon)
            sd = max(0.15 * pm, 5.0) if pm is not None else None
        elif kr is not None:
            mu_r, sd_r = kr
            pm = base + mu_r
            # krige sigma covers interpolation error only — carry the same
            # 12% instrument/model-error floor as airfield so bands stay
            # honest where the field is flat
            sd = math.sqrt(sd_r * sd_r + (0.12 * pm) ** 2)
        else:
            # krige off (too few/non-constant residuals): IDW residual blend
            if np is not None and resid_arr is not None:
                r = float(resid_arr[i])
            else:
                r = _idw([(a, b, rr) for a, b, _n, rr in resids],
                         lat, lon) if resids else 0.0
            pm = base + (r or 0.0)
            # sigma grows from the instrument floor toward the observed
            # residual spread with distance from the nearest station
            decay = 1.0 - math.exp(-(near or 30.0) / 15.0)
            sd = math.sqrt((0.12 * pm) ** 2
                           + (min(resid_spread, 60.0) * decay) ** 2
                           + (0.05 * pm) ** 2) \
                if survivors else max(0.15 * pm, 3.0)
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

    n_cells = len(out_cells)
    stats = {"mean_sigma": round(sig_sum / n_cells, 3) if n_cells else None,
             "mean_pm25": round(pm_sum / n_cells, 2) if n_cells else None}

    def prov_entry(bundle, label, extra=None):
        fa = bundle.get("fetched_at")
        e = {"label": label,
             "source": bundle.get("source"),
             "status": bundle.get("status", "ok"),
             "fetched_at": _iso(float(fa)) if fa else None,
             "age_s": int(now - float(fa)) if fa else None}
        if extra:
            e.update(extra)
        return e

    provenance = {
        "model": prov_entry(model_in, "model",
                            {"n_points": len(model_pts),
                             "fire_modifier_applied": round(modifier, 3)}),
        "stations": prov_entry(st_in, "station",
                               {"n_raw": len(raw_st),
                                "n_used": len(survivors)}),
        "fires": prov_entry(fires_in, "model",
                            {"belt_fires": fires_in.get("belt_fires"),
                             "n_fires": fires_in.get("n_fires"),
                             "modifier": round(modifier, 3)}),
        "met": prov_entry(met_in, "model",
                          {"wind_ms": met_in.get("wind_ms"),
                           "wind_deg": met_in.get("wind_deg"),
                           "blh_m": met_in.get("blh_m"),
                           "vc_m2s": met_in.get("vc_m2s")}),
    }

    grid_note = None
    if system != "h3":
        grid_note = ("h3 not installed — emitting ~0.74 km² lat/lon fallback "
                     "grid; add h3>=4 to requirements for H3 res-8 cells")

    return {
        "schema": "alive-airindex/1",
        "built_at": _iso(now),
        "built_epoch": round(now, 3),
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
