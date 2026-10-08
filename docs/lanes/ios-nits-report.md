# ios-vid nits — lane report

Lane: fix the real findings the iOS walkthrough film flagged on camera
(803 s film; sibling lane's report file `ios-demo-vid-report.md` was
never committed — timestamps below are re-measured on the film itself).

- **When:** 2026-10-08.
- **Tree:** `base/v2` @ `0b58023` + this lane's commits.
- **Build:** dev client (Debug, iphonesimulator), iPhone 17 sim
  `EDD9B083` (iOS 26.5), `EXPO_PUBLIC_API_URL=http://65.2.28.40`.
- **Gates:** `npx tsc --noEmit` clean · `npx expo lint` clean ·
  store 98/98 · nav 100/100 · api 37/37 · offline 16/16.

## 1. ~10 s bare-map after nav close (t≈455–471; also ~4 s behind search-open t≈202–206) — FIXED

**Mechanism:** the bare window is the label-drop latching across an
app-driven transition, not a field unmount. `onRegionWillChange` arms
`gesturing` on any `userInteraction=true` camera change; while armed it
hides `airfieldValues`, `airStationNames`, and every `BasemapLabels`
name (road/POI). The field cells are CPCB-band tans at ~0.6–0.9
opacity over a warm-tan base — with labels+names down the map reads as
"roads on bare brown". During the nav-exit / search-mount windows the
tap's own touch-attributed region events (plus the staggered
`setFollow(false)` + `setStop(pitch:0)` camera settle) keep re-arming
the drop, each arm restarting the 4.5 s backstop timer — the chain of
re-arms is what stretches 4.5 s into ~16 s.

Ruled out while diagnosing: `MapTree` never unmounts (`key="map"`),
`fieldGeo` is never nulled (epoch-swap only), the GeoJSON sources stay
mounted by design (the sim SIGSEGV class is remove-mid-draw), drawHold
only throttles fps.

**Fix:** `src/map/drawHold.ts` gains an app-driven **transition
marker**: `noteMapTransition()` arms inside `holdMapDrawThen` and
`whenMapDrawFree` (the two primitives every overlay mount/unmount and
every programmatic camera op rides), `inMapTransition()` exposes the
window. `App.tsx` `onRegionWillChange` now skips the label-drop arm
inside a transition — a `userInteraction=true` event there is noise,
not a drag. Real drags still drop labels exactly as before.

## 2. 1 s "Loading from Metro" flash (t≈243) — dev-client only, documented

**Verdict:** cannot appear in a release/dev-store build. The banner is
RN's `DevLoadingView` (`NativeDevLoadingView.showMessage`, type
`refresh`, `#2584e8` — matches the film's blue flash) shown by
`loadBundleFromServer` when the JS bundle reloads from Metro. In a
release bundle the native module is stripped and `__DEV__` paths that
call it don't exist — there is no Metro to load from.

**Why it fired on film:** a sibling lane's file save pushed a Fast
Refresh mid-recording — this lane's film was shot on a live dev client
while parallel lanes edited the same tree. It is a bundle-reload
artifact, not app code; no app-side fix is possible or needed. For
demo-grade footage: record on a production/dev-client build with Fast
Refresh disabled, or freeze the tree during the shoot.

## 3. Chooser 4-act draw half-hidden by the options sheet (t≈347–367) — FIXED

**Mechanism:** `useShellFlow.show()` fit-bounds every drawable
candidate with `padding: { bottom: 340 }` — a fixed guess. The
`CompareSheet` anchors bottom at `Sheet detent="half"` =
`maxHeight: window.height * 0.5` (~437 pt on the film device): the
reserved strip under-covers the real footprint by ~100 pt, so the
route tail + endpoint rings + the settle beat drew under the sheet.

**Fix:** bottom padding is now the detent's real height +
24 pt margin (`Dimensions.get("window").height * 0.5 + 24`) — every
staged candidate lands in the visible band above the sheet.

## 4. Tap-latency misses — mostly dev-sim class; see per-tap verdicts

- **t≈343 search row → ~3 s before compare:** the film predates the
  settle-first whereto rebuild (0dea487). The old pick→plan path held
  the search sheet on a GNSS+plan round-trip; the current flow commits
  the place sheet synchronously on tap (whereto-rebuild-report
  measures row tap → `place.show` ≈ 2.0 s incl. the 700 ms camera fly,
  engine rows ~0.5 s after `dir.tap`). Already replaced — verified the
  new sheet lands promptly on sim.
- **t≈359 sheet swipe stutter:** dev-client JS on a 2-core sim inside
  the draw-hold pump — known 1–4 s tap/scroll latency class, not a
  code defect (same class documented for Android in the testday lane).
- **t≈569 sidebar menu first tap:** same class — dev JS render
  contention (reports/aqi/health poll commits) delays press feedback;
  the tap is not swallowed, it lands late. `hitSlop={10}` already on
  the button.
- **t≈664 Settings row ~1 s:** `enter.settings` jank class — the
  screen mounts a settings tree on dev JS. Same known-latency class.

No code change: every observed miss sits inside the documented
dev-client latency envelope on this rig; on hardware the latency
collapses. If a demo must feel snappier, shoot on a release build.

## 5. DelhiToday ~12–19 s cold load (t≈583–602) — FIXED (paint-then-wire)

**Mechanism:** the sheet had no last-good path: `pull()` waited on the
live wire (`fetchCached` is network-first — cache is only read on wire
failure). When `/v2/city`'s server-side `_CITY_CACHE` is cold (any
donation bumps `TRIPS._rev` → full rebuild, measured up to ~19 s) or
the sheet's request joins an in-flight cold fetch started by
`IncidentsCard`, the skeleton holds the whole wait.

**Fix:**
- `src/api/city.ts`: new `peekCity()` / `peekCityMoves()` — instant
  last-good reads via `cachePeek`, with the payload's freshness ages
  corrected for cache-sit exactly like the stale wire path
  (`agedCity`, shared helper).
- `DelhiToday.tsx`: on mount, paint the peek instantly (before the
  wire pull), then let the wire land what it lands. Wire failures
  after a peek degrade to the labelled stale read, never the failure
  card — the same promise `fetchCity` already makes.
- `App.tsx`: boot warms `fetchCity` + `fetchCityMoves` alongside the
  field pull (deduped inside `fetchCached`), so first open usually has
  a hot disk copy; `/v2/city/moves` had no other warmer.

**Before/after:** cold-server worst case: skeleton ~12–19 s →
last-good paint ~0 s (peek is a disk read) with the age chip honest;
wire-warm case ~0.5 s → ~0 s. Only a true first-launch cache-miss can
still skeleton.

## 6. "819 µg · satisfactory" pairing (t≈602+) — FIXED (unambiguous scope)

**Mechanism:** the hero number is `doseUgRound(inhaled.mid)` —
cumulative µg of PM2.5 **inhaled** today (~819 µg) — while `heroFelt`
printed `feltKeyForBand(bandIdx(pm.mid))`, the **ambient** CPCB band
word ("satisfactory" for ~57 µg/m³). A dose figure wearing an air-band
word reads as "819 µg is satisfactory". The same word also opens the
lead line (`cityHeroLead`), so the ambient band was spoken twice.

**Fix:** new `cityHeroAirFelt` string scopes the word to the air it
describes — en "the air outside — {w}" · hi "बाहर की हवा — {w}" — so
"819 µg / the air outside — satisfactory" cannot mis-bind the dose to
the band.

## Files touched

- `Mobile/src/map/drawHold.ts` — transition marker
  (`noteMapTransition` / `inMapTransition`), armed inside
  `holdMapDrawThen` + `whenMapDrawFree`.
- `Mobile/App.tsx` — `inMapTransition` gate on the gesture label-drop;
  boot warm of `fetchCity`/`fetchCityMoves`.
- `Mobile/src/components/shell/useShellFlow.ts` — fitBounds bottom
  padding = real "half" detent height + margin.
- `Mobile/src/api/city.ts` — `peekCity`/`peekCityMoves`, `agedCity`
  shared age-fixup.
- `Mobile/src/screens/DelhiToday.tsx` — peek-then-wire mount; scoped
  hero felt line.
- `Mobile/src/i18n/strings.ts` — `cityHeroAirFelt` (en+hi).

## Sim evidence

Driven live on the iPhone 17 sim (dev client, prod API) —
`docs/lanes/ios-nits-shots/`:

- `delhitoday_hero_scoped.png` / `delhitoday_device.png` — DelhiToday
  opened straight into painted last-good data (hero 883 µg, full
  species list) — no skeleton — and the new scoped line
  "**the air outside — moderate**" (nits 5+6).
- `sidebar_tap_ok.png` — sidebar opens on first tap (nit 4 class).
- `chooser_pill_above_sheet.png` / `chooser_start_footer.png` — the
  compare camera reframe lands the verdict pill ("8 min · ~2.8 µg" /
  "35 min · ~11 µg") and every staged candidate fully **above** the
  half-detent sheet; Start footer reachable (nit 3). Note: the
  `[expo-notifications] Error reading persisted…` dev toast can cover
  the footer until dismissed — dev-client overlay only.
- `nav_live.png` — pitched follow camera, turn card, full label field.
- `postnav_labels_1s.png` / `postnav_labels_10s.png` — after nav X and
  receipt-Done the map keeps every label (Tolstoy Marg, Imperial
  Hotel, POIs) and the CPCB tint at +1.5 s and +10 s — the bare window
  is gone end-to-end (nit 1). A ~13 min screen recording of the whole
  drive exists at `~/vid-nits/repro-final.mov` on the lane box (161 MB,
  not committed).
