#!/usr/bin/env python3
"""Route-quality audit of the live ALive-108 API.

Drives a battery of diverse OD pairs through /v2/plan and scores the
response for the properties the routing engine promises:

  * engine rows present (graph coverage) and carrying engine_dose_ug
  * engine least-dose corridors actually lighter than the same mode's
    router (OSRM/AWS) row — compared on the SAME display integrator
    (raster dose.mid) so the check is apples-to-apples; engine_dose_ug
    is additionally compared but carries a known uplift asymmetry
    (priced per-edge uplift vs display's flat 1.0)
  * geometry sanity: endpoints near request, no teleports between
    consecutive vertices, declared distance consistent with polyline
  * via_names: real street strings, consecutive names deduped
  * alternatives non-identical: shared length fraction < 85%
  * engine_dose_ug / raster-mid agreement within an integrator bound

Anomalies are collected with a severity rank; the report prints a
per-OD table plus anomalies sorted worst-first. Pure stdlib.

    python3 tools/audit_route_quality.py [API_BASE]

Exit 0 always — this is a measurement harness, not a gate.
"""
import json
import math
import sys
import urllib.request

API = (sys.argv[1] if len(sys.argv) > 1 else
       "http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com")

# (name, from, to, class) — ~40 diverse ODs
ODS = [
    # intra-Delhi short <5km
    ("CP->IndiaGate", (28.6315, 77.2167), (28.6129, 77.2295), "short"),
    ("CP->KarolBagh", (28.6315, 77.2167), (28.6520, 77.1900), "short"),
    ("KarolBagh->RajendraPl", (28.6520, 77.1900), (28.6424, 77.1837),
     "short"),
    ("NehruPlace->Kalkaji", (28.5479, 77.2511), (28.5355, 77.2420),
     "short"),
    ("HauzKhas->GreenPark", (28.5494, 77.2001), (28.5583, 77.2030),
     "short"),
    ("Lajpat->DefenceCol", (28.5649, 77.2434), (28.5720, 77.2307),
     "short"),
    ("Rohini18->Pitampura", (28.7410, 77.1170), (28.7030, 77.1400),
     "short"),
    ("Dwarka6->Dwarka10", (28.5870, 77.0540), (28.5850, 77.0850),
     "short"),
    ("Saket->MalviyaNgr", (28.5245, 77.2066), (28.5350, 77.2100),
     "short"),
    ("ChandniChowk->Kashmere", (28.6506, 77.2303), (28.6674, 77.2273),
     "short"),
    # cross-town 15-30km
    ("CP->NehruPlace", (28.6315, 77.2167), (28.5479, 77.2511), "xtown"),
    ("CP->Dwarka21", (28.6315, 77.2167), (28.5530, 77.0580), "xtown"),
    ("Rohini18->CP", (28.7410, 77.1170), (28.6315, 77.2167), "xtown"),
    ("CP->Noida18", (28.6315, 77.2167), (28.5708, 77.3260), "xbound"),
    ("CP->CyberCity", (28.6315, 77.2167), (28.4949, 77.0894), "xbound"),
    ("Saket->Ggn29", (28.5245, 77.2066), (28.4595, 77.0266), "xbound"),
    ("CP->Faridabad12", (28.6315, 77.2167), (28.3860, 77.3100), "xbound"),
    ("CP->Vaishali", (28.6315, 77.2167), (28.6430, 77.3370), "xbound"),
    ("CP->Ggn56", (28.6315, 77.2167), (28.4180, 77.1080), "xbound"),
    ("KarolBagh->IGIT3", (28.6520, 77.1900), (28.5562, 77.1000), "xtown"),
    ("NorthCampus->NehruPlace", (28.6895, 77.2112), (28.5479, 77.2511),
     "xtown"),
    ("CP->Shahdara", (28.6315, 77.2167), (28.6712, 77.2935), "xtown"),
    ("CP->PunjabiBagh", (28.6315, 77.2167), (28.6690, 77.1330), "xtown"),
    ("CP->VasantKunj", (28.6315, 77.2167), (28.5360, 77.1500), "xtown"),
    ("CP->MayurVihar", (28.6315, 77.2167), (28.6050, 77.2950), "xtown"),
    # intra-satellite / cross-boundary local
    ("Ggn29->CyberCity", (28.4595, 77.0266), (28.4949, 77.0894), "xbound"),
    ("Noida18->NoidaCC", (28.5708, 77.3260), (28.5744, 77.3560),
     "xbound"),
    ("Noida62->CP", (28.6100, 77.3640), (28.6315, 77.2167), "xbound"),
    ("Ggn45->HauzKhas", (28.4590, 77.0550), (28.5494, 77.2001), "xbound"),
    ("NeelamChowk->NehruPlace", (28.4100, 77.2950), (28.5479, 77.2511),
     "xbound"),
    ("Vaishali->Noida62", (28.6430, 77.3370), (28.6100, 77.3640),
     "xbound"),
    ("MgRoad->Saket", (28.4790, 77.0840), (28.5245, 77.2066), "xbound"),
    ("Noida137->CP", (28.5170, 77.4090), (28.6315, 77.2167), "xbound"),
    # edge-of-field / outside (honest error expected on some)
    ("SohnaRd->CP", (28.4210, 77.0760), (28.6315, 77.2167), "edge"),
    ("CP->GgnBorder", (28.6315, 77.2167), (28.4900, 77.0400), "edge"),
    ("CP->NoidaEdge", (28.6315, 77.2167), (28.5800, 77.3600), "edge"),
    ("Rohini->BahadurgarhEdge", (28.7410, 77.1170), (28.7000, 76.9300),
     "edge"),
    ("CP->GreaterNoida", (28.6315, 77.2167), (28.4744, 77.5040),
     "edge"),
    ("CP->Bahadurgarh", (28.6315, 77.2167), (28.6800, 76.9200), "edge"),
    ("CP->Sonipat", (28.6315, 77.2167), (28.9931, 77.0151), "edge"),
]

_R = 6371000.0


def _hav(a, b):
    p1, p2 = math.radians(a[1]), math.radians(b[1])
    dp, dl = math.radians(b[1] - a[1]), math.radians(b[0] - a[0])
    h = (math.sin(dp / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return 2 * _R * math.asin(min(1.0, math.sqrt(h)))


def _polyline_len_m(coords):
    return sum(_hav(coords[i], coords[i + 1])
               for i in range(len(coords) - 1))


def _shared_frac(primary, other):
    """Fraction of `primary`'s path length whose midpoint sits within
    40 m of any vertex of `other`. Vertex-proximity approximation —
    graph polylines are dense, so it tracks shared length."""
    if not primary or not other:
        return 0.0
    shared = 0.0
    total = 0.0
    for i in range(len(primary) - 1):
        a, b = primary[i], primary[i + 1]
        seg = _hav(a, b)
        total += seg
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        for p in other:
            if abs(p[0] - mx) < 0.0005 and abs(p[1] - my) < 0.0005:
                if _hav((mx, my), p) < 40.0:
                    shared += seg
                    break
    return shared / total if total else 0.0


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


def audit():
    rows = []
    anomalies = []          # (severity, od, detail)
    for name, a, b, cls in ODS:
        resp, err = _post_plan(a, b)
        if resp is None:
            rows.append((name, cls, "NO-RESPONSE", {}))
            anomalies.append(("severe", name, f"plan call failed: {err}"))
            continue
        opts = resp.get("options") or []
        eng = [o for o in opts if o.get("engine") == "alive_core-path"]
        prim = [o for o in eng if o.get("alternative_index") in
                (None, 0)]
        alts = [o for o in eng if o.get("alternative_index")]
        d = {"n_opts": len(opts), "n_eng": len(eng),
             "resp_err": resp.get("error")}
        rows.append((name, cls, None, d))

        if resp.get("error"):
            if cls == "edge":
                continue      # honest coverage boundary
            anomalies.append(("severe", name,
                              f"in-area OD errored: {resp['error']}"))
            continue

        if not eng:
            anomalies.append(("severe", name,
                              "no engine rows on an in-area OD"))
            continue

        # --- per-row wire checks -------------------------------------
        for o in eng:
            ed = o.get("engine_dose_ug")
            if not isinstance(ed, (int, float)) or ed <= 0:
                anomalies.append(("severe", name,
                                  f"{o.get('mode')} alt="
                                  f"{o.get('alternative_index')}: "
                                  f"engine_dose_ug missing/invalid "
                                  f"({ed})"))
            dm = (o.get("dose") or {}).get("mid")
            if dm and ed:
                rat = ed / dm
                if rat > 1.4 or rat < 0.6:
                    anomalies.append(
                        ("moderate", name,
                         f"{o.get('mode')}: engine_dose {ed} vs raster "
                         f"mid {dm} (ratio {rat:.2f}) — integrators "
                         f"diverge beyond uplift+sampling"))

            geo = (o.get("geometry") or {}).get("coordinates") or []
            if len(geo) >= 2:
                if _hav(geo[0], (a[1], a[0])) > 1500:
                    anomalies.append(
                        ("moderate", name,
                         f"{o.get('mode')}: path starts "
                         f"{_hav(geo[0], (a[1], a[0])):.0f}m from origin"))
                if _hav(geo[-1], (b[1], b[0])) > 1500:
                    anomalies.append(
                        ("moderate", name,
                         f"{o.get('mode')}: path ends "
                         f"{_hav(geo[-1], (b[1], b[0])):.0f}m from dest"))
                mx = max(_hav(geo[i], geo[i + 1])
                         for i in range(len(geo) - 1))
                if mx > 3000:
                    anomalies.append(
                        ("severe", name,
                         f"{o.get('mode')}: teleport jump {mx:.0f}m "
                         f"between consecutive vertices"))
                plen = _polyline_len_m(geo) / 1000.0
                dk = o.get("distance_km")
                if dk and plen > 0:
                    rat = plen / dk
                    if rat < 0.7 or rat > 1.6:
                        anomalies.append(
                            ("moderate", name,
                             f"{o.get('mode')}: polyline {plen:.1f}km "
                             f"vs declared {dk}km"))

            vn = o.get("via_names") or []
            if not vn:
                anomalies.append(("low", name,
                                  f"{o.get('mode')}: via_names empty"))
            elif any(vn[i] == vn[i - 1] for i in range(1, len(vn))):
                anomalies.append(("low", name,
                                  f"{o.get('mode')}: via_names has "
                                  f"consecutive dupes {vn[:6]}"))

        # --- engine-vs-router dose (same raster integrator) ----------
        by_mode = {}
        for o in prim:
            by_mode.setdefault(o["mode"], {})["eng"] = o
        for o in opts:
            if o.get("engine"):
                continue
            m = o.get("mode")
            if m in by_mode:
                by_mode[m]["rtr"] = o
        for m, pair in by_mode.items():
            e, r = pair.get("eng"), pair.get("rtr")
            if not (e and r):
                continue
            em = (e.get("dose") or {}).get("mid")
            rm = (r.get("dose") or {}).get("mid")
            if em is None or rm is None or rm <= 0:
                continue
            delta = (em - rm) / rm
            d.setdefault("dose_delta", {})[m] = round(delta * 100, 1)
            if delta > 0.15:
                anomalies.append(
                    ("severe", name,
                     f"{m}: engine corridor {delta:+.0%} WORSE than "
                     f"router's on same raster ({em} vs {rm} µg) — "
                     f"least-dose claim fails"))
            elif delta > 0.05:
                anomalies.append(
                    ("moderate", name,
                     f"{m}: engine corridor {delta:+.0%} worse on "
                     f"raster ({em} vs {rm} µg) — check uplift "
                     f"pricing vs ambient"))

        # --- alternatives non-identical ------------------------------
        per_mode_prim = {}
        for o in prim:
            per_mode_prim.setdefault(o["mode"], o)
        for o in alts:
            p = per_mode_prim.get(o["mode"])
            if not p:
                continue
            sf = _shared_frac(
                (p.get("geometry") or {}).get("coordinates") or [],
                (o.get("geometry") or {}).get("coordinates") or [])
            if sf > 0.85:
                anomalies.append(
                    ("moderate", name,
                     f"{o['mode']} alt{o.get('alternative_index')}: "
                     f"{sf:.0%} shared length with primary — not a "
                     f"real corridor alternative"))

    # ---------------- report -----------------------------------------
    print(f"\n{'OD':<26} {'cls':<7} {'opts':>4} {'eng':>3}  "
          f"dose-delta% per mode (engine raster-mid vs router)")
    for name, cls, err, d in rows:
        if err:
            print(f"{name:<26} {cls:<7} {err}")
            continue
        deltas = d.get("dose_delta") or {}
        ds = " ".join(f"{m}:{v:+.0f}" for m, v in deltas.items())
        tag = f"ERR:{d['resp_err']}" if d.get("resp_err") else ""
        print(f"{name:<26} {cls:<7} {d['n_opts']:>4} {d['n_eng']:>3}  "
              f"{ds} {tag}")

    sev_rank = {"severe": 0, "moderate": 1, "low": 2}
    anomalies.sort(key=lambda a: (sev_rank[a[0]], a[1]))
    print(f"\n=== {len(anomalies)} anomalies ===")
    for sev, od, msg in anomalies:
        print(f"[{sev:<8}] {od:<26} {msg}")


if __name__ == "__main__":
    audit()
