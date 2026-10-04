#!/usr/bin/env python3
"""Live legality audit — what the wire can actually prove.

Drives the 40-OD audit corpus through the live /v2/plan and checks
the two legality properties visible on the wire:

  * CONTAINMENT — no returned row (engine, router, or transit) routes
    a vertex outside the field bbox 76.8–77.9 x 28.2–28.95 when both
    endpoints sit inside it. Endpoints outside the bbox (one corpus
    OD) legitimately force an excursion — reported, not failed.
  * DETOUR — no engine row exceeds 1.6x the same-mode fastest router
    row's distance. The router row (OSRM/AWS freeflow) is the 'fast
    row' users compare against; a least-dose corridor >1.6x it is an
    absurd detour, not a choice.

Per-edge legality (one-ways, the 230 OSM turn restrictions, the 3,428
access overrides) is NOT observable from the wire — responses carry no
edge ids. It is proven on the shipped blob the server runs by
server/tests/test_legality_corpus.py + test_path_legality.py
(travelled-edge assertions over the same graph), and the live graph
is identified by /health build_sha.

    python3 tools/audit_live_legality.py [API_BASE]

Exit 0 always — a measurement harness. Anomalies sort worst-first.
"""
import json
import math
import sys
import urllib.request

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from audit_route_quality import ODS   # noqa: E402

API = (sys.argv[1] if len(sys.argv) > 1 else
       "http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com")

BBOX = (76.80, 28.20, 77.90, 28.95)     # lon0, lat0, lon1, lat1
BOUNDARY_EPS_DEG = 0.005                # ~500 m clip tolerance
DETOUR_MAX = 1.6


def _post_plan(a, b):
    body = {"from": {"lat": a[0], "lon": a[1]},
            "to": {"lat": b[0], "lon": b[1]}, "vehicle": "car"}
    req = urllib.request.Request(
        API + "/v2/plan", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read()), None
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read()), f"HTTP {e.code}"
        except Exception:
            return None, f"HTTP {e.code}"
    except Exception as e:
        return None, repr(e)


def _outside(coords):
    """worst out-of-bbox vertex: (max_excursion_deg, (lon, lat))."""
    x0, y0, x1, y1 = BBOX
    worst = 0.0
    where = None
    for c in coords or []:
        if not isinstance(c, (list, tuple)) or len(c) < 2:
            continue
        lon, lat = c[0], c[1]
        exc = max(x0 - lon, lon - x1, y0 - lat, lat - y1, 0.0)
        if exc > worst:
            worst, where = exc, (lon, lat)
    return worst, where


def _inside_bbox(p):
    return (BBOX[0] <= p[1] <= BBOX[2] and BBOX[1] <= p[0] <= BBOX[3])


def audit():
    anomalies = []                       # (severity, od, detail)
    n_rows = n_eng = n_checked = 0
    detour_worst = (0.0, "", "")
    contain_rows = contain_checked = 0
    per_od = []
    for name, a, b, cls in ODS:
        resp, err = _post_plan(a, b)
        if resp is None:
            anomalies.append(("severe", name, f"plan call failed: {err}"))
            per_od.append((name, "NO-RESPONSE"))
            continue
        opts = resp.get("options") or []
        if not opts:
            per_od.append((name, f"no options ({resp.get('error')})"))
            continue
        od_in = _inside_bbox(a) and _inside_bbox(b)
        router_min = {}
        for o in opts:
            if o.get("engine") == "alive_core-path":
                continue
            m = o.get("mode")
            d = o.get("distance_km")
            if m and isinstance(d, (int, float)):
                router_min[m] = min(router_min.get(m, 1e9), d)
        for o in opts:
            n_rows += 1
            coords = ((o.get("geometry") or {}).get("coordinates")) or []
            exc, where = _outside(coords)
            if exc > BOUNDARY_EPS_DEG:
                contain_checked += 1
                if od_in:
                    anomalies.append((
                        "severe", name,
                        f"{o.get('mode')}/{o.get('label')}: vertex "
                        f"{where} {exc * 111:.1f}km outside field bbox"))
                else:
                    per_od.append((name, "endpoint outside bbox — "
                                         "excursion expected"))
            else:
                contain_rows += 1
            if o.get("engine") != "alive_core-path":
                continue
            n_eng += 1
            base = router_min.get(o.get("mode"))
            if base and o.get("distance_km"):
                ratio = o["distance_km"] / base
                if ratio > detour_worst[0]:
                    detour_worst = (ratio, name, o.get("label"))
                if ratio > DETOUR_MAX:
                    anomalies.append((
                        "severe", name,
                        f"{o.get('mode')}/{o.get('label')}: "
                        f"{o['distance_km']:.1f}km = {ratio:.2f}x the "
                        f"same-mode fast row {base:.1f}km"))
                n_checked += 1
        per_od.append((name, f"{len(opts)} rows"))
    print(f"ODs: {len(ODS)}   rows checked: {n_rows} "
          f"(engine: {n_eng})")
    print(f"containment: {contain_rows} rows inside bbox; "
          f"{contain_checked} excursions")
    print(f"detour: {n_checked} engine rows vs same-mode fast rows; "
          f"worst ratio {detour_worst[0]:.2f}x "
          f"({detour_worst[1]} {detour_worst[2]})")
    print()
    for name, note in per_od:
        print(f"  {name:26s} {note}")
    print()
    if anomalies:
        print(f"ANOMALIES ({len(anomalies)}):")
        for sev, od, detail in anomalies:
            print(f"  [{sev}] {od}: {detail}")
    else:
        print("ANOMALIES: none")
    return anomalies


if __name__ == "__main__":
    audit()
