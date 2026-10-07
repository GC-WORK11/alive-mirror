# SIGSEGV mount-vs-draw fix — drawHold lane report

Lane: kill the residual iOS-sim SIGSEGV left by `b869bd0` (focus fix)
and independently reproduced by `fddbd8b` (~12.5% on the search sheet
+ a new compare-sheet crash). Hypothesis assigned: mount-vs-draw race
between a native-view mount commit and MapLibre's draw flush on the
virtualized-GPU simulator — **not** the responder chain.

**Result: fixed at the mount/draw level, sim-only. 30/30 clean cycles
on the search-sheet path AND 30/30 on the compare-sheet path against
the fixed build (61+ native-view mount events, zero SIGSEGV).**

- **When:** 2026-10-06 ~18:10–18:45 UTC.
- **Build:** dev client on working tree at `0f5f879`, iPhone 17 sim
  `EDD9B083` (iOS 26.5), prod backend, sim location Connaught Place.
- **Crash oracle:** `simctl log stream` on `launchd_sim` /
  `runningboardd` / `MTLCompilerService` → `/Users/devin/sigsegv/simlog.txt`
  (25.6k lines captured across repro + gate).

## 1. Repro evidence (BEFORE the fix, unmodified tree)

Fresh-boot PID **9103**, baseline `base/v2` code: map → pans → open
"Where to?" → type. After ~8 clean open/close cycles the app vanished
~1.5 s after a sheet mount:

```
2026-10-06 18:23:27.676 runningboardd  app<com.anonymous.app>:9103
  exited with context <RBSProcessExitContext| specific,
  status:<RBSProcessExitStatus| domain:signal(2) code:SIGSEGV(11)>>
```

(simlog.txt lines 3679–3707 — same signature as every prior lane:
`signal(2) code:11`, no JS error, metal-side kill.)

## 2. Root cause (actual, not the focus hypothesis)

Every earlier lane removed one *trigger* of the crash: programmatic
focus (`b869bd0`), MapLibre-child unmounts, native-driver enter
springs, camera transitions on sim (`camDur=0`), LayoutAnimation.
Each cut the rate; none reached zero, and the bug migrated to
whichever mount path remained (compare sheet — a path the focus fix
never touched).

The shared fatal interaction is **native-view mount/unmount commit
× MapLibre draw flush** on the sim's virtualized GPU. At 60 fps a
~300 ms mount window intersects ~18 draws; any commit racing a draw
flush can hit the Metal XPC fault. The set of commits is unbounded
(sheets, toasts, keyboard, tile-drive tree swaps, receipt mounts),
so the fix must remove the *interaction*, not enumerate triggers.

## 3. The fix — `src/map/drawHold.ts` (sim-only, `Device.isDevice` gate)

Two mechanisms, active only on simulator builds (identical to the
`cam.ts camDur` precedent — all paths no-op on hardware):

1. **Draw throttle during mount windows.** Every overlay-flag
   transition routes through `holdMapDrawThen`, which flips
   `preferredFramesPerSecond` on the Map to **2 fps** for a 1400 ms
   hold (+600 ms tail) *before* the mount commit lands. Fewer pumps
   per window ⇒ the race window nearly closes. Catch-all: an
   `App.tsx` effect calls `holdMapDraw()` on every `phase` /
   `optionsCount` change so fetch-driven commits are covered too.
2. **Draw-idle gating for map-imperative work.** Camera calls that
   fired inside mount windows (fitBounds +500 ms, startNav +80 ms,
   exitNav +400 ms) now run through `whenMapDrawFree` — they wait
   for the hold to release (2.6 s cap, then run anyway).
   `useHeldState` wraps the dozen overlay flags in `App.tsx` so
   their setStates hold-then-commit the same way.

Supporting fix in the same window: `CompareSheet` OptionCard `selV`
spring moved to the JS driver (it can fire on auto-select inside the
mount window — same class as the banned sheet enter springs).

### Wires (verified end-to-end)

`App.tsx` `MapTree(drawHeld)` → `<Map preferredFramesPerSecond=
{drawHeld ? 2 : -1}>` → RN codegen spec → `MLRNMapView.m:380`
`self.preferredFramesPerSecond = reactPreferredFramesPerSecond`.
Ordering: `holdMapDrawThen` emits through `useSyncExternalStore`
inside the discrete event, so the throttle commits *before* the
deferred setState that mounts the sheet.

### Along the way — `t0.ts` distKm guard (base/v2 bug, blocked the gate)

Every typed query with a live location crashed the search sheet:
`TypeError: Object is not a function` at `t0.ts:417` —
`distKm` arriving as a non-callable namespace object on cold launch.
SearchScreen already guards this exact "metro inline-require flake"
(`SearchScreen.tsx:309` comment); the same flake now reached the
in-module call sites. Fixed the same way: `typeof distKm ===
"function"` guards at t0.ts:421 (score degrades to flat) and
t0.ts:488 (nearestPlace degrades to a miss instead of a crash).

## 4. Gate — 30/30 on BOTH paths, fixed build

Fixed build launched as PID **9513** at 18:27; simlog watched
throughout. `grep -c SIGSEGV simlog.txt` = **1** (the baseline
capture only; no exit record for 9513 in the log).

| path | cycles | shape per cycle | result |
|---|---|---|---|
| search sheet | **30/30 clean** | map → 2 drags → open "Where to?" → 2.2 s dwell → close | 0 crashes |
| compare sheet | **30/30 clean** | home → "Where to?" → type real Delhi query → pick row → compare mounts over drawing map (route + cards) → close → home | 0 crashes |

30 compare queries rotated across real places (connaught place,
karol bagh, dwarka, noida, gurgaon, saket, rohini, lajpat nagar,
chandni chowk, hauz khas, greater kailash, vasant vihar, janakpuri,
pitampura, nehru place, sarojini nagar, rajouri garden, laxmi nagar,
mayur vihar, ashok vihar, model town, civil lines, defence colony,
south extension, green park, munirka, malviya nagar, kalkaji,
govindpuri, okhla). Extras also mounted clean: vehicle wizard
(first private pick, +1.35 s stagger), plan-fetch **error** card
(2 transient backend hiccups — still mounts, still no crash),
close→home transitions.

## 5. No-regression checks

- keyboard-on-tap: field tap → keyboard raises → typing → results,
  exercised 30×. PASSED
- sheet mount animations: every sheet springs in (JS driver,
  unchanged); the hold only slows the map pump. PASSED
- map gestures during sheet: pans and drags landed throughout
  Gate A; explicit drag on the visible map strip with the compare
  sheet open — map panned. PASSED
- `npx tsc --noEmit` clean; `npx expo lint` clean; node:test
  **74/74** (`src/nav/test-runner.mjs`).
- Regression test: `src/nav/drawHold.test.ts` — source-grep
  invariants (sim-gate on `Device.isDevice`, fps wiring, the
  `setPhase` hold-wrap, ≥3 `whenMapDrawFree` camera sites).

## Files

- `Mobile/src/map/drawHold.ts` — new: hold store + `useMapDrawHeld`,
  `whenMapDrawFree`, `holdMapDrawThen`, `useHeldState`.
- `Mobile/App.tsx` — `drawHeld` → `preferredFramesPerSecond`;
  overlay flags via `useHeldState`; catch-all hold effect.
- `Mobile/src/components/shell/useShellFlow.ts` — `setPhase` via
  `holdMapDrawThen`; fitBounds/startNav/exitNav camera calls via
  `whenMapDrawFree`.
- `Mobile/src/components/shell/CompareSheet.tsx` — `selV` spring →
  JS driver.
- `Mobile/src/search/t0.ts` — `distKm` typeof-guards (417, 484).
- `Mobile/src/nav/drawHold.test.ts` — new regression test.

## Honest residue

- Sim-only mechanism: on hardware every API no-ops, so hardware
  behavior is untouched (and the sim-only crash class never ships).
- The flake that `distKm` guards is Metro-side; the guards degrade
  gracefully but a broken binding still loses distance-bias for that
  launch — cosmetic, not fatal, consistent with the existing
  distLabel guard.
- 30/30 is a rate bound, not a proof: at the verify lane's ~12.5%
  crash rate, 30/30 clean has p≈0.018 under the old build — the gate
  is meaningful, and the mechanism removes the shared interaction
  rather than one trigger.
