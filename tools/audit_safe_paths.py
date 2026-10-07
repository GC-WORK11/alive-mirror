#!/usr/bin/env python3
"""Safe-path audit for /v2/plan — route-segments lane.

Owner demand: 'routes should be safe, a regular route — not into jungle
or a route that shouldn't exist.' This audit measures whether every
road-mode option's geometry actually lies on real roads, using the
engine's own street graph as ground truth (server/data/route_graph.bin
— the same northern-zone OSM extract that prices every engine row):
1,070,459 edges / 2,324,796 polyline points covering
bbox [76.68,28.08 .. 78.02,29.07].

Method
------
For each OD pair, POST /v2/plan (local TestClient by default, --base
for a live API). For every option with a LineString geometry:

  * sample the polyline at ~250 m steps (same cadence exposure.dose
    prices)
  * for each sample, compute distance to the nearest graph-edge
    polyline (grid-bucketed edge index, ring search to ~1 km)
  * endpoints are reported separately — an endpoint up to the engine's
    1.5 km snap radius off a road is a declared snap, not a bad path

Verdict classes (per the lane mandate)
--------------------------------------
  P0       a road-mode option sustains >50 m off any graph road for
           >= 500 m (two+ consecutive bad samples) or has any interior
           sample >200 m off-road inside the graph's own bbox
  PASS     all interior samples within 50 m of a road
  DECLARED synthetic / model geometry that names itself as such
           (metro/bus ride legs are rail — off-road by design; the
           option must flag it via approximate/transit_source/legs)
  HONEST   destination outside the field/graph: the response must say
           so (error, reaches_destination=false, low confidence) — an
           outside-coverage OD answered with silent confidence fails

Transit legs are checked per-leg: walk legs against the road graph
(they should hug streets), ride legs recorded as DECLARED rail.

Writes docs/lanes/safe-path-audit.json + a markdown table to stdout.
Exit 0 always — a measurement harness, not a gate.

    PYTHONPATH=server:server/core/build312 python3 tools/audit_safe_paths.py
    PYTHONPATH=server:server/core/build312 python3 tools/audit_safe_paths.py \
        --base http://alive108-...amazonaws.com
"""
import argparse
import collections
import json
import math
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))

R_M = 6371000.0
SAMPLE_STEP_M = 250.0      # matches exposure.segment_samples cadence
OFF_ROAD_M = 50.0          # >50 m from any road = suspicious
SUSTAIN_M = 500.0          # sustained off-road length that makes a P0
HARD_MISS_M = 200.0        # single interior point this far = P0 outright
SNAP_M = 1500.0            # routegraph.SNAP_RADIUS_M — declared snap cap
CELL = 0.002               # ~210 m grid cells for the edge index
MAX_RING = 5               # ring search reach ≈ 1 km

ROAD_MODES = {"car", "car_open", "cab", "auto", "bike", "scooter",
              "bus", "cycle", "walk"}

# (name, from, to, class) — in-area pairs must route on real roads;
# 'edge'/'outside' pairs exercise the coverage-honesty ladder.
ODS = [
    # ---- intra-Delhi -------------------------------------------------
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
    # ---- cross-town --------------------------------------------------
    ("CP->NehruPlace", (28.6315, 77.2167), (28.5479, 77.2511), "xtown"),
    ("CP->Dwarka21", (28.6315, 77.2167), (28.5530, 77.0580), "xtown"),
    ("Rohini18->CP", (28.7410, 77.1170), (28.6315, 77.2167), "xtown"),
    ("NorthCampus->NehruPlace", (28.6895, 77.2112), (28.5479, 77.2511),
     "xtown"),
    ("CP->Shahdara", (28.6315, 77.2167), (28.6712, 77.2935), "xtown"),
    ("CP->PunjabiBagh", (28.6315, 77.2167), (28.6690, 77.1330), "xtown"),
    ("CP->VasantKunj", (28.6315, 77.2167), (28.5360, 77.1500), "xtown"),
    ("CP->MayurVihar", (28.6315, 77.2167), (28.6050, 77.2950), "xtown"),
    ("KarolBagh->IGIT3", (28.6520, 77.1900), (28.5562, 77.1000),
     "xtown"),
    # ---- cross-boundary (Delhi <-> satellites) -----------------------
    ("CP->Noida18", (28.6315, 77.2167), (28.5708, 77.3260), "xbound"),
    ("CP->CyberCity", (28.6315, 77.2167), (28.4949, 77.0894), "xbound"),
    ("Saket->Ggn29", (28.5245, 77.2066), (28.4595, 77.0266), "xbound"),
    ("CP->Faridabad12", (28.6315, 77.2167), (28.3860, 77.3100), "xbound"),
    ("CP->Vaishali", (28.6315, 77.2167), (28.6430, 77.3370), "xbound"),
    ("CP->Ggn56", (28.6315, 77.2167), (28.4180, 77.1080), "xbound"),
    ("Ggn29->CyberCity", (28.4595, 77.0266), (28.4949, 77.0894),
     "xbound"),
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
    # ---- task-named fringes ------------------------------------------
    ("IGIT3->Noida18", (28.5562, 77.1000), (28.5708, 77.3260), "xbound"),
    ("AnandVihar->Indirapuram", (28.6468, 77.3161), (28.6420, 77.3570),
     "xbound"),
    ("Noida18->Faridabad21", (28.5708, 77.3260), (28.4583, 77.2845),
     "xbound"),
    ("Rohini->Kundli", (28.7410, 77.1170), (28.8830, 77.1155), "edge"),
    ("Ggn29->Sohna", (28.4595, 77.0266), (28.2470, 77.0654), "edge"),
    # ---- edge-of-field / outside -------------------------------------
    ("SohnaRd->CP", (28.4210, 77.0760), (28.6315, 77.2167), "edge"),
    ("CP->GgnBorder", (28.6315, 77.2167), (28.4900, 77.0400), "edge"),
    ("CP->NoidaEdge", (28.6315, 77.2167), (28.5800, 77.3600), "edge"),
    ("Rohini->BahadurgarhEdge", (28.7410, 77.1170), (28.7000, 76.9300),
     "edge"),
    ("CP->GreaterNoida", (28.6315, 77.2167), (28.4744, 77.5040), "edge"),
    ("CP->Bahadurgarh", (28.6315, 77.2167), (28.6800, 76.9200), "edge"),
    ("CP->Sonipat", (28.6315, 77.2167), (28.9931, 77.0151), "outside"),
    ("CP->Manesar", (28.6315, 77.2167), (28.3545, 76.9389), "edge"),
    ("CP->Panipat", (28.6315, 77.2167), (29.3909, 76.9635), "outside"),
    ("CP->Meerut", (28.6315, 77.2167), (28.9845, 77.7064), "outside"),
]


def _hav(a, b):
    p1, p2 = math.radians(a[1]), math.radians(b[1])
    dp, dl = math.radians(b[1] - a[1]), math.radians(b[0] - a[0])
    h = math.sin(dp / 2) ** 2 \
        + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_M * math.asin(min(1.0, math.sqrt(h)))


# --- road index --------------------------------------------------------

class RoadIndex:
    """Grid-bucketed index over the route graph's edge polylines.

    Each edge id is registered in every cell its polyline touches —
    walked at <= CELL/2 steps so a segment can't jump a cell. A query
    ring-expands cells until candidates appear, decodes each candidate
    edge, and returns the true point-to-polyline minimum."""

    def __init__(self, graph):
        self.g = graph
        self.cells = collections.defaultdict(set)
        self._build()

    @staticmethod
    def _cell(lon, lat):
        return (int(lon / CELL), int(lat / CELL))

    def _build(self):
        g = self.g
        t0 = None
        for i in range(g.n_edges):
            pts = g.edge_pts(i)
            for j in range(1, len(pts)):
                ax, ay = pts[j - 1]
                bx, by = pts[j]
                seg_len = max(abs(bx - ax), abs(by - ay))
                steps = max(1, int(seg_len / (CELL / 2.0)) + 1)
                for k in range(steps + 1):
                    f = k / steps
                    self.cells[self._cell(ax + (bx - ax) * f,
                                          ay + (by - ay) * f)].add(i)
        self.n_indexed = len(self.cells)

    def _pt_seg_m(self, p, a, b, coslat):
        """Point-to-segment distance (m) in a local flat projection."""
        px, py = p[0] * coslat, p[1]
        ax, ay = a[0] * coslat, a[1]
        bx, by = b[0] * coslat, b[1]
        dx, dy = bx - ax, by - ay
        if dx == 0 and dy == 0:
            t = 0.0
        else:
            t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
            t = max(0.0, min(1.0, t))
        ex = (ax + t * dx - px) * 111320.0
        ey = (ay + t * dy - py) * 110540.0
        return math.hypot(ex, ey)

    def nearest_m(self, lon, lat):
        """Min distance (m) to any indexed edge polyline, or None when
        no edge lies within ~MAX_RING cells (~1 km).

        Rings expand until every cell that could hold an insertion of
        a CLOSER edge has been examined: polyline insertion points are
        ≤ CELL/2 (~105 m) apart, so an edge whose nearest point is `b`
        metres from the query has an insertion within ~b+160 m. The
        scan therefore continues while the ring's inner reach is under
        best_so_far + slack — a first-ring hit must not shadow a nearer
        edge registered only in an outer ring."""
        cx, cy = self._cell(lon, lat)
        coslat = math.cos(math.radians(lat))
        best = None
        ring = 0
        while ring <= MAX_RING:
            cand = set()
            for dx in range(-ring, ring + 1):
                for dy in range(-ring, ring + 1):
                    if max(abs(dx), abs(dy)) != ring:
                        continue
                    cand |= self.cells.get((cx + dx, cy + dy), set())
            for ei in cand:
                pts = self.g.edge_pts(ei)
                for j in range(1, len(pts)):
                    d = self._pt_seg_m((lon, lat), pts[j - 1], pts[j],
                                       coslat)
                    if best is None or d < best:
                        best = d
            ring += 1
            if best is not None:
                # degrees beyond which no insertion of a closer edge
                # can live (metric margin ~160 m + one cell)
                reach_deg = (best + 160.0) / 111320.0 + CELL
                if ring * CELL > reach_deg:
                    break
        return best


def _sample_250m(coords):
    """Polyline vertices at ~SAMPLE_STEP_M cadence — mirrors
    exposure.segment_samples (vertex-aligned, last vertex always)."""
    if len(coords) < 2:
        return coords[:]
    out = [coords[0]]
    acc = 0.0
    for i in range(1, len(coords)):
        acc += _hav(coords[i - 1], coords[i])
        if acc >= SAMPLE_STEP_M:
            out.append(coords[i])
            acc = 0.0
    if out[-1] is not coords[-1] and coords[-1] != out[-1]:
        out.append(coords[-1])
    return out


def _in_graph_bbox(pt, bbox):
    """bbox is the route graph's micro-degree [minlon,minlat,maxlon,
    maxlat]; a bad sample outside it is the coverage edge doing its
    job, not a phantom road."""
    return (bbox[0] <= int(pt[0] * 1e6) <= bbox[2]
            and bbox[1] <= int(pt[1] * 1e6) <= bbox[3])


def _audit_geom(road_idx, coords, snap_allowed=True):
    """Sample a road-mode polyline; return distance stats + worst run."""
    pts = _sample_250m(coords)
    if len(pts) < 3:
        return None
    d = []
    for p in pts:
        d.append(road_idx.nearest_m(p[0], p[1]))
    interior = d[1:-1]
    bad_run = run = 0
    bads = 0
    worst = 0.0
    first_big = None
    bad_pts = []
    for i, x in enumerate(d):
        edge_zone = snap_allowed and (i == 0 or i == len(d) - 1)
        if x is None or x > OFF_ROAD_M:
            if not edge_zone:
                bads += 1
                run += 1
                bad_run = max(bad_run, run)
                bad_pts.append(pts[i])
                if x is not None:
                    worst = max(worst, x)
                    if first_big is None:
                        first_big = (i, x)
        else:
            run = 0
            worst = max(worst, x)
    return {"n": len(d), "bad": bads, "max_off_m": round(worst, 1),
            "sustain_m": int(bad_run * SAMPLE_STEP_M),
            "snap_from_m": round(d[0], 1) if d[0] is not None else None,
            "snap_to_m": round(d[-1], 1) if d[-1] is not None else None,
            "bad_pts": bad_pts,
            "first_bad": (first_big[0], round(first_big[1], 1))
            if first_big else None}


def _post_plan(base, a, b):
    body = {"from": {"lat": a[0], "lon": a[1]},
            "to": {"lat": b[0], "lon": b[1]}, "vehicle": "car"}
    if base:
        req = urllib.request.Request(
            base + "/v2/plan", data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read()), None
        except urllib.error.HTTPError as e:
            try:
                return json.loads(e.read()), f"HTTP {e.code}"
            except Exception:
                return None, f"HTTP {e.code}"
        except Exception as e:
            return None, repr(e)
    return _local_plan(a, b)


_LOCAL_CLIENT = None


def _local_plan(a, b):
    global _LOCAL_CLIENT
    if _LOCAL_CLIENT is None:
        os.environ.setdefault("ALIVE_RATE_LIMIT", "0")
        os.environ.setdefault("ALIVE_INGEST_IN_APP", "0")
        os.environ.setdefault("ALIVE_ARCHIVE", "0")
        from fastapi.testclient import TestClient
        import main
        _LOCAL_CLIENT = TestClient(main.app)
    r = _LOCAL_CLIENT.post("/v2/plan", json={
        "from": {"lat": a[0], "lon": a[1]},
        "to": {"lat": b[0], "lon": b[1]}, "vehicle": "car"})
    try:
        return r.json(), (None if r.status_code == 200
                          else f"HTTP {r.status_code}")
    except Exception:
        return None, f"HTTP {r.status_code}"


def _segments_sane(opt):
    """Route-segments contract sanity (shipped shape, commit c152760):
    spans, when present, tile the option path contiguously — fracs
    0→1 and consecutive spans share a boundary vertex."""
    segs = opt.get("segments")
    if not segs:
        return None
    coords = (opt.get("geometry") or {}).get("coordinates") or []
    if not coords:
        return None
    try:
        ok = (segs[0]["start_frac"] == 0
              and abs(segs[-1]["end_frac"] - 1.0) < 1e-6
              and all(
                  abs(a["end_frac"] - b["start_frac"]) < 1e-6
                  and (a["geometry"]["coordinates"][-1]
                       == b["geometry"]["coordinates"][0])
                  for a, b in zip(segs, segs[1:])))
        return ok
    except (KeyError, IndexError, TypeError):
        return False


def audit(base=None):
    import routegraph
    print("loading route graph…", flush=True)
    g = routegraph.RouteGraph(routegraph.load_blob())
    road_idx = RoadIndex(g)
    print(f"indexed {g.n_edges} edges into {road_idx.n_indexed} cells",
          flush=True)

    rows, anomalies = [], []
    for name, a, b, cls in ODS:
        resp, err = _post_plan(base, a, b)
        if resp is None:
            rows.append({"od": name, "class": cls, "verdict": "NO-RESPONSE"})
            anomalies.append(("severe", name, f"plan failed: {err}"))
            print(f"{name:28s} {cls:8s} NO-RESPONSE {err}", flush=True)
            continue
        opts = resp.get("options") or []
        rec = {"od": name, "class": cls, "n_opts": len(opts),
               "error": resp.get("error"), "options": []}
        worst = "PASS"
        if resp.get("error"):
            # coverage honesty: an erroring OD is HONEST iff it is a
            # genuinely-outside pair; in-area errors are anomalies
            if cls == "outside" or cls == "edge":
                rec["verdict"] = "HONEST-ERR"
            else:
                rec["verdict"] = "P0"
                anomalies.append(("severe", name,
                                  f"in-area OD errored: {resp['error']}"))
            rows.append(rec)
            print(f"{name:28s} {cls:8s} {rec['verdict']} err={resp['error']}",
                  flush=True)
            continue

        for o in opts:
            mode = o.get("mode")
            eng = bool(o.get("engine"))
            geom = (o.get("geometry") or {})
            coords = geom.get("coordinates") or []
            dose = o.get("dose") or {}
            orow = {"mode": mode, "engine": eng,
                    "router": o.get("router_backend"),
                    "alt": o.get("alternative_index"),
                    "n_coords": len(coords),
                    "conf": dose.get("confidence"),
                    "cov": dose.get("coverage"),
                    "reaches": o.get("reaches_destination"),
                    "starts": o.get("starts_at_origin"),
                    "seg_ok": _segments_sane(o)}
            if o.get("legs"):
                # transit option: audit per-leg — walk legs vs roads,
                # ride legs are declared rail (off-road by design)
                legs = o["legs"]
                lg = []
                for li, leg in enumerate(legs):
                    lcoords = ((leg.get("geometry") or {})
                               .get("coordinates") or [])
                    if leg.get("type") == "walk" and len(lcoords) >= 2:
                        lg.append((li, "walk",
                                   _audit_geom(road_idx, lcoords)))
                    else:
                        lg.append((li, leg.get("type"), "rail"))
                orow["legs_audit"] = lg
                orow["verdict"] = "DECLARED" if (
                    o.get("transit_source") or o.get("approximate")
                    or o.get("approximation")) else "PASS"
            elif mode in ROAD_MODES and geom.get("type") == "LineString" \
                    and len(coords) >= 2:
                m = _audit_geom(road_idx, coords)
                orow.update(m or {})
                if m is None:
                    orow["verdict"] = "PASS"
                elif m["sustain_m"] >= SUSTAIN_M \
                        or (m["max_off_m"] or 0) > HARD_MISS_M:
                    # off-network only counts as a bad ROAD inside the
                    # commute-shed — beyond the graph bbox the route is
                    # on roads the graph simply never claims (the pair
                    # verdict still judges whether it answered honestly)
                    inside = [p for p in m.get("bad_pts") or []
                              if _in_graph_bbox(p, g.bbox)]
                    if inside:
                        orow["verdict"] = "P0"
                        anomalies.append(
                            ("severe", name,
                             f"{mode}{'/eng' if eng else '/' + str(o.get('router_backend'))}"
                             f" off-road: sustain {m['sustain_m']}m "
                             f"max {m['max_off_m']}m n={m['n']} "
                             f"first_bad={m['first_bad']}"))
                    else:
                        orow["verdict"] = "COVERAGE"
                        anomalies.append(
                            ("note", name,
                             f"{mode}{'/eng' if eng else '/' + str(o.get('router_backend'))}"
                             f" leaves graph bbox: sustain "
                             f"{m['sustain_m']}m off-network beyond "
                             f"the commute-shed (expected — honesty "
                             f"judged at pair level)"))
                elif m["bad"]:
                    orow["verdict"] = "WARN"
                    anomalies.append(
                        ("moderate", name,
                         f"{mode}{'/eng' if eng else '/' + str(o.get('router_backend'))}"
                         f" {m['bad']} samples >50m off-road "
                         f"(max {m['max_off_m']}m)"))
                else:
                    orow["verdict"] = "PASS"
                worst = ("P0" if orow["verdict"] == "P0"
                         else "WARN" if orow["verdict"] == "WARN"
                         and worst != "P0" else worst)
            else:
                orow["verdict"] = "DECLARED"
            if orow.get("seg_ok") is False:
                anomalies.append(("severe", name,
                                  f"{mode}: segments do not tile the "
                                  f"coordinate list"))
            rec["options"].append(orow)

        # coverage honesty for the pair as a whole — an edge/outside
        # OD answered at full confidence with no declared gap is the
        # 'confidently wrong' failure; a declared gap counts honest:
        # truncation flags, dropped confidence, coverage <0.9, or
        # segment rows with null reads (uncovered stretches declared)
        if cls in ("edge", "outside"):
            flags = [x for x in rec["options"]
                     if x.get("reaches") is False
                     or x.get("starts") is False
                     or x.get("conf") in ("low", "none", "medium")
                     or (isinstance(x.get("cov"), (int, float))
                         and x["cov"] < 0.9)]
            rec["verdict"] = ("HONEST" if (flags or not opts)
                              else "PASS")
        else:
            rec["verdict"] = worst
        rows.append(rec)
        summary = (f"{name:28s} {cls:8s} {rec['verdict']:10s} "
                   f"opts={len(opts)}")
        p0 = [x for x in rec["options"] if x.get("verdict") == "P0"]
        if p0:
            summary += f" P0={[(x['mode'], x['sustain_m']) for x in p0]}"
        print(summary, flush=True)
    return rows, anomalies


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=None,
                    help="live API base; default = local TestClient")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    rows, anomalies = audit(args.base)
    sev_rank = {"severe": 0, "moderate": 1, "low": 2}
    anomalies.sort(key=lambda t: sev_rank.get(t[0], 3))
    print("\n=== anomalies (worst first) ===")
    for s, od, msg in anomalies:
        print(f"[{s}] {od}: {msg}")
    p0 = [r for r in rows if r.get("verdict") == "P0"
          or any(o.get("verdict") == "P0" for o in r.get("options", []))]
    print(f"\n{len(rows)} ODs audited | P0 pairs: {len(p0)}")
    out = args.json or os.path.join(ROOT, "docs", "lanes",
                                    "safe-path-audit.json")
    with open(out, "w") as fh:
        json.dump({"ods": rows, "anomalies": anomalies}, fh, indent=1)
    print("wrote", out)


if __name__ == "__main__":
    main()
