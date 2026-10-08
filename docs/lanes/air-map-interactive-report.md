# Air-map-interactive report — tap-to-read the air field

Lane: `air-map-interactive`. Owner's ask: *"I can click area-wise and see the
AQI of each area around me, like admin tiles but on the map, so somebody asks
which area is safer I can just look."* The band-colored field overlay already
painted; this lane adds the readout: tap the map → `N µg/m³ — band · locality`
anchored to the same cell the paint came from.

- **Branch:** `base/v2` @ commit `360cd2c` (pushed)
- **Device:** iOS 26.5 sim (iPhone 17), dev-client build at `360cd2c`, Metro
  `EXPO_PUBLIC_API_URL=http://65.2.28.40` (prod ALB, GET-only)
- **Field under test:** `/grid?cells=28&param=pm2_5` → 784 cells over the NCR
  bbox; `air reading` live from prod (`53 live stations`)

## What was built

- `sampleFieldAt(fc, lat, lon)` (`src/api/airfield.ts`): bbox-containment scan
  over each feature's ring — cells are server-emitted axis-aligned rectangles
  (server/grid.py), so the tap answer is the *painted* value by construction;
  read and tint can never disagree. Holes/outside → honest `null`.
- `src/components/TapReadout.tsx`: `TapPin` (band-washed chip parked
  always-mounted per the draw-hold law — child swaps `<View/>`/pin, never
  mounts mid-gesture) and `TapReadout` (band dot + mono numeral + band word +
  locality + ✕; `pending` → "reading…", outside+fallback-dead →
  "outside the air map — no read here").
- `App.tsx`: `onMapPress` branches — armed pick still wins; a bare tap on the
  air-map surface (`phase==="idle" && !homeOpen`) drops the read. `/aqi?lat,lon`
  fallback only for points outside served cells, keyed `tap@epoch` (prefers
  `pm25_ambient` — the value domain cells paint), `conf:"model"`. `fieldGeo`
  in the memo's deps re-samples the same point on every field refresh — the
  read tracks the live field. Clears on leaving the surface.
- Locality via `localityAt` (bundled gazetteer, offline). en+hi strings
  (`tapHint`, `tapReading`, `tapOutside`, `tapHere`, `tapAqiA11y`).

## Device verification

Sim location set to Delhi (28.6139, 77.2090). Field renders colored; pans and
pinch zooms stayed smooth through ~20 gestures (no crash, no hitch).

| tap | readout | cross-check |
|---|---|---|
| Teen Murti area (golden) | **56 µg/m³ — satisfactory** | cell@TeenMurti = 55.6 → 56 ✓ |
| Delhi Sadar (deeper orange) | **63 µg/m³ — moderate** | distinct band+value ✓ |
| NIPGR (golden) | **54 µg/m³ — satisfactory** | cell@JNU area 56.5, tap point's cell 54 ✓ |
| Madhuban Enclave | **51 µg/m³ — satisfactory** | fourth distinct value ✓ |
| ✕ close | card+pin cleared, hint restored | — |
| dead-API relaunch | field paints from `fetchCached` last-good; tap → **56 — New Delhi** | fully local read ✓ |

Readouts are the containing cell's `pm25` — by construction identical to the
paint; `/aqi` `pm25_ambient` at the same spots lands within a few µg (the cell
is an area aggregate, the endpoint a point read — same field, different
density). Values shown are the served surface, not invented.

- `air-map-interactive-shots/tap-verify.mp4` — ~7 min clip: field open →
  locate → 4 taps → close → offline relaunch → offline tap → back online.
- `tap1-golden.jpg` `tap2-orange.jpg` `tap3.jpg` `offline-tap.jpg`

## Not exercised on device

- **"outside the air map" text:** taps stayed inside the 28-grid's served
  region through the session (dragged pans are imprecise; the map never got
  cleanly past the bbox edge). Path is code-verified: `sampleFieldAt` null →
  `/aqi` → dead → `tapOutside`; unit tests cover the null/hole contract.
- **Live re-sample mid-read:** field refreshed once during verification
  (`air reading: 0 min old`, peek ticked 56→57) but no read was open at that
  moment; re-sampling rides the `fieldGeo` memo dep — same code path as the
  verified taps.

## Gates

`npx tsc --noEmit` clean · `npx expo lint` clean · `node src/api/test-runner.mjs`
21 pass (4 new `sampleFieldAt` cases: inside-cell, shared-edge, hole/outside,
degenerate features) · store/nav/offline runners pass.

## Env notes for the next lane

- CocoaPods needs `LANG=en_US.UTF-8` (ASCII locale crashes on
  `unicode_normalize`).
- `expo-build-properties` was declared in package.json but not installed —
  `npm install expo-build-properties@~57.0.22` unblocks the EXConstants
  `app.config` script phase.
- `npx expo start … | head -N` kills Metro via SIGPIPE once output exceeds N
  lines — run `nohup npx expo start … > /tmp/metro.log 2>&1 &` instead.
- `xcrun simctl location <udid> set 28.6139,77.2090` for Delhi GPS (sim
  defaults to San Francisco — field looks "missing" otherwise).
- Sim taps: macOS coordinate click on the Simulator window = real iOS touch;
  `option+drag` = pinch (drag outward = zoom out, inward = zoom in).
- iOS-sim accessibility target exposes RN labels — `press` by name works for
  buttons (Air map, locate me, ✕).
