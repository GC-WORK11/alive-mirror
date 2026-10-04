"""POST /v2/plan — trip options with dose + emissions bands and the
doc-06 §4 ranking; POST /v2/reroute — replan from a live fix.

Every option carries `geometry` (GeoJSON LineString; also aliased as
`route_geojson`) and `steps` (turn list: instruction, distance_m,
lat/lon) — the client never needs legacy /directions. Motorized
geometry + traffic-aware duration comes from Amazon geo-routes
CalculateRoutes when ALIVE_LOCATION_KEY is set, else the same OSRM
call main.py makes (now with steps=true via deps.osrm_route). Metro
and bus come through transit_v2's GTFS connection scan — real legs
(walk → board → ride → alight → walk) with real station names and
line changes; when no feed is cached the option degrades to the
transit.py station-model, labelled `estimated` with lower confidence
— never a fabricated timetable.

Emissions are unified on server/emissions.py (`trip_emissions`) for
option totals; the static EMIT_GKM table survives only as a labelled
fallback when that module can't be imported. Dose rides
exposure.dose on the live field, preferring alive_core_ref's
integrate_dose when that function exists (another lane adds it; we
call it getattr-defensively).

`vehicle` accepts the questionnaire strings (car/auto/bike/bus/
metro/walk/cycle + common aliases); `vehicle_profile` may carry
{class, fuel, year|year_bucket} — unknown values fall back to the
Delhi fleet prior, never a 4xx.
"""
import asyncio
import functools
import concurrent.futures
import logging
import threading
import time
from typing import Optional

from fastapi import APIRouter

from . import deps
from .store import ROUTES

_log = logging.getLogger("v2.engine")

router = APIRouter()

try:
    import exposure  # server module (path fixed by v2/__init__)
except Exception:  # pragma: no cover
    exposure = None

try:
    import emissions as _emissions_mod  # unified emissions engine
except Exception:
    _emissions_mod = None

try:
    from alive_core_ref import integrate_dose as _integrate_dose
except Exception:  # another lane adds it — works before it exists
    _integrate_dose = None


# --- modes -------------------------------------------------------------------
# (mode, osrm profile, exposure microenv, label, AWS travel mode, time factor)
MODE_TABLE = [
    ("car",      "driving", "driving_car_ac",      "Car (AC)",           "Car",    1.0),
    ("car_open", "driving", "driving_car_open",    "Car (windows down)", "Car",    1.0),
    ("bike",     "driving", "driving_two_wheeler", "Bike / scooter",     "Scooter", 0.9),
    ("auto",     "driving", "auto_rickshaw",       "Auto-rickshaw",      "Car",    1.25),
    ("bus",      "driving", "bus",                 "Bus",                "Car",    1.6),
    ("metro",     None,     "metro",               "Metro + walk",        None,    1.0),
    ("metro+walk", None,    "metro",               "Metro + walk",        None,    1.0),
    ("cycle",    "cycling", "cycling",             "Bicycle",            None,     1.0),
    ("walk",     "walking", "walking",             "On foot",            "Pedestrian", 1.0),
]
_MODES = {m[0]: m for m in MODE_TABLE}

# declared-vehicle strings → canonical mode family (what the
# questionnaire can send + generous aliases; unknowns → car default)
_VEHICLE_ALIASES = {
    "car": "car", "car_ac": "car", "cab": "car", "taxi": "car",
    "four_wheeler": "car",
    "auto": "auto", "rickshaw": "auto", "autorickshaw": "auto",
    "bike": "bike", "scooter": "bike", "two_wheeler": "bike",
    "twowheeler": "bike", "motorcycle": "bike", "moped": "bike",
    "bus": "bus", "dtc": "bus",
    "metro": "metro", "train": "metro", "subway": "metro", "dmrc": "metro",
    "cycle": "cycle", "cycling": "cycle", "bicycle": "cycle", "bike_cycle": "cycle",
    "walk": "walk", "walking": "walk", "on_foot": "walk", "foot": "walk",
}
# option-mode → family (which declared vehicle it represents)
_FAMILY = {"car": "car", "car_open": "car", "cab": "car",
           "auto": "auto", "bike": "bike", "scooter": "bike",
           "bus": "bus", "metro": "metro", "metro+walk": "metro",
           "walk": "walk", "cycle": "cycle"}
# declared class → emissions-class (cab keeps its taxi uplift, scooter
# folds into the 2W table)
_PROFILE_CLASS = {"car": "car", "cab": "cab", "taxi": "cab",
                  "auto": "auto", "rickshaw": "auto",
                  "bike": "bike", "scooter": "scooter",
                  "two_wheeler": "bike", "motorcycle": "bike",
                  "bus": "bus", "metro": "metro",
                  "walk": "walk", "cycle": "cycle"}
_FUEL_ALIASES = {"petrol": "petrol", "gasoline": "petrol", "diesel": "diesel",
                 "cng": "cng", "lpg": "cng", "electric": "electric",
                 "ev": "electric", "bev": "electric", "hybrid": "petrol"}
_YEAR_BUCKETS = ("before_2010", "2010_2016", "2017_2019", "2020_plus",
                 "not_sure")
MODE_SPEED_KMH = {"cycling": 15.0, "walking": 5.0}   # stated estimate (main.py)


def _year_bucket(y) -> str:
    """Questionnaire year → emissions-year bucket. Accepts an int year,
    a bucket string, or anything (→ 'not_sure' → fleet prior)."""
    if isinstance(y, str) and y in _YEAR_BUCKETS:
        return y
    try:
        yi = int(y)
    except (TypeError, ValueError):
        return "not_sure"
    if yi < 2010:
        return "before_2010"
    if yi <= 2016:
        return "2010_2016"
    if yi <= 2019:
        return "2017_2019"
    return "2020_plus"


def _parse_vehicle(body: dict) -> tuple:
    """Body → (canonical_mode, profile_dict|None).

    Never raises, never 4xx: unknown vehicle strings → 'car' family,
    unknown fuels/years → that axis' fleet prior (emissions._resolve
    does the same for its own inputs).
    """
    body = body or {}
    vp = body.get("vehicle_profile") if isinstance(
        body.get("vehicle_profile"), dict) else {}
    raw = (body.get("vehicle") or body.get("mode")
           or vp.get("class") or "")
    canon = _VEHICLE_ALIASES.get(str(raw).lower().strip(), "car")

    profile = None
    if vp or str(raw).lower().strip() in _PROFILE_CLASS:
        pcls_raw = str(vp.get("class") or raw).lower().strip()
        pcls = _PROFILE_CLASS.get(pcls_raw, canon)
        profile = {"class": pcls}
        fuel = _FUEL_ALIASES.get(str(vp.get("fuel") or "").lower().strip())
        if fuel:
            profile["fuel"] = fuel
        yb = _year_bucket(vp.get("year_bucket", vp.get("year")))
        if yb != "not_sure":
            profile["year_bucket"] = yb
    # PUC certificate: vehicle_profile.puc (or a top-level `puc`) carries
    # the one-time analysis — measured readings + printed limits + BS.
    # Flows into the emissions vehicle dict; emissions.integrate does
    # the calibration and echoes `puc_calibrated`.
    puc = vp.get("puc") if isinstance(vp.get("puc"), dict) else \
        body.get("puc")
    if isinstance(puc, dict) and puc:
        profile = profile or {"class": canon}
        profile["puc"] = puc
    return canon, profile


# --- emissions ---------------------------------------------------------------
# FALLBACK ONLY (docs/plan/06 §2-shaped static bands). Primary path is
# emissions.trip_emissions below; this table runs only when
# server/emissions.py can't be imported — the `basis` label says so.
EMIT_GKM = {
    "car":      {"co2": (130.0, 210.0), "pm25": (0.010, 0.045),
                 "occ": 1.3, "idle_g_s": 0.45},
    "car_open": {"co2": (130.0, 210.0), "pm25": (0.010, 0.045),
                 "occ": 1.3, "idle_g_s": 0.45},
    "bike":     {"co2": (35.0, 75.0),   "pm25": (0.020, 0.100),
                 "occ": 1.2, "idle_g_s": 0.20},
    "auto":     {"co2": (55.0, 105.0),  "pm25": (0.020, 0.120),
                 "occ": 1.5, "idle_g_s": 0.25},
    "bus":      {"co2": (700.0, 1050.0), "pm25": (0.30, 0.90),
                 "occ": 16.0, "idle_g_s": 2.0},
    "metro":    {"co2_pkm": (11.0, 25.0), "pm25_pkm": (0.001, 0.010)},
    "cycle":    {"co2": (0.0, 0.0), "pm25": (0.0, 0.0)},
    "walk":     {"co2": (0.0, 0.0), "pm25": (0.0, 0.0)},
}
EMIT_BASIS = ("fallback static table — server/emissions.py unavailable "
              "(Delhi fleet prior, ARAI/ICAP factors, doc 06 §2)")

_EMIT_CLASS = {"car_open": "car", "metro+walk": "metro", "cab": "cab"}


def _option_vehicle(mode: str, profile: Optional[dict]) -> dict:
    """The emissions-vehicle dict for one option: the declared profile
    only when its class family matches the option's mode (a declared
    diesel car estimates the *car* option, not the bus); else the bare
    class → that mode's Delhi fleet prior."""
    vclass = _EMIT_CLASS.get(mode, mode)
    if profile and profile.get("class"):
        pcls = profile["class"]
        if _FAMILY.get(pcls, pcls) == _FAMILY.get(vclass, vclass):
            return dict(profile)
    return {"class": vclass}


def _emission_band(mode: str, dist_km: float, eta_s: float,
                   freeflow_s: Optional[float],
                   veh: Optional[dict] = None) -> dict:
    """{co2_kg:{lo,mid,hi}, pm25_g:{lo,mid,hi}, ...} for one option.

    Primary: emissions.trip_emissions (BS bucket × measured factors ×
    speed curve × idle × cold-start; per-passenger for shared modes;
    non-exhaust kept as a separate band — doc 06 §2-3). Fallback: the
    static EMIT_GKM table, basis-labelled as such.
    """
    if _emissions_mod is not None and hasattr(_emissions_mod, "trip_emissions"):
        try:
            out = _emissions_mod.trip_emissions(
                mode=mode, distance_km=dist_km, duration_s=eta_s,
                freeflow_s=freeflow_s, vehicle=veh)
            if isinstance(out, dict) and "co2_kg" in out:
                out.setdefault("engine", "server/emissions.py")
                return out
        except Exception:
            pass  # graceful: fall back to the table

    e = EMIT_GKM.get(mode) or EMIT_GKM.get(_EMIT_CLASS.get(mode, ""))
    if e is None:
        return {"co2_kg": None, "pm25_g": None, "basis": EMIT_BASIS}
    occ = float(e.get("occ") or 1.0)
    idle_s = max(0.0, float(eta_s or 0) - float(freeflow_s or eta_s or 0))
    if "co2_pkm" in e:  # metro: per passenger-km incl. electricity
        lo, hi = e["co2_pkm"]
        plo, phi = e["pm25_pkm"]
        co2_lo, co2_hi = lo * dist_km / 1000.0, hi * dist_km / 1000.0
        pm_lo, pm_hi = plo * dist_km, phi * dist_km
    else:
        (lo, hi), (plo, phi) = e["co2"], e["pm25"]
        idle_g = idle_s * float(e.get("idle_g_s") or 0.0)
        co2_lo = (lo * dist_km + idle_g * 0.6) / occ / 1000.0
        co2_hi = (hi * dist_km + idle_g) / occ / 1000.0
        pm_lo = plo * dist_km / occ
        pm_hi = (phi * dist_km + idle_g * 0.004) / occ
    return {
        "co2_kg": {"lo": round(co2_lo, 3), "mid": round((co2_lo + co2_hi) / 2, 3),
                   "hi": round(co2_hi, 3)},
        "pm25_g": {"lo": round(pm_lo, 3), "mid": round((pm_lo + pm_hi) / 2, 3),
                   "hi": round(pm_hi, 3)},
        "basis": EMIT_BASIS,
        "engine": "static-table fallback",
        "occupancy": occ if occ != 1.0 else None,
    }


# --- dose --------------------------------------------------------------------
def _microenv_ve(microenv: str) -> tuple:
    """(microenv ratio, VE m³/min) for a MICROENV-table key — getattr
    defensive so a renamed table can never 500 the endpoint."""
    me, ve = 1.0, 0.008
    if exposure is not None:
        try:
            me = float(exposure.MICROENV.get(microenv, 1.0))
            ve = float(exposure.VENTILATION_LPM.get(microenv, 8.0)) / 1000.0
        except Exception:
            pass
    return me, ve


def _dose_via_core(coords: list, microenv: str):
    """alive_core.integrate_dose seam — deliberately dormant.

    The real kernel signature is
        integrate_dose(coords, FieldView, me, ve, duration_s, step_m)
    and it cannot serve _dose_band today:
      • deps.field() is the AirField (.value/.sigma/.nearest_sample_km),
        not a FieldView (.band) — the only FieldView is airfield's
        _snap_fv, alive only while a snapshot is serving.
      • It returns {lo,mid,hi,coverage,n_hit,...} where lo/hi are the
        sums of per-cell band bounds (≈2σ); _dose_band's contract also
        needs avg_conc_ugm3 (client route-tint) and confidence (tests),
        and exposure.dose's mid±1σ-linear band semantics differ.
    Kept because it fails safe to exposure.dose and is the wire-in
    point if a FieldView-backed aggregate-only dose path ever lands:
    try [lon,lat] then (lat,lon), field callable then field object, and
    accept the first numeric band; anything else → None → exposure
    path."""
    if _integrate_dose is None or not coords:
        return None
    me, ve = _microenv_ve(microenv)
    try:
        F = deps.field()
    except Exception:
        return None
    fval = getattr(F, "value", None)
    latlons = [(c[1], c[0]) for c in coords if isinstance(c, (list, tuple))
               and len(c) >= 2]
    attempts = ((coords, fval), (latlons, fval), (coords, F))
    for c_arg, f_arg in attempts:
        if not c_arg or f_arg is None:
            continue
        try:
            out = _integrate_dose(c_arg, f_arg, me, ve)
        except Exception:
            continue
        if isinstance(out, dict) and isinstance(
                out.get("mid"), (int, float)):
            return {"lo": out.get("lo"), "mid": out.get("mid"),
                    "hi": out.get("hi"),
                    "coverage": out.get("coverage"),
                    "basis": "alive_core_ref.integrate_dose"}
    return None


def _dose_surface(F):
    """The ONE surface every option row in a response doses against —
    a compare sheet that mixes estimators (krige here, raster there)
    can rank a 'least-smoke' row below a route it actually beat. Order:
      1. _ENG_PACK — the priced raster the path engine just minimized
         over (nearest-cell, ~µs/read);
      2. F._snap_fv — the field's own snapshot cells, the same raster
         /grid and the admin map paint (nearest-cell, ~µs/read);
      3. (None, None) -> callers fall to F.value/F.sigma — the live
         krige+IDW point estimator.
    Rasters first because per-segment krige re-integration over a 65 km
    OD is ~1.3k solves per row and burned the whole arm budget on prod;
    the raster reads are the same real field, discretized."""
    if _ENG_PACK:
        return getattr(_ENG_PACK[0], "value", None), _ENG_PACK[1]
    fv = getattr(F, "_snap_fv", None)
    if fv is not None and hasattr(fv, "value"):
        return fv.value, getattr(fv, "sigma", None)
    return None, None


def _dose_band(geometry: dict, duration_s: float, microenv: str,
               field_fn=None, sigma_fn=None) -> dict:
    """{lo,mid,hi} µg on the live field. lo/hi may be None when the
    field can't give sigma — honest, not invented.

    field_fn overrides the per-segment concentration read — engine
    rows pass the FieldView raster the pathfinder priced against, so
    the shown dose is computed on exactly the field the path choice
    was made from (and at raster cost, not live-krige cost). sigma_fn
    likewise for the krige band — same lattice, swept once per TTL."""
    coords = (geometry or {}).get("coordinates") or []
    core = _dose_via_core(coords, microenv)
    if core is not None:
        return core
    if exposure is None:
        return {"lo": None, "mid": None, "hi": None,
                "note": "dose engine unavailable"}
    F = deps.field()
    dval, dsig = _dose_surface(F)
    fval = field_fn or dval or F.value
    try:
        e = exposure.dose(geometry, duration_s, microenv, fval,
                          F.nearest_sample_km,
                          field_sigma=sigma_fn or dsig or F.sigma)
    except Exception:
        return {"lo": None, "mid": None, "hi": None,
                "note": "dose engine error"}
    return {
        "lo": e.get("dose_ug_lo"), "mid": e.get("dose_ug"),
        "hi": e.get("dose_ug_hi"),
        "avg_conc_ugm3": e.get("avg_conc_ugm3"),
        "confidence": e.get("confidence"),
        # fraction of sampled route points inside the field — a route
        # that leaves the field honestly reports <1, never clamps
        "coverage": e.get("coverage"),
        "sparse": e.get("sparse"),
        "basis": "est." if e.get("dose_ug") is not None else None,
    }


_CONF_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3}
_LEG_MICROENV = {"walk": "walking", "metro": "metro", "bus": "bus"}


def _leg_dose(legs: list) -> dict:
    """Sum exposure.dose over transit legs (walk legs at walking
    microenv, ride legs at metro/bus; platform wait folds into the
    ride). lo = Σ leg los, hi = Σ his — conservative per doc 06 §1."""
    if exposure is None:
        return {"lo": None, "mid": None, "hi": None,
                "note": "dose engine unavailable"}
    try:
        F = deps.field()
    except Exception:
        return {"lo": None, "mid": None, "hi": None,
                "note": "field unavailable"}
    # same surface the road-mode rows dose on — a transit row ranked
    # against car/bike must not ride a different estimator
    dval, dsig = _dose_surface(F)
    lo = mid = hi = 0.0
    have_mid = have_band = False
    cov_min = None
    conf = "high"
    conc_by_dist = 0.0
    dist_sum_m = 0.0
    peak = 0.0
    for leg in legs or []:
        geom = leg.get("geometry")
        if not geom:
            continue
        me = _LEG_MICROENV.get(leg.get("type"), "walking")
        dur = float(leg.get("duration_s") or 0.0)
        if leg.get("type") != "walk":
            dur += float(leg.get("wait_s") or 0.0)
        try:
            e = exposure.dose(geom, dur, me, dval or F.value,
                              F.nearest_sample_km,
                              field_sigma=dsig or F.sigma)
        except Exception:
            continue
        if e.get("dose_ug") is None:
            conf = "low" if _CONF_RANK["low"] < _CONF_RANK.get(conf, 3) else conf
            continue
        have_mid = True
        mid += e["dose_ug"]
        if e.get("dose_ug_lo") is not None:
            lo += e["dose_ug_lo"]
            hi += e.get("dose_ug_hi") or e["dose_ug"]
            have_band = True
        # per-leg dose for the client's leg-by-leg view — the same
        # exposure.dose numbers the row sums, never a second estimate
        leg["dose"] = {
            "mid": round(e["dose_ug"], 1),
            "lo": round(e["dose_ug_lo"], 1)
                  if e.get("dose_ug_lo") is not None else None,
            "hi": round(e["dose_ug_hi"], 1)
                  if e.get("dose_ug_hi") is not None else None,
            "avg_conc_ugm3": e.get("avg_conc_ugm3"),
            "microenv": me,
        }
        ac = e.get("avg_conc_ugm3")
        d_i = _leg_dist_m(leg)
        if ac is not None and d_i > 0:
            # distance-weighted effective concentration — the same
            # ∫c·ds / ∫ds mean a road-mode row reports
            conc_by_dist += ac * d_i
            dist_sum_m += d_i
        if e.get("peak_conc") is not None:
            peak = max(peak, e["peak_conc"])
        if e.get("coverage") is not None:
            cov_min = e["coverage"] if cov_min is None else min(cov_min, e["coverage"])
        c = e.get("confidence") or "low"
        if _CONF_RANK.get(c, 0) < _CONF_RANK.get(conf, 3):
            conf = c
    if not have_mid:
        return {"lo": None, "mid": None, "hi": None,
                "confidence": "low", "coverage": 0.0, "basis": "est."}
    return {
        "lo": round(lo, 1) if have_band else None,
        "mid": round(mid, 1),
        "hi": round(hi, 1) if have_band else None,
        "avg_conc_ugm3": (round(conc_by_dist / dist_sum_m, 1)
                         if dist_sum_m > 0 else None),
        "peak_conc": round(peak, 1) if peak else None,
        "confidence": conf,
        # weakest leg's coverage — the shared floor a rider can trust
        "coverage": cov_min if cov_min is not None else None,
        "basis": "est.",
    }


# --- steps --------------------------------------------------------------------
def _endpoint_steps(geometry: dict, dist_m: float) -> list:
    """Degenerate-but-true turn list when the router gives no steps:
    depart at the first vertex, arrive at the last."""
    coords = (geometry or {}).get("coordinates") or []
    if len(coords) < 2:
        return []
    return [
        {"instruction": "Head out", "type": "depart", "modifier": "",
         "street": "", "distance_m": 0, "duration_s": 0,
         "lat": coords[0][1], "lon": coords[0][0]},
        {"instruction": "You'll arrive", "type": "arrive", "modifier": "",
         "street": "", "distance_m": round(dist_m), "duration_s": 0,
         "lat": coords[-1][1], "lon": coords[-1][0]},
    ]


def _transit_steps(legs: list) -> list:
    """transit_v2 legs → turn list with real station names + line
    changes: walk → board/ride → (transfer walk) → alight → walk."""
    steps = []
    n = len(legs or [])
    for i, leg in enumerate(legs or []):
        t = leg.get("type")
        frm, to = leg.get("from") or {}, leg.get("to") or {}
        start = leg.get("geometry", {}).get("coordinates", [[
            frm.get("lon"), frm.get("lat")]])
        lat0 = start[0][1] if start and len(start[0]) >= 2 else frm.get("lat")
        lon0 = start[0][0] if start and len(start[0]) >= 2 else frm.get("lon")
        base = {"distance_m": leg.get("distance_m"),
                "duration_s": leg.get("duration_s"),
                "lat": lat0, "lon": lon0, "street": ""}
        if t == "walk":
            if leg.get("transfer"):
                nxt = legs[i + 1] if i + 1 < n else {}
                ins = f"Walk to {to.get('name', 'the next stop')}"
                if nxt.get("line"):
                    ins += f" for the {nxt['line']} line"
                typ = "transfer"
            elif i == 0:
                ins = (f"Walk to {to.get('name', 'the station')}"
                       if to.get("name") not in (None, "Destination")
                       else "Walk to your destination")
                typ = "depart"
            else:
                ins = "Walk to your destination"
                typ = "arrive"
            steps.append({**base, "instruction": ins, "type": typ,
                          "modifier": ""})
        else:
            line = leg.get("line") or t.title()
            stops = leg.get("stops")
            ins = (f"Take {line} from {frm.get('name', '?')} to "
                   f"{to.get('name', '?')}")
            if stops:
                ins += f" — {stops} stop{'s' if stops != 1 else ''}"
            steps.append({**base, "instruction": ins, "type": t,
                          "modifier": "", "line": line,
                          "wait_s": leg.get("wait_s")})
    return steps


def _synthetic_steps(legs: list) -> list:
    """transit.py station-model legs ([lat,lon] endpoints) → the same
    turn-list shape, labelled by the same instructions."""
    steps = []
    n = len(legs or [])
    for i, leg in enumerate(legs or []):
        frm, to = leg.get("from"), leg.get("to")
        if not (isinstance(frm, list) and isinstance(to, list)):
            continue
        dist_m = (leg.get("distance_km") or 0.0) * 1000.0
        base = {"distance_m": round(dist_m),
                "duration_s": leg.get("duration_s"),
                "lat": frm[0], "lon": frm[1], "street": ""}
        if leg.get("type") == "walk":
            if i == 0:
                ins, typ = "Walk to the station", "depart"
            elif i == n - 1:
                ins, typ = "Walk to your destination", "arrive"
            else:
                ins, typ = "Walk to the next station", "transfer"
            steps.append({**base, "instruction": ins, "type": typ,
                          "modifier": ""})
        else:
            ins = (f"Take the metro from {leg.get('from_station', '?')} "
                   f"to {leg.get('to_station', '?')}")
            steps.append({**base, "instruction": ins, "type": "metro",
                          "modifier": "",
                          "line": ", ".join(leg.get("lines") or []) or None})
    return steps


def _merge_geometry(legs: list) -> dict:
    """Concatenate leg LineStrings → one route LineString."""
    coords = []
    for leg in legs or []:
        for c in (leg.get("geometry") or {}).get("coordinates") or []:
            if not coords or c != coords[-1]:
                coords.append(c)
    return {"type": "LineString", "coordinates": coords}


def _geom_length_m(geometry: dict) -> float:
    """Haversine length of a LineString — used when a leg forgets its
    distance_m (defensive; real transit_v2 legs always carry it)."""
    coords = (geometry or {}).get("coordinates") or []
    if len(coords) < 2 or exposure is None:
        return 0.0
    try:
        return sum(exposure._haversine_m(coords[i - 1], coords[i])
                   for i in range(1, len(coords)))
    except Exception:
        return 0.0


def _leg_dist_m(leg: dict) -> float:
    d = leg.get("distance_m")
    if isinstance(d, (int, float)) and d > 0:
        return float(d)
    return _geom_length_m(leg.get("geometry"))


# --- option builders -----------------------------------------------------------
def _option(mode: str, label: str, geometry: dict, dist_km: float,
            eta_s: float, freeflow_s: Optional[float], eta_model: str,
            vehicle: str, profile: Optional[dict] = None,
            steps: Optional[list] = None, steps_source: Optional[str] = None,
            dose: Optional[dict] = None, emissions: Optional[dict] = None,
            extra: Optional[dict] = None,
            origin: Optional[tuple] = None,
            dest: Optional[tuple] = None,
            field_fn=None, sigma_fn=None) -> dict:
    microenv = (_MODES.get(mode) or _MODES["car"])[2]
    veh = _option_vehicle(mode, profile)
    if steps is None:
        steps = _endpoint_steps(geometry, dist_km * 1000.0)
        steps_source = steps_source or "endpoints"
    opt = {
        "mode": mode,
        "label": label,
        "geometry": geometry,
        "route_geojson": geometry,          # compat alias, same object
        "steps": steps,
        "steps_source": steps_source,
        "distance_km": round(dist_km, 2),
        "eta_s": round(eta_s),
        "freeflow_s": round(freeflow_s) if freeflow_s else None,
        "eta_model": eta_model,
        "dose": dose if dose is not None else _dose_band(
            geometry, eta_s, microenv, field_fn=field_fn,
            sigma_fn=sigma_fn),
        "emissions": emissions if emissions is not None else _emission_band(
            mode, dist_km, eta_s, freeflow_s, veh),
        "tag": None,
        "recommended": False,
        "reason_line": "",
        "your_vehicle": _FAMILY.get(mode, mode) == vehicle,
    }
    if extra:
        opt.update(extra)
    opt["route_id"] = ROUTES.put({
        "geometry": geometry, "mode": mode,
        "duration_s": eta_s, "vehicle": vehicle,
        "emissions_vehicle": veh,
        "steps": steps,
        "from": {"lat": origin[0], "lon": origin[1]} if origin else None,
        "to": {"lat": dest[0], "lon": dest[1]} if dest else None,
    })
    return opt


def _mode_cap_duration_s(mode: str, dist_km: float, dur_s: float) -> float:
    """Router rows borrow a motorized router's duration and scale it
    per mode — on fast arterials that implied ~60-75 km/h for a bike
    (a Delhi 2W outrunning every car), which understates dose. Clamp
    implied speed at the same ceiling the engine graph applies
    (routegraph.MODE_RULES spd caps — bike 50, auto 40, cycle 16,
    walk 5): a slower duration means more time breathing, the honest
    direction. Uncapped modes return dur unchanged."""
    if dur_s <= 0 or dist_km <= 0:
        return dur_s
    try:
        import routegraph
        rules = routegraph.MODE_RULES.get(mode)
    except Exception:
        rules = None
    if not rules:
        return dur_s
    cap_kmh = rules["spd"](1e9)
    if cap_kmh >= 1e9:
        return dur_s                      # uncapped (car family)
    implied_kmh = dist_km / (dur_s / 3600.0)
    if implied_kmh <= cap_kmh:
        return dur_s
    return dist_km / cap_kmh * 3600.0


async def _motorized_options(flat, flon, tlat, tlon, vehicle, profile,
                             depart_at) -> list:
    """Car-family geometries: AWS CalculateRoutes when keyed (traffic +
    alternatives), else one OSRM driving route (now carrying real
    steps). Durations scale per mode by the same stated factors
    main.py uses."""
    loc = deps.get_location()
    aws_routes = None
    if loc is not None and getattr(loc, "enabled", False):
        for aws_mode in ("Car", "Scooter"):
            try:
                rs = await loc.calculate_routes(
                    flat, flon, tlat, tlon, travel_mode=aws_mode,
                    alternatives=2 if aws_mode == "Car" else 0,
                    depart_at=depart_at)
            except Exception:
                rs = None
            if rs:
                aws_routes = (aws_routes or {})
                aws_routes[aws_mode] = rs

    o, d = (flat, flon), (tlat, tlon)
    opts: list = []
    if aws_routes:
        car_rts = aws_routes.get("Car") or []
        sco_rts = aws_routes.get("Scooter") or car_rts
        for i, rt in enumerate(car_rts[:3]):
            dist_km = rt["distance_m"] / 1000.0
            geom, dur, ff = rt["geometry"], rt["duration_s"], \
                rt.get("freeflow_s")
            steps = rt.get("steps") or None
            src = "amazon-location" if steps else "endpoints"
            label = "Car (AC)" + (f" · alt {i}" if i else "")
            opts.append(_option("car", label, geom, dist_km, dur, ff,
                                "amazon-location", vehicle, profile,
                                steps=steps, steps_source=src,
                                origin=o, dest=d))
            if i == 0:
                opts.append(_option("car_open", "Car (windows down)",
                                    geom, dist_km, dur, ff,
                                    "amazon-location", vehicle, profile,
                                    steps=steps, steps_source=src,
                                    origin=o, dest=d))
                opts.append(_option("auto", "Auto-rickshaw", geom,
                                    dist_km,
                                    _mode_cap_duration_s(
                                        "auto", dist_km, dur * 1.25),
                                    _mode_cap_duration_s(
                                        "auto", dist_km,
                                        (ff or dur) * 1.25),
                                    "amazon-location+est", vehicle,
                                    profile, steps=steps,
                                    steps_source=src, origin=o, dest=d))
                opts.append(_option("bus", "Bus", geom, dist_km,
                                    dur * 1.6, (ff or dur) * 1.6,
                                    "amazon-location+est", vehicle,
                                    profile, steps=steps,
                                    steps_source=src, origin=o, dest=d))
        if sco_rts:
            rt = sco_rts[0]
            steps = rt.get("steps") or None
            dist_b = rt["distance_m"] / 1000.0
            ff_b = rt.get("freeflow_s")
            opts.append(_option("bike", "Bike / scooter", rt["geometry"],
                                dist_b,
                                _mode_cap_duration_s(
                                    "bike", dist_b, rt["duration_s"]),
                                _mode_cap_duration_s("bike", dist_b,
                                                     ff_b) if ff_b
                                else None,
                                "amazon-location", vehicle, profile,
                                steps=steps,
                                steps_source="amazon-location"
                                if steps else "endpoints",
                                origin=o, dest=d))
        return opts

    rt = await deps.osrm_route("driving", flon, flat, tlon, tlat)
    if not rt:
        return opts
    dist_km = rt["distance"] / 1000.0
    base = rt["duration"]  # OSRM duration ≈ free-flow — no traffic feed
    steps = rt.get("steps") or None
    src = "osrm" if steps else "endpoints"

    # row dosing is sync CPU (a cold task with no priced raster falls to
    # the live krige per segment, seconds per row): off the event loop,
    # or it blocks the plan's own budget timer (live: 34 s first plan
    # against a 20 s budget on a fresh task)
    def _rows():
        out = []
        for mode, label in (("car", "Car (AC)"),
                            ("car_open", "Car (windows down)"),
                            ("bike", "Bike / scooter"),
                            ("auto", "Auto-rickshaw"), ("bus", "Bus")):
            f = _MODES[mode][5]
            out.append(_option(mode, label, rt["geometry"], dist_km,
                               _mode_cap_duration_s(mode, dist_km,
                                                    base * f),
                               _mode_cap_duration_s(mode, dist_km,
                                                    base * f),
                               "osrm-freeflow", vehicle,
                               profile, steps=steps, steps_source=src,
                               origin=o, dest=d))
        return out
    return opts + await asyncio.to_thread(_rows)


async def _slow_mode_options(flat, flon, tlat, tlon, vehicle, profile) -> list:
    """Cycle/walk via OSRM profiles; durations are stated estimates.
    The two profile calls race — serially they can stack ~11s each and
    blow the whole plan budget on a far OD (seen live: opts=0 at 25s)."""
    opts = []
    rts = await asyncio.gather(
        *(deps.osrm_route(p, flon, flat, tlon, tlat)
          for _, p in (("cycle", "cycling"), ("walk", "walking"))),
        return_exceptions=True)
    def _rows():   # sync dosing off the loop (see _motorized_options)
        out = []
        for (mode, profile_name), rt in zip(
                (("cycle", "cycling"), ("walk", "walking")), rts):
            if not rt or isinstance(rt, Exception):
                continue
            dist_km = rt["distance"] / 1000.0
            dur = dist_km / MODE_SPEED_KMH[profile_name] * 3600.0
            steps = rt.get("steps") or None
            out.append(_option(mode, _MODES[mode][3], rt["geometry"],
                               dist_km, dur, dur, "estimated", vehicle,
                               profile, steps=steps,
                               steps_source="osrm" if steps else "endpoints",
                               origin=(flat, flon), dest=(tlat, tlon)))
        return out
    return opts + await asyncio.to_thread(_rows)


def _transit_option(j: dict, vehicle, profile, origin, dest) -> dict:
    """transit_v2 journey → plan option: real legs, real station names,
    per-leg dose, ride-distance emissions."""
    legs = j.get("legs") or []
    geom = _merge_geometry(legs)
    dist_km = sum(_leg_dist_m(l) for l in legs) / 1000.0
    ride_km = sum(_leg_dist_m(l)
                  for l in legs if l.get("type") != "walk") / 1000.0
    ride_s = sum(float(l.get("duration_s") or 0.0)
                 for l in legs if l.get("type") != "walk")
    dur = float(j.get("duration_s") or 0.0)
    tmode = j.get("mode") or "metro"
    emode = "bus" if tmode == "bus" else "metro"
    label = ("Metro + walk" if emode == "metro"
             else "Bus " + " → ".join(j.get("lines") or [])).strip()
    stations = None
    rides = [l for l in legs if l.get("type") != "walk"]
    if rides:
        stations = {"board": (rides[0].get("from") or {}).get("name"),
                    "alight": (rides[-1].get("to") or {}).get("name"),
                    "lines": j.get("lines"),
                    "transfers": j.get("transfers")}
    return _option(
        tmode, label, geom, dist_km, dur, dur,
        j.get("duration_model") or "gtfs", vehicle, profile,
        steps=_transit_steps(legs), steps_source="gtfs",
        dose=_leg_dose(legs),
        emissions=_emission_band(emode, ride_km, ride_s or dur, None,
                                 _option_vehicle(emode, profile)),
        extra={"legs": legs, "stations": stations,
               "lines": j.get("lines"), "transfers": j.get("transfers"),
               "walk_m": j.get("walk_m"),
               "depart_at": j.get("depart_at"),
               "arrive_at": j.get("arrive_at"),
               "transit_source": j.get("source")},
        origin=origin, dest=dest)


def _transit_options(flat, flon, tlat, tlon, vehicle, profile,
                     depart_at) -> list:
    """Real GTFS transit (metro + bus) via transit_v2; when no feed is
    cached, the transit.py station model carries the metro flag —
    labelled 'estimated', never a fabricated timetable."""
    opts = []
    try:
        import transit_v2
        for j in transit_v2.plan_transit(flat, flon, tlat, tlon,
                                         depart_at) or []:
            opts.append(_transit_option(j, vehicle, profile,
                                        (flat, flon), (tlat, tlon)))
    except Exception:
        pass
    if opts:
        return opts

    try:
        import transit
        F = deps.field()
        m = transit.metro_option(flat, flon, tlat, tlon, F.value)
    except Exception:
        return opts
    if not m or not m.get("geometry"):
        return opts
    legs = m.get("legs") or []
    dose = _leg_dose([{**l, "geometry": {
        "type": "LineString",
        "coordinates": [[l["from"][1], l["from"][0]],
                        [l["to"][1], l["to"][0]]]}}
        for l in legs
        if isinstance(l.get("from"), list) and isinstance(l.get("to"), list)])
    if dose.get("confidence") in (None, "high", "medium"):
        dose["confidence"] = "low"      # model legs, not real tracks
    opt = _option(
        "metro", m.get("label") or "Metro + walk (approx.)",
        m["geometry"], m.get("distance_km") or 0.0,
        m.get("duration_s") or 0.0, m.get("duration_s"),
        "estimated", vehicle, profile,
        steps=_synthetic_steps(legs) or None,
        steps_source="station-model" if legs else None,
        dose=dose,
        emissions=_emission_band("metro", m.get("distance_km") or 0.0,
                                 m.get("duration_s") or 0.0, None,
                                 _option_vehicle("metro", profile)),
        extra={"stations": m.get("stations"),
               "legs": legs,
               "approximate": True,
               "approximation": ("station-to-station model — no GTFS "
                                 "timetable feed cached")},
        origin=(flat, flon), dest=(tlat, tlon))
    opt["label"] = (m.get("label") or "Metro + walk") + " (approx.)"
    return [opt]


# --- doc-06 §4 ranking (pure — unit-tested on constructed options) -------------
def _dose_key(o: dict) -> float:
    d = o.get("dose") or {}
    # Engine rows rank on the priced objective: engine_dose_ug is the
    # edge-sum the A* minimized — the exact criterion the path won on.
    # It's a point estimate (~mid-scale), so it's mapped into the lo
    # space other rows rank in by THIS row's own band ratio (same
    # raster, same model — monotone map of the minimized value).
    ed = o.get("engine_dose_ug")
    if ed is not None:
        lo, mid = d.get("lo"), d.get("mid")
        if lo is not None and mid:
            return float(ed) * float(lo) / float(mid)
        return float(ed)
    v = d.get("lo") if d.get("lo") is not None else d.get("mid")
    return float(v) if v is not None else float("inf")


def _co2_mid(o: dict) -> float:
    e = (o.get("emissions") or {}).get("co2_kg") or {}
    v = e.get("mid")
    return float(v) if v is not None else float("inf")


def rank_options(options: list) -> list:
    """Sort + tag in place per doc 06 §4 and return the list.

      tied   = dose_lo within 10% of the best (boundary inclusive)
      winner = min emission inside tied  → recommended
      tag 'lightest on both' if winner also has the global min emission,
      else 'lightest for you' on the dose winner and 'lightest for
      Delhi' on the emission winner. Time guard: a recommendation slower
      than 1.6x the fastest option must say '+N min'.
    """
    scored = [o for o in options
              if _dose_key(o) != float("inf") and o.get("eta_s")]

    for o in options:           # reset ALL — stale flags must never survive
        o["tag"] = None
        o["reason_line"] = ""
        o["recommended"] = False
    if not scored:
        return options

    dose_min = min(_dose_key(o) for o in scored)
    # the least-dose option IS the safest path — app renders the leaf
    # chip on this flag (falls back to dose-min when absent)
    for o in options:
        o.pop("safest_path", None)
    min(scored, key=_dose_key)["safest_path"] = True
    tied = [o for o in scored if _dose_key(o) <= 1.10 * dose_min]
    emin = min(scored, key=_co2_mid)
    dwin = min(scored, key=_dose_key)
    fastest = min(o["eta_s"] for o in scored)
    emis_known = _co2_mid(emin) != float("inf")
    winner = min(tied, key=_co2_mid) if emis_known else dwin

    winner["recommended"] = True

    if not emis_known:
        winner["tag"] = "lightest for you"
        winner["reason_line"] = ("Least smoke for you — no emissions "
                                 "estimate for this set.")
    elif _co2_mid(winner) == _co2_mid(emin):
        winner["tag"] = "lightest on both"
        winner["reason_line"] = (
            "Least smoke for you and lowest emissions — the easy pick.")
    else:
        dwin["tag"] = "lightest for you"
        if dwin is not winner:
            dwin["reason_line"] = ("Least smoke for you, "
                                   "but heavier for Delhi.")
        emin["tag"] = "lightest for Delhi"
        emin["reason_line"] = ("Lowest emissions of the options — "
                               "but you'd breathe more.")
        winner["reason_line"] = (
            "Within ~10% of the lightest dose and the lightest exhaust "
            "of those — a fair trade.")

    if fastest and winner["eta_s"] > 1.6 * fastest:
        extra_min = int(round((winner["eta_s"] - fastest) / 60.0))
        winner["reason_line"] += f" +{extra_min} min vs fastest."

    options.sort(key=lambda o: (o is not winner, _dose_key(o)))
    return options


# --- endpoints ------------------------------------------------------------------
# Hard per-request budget: every upstream call in the option path is
# bounded individually, but a pathological stack (local + public OSRM
# per mode, transit scan) could still sum past what a single-worker
# task can afford between ALB health checks — cap the whole build.
# The total must stay under the app's ~30 s client cap with margin for
# queue + response overhead, else the typed timeout lands after the
# client already gave up and the "can't plan" notice is unreachable
# (audit: far pins on the public OSRM demo hit exactly that).
PLAN_BUDGET_S = 20.0
FIELD_REFRESH_BUDGET_S = 10.0
# Transit leg's own ceiling inside the plan budget — a fresh task's
# first plan can race the boot-time feed compile; without this the
# scan eats the whole 20 s and even motorized options are lost.
TRANSIT_BUDGET_S = 12.0


def _service_area(flat, flon, tlat, tlon) -> bool:
    """Both endpoints must sit inside the field's coverage + margin —
    dose past it would clamp to edge cells (a 10,000 km SF→Delhi OSRM
    "route" is what wedged the task on E2E)."""
    try:
        from airfield import in_service_area
        return in_service_area(flat, flon) and in_service_area(tlat, tlon)
    except Exception:
        return True   # airfield importable everywhere prod runs


async def _field_refresh_bounded() -> None:
    """Field refresh is best-effort — never let an upstream stall hold
    a plan request hostage."""
    try:
        await asyncio.wait_for(deps.field_refresh(),
                               timeout=FIELD_REFRESH_BUDGET_S)
    except Exception:
        pass


async def _options_bounded(flat, flon, tlat, tlon, vehicle, profile,
                           depart_at):
    """_build_options under the hard budget. Returns (options, error)
    — error is a fast structured string, never an open request."""
    try:
        options, missing = await asyncio.wait_for(
            _build_options(flat, flon, tlat, tlon, vehicle, profile,
                           depart_at),
            timeout=PLAN_BUDGET_S)
        return options, None, missing
    except asyncio.TimeoutError:
        return [], "planner timed out", ["planner"]


def _pt(v, name: str):
    if isinstance(v, dict):
        try:
            return float(v["lat"]), float(v["lon"])
        except KeyError as e:
            # name the side + the field — 'to: missing lon', not "'lon'"
            raise ValueError(f"{name}: missing {e}") from e
    if isinstance(v, (list, tuple)) and len(v) >= 2:
        # [lon, lat] GeoJSON order
        return float(v[1]), float(v[0])
    raise ValueError(f"{name}: need {{lat,lon}} or [lon,lat]")


async def _build_options(flat, flon, tlat, tlon, vehicle, profile,
                         depart_at) -> list:
    """The full option set for one OD pair: motorized + slow + transit +
    the least-inhalation engine paths."""
    # engine arm gets its own sub-budget: a cold-task first reweight
    # (field boot + ~1.25M sample calls) can outlast the plan budget —
    # without this its slowness cancels the WHOLE gather and motorized
    # options die with it. wait_for only abandons the future; the
    # detached thread still finishes pricing for the next request.
    # all four arms race together — the transit GTFS scan used to start
    # only after the gather resolved, so a far OD serialized motor+engine
    # (~8-10s) then transit's own 12s cap and overshot PLAN_BUDGET_S:
    # _options_bounded then returned 'planner timed out' with zero rows.
    # Sync GTFS stays off-loop via to_thread (its 12 s cap still applies;
    # a slow scan just drops the transit legs, never the whole plan).
    # asyncio.wait (not gather): when the plan budget lands mid-arm the
    # arms that ALREADY finished still contribute their real rows — a
    # cancelled cold arm no longer drags complete ones to zero.
    arms = [
        asyncio.ensure_future(_motorized_options(
            flat, flon, tlat, tlon, vehicle, profile, depart_at)),
        asyncio.ensure_future(_slow_mode_options(
            flat, flon, tlat, tlon, vehicle, profile)),
        asyncio.ensure_future(asyncio.wait_for(
            asyncio.get_running_loop().run_in_executor(
                _ENG_EXEC, _engine_options, flat, flon, tlat, tlon,
                vehicle, profile),
            timeout=ENGINE_BUDGET_S)),
        asyncio.ensure_future(asyncio.wait_for(asyncio.to_thread(
            _transit_options, flat, flon, tlat, tlon, vehicle, profile,
            depart_at), timeout=TRANSIT_BUDGET_S)),
    ]
    done, pending = await asyncio.wait(
        arms, timeout=PLAN_BUDGET_S - 2.0)
    for p in pending:
        p.cancel()

    def _arm(i):
        """(rows, failed): an arm that timed out, cancelled or raised is
        *missing* — not the same as an arm that legitimately found no
        rows. Callers must be able to tell the difference: a plan whose
        engine arm died is degraded, not complete."""
        t = arms[i]
        if t in done and not t.cancelled() and t.exception() is None:
            return t.result(), False
        return [], True

    (motor, m_bad), (slow, s_bad), (eng, e_bad), (transit, t_bad) = (
        _arm(0), _arm(1), _arm(2), _arm(3))
    missing = [name for name, bad in
               (("motor", m_bad), ("slow", s_bad),
                ("engine", e_bad), ("transit", t_bad)) if bad]
    options = ([o for o in (motor or []) if isinstance(o, dict)]
               if isinstance(motor, list) else [])
    options += ([o for o in (slow or []) if isinstance(o, dict)]
                if isinstance(slow, list) else [])
    if isinstance(eng, list):
        options += _engine_merge(eng, options)
    if isinstance(transit, list):
        options += [o for o in transit if isinstance(o, dict)]
    return options, missing


# --- least-inhalation path engine ----------------------------------------------
# alive_core.PathEngine over the real NCR road graph (ARG1 packed build,
# tools/build_route_graph.py): edge cost = inhaled dose for the queried
# mode, A* in ~10 ms. The option it emits is the *safest* path, not the
# fastest — the reason the engine exists. reweight() re-prices edges on
# the live field on a lazy TTL (the field itself refreshes on its own
# cadence; 10 min always lands inside freshness).
ENGINE_REWEIGHT_TTL_S = 600.0
ENGINE_BUDGET_S = 8.0        # sub-budget inside PLAN_BUDGET_S
ALT_OD_KM = 50.0             # buy corridor alts only at NCR scale
ALT_ARM_SOFT_S = 6.0         # stop launching alt solves past this mark
ALT_MAX_DETOUR = 1.6         # alt corridor must stay within 1.6x its
                             # least-dose primary's distance — past that
                             # the diversity well is dry, not an option
DETOUR_MAX_VS_FAST = 1.6     # wire promise: no engine row serves past
                             # 1.6x the same-mode fast (router) row's
                             # distance — enforced at merge where the
                             # fast rows exist; unbounded when the
                             # router arm failed (row kept, no compare)
ENGINE_MODES = (("car", "Car (AC)"), ("bike", "Bike / scooter"),
                ("auto", "Auto-rickshaw"), ("cycle", "Bicycle"),
                ("walk", "On foot"))
_ENG_T = 0.0
_ENG_PACK = None          # (fv, sigma_fn) the last reweight priced against
_ENG_LOCK = threading.Lock()
_ENG_BUSY_LOCK = threading.Lock()
_ENG_BUSY = False         # a reweight is already sweeping/repricing —
                          # concurrent arms serve the last pricing
                          # instead of stacking a second CPU storm
_ENG_DONE = threading.Event()   # set when the busy holder finishes —
                                # lets unpriced arms join instead of
                                # serving nothing during a cold sweep
ENG_BUSY_JOIN_S = 3.5      # unpriced arms wait this long for the
                           # in-flight sweep — well inside the 8 s arm
                           # budget; past it the row honestly drops
ENGINE_RASTER_MAX_CELLS = 56
ENGINE_RASTER_MIN_CELLS = 14
ENGINE_RASTER_BUDGET_S = 12.0   # cap the lattice sweep's wall time —
                                # per-read latency decides the lattice
                                # density (a cold task's live-krige
                                # reads crawled ~45 s on prod)
# private pool: the shared default executor serves every to_thread in
# the process (GTFS compile, rasters, forecasts) — a busy moment could
# queue the engine arm inside its own 8 s budget and burn it before a
# single query ran. Joined callers park on an Event (no CPU), so a
# third worker keeps a queued arm from starving behind a parked one.
_ENG_EXEC = concurrent.futures.ThreadPoolExecutor(
    max_workers=3, thread_name_prefix="alive-eng")

# --- shared engine solves ------------------------------------------------------
# One in-flight/memoized solve per (rounded OD, pricing epoch): the
# fast paint (primaries only) and the full plan's engine arm
# (primaries + corridor alts) — which the app always fires together —
# split the A* work instead of stacking a second sweep onto the same
# single vCPU (live: the arm hit its 8 s budget under concurrency).
# Keys carry _ENG_T, so a reprice retires entries by construction; the
# size cap only bounds memory left behind on stale epochs.
_ENG_SOLVE = {}
_ENG_SOLVE_LOCK = threading.Lock()
ENGINE_SOLVE_JOIN_S = 7.0      # < ENGINE_BUDGET_S — then the waiter
                               # solves for itself rather than serve 0
ENGINE_SOLVE_MAX = 256         # bound map memory across stale epochs


class _SolveSlot:
    __slots__ = ("ev", "val")

    def __init__(self):
        self.ev = threading.Event()
        self.val = None


def _solve_join(key, compute):
    """Run compute() once per key: first caller owns it, concurrent
    callers wait on the same result instead of duplicating the solve —
    the dedupe that keeps fast+full plans from doubling engine CPU.
    Owner results (failures -> {}) stay memoized under the epoch key;
    a waiter whose owner overruns the join window solves for itself."""
    with _ENG_SOLVE_LOCK:
        slot = _ENG_SOLVE.get(key)
        if slot is None:
            slot = _SolveSlot()
            _ENG_SOLVE[key] = slot
            while len(_ENG_SOLVE) > ENGINE_SOLVE_MAX:
                _ENG_SOLVE.pop(next(iter(_ENG_SOLVE)))
            owner = True
        else:
            owner = False
    if owner:
        try:
            slot.val = compute()
        except Exception as e:
            _log.warning("engine solve %s failed: %r", key[0], e)
            slot.val = {}
        finally:
            slot.ev.set()
        return slot.val
    if slot.ev.wait(ENGINE_SOLVE_JOIN_S):
        return slot.val if isinstance(slot.val, dict) else {}
    _log.warning("engine solve %s: owner overran — solving", key[0])
    try:
        return compute() or {}
    except Exception as e:
        _log.warning("engine solve %s fallback failed: %r", key[0], e)
        return {}


def _engine_primaries(eng, flat, flon, tlat, tlon) -> dict:
    """{mode: least-dose path} — the primaries every engine row needs,
    one A* per engine mode on the currently priced graph."""
    out = {}
    for mode, _ in ENGINE_MODES:
        try:
            r = eng.query(flat, flon, tlat, tlon, mode)
        except Exception as e:
            _log.warning("engine query %s failed: %r", mode, e)
            continue
        if isinstance(r, dict) and not r.get("error") \
                and r.get("geometry"):
            out[mode] = r
        else:
            _log.warning("engine query %s: %s", mode,
                         (r or {}).get("error") or "no geometry")
    return out


def _engine_alts(eng, alts_fn, flat, flon, tlat, tlon, deadline) -> dict:
    """{mode: [primary, alt, ...]} — the taxed re-solve list per mode,
    primary included so callers can fall back to it. Bounded by the
    arm's soft clock; a partial map is honest (fewer alts, no zeros).
    Alternatives past ALT_MAX_DETOUR× the primary's distance are the
    diversity well running dry — they offer no comparable trade, so
    they are dropped rather than served (live audit: a 1.77× alt that
    was also worse-dosed)."""
    out = {}
    for mode, _ in ENGINE_MODES:
        if time.time() >= deadline:
            break
        try:
            paths = alts_fn(flat, flon, tlat, tlon, mode, 2)
        except Exception as e:
            _log.warning("engine alts %s failed: %r", mode, e)
            continue
        good = [r for r in (paths or [])
                if isinstance(r, dict) and not r.get("error")
                and r.get("geometry")]
        if not good:
            continue
        prim_m = good[0].get("distance_m") or 0.0
        if prim_m > 0:
            good = [good[0]] + [r for r in good[1:]
                                if (r.get("distance_m") or 0.0)
                                <= ALT_MAX_DETOUR * prim_m]
        out[mode] = good
    return out


def _engine():
    """The path engine singleton (C++ when built, Python twin otherwise).
    None when the packed graph isn't shipped — the API degrades to the
    upstream-router options only, never errors."""
    try:
        import routegraph
        return routegraph.path_engine()
    except Exception:
        return None


def _field_epoch(F) -> float:
    """Wall-clock stamp of the field the engine would raster now —
    live fetch time or serving-snapshot epoch, whichever applies. A
    raster built before this stamp is stale even inside the TTL."""
    epoch = 0.0
    for attr in ("_fetched_at", "_snap_epoch"):
        try:
            v = float(getattr(F, attr, 0.0) or 0.0)
        except Exception:
            continue
        if v > epoch:
            epoch = v
    return epoch


def _engine_reweight(eng) -> None:
    global _ENG_T, _ENG_PACK
    try:
        F = deps.field()
    except Exception as e:
        _log.warning("engine reweight: deps.field failed: %r", e)
        return
    # Reprice on TTL expiry OR when the field itself refreshed since
    # the last reweight — a fresher field must invalidate pricing
    # promptly, not sit out the rest of the 10 min serving a stale
    # raster. epoch<=_ENG_T covers the "same field, cheap repack" case.
    epoch = _field_epoch(F)
    if time.time() - _ENG_T <= ENGINE_REWEIGHT_TTL_S and epoch <= _ENG_T:
        return
    global _ENG_BUSY
    with _ENG_BUSY_LOCK:
        if _ENG_BUSY:
            # another arm is mid-sweep/reprice — serve the existing
            # pricing rather than stack a second sweep onto the same
            # single vCPU
            busy = True
        else:
            _ENG_BUSY = True
            _ENG_DONE.clear()
            busy = False
    if busy:
        # last pricing genuinely exists only when edges are priced —
        # on a cold task there is nothing to serve, so join the
        # in-flight sweep within the arm budget instead of instantly
        # dropping the engine rows (prod log: ~45 s of 'unpriced'
        # while the first raster crawl ran)
        ep = getattr(eng, "edges_priced", None)
        try:
            ep = ep() if callable(ep) else (ep or 0)
        except Exception:
            ep = 0
        if ep > 0:
            _log.warning("engine reweight: already in flight — "
                         "serving last pricing")
            return
        if _ENG_DONE.wait(ENG_BUSY_JOIN_S):
            _log.warning("engine reweight: joined in-flight sweep")
        else:
            _log.warning("engine reweight: in-flight sweep overran "
                         "%.1fs — rows drop this call", ENG_BUSY_JOIN_S)
        return
    try:
        _engine_reweight_inner(eng, F, epoch)
    finally:
        with _ENG_BUSY_LOCK:
            _ENG_BUSY = False
            _ENG_DONE.set()


def _engine_reweight_inner(eng, F, epoch) -> None:
    global _ENG_T, _ENG_PACK

    def val(lat, lon):
        try:
            return F.value(lat, lon)
        except Exception:
            return None

    # fast path: hand reweight a FieldView instead of ~1.25M
    # python-callable crossings. The snapshot's own FieldView is used
    # when it exists; on prod no snapshot file ships (data/field/ is
    # docker-ignored so a stale image can't lie about field age), so
    # the live field is rasterized through the same cells /grid serves
    # — still the real field, read once per TTL.
    #
    # The raster sweep (3,136 cells x value+sigma reads, seconds) runs
    # BEFORE _ENG_LOCK: a live plan queueing its engine arm behind a
    # whole sweep would burn its 8 s budget on the lock alone.
    sig_fn = None
    try:
        fv = getattr(F, "_snap_fv", None)
        if fv is None or not hasattr(fv, "value"):
            pack = _engine_field_view(F)
            if pack is None:
                fv = None
            else:
                fv, sig_fn = pack
    except Exception as e:
        _log.warning("engine reweight: field view failed: %r", e)
        fv = None
    if fv is None:
        sampler = val
    else:
        # The C++ PathEngine reweight fast path needs a real
        # alive_core.FieldView; everything else — the Python twin,
        # or a PyFieldView view — prices off fv.value as an
        # ordinary callable. All are cheap nearest-cell lookups,
        # honest on a live field either way.
        sampler = fv.value
        try:
            import alive_core
            if (isinstance(eng, alive_core.PathEngine)
                    and isinstance(fv, alive_core.FieldView)):
                sampler = fv
        except ImportError:
            pass
    _log.warning(
        "engine reweight: sampler=%s eng=%s snap_fv=%s serving=%s",
        type(sampler).__name__, type(eng).__name__,
        type(getattr(F, "_snap_fv", None)).__name__,
        getattr(F, "_serving_snapshot", lambda: "?")())

    # never start a callable reweight against the live field: krige
    # posterior + Bayesian traverse per sample makes ~1.25M crossings
    # take minutes on one vCPU — the arm would hold the lock and
    # starve every plan. Snapshot serving keeps F.value cheap, so the
    # callable path is only honest then.
    if (sampler is val
            and not getattr(F, "_serving_snapshot", lambda: False)()):
        return

    with _ENG_LOCK:
        if time.time() - _ENG_T <= ENGINE_REWEIGHT_TTL_S \
                and epoch <= _ENG_T:
            return
        try:
            t_rw = time.time()
            res = eng.reweight(sampler) or {}
            # only mark fresh when edges actually priced — a reweight
            # against an empty field (cold task, no snapshot yet) would
            # otherwise stick zero-cost paths for the whole TTL
            if res.get("edges_priced", 0) > 0:
                _ENG_T = time.time()
                # keep the raster that priced these edges — engine rows
                # price their displayed dose against the same field view
                # the pathfinder minimized over
                _ENG_PACK = (fv if hasattr(fv, "value") else None, sig_fn)
            _log.warning("engine reweight done: %s in %.0fms (epoch %s)",
                         res, (time.time() - t_rw) * 1000.0,
                         "fresh" if epoch > 0 else "?")
        except Exception as e:
            _log.warning("engine reweight failed: %r", e)


def _engine_field_view(F):
    """Live-field raster for the engine — the same cells /grid serves.

    Reweighting ~1.25M edge samples through live F.value (krige posterior
    + Bayesian traverse) takes minutes on one vCPU; this samples the field
    once per reweight TTL over the /grid lattice and prices edges through
    a FieldView instead. Rows carry only real reads — cells the field
    can't serve are skipped, never zero-filled.
    """
    # cheap probe before the 3,136-cell sweep: a field that serves
    # nothing anywhere can only yield an empty raster — one read tells
    # us that without ~3k dead krige calls per retry (the boot-warm
    # loop and a live plan can otherwise hold _ENG_LOCK for seconds at
    # a time while the field is still fetching).
    try:
        probe = F.value(28.6315, 77.2167)
    except Exception:
        probe = None
    if probe is None:
        _log.warning("engine raster: field serves no reads — skip sweep")
        return None
    import math
    try:
        import grid as _g
        x0, y0, x1, y1 = _g.BBOX
    except Exception:
        x0, y0, x1, y1 = (76.80, 28.20, 77.90, 28.95)
    # Lattice density is read-latency adaptive: a warm field answers
    # F.value in ~ms so the full 56-cell lattice is seconds; a cold
    # task's krige-backed reads crawled ~45 s on prod, pinning every
    # unpriced arm behind _ENG_BUSY. Probe a few cells, extrapolate,
    # and pick the finest lattice that fits ENGINE_RASTER_BUDGET_S —
    # coarser cells are still real reads on the same lattice origin.
    def _read(cx, cy):
        v = F.value(cy, cx)
        try:
            sd = F.sigma(cy, cx)
        except Exception:
            sd = None
        return v, (sd if sd is not None and math.isfinite(sd) else None)

    t_probe = time.time()
    probe_n = 0
    for i in range(3):
        for j in range(3):
            _read(x0 + (i + 0.5) * (x1 - x0) / 3.0,
                  y0 + (j + 0.5) * (y1 - y0) / 3.0)
            probe_n += 1
            if time.time() - t_probe > ENGINE_RASTER_BUDGET_S / 4:
                break
        if time.time() - t_probe > ENGINE_RASTER_BUDGET_S / 4:
            break
    per_read = max(0.001, (time.time() - t_probe) / max(1, probe_n))
    fits = int((ENGINE_RASTER_BUDGET_S / per_read) ** 0.5)
    cells = max(ENGINE_RASTER_MIN_CELLS,
                min(ENGINE_RASTER_MAX_CELLS, fits))
    if cells < ENGINE_RASTER_MAX_CELLS:
        _log.warning("engine raster: %.1fms/read — lattice %d cells "
                     "(budget %.0fs)", per_read * 1000.0, cells,
                     ENGINE_RASTER_BUDGET_S)
    dx, dy = (x1 - x0) / cells, (y1 - y0) / cells
    # one lattice pass reading value AND krige-sigma per cell center —
    # the row's sigma slot gets the real band and the returned sigma_fn
    # gives exposure.dose a dict-lookup band instead of a per-segment
    # krige solve (which alone burned ~10s on a 65km OD).
    rows = []
    sig = {}
    t_sweep = time.time()
    for ix in range(cells):
        for iy in range(cells):
            cx = x0 + (ix + 0.5) * dx   # lon
            cy = y0 + (iy + 0.5) * dy   # lat
            v, sd = _read(cx, cy)
            if v is None:
                continue
            if sd is not None:
                sig[(ix, iy)] = float(sd)
            rows.append((cy, cx, float(v), float(v), float(v),
                         float(sd) if sd is not None else float("nan")))
            if time.time() - t_sweep > ENGINE_RASTER_BUDGET_S:
                break   # hard cap: partial lattice still prices edges
        if time.time() - t_sweep > ENGINE_RASTER_BUDGET_S:
            _log.warning("engine raster: budget stop at %d/%d cells",
                         len(rows), cells * cells)
            break
    if not rows:
        _log.warning("engine raster: field served no cells")
        return None

    def _sigma_at(lat, lon):
        if not (x0 <= lon <= x1 and y0 <= lat <= y1):
            return None          # past the lattice: honest 'no band'
        ix = min(cells - 1, max(0, int((lon - x0) / dx)))
        iy = min(cells - 1, max(0, int((lat - y0) / dy)))
        return sig.get((ix, iy))

    try:
        import core_engine
        # 8 km coverage: every graph edge lands within reach of a raster
        # cell — past the lattice, nearest_cell would leave edges unpriced
        fv = core_engine.field_view(rows, 8.0)
        _log.warning("engine raster: %d cells (%d sigma) -> %s",
                     len(rows), len(sig), type(fv).__name__)
        return fv, _sigma_at
    except Exception as e:
        _log.warning("engine raster: field_view failed: %r", e)
        return None


def _geom_midpoint(geometry: dict):
    coords = (geometry or {}).get("coordinates") or []
    if not coords:
        return None
    return coords[len(coords) // 2]


def _engine_options(flat, flon, tlat, tlon, vehicle, profile,
                    alts: bool = True) -> list:
    """Least-dose path per engine mode, as plan options.

    Two dose surfaces per row: `engine_dose_ug` — the µg the A* summed
    over priced edges, the exact criterion the path minimized (server
    ranking keys on it) — and `dose` — the shared raster band through
    exposure.dose, so every row on screen shows one dose model."""
    eng = _engine()
    if eng is None:
        _log.warning("engine options: no engine (graph/engine load failed)")
        return []
    _engine_reweight(eng)
    try:
        ep = getattr(eng, "edges_priced", None)
        ep = ep() if callable(ep) else (ep or 0)   # C++ binding = method,
        if ep <= 0:                                # Python twin = attr
            _log.warning("engine options: unpriced (edges_priced=0)")
            return []   # unpriced = degenerate paths — serve nothing
    except Exception as e:
        _log.warning("engine options: edges_priced probe failed: %r", e)
        return []
    try:
        from airfield import MAX_ROUTE_KM
    except Exception:
        MAX_ROUTE_KM = 80.0
    # dose sampler for the option rows: the FieldView raster the edges
    # were priced against (nearest-cell, ~µs) — NOT the live krige. A
    # 65 km OD × 5 modes re-integrated through live F.value is ~1.3k
    # krige reads and burned the whole 8 s arm budget on prod, killing
    # every engine row; the raster read is the same real field and
    # makes the shown dose the exact criterion the path won on. The
    # sigma band rides the same raster (live F.sigma would add another
    # ~1.3k krige solves).
    field_fn = None
    sigma_fn = None
    if _ENG_PACK:
        field_fn = getattr(_ENG_PACK[0], "value", None)
        sigma_fn = _ENG_PACK[1]
    # Honest alternative corridors need a fast engine: alternatives()
    # runs up to ALT_MAX_ATTEMPTS A* solves per mode. The C++ kernel
    # pays that in ~50-100 ms; the Python twin (dev fallback when the
    # extension isn't built) would burn the whole 8 s arm budget —
    # it serves the single optimum per mode, exactly as before.
    alts_fn = getattr(eng, "alternatives", None)
    if alts_fn is not None:
        try:
            import alive_core
            if not isinstance(eng, alive_core.PathEngine):
                alts_fn = None
        except ImportError:
            alts_fn = None
    # Bound the detached arm's CPU: each alt is a full tax-and-re-solve
    # A* on the priced graph — up to ALT_MAX_ATTEMPTS per mode. On a
    # single-core task an overrun keeps burning after wait_for abandons
    # the future and starves the whole plan gather (live: opts=0 at
    # ~30 s on a 61 km OD). Alternatives are therefore bought only for
    # in-city-scale ODs while arm time remains; far ODs still get all
    # five least-dose primaries.
    air_km = exposure._haversine_m(
        (flon, flat), (tlon, tlat)) / 1000.0
    t0 = time.time()
    # shared solves keyed on the OD (~11 m rounding) + the pricing
    # epoch — the fast paint's primaries are the same A* work this arm
    # needs, so a fast+full pair costs one solve, not two.
    ek = (round(flat, 4), round(flon, 4), round(tlat, 4),
          round(tlon, 4), _ENG_T)
    prim = _solve_join(
        ("prim",) + ek,
        lambda: _engine_primaries(eng, flat, flon, tlat, tlon))
    altmap = {}
    if (alts and alts_fn is not None and air_km <= ALT_OD_KM
            and (time.time() - t0) < ALT_ARM_SOFT_S):
        altmap = _solve_join(
            ("alts",) + ek,
            lambda: _engine_alts(eng, alts_fn, flat, flon, tlat, tlon,
                                 t0 + ALT_ARM_SOFT_S))
    opts = []
    for mode, label in ENGINE_MODES:
        alist = altmap.get(mode) or []
        primary = prim.get(mode) or (alist[0] if alist else None)
        paths = ([primary] if isinstance(primary, dict) else []) \
            + alist[1:]
        for alt_i, r in enumerate(paths):
            if not isinstance(r, dict) or r.get("error") \
                    or not r.get("geometry"):
                if alt_i == 0:
                    _log.warning("engine query %s: %s", mode,
                                 (r or {}).get("error") or "no geometry")
                continue
            snap = r.get("snap") or {}
            if (snap.get("from_m", 1e9) > 1200.0
                    or snap.get("to_m", 1e9) > 1200.0):
                continue   # path would start mid-graph — not servable
            dist_km = r["distance_m"] / 1000.0
            if dist_km <= 0.0 or dist_km > MAX_ROUTE_KM:
                continue
            dur_s = float(r["duration_s"])
            row_label = (f"{label} · least-smoke rd" if alt_i == 0
                         else f"{label} · least-smoke alt {alt_i}")
            opts.append(_option(
                mode, row_label,
                r["geometry"], dist_km, dur_s, dur_s, "estimated",
                vehicle, profile,
                steps=None, steps_source="endpoints",
                extra={
                    "engine": "alive_core-path",
                    "duration_model": "estimated",
                    # freeflow graph speeds (OSM maxspeed / class
                    # defaults, mode-capped) — no congestion feed;
                    # real Delhi traffic is slower so real dose is
                    # higher. docs/plan/duration-model.md
                    "duration_basis": "freeflow",
                    "via_names": r.get("names") or [],
                    "snap_m": {"from_m": round(snap.get("from_m") or 0, 1),
                               "to_m": round(snap.get("to_m") or 0, 1)},
                    "alternative_index": alt_i or None,
                    # the priced objective the path minimized — the
                    # wire field ranking keys on; display dose stays
                    # the raster band in `dose`
                    "engine_dose_ug": (round(r["dose_ug"], 1)
                                       if isinstance(r.get("dose_ug"),
                                                     (int, float))
                                       else None),
                },
                origin=(flat, flon), dest=(tlat, tlon),
                field_fn=field_fn, sigma_fn=sigma_fn))
    _log.warning("engine options: %d rows in %.0fms",
                 len(opts), (time.time() - t0) * 1000.0)
    return opts


def _engine_merge(eng_opts: list, options: list) -> list:
    """Drop an engine option whose geometry is essentially the same road
    a router already returned for that mode — flag the existing option
    'engine_confirmed' instead (the fast road IS the least-smoke one).
    Also drop any engine row past DETOUR_MAX_VS_FAST× the same-mode
    fastest router row — a corridor that far out is not a servable
    answer, whatever its dose."""
    fast_min = {}
    for o in options:
        if o.get("engine") == "alive_core-path":
            continue
        d = o.get("distance_km")
        m = o.get("mode")
        if isinstance(d, (int, float)) and m:
            fast_min[m] = min(fast_min.get(m, 1e18), d)
    out = []
    for eo in eng_opts:
        base = fast_min.get(eo.get("mode"))
        if base and eo.get("distance_km", 0) > DETOUR_MAX_VS_FAST * base:
            _log.warning("engine row dropped: %s %.1fkm > %.1fx "
                         "same-mode fast %.1fkm",
                         eo.get("label"), eo["distance_km"],
                         DETOUR_MAX_VS_FAST, base)
            continue
        mode = eo["mode"]
        dup = None
        emid = _geom_midpoint(eo.get("geometry"))
        for o in options:
            if o.get("mode") != mode:
                continue
            omid = _geom_midpoint(o.get("geometry"))
            if emid is None or omid is None:
                continue
            if (abs(o.get("distance_km", 0) - eo["distance_km"])
                    <= max(0.5, 0.03 * eo["distance_km"])):
                # midpoint proximity ≈ same corridor (deg-space ~150 m)
                if (abs(emid[0] - omid[0]) < 0.0015
                        and abs(emid[1] - omid[1]) < 0.0015):
                    dup = o
                    break
        if dup is not None:
            dup["engine_confirmed"] = True
            continue
        out.append(eo)
    return out


@router.post("/plan")
async def plan(body: dict):
    t0 = time.perf_counter()
    try:
        flat, flon = _pt(body.get("from") or body.get("from_"), "from")
        tlat, tlon = _pt(body.get("to"), "to")
    except (KeyError, TypeError, ValueError) as e:
        return {"options": [], "error": str(e)}
    vehicle, profile = _parse_vehicle(body)
    depart_at = body.get("depart_at")
    # echo what the client asked + what the engine actually modelled —
    # silent remapping would hide the fallback (fuzz-lane finding)
    vehicle_req = str(body.get("vehicle") or body.get("mode")
                      or vehicle)[:40]

    if not _service_area(flat, flon, tlat, tlon):
        from airfield import OUT_OF_AREA
        return {"from": {"lat": flat, "lon": flon},
                "to": {"lat": tlat, "lon": tlon},
                "options": [], "error": OUT_OF_AREA,
                "code": "outside_service_area",
                "field": _field_status(),
                "took_ms": round((time.perf_counter() - t0) * 1000.0, 1)}

    # fire-and-forget: the refresh is best-effort background work and
    # already bounded + deduped internally; awaiting it here would let a
    # slow upstream add its budget on top of the options budget
    asyncio.ensure_future(_field_refresh_bounded())
    fast = body.get("fast") is True
    if fast:
        options, opt_err, missing = await _engine_first(
            flat, flon, tlat, tlon, vehicle, profile)
    else:
        options, opt_err, missing = await _options_bounded(
            flat, flon, tlat, tlon, vehicle, profile, depart_at)
    rank_options(options)
    resp = {
        "from": {"lat": flat, "lon": flon},
        "to": {"lat": tlat, "lon": tlon},
        "vehicle": vehicle,
        "vehicle_requested": vehicle_req,
        "vehicle_profile": profile,
        "depart_at": depart_at,
        "options": options,
        "ranking": "doc 06 §4: dose_lo within 10% ties, lowest emission wins",
        "field": _field_status(),
        "took_ms": round((time.perf_counter() - t0) * 1000.0, 1),
    }
    if any((o.get("emissions") or {}).get("puc_calibrated")
           for o in options):
        resp["puc_calibrated"] = True   # server honoured the PUC card
    if fast:
        # engine rows only — the client paints these first and swaps in
        # the full set (router + transit + engine) when it lands
        resp["partial"] = True
    if missing:
        # an arm timed out/cancelled/raised — the option set is real but
        # INCOMPLETE. Silent absence is how an engine outage used to look
        # like a normal plan; clients + audits must be able to tell.
        resp["degraded"] = missing
    if opt_err:
        resp["error"] = opt_err
    elif not options:
        resp["error"] = "no route"   # OD in-area but unroutable
    return resp


async def _engine_first(flat, flon, tlat, tlon, vehicle, profile):
    """Least-inhalation rows alone: no public-router or GTFS wait, so the
    answer the engine exists for paints in ~engine time, not ~router time.
    Same rows, same pricing as the full plan's engine arm."""
    try:
        rows = await asyncio.wait_for(
            asyncio.get_running_loop().run_in_executor(
                _ENG_EXEC, functools.partial(
                    _engine_options, flat, flon, tlat, tlon, vehicle,
                    profile, alts=False)),
            timeout=ENGINE_BUDGET_S)
    except asyncio.TimeoutError:
        return [], "engine timed out", ["engine"]
    except Exception as e:
        _log.warning("engine-first arm failed: %r", e)
        return [], "engine unavailable", ["engine"]
    return ([o for o in (rows or []) if isinstance(o, dict)],
            None, [])


@router.post("/reroute")
async def reroute(body: dict):
    """Replan mid-trip (doc 04 §4: 3 off-route fixes → reroute).

    Body: {route_id?, at|from:{lat,lon}, to?:{lat,lon}, mode?, vehicle?,
           vehicle_profile?}. `to` falls back to the stored route's
    destination. Response carries the fresh option set, the selected
    option flattened to the top level (the mode the client asked for,
    else the ranked winner) AND under `option`, plus a fresh route_id —
    every failure is an honest body, never a fabricated route.
    """
    t0 = time.perf_counter()
    body = body or {}
    rec = None
    rid = body.get("route_id")
    if rid:
        rec = ROUTES.get(str(rid))

    try:
        cur = body.get("at") or body.get("position") or body.get("from")
        flat, flon = _pt(cur, "at")
    except (KeyError, TypeError, ValueError) as e:
        return {"route_id": rid, "options": [], "error": str(e)}

    to_v = body.get("to") or (rec or {}).get("to")
    if to_v is None:
        return {"route_id": rid, "options": [],
                "error": ("destination unknown — pass `to` or a live "
                          "route_id (route_ids expire after 1 h)")}
    try:
        tlat, tlon = _pt(to_v, "to")
    except (KeyError, TypeError, ValueError) as e:
        return {"route_id": rid, "options": [], "error": str(e)}

    vehicle, profile = _parse_vehicle(body)
    if profile is None and (rec or {}).get("emissions_vehicle"):
        profile = {"class": rec["emissions_vehicle"].get("class")}
        for k in ("fuel", "year_bucket"):
            if rec["emissions_vehicle"].get(k):
                profile[k] = rec["emissions_vehicle"][k]

    if not _service_area(flat, flon, tlat, tlon):
        from airfield import OUT_OF_AREA
        return {"route_id": None, "options": [], "option": None,
                "rerouted_from": rid, "error": OUT_OF_AREA,
                "code": "outside_service_area",
                "field": _field_status(),
                "took_ms": round((time.perf_counter() - t0) * 1000.0, 1)}

    asyncio.ensure_future(_field_refresh_bounded())   # fire-and-forget
    options, opt_err, missing = await _options_bounded(
        flat, flon, tlat, tlon, vehicle, profile, body.get("depart_at"))
    rank_options(options)
    if not options:
        return {"route_id": None, "options": [], "option": None,
                "rerouted_from": rid,
                "error": opt_err or "routing unavailable from this position",
                "field": _field_status(),
                "took_ms": round((time.perf_counter() - t0) * 1000.0, 1)}

    mode_hint = str(body.get("mode") or body.get("vehicle") or "").lower()
    best = options[0]
    if mode_hint:
        fam = _VEHICLE_ALIASES.get(mode_hint, mode_hint)
        best = next((o for o in options
                     if _FAMILY.get(o["mode"], o["mode"]) == fam),
                    options[0])
    resp = {
        "rerouted_from": rid,
        "from_fix": {"lat": flat, "lon": flon},
        "to": {"lat": tlat, "lon": tlon},
        "vehicle": vehicle,
        # flattened selected option (both names the client may read)
        "route_id": best["route_id"],
        "geometry": best["geometry"],
        "route_geojson": best["geometry"],
        "eta_s": best["eta_s"],
        "duration_s": best["eta_s"],
        "distance_km": best["distance_km"],
        "steps": best["steps"],
        "dose": best["dose"],
        "emissions": best["emissions"],
        "mode": best["mode"],
        "option": best,
        "options": options,
        "field": _field_status(),
        "took_ms": round((time.perf_counter() - t0) * 1000.0, 1),
    }
    if missing:
        resp["degraded"] = missing   # same honesty flag as /v2/plan
    # finish-on-foot honesty check: when the remaining leg is walkable
    # and the selected continuation is motorized, surface the real
    # least-dose walk option's numbers — the client can offer "park and
    # finish on foot" with honest distance + dose, nothing synthesized.
    if best.get("mode") != "walk":
        walk_opts = [o for o in options if o.get("mode") == "walk"]
        if walk_opts:
            wopt = min(walk_opts, key=_dose_key)
            if 0.0 < wopt.get("distance_km", 1e9) <= 1.5:
                resp["finish_on_foot"] = {
                    "distance_km": wopt["distance_km"],
                    "eta_s": wopt["eta_s"],
                    "dose": wopt.get("dose"),
                    "route_id": wopt["route_id"],
                }
    return resp


def _field_status() -> dict:
    try:
        return deps.field().status()
    except Exception:
        return {"source": "unavailable"}
