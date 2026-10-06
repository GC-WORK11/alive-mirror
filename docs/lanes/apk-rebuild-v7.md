# Lane: apk-rebuild-v7 — the overhauled demo binary

## Why
The demo phone's binary (0b11123) predates: app-overhaul-v2 `d210492`
(the component redesign the owner demanded), search-crash `d791879`
(stage-critical segfault fix), any hi-parity-v2 fixes that land.
This lane builds + drives THE binary the owner demos with.

## Build rules
- `git pull --rebase origin base/v2` AT BUILD TIME — if a lane lands
  while you work (hi-parity-v2 is in flight), rebase and rebuild;
  the binary must carry HEAD.
- macOS build path (apk-final-report.md has it):
  `EXPO_PUBLIC_API_URL=http://65.2.28.40 ./gradlew assembleRelease -x lint`
  in Mobile/android, universal APK, debug-signed.
- Verify bundle: 65.2.28.40 baked; new copy strings present
  ("the air map", "Where to?", gloss) + Hermes table check for
  Devanagari (hi strings).

## Drive rules (Linux/KVM Pixel_7 child, harness: apk-drive-v5.md)
- Re-run the apk-final 14/14 surface set (docs/lanes/
  apk-final-report.md) — every surface must still PASS.
- PLUS the overhaul deltas: tinted hero + icon-tile doors on home,
  option tiles on compare, stat tiles on receipt — each visible.
- PLUS the crash regression: ≥15 search opens across relaunches —
  ZERO crashes (the fix must hold on Android too; if Android
  crashes differently, document it).
- PLUS hi surfaces: hero/doors/ledger in Hindi, no tofu/leaks.
- Consent-OFF pcap: plan/reroute POSTs only, nothing else.
- Cold-open timing on the new build.

## Deliverable
- alive108-<sha>.apk uploaded via upload_attachment.
- Report → docs/lanes/apk-rebuild-v7-report.md (verdict table vs
  the 14/14 + deltas + crash count + pcap + cold-open).
- Commit report to base/v2. Never deploy.
