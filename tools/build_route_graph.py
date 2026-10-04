#!/usr/bin/env python3
"""Build the NCR route graph for alive_core's exposure pathfinder.

One-time offline step: reads the OSM zone extracts under
server/data/corpus/dl/*.osm.pbf (northern-zone for Delhi/Haryana +
central-zone for the UP side — Geofabrik's zone edge cuts through NCR,
so Ghaziabad/GB Nagar only exist in the second file), keeps highway=*
ways inside the dose-field bbox + margin, collapses degree-2 node chains
into junction-to-junction edges with full polyline geometry, and emits
a compact gzipped blob the C++ engine (and the Python parity twin) loads
at boot. Ways that exist in both extracts' overlap are deduped on
OSM way id.

Output: server/data/route_graph.bin.gz — gzipped packed binary:
  header  : magic "ARG1" | u32 n_nodes | u32 n_edges | u32 n_names |
            u32 n_pts | u32 bbox×4 (i32 microdeg)
  nodes   : i32 lon_e6, i32 lat_e6  (8B each; osm ids dropped post-build)
  names   : u16 len + utf-8 bytes, ×n_names
  edges   : u32 u | u32 v | f32 len_m | u32 pts_off | u16 pts_n |
            u8 hw | i8 oneway(-1/0/1) | u8 speed_kmh | u32 name_idx |
            u8 in_field_flag  (pad u8 to keep the 27B layout explicit)
  pts     : per-edge polyline, i16 microdeg deltas from the previous
            point; first point absolute i32 pair (deg×1e6)
  meta.json sidecar: {pbf, pbf_sha256, bbox, counts}

Run: tools/corpus-venv/bin/python tools/build_route_graph.py
"""
import gzip
import hashlib
import json
import math
import os
import struct
import sys
from collections import defaultdict

import osmium

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PBF_DIR = os.path.join(ROOT, "server", "data", "corpus", "dl")
PBF = os.path.join(PBF_DIR, "northern-zone-latest.osm.pbf")
PBFS = sorted(
    os.path.join(PBF_DIR, f) for f in os.listdir(PBF_DIR)
    if f.endswith(".osm.pbf")) or [PBF]
OUT = os.path.join(ROOT, "server", "data", "route_graph.bin.gz")
META = os.path.join(ROOT, "server", "data", "route_graph.meta.json")
FIELD_BBOX = (76.80, 28.20, 77.90, 28.95)   # dose field — reweight scope
RDP_TOL_M = 12.0                            # polyline simplify tolerance

# dose-field bbox (76.80,28.20,77.90,28.95) + ~0.12 deg margin so a
# least-dose path can use border roads without hitting a graph wall.
MINLON, MINLAT, MAXLON, MAXLAT = 76.68, 28.08, 78.02, 29.07

HW_CODES = {
    "motorway": 0, "motorway_link": 1, "trunk": 2, "trunk_link": 3,
    "primary": 4, "primary_link": 5, "secondary": 6, "secondary_link": 7,
    "tertiary": 8, "tertiary_link": 9, "unclassified": 10,
    "residential": 11, "living_street": 12, "service": 13, "track": 14,
    "cycleway": 15, "footway": 16, "pedestrian": 17, "path": 18,
    "steps": 19, "bridleway": 20, "corridor": 21, "road": 22,
}
# plausible-speed defaults per class (km/h, Delhi-urban conservative);
# overridden by a real maxspeed tag when present.
SPEED = {0: 80, 1: 50, 2: 60, 3: 50, 4: 50, 5: 40, 6: 40, 7: 35,
         8: 35, 9: 30, 10: 30, 11: 25, 12: 15, 13: 20, 14: 15,
         15: 15, 16: 8, 17: 8, 18: 10, 19: 5, 20: 10, 21: 8, 22: 25}

EARTH_M = 6371000.0


def hav_m(lon1, lat1, lon2, lat2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_M * math.asin(math.sqrt(a))


class WayScan(osmium.SimpleHandler):
    """Pass 1: accepted highway ways + their node id lists."""

    def __init__(self):
        super().__init__()
        self.ways = []          # (hw_code, oneway, name, maxspeed, [node ids])
        self.need = set()       # node ids we must look up in pass 2
        self.seen = set()       # way ids — dedupe across merged extracts

    def way(self, w):
        hw = w.tags.get("highway")
        if hw not in HW_CODES:
            return
        if w.id in self.seen:
            return
        self.seen.add(w.id)
        # skip ways that clearly can't intersect the box: cheap check via
        # node refs is impossible here, so keep every candidate way —
        # pass-2 coords decide. (Highway filter already cut ~97% of ways.)
        ow = 0
        if w.tags.get("oneway") in ("yes", "true", "1"):
            ow = 1
        elif w.tags.get("oneway") == "-1":
            ow = -1
        try:
            ms = int(float(w.tags.get("maxspeed", "0").split()[0]))
        except (ValueError, IndexError):
            ms = 0
        ids = [n.ref for n in w.nodes]
        if len(ids) < 2:
            return
        self.ways.append((HW_CODES[hw], ow, w.tags.get("name"), ms, ids))
        self.need.update(ids)


class NodeScan(osmium.SimpleHandler):
    """Pass 2: coords for the nodes the accepted ways reference."""

    def __init__(self, need):
        super().__init__()
        self.need = need
        self.coords = {}

    def node(self, n):
        if n.id in self.need and n.location.valid():
            if MINLON - 0.05 <= n.lon <= MAXLON + 0.05 \
                    and MINLAT - 0.05 <= n.lat <= MAXLAT + 0.05:
                self.coords[n.id] = (n.lon, n.lat)


def build():
    sys.setrecursionlimit(200000)
    sha = hashlib.sha256()
    for p in PBFS:
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                sha.update(chunk)
    pbf_sha = sha.hexdigest()[:16]

    ws = WayScan()
    for p in PBFS:
        ws.apply_file(p)
    print(f"ways kept: {len(ws.ways)}; nodes needed: {len(ws.need)} "
          f"({len(PBFS)} pbfs)", file=sys.stderr)

    ns = NodeScan(ws.need)
    for p in PBFS:
        ns.apply_file(p)
    print(f"coords in box+pad: {len(ns.coords)}", file=sys.stderr)

    # junction detection: a node is a graph junction when it is shared by
    # ≥2 distinct ways, appears twice in the same way (self-intersect),
    # or ends a run. Tracking a single last-way per node flags "seen on
    # another way" without a per-node set.
    last_way = {}
    junction = set()
    for wi, (_, _, _, _, ids) in enumerate(ws.ways):
        for nid in ids:
            if nid not in ns.coords:
                continue
            prev = last_way.get(nid)
            if prev is not None and prev != wi:
                junction.add(nid)
            last_way[nid] = wi
        # self-intersecting node within one way
        seen = set()
        for nid in ids:
            if nid in seen and nid in ns.coords:
                junction.add(nid)
            seen.add(nid)

    # collapse through non-junction nodes: split each run at junction
    # nodes (shared by ≥2 ways / self-intersect) and run endpoints
    names = []
    name_idx = {}

    def nm_idx(name):
        if name is None:
            return -1
        if name not in name_idx:
            name_idx[name] = len(names)
            names.append(name)
        return name_idx[name]

    node_ix = {}
    nodes_out = []

    def n_ix(osm_id):
        if osm_id not in node_ix:
            node_ix[osm_id] = len(nodes_out)
            lon, lat = ns.coords[osm_id]
            nodes_out.append([osm_id, round(lon, 6), round(lat, 6)])
        return node_ix[osm_id]

    edges = []
    for hw, ow, name, ms, ids in ws.ways:
        # keep the way's ORIGINAL node order; a node outside the coord
        # box breaks the run (a way dipping out+in must not jump the gap)
        runs, cur = [], []
        for pos, nid in enumerate(ids):
            if nid in ns.coords:
                cur.append(nid)
            else:
                if len(cur) >= 2:
                    runs.append(cur)
                cur = []
        if len(cur) >= 2:
            runs.append(cur)

        for run in runs:
            if len(run) < 2:
                continue
            # split at junction nodes — endpoints always split
            chain, start = [run[0]], run[0]
            for k in range(1, len(run)):
                nd = run[k]
                chain.append(nd)
                last = k == len(run) - 1
                if nd in junction or last:
                    if len(chain) >= 2:
                        pts = [[round(ns.coords[p][0], 6),
                                round(ns.coords[p][1], 6)] for p in chain]
                        length = sum(
                            hav_m(pts[t][0], pts[t][1],
                                  pts[t + 1][0], pts[t + 1][1])
                            for t in range(len(pts) - 1))
                        if length < 5:      # degenerate stub
                            chain = [nd]
                            continue
                        edges.append({
                            "u": n_ix(chain[0]), "v": n_ix(chain[-1]),
                            "len": round(length, 1),
                            "hw": hw, "ow": ow,
                            "sp": ms or SPEED[hw],
                            "nm": nm_idx(name), "pts": pts})
                    chain = [nd]

    # ---- emit packed binary ----
    # geometry simplify (RDP on metres) + in-field flag per edge
    def rdp(pts, tol):
        if len(pts) <= 2:
            return pts
        ax, ay = pts[0]
        bx, by = pts[-1]
        dx, dy = bx - ax, by - ay
        dmax, imax = -1.0, 0
        ln = math.hypot(dx, dy) or 1e-9
        for i in range(1, len(pts) - 1):
            px, py = pts[i]
            # distance point→segment in degree space scaled to metres
            t = ((px - ax) * dx + (py - ay) * dy) / (ln * ln)
            t = max(0.0, min(1.0, t))
            qx, qy = ax + t * dx, ay + t * dy
            d = hav_m(px, py, qx, qy)
            if d > dmax:
                dmax, imax = d, i
        if dmax <= tol:
            return [pts[0], pts[-1]]
        return rdp(pts[:imax + 1], tol)[:-1] + rdp(pts[imax:], tol)

    # delta-encode safety: any consecutive-point gap beyond the i16
    # range gets evenly-spaced midpoints interpolated in (geometry
    # vertices, not graph nodes — the edge stays whole). Sparse rural
    # ways and RDP'd straight runs both land here.
    MAX_D = 0.028  # deg — inside i16 (32767 e6) with headroom

    def densify(pts):
        out = [pts[0]]
        for t in range(1, len(pts)):
            a, b = out[-1], pts[t]
            dx, dy = b[0] - a[0], b[1] - a[1]
            steps = max(math.ceil(abs(dx) / MAX_D),
                        math.ceil(abs(dy) / MAX_D))
            if steps <= 1:
                out.append(b)
            else:
                for s in range(1, steps):
                    out.append([a[0] + dx * s / steps,
                                a[1] + dy * s / steps])
                out.append(b)
        return out

    pt_count = 0
    edge_pts = []
    for e in edges:
        pts = densify(rdp(e["pts"], RDP_TOL_M))
        e["pts"] = pts
        e["in_field"] = int(any(
            FIELD_BBOX[0] <= p[0] <= FIELD_BBOX[2]
            and FIELD_BBOX[1] <= p[1] <= FIELD_BBOX[3] for p in pts))
        edge_pts.append(pts)
        pt_count += len(pts)

    blob = bytearray()
    blob += struct.pack("<4s4I", b"ARG1", len(nodes_out), len(edges),
                        len(names), pt_count)
    blob += struct.pack("<4i", int(MINLON * 1e6), int(MINLAT * 1e6),
                        int(MAXLON * 1e6), int(MAXLAT * 1e6))
    for _, lon, lat in nodes_out:
        blob += struct.pack("<2i", int(lon * 1e6), int(lat * 1e6))
    for n in names:
        b = n.encode("utf-8")
        blob += struct.pack("<H", len(b)) + b
    pts_off = 0
    pt_blob = bytearray()
    for e, pts in zip(edges, edge_pts):
        e["_pts_off"] = pts_off
        e["_pts_n"] = len(pts)
        px = struct.pack("<2i", int(round(pts[0][0] * 1e6)),
                         int(round(pts[0][1] * 1e6)))
        pt_blob += px
        for t in range(1, len(pts)):
            dl = int(round((pts[t][0] - pts[t - 1][0]) * 1e6))
            dp = int(round((pts[t][1] - pts[t - 1][1]) * 1e6))
            if not (-32768 <= dl <= 32767 and -32768 <= dp <= 32767):
                raise ValueError("pt delta overflow — split edge further")
            pt_blob += struct.pack("<2h", dl, dp)
        pts_off += 2 + (len(pts) - 1)  # 4-byte slots: abs(2) + deltas(1)
    for e in edges:
        blob += struct.pack("<IIfIHBbBiB", e["u"], e["v"], e["len"],
                            e["_pts_off"], e["_pts_n"], e["hw"], e["ow"],
                            e["sp"], max(0, e["nm"] + 1), e["in_field"])
    blob += pt_blob

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with gzip.open(OUT, "wb") as fh:
        fh.write(bytes(blob))
    meta = {"pbf": os.path.basename(PBF),
            "pbfs": [os.path.basename(p) for p in PBFS],
            "pbf_sha256": pbf_sha,
            "bbox": [MINLON, MINLAT, MAXLON, MAXLAT],
            "field_bbox": list(FIELD_BBOX),
            "rdp_tol_m": RDP_TOL_M,
            "generated": "tools/build_route_graph.py",
            "ways_in": len(ws.ways), "edges": len(edges),
            "nodes": len(nodes_out), "points": pt_count,
            "format": "ARG1 (see tools/build_route_graph.py header)"}
    with open(META, "w") as fh:
        json.dump(meta, fh, indent=1)
    size = os.path.getsize(OUT) / 1e6
    print(f"wrote {OUT}: {len(edges)} edges, {len(nodes_out)} nodes, "
          f"{pt_count} pts, {size:.1f} MB gz", file=sys.stderr)


if __name__ == "__main__":
    build()
