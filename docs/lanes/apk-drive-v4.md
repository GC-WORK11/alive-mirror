# Lane: apk-drive-v4 — rebuilt demo APK with hero-sparse + nav-pick

## Why now
HEAD now carries the owner's #1 fix (designed sparse hero — the fresh-
install "looks broken" is dead) + nav-start-pick (Start launches the
SELECTED card — the pick-reset bug) + the 24h/12h window-format fix.
The demo phone's APK (`alive108-b4a96d2.apk`) predates all three.
Build the new demo APK and drive it.

## Scope
- Build ONE release APK at base/v2 HEAD (same recipe as v3: macOS box
  has the proven ~3min build; name the file with the HEAD sha).
- Then spawn a Linux/KVM child for the emulator drive (read
  ~/memory/android-emulator-box.md first — KVM perms, Maven-429 mirror,
  adb quirks). SWE-2 cap may 429 — wait ~90s and retry once.
- Drive the NEW surfaces specifically:
  1. Fresh-install sparse hero — the designed state (ambient arc +
     "today's air where you are" + sample meter), NOT the old gray bar.
  2. Pick-metro→Start launches METRO nav (the fix), and no-pick→Start
     launches the recommended card (regression).
  3. Open-ended window label — no "7pm"-style mixed format.
  4. Full regression smoke: cold-open ms, journey end-to-end, consent-
     OFF silent (tcpdump or logcat nettrace if available), hi locale
     no-tofu, D1 sheet drag still fixed.
- Upload APK + ≤2min recording via upload_attachment. Report →
  docs/lanes/apk-drive-v4-report.md: APK URL, sha, surface×verdict
  table, cold-open ms, evidence paths.

## Hard rules
- Live API http://65.2.28.40 — GETs + /v2/plan + /v2/reroute only.
- Code fixes only for smoke defects (tsc+lint gate, pull --rebase
  first). Never deploy. Never hand-edit android/ios/.
