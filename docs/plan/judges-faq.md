# Judges' FAQ — the brutal set, every answer proven live

Short stage answers to the questions a hostile judge actually asks.
Every answer carries its proof: a curl you can run against the live
service while the judge watches, or a file:line you can open.

All numbers below were read off `http://65.2.28.40` on **2026-10-05
~22:40–22:50 UTC** (build `80a15258`, breathing-zone dose basis,
`smoke_modifier` 1.09). They drift with the field — the drift IS the
proof it's live; re-run `scripts/verify_numbers.sh` at T-45.

---

## 1. "How is this different from the AQI apps on my phone?"

**Stage answer:** "AQI apps tell you how bad the city is; we tell you
what it cost *you* — inhaled micrograms on your actual route, per mode,
with a receipt. Nobody computes personal dose without hardware."

**Proof — the dose ladder no AQI app can produce** (same O→D, same
minute, only the mode changes):

```bash
curl -sX POST http://65.2.28.40/v2/plan -H 'content-type: application/json' \
  -d '{"from":{"lat":28.6315,"lon":77.2167},"to":{"lat":28.495,"lon":77.089}}'
# Connaught Place → Gurugram, today's live mids (µg inhaled PM2.5,
#   2026-10-07 ~11:20 UTC, build 698cf808):
#   Car (AC) 8.6 · Car windows-down ~13 · Bike ~17 · Bus ~19
#   Auto-rickshaw ~22 · Metro+walk ~33 · Bicycle ~105 · On foot ~285
# 18 options this hit (16–24 drift), took_ms 7,551 fresh / ~1.1 s warm,
#   smoke_modifier 1.06 echoed on the wire → ~33× car↔walk.
```

AQI has no route, no breathing rate, no duration, no vehicle — a city
average can't rank "drive vs ride". Proof the receipt is real: the
wire carries `dose.{lo,mid,hi}` bands and `confidence` per option,
and `ranking: "dose_lo within 10% ties, lowest emission wins"`.

## 2. "Prove the field isn't fake"

**Stage answer:** "The model grades itself in public — served forecast
vs what the station field later recorded, and it publishes buckets too
thin to score as `thin` instead of a number."

```bash
curl -s http://65.2.28.40/v2/skill
#   pairs: 304 (served-forecast vs recorded-hour) — re-read 2026-10-07
#   h+0: MAE 3.8 µg/m³, band-hit 90.2% cell
#   h+11: MAE 37.2, band-hit 37.7% — error widens honestly with horizon
#   under 5 pairs a horizon refuses to grade itself (`thin`)
```

**Second proof — the field admits its own provenance:**

```bash
curl -s http://65.2.28.40/health | python3 -c 'import json,sys;print(json.load(sys.stdin)["sources"])'
#   model:  up, ~97 samples, "waqi+dpcc-stations+open-meteo/cams"
#   stations: up, 52 instruments (WAQI + DPCC both ok — re-read 2026-10-07, drift band 52–54)
#   fires:  up, 44 NASA FIRMS detections (drifts daily — 67–79 earlier)
#   engine: "alive_core" — our own C++ kriging build, not a proxy
```

**Third — the recorded-vs-model archive:** `GET /v2/archive` replays
the field as actually served, hour by hour — today hours 01:00 and
03:00–16:00 IST are `basis:"recorded"`, hours 0 and 2 are honest
`gap`s, hours 17–23 `pending`. Nothing is back-filled.

Offline ground truth: `server/data/field_validation.md` — 3,550
held-out station-hours across 85 stations; measured ±2σ coverage
95.2% vs 95.4% nominal (raw krige σ covered only ~29% of truth, so we
re-calibrated — the file publishes the ugly per-station bias table too).

## 3. "Privacy is a slide — prove it's an architecture"

**Stage answer:** "No accounts exist to leak. The only upload path folds
a trip into k≥3 aggregates at ingest — the per-trip row is never
created, so there is nothing to breach."

**Proof — the transform chain is in the code, not the policy:**

- `server/v2/trip.py:35-38` — `TRIM_M=300`, `THIN_M=100`, `ROUND_DP=4`,
  `MAX_POINTS=5000`: first/last 300 m of every trip are dropped
  server-side, points thinned to ~100 m, rounded to ~11 m.
- `server/v2/trip.py:214` — the device token becomes
  `sha256[:16]` before it touches any store; the raw payload is
  discarded (docstring line 11: "never stored, never logged").
- `server/community.py:89-90` — `_K_MIN_DEVICES = 3`,
  `_CELL_WINDOW_S = 72*3600`; `corridors()` (~line 538) publishes a
  street only with ≥3 distinct hashed devices inside 72 h.
- `server/community.py:116-161` — `_fold()` writes straight into
  cell/hour/day/lifetime aggregate counters. No trip table exists.
- `server/main.py:1247-1258` — `/observe` (the old raw-coords
  endpoint) answers **410 Gone**, not a quiet deprecation.

**Proof on the wire** — the suppression counter is public:

```bash
curl -s http://65.2.28.40/v2/city/moves
#   min_k: 3 · mode_share_suppressed_trips: 0 ·
#   corridors: 12 active of 55 tracked (43 honestly suppressed) — 2026-10-07
curl -s http://65.2.28.40/community
#   top_corridors[].devices = 6,4,4,3,4 — every published row ≥3
#   basis: "corridor cells published only with >=3 distinct devices
#          in 72 h; no per-trip records exist at rest"
```

**Proof it doesn't leak when asked not to:** the apk-v3 drive ran the
release APK with sharing OFF under tcpdump — 268 requests captured,
the only POSTs were `/v2/plan` + `/v2/reroute` (read-only surfaces),
zero donation frames (`docs/plan/handoff.md` cont.42).

**Runnable:** `server/tests/test_community_v2.py` + `test_v2.py` —
52 tests incl. `test_no_per_trip_rows_can_exist_at_rest`,
`test_corridor_below_k_never_publishes`, token-absent-from-store repr
assertions. Passed tonight on this checkout (`52 passed`). The claim→
line table is `docs/privacy/verify.md`; known gaps (sybil, bearer
token, NLB sees request lines) are listed in `PRIVACY.md`, not hidden.

## 4. "How is the dose actually computed?"

**Stage answer:** "inhaled µg = Σ over ~250 m route samples of
concentration × mode micro-environment × ventilation × time — every
factor a published Delhi measurement, and the same integral priced the
path, so the number shown is the criterion the route won on."

**Proof:**

- `server/exposure.py:1-8` — the formula and its citation block
  ([1]–[6]: Sci. Total Environ. 2021 six-mode Delhi micro-environments,
  Discover Atmosphere 2025 Magenta-line run means, Zuurbier 2009
  ventilation, EPA near-road decay, Goel 2015 on-road exceedances,
  Apte 2011 in-rickshaw).
- `server/exposure.py:51-149` — the ME/VE tables: microenv metro 0.45 /
  car-AC 0.55 / walk 1.30 / auto 1.30; ventilation seated 10.0 /
  walk 14.0 / cycle 22.0 L/min. Unknown modes degrade to open-air
  factors with `known_mode:false`, never a crash (`mode_factors`,
  line 180).
- `server/exposure.py:232,278-393` — 250 m sampling, dose_lo/hi as a
  linear σ propagation (conservative, not independence-assuming).
- `Mobile/src/store/daylog.ts:228-239` — the on-device day arc uses
  the same trapezoid integral (the ledger-audit lane caught left-edge
  sampling disagreeing with the hero total; the test pins them equal).
- **Runnable tonight:** `cd Mobile && node src/store/test-runner.mjs`
  → `tests 13, pass 13` — including a fixture built from real live
  `/aqi` reads where the hero number equals a hand-computed trapezoid.
- **C++ parity:** `server/tests/test_parity_dose.py` — 8 tests proving
  the `alive_core` engine reproduces the Python reference bit-for-bit
  (`8 passed` tonight).

## 5. "What happens offline — say, on venue wifi?"

**Stage answer:** "Search, the ledger, a pre-planned nav leg and the
receipt work air-gapped; what needs the network fails with an age
label, never a frozen or fabricated number."

**Proof:** the contract is `docs/plan/offline.md` — the full
fresh/stale/none matrix. Mechanisms: `Mobile/src/offline/queue.ts`
(durable outbox for donations — pill shows "N saved to send", flushes
on recovery), `Mobile/src/offline/net.ts` (network-first 6 s abort →
last-good + `stale` + `ageS`), and a bundled 124k-entry gazetteer so
search needs no network at all. Verified on the release-APK emulator
gauntlet (airplane cold-start, edge/gprs throttle, mid-request
airplane, dead-server) — `docs/demo-day.md` "Connectivity plan".

## 6. "What's AWS doing here — is this an EC2 with a paint job?"

**Stage answer:** "The whole pipeline is AWS: CodeBuild builds the
image in-cloud from S3, ECR holds it, Fargate runs it behind an NLB on
an Elastic IP, S3 persists the community aggregates and the hourly
field archive, DynamoDB holds the aggregate tables, Secrets Manager
holds the keys, IAM is split least-privilege."

**Proof:** `docs/18-aws-architecture.md` (the live diagram) +
`scripts/deploy.sh` — the one-command pipeline itself. Live traces on
every response: `/v2/archive.storage` reads `bucket: alive108-air`,
`/health.build_sha` = the ECR image tag. Two IAM roles because the
task's own identity (`alive108-task`) is scoped to `s3:Get/PutObject`
on `community/*` only. The console footage is scripted into the video
(`docs/submission/video-shotlist.md`).

## 7. "33× between walk and car? That number looks cooked"

**Stage answer:** "Mode dominates street choice — it's not magic
routing. The walker spends ~10× longer in the plume, at ~2.4× the
breathing-zone concentration, breathing ~1.4× harder. 2.4 × 10 × 1.4 ≈
33. The physics is the gap; we just integrate it."

**Proof — decompose tonight's wire:**

```
walk: 71.4 µg/m³ breathing-zone · 285 min · 14 L/min → 284.6 µg
car:  30.2 µg/m³ breathing-zone ·  28 min · 10 L/min →   8.6 µg
2.36× conc (microenv 1.30/0.55) × 10.0× time × 1.4× VE ≈ 33×
                                        wire says 33.1× — closes.
```

And the honest framing: the range is 31–45× this week (it moves with
the field), and each option still carries its own band — walk
156.7–559.1 µg, car 4.7–16.9. If a judge hits it in a clean hour the
spread narrows; that's the point of quoting bands, not constants.

## 8. "What breaks at scale?"

**Stage answer:** "Honest answers: it's a 1-vCPU Fargate task with one
worker — a cold first plan legitimately takes ~5–7 s; the field
rebuilds every 15 min; reach is capped and says so on the wire."

**Proof:**

- `POST /v2/plan` tonight: `took_ms 4740` for a fresh OD under
  `PLAN_BUDGET_S = 20.0` (`server/v2/plan.py:1131`); an arm that dies
  inside the budget is named on the wire as `degraded:["<arm>"]`
  (`plan.py:1981`) instead of the others fabricating rows.
- `GET /v2/reach?mode=car&budget_ug=25` tonight: `edge_count 890566,
  distance_km 75805, edge_partial: true` — the bounded-Dijkstra hit
  its cap and reports `partial` instead of pretending completeness.
  Walk@25 settled 3,168 edges in `took_ms 11`.
- `refresh_ttl_s: 900` on the `field` block — the 15-minute cadence is
  on the wire, and `field_age_s`/`field_stale` expose staleness
  instead of hiding it.
- Cold-path measured table: `docs/plan/cold-path.md` — cold plan
  6,650 ms → warm re-hits ~120 ms; the burst-contention failure mode
  (event-loop queueing under parallel probes) is documented there too.

## 9. "Isn't this just a wrapper around government data?"

**Stage answer:** "The stations are one input of three. The product is
what doesn't exist in the feed: a kriged field with a calibrated σ, a
million-edge dose-priced graph, the dose integral itself, and the
recorded archive that grades the model."

**Proof:**

- The WAQI feed is a US-EPA *sub-index*, not µg/m³ — we invert it
  through the EPA breakpoint table, Kalman-smooth and de-bias it
  (`server/ingest_waqi.py:21-22,137-142`). "Wrapper" can't invert.
- `/health` `sources.model.source` = `waqi+dpcc-stations+open-meteo/cams` —
  the fused feeds, plus ~67 FIRMS fire detections feeding a smoke
  modifier (×1.08–1.24 across today's reads) that's echoed inside the
  plan doses themselves.
- The engine is ours: `engine:"alive_core"` (C++/Eigen;
  `server/core/bindings.cpp`), routing over 1,070,459 real edges
  (`/health.routing`).
- And the decade product under the "typical" comparisons: the OpenAQ
  public-archive climatology — 125 stations × ~10 years of hourly
  readings (the "9.04M measurements" figure was the raw-row count,
  never independently re-verified), named in
  `/health.history.source`.

## 10. "Your community map shows 44 trips. That's nothing."

**Stage answer:** "Correct — it's 44 real donations from dev devices,
and the reason the map isn't fuller is the k≥3 gate doing its job:
43 of 55 tracked corridors are suppressed today because not enough
distinct devices crossed them. We'd rather show the suppression
counter than pad the map."

```bash
curl -s http://65.2.28.40/community
#   obs_total 44 · contributors 24 · avoided_ug_all 1,278.9 — 2026-10-07
#   corridors publish devices counts — every row ≥3 distinct devices
```

It's also the integrity answer to "did you seed it": a seeded map
wouldn't have a suppression mechanism at all.

## 11. "Why should I trust your model over a monitor?"

**Stage answer:** "Don't — it carries its own error bars, calibrated
on held-out stations, and it grades itself every hour. When it's
uncertain it says `confidence:"low"` or shows a wide band instead of
false precision."

**Proof:** measured ±2σ coverage 95.2% on 3,550 held-out
station-hours (`server/data/field_validation.md`), LOO calibration
`MAE 8.8, mean bias +0.2` (`server/data/field_calibration.json`),
and the live `/aqi` at Connaught Place honestly reports its
`nearest_sample_km` with a band that widens where sensors are
farther (59.5–93.4 at the Oct-6 pin). Live self-grade at `/v2/skill` (Q2).

## 12. "Plan me a trip to Mumbai."

**Stage answer:** "It refuses — typed error, no fabricated route."

```bash
curl -sX POST http://65.2.28.40/v2/plan -H 'content-type: application/json' \
  -d '{"from":{"lat":28.6315,"lon":77.2167},"to":{"lat":19.076,"lon":72.8777}}'
#   {"options": [], "error": "outside service area — dose field covers
#    Delhi/NCR only", "code": "outside_service_area", took_ms: 0.1}
```

The service area is the field's real bbox (`/aqi.field.coverage.bbox`
— 76.85–77.75°E, 28.25–28.85°N, 70 cells tonight); edge trips degrade
with `confidence:"medium"`/coverage < 1 rather than extrapolating.

## 13. "The uncertainty bands — real or decorative?"

**Stage answer:** "Real, and you can watch them widen where sensors
are thin — segment σ propagates through the same dose integral, and
thin coverage drops confidence instead of hiding."

**Proof:** `server/exposure.py:341-347` — per-sample krige σ ×
microenv × uplift × VE summed linearly into `dose_ug_lo/hi` (the
conservative bound; independence-assuming RSS is commented out);
confidence tiers at lines 367-374 (`coverage<0.5 → low`; nearest
sample <5 km → high). Today's walk option: 284.6 with band
0–931.3 — the band honestly spans a floor of zero where coverage is
thin, and we show it anyway.

## 14. "Health claims — are you telling people this causes cancer?"

**Stage answer:** "No population-level claims, ever. The product
refuses GBD-style 'years lost' math; the cigarette-equivalent is a
perception unit (Berkeley Earth: 22 µg/m³-day ≈ 1 cig), labelled
`basis:"est."` on the wire, not a diagnosis."

**Proof:** `docs/plan/alive-depth.md` "What we refuse" — no health-
outcome claims, no fake precision, no behavioral nagging.
`server/exposure.py:169-171` — `CIG_UG = 316` with its basis string
served in the payload; `GET /v2/city` `breath` block reads
"day of breathing ≈ 885 µg / 2.8 cig" with lo/hi, not a mortality
claim. The day surface issues *decisions* ("open windows ~12:30–18:30"),
never prognosis.

## 15. "Show me something that fails — right now, live."

**Stage answer:** "Gladly — the scorecard's horizons are `thin` where
we don't have 5 pairs yet, and the archive has an honest gap in hour
4. Failures are on the wire by design."

```bash
curl -s http://65.2.28.40/v2/skill | python3 -c 'import json,sys;
[print(h["h"],h["status"],h.get("n")) for h in json.load(sys.stdin)["horizons"]]'
#   example output stamped when thin horizons existed; today
#   (2026-10-07) all h+0..h+11 grade `ok` on 304 pairs — run it fresh
curl -s http://65.2.28.40/v2/archive | python3 -c 'import json,sys;print(json.load(sys.stdin)["coverage"])'
#   recorded [1,3–16] · gaps [0,2] · pending [17..23] today — never back-filled
```

Also live tonight: `nh3: null` in `/aqi` (the feed doesn't serve it —
empty, not zero-filled). OpenAQ stays dormant in
`/health.sources.stations` (the adapter exists but stays off without a
key — WAQI + DPCC carry 52 instruments today — the sources table
names what is up instead of padding).

## 16. "Fine — what's the moat if I copy the UI tomorrow?"

**Stage answer:** "Copy the UI in a weekend. The pipeline under it —
a C++ kriging engine re-pricing a million edges every 15 minutes,
bands calibrated on 3,550 held-out station-hours, a three-arm planner
that degrades by naming its dead arm, and a privacy transform chain —
is what's hard, and it's the part that's verified tonight."

**Proof:** `engine:"alive_core"` (`/health`); the re-priced graph
`/health.routing` = 1,070,459 edges; the calibrated-band file
`server/data/field_validation.md`; the 20 s / 4-arm budget and named
`degraded` set in `server/v2/plan.py:1131,1981`; the aggregate-at-
ingest store in `server/community.py:_fold`. A demo is easy to
imitate; a verified pipeline isn't.

---

### Numbers a judge might re-derive on the spot (all live tonight)

| claim | where | today (2026-10-07 ~11:00 UTC, `698cf808`) |
|---|---|---|
| dose spread CP→Gurugram | `POST /v2/plan` | car-AC 7.2 vs walk 237.9 µg → 33.0× |
| options per plan | same | 16–24 rows incl. metro+walk + corridor alternates |
| day windows | `GET /v2/day` | both honestly null today (flat moderate 61–75, mean 67.5) — `decisions` says so in words |
| leave-later | `GET /depart` | demo OD: now 20.7 → worst +19 h 45.2 (2.2×), +23 h 17.3 (−16% row present; script OD read 0/absent) |
| breath-of-the-city | `GET /v2/city` | ~620 µg/day ≈ 1.96 cig; −24.0% vs the typical October median today (`vs_now_pct` drifts hour to hour; re-read live) |
| stations / samples | `GET /health` | 52 instruments (WAQI + DPCC both ok, drift band 52–54) + ~97 model samples; field age ~7 min |
| engine | `GET /health` | `alive_core`; 1,070,459 edges / 903,058 priced |
| self-grade | `GET /v2/skill` | 304 pairs — all h+0..h+11 `ok` (h+0 MAE 3.8, h+11 37.2 / band-hit 37.7%) |
| reach | `GET /v2/reach` | walk@25 µg → 3,767 edges / 167.9 km; walk@50 → 11,409/618.0; car@25 → capped 993,344, `edge_partial` |
| community | `GET /community` `/v2/city/moves` | 44 obs / 24 contributors / 1,278.9 µg avoided; 12 of 55 corridors publishable, k=3 |
| archive | `GET /v2/archive` | recorded[1,3–16], gaps{0,2} today — grows hourly; honest gaps stay unbackfilled |
| cause note | `GET /v2/why` | `cause_note` live since `795ff3b`: "12 fires in the Punjab–Haryana belt — the wind isn't carrying it this way right now · city mean 60.6 → 46.8 over 5.8 h"; trend primary, fires refused on SW wind |
| admin | `GET /admin` | gate card since `b563da2` — sign in via `POST /v2/admin/login` (HMAC HttpOnly cookie ~8 h) |
| outside-area | `POST /v2/plan` to Mumbai | typed `outside_service_area`, ~ms |
| reroute | `POST /v2/reroute` | fresh option set + route_id |
| field species | `GET /aqi` | pm2.5 64.5 bz / 60.8 ambient today · pm10 · no2 · o3 · co · so2 · dust · aod; nh3 honestly null |
