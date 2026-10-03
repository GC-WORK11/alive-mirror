# 03 · Design system — dark, detailed, calm

## Look
Night-map aesthetic: near-black canvas, crisp grey roads, white labels, colour reserved for meaning. References: Google Maps dark/navigation mode, Pixel "Maps" dark, Mobbin map screens (bottom-sheet + pin patterns). Not glass, not neon, not gradients.

## Colour tokens
| Token | Hex | Use |
|---|---|---|
| `bg` | `#0B0D10` | app background, sheets |
| `surface` | `#15181D` | cards, sidebar rows |
| `surface2` | `#1E2228` | pressed, inputs |
| `line` | `#2A2F36` | hairlines |
| `text` | `#F2F4F7` | primary text |
| `text2` | `#A3AAB5` | secondary |
| `text3` | `#6B7280` | tertiary, disabled |
| `accent` | `#4C8DFF` | the one interactive colour: buttons, route, puck |
| `breath` ramp | `#F2C14E → #F08A3C → #E5484D` | smoke you breathe: light → heavy (warm, single direction) |
| `out` ramp | `#9AA4B2 → #6E7A8A → #3E4754` + outline | smoke your ride puts out (cool greys; reads as exhaust) |
| `good` | none | lightness is shown by *absence* of colour — no green |

Contrast: all text ≥ 4.5:1 on `bg`/`surface` (checked with a contrast tool at implementation).

## Type
- **Inter** (OFL) for everything; tabular numerals (`fontVariant: ['tabular-nums']`) for every number.
- Noto Sans Devanagari for Hindi.
- Scale: 34 (receipt hero) · 22 (titles) · 17 (body) · 15 (secondary) · 13 (labels). Weights 400/500/600 only.

## Icons
- One family: Material Symbols Rounded (Apache 2.0), 24 px grid, outline at rest, filled when selected.
- Mode icons: walk, cycle, scooter/bike, auto (custom glyph drawn on the same grid), car, cab, bus, metro.
- Map pins: Google-style pinlet (rounded, category glyph inside), destination red `#E5484D`, origin white ring.

## Shape, spacing, elevation
4-pt grid. Radius: 12 (rows), 20 (sheets), 999 (search bar, chips). One shadow level for floating controls; sheets use `surface` with a 1-px `line` top edge.

## Motion
- Sheets: spring (damping 22, stiffness 220); 3 detents (peek 15%, half 50%, full 92%).
- Counters: numbers interpolate every 1 s, never jump; easing linear.
- Camera: `easeTo` 600 ms for route fit; follow mode 1 Hz updates with 900 ms ease so the puck glides.
- Respect "reduce motion".

## Map styling (Amazon Location "Standard" Dark, political view IND)
Verified: style descriptor has 160 layers over sources `roads, buildings, pois, places, water, landuse, boundaries, earth` [V]. Runtime overrides via MapLibre layer props:
- Desaturate POI icon colours to `text2`; keep transit (metro) icons coloured by line.
- Roads: motorways `#3A4049`, primaries `#2E333A`, minor `#24282E`; labels `text2`.
- Buildings: `fill-extrusion` at z≥15, `#1C2026`, height from tile data.
- Water `#0E1A24`, parks `#121A15` (barely tinted).
- Our layers on top: route (accent, 6 px, casing 9 px `bg`), breath heat along route (breath ramp), city field (only in "Delhi today").

## Accessibility
Dynamic type up to 130% without layout break; every control has an accessibility label; colour never the only signal (bars have length, routes have labels).
