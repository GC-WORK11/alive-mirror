"""Live-field grid — the map's PM2.5 surface.

GeoJSON cells over the NCR bbox, valued from the same interpolated
field the dose engine uses (airfield.FIELD). Each cell carries a
confidence grade derived from distance to the nearest real sample —
the surface fades honestly where the field is thin.

No invented data: cells whose interpolated value is None are dropped.
"""
from typing import Optional

# NCR extent (matches airfield/main bbox): lon_min, lat_min, lon_max, lat_max
BBOX = (76.80, 28.20, 77.90, 28.95)


def _conf(km: Optional[float]) -> str:
    if km is None:
        return "lo"
    if km < 5:
        return "hi"
    if km < 15:
        return "med"
    return "lo"


def as_geojson(field, cells: int = 22, param: str = "pm2_5") -> dict:
    """field: the airfield FIELD object (must already be refreshed)."""
    x0, y0, x1, y1 = BBOX
    dx, dy = (x1 - x0) / cells, (y1 - y0) / cells
    feats = []
    for ix in range(cells):
        for iy in range(cells):
            cx, cy = x0 + (ix + 0.5) * dx, y0 + (iy + 0.5) * dy
            v = field.value(cy, cx, param)
            if v is None:
                continue
            feats.append({
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [x0 + ix * dx, y0 + iy * dy],
                        [x0 + (ix + 1) * dx, y0 + iy * dy],
                        [x0 + (ix + 1) * dx, y0 + (iy + 1) * dy],
                        [x0 + ix * dx, y0 + (iy + 1) * dy],
                        [x0 + ix * dx, y0 + iy * dy],
                    ]],
                },
                # property named for the species it holds — 'pm25' stays
                # 'pm25' for the default layer so existing readers don't
                # break; another species never borrows its name
                "properties": {
                    ("pm25" if param == "pm2_5" else param): round(v, 1),
                    "param": param,
                    "conf": _conf(field.nearest_sample_km(cy, cx)),
                },
            })
    return {"type": "FeatureCollection", "features": feats}
