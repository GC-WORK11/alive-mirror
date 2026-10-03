"""GET /v2/city — the consumer 'Delhi today' summary (docs/plan/07 §1).

Live field stats + provenance + trip aggregates. Everything here is a
city total or average — the privacy contract is structural, not a
promise: TripAggregates holds nothing else to leak.
"""
import statistics
import time

from fastapi import APIRouter

from . import deps
from .store import TRIPS

router = APIRouter()

# light lattice over the NCR bbox for city stats — 15 evals, not a crawl
_LATS = (28.30, 28.45, 28.60, 28.75, 28.88)
_LONS = (76.88, 77.10, 77.32, 77.54, 77.76)


def _field_stats(F) -> dict:
    vals = []
    for la in _LATS:
        for lo in _LONS:
            try:
                v = F.value(la, lo)
            except Exception:
                v = None
            if v is not None:
                vals.append(v)
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


@router.get("/city")
async def city():
    await deps.field_refresh()
    F = deps.field()
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

    return {
        "ts": time.time(),
        "pm25_stats": _field_stats(F),
        "field": fstat,
        "field_age_s": fstat.get("age_s"),
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
        "trips": TRIPS.city_aggregates(),
    }
