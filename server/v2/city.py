"""GET /v2/city — the consumer 'Delhi today' summary (docs/plan/07 §1).

Live field stats + provenance + trip aggregates. Everything here is a
city total or average — the privacy contract is structural, not a
promise: TripAggregates holds nothing else to leak.

Additive payload — the original keys (ts, pm25_stats, field,
field_age_s, wind, sources, trips) keep their shape. The 'Delhi today'
blocks on top:

  generated_at   ISO-8601 UTC timestamp of this build
  breath         field-weighted PM2.5 turned into a day-of-breathing
                 band {lo, mid, hi} — µg/m³, inhaled µg, cigarettes;
                 None when the field is empty (never fake precision)
  freshness      field age + an explicit live/stale/unknown label
  provenance     what the number is really made of — model source,
                 live-station count (zero says so plainly), and the
                 k>=3 / 72 h corridor rule
  corridors      publishable street cells from TripAggregates only —
                 sorted heaviest-first, [] until k>=3 distinct devices
                 cross a cell inside 72 h
  enough_data    False while corridors is empty — never fabricated

GET /v2/city/moves — the "how Delhi moves" aggregate view — lives at the
bottom of this module. Same contract: TripAggregates only, every emitted
row k>=3, window/min_k/n_trips always stated, and an empty store answers
insufficient_data rather than a zero posing as measurement.
"""
import asyncio
import math
import statistics
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter

from . import deps
from .gazetteer import GAZ, _haversine_m
from .places import _name_reverse
from .store import TRIPS

router = APIRouter()

# light lattice over the NCR bbox for city stats — 15 evals, not a crawl
_LATS = (28.30, 28.45, 28.60, 28.75, 28.88)
_LONS = (76.88, 77.10, 77.32, 77.54, 77.76)

CIG_UG = 316.0            # Berkeley Earth: 1 cigarette ≈ 316 µg inhaled PM2.5
DAY_M3 = CIG_UG / 22.0    # its 22 µg/m³-day rule → ~14.4 m³ breathed a day
K_MIN = 3                 # corridor display threshold (docs/plan/07 §3)
MOVES_DAYS = 7            # /city/moves: trailing UTC day buckets covered
CORRIDOR_TOP = 5          # heaviest rows kept…
CORRIDOR_TAIL = 5         # …and lightest rows kept
NAME_RADIUS_M = 1200.0    # gazetteer nearest-name reach for a cell
NAME_NEAR_M = 200.0       # beyond this a name is "near X", not "X"

try:  # field cadence — airfield keeps samples for 15 min between refreshes
    from airfield import CACHE_TTL as _FIELD_TTL
except Exception:  # pragma: no cover - airfield always ships together
    _FIELD_TTL = 900.0
STALE_S = 2 * _FIELD_TTL  # one missed refresh still reads live; beyond = stale


# ---------------------------------------------------------------- lattice

def _lattice(F) -> tuple:
    """(values, sigmas) at each NCR lattice point — one pass shared by
    pm25_stats and the breath band. Sigma is the field's kriged std-dev
    when krige is on; points that error are skipped, never guessed."""
    vals, sigs = [], []
    for la in _LATS:
        for lo in _LONS:
            try:
                v = F.value(la, lo)
            except Exception:
                v = None
            try:
                s = F.sigma(la, lo) if hasattr(F, "sigma") else None
            except Exception:
                s = None
            if v is not None:
                vals.append(float(v))
            if s is not None:
                sigs.append(float(s))
    return vals, sigs


def _field_stats(vals: list) -> dict:
    if not vals:
        return {"n": 0}
    return {
        "n": len(vals),
        "mean": round(statistics.fmean(vals), 1),
        "median": round(statistics.median(vals), 1),
        "max": round(max(vals), 1),
        "above_who24h_15": round(sum(v > 15 for v in vals) / len(vals) * 100),
        "above_cpcb_60": round(sum(v > 60 for v in vals) / len(vals) * 100),
        "note": "% of sampled NCR points above each 24h guideline",
    }


_SPECIES = ("pm10", "nitrogen_dioxide", "ozone", "carbon_monoxide",
            "sulphur_dioxide", "ammonia", "us_aqi", "dust",
            "aerosol_optical_depth")


def _species(F) -> dict:
    """Field-mean of every other real species over the same 15-pt lattice.
    Snapshot-serving fields carry pm25 only — a species that returns None
    everywhere is honestly omitted, never interpolated into fiction.

    us_aqi is computed per lattice point (max EPA sub-index over the
    species actually served — same definition /aqi uses) rather than
    reading the raw CAMS layer, which ran ~239 tonight vs ~154 projected
    and ~160 on the public instruments. One us_aqi definition API-wide."""
    import ingest_waqi
    _AQI_PARAMS = ("pm2_5", "pm10", "nitrogen_dioxide", "ozone",
                   "carbon_monoxide", "sulphur_dioxide")
    out = {}
    for sp in _SPECIES:
        vals = []
        for la in _LATS:
            for lo in _LONS:
                try:
                    v = F.value(la, lo, sp)
                except Exception:
                    v = None
                if v is not None:
                    vals.append(float(v))
        if vals:
            out[sp] = {
                "mean": round(statistics.fmean(vals), 1),
                "median": round(statistics.median(vals), 1),
                "max": round(max(vals), 1),
                "n": len(vals),
            }
    # replace the raw CAMS us_aqi read with the computed sub-index
    subs = []
    for la in _LATS:
        for lo in _LONS:
            pt = []
            for sp in _AQI_PARAMS:
                try:
                    v = F.value(la, lo, sp)
                except Exception:
                    v = None
                if v is not None:
                    s = ingest_waqi.us_aqi_sub_index(sp, float(v))
                    if s is not None:
                        pt.append(s)
            if pt:
                subs.append(max(pt))
    if subs:
        out["us_aqi"] = {
            "mean": round(statistics.fmean(subs), 1),
            "median": round(statistics.median(subs), 1),
            "max": round(max(subs), 1),
            "n": len(subs),
            "basis": "computed — max EPA sub-index over served species "
                     "per lattice point (same as /aqi); raw CAMS layer "
                     "kept only on the field, not served here",
        }
    return out


def _breath_band(vals: list, sigs: list) -> dict:
    """The hero figure: what a day of breathing Delhi's air adds up to.

    mid   = field-weighted mean PM2.5 over the lattice
    band  = 1.96σ combining field σ (krige; the 15% model-only floor
            airindex uses when krige is off) with the spatial spread —
            'Delhi' is one number AND a city of different neighbourhoods
    units = µg/m³, inhaled µg/day (~14.4 m³ breathed — the Berkeley
            Earth 22 µg/m³-day ≈ 1 cigarette rule behind CIG_UG), and
            cigarette-equivalents (= pm25/22 exactly).
    """
    if not vals:
        return None
    mid = statistics.fmean(vals)
    spread = statistics.pstdev(vals) if len(vals) > 1 else 0.0
    inst = statistics.fmean(sigs) if sigs else 0.15 * mid
    sd = math.hypot(inst, spread)
    lo = max(0.0, mid - 1.96 * sd)
    hi = mid + 1.96 * sd

    def scaled(x: float, nd: int) -> dict:
        return {"lo": round(lo * x, nd),
                "mid": round(mid * x, nd),
                "hi": round(hi * x, nd)}

    return {
        "pm25_ugm3": scaled(1.0, 1),
        "day_inhaled_ug": scaled(DAY_M3, 0),
        "cigarettes": scaled(DAY_M3 / CIG_UG, 2),
        "n_points": len(vals),
        "basis": ("field-weighted mean over the NCR sample lattice; a day "
                  "of breathing ≈14.4 m³ (Berkeley Earth: 22 µg/m³-day ≈ 1 "
                  "cigarette); band = 1.96σ of field σ + spatial spread"),
    }


# ---------------------------------------------------------------- honesty

def _freshness(age_s) -> dict:
    """Explicit freshness — the chip on the screen reads this verbatim:
    live inside two refresh cadences, stale beyond, unknown when the
    field never reported an age."""
    age = None if age_s is None else max(0, int(age_s))
    label = ("unknown" if age is None else
             "live" if age <= STALE_S else "stale")
    return {"field_age_s": age,
            "age_min": None if age is None else age // 60,
            "label": label}


def _provenance(fstat: dict, agg: dict) -> dict:
    """What the hero number is made of. stations count 0 says so in the
    note — the payload must never imply live stations that aren't."""
    stations = int(fstat.get("station_readings") or 0)
    return {
        "model": {
            "name": "CAMS / Open-Meteo",
            "source": fstat.get("source") or "open-meteo/cams",
            "samples": int(fstat.get("samples") or 0),
            "up": bool(fstat.get("samples")),
        },
        "stations": {
            "count": stations,
            "live": stations > 0,
            "note": (f"{stations} live stations blended into the field"
                     if stations else
                     "no live station data — model + satellite field only"),
        },
        "trips": {
            "publishable_corridors": agg.get("corridors_publishable", 0),
            "cells_tracked": agg.get("cells_tracked", 0),
            "window_h": 72,
            "k_min": K_MIN,
        },
    }


# ---------------------------------------------------------------- corridors

def _cell_center(cell: str):
    """cell key → (lat, lon) for both schemes /v2/trip emits: h3 res-8
    ids and the 'll:<lat>,<lon>' 4-decimal fallback."""
    if cell.startswith("ll:"):
        try:
            la, lo = cell[3:].split(",")
            return float(la), float(lo)
        except ValueError:
            return None
    try:
        import h3
        fn = getattr(h3, "cell_to_latlng", None) or getattr(h3, "h3_to_geo")
        la, lo = fn(cell)
        return float(la), float(lo)
    except Exception:
        return None


_GEO_BUCKET = 0.01   # ~1.1 km cells for the gazetteer spatial index
_gaz_geo_idx: dict = {}
_gaz_geo_rows = None


def _gaz_geo(rows: list) -> dict:
    """(ilat, ilon) bucket -> rows, built once per gazetteer load.
    _gaz_nearest used to walk all ~120k rows per corridor cell — this
    cuts each lookup to the few buckets touching the radius box. Keyed
    on the rows-list identity: GAZ._load() hands back one stable list."""
    global _gaz_geo_idx, _gaz_geo_rows
    if _gaz_geo_rows is not rows:
        idx: dict = {}
        for r in rows:
            la, lo = r.get("lat"), r.get("lon")
            if la is None or lo is None:
                continue
            idx.setdefault(
                (math.floor(la / _GEO_BUCKET), math.floor(lo / _GEO_BUCKET)),
                []).append(r)
        _gaz_geo_idx, _gaz_geo_rows = idx, rows
    return _gaz_geo_idx


def _gaz_nearest(lat: float, lon: float, radius_m: float = NAME_RADIUS_M):
    """Closest gazetteer entry within radius_m — the offline corridor
    namer. -> (name, distance_m) or None."""
    try:
        rows = GAZ._load()
    except Exception:
        return None
    dlat = radius_m / 111_000.0
    dlon = radius_m / (111_000.0 * max(0.2, math.cos(math.radians(lat))))
    idx = _gaz_geo(rows)
    i0 = math.floor((lat - dlat) / _GEO_BUCKET)
    i1 = math.floor((lat + dlat) / _GEO_BUCKET)
    j0 = math.floor((lon - dlon) / _GEO_BUCKET)
    j1 = math.floor((lon + dlon) / _GEO_BUCKET)
    best = None
    for i in range(i0, i1 + 1):
        for j in range(j0, j1 + 1):
            for r in idx.get((i, j), ()):
                d = _haversine_m(lat, lon, r["lat"], r["lon"])
                if d <= radius_m and (best is None or d < best[1]):
                    best = (r["name"], d)
    return best


async def _name_corridor(loc, lat: float, lon: float):
    """Street/locality name for a cell centre: Amazon reverse-geocode
    when the key exists, else the nearest gazetteer entry ('near X'
    when it's far). None when nothing honest is found — a name is
    never invented."""
    if loc is not None and getattr(loc, "enabled", False):
        try:
            items = await loc.reverse_geocode(lat, lon, limit=10)
        except Exception:
            items = None
        if items:
            hit = _name_reverse(items, lat, lon)
            if hit and hit.get("name"):
                return hit["name"]
    near = _gaz_nearest(lat, lon)
    if near is None:
        return None
    name, dist = near
    return name if dist <= NAME_NEAR_M else f"near {name}"


async def _corridors(loc) -> list:
    """Heaviest + lightest publishable street cells. TripAggregates
    already enforces the k>=3-distinct-devices / 72 h rule — this only
    sorts, labels against the median corridor dose, and names. Empty
    store → [] — the caller turns that into enough_data: false."""
    pub = TRIPS.corridors(limit=20)
    if not pub:
        return []
    med = statistics.median(c["avg_dose_ug"] for c in pub)
    by_dose = sorted(pub, key=lambda x: -x["avg_dose_ug"])
    picked = []
    for c in by_dose[:CORRIDOR_TOP] + by_dose[-CORRIDOR_TAIL:]:
        if c["cell"] not in {x["cell"] for x in picked}:
            picked.append(c)
    rows = []
    for c in sorted(picked, key=lambda x: -x["avg_dose_ug"]):
        ctr = _cell_center(c["cell"])
        if ctr is None:
            continue
        rows.append({
            "cell": c["cell"],
            "name": await _name_corridor(loc, ctr[0], ctr[1]),
            # 4-dp out — the same precision ceiling as the pipeline in
            "lat": round(ctr[0], 4),
            "lon": round(ctr[1], 4),
            "trips": c["trips"],
            "devices": c["devices"],
            "avg_dose_ug": c["avg_dose_ug"],
            "co2_g_per_100m": c.get("co2_g_per_100m"),
            "relative": "heavier" if c["avg_dose_ug"] >= med else "lighter",
        })
    return rows


# ---------------------------------------------------------------- endpoint

def _typical(now_pm25: Optional[float]) -> Optional[dict]:
    """Decade-climatology context at the city centroid: what Connaught
    Place usually reads this month, this hour (9M measured station-hours
    from the openaq-data-archive), versus the live field mean. None when
    the archive or the live mean is unavailable — never a guess."""
    if now_pm25 is None:
        return None
    try:
        import history
        ist = timezone(timedelta(hours=5, minutes=30))
        n = datetime.now(ist)
        band = history.typical_band(28.6315, 77.2167, n.month, n.hour)
        med = band.get("median")
        if med is None:
            return None
        return {"month": n.month, "hour_ist": n.hour,
                "median": round(med, 1), "p25": band.get("p25"),
                "p75": band.get("p75"),
                "vs_now_pct": round((now_pm25 - med) / med * 100, 1)
                if med else None}
    except Exception:
        return None


async def _next_hours() -> Optional[list]:
    """Next 12 hourly PM2.5 forecast at the city centroid — the same
    live-anchored CAMS horizon /depart uses (forecast grid x stagnation
    factor + decaying live-field correction). Best-effort bounded
    refresh; None when the forecast field is cold or dead — never a
    guess."""
    try:
        from forecast import FORECAST
        await asyncio.wait_for(FORECAST.refresh(deps.http()), timeout=12.0)
    except Exception:
        pass
    try:
        from forecast import FORECAST
        out = []
        for h in range(12):
            v = FORECAST.pm25(28.6315, 77.2167, h)
            if v is None:
                continue
            idx = FORECAST.hour_index(h)
            out.append({
                "h": h,
                "start": (FORECAST.time_at(idx)
                          if idx is not None else None),
                "pm25": round(v, 1),
            })
        return out or None
    except Exception:
        return None


@router.get("/city")
async def city():
    global _CITY_CACHE
    from .plan import _field_refresh_bounded
    await _field_refresh_bounded()
    F = deps.field()
    ckey = _city_cache_key(F)
    if (_CITY_CACHE and _CITY_CACHE[1] == ckey
            and time.time() - _CITY_CACHE[0] < _CITY_TTL_S):
        built, _k, payload = _CITY_CACHE
        now = time.time()
        # the UTC-day ledger keys re-derive per serve — a payload built
        # at 23:59 must never paint yesterday under 'today' for the TTL
        tk = time.strftime("%Y-%m-%d", time.gmtime(now))
        trips = {**(payload.get("trips") or {}), "today_key": tk,
                 "today": ((payload.get("trips") or {}).get("days")
                           or {}).get(tk)}
        return {**payload, "ts": now, "trips": trips,
                "generated_at": datetime.fromtimestamp(
                    now, tz=timezone.utc).isoformat(timespec="seconds"),
                "cached_s": round(now - built, 1)}
    try:
        fstat = F.status()
    except Exception:
        fstat = {}

    loc = deps.get_location()
    fires = {}
    try:
        from fires import FIRES
        fires = FIRES.status()
    except Exception:
        pass

    vals, sigs = _lattice(F)
    stats = _field_stats(vals)
    agg = TRIPS.city_aggregates()
    corridors = await _corridors(loc)
    now = time.time()
    # 'today' is the store's own UTC day — served explicitly so the
    # page's ledger never keys on the last POPULATED day (the stale-today
    # bug: after a donation gap the newest key is yesterday, and the card
    # was painting it under a TODAY label). today is the real day dict or
    # null — an absent key is the honest 'nothing shared yet today'.
    _today_key = time.strftime("%Y-%m-%d", time.gmtime(now))
    agg["today_key"] = _today_key
    agg["today"] = (agg.get("days") or {}).get(_today_key)

    why_block = None
    try:
        from .why import build_why
        # the field refresh already ran above; drivers reuse it warm
        full = await build_why(28.6139, 77.2090)
        why_block = {
            "line": full.get("line"),
            # the parali/news line + the raw ingredients for clients
            # that re-localize it (the app's Hindi rebuild)
            "cause_note": full.get("cause_note"),
            "cause_note_fields": full.get("cause_note_fields"),
            "drivers": [{"kind": d.get("kind"), "weight": d.get("weight"),
                         "score": d.get("score"),
                         "evidence": d.get("evidence")}
                        for d in full.get("drivers") or []],
            "why_url": "/v2/why",
        }
    except Exception:
        why_block = None  # the number stands alone before it guesses

    out = {
        "ts": now,
        "why": why_block,
        "generated_at": datetime.fromtimestamp(
            now, tz=timezone.utc).isoformat(timespec="seconds"),
        "pm25_stats": stats,
        "typical": _typical(stats.get("mean")),
        "next_hours": await _next_hours(),
        "species": _species(F),
        "breath": _breath_band(vals, sigs),
        "field": fstat,
        "field_age_s": fstat.get("age_s"),
        "freshness": _freshness(fstat.get("age_s")),
        "provenance": _provenance(fstat, agg),
        "corridors": corridors,
        "enough_data": bool(corridors),
        "wind": F.wind() if hasattr(F, "wind") else {},
        "sources": {
            "model": {"up": bool(fstat.get("samples")),
                      "source": fstat.get("source")},
            "stations": {"up": bool(fstat.get("station_readings")),
                         "count": fstat.get("station_readings", 0)},
            "fires": {"up": bool(fires.get("fires")),
                      "count": fires.get("fires", 0)},
            "location": {"up": bool(loc is not None and
                                    getattr(loc, "enabled", False))},
        },
        "trips": agg,
    }
    # the legal frame over the same field summary — which CAQM stage
    # Delhi's air maps to under the GRAP rules, from pm25_stats.mean
    # through the codebase's one PM2.5→CPCB-AQI formula. Key absent on a
    # cold field (stats.n == 0 → nothing honest to map).
    import districts as _d
    grap = _d.grap_block(stats.get("mean"), "cpcb aqi of pm25_stats.mean")
    if grap is not None:
        out["grap"] = grap
    _CITY_CACHE = (time.time(), ckey, out)
    return {**out, "cached_s": 0.0}


# ---------------------------------------------------------------- districts
#
# GET /v2/districts — the NCR choropleth feed for /city. Boundaries are a
# baked static asset (server/static/ncr_districts.geojson — OSM admin
# relations, one-time fetch via server/tools/bake_ncr_districts.py);
# values are the same /grid pm2.5 cells the public map paints — mean of
# covered cells per district, centroid read under <3 (confidence:
# 'sparse'), never zero-filled. Category/colour are the official CPCB
# six-band scale; aqi_us is the US-EPA companion index.


_CITY_TTL_S = 60.0
_CITY_CACHE = None   # (built_ts, key, payload) — the 'Delhi today'
                     # payload only moves when its inputs do: the field
                     # (same key as /v2/districts), the live station
                     # layer, the donation store's mutation counter,
                     # the forecast build next_hours reads. A 60 s TTL
                     # caps residual drift, disclosed via 'cached_s'.
                     # Rebuilding per call re-ran lattice + why +
                     # corridors + forecast for byte-identical output
                     # (~0.5 s of CPU against a 52-station field).


def _city_cache_key(F):
    """_districts_field_key plus the other inputs a payload can move
    with: the live station layer, the donation store's _rev (in-memory
    backend; DDB reports 0 and rides the TTL), the forecast build."""
    try:
        from forecast import FORECAST
        f_at = getattr(FORECAST, "_fetched_at", None)
    except Exception:
        f_at = None
    return (_districts_field_key(F),
            getattr(F, "_station_count", None),
            len(getattr(F, "_stations_live", None) or []),
            getattr(TRIPS, "_rev", 0), f_at)


_DIST_TTL_S = 120.0
_DIST_CACHE = None   # (built_ts, field_key, payload) — district means
                     # only move when the field does; the key pins the
                     # cache to the field state it was built from so an
                     # emptied/reloaded field can't inherit stale rows.
                     # A short TTL caps any drift from donated traversals
                     # at <=2 min, disclosed via 'cached_s'. Rebuilding
                     # per request re-solved 1600 krige cells (~4 s) for
                     # byte-identical output.


def _districts_field_key(F):
    """(fetched_at, sample_count, snap_epoch) — any reload, refresh, or
    wipe changes it and forces a rebuild."""
    return (getattr(F, "_fetched_at", None),
            len(getattr(F, "_samples", None) or []),
            getattr(F, "_snap_epoch", None))


@router.get("/districts")
async def v2_districts():
    global _DIST_CACHE
    from .plan import _field_refresh_bounded
    await _field_refresh_bounded()
    F = deps.field()
    fkey = _districts_field_key(F)
    if (_DIST_CACHE and _DIST_CACHE[1] == fkey
            and time.time() - _DIST_CACHE[0] < _DIST_TTL_S):
        built, _k, payload = _DIST_CACHE
        return {**payload, "ts": time.time(), "cached_s":
                round(time.time() - built, 1)}
    import districts as _d
    import grid as _g
    F = deps.field()
    geo = _g.as_geojson(F, cells=40, param="pm2_5")
    rows = _d.live(geo.get("features", []))
    rows = _d.finalize(rows, lambda la, lo: F.value(la, lo, "pm2_5"))
    payload = {
        "districts": rows,
        "bands": [{"min": lo, "max": hi, "category": c, "color": col}
                  for lo, hi, c, col in _d.CPCB_BANDS],
        "geojson": "/ncr.geojson",
        "subdistrict_geojson": "/delhi_subdistricts.geojson",
        "scale": "cpcb",
        "field_age_s": (F.status() or {}).get("age_s")
        if hasattr(F, "status") else None,
    }
    _DIST_CACHE = (time.time(), fkey, payload)
    return {**payload, "ts": time.time(), "cached_s": 0.0}


# ---------------------------------------------------------------- moves
#
# GET /v2/city/moves — "how Delhi moves": the aggregated mobility view.
# Everything below is a second read of the same TripAggregates store —
# day counters (per-mode trip counts, km, dose_ug, co2_kg_mid,
# pm25_g_mid, switched) and the publishable corridor cells. Nothing is
# computed from anything else, because nothing else exists server-side.
#
# k>=3 on every row:
#   * corridors — the store's publishable set itself (>=3 distinct
#     hashed devices per cell inside 72 h, enforced under the lock)
#   * mode share — a mode earns its own row only at >=K_MIN trips in
#     the window; smaller modes pool into one "other" row, and that row
#     is itself emitted only when the pool reaches K_MIN. Whatever is
#     left is reported as a suppressed trip COUNT, never a labelled row
#   * per-trip bands — percentiles across per-DAY means, and a day only
#     counts when it has >=K_MIN trips AND actually recorded the value
#     (a missing dose/co2 sum is not a measured zero)
#
# n_trips < min_k across the window → insufficient_data: true. The raw
# counts still ship (they are real), but no distribution is drawn from
# them — never zeros dressed up as data.


def _pct_band(vals, nd: int = 1):
    """{p25, p50, p75, n} — the honest middle half of a small sample.

    None when there is nothing to summarize (a null band, not a zero
    one). One value collapses to a point and reports n=1 so the UI can
    say 'the only qualifying day' instead of implying a spread.
    """
    vals = sorted(float(v) for v in vals)
    if not vals:
        return None
    if len(vals) == 1:
        v = round(vals[0], nd)
        return {"p25": v, "p50": v, "p75": v, "n": 1}
    q = statistics.quantiles(vals, n=4, method="inclusive")
    return {"p25": round(q[0], nd), "p50": round(q[1], nd),
            "p75": round(q[2], nd), "n": len(vals)}


@router.get("/city/moves")
async def city_moves():
    now = time.time()
    today = datetime.fromtimestamp(now, tz=timezone.utc).date()
    first = today - timedelta(days=MOVES_DAYS - 1)
    agg = TRIPS.city_aggregates()
    days = {k: v for k, v in (agg.get("days") or {}).items()
            if first.isoformat() <= k <= today.isoformat()}

    n_trips = sum(int(d.get("trips") or 0) for d in days.values())
    n_days = sum(1 for d in days.values() if int(d.get("trips") or 0) > 0)

    # ---- mode share — every row >=K_MIN trips, or pooled/suppressed ----
    modes = {}
    for d in days.values():
        for m, n in (d.get("modes") or {}).items():
            modes[m] = modes.get(m, 0) + int(n)
    big = sorted(((m, n) for m, n in modes.items() if n >= K_MIN),
                 key=lambda x: -x[1])
    small_n = sum(n for _, n in modes.items() if n < K_MIN)
    mode_share = [{"mode": m, "trips": n,
                   "share": round(n / n_trips, 3)}
                  for m, n in big] if n_trips else []
    suppressed = 0
    if small_n >= K_MIN:
        # the pool itself clears k — one anonymous 'other' row, labelled
        # by nothing but size (the pool is what protects the members)
        mode_share.append({"mode": "other", "trips": small_n,
                           "share": round(small_n / n_trips, 3)})
    elif small_n:
        suppressed = small_n  # below k even pooled — a count, not a row

    # ---- per-trip bands — per-day means over qualifying days only ----
    qual = [d for d in days.values() if int(d.get("trips") or 0) >= K_MIN]

    def _means(key):
        """day[key] ÷ day trips for qualifying days that recorded key —
        a 0 sum means 'not recorded', not 'measured zero'."""
        return [float(d[key]) / int(d["trips"])
                for d in qual if float(d.get(key) or 0.0) > 0]

    per_trip = {
        "n_days": len(qual),
        "dose_ug": _pct_band(_means("dose_ug"), 1),
        "co2_kg": _pct_band(_means("co2_kg_mid"), 2),
        "pm25_g": _pct_band(_means("pm25_g_mid"), 3),
        "basis": ("percentiles of per-day means (day total ÷ day "
                  "trips); only days with >=3 trips and a recorded "
                  "value contribute"),
    }

    # ---- corridors — the store's own publishable set, count + dose ----
    pub = TRIPS.corridors(now=now, limit=500)
    corridors = {
        "window_h": 72,
        "active": len(pub),
        "tracked": int(agg.get("cells_tracked") or 0),
        # distribution of per-cell mean dose across publishable cells —
        # each input row is already a >=3-device aggregate by the store's
        # own rule, so the band never rests on a single traveller
        "avg_dose_ug": _pct_band([c["avg_dose_ug"] for c in pub], 1),
        # emission intensity where trips reported co2 — g per 100 m of
        # corridor; band over cells that have the index, null when none
        "co2_g_per_100m": _pct_band(
            [c["co2_g_per_100m"] for c in pub
             if c.get("co2_g_per_100m") is not None], 1),
    }

    return {
        "ts": now,
        "generated_at": datetime.fromtimestamp(
            now, tz=timezone.utc).isoformat(timespec="seconds"),
        "window": {"days": MOVES_DAYS,
                   "from": first.isoformat(), "to": today.isoformat()},
        "min_k": K_MIN,
        "n_trips": n_trips,
        "n_days": n_days,
        "insufficient_data": n_trips < K_MIN,
        "mode_share": mode_share,
        "mode_share_suppressed_trips": suppressed,
        "corridors": corridors,
        "per_trip": per_trip,
        "basis": ("aggregates only — modes count donated trips, "
                  "corridors are street cells with >=3 distinct devices "
                  "in 72 h; no per-device data exists server-side"),
    }
