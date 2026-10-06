# Lane: apk-android-audit — Android-side anti-list + render audit

## Why
The app-overhaul-v2 lane redesigns on iOS sim. Android rendering
differs (elevation vs shadow, font metrics, density buckets, BlurView
support) — violations that look fine on iOS can land cheap/broken on
the demo phone. This lane produces the Android violation list BEFORE
the rebuild so the overhaul knows what Android specifically needs.

## Scope
- Drive binary `alive108-0b11123.apk` (attachment URL in
  docs/lanes/apk-final-report.md) on the Linux/KVM Pixel_7 emulator
  child pattern (see docs/lanes/apk-drive-v5.md for the harness:
  adb, uiautomator dumps, screenshots).
- Audit EVERY surface against the owner's HARD ANTI-LIST +
  DECODED REGISTER (docs/lanes/app-overhaul-v2.md):
  * anything that reads cheap on Android specifically — default
    shadows, font fallback (does Fraunces/Plex Mono actually
    render or is it system serif?), density quirks, text clipped
    by smaller font metrics
  * broken/missing assets, SVG render failures
  * any neon-ish/cheap tones where band colors render differently
  * elevation vs intended depth on Android
  * blur/glass: does the glass-tint render or fall back ugly?
- PLUS: the day-in-life + video-v6 lanes both hit SearchScreen
  SIGSEGV on iOS sim — probe whether the same crash exists on
  ANDROID (open search repeatedly ~15×). If Android is clean,
  that's real evidence the bug is iOS-side (Hermes/iOS interplay).
- Produce the **android-checklist** section for the rebuild verify:
  items the overhauled APK must pass on this emulator.

## Deliverable
- Report → docs/lanes/apk-android-audit-report.md: violation list
  with screenshots, the Android-vs-iOS crash data point, the
  rebuild checklist.
- No code changes. Live API GETs + /v2/plan only. KVM child is
  yours to spawn (parent waits + commits the report).
