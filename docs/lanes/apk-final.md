# Lane: apk-final — THE demo binary (vibe + coldread + all fixes)

## Why
`alive108-0a26f5a.apk` (v5, 11/11 PASS) is proven but predates
vibe-polish `9b3abe4` (solid content panes — the "looks odd" fix) and
coldread-home `7facc34` (Delhiite-English copy pass). This is the
binary the owner installs for the demo. Build at HEAD, prove it.

## Scope
- Build release APK at base/v2 HEAD (recipe:
  docs/lanes/apk-drive-v5-report.md — macOS box,
  `EXPO_PUBLIC_API_URL=http://65.2.28.40 ./gradlew assembleRelease -x lint`).
- Drive on a Linux/KVM child (spawn ONE, 429 → ~90s retry;
  ~/memory/android-emulator-box.md): COLD-INSTALL → consent OFF →
  sparse hero → verify the vibe deltas (solid panes — no ghosting
  behind Trips/Settings/DelhiToday; days-ahead numerals full ink;
  ledger dose hero 30px) AND the coldread deltas ("µg (micrograms)"
  first-use gloss, "least smoky way" not "least-smoke rd", "counted"
  not "accounted", hi "दिल्ली"/"घं" not DELHI/+Nh) → one nav trip on
  non-recommended pick → arrival → receipt ("about" not "est.") →
  populated surfaces → cold-open time → pcap zero POSTs except
  plan/reroute.
- Compare against the v5 report's screenshot set for the same
  surfaces — regressions in either direction get evidence shots.
- Upload APK; report → docs/lanes/apk-final-report.md: attachment
  URL + verdict table + ≤90s recording.

## Hard rules
- Live API http://65.2.28.40 — GETs + /v2/plan + /v2/reroute only;
  consent OFF throughout, zero POSTs otherwise.
- No app code changes unless a smoke defect (tsc+lint first).
- Never deploy.
