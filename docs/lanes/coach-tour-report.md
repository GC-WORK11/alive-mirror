# coach-tour report — first-run guided tour

Lane: `coach-tour`. Owner's ask: *"after onboarding, first time, there should
be like explanation — this is for this, this is for — first-time user should
see how it's clean explanation."* A one-time overlay tour that spotlights the
home sheet's core pieces, in the order a Delhi person needs them: the ambient
number → the dose ledger → the map door → the go/where-to pill → the week
strip. Skippable, dismissible, never re-shows.

- **Branch:** `base/v2` (pushed; see `git log` for the commit)
- **Device:** iOS 26.5 sim (iPhone 17, `EDD9B083`), dev-client build,
  Metro `EXPO_PUBLIC_API_URL=http://65.2.28.40` (prod, GET-only)
- **Persistence:** `src/store/tour.ts` — `coach_tour_seen_v1.json` via the
  `expo-file-system` `File`/`Paths` + in-memory mirror pattern (same as
  `welcome.ts`/`consent.ts`; there is no AsyncStorage dep in this app).
  Cleared by `clearAllData` in `shell/settings.ts` — a wiped phone is a
  first run again.

## What was built

- `src/components/shell/CoachTour.tsx` — a tiny content-space rect registry:
  `useMeasureTarget(id)`/`TourTarget` report each stop's window rect, converted
  to content-space (`contentY = win.y + scroll.offset - scroll.viewY`) so the
  spotlight tracks live drags with no re-measure. `useTourScroller` +
  `tourScrolled` wire the home ScrollView's offset in.
- 5 stops: `hero` (title `homeAirNowLead`, body `tourAmbient`) →
  `day`/`heroLedger` (`dayTitle`, `tourLedger`) → `doorMap` (`homeLinkMap`,
  `tourMap`) → `cta` (`searchPlaceholder`, `tourGo`) → `week` (`weekTitle`,
  `tourWeek`). On a fresh install `day`/`week` aren't mounted yet: the ledger
  stop falls back to the hero's sparse progress row, the week stop degrades
  to a centred caption-only card. The tour auto-scrolls to each target.
- Overlay: root `pointerEvents="box-none"`, all four scrim panes + the ring
  `pointerEvents="none"` — taps pass through to whatever's underneath (verified
  live, below). Only the caption card (`skip` / dots / `next`→`got it` pill)
  is interactive. Warm-neutral `V2T.glassDeep` card, Satoshi via `fam()`,
  no decoration.
- `strings.ts` — 8 keys in en + hi (`tourAmbient`, `tourLedger`, `tourMap`,
  `tourGo`, `tourWeek`, `tourSkip`, `tourNext`, `tourDone`); the compiler
  enforces parity.
- `App.tsx` mounts it under
  `tourSeen === false && introSeen === true && homeOpen && phase === "idle"`
  — post-onboarding, on the home sheet, not while a sub-surface (search /
  compare / nav) is up.
- **Seen-flag written at tour mount, not at dismissal** — a kill mid-tour
  never replays; `presented` is recorded once, forever.

## Bugs found and fixed during verification

1. **Tour vanished on the first state change.** An inline
   `onDone={() => setTourSeen(true)}` lambda recreated the internal `done`
   callback every App commit; a `[done]`-dep unmount cleanup re-fired and ran
   `done()` on the location-grant commit — marking the tour seen and unmounting
   it. Fixed with `onDoneRef` + stable empty-dep `done` and a `useCallback`
   `onTourDone` in App. Re-verified: tour survives the location grant.
2. **Tour floated over the search surface.** Tapping "Where to?" *through* the
   scrim (pass-through working as designed) opened search, but `homeOpen` stays
   true for the search phase so the tour kept floating. Added `phase === "idle"`
   to the mount predicate — the real nav-away condition.

## Device verification (fresh `simctl uninstall` + install)

Recorded: `docs/lanes/coach-tour-shots/tour-run.mp4` (111 s).

| check | result |
|---|---|
| Shows once post-onboarding | ✓ mounts ~0.7 s after the onboarding sheet leaves, after the location ask |
| Stop 1 hero spotlight | ✓ ring around the hero card, scrim dims the rest (shot 02) |
| Stop 2 ledger | ✓ lands on the sparse "your count starts…" row (fresh-install fallback), sheet auto-scrolled |
| Stop 3 map door | ✓ just the "Air map" row lit inside the doors card, siblings dimmed |
| Stop 4 cta | ✓ "Where to?" pill lit, caption below |
| Stop 5 week | ✓ caption-only fallback ("your lungs' calendar"), `got it` armed |
| Skip | ✓ tapped on stop 1 → tour dismissed, home live |
| Never re-shows | ✓ terminate + relaunch → straight to home, no overlay — verified after both the full next-path and the skip path (shot 03) |
| Taps pass through | ✓ tapped "Where to?" through the scrim — search opened; scrim is `pointerEvents="none"` |

Shots: `coach-tour-shots/01-onboard.jpg`, `02-stop1-hero.jpg`,
`03-relaunch-notour.jpg`.

## Gates

`npx tsc --noEmit` clean · `npx expo lint` clean · `node src/{store,nav,api,offline}/test-runner.mjs` 16/94/26/16 pass.

## Notes

- The `[expo-notifications] Error reading persisted…` toast in shots is
  pre-existing dev noise (missing keychain entitlement on sim), unrelated.
- `heroLedger`/`doorMap`/`week` ids are registry slots, not new UI —
  `TourTarget`/`useMeasureTarget` wrap existing rows; no component was removed
  or restyled.
