# Lane: nav-start-pick — Start must launch the SELECTED option

## Finding (apk-drive-v3, verified on-device)
On the compare sheet, tapping a non-recommended option (e.g. Metro) then
`Start` still launches navigation for the RECOMMENDED card (Car-AC).
The receipt then compares against "your usual" (the pick) — so the user
navigates a different mode than the receipt compares. A judge demoing
"pick metro → start" gets the car's route and calls it a bug.

## Correct behavior
`Start` launches the option the user SELECTED (the highlighted card).
Recommendation = default selection only — if the user never taps, Start
follows the recommended card exactly as today. "Your usual" copy stays
tied to the pick; receipt attribution unchanged.

## Scope
- Mobile/ only: find the compare-sheet selection state → where Start
  reads the chosen option (likely the recommended index is re-derived at
  tap-time instead of reading selection state). Fix the read.
- Verify BOTH paths on the emulator or via the store test-runner:
  pick-metro→Start launches metro nav; no-pick→Start launches the
  recommended card (regression).
- While inside: check the receipt's compared-mode is the launched mode,
  not the stale "usual" (if receipt already tracks launched mode, prove
  it and say so).
- Gates: `cd Mobile && npx tsc --noEmit && npx expo lint`; node
  src/store/test-runner.mjs must stay green (extend it with a
  selection→launch test if the harness covers sheet state).
- Commit to base/v2 (pull --rebase first). Report →
  docs/lanes/nav-start-pick-report.md: the bug's mechanism, the fix,
  both-path evidence.

## Hard rules
- Minimal diff — this is a state-read fix, not a sheet redesign.
- No behavior change to recommendation ranking itself.
- Never deploy; never POST to live (plan/reroute GETs fine for driving).
