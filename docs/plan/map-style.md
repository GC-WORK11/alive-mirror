# Map style — v2 dark vector (ALive-108)

Self-contained MapLibre style JSON on the **OpenMapTiles v3 schema** —
`Mobile/src/map/v2-dark.json`. 47 layers, validated with
`@maplibre/maplibre-gl-style-spec` `validateStyleMin` (0 errors). It replaces
the remote `https://tiles.openfreemap.org/styles/dark` URL the app currently
renders; same schema, same `openmaptiles` source name, same default tile
endpoint, so adoption is a drop-in — no data change until the Delhi PMTiles
land.

## Integration (one line)

```tsx
import { v2StyleUrl } from "./src/map";
<Map mapStyle={v2StyleUrl()} …>   // in App.tsx, replacing STYLE_URL
```

Then delete the inline `buildings3d` `<Layer>` (App.tsx ~L142) — the style
already carries `v2-building-extrusion`; keeping both double-renders.

## Tile-source chain — `v2StyleUrl()`

| # | Source | Trigger | Result |
|---|---|---|---|
| 1 | `EXPO_PUBLIC_TILES_URL` env | set by the Delhi-PMTiles lane | `withVectorTiles()` re-points `sources.openmaptiles` — `pmtiles://…`/`*.pmtiles` → `url` (protocol handled by MapLibre Native), `…{z}/{x}/{y}…` → `tiles[]`, anything else → `url` (TileJSON) |
| 2 | `delhi.pmtiles` in `Paths.document` (download) or `Paths.bundle` | file exists at resolve time | `pmtiles://<file uri>` in the same style |
| 3 | hosted OpenFreeMap planet | always available | `v2Style` as shipped — `url: https://tiles.openfreemap.org/planet` |
| 4 | `v2RasterStyle` export | integrator swaps on persistent vector load failure (offline/`onDidFailLoadingMap`) | desaturated/dimmed OSM raster — emergency only, no labels styling; mind OSM tile ToS |

`EXPO_PUBLIC_GLYPHS_URL` overrides the glyphs template (the style's only
remote dependency besides tiles — no sprite is used; all markers are text or
vector RN components). For a fully offline build, the tiles lane should also
bundle a `{fontstack}/{range}.pbf` glyph set (`Noto Sans Regular/Bold/Italic`,
must include Devanagari ranges for `name:nonlatin`) and point this env at it.
Note: `EXPO_PUBLIC_*` is inlined at build time — env changes need a rebuild.

## Token → style mapping

| V2T token | Hex | Style usage (layer ids) |
|---|---|---|
| `bg` | `#0B0D10` | `v2-background`; text halo on every label; rail tie overlay `v2-rail-ties` |
| `mapMotorway` | `#3A4049` | `v2-road-motorway`, motorway `v2-road-bridge`, `v2-road-arterial-glow` halo |
| `mapPrimary` | `#2E333A` | `v2-road-primary` (trunk+primary), non-motorway `v2-road-bridge` |
| `mapMinor` | `#24282E` | `v2-road-minor`, tunnel fallback in `v2-road-tunnel` |
| `mapBuilding` | `#1C2026` | `v2-building-flat` (z≥15 color), `v2-building-extrusion` |
| `mapWater` | `#0E1A24` | `v2-water` |
| `mapPark` | `#121A15` | `v2-landcover-green`, `v2-landuse-park`, `v2-park` |
| `surface2` | `#1E2228` | `v2-aeroway-line` |
| `line` | `#2A2F36` | `v2-boundary-country` |
| `text` | `#F2F4F7` | `v2-place-city` labels; puck ring (markers.tsx) |
| `text2` | `#A3AAB5` | `v2-road-label-major`, village/town place labels (doc 03: road labels `text2`) |
| `text3` | `#6B7280` | minor road/POI/neighbourhood/state/country labels |
| `accent` | `#4C8DFF` | reserved for interactive overlays (route, puck) — not in basemap |
| `pinDest` | `#E5484D` | `DestPin` marker only |

Derived (documented, not tokens): casing `#12161C`, tunnel/bridge dimming via
opacity, waterway `#17314A`, rail `#414B58` + tie overlay, **metro steel
`#5F6F84`**, urban landuse `#0D1014`, institutions `#101419`, service
`#20252B`, tertiary `#262B32`, secondary `#2B3038`, link `#262B32`, water
labels `#3E5C77`, station dots `#9AA4B2`, suburb `#8A94A1`.

## Layer order & emphasis

Canvas → green/landuse → water → aeroway → boundaries → buildings → **tunnels**
→ service/minor/link → tertiary → secondary → **arterial glow → casing →
motorway** (brightest on canvas, the driving hierarchy) → rail → metro →
**bridges** (on top) → station dots → road labels → POI → place labels.

- **Emphasize**: motorway/trunk — bright fill + 30% glow halo + dark casing;
  elevated roads (`brunnel=bridge`, trunk/primary/motorway) drawn last in the
  road stack so flyovers read over surface streets.
- **De-emphasize**: pedestrian/path/cycleway/track — dropped entirely (driver
  POV); service roads ≥z14.5; minor ≥z12.5; housenumber/peak layers omitted.
- **Metro**: `transit`/`subway` class → steel `#5F6F84` line + `#10141B`
  casing, underground sections dashed at 45% opacity; stations get
  `#9AA4B2` dots + labels at z≥13. Mainline `rail` is dimmer with tie ticks.
- **Buildings**: flat fill z≥13 ramping to `#1C2026`, `fill-extrusion` z≥15,
  height `render_height`→`height`→10 m, base `render_min_height`, opacity
  0.6, no vertical gradient (doc 03 spec).

## Zoom behavior

| Zoom | What appears |
|---|---|
| 1–5 | countries, states, cities, water, country borders, motorway (≥5) |
| 8–10 | trunk/primary, rail, town labels, secondary casing |
| 11–12 | secondary/tertiary, metro lines+casing, aeroway, suburb labels |
| 12.5–13 | minor roads, flat buildings, station dots/labels, arterial road names, neighbourhood labels |
| 14.5–15 | service roads, **building extrusions**, minor road names, driver POIs |
| 16+ | full density — nothing new appears, widths/labels grow |

## POI decluttering (driver-only)

Only `fuel`, `gas_station`, `parking`, `hospital`, `charging_station`,
`bus`/`bus_station`, `ferry_terminal`, `airport`, `police` at z≥15, plus
`subway`/`railway`/`transit` station labels at z≥13. No icons (no sprite) —
text-only, `text3`, rank-sorted. Shops/food/attractions are intentionally
absent.

## Handoff notes

- **Delhi PMTiles lane**: ship OpenMapTiles-schema tiles, then either set
  `EXPO_PUBLIC_TILES_URL=pmtiles://…` (env) or drop `delhi.pmtiles` into
  `Paths.document`/`Paths.bundle` — `v2StyleUrl()` picks it up with no code
  change here. Glyphs: bundle `Noto Sans Regular/Bold/Italic` ranges incl.
  Devanagari and set `EXPO_PUBLIC_GLYPHS_URL`.
- **Amazon Location (doc 04)**: if the Amazon `Standard/Dark` descriptor
  becomes the basemap instead, keep this JSON as the offline fallback; the
  look transfers via `buildingLayers` + `roadGlowLayers` — re-point
  `source`/`source-layer` (Amazon sources are themed: `roads`, `buildings`,
  …) and swap property names (`render_height` → their height field).
- **Markers**: `DestPin`, `OriginPin`, `UserPuck` in `src/map/markers.tsx`
  replace `EndpointPin` for new screens; reference SVGs in `assets/map/`.
- **Labels**: `name:latin` → `name_en` → `name` (English-first for glanceable
  driving); add `name:nonlatin` second lines later if needed — glyph ranges
  already exist on the hosted font server.
