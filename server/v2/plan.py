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


def _dose_band(geometry: dict, duration_s: float, microenv: str) -> dict:
    """{lo,mid,hi} µg on the live field. lo/hi may be None when the
    field can't give sigma — honest, not invented."""
    coords = (geometry or {}).get("coordinates") or []
    core = _dose_via_core(coords, microenv)
    if core is not None:
        return core
    if exposure is None:
        return {"lo": None, "mid": None, "hi": None,
                "note": "dose engine unavailable"}
    F = deps.field()
    try:
        e = exposure.dose(geometry, duration_s, microenv, F.value,
                          F.nearest_sample_km, field_sigma=F.sigma)
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
    lo = mid = hi = 0.0
    have_mid = have_band = False
    cov_min = None
    conf = "high"
    for leg in legs or []:
        geom = leg.get("geometry")
        if not geom:
            continue
        me = _LEG_MICROENV.get(leg.get("type"), "walking")
        dur = float(leg.get("duration_s") or 0.0)
        if leg.get("type") != "walk":
            dur += float(leg.get("wait_s") or 0.0)
        try:
            e = exposure.dose(geom, dur, me, F.value,
                              F.nearest_sample_km, field_sigma=F.sigma)
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
            dest: Optional[tuple] = None) -> dict:
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
            geometry, eta_s, microenv),
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
                                    dist_km, dur * 1.25,
                                    (ff or dur) * 1.25,
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
            opts.append(_option("bike", "Bike / scooter", rt["geometry"],
                                rt["distance_m"] / 1000.0,
                                rt["duration_s"], rt.get("freeflow_s"),
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
    for mode, label in (("car", "Car (AC)"), ("car_open", "Car (windows down)"),
                        ("bike", "Bike / scooter"), ("auto", "Auto-rickshaw"),
                        ("bus", "Bus")):
        f = _MODES[mode][5]
        opts.append(_option(mode, label, rt["geometry"], dist_km,
                            base * f, base * f, "osrm-freeflow", vehicle,
                            profile, steps=steps, steps_source=src,
                            origin=o, dest=d))
    return opts


async def _slow_mode_options(flat, flon, tlat, tlon, vehicle, profile) -> list:
    """Cycle/walk via OSRM profiles; durations are stated estimates."""
    opts = []
    for mode, profile_name in (("cycle", "cycling"), ("walk", "walking")):
        rt = await deps.osrm_route(profile_name, flon, flat, tlon, tlat)
        if not rt:
            continue
        dist_km = rt["distance"] / 1000.0
        dur = dist_km / MODE_SPEED_KMH[profile_name] * 3600.0
        steps = rt.get("steps") or None
        opts.append(_option(mode, _MODES[mode][3], rt["geometry"], dist_km,
                            dur, dur, "estimated", vehicle, profile,
                            steps=steps,
                            steps_source="osrm" if steps else "endpoints",
                            origin=(flat, flon), dest=(tlat, tlon)))
    return opts


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
        return await asyncio.wait_for(
            _build_options(flat, flon, tlat, tlon, vehicle, profile,
                           depart_at),
            timeout=PLAN_BUDGET_S), None
    except asyncio.TimeoutError:
        return [], "planner timed out"


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
    motor, slow, eng = await asyncio.gather(
        _motorized_options(flat, flon, tlat, tlon, vehicle, profile,
                           depart_at),
        _slow_mode_options(flat, flon, tlat, tlon, vehicle, profile),
        asyncio.wait_for(
            asyncio.to_thread(_engine_options, flat, flon, tlat, tlon,
                              vehicle, profile),
            timeout=ENGINE_BUDGET_S),
        return_exceptions=True)
    options = ([o for o in (motor or []) if isinstance(o, dict)]
               if isinstance(motor, list) else [])
    options += ([o for o in (slow or []) if isinstance(o, dict)]
                if isinstance(slow, list) else [])
    if isinstance(eng, list):
        options += _engine_merge(eng, options)
    try:
        # sync GTFS scan runs off-loop: a big OD pair's graph walk would
        # otherwise stall the single worker's event loop (and /health
        # with it — that was the ALB wedge). Its own sub-budget keeps a
        # slow scan (first plan on a fresh task, feed still compiling)
        # from eating the whole plan budget — motorized+slow options
        # still land honestly without a transit leg.
        options += await asyncio.wait_for(asyncio.to_thread(
            _transit_options, flat, flon, tlat, tlon, vehicle, profile,
            depart_at), timeout=TRANSIT_BUDGET_S)
    except Exception:
        pass
    return options


# --- least-inhalation path engine ----------------------------------------------
# alive_core.PathEngine over the real NCR road graph (ARG1 packed build,
# tools/build_route_graph.py): edge cost = inhaled dose for the queried
# mode, A* in ~10 ms. The option it emits is the *safest* path, not the
# fastest — the reason the engine exists. reweight() re-prices edges on
# the live field on a lazy TTL (the field itself refreshes on its own
# cadence; 10 min always lands inside freshness).
ENGINE_REWEIGHT_TTL_S = 600.0
ENGINE_BUDGET_S = 8.0        # sub-budget inside PLAN_BUDGET_S
ENGINE_MODES = (("car", "Car (AC)"), ("bike", "Bike / scooter"),
                ("auto", "Auto-rickshaw"), ("cycle", "Bicycle"),
                ("walk", "On foot"))
_ENG_T = 0.0
_ENG_LOCK = threading.Lock()


def _engine():
    """The path engine singleton (C++ when built, Python twin otherwise).
    None when the packed graph isn't shipped — the API degrades to the
    upstream-router options only, never errors."""
    try:
        import routegraph
        return routegraph.path_engine()
    except Exception:
        return None


def _engine_reweight(eng) -> None:
    global _ENG_T
    if time.time() - _ENG_T <= ENGINE_REWEIGHT_TTL_S:
        return
    with _ENG_LOCK:
        if time.time() - _ENG_T <= ENGINE_REWEIGHT_TTL_S:
            return
        try:
            F = deps.field()
        except Exception as e:
            _log.warning("engine reweight: deps.field failed: %r", e)
            return

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
        sampler = val
        try:
            fv = getattr(F, "_snap_fv", None)
            if fv is None or not hasattr(fv, "value"):
                fv = _engine_field_view(F)
            if fv is not None and hasattr(fv, "value"):
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
        except Exception as e:
            _log.warning("engine reweight: field view failed: %r", e)
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

        try:
            res = eng.reweight(sampler) or {}
            # only mark fresh when edges actually priced — a reweight
            # against an empty field (cold task, no snapshot yet) would
            # otherwise stick zero-cost paths for the whole TTL
            if res.get("edges_priced", 0) > 0:
                _ENG_T = time.time()
            _log.warning("engine reweight done: %s", res)
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
    try:
        import grid as _g
        geo = _g.as_geojson(F, cells=56, param="pm2_5")
    except Exception as e:
        _log.warning("engine raster: as_geojson failed: %r", e)
        return None
    rows = []
    for ft in (geo.get("features") or []):
        pm = (ft.get("properties") or {}).get("pm25")
        ring = ((ft.get("geometry") or {}).get("coordinates") or [[]])[0]
        if pm is None or len(ring) < 4:
            continue
        cx = (ring[0][0] + ring[2][0]) / 2.0
        cy = (ring[0][1] + ring[2][1]) / 2.0
        rows.append((cy, cx, float(pm), float(pm), float(pm),
                     float("nan")))
    if not rows:
        _log.warning("engine raster: field served no cells")
        return None
    try:
        import core_engine
        # 8 km coverage: every graph edge lands within reach of a raster
        # cell — past the lattice, nearest_cell would leave edges unpriced
        fv = core_engine.field_view(rows, 8.0)
        _log.warning("engine raster: %d cells -> %s", len(rows),
                     type(fv).__name__)
        return fv
    except Exception as e:
        _log.warning("engine raster: field_view failed: %r", e)
        return None


def _geom_midpoint(geometry: dict):
    coords = (geometry or {}).get("coordinates") or []
    if not coords:
        return None
    return coords[len(coords) // 2]


def _engine_options(flat, flon, tlat, tlon, vehicle, profile) -> list:
    """Least-dose path per engine mode, as plan options.

    The engine's own dose is only the pathfinding criterion — the option
    still prices through the shared exposure.dose band, so every row on
    screen comes from one dose model."""
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
    opts = []
    for mode, label in ENGINE_MODES:
        try:
            r = eng.query(flat, flon, tlat, tlon, mode)
        except Exception as e:
            _log.warning("engine query %s failed: %r", mode, e)
            continue
        if not isinstance(r, dict) or r.get("error") or not r.get("geometry"):
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
        opts.append(_option(
            mode, f"{label} · least-smoke rd",
            r["geometry"], dist_km, dur_s, dur_s, "estimated",
            vehicle, profile,
            steps=None, steps_source="endpoints",
            extra={
                "engine": "alive_core-path",
                "duration_model": "estimated",
                "via_names": r.get("names") or [],
                "snap_m": {"from_m": round(snap.get("from_m") or 0, 1),
                           "to_m": round(snap.get("to_m") or 0, 1)},
            },
            origin=(flat, flon), dest=(tlat, tlon)))
    return opts


def _engine_merge(eng_opts: list, options: list) -> list:
    """Drop an engine option whose geometry is essentially the same road
    a router already returned for that mode — flag the existing option
    'engine_confirmed' instead (the fast road IS the least-smoke one)."""
    out = []
    for eo in eng_opts:
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
    options, opt_err = await _options_bounded(
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
    if opt_err:
        resp["error"] = opt_err
    elif not options:
        resp["error"] = "no route"   # OD in-area but unroutable
    return resp


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
    options, opt_err = await _options_bounded(
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
    return {
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


def _field_status() -> dict:
    try:
        return deps.field().status()
    except Exception:
        return {"source": "unavailable"}
