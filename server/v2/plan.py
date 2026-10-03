"""POST /v2/plan — trip options with dose + emissions bands and the
doc-06 §4 ranking (docs/plan/05 §3).

Options span the real mode set (car AC / open, bike-scooter, auto, bus,
metro, cycle, walk — same family /compare serves). Motorized geometry
comes from Amazon geo-routes CalculateRoutes when ALIVE_LOCATION_KEY is
set (traffic-aware duration + alternatives), else the same OSRM call
main.py makes. Metro comes through transit_real.py's GTFS router with
the synthetic fallback. Dose rides exposure.dose on the live field;
emissions come from server/emissions.py when importable, else the
honest per-km band table below (est., labeled). Ranking is the spec's
epsilon-constraint: dose_lo within 10% ties, lowest emission wins;
'lightest on both' / 'lightest for you' / 'lightest for Delhi' tags and
the 1.6x-fastest time guard — all in `rank_options`, a pure function.
"""
import time
from typing import Optional

from fastapi import APIRouter

from . import deps
from .store import ROUTES

router = APIRouter()

try:
    import exposure  # server module (path fixed by v2/__init__)
except Exception:  # pragma: no cover
    exposure = None

try:
    import emissions as _emissions_mod  # may be built by another lane
except Exception:
    _emissions_mod = None


# --- modes -------------------------------------------------------------------
# (mode, osrm profile, exposure microenv, label, AWS travel mode, time factor)
MODE_TABLE = [
    ("car",      "driving", "driving_car_ac",      "Car (AC)",           "Car",    1.0),
    ("car_open", "driving", "driving_car_open",    "Car (windows down)", "Car",    1.0),
    ("bike",     "driving", "driving_two_wheeler", "Bike / scooter",     "Scooter", 0.9),
    ("auto",     "driving", "auto_rickshaw",       "Auto-rickshaw",      "Car",    1.25),
    ("bus",      "driving", "bus",                 "Bus",                "Car",    1.6),
    ("cycle",    "cycling", "cycling",             "Bicycle",            None,     1.0),
    ("walk",     "walking", "walking",             "On foot",            "Pedestrian", 1.0),
]
_MODES = {m[0]: m for m in MODE_TABLE}
_VEHICLE_ALIASES = {"two_wheeler": "bike", "scooter": "bike", "car_ac": "car",
                    "cab": "car", "rickshaw": "auto", "walking": "walk",
                    "cycling": "cycle", "metro": "metro"}
MODE_SPEED_KMH = {"cycling": 15.0, "walking": 5.0}   # stated estimate (main.py)

# --- emissions band table (fallback) -----------------------------------------
# Per vehicle-km bands for the Delhi fleet prior (doc 06 §2: BS bucket x
# ARAI/ICAP measured factors x real-world uplift). Shared modes divide by
# occupancy; metro is per passenger-km *including electricity* (verified:
# 11-25 g CO2e/pkm, claims ledger). Bands, never point values — per-vehicle
# truth is unknowable and we say so.
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
EMIT_BASIS = ("est. for vehicles like yours — Delhi fleet prior "
              "(ARAI/ICAP factors, BS-IV-ish mix), doc 06 §2")


def _emission_band(mode: str, dist_km: float, eta_s: float,
                   freeflow_s: Optional[float]) -> dict:
    """{co2_kg:{lo,mid,hi}, pm25_g:{lo,mid,hi}} for one option.

    Congestion = (eta - freeflow) adds idle fuel at the mode's idle rate;
    shared modes divide by stated occupancy. If a real emissions module
    lands (server/emissions.py) it takes over via _module_emissions.
    """
    if _emissions_mod is not None and hasattr(_emissions_mod, "trip_emissions"):
        try:
            out = _emissions_mod.trip_emissions(
                mode=mode, distance_km=dist_km, duration_s=eta_s,
                freeflow_s=freeflow_s)
            if isinstance(out, dict) and "co2_kg" in out:
                out.setdefault("basis", "emissions.py")
                return out
        except Exception:
            pass  # graceful: fall back to the table

    e = EMIT_GKM.get(mode)
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
        "occupancy": occ if occ != 1.0 else None,
    }


# --- option builders -----------------------------------------------------------
def _dose_band(geometry: dict, duration_s: float, microenv: str) -> dict:
    """exposure.dose on the live field → {lo,mid,hi}; lo/hi may be None
    when the field can't give sigma — honest, not invented."""
    if exposure is None:
        return {"lo": None, "mid": None, "hi": None, "note": "dose engine unavailable"}
    F = deps.field()
    try:
        e = exposure.dose(geometry, duration_s, microenv, F.value,
                          F.nearest_sample_km, field_sigma=F.sigma)
    except Exception:
        return {"lo": None, "mid": None, "hi": None, "note": "dose engine error"}
    return {
        "lo": e.get("dose_ug_lo"), "mid": e.get("dose_ug"),
        "hi": e.get("dose_ug_hi"),
        "avg_conc_ugm3": e.get("avg_conc_ugm3"),
        "confidence": e.get("confidence"),
        "basis": "est." if e.get("dose_ug") is not None else None,
    }


def _option(mode: str, label: str, geometry: dict, dist_km: float,
            eta_s: float, freeflow_s: Optional[float], eta_model: str,
            vehicle: str, extra: Optional[dict] = None) -> dict:
    microenv = _MODES[mode][2]
    opt = {
        "mode": mode,
        "label": label,
        "route_geojson": geometry,
        "distance_km": round(dist_km, 2),
        "eta_s": round(eta_s),
        "freeflow_s": round(freeflow_s) if freeflow_s else None,
        "eta_model": eta_model,
        "dose": _dose_band(geometry, eta_s, microenv),
        "emissions": _emission_band(mode, dist_km, eta_s, freeflow_s),
        "tag": None,
        "recommended": False,
        "reason_line": "",
        "your_vehicle": mode == vehicle,
    }
    if extra:
        opt.update(extra)
    opt["route_id"] = ROUTES.put({
        "geometry": geometry, "mode": mode,
        "duration_s": eta_s, "vehicle": vehicle,
    })
    return opt


async def _motorized_options(flat, flon, tlat, tlon, vehicle, depart_at) -> list:
    """Car-family geometries: AWS CalculateRoutes when keyed (traffic +
    alternatives), else one OSRM driving route. Durations scale per mode
    by the same stated factors main.py uses."""
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

    opts: list = []
    if aws_routes:
        car_rts = aws_routes.get("Car") or []
        sco_rts = aws_routes.get("Scooter") or car_rts
        for i, rt in enumerate(car_rts[:3]):
            dist_km = rt["distance_m"] / 1000.0
            geom, dur, ff = rt["geometry"], rt["duration_s"], rt.get("freeflow_s")
            label = "Car (AC)" + (f" · alt {i}" if i else "")
            opts.append(_option("car", label, geom, dist_km, dur, ff,
                                "amazon-location", vehicle))
            if i == 0:
                opts.append(_option("car_open", "Car (windows down)", geom,
                                    dist_km, dur, ff, "amazon-location",
                                    vehicle))
                opts.append(_option("auto", "Auto-rickshaw", geom, dist_km,
                                    dur * 1.25, (ff or dur) * 1.25,
                                    "amazon-location+est", vehicle))
                opts.append(_option("bus", "Bus", geom, dist_km, dur * 1.6,
                                    (ff or dur) * 1.6, "amazon-location+est",
                                    vehicle))
        if sco_rts:
            rt = sco_rts[0]
            opts.append(_option("bike", "Bike / scooter", rt["geometry"],
                                rt["distance_m"] / 1000.0, rt["duration_s"],
                                rt.get("freeflow_s"), "amazon-location",
                                vehicle))
        return opts

    rt = await deps.osrm_route("driving", flon, flat, tlon, tlat)
    if not rt:
        return opts
    dist_km = rt["distance"] / 1000.0
    base = rt["duration"]  # OSRM duration ≈ free-flow — no traffic feed
    for mode, label in (("car", "Car (AC)"), ("car_open", "Car (windows down)"),
                        ("bike", "Bike / scooter"), ("auto", "Auto-rickshaw"),
                        ("bus", "Bus")):
        f = _MODES[mode][5]
        opts.append(_option(mode, label, rt["geometry"], dist_km,
                            base * f, base * f, "osrm-freeflow", vehicle))
    return opts


async def _slow_mode_options(flat, flon, tlat, tlon, vehicle) -> list:
    """Cycle/walk via OSRM profiles; durations are stated estimates."""
    opts = []
    for mode, profile in (("cycle", "cycling"), ("walk", "walking")):
        rt = await deps.osrm_route(profile, flon, flat, tlon, tlat)
        if not rt:
            continue
        dist_km = rt["distance"] / 1000.0
        dur = dist_km / MODE_SPEED_KMH[profile] * 3600.0
        opts.append(_option(mode, _MODES[mode][3], rt["geometry"], dist_km,
                            dur, dur, "estimated", vehicle))
    return opts


def _metro_option(flat, flon, tlat, tlon, vehicle) -> Optional[dict]:
    """transit.py metro (GTFS when cached, synthetic model otherwise)."""
    try:
        import transit
        F = deps.field()
        m = transit.metro_option(flat, flon, tlat, tlon, F.value)
    except Exception:
        return None
    if not m or not m.get("geometry"):
        return None
    dose_mid = (m.get("exposure") or {}).get("dose_ug")
    return {
        "mode": "metro",
        "label": m.get("label") or "Metro + walk",
        "route_geojson": m["geometry"],
        "distance_km": m.get("distance_km"),
        "eta_s": m.get("duration_s"),
        "freeflow_s": m.get("duration_s"),
        "eta_model": m.get("duration_model") or "gtfs",
        "dose": {"lo": None, "mid": dose_mid, "hi": None,
                 "confidence": (m.get("exposure") or {}).get("confidence"),
                 "basis": "est."},
        "emissions": _emission_band("metro", m.get("distance_km") or 0.0,
                                   m.get("duration_s") or 0.0, None),
        "tag": None, "recommended": False, "reason_line": "",
        "your_vehicle": vehicle == "metro",
        "stations": m.get("stations"),
        "route_id": ROUTES.put({"geometry": m["geometry"], "mode": "metro",
                                "duration_s": m.get("duration_s"),
                                "vehicle": vehicle}),
    }


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

      tied   = dose_lo within 10% of the best
      winner = min emission inside tied  → recommended
      tag 'lightest on both' if winner also has the global min emission,
      else 'lightest for you' on the dose winner and 'lightest for
      Delhi' on the emission winner. Time guard: a recommendation slower
      than 1.6x the fastest option must say '+N min'.
    """
    scored = [o for o in options
              if _dose_key(o) != float("inf") and o.get("eta_s")]
    if not scored:
        return options
    dose_min = min(_dose_key(o) for o in scored)
    tied = [o for o in scored if _dose_key(o) <= 1.10 * dose_min]
    winner = min(tied, key=_co2_mid)
    emin = min(scored, key=_co2_mid)
    dwin = min(scored, key=_dose_key)
    fastest = min(o["eta_s"] for o in scored)

    for o in scored:
        o["tag"] = None
        o["reason_line"] = ""
        o["recommended"] = False
    winner["recommended"] = True

    if _co2_mid(winner) == _co2_mid(emin):
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


# --- endpoint ------------------------------------------------------------------
def _pt(v, name: str):
    if isinstance(v, dict):
        return float(v["lat"]), float(v["lon"])
    if isinstance(v, (list, tuple)) and len(v) >= 2:
        # [lon, lat] GeoJSON order
        return float(v[1]), float(v[0])
    raise ValueError(f"{name}: need {{lat,lon}} or [lon,lat]")


@router.post("/plan")
async def plan(body: dict):
    t0 = time.perf_counter()
    try:
        flat, flon = _pt(body.get("from") or body.get("from_"), "from")
        tlat, tlon = _pt(body.get("to"), "to")
    except (KeyError, TypeError, ValueError) as e:
        return {"options": [], "error": str(e)}
    vehicle = _VEHICLE_ALIASES.get(
        (body.get("vehicle") or "").lower(),
        (body.get("vehicle") or "").lower() or "car")
    depart_at = body.get("depart_at")

    import asyncio
    await deps.field_refresh()
    motor, slow = await asyncio.gather(
        _motorized_options(flat, flon, tlat, tlon, vehicle, depart_at),
        _slow_mode_options(flat, flon, tlat, tlon, vehicle),
        return_exceptions=True)
    options = ([o for o in (motor or []) if isinstance(o, dict)]
               if isinstance(motor, list) else [])
    options += ([o for o in (slow or []) if isinstance(o, dict)]
                if isinstance(slow, list) else [])
    metro = _metro_option(flat, flon, tlat, tlon, vehicle)
    if metro:
        options.append(metro)

    rank_options(options)
    return {
        "from": {"lat": flat, "lon": flon},
        "to": {"lat": tlat, "lon": tlon},
        "vehicle": vehicle,
        "depart_at": depart_at,
        "options": options,
        "ranking": "doc 06 §4: dose_lo within 10% ties, lowest emission wins",
        "field": _field_status(),
        "took_ms": round((time.perf_counter() - t0) * 1000.0, 1),
    }


def _field_status() -> dict:
    try:
        return deps.field().status()
    except Exception:
        return {"source": "unavailable"}
