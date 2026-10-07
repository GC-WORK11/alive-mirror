# Lane report — air-map rebuild

Owner's order: "the air map" should be the admin-dashboard field MERGED with
the map — band colors, instrument numbers, an explanation, live location —
and REMOVE the 'from' component. Done, verified on iPhone 17 sim.

## What "the air map" is

The idle map surface (`phase === "idle"`, home closed) in `App.tsx`. Entry:
Home → "Air map" door row → `setHomeOpen(false)`. There is no separate screen;
the map IS the surface, so the field is painted inside the existing `MapTree`.

## What shipped

**`Mobile/src/api/airfield.ts` (new)** — `fetchAirField()` hits prod
`GET /grid?cells=28&param=pm2_5` through `fetchCached` (10-min TTL, inflight
dedupe, stale fallback). Returns the measured field (`basis: "recorded"`,
`cell_epoch[0]`). No new server endpoint needed — option (c), the vector grid
the web surfaces already use.

**`Mobile/src/components/AirFieldLayer.tsx` (new)** — always-mounted
GeoJSONSource, per the iOS-sim SIGSEGV law (empty FC = off, never unmount):
- `airfieldCells` fill layer: `pm25` → step expression at CPCB breaks
  30/60/90/120/250 → `V2T.band0-5`; `fill-opacity` by cell `conf`
  (hi .55 / med .38 / lo .20) — the confidence texture city.html paints, a
  notch stronger so the band reads as color, not tint. `beforeId:
  "v2-road-tunnel"` seats the field under roads/labels — traffic-layer seat.
- `airfieldValues` symbol layer (minzoom 10.5): each cell's own µg/m³ read —
  the field's blended instrument number, haloed, collision-thinned.
- `airStations` source: ring markers + names (minzoom 14.5) at the 54 real
  monitor positions from `/aqi`'s field block (`stations[]`).
Nothing invented: every cell, dot, and label came off the wire.

**`Mobile/src/components/AirMapCard.tsx` (new)** — glass legend card,
`pointerEvents="none"`: "the air map" · "redder = worse air right now" ·
6 band dots + "good → severe" · "{n} live stations" · field age line
(reuses howWe_fieldAge/cityStale/cityNoField keys).

**`App.tsx`** — boot `fieldPull` + 10-min interval re-poll with
`airFieldEpoch` dedupe (identical serves don't re-render the memo'd MapTree);
`fieldStations` memo off `/aqi`'s field block; SearchBar route pill and
FreshnessChip now render only in `phase === "compare"` — the 'from'
component is gone from the idle map (its `fromLabel`/`fromHint` strings were
already dead since c0dcf5e); AirMapCard + clearance offsets for the
offline/pick-hint pills.

**Contract** — no new server fields consumed: `FieldStatus.stations[]` +
`stations_src` already exist in `Bridge/contract.ts`; shadow added to
`Mobile/src/api/plan.ts`.

## Verified

- iPhone 17 sim (EDD9B083, iOS 26.5), dev-client build,
  `EXPO_PUBLIC_API_URL=http://65.2.28.40`:
  `docs/lanes/air-map-shots/02-field-delhi.png` + `04-field-stronger.png` —
  warm band field over Delhi with per-cell reads ("61"/"62"), legend card,
  live-location dot, no route pill.
- Live `/grid?cells=28` at capture time: 784 cells, pm25 54.5–136.4,
  conf hi 252 / med 484 / lo 48 → 4 bands on the field right now
  (44 sat, 424 mod, 302 poor, 14 vpoor). Color variation is real data, the
  step expression is the same one the web uses.
- Fast open: field is pulled at boot in the same effect as the `/aqi` poll,
  so on Air-map open the cells paint from cache — observed instant in sim.
- Stability: ~7 min sim session with the layer mounted and swapping
  EMPTY→field, zero crashes. One clean run, not a guarantee — the known
  iOS-debug SIGSEGV class (14/30) needs the KVM/Android lane's larger sample.
- Gates: `npx tsc --noEmit` clean · `npx expo lint` clean · node runners
  store 84 · nav 76 · api 12 · offline 12 — all pass.

## Not in scope / honest gaps

- Per-station pm25 values are not on the wire (`station_readings` is a count);
  the numbers on the map are the kriged cells' own reads. If he wants each
  station's raw number labeled, that's a server change (deploy-pending
  class) — flag it, don't fake it.
- Zoom-out band panorama verified via data distribution, not a screenshot —
  sim a11y pinch pans rather than zooms.
