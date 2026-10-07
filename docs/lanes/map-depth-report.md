# Map depth pass — "GTA Vice City" → street-level (lane r6, 7 Oct 2026)

Owner verdict: map is smooth but feels like GTA Vice City — wants
every route, every street, block-to-block density, Google Maps feel.

## Diagnosis: style gap, not a data gap

Both tile sources the app can render already carry the full
OpenMapTiles schema:

| source | status | contents |
|---|---|---|
| bundled style → hosted OpenFreeMap planet | **default in app** (no `EXPO_PUBLIC_TILES_URL` set anywhere) | minor/service roads, buildings, housenumbers, one-ways, POIs, locality names — full planet, all zooms |
| prod `GET /tiles/delhi.pmtiles` | live, 22.7 MB, z0–14, NCR bbox, 1644 tiles | same OMT layers: transportation + transportation_name z4–14, building z13–14, housenumber z14, poi z12–14, landuse/landcover, park, water, aeroway |

The "empty" look had three style-side causes:

1. **minzooms hid the data** — minor roads only from z12.5, service
   z14.5, tracks z14, paths z14.5, buildings z14, housenumbers z16.5,
   one-ways z16, minor street-name labels z14.5, neighbourhood labels
   z12.5. At the app's opening zoom (z11) nothing but arterials and
   top-level locality names existed on screen → the Vice City look.
2. **hairline minor roads, no casing** — Google draws streets as white
   ribbons on a soft grey casing; ours drew a single thin line, so the
   mesh read as texture, not streets.
3. **opening camera z11** — first frame landed below the street-mesh
   regime entirely.

Conclusion: nothing to buy, nothing to rebuild. Fix the style + open
deeper + prefetch.

## What changed (Mobile only, ₹0)

`Mobile/src/map/v2-light.json` (+271 lines):

- minor roads z12.5→**z12**, slightly wider, + new `v2-road-minor-casing`
  (white ribbon over warm-grey edge — the Google look)
- service roads z14.5→**z13.5** + new `v2-road-service-casing`;
  track z14→13.5; path z14.5→14
- buildings z14→**z13**; one-way arrows z16→15; housenumbers z16.5→**15.5**
- street-name labels (minor) z14.5→**13.5**; neighbourhood z12.5→12;
  suburb z11.5→11; park labels z11.5→11
- POIs: civic z13.5→13; services + text z15.5→15
- `v2-landuse-urban` differentiated per class (residential / commercial /
  industrial warm tints); water pulled to quieter cyan `#9CD5E8`
- everything added is warm-neutral — dose colors stay the only
  saturated hues on the map, so segment colors and the field overlay
  keep reading against the denser base

`Mobile/App.tsx`:

- `INIT_VIEW` zoom 11 → **12.5** — first frame lands inside the
  street-mesh regime instead of on empty arterial-only tiles
- `onDidFinishRenderingMapFully` → `onMapFullyRendered`: still calls
  `onMapIdle`, plus kicks the one-time basemap prefetch

`Mobile/src/map/tileWarm.ts` (new):

- after first full render, `OfflineManager.createPack` prefetches the
  NCR bbox **z9–13** (~630 tiles ≈ 40–55 MB worst case; outer-NCR tiles
  are sparse so real figure is lower), once per install, in the
  background — panning the service area reads disk, not the network,
  and the demo map survives venue-wifi death
- ambient cache ceiling raised to 160 MB so the pack and everyday
  browsing can't evict each other
- z14 deliberately excluded (~1.7k tiles / ~200 MB); z14+ streams live
  and sticks in the ambient cache
- fails silent: offline DB unavailable → app behaves exactly as before

`Mobile/src/nav/drawHold.test.ts` updated for the handler rename.

## Verification

Render harness (`/Users/devin/mapdrive/`: maplibre-gl + CDP shots of
the real style JSON — same style object the app renders).
Shots in `docs/lanes/map-depth-shots/`:

- `before-z11.png` vs `after2-z125.png` vs `google-z125.png`:
  z11 showed arterials + locality names only; z12.5 now shows the
  street mesh, suburb/neighbourhood labels, metro icons
- `before-z13.png` vs `after2-z13.png`: minor-road ribbons now carry
  casing edge definition; label density up
- `before-z15.png` vs `after2-z15.png`: every street named,
  housenumbers, one-way arrows, building footprints, parking/POI icons

Honest "how close to Google for ₹0": at **z13+ we're at Google's
street-level coverage** — same OSM-derived data, every block drawn and
named. What we don't have: brand POIs with ratings/photos, Google's
traffic layer, landmark pictograms, and Google's road-class palette is
greyer (ours keeps warm-yellow arterials — deliberate, matches the
app's warm register). For a PM2.5 dosimeter the gap that mattered —
street-level orientation — is closed.

iOS sim verification (dev build, iPhone 17 sim, location spoofed to
Delhi — `ios-z13-nd.png`, `ios-z135-nd.png`, `ios-z14-nd.png`,
`ios-z15-nd.png`, `ios-z16-nd.png` in `map-depth-shots/`): the new
style renders on-device as the harness predicted — at z13 the CP /
New Delhi minor mesh is complete with casings; z15–16 shows named
streets on every block, housenumbers, one-way arrows, building
footprints, POI icons. The dose-over-Delhi marker and the live
`now ~62 µg/m³` read still render over the denser base — nothing
saturated competes with the air colors.

Offline pack verified on-device: `.mapbox/cache.db` holds the
`delhi-ncr-z9-13-r1` region — 744 region tiles, 27.4 MB total
(under the 55 MB worst case; outer-NCR tiles are sparse as
predicted). Panning the service area is disk-read; venue wifi
loss can't blank the demo map.

## Rejected / not done

- **Amazon Location free tier**: not needed — data was never the gap.
  Would need console key creation (owner step) + re-pointing every
  layer to the themed source for zero gain. Steps not documented since
  we don't recommend it; if OFM ever dies, `v2RasterStyle` (OSM raster)
  and `EXPO_PUBLIC_TILES_URL` → prod delhi.pmtiles (NCR-only, no
  outside-NCR basemap) are the existing fallbacks.
- **z14 prefetch**: ~200 MB on-device — wrong trade; z9–13 covers every
  region→street transition and deeper zooms stream fine.

## Checks

- `node src/nav/test-runner.mjs`: 76/76 pass
- `npx tsc --noEmit`: clean
- `npx expo lint`: clean
