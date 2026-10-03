"""GET /v2/strip?route_id — the live-counter strip (docs/plan/04 §5).

Returns the field sampled every ~250 m along a stored route (the
geometries /v2/plan issues route_ids for) plus the emission-curve
parameters the client integrates locally. No per-second network: the
client walks this strip with GNSS position + clock ticks.
"""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from . import deps
from .plan import EMIT_GKM
from .store import ROUTES

router = APIRouter()

STEP_M = 250.0


def _emission_curve(mode: str) -> dict:
    """Flat factor set the ticker integrates: ef g/km band + idle g/s +
    cold-start distance. Bands, per doc 06 — a single fake-precise
    number would be a lie we refuse to tell."""
    e = EMIT_GKM.get(mode) or {}
    out = {"mode": mode}
    if "co2_pkm" in e:
        out["co2_g_pkm"] = {"lo": e["co2_pkm"][0], "hi": e["co2_pkm"][1]}
        out["pm25_g_pkm"] = {"lo": e["pm25_pkm"][0], "hi": e["pm25_pkm"][1]}
    else:
        out["co2_g_km"] = {"lo": (e.get("co2") or (0, 0))[0],
                           "hi": (e.get("co2") or (0, 0))[1]}
        out["pm25_g_km"] = {"lo": (e.get("pm25") or (0, 0))[0],
                            "hi": (e.get("pm25") or (0, 0))[1]}
        out["idle_g_s"] = e.get("idle_g_s")
        out["occupancy"] = e.get("occ")
        out["cold_start_km"] = 4.0 if (e.get("co2") or (0, 0))[1] else 0.0
    out["basis"] = ("est. — vehicles like yours; band = class spread x "
                    "speed-curve uncertainty")
    return out


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
        "step_m": STEP_M,
        "samples": strip_pts,
        "emissions_curve": _emission_curve(rec.get("mode") or ""),
        "field": F.status() if hasattr(F, "status") else {},
    }
