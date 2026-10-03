# Map style — r4 palette pass (lane `r4-mapstyle`)

Restyle of `Mobile/src/map/v2-dark.json` (same 47 layers, same `openmaptiles`
source/schema — drop-in). Driver complaint fixed: greenish, muddy, "cheap".
Validated with `@maplibre/maplibre-gl-style-spec` `validateStyleMin` — 0 errors;
all 13 `source-layer`s exist in the local tilemaker config
(`scripts/geo/config-openmaptiles.json`).

## What changed

**Green → graphite.** `#121A15` (3 uses: `v2-landcover-green`,
`v2-landuse-park`, `v2-park`) replaced by neutral cool-graphite land tints in
the V2T ink family (hue ~215°, no green channel dominance):

| Layer | Was | Now |
|---|---|---|
| `v2-landcover-green` | `#121A15` @0.85 | `#141920` @0.8 |
| `v2-landuse-park` / `v2-park` | `#121A15` @0.9 | `#151B22` @0.9 |
| `v2-landuse-urban` | `#0D1014` | `#0D1116` |
| `v2-landuse-institution` | `#101419` | `#10161D` |

**Water → ink-navy.** `#0E1A24` read teal next to the green land; now a deep
navy `#0C1726` with waterways lifted to `#1D3D5F` and water labels `#4E7299`
(was `#3E5C77`) so the Yamuna/canals stay legible.

**Roads → slate ramp, luminous edges on majors.** Inner colors stepped up the
graphite→slate ramp; motorway/trunk/primary casings are now *brighter* than
their inner fill (lit-edge look) instead of near-black, keeping the arterial
hierarchy readable at a glance:

| Class | Inner | Casing |
|---|---|---|
| service | `#21262E` | — |
| minor/track | `#252B33` | — |
| links | `#29313B` | — |
| tertiary | `#2C3440` | `#10151B` (dark edge) |
| secondary | `#323B48` | `#121820` (dark edge) |
| primary/trunk | `#3D4757` | `#4A5668` (brighter) |
| motorway | `#4B5A70` | `#5C6B84` (brighter) + glow `#4B5A70` @0.3 |
| rail | `#4A5666` | ties `#0B0D10` |
| metro/transit | `#6E8098` | `#0F141B` |

**Labels on the V2T ramp.** Stale `#6B7280` / one-off `#8A94A1` / `#8B98A8`
replaced by theme values only: primary `#F2F4F7` (city), mid `#A3AAB5`
(town/village/station/major road names), secondary `#8A94A0` (everything
else). Halos stay `#0B0D10`.

## Noise reductions

- `v2-building-flat`: minzoom 13→14, opacity ramp 0.5→0.85 cut to 0.4→0.72 —
  Delhi blocks no longer carpet the map at mid-zoom; texture arrives at street
  level. Extrusion opacity 0.6→0.55, color `#1F2630`.
- `v2-poi-label`: classes 10→6 — kept `fuel`, `charging_station`, `hospital`,
  `parking`, `bus_station`, `airport`; dropped `gas_station` (dup), `bus`,
  `ferry_terminal`, `police`. `text-padding` 20→24.
- `v2-place-neighbourhood`: dropped `hamlet`, `isolated_dwelling`.
- `v2-landuse-institution`: dropped `bus_station` (polygon clutter).
- `v2-road-label-minor`: `symbol-spacing` 500→600, `text-padding` 16→20.

## Overlay readability (route + breath gradient)

Basemap is now strictly cool-hued and dim: brightest surface is motorway
`#4B5A70` (rel. luminance ≈0.10). Accent `#4C8DFF` and the warm breath ramp
`#F2C14E`→`#F08A3C`→`#EE5A5F` sit on opposite hue/luminance poles — both the
route casing halo and a `line-gradient` breath overlay will read cleanly.
Nothing warm remains in the basemap; warm = air quality, by design (doc 03:
"colour reserved for meaning").
