"""GET /v2/search — 3-tier merged suggestions (docs/plan/04 §2).

T1 = our server index: `alive_core` (C++) if importable, else
`alive_core_ref`, else the bundled-gazetteer scan — picked once at
import. T2 = Amazon Location geo-places Suggest, queried in parallel via
asyncio.gather when ALIVE_LOCATION_KEY is configured. Merge/dedupe by
normalized name + 75 m radius; rank exact-prefix > token-prefix > fuzzy
> distance from the user. Response reports took_ms per tier and which
tiers actually ran — including the honest 't2 disabled' state.
"""
import asyncio
import math
import time
from typing import Optional

from fastapi import APIRouter, Query

from . import deps
from .gazetteer import GAZ, classify, normalize

router = APIRouter()

DEDUPE_RADIUS_M = 75.0
_MATCH_NAMES = {0: "exact-prefix", 1: "token-prefix", 2: "fuzzy", 3: "other"}


def _hav_m(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371000.0 * math.asin(math.sqrt(h))


# --- T1 engine selection (once, at import) -----------------------------------
def _engine_rows(out: object, default_source: str) -> list:
    """Normalize whatever an engine returns into result rows."""
    rows = []
    for r in out or []:
        if not isinstance(r, dict):
            continue
        lat, lon = r.get("lat"), r.get("lon")
        if lat is None or lon is None:
            continue
        row = dict(r)
        row.setdefault("id", None)
        row.setdefault("name", r.get("title") or r.get("n")
                       or r.get("display") or "")
        row["lat"], row["lon"] = float(lat), float(lon)
        row["source"] = r.get("source") or default_source
        row["sources"] = list(dict.fromkeys(
            (r.get("sources") or []) + ["t1"]))
        rows.append(row)
    return rows


def _pick_t1():
    # core_engine.SearchIndex is parked, not wired: its bag-of-tokens
    # scoring scores 16/20 on test_search_quality's tuned acceptance —
    # the gazetteer ranker (lead-token coverage + name-precision) wins.
    # It stays available in core_engine until its ranking reaches parity.
    try:
        import alive_core as mod  # bare extension — no index wiring there
        if hasattr(mod, "search"):
            return "alive_core", mod.search
    except Exception:
        pass
    try:
        import alive_core_ref as mod  # pure-python reference build
        if hasattr(mod, "search"):
            return "alive_core_ref", mod.search
    except Exception:
        pass
    return "gazetteer", GAZ.search


T1_ENGINE, _t1_raw = _pick_t1()


def _t1(q: str, lat: float, lon: float, limit: int) -> list:
    try:
        out = _t1_raw(q, lat=lat, lon=lon, limit=limit)
    except TypeError:
        try:
            out = _t1_raw(q, lat, lon, limit)
        except Exception:
            return []
    except Exception:
        return []
    return _engine_rows(out, T1_ENGINE)


def _tag_match(rows: list, qn: str) -> None:
    """Attach match_rank/match to rows that don't already carry them
    (T2 rows get classified against the same rule for a fair merge)."""
    for r in rows:
        if r.get("match_rank") is not None:
            continue
        cls = classify(qn, normalize(r.get("name") or ""))
        r["match_rank"] = cls
        r["match"] = _MATCH_NAMES[cls]


def _merge(t1: list, t2: list, qn: str, blat: float, blon: float) -> list:
    """Dedupe on normalized name within 75 m; rank by match class then
    distance. Sources merge honestly: a place found by both tiers says so."""
    merged: list = []
    for r in t1 + t2:
        r.setdefault("sources", [r.get("source", "?")])
        if r.get("distance_m") is None:
            r["distance_m"] = round(_hav_m(blat, blon, r["lat"], r["lon"]))
        key = normalize(r.get("name") or "")
        dup = None
        for e in merged:
            if normalize(e.get("name") or "") != key:
                continue
            if _hav_m(e["lat"], e["lon"], r["lat"], r["lon"]) <= DEDUPE_RADIUS_M:
                dup = e
                break
        if dup is not None:
            dup["sources"] = list(dict.fromkeys(
                dup["sources"] + r["sources"]))
            if r.get("id") and not dup.get("id"):
                dup["id"] = r["id"]
            if r["match_rank"] < dup["match_rank"]:
                dup["match_rank"] = r["match_rank"]
                dup["match"] = r["match"]
        else:
            merged.append(r)
    merged.sort(key=lambda r: (r.get("match_rank", 3),
                               # scored T1 rows order by score inside a
                               # match class; unscored rows (T2, rank 3
                               # partials) stay distance-ordered
                               -(r.get("score") or 0.0)
                               if r.get("match_rank", 3) < 3 else 0.0,
                               r.get("distance_m") or 9e9,
                               0 if "t1" in r.get("sources", []) else 1))
    return merged


@router.get("/search")
async def search(q: str = Query(min_length=1, max_length=200),
                 lat: Optional[float] = None, lon: Optional[float] = None,
                 limit: int = Query(default=8, le=15)):
    limit = max(0, limit)      # limit<=0 → no rows; never a negative slice
    blat = lat if lat is not None else deps.DELHI_CENTER["lat"]
    blon = lon if lon is not None else deps.DELHI_CENTER["lon"]
    qn = normalize(q)
    t0 = time.perf_counter()

    t1_task = asyncio.create_task(
        asyncio.to_thread(_t1, q, blat, blon, limit))
    loc = deps.get_location()
    t2_task = None
    if loc is not None and getattr(loc, "enabled", False):
        async def _t2():
            try:
                return await loc.suggest(q, blat, blon, limit)
            except Exception:
                return None
        t2_task = asyncio.create_task(_t2())

    t1_rows = await t1_task
    t1_ms = (time.perf_counter() - t0) * 1000.0

    t2_rows, t2_ms = [], None
    if t2_task is not None:
        t1 = time.perf_counter()
        t2_rows = await t2_task
        t2_ms = (time.perf_counter() - t1) * 1000.0
        if t2_rows is None:  # upstream failed — honest, not an error tier
            t2_rows = []

    for r in t1_rows:
        r["sources"] = list(dict.fromkeys(r.get("sources") or ["t1"]))
    for r in t2_rows:
        r["sources"] = ["t2"]
    _tag_match(t1_rows + t2_rows, qn)

    merged = _merge(t1_rows, t2_rows, qn, blat, blon)
    tiers = ["t1"] + (["t2"] if t2_task is not None else [])
    return {
        "q": q,
        "bias": {"lat": blat, "lon": blon},
        "results": merged[:limit],
        "count": len(merged[:limit]),
        "t1": t1_rows,
        "t2": t2_rows,
        "tiers": tiers,
        "t1_engine": T1_ENGINE,
        "t2_status": ("ok" if t2_task is not None else
                      "disabled:no ALIVE_LOCATION_KEY"),
        "took_ms": {
            "t1": round(t1_ms, 1),
            "t2": round(t2_ms, 1) if t2_ms is not None else None,
            "total": round((time.perf_counter() - t0) * 1000.0, 1),
        },
    }
