#!/usr/bin/env python3
"""One-time bake: OSM admin relations -> server/static/ncr_districts.geojson.

Sources (whichever file is present in the geom dir):
  * geom_<osm_id>.json — Overpass `relation(<id>); out geom;`
  * nom_<osm_id>.json  — Nominatim lookup?osm_ids=R<id>&polygon_geojson=1

The boundary data ships as a static asset so the live server never
depends on OSM endpoints at request time. Data (c) OpenStreetMap
contributors, ODbL.

Districts = the NCR Planning Board constituents the air field can
actually value (Regional Plan 2041 list: NCT Delhi + 14 Haryana + 8 UP
+ 2 Rajasthan districts; the 12 that lie wholly outside the field's
spatial domain are omitted — they could never carry a number).

Ring assembly: Overpass outer way members are stitched into closed
rings by matching endpoint node refs (Nominatim already returns
assembled GeoJSON); all geometry is simplified with Douglas-Peucker
(~50 m) in a local equirectangular projection; an area-weighted
centroid is baked per feature for the server's sparse-fallback read.
"""
import json
import math
import os
import sys

TOL_KM = 0.05                      # ~50 m Douglas-Peucker tolerance
LAT0 = 28.55                       # projection origin (Delhi)

# osm relation id -> (display name, state)
DISTRICTS = {
    1942586: ("Delhi NCT", "Delhi"),
    9999195: ("Baghpat", "Uttar Pradesh"),
    9999582: ("Ghaziabad", "Uttar Pradesh"),
    9999630: ("Gautam Buddha Nagar", "Uttar Pradesh"),   # Noida/Gr. Noida
    10002301: ("Bulandshahr", "Uttar Pradesh"),
    10002584: ("Hapur", "Uttar Pradesh"),
    10396743: ("Sonipat", "Haryana"),
    10397935: ("Jhajjar", "Haryana"),
    10398244: ("Gurugram", "Haryana"),                  # OSM name: Gurgaon
    10398275: ("Faridabad", "Haryana"),
    10398317: ("Palwal", "Haryana"),
    10398371: ("Nuh", "Haryana"),                       # formerly Mewat
    17749398: ("Meerut", "Uttar Pradesh"),
}


def _project(lat, lon):
    """lon/lat deg -> local km (equirectangular about LAT0)."""
    return (lon * 111.32 * math.cos(math.radians(LAT0)),
            lat * 110.57)


def _dp(points, tol):
    """Douglas-Peucker on (x,y) km points; keeps first/last."""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        (x1, y1), (x2, y2) = points[a], points[b]
        dx, dy = x2 - x1, y2 - y1
        seg = math.hypot(dx, dy)
        dmax, imax = 0.0, -1
        for i in range(a + 1, b):
            px, py = points[i]
            if seg < 1e-12:
                d = math.hypot(px - x1, py - y1)
            else:
                d = abs(dy * px - dx * py + x2 * y1 - y2 * x1) / seg
            if d > dmax:
                dmax, imax = d, i
        if dmax > tol and imax > 0:
            keep[imax] = True
            stack += [(a, imax), (imax, b)]
    return [p for p, k in zip(points, keep) if k]


def _key(node):
    """Endpoint identity for stitching — 'out geom' nodes carry lat/lon
    (refs only appear with 'out body'); shared endpoints share coords."""
    return (round(node["lat"], 6), round(node["lon"], 6))


def _stitch(ways):
    """member ways -> list of closed rings, keyed on endpoint coords."""
    segs = [w["geometry"] for w in ways if len(w.get("geometry") or []) >= 2]
    rings = []
    while segs:
        ring = segs.pop()
        closed = _key(ring[0]) == _key(ring[-1])
        guard = 0
        while not closed and guard < 2000:
            guard += 1
            head, tail = _key(ring[0]), _key(ring[-1])
            nxt = None
            for i, s in enumerate(segs):
                s0, s1 = _key(s[0]), _key(s[-1])
                if s0 == tail:
                    ring = ring + s[1:]
                elif s1 == tail:
                    ring = ring + s[-2::-1]
                elif s1 == head:
                    ring = s[:-1] + ring
                elif s0 == head:
                    ring = s[1::-1] + ring
                else:
                    continue
                segs.pop(i)
                nxt = True
                break
            if not nxt:
                break                       # unclosed gap — keep what we have
            closed = _key(ring[0]) == _key(ring[-1])
        if closed and len(ring) >= 4:
            rings.append(ring)
    return rings


def _centroid(ring_ll):
    """Area-weighted centroid of one lon/lat ring (shoelace)."""
    a = cx = cy = 0.0
    for (lon1, lat1), (lon2, lat2) in zip(ring_ll, ring_ll[1:]):
        cross = lon1 * lat2 - lon2 * lat1
        a += cross
        cx += (lon1 + lon2) * cross
        cy += (lat1 + lat2) * cross
    if abs(a) < 1e-12:
        n = len(ring_ll)
        return [sum(p[0] for p in ring_ll) / n,
                sum(p[1] for p in ring_ll) / n]
    a *= 0.5
    return [cx / (6 * a), cy / (6 * a)]


def _ring_area_km2(ring_ll):
    pts = [_project(la, lo) for lo, la in ring_ll]
    return abs(sum(x1 * y2 - x2 * y1
                   for (x1, y1), (x2, y2) in zip(pts, pts[1:]))) / 2


def _simplify_ring(ring_ll):
    """lon/lat ring -> simplified lon/lat ring (closed, rounded 5dp)."""
    km = [_project(la, lo) for lo, la in ring_ll]
    simp = _dp(km, TOL_KM)
    keep_ll = []
    used = set()
    for kp in simp:
        for i, p in enumerate(km):
            if i in used:
                continue
            if abs(p[0] - kp[0]) < 1e-9 and abs(p[1] - kp[1]) < 1e-9:
                used.add(i)
                keep_ll.append(ring_ll[i])
                break
    if len(keep_ll) < 4:
        keep_ll = ring_ll[:4]
    return [[round(p[0], 5), round(p[1], 5)] for p in keep_ll]


def _overpass_rings(path):
    """-> list of lon/lat outer rings from an Overpass 'out geom' rel."""
    with open(path) as f:
        data = json.load(f)
    rel = data["elements"][0]
    outers = [m for m in rel.get("members", [])
              if m.get("type") == "way" and "geometry" in m
              and m.get("role", "outer") == "outer"]
    return [[[n["lon"], n["lat"]] for n in ring]
            for ring in _stitch(outers)]


def _nominatim_rings(path):
    """-> list of lon/lat outer rings from a Nominatim geojson lookup."""
    with open(path) as f:
        data = json.load(f)
    geom = data[0]["geojson"]
    if geom["type"] == "Polygon":
        return [geom["coordinates"][0]]
    return [p[0] for p in geom["coordinates"]]


def _rings_for(geom_dir, rel_id):
    op = os.path.join(geom_dir, f"geom_{rel_id}.json")
    err = None
    if os.path.exists(op) and os.path.getsize(op) > 2000:
        try:
            rings = _overpass_rings(op)
            if rings:
                return rings, "overpass"
        except Exception as e:
            err = e
    nom = os.path.join(geom_dir, f"nom_{rel_id}.json")
    if os.path.exists(nom):
        rings = _nominatim_rings(nom)
        return rings, "nominatim"
    raise SystemExit(f"rel {rel_id}: no usable geometry "
                     f"(overpass err={err}; {nom} missing)")


def build(geom_dir: str) -> dict:
    features = []
    for rel_id, (name, state) in DISTRICTS.items():
        rings, src = _rings_for(geom_dir, rel_id)
        if not rings:
            raise SystemExit(f"{name} ({rel_id}): no outer rings")
        polys = [[_simplify_ring(r)] for r in rings if len(r) >= 4]
        biggest = max(polys, key=lambda p: _ring_area_km2(p[0]))
        centroid = _centroid(biggest[0])
        features.append({
            "type": "Feature",
            "properties": {
                "name": name,
                "state": state,
                "osm_relation": rel_id,
                "centroid": [round(centroid[0], 5), round(centroid[1], 5)],
                "outer_rings": len(polys),
                "geom_source": src,
            },
            "geometry": ({"type": "Polygon", "coordinates": polys[0]}
                         if len(polys) == 1 else
                         {"type": "MultiPolygon", "coordinates": polys}),
        })
    return {
        "type": "FeatureCollection",
        "properties": {
            "source": ("OpenStreetMap admin relations (ODbL) via Overpass/"
                       "Nominatim — one-time bake; never refetched per request"),
            "simplification": f"Douglas-Peucker ~{int(TOL_KM * 1000)} m",
            "districts": "NCR Planning Board (Regional Plan 2041) "
                         "constituents overlapping the air-field domain",
            "baked_at": "2026-10-03",
        },
        "features": features,
    }


if __name__ == "__main__":
    geom_dir = sys.argv[1] if len(sys.argv) > 1 else "/tmp/ncr"
    out = (sys.argv[2] if len(sys.argv) > 2 else
           os.path.join(os.path.dirname(os.path.dirname(
               os.path.abspath(__file__))), "static", "ncr_districts.geojson"))
    fc = build(geom_dir)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(fc, f, separators=(",", ":"))
    kb = os.path.getsize(out) / 1024
    print(f"{out}: {kb:.0f} KB, {len(fc['features'])} districts")
    for ft in fc["features"]:
        p = ft["properties"]
        print(f"  {p['name']:<22} {ft['geometry']['type']:<12} "
              f"centroid {p['centroid']} src={p['geom_source']}")
