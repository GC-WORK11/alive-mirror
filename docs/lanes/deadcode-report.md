# Dead-code lane — report

Lane scope: verify every server-audit / mobile-audit dead-code claim against
HEAD (incl. string-dynamic refs — `getattr`, `importlib`, `D[...]` lookups,
computed `Glyph` sources, barrel imports), widen the net to never-imported
files / never-called functions / impossible branches / always-off flags /
large commented blocks / duplicate helpers / dead exports, remove only what
is verifiably dead, keep every gate green, and flag docs-debt without
fixing it.

Gates at HEAD of lane work: server `PYTHONPATH=core/build312:. .venv312/bin/python -m pytest -q tests`
(green); Mobile `npx tsc --noEmit` + `npx expo lint` (clean) + the four
`test-runner.mjs` suites 170/170 pass.

## Removed — commit refs

### `b8552f2` — server/

| Item | Location | Verdict evidence |
|---|---|---|
| `WIND_GONE_S` | `server/v2/why.py` | Module constant, zero reads anywhere; introduced in 0908d9a and never wired. |
| `_lev_le1` | `server/v2/gazetteer.py` | Typo-tolerance helper, zero calls; added in f73f287 but the typo bucket was never adopted — `_lev_bound` is the live sibling actually called. |
| `city_median` | `server/core/bench/bench_krige.py` | Bench helper, zero callers. |
| `bias_s` → `_bias_s` | `server/validate_field.py` | Tuple slot unpacked but never read (the row uses `bp_s`). |
| `nearest_stop` | `server/transit_real.py` | Public helper, zero callers since a840f32; not a route, not in `__all__`, no docs/demo-script reference. |

### `f9c23c4` — Mobile/

| Item | Location | Verdict evidence |
|---|---|---|
| `markers.tsx` (file) | `src/map/` | `DestPin`/`OriginPin`/`UserPuck` never rendered — app draws endpoints via MapLibre `Marker`/`UserLocation` + `Icon`. Design-review SVGs in `Mobile/assets/map/` kept. |
| `index.ts` (file) | `src/map/` | Barrel re-export, zero importers; style helpers are imported directly from `./style`. |
| `cacheGet` | `src/api/cache.ts` | Superseded by `cachePeek` (last-good read); zero callers. Header comment updated to the one remaining read mode. |
| `label` field + `labelFor` | `src/offline/status.ts` | English-only pill text never rendered — `App.tsx` builds the pill from `t()` keys; also an i18n gap, not just dead code. |
| `VEHICLE_CLASSES`, `YEAR_BANDS` | `src/store/vehicle.ts` | Alias re-export line, zero consumers. |
| `bandWashMidIdx` | `src/theme.ts` | Zero call sites (siblings `bandWashIdx`/`bandWashDeepIdx`/`bandEdgeIdx` all live). |
| 11 glyphs | `src/icons.tsx` | `bookmark`, `cigarette`, `collapse`, `expand`, `forkL`, `forkR`, `help`, `lungs`, `nature`, `nearMe`, `pinDrop` — union members + `D` entries removed. Verified no `D["name"]`/`D["name@fill"]` string refs (`bolt` is the only internally-referenced glyph, kept) and no computed `Glyph` source reaches them (`MANEUVER_GLYPH`, `MODE_STRIP`, `vehicleGlyph`, `reportGlyph`, `CategoryIcon` map, chip/drawer pill lists — all use live names only). |

## Verified dead-but-kept — and why

- `BreathEdge` (`src/ui.tsx`) — zero JSX renders, but it is the register's
  documented signature motion ("soul of the register"); removing design
  vocabulary is an owner call, not a hygiene call.
- `AlertBanner` (`src/ui.tsx`) — zero mounts; design spec reserves it for
  GRAP-level events (docs/plan/24-design-language-spec.md §250) — dormant by
  intent / feature-flaggable.
- `v2RasterStyle`, `buildingLayers`, `roadGlowLayers` (`src/map/style.ts`) —
  integrator style-kit fragments documented in docs/plan/map-style.md;
  unused in-tree by design.
- `V2_TILES_ENV` / `V2_GLYPHS_ENV` / `V2_PMTILES_NAME` (`src/map/style.ts`) —
  env-var contract for the tiles lane. Reads must stay `process.env.EXPO_PUBLIC_*`
  literals (Metro inlines them at build time) — the constants can't be
  substituted into the reads, they document which vars to set.
- `n_drift` (`server/core/ref_krige.py`) — mirrors C++
  `KrigeField::n_drift` (bindings_krige.cpp); parity API, not dead.
- `transit_rt.py`, `snapshot_gc.py`, `iitm_probe.py` — dormant maintenance
  tools (prior codebase-audit adjudication: intentionally unwired).
- `server/tools/bake_*.py` — one-time bakers whose artifacts ship in
  `server/static/`; documented manual tools.
- `server/test_api.py` — documented 46-assert live smoke tool (runs against
  prod, GET-only).
- v1 REST surface + `/v2` alias routes — documented public API; owner law:
  no feature removal even if a route looks quiet.
- `src/map/routeTint.test.ts` — self-documented manual self-test
  (`npx tsc … + node`); kept, flagged below as unwired.
- `Mobile/assets/map/*.svg` — design-review sources for the (removed)
  runtime pin kit; assets, not code.

## Audit claims verified already-gone (prior lanes)

- `postTrip`/`src/api/trip.ts`, `src/components/FieldLayer.tsx` — deleted by
  the fix-mobile-audit lane (4bfcdb9); zero refs at HEAD.
- Sidebar `|| true`, `OnboardingScreen:160`, `CompareSheet` stale comments —
  fixed in 4bfcdb9.
- `OSRM=`, `MAX_OD_KM`, `APP_MODES`, `CATALOG_UUID`, `KEY_FMT`, `CLUSTER_KM`,
  `_load_fields`, `_anchor_row`, `_pack_i16`, `districts_meta`,
  `get_ledger_store`, `fmFindDistrict`, `carry_i` — removed by the
  codebase-hygiene lane; zero grep hits at HEAD.
- FastAPI route-handler defs and tuple-unpacked binary-header fields
  (`tiles.py`, `routegraph.py`) were vulture false positives — live.

## Docs-debt — flagged, not fixed

1. `Mobile/AGENTS.md` prescribes Expo Router: "Routes live in `src/app/`…
   every file there is a screen". The app has no `expo-router` dependency
   and no `src/app/` — navigation is a hand-rolled stack in `App.tsx`.
   Actively misleading for a new contributor.
2. `docs/plan/offline.md:12` — module table lists `cacheGet` (removed in
   f9c23c4); the row should name `cachePeek` as the only read mode.
3. `docs/plan/perf-ram.md:34` — fix suggestion says "delete a stale file on
   `cacheGet` miss"; the read it means is now `cachePeek`.
4. `docs/plan/map-style.md` — documents the `src/map/` pin kit
   (`DestPin`/`OriginPin`/`UserPuck`) and the `./src/map` barrel
   integration snippet; both files removed in f9c23c4.
5. `ReceiptSheet.tsx` header comment (~line 112) describes a "cigarette
   glyph mark" on the dose ruler — the ruler never rendered that glyph
   (tick only), and `cigarette` is now removed from the icon set. Comment
   was stale before this lane; now doubly so.
6. `src/map/routeTint.test.ts` — the only `*.test.ts` outside a
   `test-runner.mjs` directory; it only runs via the manual
   tsc-emit + node recipe in its own header. Either wire it into a runner
   or accept it as a manual check.
7. `server/v2/why.py` wind-gating: `WIND_GONE_S`'s comment promised a wind
   staleness gate that was never implemented — the gate itself is
   (pre-existing) docs-debt in the same file, now noted rather than
   orphaned by the removed constant.
