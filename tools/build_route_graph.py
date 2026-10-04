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

Honest legality notes (audited in server/tests/test_path_legality.py):
the build keeps OSM `highway=*` class, `oneway` (incl. `oneway=-1`),
per-tag access overrides (`access`/`vehicle`/`motor_vehicle`/`motorcar`/
`motorcycle`/`bicycle`/`foot` = no|private deny, permissive/destination/
designated allow, general→specific cascade) and `restriction=*` TURN
RELATIONS. Bans are emitted as (directed in-edge, via node, directed
out-edge, mode mask) triples and enforced inside the engines' A*:
no_left/no_right/no_straight_on → the listed transition; no_u_turn →
the same-edge reversal; only_* → every other exit at the via node;
no_entry/no_exit → all entries/exits onto/off the restricted way.
via=way relations: when the via way is exactly one packed edge whose
only forward continuations are onto the to-way, the ban is emitted as an
entry ban at the via edge's tail node (exact semantics); multi-edge or
ambiguous via ways are counted and skipped — never silently dropped,
never faked. Bans apply to motorized modes + bicycle; walking ignores
vehicular turn bans. `except=` values clear the matching mode bit.

Output: server/data/route_graph.bin.gz — gzipped packed binary:
  header  : magic "ARG2" | u32 n_nodes | u32 n_edges | u32 n_names |
            u32 n_pts | u32 bbox×4 (i32 microdeg)
  nodes   : i32 lon_e6, i32 lat_e6  (8B each; osm ids dropped post-build)
  names   : u16 len + utf-8 bytes, ×n_names
  edges   : u32 u | u32 v | f32 len_m | u32 pts_off | u16 pts_n |
            u8 hw | i8 oneway(-1/0/1) | u8 speed_kmh | u32 name_idx |
            u8 in_field_flag | u8 acc_mask  (deny bits: 1 motor, 2 cycle,
            4 foot, 8 motorcar-class, 16 motorcycle)
  bans    : u32 n_bans, then per ban u32 in_dir | u32 via | u32 out_dir |
            u8 mode_mask (1 motor, 2 cycle, 4 walk) — directed edge ids
            use the adjacency convention (e | 0x80000000 = v->u)
  pts     : per-edge polyline, i16 microdeg deltas from the previous
            point; first point absolute i32 pair (deg×1e6)
  meta.json sidecar: {pbf, pbf_sha256, bbox, counts}

  ARG1 (pre-restriction builds) reads as acc=0 / no bans — both engines
  accept it, legality degrades to the old class-level behaviour.

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


# per-edge access deny bits (routegraph.py/path.cpp keep the same map)
ACC_MOTOR = 1
ACC_CYCLE = 2
ACC_FOOT = 4
ACC_MOTORCAR = 8
ACC_MOTORCYCLE = 16

# access values → legality. `no` is a hard deny for the modes it
# names. `private` is deliberately NOT a deny: in this extract it
# blankets gated-colony streets (~30k ways in the central zone alone)
# that carry ordinary traffic — enforcing it strands whole colonies
# inside "no path" pockets, and real routers only ever honour it at
# path endpoints. access=private stays a documented non-constraint.
_ACCESS_DENY = {"no"}
_ACCESS_ALLOW = {"yes", "designated", "permissive", "destination",
                 "delivery", "customers", "permit", "public", "official"}
# access cascade, general → specific; vehicle=* covers every vehicle
# incl. bicycles but not pedestrians
_ACCESS_ORDER = (("access", ACC_MOTOR | ACC_CYCLE | ACC_FOOT),
                 ("vehicle", ACC_MOTOR | ACC_CYCLE),
                 ("motor_vehicle", ACC_MOTOR),
                 ("motorcar", ACC_MOTORCAR),
                 ("motorcycle", ACC_MOTORCYCLE),
                 ("bicycle", ACC_CYCLE),
                 ("foot", ACC_FOOT))


def access_mask(tags):
    """way tags → per-edge deny byte. `no` sets a bit; the allow-family
    clears it — a specific allow overrides a general deny
    (`access=no` + `foot=yes` blocks motors, admits walkers).
    Conditional restrictions (`*:conditional`) are not evaluated —
    a timed ban is not a ban for path legality here. `private` is
    likewise not evaluated — see _ACCESS_DENY for why."""
    acc = 0
    for key, bits in _ACCESS_ORDER:
        v = tags.get(key)
        if v is None:
            continue
        v = v.strip().lower().split(";")[0].split(" ")[0]
        if v in _ACCESS_DENY:
            acc |= bits
        elif v in _ACCESS_ALLOW:
            acc &= ~bits
    return acc


class WayScan(osmium.SimpleHandler):
    """Pass 1: accepted highway ways + their node id lists."""

    def __init__(self):
        super().__init__()
        self.ways = []          # (osm_id, hw_code, oneway, name, maxspeed,
                                #  acc_mask, [node ids])
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
        self.ways.append((w.id, HW_CODES[hw], ow, w.tags.get("name"),
                          ms, access_mask(w.tags), ids))
        self.need.update(ids)


class RelScan(osmium.SimpleHandler):
    """Pass 1b: turn-restriction relations (`restriction=*`). Members
    are kept raw (OSM ids); they resolve to packed edges/nodes after the
    collapse because only junction nodes and per-way edges survive."""

    def __init__(self):
        super().__init__()
        self.rels = []          # (restriction, from_ways, via_nodes,
                                #  via_ways, to_ways, except_values)
        self.seen = set()

    def relation(self, r):
        rest = r.tags.get("restriction")
        if rest is None:
            return
        if r.id in self.seen:
            return
        self.seen.add(r.id)
        from_w, via_n, via_w, to_w = [], [], [], []
        for m in r.members:
            if m.role == "from" and m.type == "w":
                from_w.append(m.ref)
            elif m.role == "via" and m.type == "n":
                via_n.append(m.ref)
            elif m.role == "via" and m.type == "w":
                via_w.append(m.ref)
            elif m.role == "to" and m.type == "w":
                to_w.append(m.ref)
        if not from_w or not (via_n or via_w):
            return
        exc = r.tags.get("except") or ""
        exc = {x.strip().lower() for x in exc.replace(",", ";").split(";")
               if x.strip()}
        self.rels.append((rest, from_w, via_n, via_w, to_w, exc))


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

    rs = RelScan()
    for p in PBFS:
        rs.apply_file(p)
    print(f"restriction relations: {len(rs.rels)}", file=sys.stderr)

    # junction detection: a node is a graph junction when it is shared by
    # ≥2 distinct ways, appears twice in the same way (self-intersect),
    # or ends a run. Tracking a single last-way per node flags "seen on
    # another way" without a per-node set.
    last_way = {}
    junction = set()
    for wi, (_wid, _hw, _ow, _nm, _ms, _acc, ids) in enumerate(ws.ways):
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
    way_edges = defaultdict(list)   # way index → packed edge indices
    wi_of_osm = {}                  # osm way id → way index
    for wi, (wid, hw, ow, name, ms, acc, ids) in enumerate(ws.ways):
        wi_of_osm[wid] = wi
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
                        e_ix = len(edges)
                        edges.append({
                            "u": n_ix(chain[0]), "v": n_ix(chain[-1]),
                            "len": round(length, 1),
                            "hw": hw, "ow": ow, "acc": acc, "_wi": wi,
                            "sp": ms or SPEED[hw],
                            "nm": nm_idx(name), "pts": pts})
                        way_edges[wi].append(e_ix)
                    chain = [nd]

    # ---- turn restrictions → (dir-in, via node, dir-out, mode mask) ----
    # directed-id convention matches adjacency: e | 0x80000000 = v->u.
    REV = 0x80000000
    out_dirs = defaultdict(list)    # packed node → [(edge, rev)] leaving
    in_dirs = defaultdict(list)     # packed node → [(edge, rev)] arriving
    for i, e in enumerate(edges):
        out_dirs[e["u"]].append((i, False))
        out_dirs[e["v"]].append((i, True))
        in_dirs[e["u"]].append((i, True))   # v->u traversal ends at u
        in_dirs[e["v"]].append((i, False))  # u->v traversal ends at v

    def dirs_arriving_on(wi, node):
        """directed edges of way wi ENDING at node, filtered to the
        way's legal travel direction."""
        ow = ws.ways[wi][2]
        out = []
        for e in way_edges.get(wi, ()):
            if edges[e]["v"] == node and ow != -1:
                out.append(e)              # forward arrival u->v
            if edges[e]["u"] == node and ow != 1:
                out.append(e | REV)        # reversed arrival v->u
        return out

    def dirs_leaving_on(wi, node):
        """directed edges of way wi STARTING at node (way-legal dirs)."""
        ow = ws.ways[wi][2]
        out = []
        for e in way_edges.get(wi, ()):
            if edges[e]["u"] == node and ow != -1:
                out.append(e)              # forward leave u->v
            if edges[e]["v"] == node and ow != 1:
                out.append(e | REV)        # reversed leave v->u
        return out

    def ban_mask(exc):
        """turn bans bind motorized modes + bicycle; pedestrians ignore
        vehicular turn signs. `except=` clears the matching bit."""
        mask = 0b011
        if exc & {"bicycle", "bicycles"}:
            mask &= ~0b010
        if exc & {"motor_vehicle", "motorcar", "motorcycle", "psv",
                  "hgv", "motorized", "vehicle"}:
            mask &= ~0b001
        return mask

    bans = []
    stats = defaultdict(int)
    for rest, from_w, via_n, via_w, to_w, exc in rs.rels:
        mask = ban_mask(exc)
        if not mask:
            stats["all_except"] += 1
            continue
        fw_ix = [wi_of_osm[w] for w in from_w if w in wi_of_osm]
        tw_ix = [wi_of_osm[w] for w in to_w if w in wi_of_osm]
        if not fw_ix:
            stats["from_way_outside"] += 1
            continue
        if via_w:
            # via-way relations encode naturally in the (arrival dir,
            # node, exit dir) tuple space: after traversing the via
            # edge to its head node, the move onto the to-way is the
            # banned one — so ban (via_dir, head, to_dir). Only the
            # link's far-end move is restricted, never its entry.
            # Requires the via way to map to exactly ONE packed edge
            # (a multi-edge link has no single arrival dir to key on —
            # counted skipped). Over-ban caveat: if the link is also
            # reachable from ways other than the relation's `from`,
            # those approaches get the same ban — the tuple can't key
            # on the pre-link edge. Documented, not faked.
            stats["via_way_seen"] += len(via_w)
            for vwid in via_w:
                vw = wi_of_osm.get(vwid)
                if vw is None or len(way_edges.get(vw, ())) != 1:
                    stats["via_way_multiedge_or_outside"] += 1
                    continue
                ve = way_edges[vw][0]
                for tail, head, fwd_dir in (
                        (edges[ve]["u"], edges[ve]["v"], ve),
                        (edges[ve]["v"], edges[ve]["u"], ve | REV)):
                    # the relation only binds when its `from` way
                    # actually feeds this end of the link
                    if not any(dirs_arriving_on(wi, tail)
                               for wi in fw_ix):
                        continue
                    if rest.startswith("only_"):
                        to_e = {d & ~REV for wi in tw_ix
                                for d in dirs_leaving_on(wi, head)}
                        outs = [e | REV if rr else e
                                for e, rr in out_dirs[head]]
                        emitted_here = 0
                        for o in outs:
                            if (o & ~REV) not in to_e:
                                bans.append((fwd_dir, head, o, mask))
                                emitted_here += 1
                    else:
                        emitted_here = 0
                        for wi in tw_ix:
                            for o in dirs_leaving_on(wi, head):
                                bans.append((fwd_dir, head, o, mask))
                                emitted_here += 1
                    stats["via_way_enforced"] += emitted_here
                    if not emitted_here:
                        stats["via_way_to_outside"] += 1
            continue
        if rest == "no_u_turn":
            # same-way reversal: arriving on d, can't leave on d^REV
            emitted = 0
            for node in via_n:
                pnode = node_ix.get(node)
                if pnode is None:
                    stats["via_node_outside"] += 1
                    continue
                for wi in fw_ix:
                    for d in dirs_arriving_on(wi, pnode):
                        bans.append((d, pnode, d ^ REV, mask))
                        emitted += 1
            stats["no_u_turn"] += emitted
            continue
        # via-node relations
        emitted = 0
        for node in via_n:
            pnode = node_ix.get(node)
            if pnode is None:
                stats["via_node_outside"] += 1
                continue
            to_dirs = []
            for wi in tw_ix:
                to_dirs += dirs_leaving_on(wi, pnode)
            to_e = {d & ~REV for d in to_dirs}
            if rest.startswith("no_"):
                if not tw_ix or not to_dirs:
                    stats["to_way_outside"] += 1
                    continue
                for wi in fw_ix:
                    for d in dirs_arriving_on(wi, pnode):
                        for o in to_dirs:
                            bans.append((d, pnode, o, mask))
                            emitted += 1
            elif rest.startswith("only_"):
                if not tw_ix or not to_dirs:
                    stats["to_way_outside"] += 1
                    continue
                outs = [e | REV if rr else e for e, rr in out_dirs[pnode]]
                for wi in fw_ix:
                    for d in dirs_arriving_on(wi, pnode):
                        for o in outs:
                            if (o & ~REV) not in to_e:
                                bans.append((d, pnode, o, mask))
                                emitted += 1
            elif rest == "no_entry":
                f_leave = [d for wi in fw_ix
                           for d in dirs_leaving_on(wi, pnode)]
                f_edges = set()
                for wi in fw_ix:
                    f_edges.update(way_edges.get(wi, ()))
                for e, rr in in_dirs[pnode]:
                    if e in f_edges:
                        continue
                    din = e | REV if rr else e
                    for o in f_leave:
                        bans.append((din, pnode, o, mask))
                        emitted += 1
            elif rest == "no_exit":
                f_edges = set()
                for wi in fw_ix:
                    f_edges.update(way_edges.get(wi, ()))
                outs = [e | REV if rr else e for e, rr in out_dirs[pnode]
                        if e not in f_edges]
                for wi in fw_ix:
                    for d in dirs_arriving_on(wi, pnode):
                        for o in outs:
                            bans.append((d, pnode, o, mask))
                            emitted += 1
            else:
                stats["unhandled_kind"] += 1
        stats[rest] = stats.get(rest, 0) + emitted
    stats["bans"] = len(bans)
    print("restrictions:", dict(stats), file=sys.stderr)

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
    blob += struct.pack("<4s4I", b"ARG2", len(nodes_out), len(edges),
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
        blob += struct.pack("<IIfIHBbBiBB", e["u"], e["v"], e["len"],
                            e["_pts_off"], e["_pts_n"], e["hw"], e["ow"],
                            e["sp"], max(0, e["nm"] + 1), e["in_field"],
                            e["acc"])
    blob += struct.pack("<I", len(bans))
    for din, via, dout, mask in bans:
        blob += struct.pack("<IIIB", din, via, dout, mask)
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
            "bans": len(bans), "ban_stats": dict(stats),
            "format": "ARG2 (see tools/build_route_graph.py header)"}
    with open(META, "w") as fh:
        json.dump(meta, fh, indent=1)
    size = os.path.getsize(OUT) / 1e6
    print(f"wrote {OUT}: {len(edges)} edges, {len(nodes_out)} nodes, "
          f"{pt_count} pts, {size:.1f} MB gz", file=sys.stderr)


if __name__ == "__main__":
    build()
