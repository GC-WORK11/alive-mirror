"""GET /v2/strip?route_id — the live-counter strip (docs/plan/04 §5).

Returns the field sampled every ~250 m along a stored route (the
geometries /v2/plan issues route_ids for) plus the emission-curve
parameters the client integrates locally:

    rate = max(idle_g_s, ef_g_km(vehicle, v) * v / 1000)
    out += rate * dt * cold_factor(km_driven)

The curve is decomposed from server/emissions.py — the same engine
/v2/plan totals come from, so strip and plan agree by construction:
g/km band at the engine's reference speed, idle g/s band, cold-start
zone km + multiplier, occupancy for shared modes. `basis` labels say
which engine produced the numbers; the static EMIT_GKM table runs only
when emissions.py can't be imported. No per-second network: the client
walks this strip with GNSS position + clock ticks.
"""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from . import deps
from .plan import EMIT_GKM, _EMIT_CLASS
from .store import ROUTES

router = APIRouter()

STEP_M = 250.0

try:
    import emissions as _emissions_mod
except Exception:
    _emissions_mod = None


def _band(d: dict) -> dict:
    """{lo,mid,hi} rounded — or pass through whatever the engine gave."""
    if not isinstance(d, dict):
        return {"lo": None, "mid": None, "hi": None}
    return {"lo": d.get("lo"), "mid": d.get("mid"), "hi": d.get("hi")}


def _idle_band_g_s(veh: dict) -> dict:
    """One-second idle span through emissions.integrate → g/s bands.
    Public-API derivation, no table peeking."""
    try:
        out = _emissions_mod.integrate(
            veh, [{"dist_m": 0.0, "speed_mps": 0.0,
                   "moving": False, "dur_s": 1.0}])
    except Exception:
        return {}
    co2 = out.get("co2_kg") or {}
    pm = out.get("pm25_g") or {}
    return {
        "co2_g_s": {"lo": (co2.get("lo") or 0.0) * 1000.0,
                    "mid": (co2.get("mid") or 0.0) * 1000.0,
                    "hi": (co2.get("hi") or 0.0) * 1000.0},
        "pm25_g_s": {"lo": pm.get("lo"), "mid": pm.get("mid"),
                     "hi": pm.get("hi")},
    }


def _emission_curve(mode: str, vehicle: dict = None) -> dict:
    """Flat factor set the ticker integrates — decomposed from
    server/emissions.py (ef band at REF_SPEED, idle g/s, cold-start km
    + multiplier, occupancy). Bands, per doc 06 — a single fake-
    precise number would be a lie we refuse to tell.

    alive_core.emission_g_km(mode, speed_kmh) exists but stays unwired
    here: it takes only a mode string (fleet-prior class defaults baked
    into the generated EF table) while this contract resolves the
    DECLARED vehicle {class,fuel,year} and returns cold/idle/occupancy
    factors the client ticker needs — different inputs, different
    payload."""
    veh = dict(vehicle or {})
    veh.setdefault("class", _EMIT_CLASS.get(mode, mode) or "car")

    if _emissions_mod is not None and \
            hasattr(_emissions_mod, "emission_factors"):
        try:
            ef = _emissions_mod.emission_factors(veh)
        except Exception:
            ef = None
        if isinstance(ef, dict) and "co2" in ef:
            out = {"mode": mode}
            if ef.get("units") == "g/pkm":      # metro: per passenger-km
                out["co2_g_pkm"] = _band(ef["co2"])
                out["pm25_g_pkm"] = _band(ef.get("pm25") or {})
            else:
                out["co2_g_km"] = _band(ef["co2"])
                out["pm25_g_km"] = _band(ef.get("pm25") or {})
                out["nox_g_km"] = _band(ef.get("nox") or {})
                out["cold_start_km"] = float(
                    getattr(_emissions_mod, "COLD_KM", 4.0))
                # cold multiplier at km 0 — getattr-guarded internals
                fuel = None
                try:
                    _res = getattr(_emissions_mod, "_resolve", None)
                    fuel = _res(veh)[1] if _res else veh.get("fuel")
                except Exception:
                    fuel = veh.get("fuel")
                cm = getattr(_emissions_mod, "_COLD_MULT", {}) or {}
                cold = (cm.get(fuel) or {}).get("co2", 1.0) if fuel else 1.0
                out["cold_mult_co2"] = cold or 1.0
                if fuel == "electric" or out["cold_mult_co2"] <= 1.0:
                    out["cold_start_km"] = 0.0
                out["occupancy"] = ef.get("occupancy") or 1.0
                out["idle"] = _idle_band_g_s(veh)
                out["idle_g_s"] = (out["idle"].get("co2_g_s") or {}).get("mid")
                out["ref_speed_kmh"] = round(
                    float(getattr(_emissions_mod, "REF_SPEED_MPS",
                                  30.0 / 3.6)) * 3.6, 1)
            out["bs_class"] = ef.get("bs_class")
            out["confidence"] = ef.get("confidence")
            out["label"] = ef.get("label")
            out["basis"] = ("server/emissions.py — est., "
                            + (ef.get("label") or
                               "vehicles like yours; band = class spread "
                               "x speed-curve uncertainty"))
            out["engine"] = "server/emissions.py"
            return out

    # --- labelled fallback: static table (emissions.py not importable)
    e = EMIT_GKM.get(mode) or EMIT_GKM.get(_EMIT_CLASS.get(mode, "")) or {}
    out = {"mode": mode}
    if "co2_pkm" in e:
        out["co2_g_pkm"] = {"lo": e["co2_pkm"][0], "hi": e["co2_pkm"][1],
                            "mid": sum(e["co2_pkm"]) / 2}
        out["pm25_g_pkm"] = {"lo": e["pm25_pkm"][0], "hi": e["pm25_pkm"][1],
                             "mid": sum(e["pm25_pkm"]) / 2}
    else:
        out["co2_g_km"] = {"lo": (e.get("co2") or (0, 0))[0],
                           "hi": (e.get("co2") or (0, 0))[1],
                           "mid": sum(e.get("co2") or (0, 0)) / 2}
        out["pm25_g_km"] = {"lo": (e.get("pm25") or (0, 0))[0],
                            "hi": (e.get("pm25") or (0, 0))[1],
                            "mid": sum(e.get("pm25") or (0, 0)) / 2}
        out["idle_g_s"] = e.get("idle_g_s")
        out["occupancy"] = e.get("occ")
        out["cold_start_km"] = 4.0 if (e.get("co2") or (0, 0))[1] else 0.0
    out["basis"] = ("fallback static table — server/emissions.py "
                    "unavailable (Delhi fleet prior)")
    out["engine"] = "static-table fallback"
    return out


def _roads_for(samples: list, steps: list) -> list:
    """Group strip samples under the road they were driven on.

    Steps carry OSRM street names + per-step distance_m (stored on the
    plan-time RouteStore record). Each sample's chunk length is split
    across the step spans it overlaps; roads aggregate consecutive
    same-name steps into one entry so the answer reads 'Ring Road:
    3.2 km, 61% of dose', not 14 step slices.
    dose_share is the distance-weighted pm25 fraction over chunks with
    real readings — None when nothing sampled (honest, never invented).
    """
    spans = []
    cum = 0.0
    for st in steps or []:
        d = float(st.get("distance_m") or 0.0)
        if d > 0:
            spans.append((cum, cum + d, (st.get("street") or "").strip()))
        cum += d
    if not samples or not spans:
        return []

    groups = []          # ordered, merge adjacent same-name spans
    for lo, hi, name in spans:
        name = name or "unnamed road"
        if groups and groups[-1]["name"] == name:
            groups[-1]["hi"] = hi
        else:
            groups.append({"name": name, "lo": lo, "hi": hi})

    total_w = 0.0
    for g in groups:
        g["dist_m"] = 0.0
        g["w_sum"] = 0.0
        g["covered_m"] = 0.0
        g["n"] = 0
    cum = 0.0
    for s in samples:
        # sample dist_m is the chunk's own length — cumulative position is
        # accumulated here to align with OSRM per-step distance_m spans
        seg = float(s.get("dist_m") or STEP_M)
        lo_d, hi_d = cum, cum + seg
        cum = hi_d
        pm = s.get("pm25")
        overlapped = False
        for g in groups:
            ov = min(hi_d, g["hi"]) - max(lo_d, g["lo"])
            if ov <= 0:
                continue
            overlapped = True
            g["dist_m"] += ov
            g["n"] += 1
            if pm is not None:
                w = float(pm) * ov
                g["w_sum"] += w
                g["covered_m"] += ov
                total_w += w
        if not overlapped:
            # step-distance drift past the last span → last road, honestly
            g = groups[-1]
            g["dist_m"] += seg
            g["n"] += 1
            if pm is not None:
                g["w_sum"] += float(pm) * seg
                g["covered_m"] += seg
                total_w += float(pm) * seg

    roads = []
    for g in groups:
        cov = g["covered_m"]
        roads.append({
            "name": g["name"],
            "dist_m": int(round(g["dist_m"])),
            "samples": g["n"],
            "avg_pm25": round(g["w_sum"] / cov, 1) if cov else None,
            "dose_share": round(g["w_sum"] / total_w, 3)
            if total_w and cov else None,
        })
    return [r for r in roads if r["dist_m"] > 0]


@router.get("/strip")
async def strip(route_id: str = Query(min_length=1)):
    rec = ROUTES.get(route_id)
    if rec is None:
        return JSONResponse(status_code=404, content={
            "error": "unknown route_id",
            "detail": "route_ids come from /v2/plan and expire after 1 h"})

    await deps.field_refresh()
    F = deps.field()
    try:
        import exposure
        samples = exposure.segment_samples(
            rec["geometry"], rec.get("duration_s") or 0.0, step_m=STEP_M)
    except Exception:
        samples = []

    strip_pts = []
    for s in samples:
        c = F.value(s["lat"], s["lon"])
        sd = None
        try:
            sd = F.sigma(s["lat"], s["lon"])
        except Exception:
            pass
        strip_pts.append({
            "lat": round(s["lat"], 5), "lon": round(s["lon"], 5),
            "dist_m": round(s["dist_m"]),
            "pm25": round(c, 1) if c is not None else None,
            "lo": round(max(0.0, c - sd), 1) if (c is not None and sd) else None,
            "hi": round(c + sd, 1) if (c is not None and sd) else None,
        })

    return {
        "route_id": route_id,
        "mode": rec.get("mode"),
        "vehicle": rec.get("vehicle"),
        "route_age_s": ROUTES.age_s(route_id),
        "step_m": STEP_M,
        "samples": strip_pts,
        "roads": _roads_for(strip_pts, rec.get("steps") or []),
        "emissions_curve": _emission_curve(
            rec.get("mode") or "", rec.get("emissions_vehicle")),
        "field": F.status() if hasattr(F, "status") else {},
    }
