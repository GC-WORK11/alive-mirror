# Air-layer gating lane — report

Owner's rule: *"remove the colored maps until the user searches specifically for air around me or something like that — the where-to looks ugly with colored maps."*

## What changed

**One honest toggle** — `airLayerVisible` in `Mobile/App.tsx`:

```ts
airLayerVisible =
  (airMapOpen && !mapPickArmed) || phase === "place" || phase === "explore";
```

The PM2.5 field layer (`AirFieldLayer`) now paints **only while air intent is active**:

- the air-map readout surface (idle phase, home sheet lifted, no trip pick armed) — includes tapping the map for a readout and arriving there via an air query
- a place's air detail (settle sheet, `phase === "place"`)
- an air answers sheet (stays/playtime, `phase === "explore"`)

Everywhere else — home browsing, search, the where-to/compare chooser, nav — the basemap renders **plain**. Air numbers, chips, pills and delta rows are untouched: the data lives, the paint doesn't.

Implementation follows the mounted-source contract (the iOS-sim SIGSEGV law): `<AirFieldLayer>` gained an `on` prop that swaps the two GeoJSON sources to an empty FeatureCollection instead of unmounting — same convention as `FiresLayer`/`CorridorLayer`. The polled field still lands so turning back on paints instantly, stale-free.

## Air intent in search

New `airIntent(raw, parsed)` detector in `Mobile/src/search/explore.ts` — three honest branches, a miss returns null:

1. **Hard tokens** — `aqi`, `pollution`, `smog`, `haze`, `pm25/pm10`, `pradushan`, `dhundh`, `vayugunvatta`…, or any Devanagari air term (`हवा`, `वायु`, `प्रदूष`, `धुंध`, `एयर`, `पीएम`…) matched on the raw query (normalize() strips non-Latin).
2. **Pure air ask** — every token is an air word or a stop word (`air around me`, `hows the air today`, `हवा कैसी है`).
3. **Anchored head** — latin `air/aer/eyar` + a place phrase (`air karol bagh`). Guarded by `AIR_BLOCK` (`india`, `force`, `airlines`, `port`…) so 'air india' stays a place ask and 'hawa mahal' isn't hijacked (the head only accepts latin air spellings).

A hit renders one **"the air map"** row under the *air answers* section in SearchScreen (new i18n key `airIntentTitle`, en + hi). Selecting it emits `{ type: "air", nearQuery }` — a new `SearchSelection` variant. The shell lands the user on the air-map surface, flies to the anchor (bundled gazetteer for a named place, `posNowDetailed()` for "around me"), and drops the tap-read pin so the ask answers with a number, not just colour. The keyboard submit path picks the air row first when the query is an air ask.

## Route paint flattened

The where-to chooser and nav previously painted band-segmented route polylines — orange/brown chunks per PM2.5 span, which reads as "colored map". `RouteTint` layer colours are now flat constants:

- picked/ahead route → forest accent (`V2T.accent`, the app's one "go" colour)
- alternates + travelled span → quiet grey (`MAP_QUIET`)

The per-chunk `pm25`/`color` values still bake onto each feature as data — the pill and the route delta rows carry the air story in numbers, which is the feature.

## Verification

Gates: `npx tsc --noEmit` clean, `npx expo lint` clean, all mobile test runners green (store / nav / api / offline / search).

iOS sim shots in `docs/lanes/air-gate-shots/`:

| Shot | State |
|------|-------|
| a — home cold | plain basemap, zero colored cells |
| b — "air around me" | field paints + tap-read pin |
| c — where-to flow | plain map + route + delta rows intact |
| d — back out | plain again |
