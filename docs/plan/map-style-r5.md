# Map style — r5 detail pass (lane `app-map`)

`Mobile/src/map/v2-light.json`: 47 → 62 layers, same keyless sources
(`tiles.openfreemap.org` vector + fonts). Goal: Google-Maps-grade density —
buildings, housenumbers, POI icons, landmark-level labels — while keeping the
light graphite/ink palette.

## What changed

- `sprite` added: `tiles.openfreemap.org/sprites/ofm_f384/ofm` (264-icon
  osm-liberty set). Icons are greyscale; labels carry the hierarchy.
- `terrain-dem` raster-dem source: AWS Terrarium (`elevation-tiles-prod`,
  no key, maxzoom 15) → `v2-hillshade` (exaggeration 0.3 — Delhi is flat,
  only the Aravalli ridge reads).
- New detail layers:
  - `v2-waterway-name` — Yamuna/canals/drains (z13+, italic, water colour)
  - `v2-road-pedestrian(-casing)` — pedestrian precincts (z14+)
  - `v2-road-path` — footway/cycleway/steps/bridleway dashed (z14.5+)
  - `v2-road-track` — tracks split out of `v2-road-minor`, dashed (z14+)
  - `v2-oneway` — `oneway` sprite arrows, `icon-rotate` handles `oneway=-1` (z16+)
  - `v2-housenumber` — housenumber points (z16.5+, collision-managed)
  - `v2-aeroway-label` — aerodrome_label: `airport`/`airfield`/`heliport`
    icons + names (z8.5+, so IGI/Hindon show early)
  - `v2-peak` — mountain_peak + name (z11+, Aravalli outcrops)
  - `v2-park-label` — park source-layer names, italic sage (z11.5+, rank-sorted)
  - `v2-landcover-farm` / `v2-landcover-sand` — farmland/scrub and sand/beach
    split out of the green fill so farmland reads pale
- POI icon tiers replace `v2-station-dot` / `v2-station-label` / `v2-poi-label`:
  - `v2-poi-transit` (z12+): subway/light_rail/tram → `railway_metro_11`,
    railway → `railway_11`, bus/ferry/aerialway icons. Metro stations are
    landmarks — they surface early.
  - `v2-poi-civic` (z13.5+): hospital/school/college/police/fire/post/embassy/
    monument/museum/zoo/stadium/cemetery/place_of_worship (+ muslim/christian/
    jewish religious icons; hindu/sikh → generic worship icon — no hindu icon
    exists in the set).
  - `v2-poi-services` (z15.5+): fuel/parking/restaurant/cafe/lodging/bank/atm/
    cinema/playground/pitch etc.
  - `v2-poi-gate` (z16.5+): metro gate/entrance names — "Gate No. 3" matters.
  - `v2-poi-text` (z15.5+): text-only catch-all for named POIs not in the icon
    classes; junk classes excluded (lift_gate, bench, waste_basket, fountain…).
- Label density: minor road labels z15 → 14.5 (spacing 600 → 420, classes
  +path/track/pedestrian), major spacing 350 → 300, neighbourhoods z13 → 12.5.
- `symbol-sort-key` on POIs uses OMT `rank` so the collision manager drops
  the least important features first.
- Bilingual labels (r5.1): road-label-major, poi-civic, poi-transit and
  neighbourhood/suburb place labels render `latin\nDevanagari` — the
  Google-Maps local-script pattern. Second line comes from `name:hi`
  (OMT's Delhi `name` tag is English; `name:hi` carries देवनागरी), and is
  suppressed when `downcase(name:hi)` equals `name` or the latin —
  romanized `name:hi` values (e.g. "Eastern Court") don't duplicate.
- App.tsx: deleted the inline `buildings3d` fill-extrusion layer — it
  double-drew on top of the style's own `v2-building-extrusion` (which also
  honours `render_min_height`). See map-style.md §cleanup note.

Validated with `@maplibre/maplibre-gl-style-spec` `validateStyleMin` — 0 errors.

## Still keyless

Vector tiles, sprites and glyphs all come from `tiles.openfreemap.org`;
hillshade comes from AWS Open Data Terrarium. No API keys anywhere.
