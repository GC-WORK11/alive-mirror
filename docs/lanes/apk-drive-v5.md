# Lane: apk-drive-v5 — the final demo binary

## Why
The demo phone APK `alive108-609a6ef.apk` predates two app-side fixes
the demo actually exercises: `3711ccd` off-corridor arrival-gating
(phantom arrival would end a staged nav early on GPS jitter) and
`0fdd597` ledger dedupe-removal + offline-pill mount order + /v2/trip
floor (outbox 4xx drop). Rebuild at base/v2 HEAD and prove the binary.

## Scope
- Build the release APK at current base/v2 HEAD (EAS or local gradle —
  whichever produced apk-v4; read docs/lanes/apk-drive-v4-report.md for
  the working recipe + the Linux/KVM child pattern).
- Drive it on the KVM emulator (~/memory/android-emulator-box.md):
  cold-install → consent OFF → sparse hero (design state) → a real nav
  trip STARTING A NON-RECOMMENDED PICK (pick→Start) → arrival → receipt
  honest copy → second same-OD trip → BOTH land in ledger (dedupe
  removal) → symptom check-in → ledger/hero populated state → pcap
  assert zero POSTs besides /v2/plan + /v2/reroute.
- New-app-side checks this build adds: (a) staged GPS jitter off-
  corridor must NOT phantom-arrive (offsetM > 40 → arrival gate holds);
  (b) a queued trip offline → back online → lands once, not duplicated;
  (c) 0-km trip POST gets a 422 (the floor).
- Cold-open timing on the emulator + hi locale spot check (no tofu).
- Upload the APK, report → docs/lanes/apk-drive-v5-report.md with the
  attachment URL + verdict table + recording ≤2min.

## Hard rules
- Live API http://65.2.28.40 — GETs + /v2/plan + /v2/reroute only;
  consent OFF throughout (never POST /v2/trip to live EXCEPT the single
  deliberate 0-km 422 check, which is the test itself — one call).
- Spawn ONE Linux/KVM child for build+drive (SWE-2 429 → ~90s retry).
- No app code changes unless a smoke defect — tsc+lint first.
- Never deploy.
