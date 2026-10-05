# Lane: ledger-batch — the app-stress follow-ups (dedupe, banner, plausibility)

## Source
docs/lanes/app-stress-report.md (`3711ccd`) — the hostile drive's
findings beyond the fixed phantom-arrival. Three small real items,
one lane.

## 1. MED — ledger dedupe eats real trips
The 10-min same-name dedupe (keep-first) silently dropped a
1.8km/1.1µg and a 2.5km/0.7µg trip on the wire — a phantom entry
absorbs a following real one, and the dedupe key is locale-fragile
(stored "सेंट्रल दिल्ली" vs queried "central Delhi" — the name string
crosses locale states). Read Mobile/src/store/daylog.ts (dedupe) +
the trip-append path.
Fix direction (choose the least invasive that is CORRECT):
- key on stable identity (route option identity / start+dest
  coordinates rounded, NOT the display name), and/or
- drop the dedupe entirely if the phantom-arrival fix already makes
  duplicate suppression unnecessary — check whether dedupe exists to
  mask the phantom-arrival noise; if yes, prefer deleting it over
  sharpening it (the dosimeter's ledger must never silently eat a
  real trip). Add a nav/store-runner test: two same-name trips 4min
  apart → both land.

## 2. LOW — offline banner under the nav turn card
Only its tail peeks out — z-order/elevation vs the turn card. Find
the banner's mount + the nav overlay stack; the D1 work set the
elevation ladder — keep it consistent (banner above map chrome,
below sheets, but not UNDER the turn card).

## 3. Note — server accepts 0-km/37s donations
/v2/trip has no plausibility floor. Add a cheap honest guard:
reject (or accept-but-exclude-from-aggregates) trips with
distance_km==0 or implausible duration vs distance. Check how
community.py aggregates ingest — exclusion at ingest is fine;
don't break the real receipt path (a real 0km donation is still
possible from a cancelled nav — decide + document).
Test: POST a 0km trip → not counted in community counters.

## Gates
- Mobile: cd Mobile && npx tsc --noEmit && npx expo lint (cam.ts
  resolver nit is pre-existing — don't chase) && node
  src/store/test-runner.mjs && node src/nav/test-runner.mjs
- Server: PYTHONPATH=core/build312:. .venv312/bin/python -m pytest
  -q tests/test_community*.py tests/test_trip*.py (whatever the
  donation path tests are) — full suite only if touching shared code.
- Commit to base/v2 (pull --rebase). Report →
  docs/lanes/ledger-batch-report.md — findings×fix×evidence.

## Hard rules
- Live API http://65.2.28.40: GETs only — NEVER POST /v2/trip or
  /v2/feedback to live; test donations against a LOCAL server or a
  stubbed path.
- Never deploy. Never hand-edit android/ios/.
