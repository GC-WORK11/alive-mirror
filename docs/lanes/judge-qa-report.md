# Lane report: judge-qa — the brutal set, verified live

Pass: 2026-10-05 ~22:35–22:55 UTC. Every curl below was executed against
`http://65.2.28.40` during the pass (build `80a15258` — the strip-bz
deploy; `/health.build_sha` matches the image tag). Deliverable:
`docs/plan/judges-faq.md` rewritten — 16 questions, each with a one-line
stage answer + live output or file:line.

## What the old doc had, and what changed

Old `judges-faq.md` was a 5-question prose FAQ, correct but
pre-dosimeter-epoch in framing: it answered "is the data real", "why
dose ≠ AQI", "privacy", "moat", "what does 95.2% mean". All five were
still true but none had the *show-me* shape — no curls, no file:line,
and several mandated attack surfaces (offline, AWS role, scale limits,
gov-wrapper, too-good numbers) were missing entirely.

New set = the 9 mandated questions + 7 added ones a hostile judge would
use to make it fail.

## The question list → status

| # | Question | Status | Proof anchor |
|---|---|---|---|
| 1 | Differentiation vs AQI apps | covered (rewritten harder) | `POST /v2/plan` dose ladder 10.8→357.9 µg live |
| 2 | Field isn't fake | covered (was "is the data real") | `GET /v2/skill` 21 pairs graded; `/health.sources` 24 stations; `/v2/archive` recorded hours |
| 3 | Privacy isn't a slide | covered (was prose) | `trip.py:35-38,214`; `community.py:89-90,116-161,538`; `main.py:1247` (observe→410); `/v2/city/moves` + `/community` live gates; apk-v3 tcpdump 268 reqs (handoff cont.42) |
| 4 | Dose math | covered (expanded) | `exposure.py:1-8,51-149,232-393`; `daylog.ts:228-239`; `test-runner.mjs` 13/13 ran; `test_parity_dose.py` 8/8 ran |
| 5 | Offline / venue wifi | **gap → added** | `docs/plan/offline.md` matrix; outbox queue; emulator gauntlet in demo-day |
| 6 | AWS role | **gap → added** | `docs/18-aws-architecture.md`; `scripts/deploy.sh`; `archive.storage.bucket` on the wire |
| 7 | 33× too-good numbers | **gap → added** | live decomposition 2.36× conc × 10.2× time × 1.4× VE ≈ 33× |
| 8 | Scale limits | **gap → added** | live `took_ms 4740`; `edge_partial:true` on car reach; `refresh_ttl_s 900`; `plan.py:1131` 20 s budget; cold-path.md |
| 9 | Gov-data wrapper | covered (was inside "moat") | `ingest_waqi.py:21-22,137-142` EPA inversion; three-feed source string; `alive_core` engine |
| 10 | "22 trips is nothing" | added | `/community` + `/v2/city/moves` suppression counters live |
| 11 | Trust model vs monitor | carried over (95.2% kept) | `field_validation.md` 3,550 pairs; `field_calibration.json`; `nearest_sample_km` on the wire |
| 12 | Plan to Mumbai | added | live typed `outside_service_area`, 0.1 ms |
| 13 | Bands real or decorative | added | `exposure.py:341-374` σ propagation + confidence tiers; wide band shown live |
| 14 | Health claims | added | `alive-depth.md` "What we refuse"; `CIG_UG=316` basis on the wire |
| 15 | Show me a failure, live | added | `/v2/skill` thin horizons; `/v2/archive` hour-4 gap; `nh3:null`; CPCB dormant |
| 16 | The moat | carried over (tightened) | `alive_core` + 1,070,459 priced edges + calibrated bands + named `degraded` |

## Verified tonight (the numbers the FAQ quotes)

```
/health        ok · build 80a15258 · engine alive_core · 1,070,459 edges
               (903,058 priced) · field_age ~770-900 s · TTL 900 s
               stations: 24 WAQI up · model 70 samples · fires 79 up
               transit bus+metro real feeds on disk
/v2/plan       CP→GG: 24 options · took_ms 4740 · smoke_modifier 1.09
               car-AC 10.8 (4.7–16.9) · windows-down 19.6 · bike 24.8
               bus 28.3 · auto 32.0 · bus-transit 65.8 · metro+walk 95.8
               bicycle 158.6 · walk 357.9 (156.7–559.1) → 33.1×
/v2/plan       CP→Mumbai → {"code":"outside_service_area"} in 0.1 ms
/v2/reroute    works — fresh option set (21) + route_id
/v2/strip      route_id → 77 samples · step 250 m · 8 roads
/v2/skill      21 pairs · h+1 MAE 16.3/+15.8 (71.4%/80.0% band-hit)
               h+2 29.9/+29.6 (13.9%/20.0%) · h0 & h≥3 thin
/v2/day        heavy 22:30→day end @159.2 · cleanest 12:30–18:30 @44.7
               mean 105.2 · 3 populated decisions rows
/v2/archive    8 snapshots since Oct-5 20:00 IST · today hours 0-3
               recorded, hour 4 a real gap, 5-23 pending
/v2/city       breath 885 µg ≈ 2.8 cig · −44.8% vs decade-typical hour
/v2/city/moves min_k 3 · 36 trips/7d · corridors 12 of 54 publishable
/community     22 obs · 14 contributors · 725.9 µg avoided
               corridor rows carry devices ≥3 (6,4,4,3,4)
/v2/reach      walk@25 → 3,168 edges / 139.0 km / took_ms 11.2
               car@25 → 890,566 edges / 75,805 km / edge_partial:true
/depart        auto CP→GG: now 29.2 → best +12h 14.4 (51% less),
               worst +16h 79.7 · 24 slots · 120 h horizon
/v2/outlook    5-day: "today looks least-bad ~107 vs ~130"
/v2/districts  29 rows (Delhi NCT pm25 71.0)
/aqi @CP       pm25 76.4 bz / 70.1 ambient · US AQI 159 ·
               smoke_modifier 1.09 · fires 79/17 belt · nearest_sample
               1.8 km · nh3 null (honest empty)
/v2/why        stagnation — VC ~100 m²/s vs ~3,000 · fires checked,
               refused (carrying:false, S wind outside NW gate)
/fires         79 detections · firms-public-csv · live
```

Local runs: `cd Mobile && node src/store/test-runner.mjs` → 13/13;
`pytest tests/test_parity_dose.py` → 8/8;
`pytest tests/test_community_v2.py tests/test_v2.py` → 52/52.

## Drift warnings for the day

- The 33× moves with the field (31–45× this week) — say the range.
- Options count drifts (16–24) as transit rows enter/leave service
  hours; tonight 24 (metro+walk present at ~04:15 IST).
- `/v2/skill` pairs accumulate since the archive went live Oct-5 20:00
  IST — by demo morning the count will be higher and h≥3 may grade.
- `fires`/smoke_modifier swing daily; if `smoke_modifier` reads `null`
  at CP, drop the ×1.09 clause.
- Field age ~13 min is normal (15-min cadence); a fresh task reads thin
  (~16 stations/41 samples) for ~60 min — don't demo inside T-60 of a
  deploy (demo-day.md wart list).

## Not done / limits of this pass

- The tcpdump evidence is cited from the parent's ledger entry
  (handoff.md cont.42, apk-drive-v3 verdict SHIP) — the raw capture
  lives on the child session's box; the claim is quoted, not re-run.
- `/admin/api/*` is token-gated and was not probed (by design — no
  admin token needed for any judge-visible surface).
- No POSTs were made to trip/feedback/observe (lane rule); the privacy
  claims are proven by file:line + tests, not by live writes.
