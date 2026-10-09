# Air-map restyle lane — report

Owner's verdict on the old field: *"the air around me is all orange map — fuck you that is shit."*
The kriged PM2.5 cells painted at up to .92 fill-opacity — one flat band-colour
blanket that hid the streets it was measuring.

## What changed

`Mobile/src/components/AirFieldLayer.tsx` — the field is haze, not paint:

- **Fill alpha way down** — `fill-opacity` per confidence: `hi .32 / med .22 /
  lo .14 / default .20` (was `.92 / .60 / .34 / .45`). Every cell is ≤35%
  effective opacity; streets and labels read through at every zoom.
- **Continuous per-cell ramp, not banded steps** — `fill-color` is now an
  `interpolate` on the served `pm25` property across the same six anchors
  (band0→band5 at 0/30/60/90/120/250). Neighbouring cells step *subtly*
  between close tones instead of snapping band-to-band — the concentration
  gradient shows at a glance, the staircase lives in the gradient not in
  hard fills.
- **Edges feathered** — `airfieldEdges` line-width halved (0.25 → 1.0 by
  zoom) and `line-opacity` .20 (was .55). At NCR zoom the cell lattice reads
  as a fine woven texture; up close the cells just melt into the basemap.
- Values (`µg` labels, minzoom 10.5), station dots, station names,
  `gesturing` flag, and the mounted-source `on` contract are untouched.

`Mobile/src/theme.ts` — one new export: `bandFieldIdx(i)`, the band colour at
its painted hi-confidence alpha (.32) composited over the basemap's urban
land `#EDEAE3`. That is literally what a field cell reads as on the streets.

`Mobile/src/components/AirMapCard.tsx` — the legend swatches now paint
`bandFieldIdx` instead of the raw band chips, so "redder = worse" previews
the real on-map tone. Header (`{stations} live stations`) and the staleness
lines are untouched. Tap-readout untouched (verified live below).

## Legend honesty, verified numerically

Rendered legend dot #2 sampled at `#e1d3b4` vs computed
`bandFieldIdx(1) = #e1d3b3` — identical to within one rounding bit. Swatches
match the rendered field because they share the same composite math.

## Verification

Gates: `npx tsc --noEmit` clean, `npx expo lint` clean.

iOS 26.5 sim (iPhone 17), live prod field (88–90 µg morning haze), shots in
`docs/lanes/airmap-restyle-shots/`:

| Zoom | Before | After |
|------|--------|-------|
| Neighbourhood | `before-neighbourhood.png` — solid orange slab, streets crushed | `after-neighbourhood.png` — pink haze, every street + building legible |
| City | `before-city.png` — orange wash w/ hard cell edge | `after-city.png` — soft tint, band steps still visible (Connaught Place ↔ Central Ridge) |
| NCR-wide | `before-ncr.png` — heavy mosaic slab drowning city names | `after-ncr.png` — fine textured lattice, Karnal/Meerut/Aligarh all read |

Street names read through the field at all three zooms — the gate.

Feature-presence check while driving: tapping the map on the air-map
surface answered *"near G Block — platform — air there now ~88 µg/m³"* —
tap-readout intact; the legend card's "52 live stations · air reading: 1
min old" header line renders unchanged.

## Drive notes for siblings

- iOS sim zoom without a two-finger pinch: MapLibre's one-finger zoom —
  double-tap, hold the second tap, drag up to zoom out (script in this
  lane: `/tmp/dtapzoom.jxa` via `osascript -l JavaScript … x y yend`).
- iOS 27.0 sim window overlaps the 26.5 one — clicks near the window's
  top edge can hit the other sim's titlebar; move it or re-`AXRaise`.
- The a11y `press` on the Air-map door row works but needs ~2 dispatches;
  taps take 1-4 s to land — screenshot before concluding one failed.
