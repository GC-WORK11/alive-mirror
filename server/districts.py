"""NCR district choropleth — per-district live air for /city.

Boundaries are the baked asset server/static/ncr_districts.geojson
(OSM admin relations, one-time Overpass fetch — see
server/tools/bake_ncr_districts.py). Values come from the same live
PM2.5 field /grid serves:

  * mean of the /grid cells whose centres fall inside the district
    polygon (grid.as_geojson at cells=40 — the field's own samples,
    never interpolated differently for the map)
  * <3 covered cells -> the baked polygon centroid read instead, and the
    district reports confidence "sparse" — never zero-filled
  * no read at all -> aqi/pm25 None, confidence "none"

Two index numbers ride each row: `aqi` is the CPCB sub-index for PM2.5
(the official Indian scale the colours and categories belong to);
`aqi_us` is the US EPA PM2.5 AQI — kept for parity with the field's
us_aqi species. `category`/`color` always follow the CPCB bands.

CPCB palette source: Google's `ind_cpcb` implementation of the national
AQI, which documents the official hexes
(developers.google.com/maps/documentation/air-quality/laqis) — the
'mandate' hex for Poor (#FF9900) is not the official one; CPCB uses
#FF6500. Categories/health bands per CPCB 'How AQI is Calculated'
(airquality.cpcb.gov.in/ccr_docs/How_AQI_Calculated.pdf).
"""
import json
import os
import statistics
import threading
from typing import Optional

_DIR = os.path.dirname(os.path.abspath(__file__))
GEOJSON_PATH = os.path.join(_DIR, "static", "ncr_districts.geojson")
SUBDISTRICT_GEOJSON_PATH = os.path.join(
    _DIR, "static", "delhi_subdistricts.geojson")

# CPCB National AQI — six categories with official colours.
# ind_cpcb hexes per Google Air Quality API docs (matches CPCB scheme):
# Good #00B050, Satisfactory #92D050, Moderate #FFFF00,
# Poor #FF6500, Very Poor #FF0000, Severe #C00000
CPCB_BANDS = [
    # (aqi_lo, aqi_hi, category, color)
    (0, 50, "Good", "#00B050"),
    (51, 100, "Satisfactory", "#92D050"),
    (101, 200, "Moderate", "#FFFF00"),
    (201, 300, "Poor", "#FF6500"),
    (301, 400, "Very Poor", "#FF0000"),
    (401, 500, "Severe", "#C00000"),
]

# CPCB PM2.5 sub-index breakpoints (24-hr µg/m³ -> AQI) — Table 3.1 of
# the national AQI doc: 0-30->0-50, 31-60->51-100, 61-90->101-200,
# 91-120->201-300, 121-250->301-400, >250->401-500 (linear on 250-500).
_CPCB_PM25 = [
    (0.0, 30.0, 0, 50),
    (30.0, 60.0, 51, 100),
    (60.0, 90.0, 101, 200),
    (90.0, 120.0, 201, 300),
    (120.0, 250.0, 301, 400),
    (250.0, 500.0, 401, 500),
]

# US EPA PM2.5 breakpoints (24-hr µg/m³ -> AQI) — the 2024 revision
# Open-Meteo's us_aqi follows (aqs.epa.gov/aqsweb/documents/codetables/
# aqi_breakpoints.html): Good tightened to 0-9.0, Hazardous re-banded.
_US_PM25 = [
    (0.0, 9.0, 0, 50),
    (9.0, 35.4, 51, 100),
    (35.4, 55.4, 101, 150),
    (55.4, 125.4, 151, 200),
    (125.4, 225.4, 201, 300),
    (225.4, 325.4, 301, 400),
    (325.4, 500.4, 401, 500),
]


def _sub_index(pm25: float, table) -> float:
    """Linear interpolation inside the breakpoint band (CPCB/EPA
    sub-index formula). Concentrations above the last band extrapolate
    linearly and are returned unclamped — the caller rounds."""
    for bp_lo, bp_hi, i_lo, i_hi in table:
        if pm25 <= bp_hi:
            if bp_hi <= bp_lo:
                return float(i_hi)
            return (i_hi - i_lo) / (bp_hi - bp_lo) * (pm25 - bp_lo) + i_lo
    bp_lo, bp_hi, i_lo, i_hi = table[-1]
    return (i_hi - i_lo) / (bp_hi - bp_lo) * (pm25 - bp_lo) + i_lo


def cpcb_aqi(pm25: float) -> Optional[int]:
    """CPCB PM2.5 sub-index, rounded to an integer AQI."""
    if pm25 is None:
        return None
    return int(round(_sub_index(max(0.0, pm25), _CPCB_PM25)))


def us_aqi(pm25: float) -> Optional[int]:
    """US EPA PM2.5 AQI, rounded."""
    if pm25 is None:
        return None
    return int(round(_sub_index(max(0.0, pm25), _US_PM25)))


def cpcb_band(aqi: Optional[int]):
    """(category, color) for an AQI value — official CPCB six-band."""
    if aqi is None:
        return "No data", "#A6ACB8"
    for lo, hi, cat, color in CPCB_BANDS:
        if aqi <= hi:
            return cat, color
    return CPCB_BANDS[-1][2], CPCB_BANDS[-1][3]


# ------------------------------------------------------------------- GRAP
# Delhi's legally binding emergency stages, declared by CAQM on Delhi's
# CPCB national AQI — CAQM 'Comprehensively revised GRAP Schedule' for
# NCR (caqm.nic.in, Dec 2024; further revised 21-Nov-2025, which moved
# measures between stages without touching the AQI thresholds):
#   Stage I  'Poor'      AQI 201-300
#   Stage II 'Very Poor' AQI 301-400
#   Stage III 'Severe'   AQI 401-450
#   Stage IV 'Severe+'   AQI >450
def grap_stage(aqi: Optional[int]) -> Optional[int]:
    """GRAP stage number (1-4) an AQI maps to; 0 below the Stage-I
    floor — a real answer, not an absence. None when there is no AQI
    at all: no honest stage exists to report."""
    if aqi is None:
        return None
    return (4 if aqi > 450 else 3 if aqi > 400 else
            2 if aqi > 300 else 1 if aqi > 200 else 0)


def grap_block(mean_pm25, basis: str) -> Optional[dict]:
    """The v2 GRAP-equivalent block served beside a field summary:
    {equivalent_stage, aqi, basis, note}. The stage is computed from the
    served PM2.5 mean through cpcb_aqi — the national index GRAP is
    declared on — so every surface maps air to a stage the same way and
    no second AQI formula exists. 'Equivalent', never 'in effect': the
    legal stage is CAQM's declaration, which we don't receive. None on a
    cold field — the caller omits the key rather than fake a stage."""
    aqi = cpcb_aqi(mean_pm25)
    if aqi is None:
        return None
    return {
        "equivalent_stage": grap_stage(aqi),
        "aqi": aqi,
        "basis": basis,
        "note": "computed from today's air, not the official "
                "CAQM declaration",
    }


# ---------------------------------------------------------------- geometry

def _rings(geom: dict):
    """GeoJSON Polygon/MultiPolygon -> list of outer rings (lon/lat)."""
    t = geom.get("type")
    c = geom.get("coordinates") or []
    if t == "Polygon":
        return [r for r in c if r]
    if t == "MultiPolygon":
        return [p[0] for p in c if p and p[0]]
    return []


def _point_in_ring(lon: float, lat: float, ring) -> bool:
    """Ray casting — standard even-odd test."""
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > lat) != (yj > lat)) and (
                lon < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _ring_bbox(ring):
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return min(xs), min(ys), max(xs), max(ys)


# ---------------------------------------------------------------- loading

_lock = threading.Lock()
_cache = None


def _load_features(path: str, level: str) -> list:
    with open(path) as f:
        fc = json.load(f)
    out = []
    for ft in fc.get("features", []):
        p = ft.get("properties") or {}
        rings = _rings(ft.get("geometry") or {})
        if not rings:
            continue
        out.append({
            "name": p.get("name") or "?",
            "state": p.get("state"),
            "centroid": p.get("centroid"),
            "level": p.get("level") or level,
            "parent": p.get("parent"),
            "rings": rings,
            "bboxes": [_ring_bbox(r) for r in rings],
        })
    return out


def _districts() -> list:
    """Load + index both baked geojsons once per process.

    The NCR district list comes first, then Delhi NCT's 13 OSM
    admin_level=5 sub-areas (level 'osm_admin_5', parent 'Delhi NCT').
    A sub-area row is just another polygon the same cells+centroid
    pipeline values — /v2/districts rows carry 'level'/'parent' so a
    consumer can group them without re-deriving the geography."""
    global _cache
    if _cache is not None:
        return _cache
    with _lock:
        if _cache is not None:
            return _cache
        out = _load_features(GEOJSON_PATH, "district")
        try:
            out += _load_features(SUBDISTRICT_GEOJSON_PATH, "subdistrict")
        except FileNotFoundError:
            pass  # asset absent -> district rows only, nothing invented
        _cache = out
        return out


def area_for_point(lon: float, lat: float):
    """Finest named area containing (lon, lat): a Delhi sub-district when
    the point lands inside one of NCT's 13 OSM admin_level=5 sub-areas,
    else the NCR district polygon, else None. Sub-areas are checked
    first — they nest inside the Delhi NCT district ring, so district-
    first would never resolve them. Returns
    {"name", "level", "parent"} or None — used to snap donated-trip
    endpoints to an area for the admin global aggregates."""
    for d in reversed(_districts()):   # sub-areas load after districts
        for (x0, y0, x1, y1), ring in zip(d["bboxes"], d["rings"]):
            if x0 <= lon <= x1 and y0 <= lat <= y1 \
                    and _point_in_ring(lon, lat, ring):
                return {"name": d["name"], "level": d["level"],
                        "parent": d["parent"]}
    return None


def _cell_center(geom: dict):
    t = geom.get("type")
    c = geom.get("coordinates")
    if t == "Point":
        return c[0], c[1]
    ring = (c[0] if t == "Polygon" else c[0][0]) if c else None
    if not ring:
        return None, None
    xs = [p[0] for p in ring[:-1]]
    ys = [p[1] for p in ring[:-1]]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


# ---------------------------------------------------------------- live read

def live(grid_features: list) -> list:
    """Per-district read over the /grid FeatureCollection cells.

    Each district takes the mean pm25 of cells whose centre lies inside
    its outer rings; districts with <3 covered cells fall back to the
    baked centroid point read and are flagged 'sparse' — a district is
    never zero-filled or skipped silently."""
    ds = _districts()
    cells = []
    for f in grid_features:
        g = f.get("geometry") or {}
        lon, lat = _cell_center(g)
        if lon is None:
            continue
        pm = (f.get("properties") or {}).get("pm25")
        cells.append((lon, lat, pm))

    # partial coverage is computed, not claimed: a district whose ring
    # bounding boxes reach past the grid's own cell-center extent can
    # only be read on its in-field part (Rohtak's SE corner, Rewari's
    # NE tip, the northern districts past 28.95). The flag rides every
    # row so a consumer never reads a mean as district-wide truth.
    if cells:
        fx0 = min(c[0] for c in cells)
        fy0 = min(c[1] for c in cells)
        fx1 = max(c[0] for c in cells)
        fy1 = max(c[1] for c in cells)
    else:
        fx0 = fy0 = fx1 = fy1 = None

    out = []
    for d in ds:
        hits = []
        for lon, lat, pm in cells:
            if pm is None:
                continue
            covered = False
            for (x0, y0, x1, y1), ring in zip(d["bboxes"], d["rings"]):
                if not (x0 <= lon <= x1 and y0 <= lat <= y1):
                    continue
                if _point_in_ring(lon, lat, ring):
                    covered = True
                    break
            if covered:
                hits.append(pm)
        sparse = len(hits) < 3
        pm25 = round(statistics.fmean(hits), 1) if hits else None
        partial = (cells and any(
            not (fx0 <= x0 and x1 <= fx1 and fy0 <= y0 and y1 <= fy1)
            for (x0, y0, x1, y1) in d["bboxes"])) or False
        out.append({
            "name": d["name"],
            "state": d["state"],
            "level": d["level"],
            "parent": d["parent"],
            "partial_field_coverage": bool(partial),
            "cells_covered": len(hits),
            "pm25": pm25,
            "_centroid": d["centroid"],
            "_sparse": sparse,
        })
    return out


def finalize(rows: list, centroid_read) -> list:
    """Attach AQI/category/colour; sparse districts (<3 covered cells)
    take the centroid read (centroid_read(lat, lon) -> Optional[pm25]).
    A district the field can't value at all reports aqi/pm25 None and
    confidence 'none' — never zero-filled, never skipped."""
    for r in rows:
        c = r.pop("_centroid", None)
        sparse = r.pop("_sparse", False)
        if sparse:
            v = centroid_read(c[1], c[0]) if c else None
            if v is not None:
                r["pm25"] = round(v, 1)
                r["centroid_read"] = True
                r["confidence"] = "sparse"
            else:
                r["confidence"] = "none" if r["pm25"] is None else "sparse"
        else:
            r["confidence"] = "field"
        r["aqi"] = cpcb_aqi(r["pm25"])
        r["aqi_us"] = us_aqi(r["pm25"])
        cat, color = cpcb_band(r["aqi"])
        r["category"] = cat
        r["color"] = color
    return rows
