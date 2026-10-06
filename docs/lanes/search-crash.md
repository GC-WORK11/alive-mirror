# Lane: search-crash — the stage-risk segfault

## Why
video-v6's shoot hit SearchScreen segfaults 6× CONSECUTIVELY on iOS
sim (two relaunches + state wipe + full sim reboot — persisted). The
documented residual is `search-open ~2/5` — an RN/keyboard-map race
(SearchScreen.tsx L241-298). On stage, the owner typing a search is
the SECOND thing a judge sees; a crash there is fatal to the demo.

## Scope
- Reproduce on iOS sim at HEAD (delhi-air-108-ios-testing skill:
  sim selection quirks; drive via xcrun simctl — open the app, open
  search repeatedly ~15-20× across relaunches/state variants).
- Capture the actual fault: Xcode Devices/sim logs (simctl spawn
  log show --level debug, or Console on the sim host), the RN
  red-box/native crash report, and WHICH of the L241-298 surface
  area is the racy path (keyboard show timing, map ref, sheet
  mount vs useEffect ordering).
- Fix the root cause — defer mount until the screen's transition
  completes, guard the map ref, gate the autofocus — whatever the
  log says, not a guess.
- PROOF: same drive loop post-fix must show ≥20 clean opens
  across relaunches + cold install. Zero is the only acceptable
  count — an intermittent crash can't be demoed around.
- Gates: npx tsc --noEmit && npx expo lint && both test-runners
  (store 18, nav 68). Commit to base/v2 (pull --rebase).
- NOTE: this fix lands AFTER binary 0b11123 — flag in the report
  that the demo-phone APK needs one rebuild to carry it (I'll
  respin the APK lane).

## Hard rules
- Never deploy. Live API GETs only. No scope creep — only the
  crash fix + its regression test.
- Report → docs/lanes/search-crash-report.md: repro count,
  root cause (with the log evidence), fix, post-fix proof count.
