"""Bake Delhi NCT's sub-district boundaries -> static/delhi_subdistricts.geojson.

Same pipeline as bake_ncr_districts.py: OSM relations fetched to a
geom dir (overpass 'out geom' as geom_<rel>.json, nominatim lookup as
nom_<rel>.json), Douglas-Peucker simplified at ~50 m, one centroid per
feature for the server's sparse-fallback read.

Usage:
    cd server/tools && python bake_delhi_subdistricts.py /path/to/geom_dir

Delhi's revenue districts are NOT all OSM relations (Shahdara has none
— its area sits inside the North East / East relations). OSM instead
carries 13 admin_level=5 sub-areas of the Delhi NCT relation
(1942586): Outer North, Old Delhi and Central North are the three
names the govt's 11-district list doesn't have; Shahdara is the govt
district with no OSM boundary. We bake what OSM actually defines and
mark each feature `level: "osm_admin_5"` + `nct_subarea: true` so the
honest mapping caveat travels with the data.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bake_ncr_districts import (  # noqa: E402
    _centroid, _ring_area_km2, _rings_for, _simplify_ring,
)

# OSM relation id -> display name. All are admin_level=5 sub-areas of
# rel 1942586 (Delhi NCT), verified via an area query on 2026-10-04.
SUB_DISTRICTS = {
    21181211: "Outer North Delhi",
    21181212: "Old Delhi",
    21181213: "Central North Delhi",
    21181214: "North West Delhi",
    21181215: "West Delhi",
    21181216: "South West Delhi",
    21181217: "Central Delhi",
    21181218: "New Delhi",
    21181219: "North Delhi",
    21181220: "North East Delhi",
    21181221: "East Delhi",
    21181222: "South East Delhi",
    21181223: "South Delhi",
}


def build(geom_dir: str) -> dict:
    features = []
    for rel_id, name in SUB_DISTRICTS.items():
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
                "parent": "Delhi NCT",
                "state": "Delhi",
                "osm_relation": rel_id,
                "level": "osm_admin_5",
                "nct_subarea": True,
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
            "source": ("OpenStreetMap admin_level=5 sub-areas of rel "
                       "1942586 (Delhi NCT) via Overpass/Nominatim — "
                       "one-time bake; never refetched per request"),
            "caveat": ("OSM sub-areas, not the govt's 11 revenue "
                       "districts — Shahdara has no OSM boundary; "
                       "Outer North / Old Delhi / Central North are "
                       "OSM-only names"),
            "simplification": "Douglas-Peucker ~50 m",
            "baked_at": "2026-10-04",
        },
        "features": features,
    }


if __name__ == "__main__":
    geom_dir = sys.argv[1] if len(sys.argv) > 1 else "geom"
    fc = build(geom_dir)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "static", "delhi_subdistricts.geojson")
    with open(out, "w") as f:
        json.dump(fc, f, separators=(",", ":"))
    print(f"{len(fc['features'])} sub-districts -> {out} "
          f"({os.path.getsize(out)} bytes)")
