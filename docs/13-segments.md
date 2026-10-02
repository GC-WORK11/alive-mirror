# 13 — Segment hot-zones + live field surface

Two server modules that take the field from a *point* answer to a
*path + surface* answer.

## segments.py

Every `/route` and `/compare` option (road modes) is split into ~90-second
spans (`split_geometry`, time-proportional cuts — a fast leg gets longer
segments, a slow leg shorter, each span ≈ equal inhaled volume).

Each span is scored on the live field at **three** sample points —
midpoint + the two quarter points — then averaged. Midpoint-only
sampling misses peaks inside a span (a 1.5 km span can cross a ring
road).

Per span: `{start_frac, end_frac, minutes, coords, avg_conc_ugm3,
dose_ug, color}`. `color` is the map paint for that span
(slate → crimson → dark-red ramp on `avg_conc`).

`hotspots()` = the top-3 spans by share of total trip dose
(`share_pct`, `midpoint_coord`, `span_frac`). The app surfaces this as
"N% in one stretch" on an option row — the honest answer to
"where along this trip do I actually inhale it?" and it lets the UI
draw the polyline as a dose-heatmap instead of a flat line.

Metro option skips segmentation (its legs are walk→metro→walk with their
own physics) — `segments` absent on that row by design.

## grid.py + /grid

`GET /grid` → FeatureCollection of ~22×22 cells over the NCR bbox
(76.80,28.20 → 77.90,28.95). Each cell carries `pm25` (field value at
cell centre) and `conf` (`hi` < 5 km to nearest field sample,
`med` < 15 km, `lo` beyond — the same honesty rule the point API uses).

The app's `FieldLayer` paints it as a low-alpha single-hue ramp so the
basemap stays readable — you see *where the dirty air actually sits*
right now, not a categorical AQI choropleth.
