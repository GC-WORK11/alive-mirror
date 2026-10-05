# Lane: app-stress — adversarial on-device drive of the demo APK

## Why now
apk-v3 verified the clean-drive path on `alive108-b4a96d2.apk`. Judges
don't drive clean — they poke. Hunt the breaks the clean drive can't see
before a judge finds them on stage.

## Scope (Android emulator; APK at the link below)
Drive `alive108-b4a96d2.apk` ADVERSARIALLY on the emulator (memory file
~/memory/android-emulator-box.md has the box's emulator/KVM/adb quirks —
read it first):
- **Nav churn**: start nav → cancel mid-route → immediately plan a new
  trip ×5 rapid; kill the backend reachability mid-nav if you can (wifi
  off/on) and watch honesty degrade vs hang.
- **Consent flips mid-flow**: flip data-sharing OFF mid-navigation →
  verify trip recording stops honestly (no phantom upload, no crash);
  flip ON again → resume cleanly.
- **Locale switch mid-flow**: EN→HI mid-session on each surface — no
  clipped text, no stale-English keys, no layout breaks (rtl=False but
  check wrapping).
- **Lifecycle torture**: background mid-nav 60s → foreground (trip state
  honest?); rotate if enabled; rapid sheet open/close ×20 (D1 regression
  hunt — the elevation fix must hold under stress).
- **Memory pressure**: `adb shell am send-trim-memory` or a memory hog —
  does the app recover state or white-screen?
- **Rapid-fire inputs**: spam search field, rapid vehicle toggles,
  double-tap options — race conditions, duplicate sheets, dead buttons.
- Time-box ~90min of driving. RECORD every break found (screen record or
  pull the frames); a PASS list too (what survived torture).

## Deliverable
docs/lanes/app-stress-report.md — findings table (severity × surface ×
repro steps × evidence path) + PASS list + the verdict line ("a judge
poking it for N minutes finds: …"). If you fix a trivially-safe bug (e.g.
a guard clause), commit to base/v2 (pull --rebase first; tsc+lint gate —
`npx tsc --noEmit` + `npx expo lint` in Mobile/); anything structural →
report it, don't patch blind.

APK: https://app.devin.ai/attachments/670fb515-3b24-4119-b40c-46c94a045950/alive108-b4a96d2.apk
Live API: http://65.2.28.40 (health check first — app talks to it).

## Hard rules
- Real device evidence for every claim — recording or adb log/screenshot
  path, not prose.
- Never deploy, never hand-edit android/ios/ dirs (regenerate only via
  expo tooling if ever needed — prefer reporting).
- Nothing fake: if the emulator can't reproduce a scenario, mark it
  UNTESTED not passed.
