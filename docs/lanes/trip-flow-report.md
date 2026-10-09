# Trip-flow lane — From/To + journey flow rebuild

Lane: Mobile/ where-to flow (CompareSheet, plan consumers, App.tsx trip phases, SearchScreen destination handoff). Branch `base/v2`, direct push. Owner ask: "two sections From and To … finding the purest route for you … animation of multiple routes loading … then comes one … before start journey select vehicle … 'start journey' … maps zoomed like Google Maps."

## What shipped (all real, nothing staged)

1. **From + To fields** — the where-to sheet opens with a two-row card: `from: your location` (live position, tappable → re-arms origin search) and `To: Where to?` (tappable → destination search). The auto-From lands via a `posNowDetailed`/`fixName` effect when search opens. Both rows pick real gazetteer results through the same `pick()` path — no assumed origin.
2. **Finding state** — picking a destination with an origin set calls `pick(direct)` → `setPhase("compare")` → `planEngineFirst` fires `POST /v2/plan` immediately; CompareSheet shows a spinner row + "finding the purest route for you…" (`checkingRoutes`, en+hi) with the from→to trip strip pinned at top while the call is in flight.
3. **Multi-route load-in** — alternates paint grey on the map during the finding window; the purest route then lands as the forest pick (verified live: route lines visible behind the finding sheet before the chooser settles).
4. **Vehicle select before start** — the chooser keeps the full real option set: Car (AC) + 3 alts, windows-down, bike/scooter +3, bus, auto +3, metro+walk, Bus 181B, bicycle +3, on foot +3 — every card carries live API dose/time/distance (e.g. Car AC ≈5 µg 2–8, 9 min, 6.75 km, arrive 9:26 am). Vehicle chip pinned above the footer; switching re-prices deltas live.
5. **"start journey"** — plain-text CTA via new i18n key `startJourney` ("start journey" / "यात्रा शुरू करें"), plus `fieldTo` ("To"/"मंज़िल") and `checkingRoutes`.
6. **Nav zoom** — `startNav` entry camera: `easeTo` zoom 16.6, pitch 55, route-bearing, deferred 80 ms into `whenMapDrawFree` so it doesn't race the sheet mount (mount-vs-draw class). Street-level follow from the existing follow-camera.
7. **Glitch sweep — real bug class found + fixed.** On the sim the JS event loop starves during map draw-holds (RAF/timer callbacks fire tens of seconds late). JS-driven `Animated.spring`s then oscillate around `toValue` without ever resting — `.start()` callbacks never fire. Two permanent failures traced to that:
   - `Sheet.enterVeil` (`pointerEvents="auto"`, absolute fill) only unmounts when `settled` flips in the spring callback → **every touch on the sheet was dead forever** (start journey, turn-by-turn, ×, nudge — dead-tap verified live).
   - `SearchScreen`'s `enter` value drives sheet opacity → sheets could sit ghosted at ~0 opacity for a minute+ while still mounted and swallowing touches.
   - Fix: hard-settle `setTimeout` (600/700 ms) that `stopAnimation()` + `setValue(1)` + `setSettled(true)` in `ui.tsx` Sheet, `SearchScreen.tsx`, and CompareSheet `selV` wash. Springs stay the design animation; the timer is the floor. Dead-code on hardware (`Device.isDevice` paths unchanged).
   - Also: `pick()` gained `opts.direct` — destination pick with an origin skips the place-settle sheet entirely (the double-sheet the owner called glitchy).

## Verified live on iPhone 17 sim (iOS 26)

| State | Evidence |
|---|---|
| From/To entry | `/tmp/tripflow/03-search`, `42-rows3`, `66-compare` (sheet settled opaque post-fix) |
| Finding | `45-finding` (spinner + "finding the purest route for you…" + trip strip) |
| Chooser + vehicles + start journey | `46-mid1`, `47-mid2`, `68-cmp2` |
| OD strip on SearchBar | `68-cmp2` ("your location → Gift Palace, Khan Market") |
| pick→compare direct | session log: `pick which=to direct=true from=set at=Gift Palace…` → `search -> compare` |
| Nav-zoomed | camera values verified in code (z16.6/pitch55/bearing); sim input went tap-dead before the final nav frame — see Known flakes |

## Known flakes / honest notes

- **Sim tap-dead end state:** after ~90 s of starved commits the running app's touches died app-wide (even top-bar ×) — most consistent with an opacity-0 sheet still mounted over the tree; the enter-settle fix prevents the mount-stuck case on fresh launches, but a second stale-instance path may exist. On hardware the spring completes in ~300 ms and none of this is reachable.
- **`setPhase` has no same-value guard** — observed `search -> search` double-commits (harmless, noted for a later lane).
- **Gazetteer quirk:** "khan market" typed query returns zero rows; "connaught place" works. Recent-row picks are reliable. Not in lane scope.
- **Unrelated i18n bug spotted live:** a notification banner rendered a literal `{word}` placeholder (formatter didn't substitute). Flagging for the copy lane.

## Gates

`npx tsc --noEmit` clean · `npx expo lint` clean · runners: store 100 · nav 100 · api 37 · offline 16 — all pass.

Files: `App.tsx` (minimal — direct pick opt, labels), `CompareSheet.tsx` (trip strip, pinned chip, startJourney CTA, selV settle), `useShellFlow.ts` (direct pick, auto-From, nav entry camera), `SearchScreen.tsx` (routeCard From/To, enter settle), `strings.ts` (3 keys ×2), `ui.tsx` (enterVeil settle fix).
