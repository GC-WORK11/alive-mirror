#!/usr/bin/env python3
"""Pre-heat a fresh Fargate task for demo day.

A cold task serves /health immediately but three lazy layers load on
first touch: the PM2.5 field (request-driven FIELD.refresh — otherwise
the engine reweight loop logs "field serves no reads"), the GTFS feeds
(now also warmed in _lifespan), and the priced engine raster (graph
load ~36 s + first reweight sweep). This script walks them all with
real requests and reports when each layer turns warm.

What it does, in order — every call is a real endpoint, no fake data:
  1. GET /health            -> build_sha + engine/field status
  2. GET /aqi, /grid        -> kicks the field refresh + raster
  3. POST /v2/plan x N ODs  -> real NCR origin/dests until a plan row
                               carries steps_source "endpoints" (i.e.
                               the priced engine contributed alts)
  4. GET /reports, /v2/city -> admin/community surfaces
  5. GET /grid?h=12, /v2/day, /v2/reach (walk@25/50, car@25),
     /v2/outlook, /v2/why, /v2/skill, /v2/archive, /community
                             -> the dosimeter surfaces + forecast scrub
                             -> the city page's reach veil combos +
                                the why/skill/archive demo reads
  6. GET /tiles/health      -> self-hosted Delhi basemap archive check

Usage: python3 tools/warm_task.py [BASE_URL] [--timeout 300] [--ods 12]
Exit 0 when the engine is serving rows; 1 on timeout.
"""
import json
import sys
import time
import urllib.request

BASE = "http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com"

# A spread of real NCR ODs — short hops, cross-town, and boundary legs
# taken from the audit set so the warm paths are representative.
WARM_ODS = [
    ("CP->IndiaGate", (28.6315, 77.2167), (28.6129, 77.2295)),
    ("NehruPlace->Kalkaji", (28.5479, 77.2511), (28.5355, 77.2420)),
    ("Dwarka6->Dwarka10", (28.5870, 77.0540), (28.5850, 77.0850)),
    ("Rohini18->Pitampura", (28.7410, 77.1170), (28.7030, 77.1400)),
    ("CP->NoidaSec18", (28.6315, 77.2167), (28.5708, 77.3260)),
    ("KarolBagh->Gurgaon", (28.6520, 77.1900), (28.4595, 77.0266)),
    ("Connaught->Faridabad", (28.6315, 77.2167), (28.4089, 77.3178)),
    ("DU->Ghaziabad", (28.6862, 77.2070), (28.6692, 77.4538)),
    ("Saket->IGI", (28.5244, 77.2066), (28.5562, 77.0990)),
    ("LaxmiNgr->PunjabiBagh", (28.6304, 77.2773), (28.6743, 77.1340)),
    ("Chandni->Okhla", (28.6500, 77.2300), (28.5300, 77.2900)),
    ("KashGate->Nizamuddin", (28.6667, 77.2280), (28.5880, 77.2540)),
]


def _get(path, timeout=30):
    req = urllib.request.Request(BASE + path)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read()), None
    except Exception as e:
        return None, repr(e)


def _post_plan(a, b):
    body = {"from": {"lat": a[0], "lon": a[1]},
            "to": {"lat": b[0], "lon": b[1]}, "vehicle": "car"}
    req = urllib.request.Request(
        BASE + "/v2/plan", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read()), None
    except Exception as e:
        return None, repr(e)


def _engine_rows(resp):
    """Count plan rows produced by the priced engine (endpoint-snapped
    geometry = the C++ pathfinder's own routes)."""
    n = 0
    for o in (resp or {}).get("options", []):
        if o.get("steps_source") == "endpoints" \
                or "least-smoke" in (o.get("label") or ""):
            n += 1
    return n


def _transit_rows(resp):
    """Count plan rows backed by real GTFS legs. The first cold plan
    could silently ship zero of these while road rows landed — a warm
    report that never counts them can't notice transit is dead."""
    n = 0
    for o in (resp or {}).get("options", []):
        if o.get("steps_source") == "gtfs":
            n += 1
    return n


def main():
    global BASE
    args = [a for a in sys.argv[1:]]
    timeout = 300
    n_ods = len(WARM_ODS)
    if args and not args[0].startswith("-"):
        BASE = args.pop(0).rstrip("/")
    if "--timeout" in args:
        timeout = int(args[args.index("--timeout") + 1])
    if "--ods" in args:
        n_ods = int(args[args.index("--ods") + 1])

    t0 = time.time()
    print(f"[{time.time()-t0:6.1f}s] base = {BASE}")

    # 1. /health
    h, err = _get("/health")
    if h:
        print(f"[{time.time()-t0:6.1f}s] /health ok — build "
              f"{h.get('build_sha') or h.get('build')}, "
              f"field: {(h.get('field') or {}) if isinstance(h.get('field'), dict) else h.get('field')}")
    else:
        print(f"[{time.time()-t0:6.1f}s] /health {err}")

    # 2. kick the field + raster
    _, e1 = _get("/aqi?lat=28.6139&lon=77.2090")
    _, e2 = _get("/grid")
    print(f"[{time.time()-t0:6.1f}s] /aqi {'ok' if not e1 else e1} · "
          f"/grid {'ok' if not e2 else e2}")

    # 3. plan calls over real ODs until the engine contributes rows
    engine_at = None
    transit_seen = 0
    for i, (label, a, b) in enumerate(WARM_ODS[:n_ods]):
        if time.time() - t0 > timeout:
            break
        ts = time.time()
        resp, err = _post_plan(a, b)
        n = _engine_rows(resp)
        t = _transit_rows(resp)
        transit_seen += 1 if t else 0
        opts = len((resp or {}).get("options", []))
        print(f"[{time.time()-t0:6.1f}s] /v2/plan {label:<22} "
              f"{time.time()-ts:5.1f}s rows={opts} engine_rows={n} "
              f"transit_rows={t} "
              f"{err or ''}")
        if n > 0:
            engine_at = time.time() - t0
            break

    # retry loop: engine may still be repricing — plans return router
    # rows honestly in the meantime (never a fabricated engine row)
    while engine_at is None and time.time() - t0 < timeout:
        time.sleep(10)
        resp, err = _post_plan(*WARM_ODS[0][1:3])
        n = _engine_rows(resp)
        t = _transit_rows(resp)
        print(f"[{time.time()-t0:6.1f}s] retry {WARM_ODS[0][0]:<22} "
              f"rows={len((resp or {}).get('options', []))} "
              f"engine_rows={n} transit_rows={t} {err or ''}")
        if n > 0:
            engine_at = time.time() - t0

    # 4. admin/community surfaces (aggregate-only endpoints)
    _, e3 = _get("/reports")
    _, e4 = _get("/v2/city")
    print(f"[{time.time()-t0:6.1f}s] /reports {'ok' if not e3 else e3} · "
          f"/v2/city {'ok' if not e4 else e4}")

    # 5. dosimeter surfaces + forecast scrub — the T-30 checklist used to
    # warm these by hand; a cold /v2/reach honestly answers
    # engine_unavailable, so run these only after the plan arm is warm.
    lat, lon = WARM_ODS[0][1]
    for label, path in [
            ("grid?h=12", "/grid?h=12"),
            ("v2/day", f"/v2/day?lat={lat}&lon={lon}"),
            ("v2/reach", f"/v2/reach?lat={lat}&lon={lon}"
                         f"&mode=walk&budget_ug=25"),
            # the city page's mode x budget pills — car@25 settled
            # 866k edges live (~1.3 s solve + a 3.5 MB veil encode on
            # a fresh cache); warm the pairs a demo tap is likeliest
            # to hit
            ("reach w@50", f"/v2/reach?lat={lat}&lon={lon}"
                           f"&mode=walk&budget_ug=50"),
            ("reach c@25", f"/v2/reach?lat={lat}&lon={lon}"
                           f"&mode=car&budget_ug=25"),
            ("v2/outlook", f"/v2/outlook?lat={lat}&lon={lon}"),
            ("v2/why", f"/v2/why?lat={lat}&lon={lon}"),
            ("v2/skill", "/v2/skill"),
            ("v2/archive", "/v2/archive"),
            ("community", "/community")]:
        ts = time.time()
        body, e = _get(path, timeout=60)
        note = e or ""
        if not e and isinstance(body, dict):
            note = body.get("error") or body.get("code") or "ok"
        print(f"[{time.time()-t0:6.1f}s] /{label:<12} "
              f"{note} ({time.time()-ts:.1f}s)")

    # 6. vector-tiles lane — the geo mirror pulls delhi.pmtiles at boot,
    # so /tiles/health should already report the archive; a 503 here
    # means the S3 artifact is missing (basemap falls back to hosted
    # tiles — the map still renders, just not ours).
    tj, e5 = _get("/tiles/health")
    if tj and tj.get("ok"):
        print(f"[{time.time()-t0:6.1f}s] /tiles/health ok — "
              f"{tj.get('size_mb')} MB z{tj.get('zoom')} "
              f"{tj.get('tile_entries')} entries")
    else:
        print(f"[{time.time()-t0:6.1f}s] /tiles/health {e5 or tj} "
              f"(app falls back to hosted OpenFreeMap tiles)")

    if transit_seen == 0 and engine_at is not None:
        # not fatal — honest geography means some ODs have no GTFS leg —
        # but zero across the whole audit set reads exactly like the
        # first-plan wart, so say it out loud.
        print("NOTE: no GTFS transit rows on any plan OD — if these ODs "
              "served transit before, the transit arm is likely starved")
    if engine_at is not None:
        print(f"WARM: priced engine serving after {engine_at:.0f}s · "
              f"transit rows on {transit_seen} plan OD(s)")
        return 0
    print(f"TIMEOUT: engine rows never appeared within {timeout}s — "
          f"check /ecs/alive108 logs for the reweight loop")
    return 1


if __name__ == "__main__":
    sys.exit(main())
