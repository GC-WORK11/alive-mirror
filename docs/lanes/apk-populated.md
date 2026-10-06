# Lane: apk-populated — the used-phone state on Android

## Why
apk-v4 verified the SPARSE hero on Android (`alive108-609a6ef.apk`)
and populated on iOS sim — but the demo phone will be a USED phone:
days of samples, counted dose, trips in the ledger, symptom check-ins.
The populated Android state (hero with real dose + gauge + week dots
filled + day arc + budget ring + ledger entries + symptom lens panel)
is the surface a judge most likely sees. Verify it on the target
platform.

## Scope
- Drive `alive108-609a6ef.apk` on the Linux/KVM emulator (read
  ~/memory/android-emulator-box.md — KVM perms, adb quirks).
- Get it into the populated state honestly: let it sample (gps fixes
  via `adb emu geo fix` — or the location replay pattern), run a nav
  trip to seed a real ledger entry, do a symptom check-in. If the
  sampling cadence makes live seeding slow, drive what accumulates
  in-session + force any legitimate accelerate path the app exposes
  (never fabricate store state by hand-editing daylog files —
  that tests nothing).
- Assert: hero shows a real dose number + gauge, week dots fill,
  day-arc bars, budget ring decrement, trip appears in ledger with
  real distance/dose, symptom lens renders (or honestly says it
  needs more days), "how sure" line reads, no layout overflow at
  420dpi on any populated card.
- Also re-check: the trips→receipt copy (post donation-floor +
  dedupe-removal the receipt should still read honestly), and the
  pick→Start on a used phone (journey intact).
- Recording ≤2min + surface×verdict table →
  docs/lanes/apk-populated-report.md.

## Hard rules
- Live API http://65.2.28.40 — GETs + /v2/plan + /v2/reroute only;
  toggle share/consent OFF before any nav so no donation posts.
- Spawn ONE Linux/KVM child for the drive if needed (SWE-2 429 →
  wait ~90s retry). Code fixes only for smoke defects (tsc+lint).
  Never deploy.
