"""GET /v2/reach — the dose-budget reachable region (docs/plan/alive-depth L4).

"Where can your lungs go today inside your budget": a bounded Dijkstra
over the same directed-edge-state expansion the least-dose A* uses —
no heuristic, no destination — settling every edge state whose inhaled
dose stays <= budget_ug. What it returns is the real settled edge set
(the frontier is the data, never a smoothed circle), as e6 polylines
the city map can paint directly.

The heavy search runs off the request thread on plan._ENG_EXEC — same
shared executor as the engine option arm — and is hard-bounded by
REACH_BUDGET_S.
"""
import asyncio
import concurrent.futures
import json
import math
import struct
import time

from fastapi import APIRouter
from fastapi.responses import Response

from . import deps, plan

router = APIRouter()

# 60 s veil cache — same anchor cell + budget + mode inside a minute
# serves the SAME serialized body, no re-solve, no re-encode. The veil
# is deterministic over the priced raster, so a hit is identical work;
# the field epoch in the key makes a mid-TTL raster refresh invalidate
# honestly instead of outliving the TTL. Storing BYTES is the point: a
# hit costs zero event-loop JSON encode (the ~1-3 s loop-block the
# starve probe showed on car<=100 bodies).
_REACH_CACHE = deps.TTLCache(60.0, max_entries=12)

REACH_MAX_STATES = 2_000_000    # directed edge states the Dijkstra may pop
EDGE_SERVE_MAX = 90_000         # beyond this the veil payload outweighs
                                # the map — serve the settled core, flag it
REACH_BUDGET_S = 9.0            # hard bound inside the single worker
                                # (matches plan.ENGINE_BUDGET_S — a cold
                                # first call may wait out the raster
                                # reprice before solving)

# Veil encoding needs its own pool: _ENG_EXEC stays for engine work (a
# multi-MB serialize must not hold an engine slot), and the shared
# default executor is squatted by the boot-warm fleet on a cold task —
# the encode would queue behind it and stretch the response by the
# whole warm window (executor-audit lane). One worker; encodes are
# short and the veil cache absorbs repeats.
_ENCODE_EXEC = concurrent.futures.ThreadPoolExecutor(
    max_workers=1, thread_name_prefix="alive-encode")


# --- slim ARG1/ARG2 geometry decoder --------------------------------------
# The full RouteGraph parse walks every edge + name; a reach reply only
# needs the polyline stream, so this decodes the header once and then
# reads edge records random-access (fixed-stride struct).
class _EdgeGeom:
    def __init__(self, blob: bytes):
        magic, nn, ne, nname, _ = struct.unpack_from("<4s4I", blob, 0)
        if magic not in (b"ARG1", b"ARG2"):
            raise ValueError("route_graph: bad magic")
        off = 20 + 16 + 8 * nn
        for _ in range(nname):
            (ln,) = struct.unpack_from("<H", blob, off)
            off += 2 + ln
        fmt = "<IIfIHBbBiBB" if magic == b"ARG2" else "<IIfIHBbBiB"
        self._sz = struct.calcsize(fmt)
        self._fmt = fmt
        self._blob = blob
        self._e_off = off
        off += self._sz * ne
        if magic == b"ARG2":
            (nb,) = struct.unpack_from("<I", blob, off)
            off += 4 + 13 * nb
        self._pts = struct.unpack_from(
            "<%di" % ((len(blob) - off) // 4), blob, off)
        import routegraph
        self._un16 = routegraph._unpack_i16

    def edge_e6(self, i):
        """Edge polyline as flat e6 ints [lon, lat, ...] — the ints the
        graph itself stores, so what the client paints is exactly the
        settled edge, not a re-quantized copy."""
        t = struct.unpack_from(self._fmt, self._blob,
                               self._e_off + i * self._sz)
        off, n = t[3], t[4]
        pts = self._pts
        lon, lat = pts[off], pts[off + 1]
        out = [lon, lat]
        k = off + 2
        un = self._un16
        for _ in range(n - 1):
            dl, dp = un(pts[k])
            k += 1
            lon += dl
            lat += dp
            out.append(lon)
            out.append(lat)
        return out


_GEOM = None


def _geom():
    global _GEOM
    if _GEOM is None:
        import routegraph
        _GEOM = _EdgeGeom(routegraph.load_blob())
    return _GEOM


def _field_age_s():
    try:
        st = deps.field().status()
        return st.get("age_s") if isinstance(st, dict) else None
    except Exception:
        return None


def _json_bytes(payload: dict) -> bytes:
    """The exact bytes Starlette's JSONResponse would render — the
    encode runs OFF the event loop (run_in_executor) so a 3.5 MB veil
    doesn't park every other request behind jsonable_encoder +
    json.dumps on the single request thread."""
    return json.dumps(payload, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def _cache_hit(body: bytes, t0: float) -> Response:
    """Serve stored veil bytes with took_ms spliced to the real (cache)
    serve time — took_ms is the last JSON member by construction, so
    the splice rewrites only the tail; x-alive-cache marks the hit."""
    ms = (time.perf_counter() - t0) * 1000.0
    i = body.rfind(b'"took_ms":')
    if i != -1 and body.endswith(b"}"):
        try:
            float(body[i + len(b'"took_ms":'):-1])   # tail is exactly
        except ValueError:                            # "took_ms":<num>}
            i = -1                                    # else don't touch
    if i != -1:
        body = (body[:i] + b'"took_ms":' +
                f"{ms:.1f}".encode() + b"}")
    return Response(content=body, media_type="application/json",
                    headers={"x-alive-cache": "hit"})


def _mode_or_car(mode) -> str:
    try:
        import routegraph
        rules = routegraph.MODE_RULES
    except Exception:
        rules = {"car": None}
    m = (mode or "").lower().strip()
    return m if m in rules else "car"


def _solve(eng, lat, lon, mode, budget):
    """Runs on _ENG_EXEC. Prices the graph (TTL-cached inside
    _engine_reweight), refuses to serve a cold field — an unpriced
    engine would flood every edge to the cap at cost 0, which is a
    wrong answer, not a cheap one — runs the bounded Dijkstra, then
    decodes the settled edges off the request thread too."""
    plan._engine_reweight(eng)
    ep = getattr(eng, "edges_priced", None)
    try:
        ep = ep() if callable(ep) else (ep or 0)
    except Exception:
        ep = 0
    if not ep:
        return {"error": "dose field not priced yet — retry in a few "
                         "seconds", "code": "engine_unavailable"}
    res = eng.reach(lat, lon, mode, budget, REACH_MAX_STATES)
    if not isinstance(res, dict) or res.get("error") or res.get("code"):
        return res
    ids = res.get("edge_ids") or []
    # Settle order is dose-ascending, so ids[:N] paints only the
    # cheapest core around the anchor — for a big settled region (car
    # modes routinely settle ~10x the cap) the veil showed a blob, not
    # the real reach. A uniform stride across settle order paints the
    # full extent at the same edge count and wire size — every dose
    # band represented, no region invented. edge_partial still says
    # honestly that the served set is a subset.
    if len(ids) > EDGE_SERVE_MAX:
        stride = len(ids) / EDGE_SERVE_MAX
        served = [ids[int(i * stride)] for i in range(EDGE_SERVE_MAX)]
    else:
        served = ids
    g = _geom()
    return {
        "snap_m": res.get("snap_m"),
        "edges_e6": [g.edge_e6(i) for i in served],
        "edge_count": len(ids),
        "edge_partial": len(ids) > len(served),
        "expanded": res.get("expanded", 0),
        "nodes": res.get("nodes", 0),
        "distance_km": round((res.get("distance_m") or 0.0) / 1000.0, 3),
        "frontier_budget_ug": res.get("frontier_ug", 0.0),
        "truncated": bool(res.get("truncated")),
    }


@router.get("/reach")
async def reach(lat: float, lon: float, mode: str = "walk",
                budget_ug: float = 50.0):
    t0 = time.perf_counter()
    mode = _mode_or_car(mode)
    try:
        budget = float(budget_ug)
    except (TypeError, ValueError):
        budget = 0.0
    if not math.isfinite(budget) or budget < 0:
        budget = 0.0
    resp = {"from": {"lat": lat, "lon": lon}, "mode": mode,
            "budget_ug": budget, "snap_m": None, "edges_e6": [],
            "edge_count": 0, "edge_partial": False, "expanded": 0,
            "nodes": 0, "distance_km": 0.0, "frontier_budget_ug": 0.0,
            "truncated": False, "field_age_s": _field_age_s()}

    def _done(**extra):
        resp.update(extra)
        resp["took_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)
        return resp

    if not (math.isfinite(lat) and math.isfinite(lon)):
        return _done(error="non-finite coordinate", code="bad_request")
    try:
        from airfield import in_service_area
        in_area = in_service_area(lat, lon)
    except Exception:
        in_area = True          # field itself down — don't reject on a guess
    if not in_area:
        from airfield import OUT_OF_AREA
        return _done(error=OUT_OF_AREA, code="outside_service_area")

    # ~11 m anchor cells — a veil solved 11 m away settles the same
    # region at city scale; the echoed `from` is the first requester's
    # coords (drift <= cell size, immaterial next to a km-scale veil)
    cache_key = (mode, round(budget, 1), round(lat, 4), round(lon, 4),
                 deps.data_epoch())
    hit = _REACH_CACHE.get(cache_key)
    if hit is not None:
        return _cache_hit(hit, t0)

    eng = plan._engine()
    if eng is None or not hasattr(eng, "reach"):
        return _done(error="routing engine unavailable",
                     code="engine_unavailable")
    try:
        res = await asyncio.wait_for(
            asyncio.get_running_loop().run_in_executor(
                plan._ENG_EXEC, _solve, eng, lat, lon, mode, budget),
            timeout=REACH_BUDGET_S)
    except asyncio.TimeoutError:
        return _done(error="reach solve timed out", code="timeout")
    except Exception as e:
        return _done(error=f"reach solve failed: {type(e).__name__}",
                     code="engine_unavailable")
    if not isinstance(res, dict):
        return _done(error="reach solve failed",
                     code="engine_unavailable")
    if res.get("code"):
        return _done(error=res.get("error") or "reach solve failed",
                     code=res["code"])
    if res.get("error"):
        return _done(error=res["error"], code="no_snap")
    resp.update(res)
    resp["took_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)
    try:
        # encode on its own pool — off _ENG_EXEC so a multi-MB veil's
        # serialization never occupies an engine worker slot, and off
        # the boot-warm-squatted shared default executor
        body = await asyncio.get_running_loop().run_in_executor(
            _ENCODE_EXEC, _json_bytes, resp)
    except Exception:
        return resp          # exotic value — fall back to the dict path
    _REACH_CACHE.put(cache_key, body)
    return Response(content=body, media_type="application/json",
                    headers={"x-alive-cache": "miss"})
