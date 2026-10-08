# Walk-fixups lane — repair pass on feature-walk findings F2, F3, F6

**Lane:** walk-fixups. Base `base/v2` pulled to `11f9d3f`, fixes landed on top; re-verified after a mid-lane merge to `eae5514` (coach-tour/fresh-state/drawer-perf lanes landed alongside — the fixes were re-driven on the merged bundle).
**Source findings:** `docs/lanes/feature-walk-report.md` @1274e68 (F2, F3, F6).
**Rig:** iPhone 17 sim · iOS 26.5 (`EDD9B083-…`), Debug dev-client at `~/dd-alive`, metro `:8081` with `EXPO_PUBLIC_API_URL=http://65.2.28.40` (prod GET-only, no writes). Offline = host route blackhole (`route add 65.2.28.40 127.0.0.1`, removed after). GPS `simctl location set 28.6328,77.2197` (Connaught Place). Evidence: `docs/lanes/walk-fixups-shots/`.
**Before/after method:** `git stash` → app reload served the unfixed JS bundle → drove the repro; `git stash pop` → reload → same drive on fixed code. Screenshots taken in both states.

## F3 — offline map-pick was silent (fixed)

**What the walk saw:** airplane-mode pick-on-map consumed the pick with no pin, no error.

**Root cause (deeper than the walk's window):** the pick *did* resolve eventually — on the unfixed bundle an offline pick landed the pin and `planError` ("couldn't load the ways there") at ~35 s (`f3-before-after35s`). The defect was the **~30 s dead window before any feedback**: `posNow()` awaited `getCurrentPositionAsync` with **no timeout** (`net.ts`), and `locNotice` — the channel the flow uses to say anything — was only rendered inside the search sheet, so on the idle map nothing at all acknowledged the tap (`f3-before-silent`).

**Fix:**
- `net.ts` — `posNow()` wrapped in a 9 s `Promise.race`; last-known fallback (in-NCR, <15 min) unchanged. The unbounded await was the silent-hang core.
- `useShellFlow.pick()` + `App.onMapPress/onMapLongPress` — sets `locNotice` to a new `mapPickChecking` string ("checking this spot…" / "यह जगह जाँच रहे हैं…") at pick entry, cleared on every success exit, overwritten by the existing honest rejection lines (`pickTooClose`, `locPickFailed`). Pending state, not a fake pin.
- `App.tsx` — `mapPickNote` held-mirror (`useHeldState`) surfaces `locNotice` as a tappable pill on the idle map, which previously had no notice channel at all.

**Verified on sim (API blackholed):** armed pick → map tap → "checking this spot…" pill appears **immediately** (`f3-after-pending`), then the real terminal state lands — pin + "couldn't load the ways there — check the connection" + retry (`f3-after-endstate`). Same honest outcome as before; the silence is gone. Note: the pin still drops offline (bundled gazetteer "nearest:" labels it honestly) — nothing is faked.

## F2 — receipt "Done" left a bare map (fixed)

**What the walk saw:** "Done dumps you on a bare map; DayPeek does not auto-appear until a surface tap."

**Root cause:** `onNavExit` already called `setHomeOpen(true)` — but only inside the 280 ms-deferred teardown (`setTimeout(onExit, 280)`), and every held setter in that window queues behind `holdMapDraw`. On the sim rig (all draw-holds active — `Device.isDevice` gates them on hardware) the whole chain → `phase idle` + `homeOpen` commit + HomeScreen mount + `dayData` hydration produced a **multi-second chromeless map**. I reproduced exactly this pre-fix: receipt gone, map bare, no FABs/DayPeek for several seconds (`f2-before-bare`); home did eventually arrive, but a user who taps the map in that window reads it as the walk described.

**Fix:** Done is the moment the trip is over — the home door is now committed **at press time**, not inside the deferred teardown: new `NavSession` prop `onHome` (wired to the existing `onPeekOpen` = `setHomeOpen(true)`), called first in `onDone`. `onNavExit`'s own `setHomeOpen` stays as the idempotent backstop. Mount-vs-unmount commits remain on separate frames (the crash class the 280 ms defends against is untouched — home mounts on the press frame, nav tears down 280 ms later).

**Verified on sim:** nav → turn-card × → receipt → Done → receipt closes and **HomeScreen mounts on its own** — "Up late · you've breathed today" (`f2-after-home`). Re-verified post-merge at `eae5514`: same behavior. Honest residual: on the sim the HomeScreen mount is still ~5–10 s of settling because `dayData` rehydrates and the draw-hold pump serialises commits; on hardware the holds are all no-ops so the door lands in ~300 ms. No fake surface was added to paper over the gap.

## F6 — "About this map" + "You Are Here" dead taps (fixed)

**What the walk saw:** both ornaments read as buttons but did nothing.

**Root cause:** both are native MapLibre chrome. The puck's native a11y label "You Are Here" had no `onPress` wired. The ⓘ attribution ornament *does* have a native handler, but at `attributionPosition {right: 10}` it renders ~10 px and half-clipped at the device bezel — effectively unreachable (dead tap).

**Fix:**
- **You Are Here:** `UserLocation onPress` → `onPuckPress` — `posNow()` → `flyTo` the real fix + `setFollow(true)` inside `whenMapDrawFree`; a failed fix shows the same honest `locDenied` pill the crosshair uses (no fabricated position).
- **About this map:** new Pressable row in `LayersSheet` (info glyph, `aboutMap` string: "about this map" / "इस नक्शे के बारे में") → `MapRef.showAttribution()` — the *same* native attribution sheet the ornament owns. `attributionPosition` nudged `right: 10 → 16` so the ornament itself stops clipping at the bezel.

**Verified on sim:** puck tap after panning off → camera flies back to the fix and follow re-engages (green locate FAB) (`f6-after-puck-recenter`). Layers → "about this map" → native attribution sheet lists real sources: MapLibre Native iOS / OpenFreeMap / © OpenMapTiles / Data From OpenStreetMap (`f6-after-about-row`, `f6-after-attribution`). Verified again post-merge.
Minor honest quirk: a puck tap also lands a field read at that point (the map's own tap rule — real data, same as any map tap); noted, not treated as a defect.

## Files

- `Mobile/src/components/shell/net.ts` — `posNow` 9 s bound (F3)
- `Mobile/src/components/shell/useShellFlow.ts` — `pick()` pending/outcome notice (F3)
- `Mobile/App.tsx` — `mapPickNote` mirror pill, `onPuckPress`, `onAboutMap`+`mapRef`, `attributionPosition`, `onHome` prop (F3/F6/F2)
- `Mobile/src/components/shell/LayersSheet.tsx` — "about this map" row (F6)
- `Mobile/src/i18n/strings.ts` — `mapPickChecking`, `aboutMap` (en+hi, parity)

## Gates

`npx tsc --noEmit` clean · `npx expo lint` clean · `node src/{store,nav,api,offline}/test-runner.mjs` — **152/152 pass** (16+94+26+16), on the merged tree. (The store runner's earlier post-test module-resolution quirk did not recur.)

## Honest gaps / notes

- F5's queued-tap pattern (a11y bridge + draw-holds on sim) made several presses during verification land on the 2nd–3rd try — unchanged by this lane; it's a rig artifact per the walk's own note, and these sim-only holds are all `Device.isDevice`-gated no-ops on hardware.
- The F2 "chromeless window" on sim shrinks to the HomeScreen mount/hydration time; the guarantee is now structural (door committed at press), not just timing luck.
- Pre-existing untracked build artifacts (ios/Pods changes from `pod install`) were left out of the commit; `project.pbxproj` reverted per AGENTS.md.
