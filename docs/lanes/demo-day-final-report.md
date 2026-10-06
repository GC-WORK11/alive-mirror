# demo-day-final — final truth pass on the demo docs

Date: 2026-10-06, ~05:10–05:35 UTC (10:40–11:05 IST).
Live build at probe time: **`f4139b24`** (`/health` `build_sha`), ECS
`alive108` task-def `:178`, image `alive108-api:f4139b24` (boto3
describe-task-definition — image tag == build_sha; the lag wart is
resolved on this revision).
Base: `http://65.2.28.40` (NLB IP, HTTP :80). Probe rules honoured:
**GETs + POST /v2/plan + POST /v2/reroute only**. No deploys, no
server/app code touched — docs only.

## What changed in the docs

- `docs/demo-day.md`: last-verified line at top; new drift note
  (demo-day-final block); dose ladder, why-numbers, skill, archive,
  day windows, breath, reach, options count, build_sha, task-def
  `:141/:153 → :178`, Spot pre-state re-verified — all updated in
  place. New section: **"The judge's first 90 seconds (demo binary
  `0b11123`)"** — cold-open (~452 ms measured on the apk-final box) →
  consent (the owner's real choice on camera) → sparse hero (band-dot
  arc + "N of 3 samples" meter, never a fake number) → first live
  number ~3 s → three taps to the dose gap (from-row India Gate → dest
  Huda City Centre → compare-sheet "+N vs lightest · N×" rows).
- `docs/plan/demo-script.md`: header re-verify note; beats 1–5 & 7
  verbatims + verified columns re-read; numbers sheet refreshed;
  do-not-say list updated (walk reads, fires, "~70 ms", metro claim);
  Pass 6 rehearsal log added; AWS beat + CLI understudy output →
  `:178`.
- `docs/plan/judge-qa-v2.md`: §7 "beat persistence" rewritten — the
  persistence-blend deploy landed since it was written; the claim is
  now EARNED (see below). Risk-register row updated. GRAP "live now"
  block re-read (stage 0 / aqi 110 day · 0 / 92 city this morning).
  Breath wire-read note updated (mid ~795 µg ≈ 2.52 cig today — it
  scales with the field mean).

## Live evidence per figure

| figure | doc(s) quoted | live read (evidence) | command |
|---|---|---|---|
| breath | ~795 µg ≈ 2.5 cig | `breath.day_inhaled_ug.mid 795.0`, `cigarettes.mid 2.52` (basis: 22 µg/m³-day ≈ 1 cig, ~14.4 m³/day) | `GET /v2/city` |
| dose gap (demo OD) | ~12 vs ~430–450, ~36× | call1 IG(28.6129,77.2295)→Huda(28.4594,77.0725): car-AC 12.6 / walk 451.5 µg; warm re-hit: car 11.9 / walk 427.2 → 35.8–35.9× | `POST /v2/plan` |
| dose ladder (script OD) | ~11 vs ~359, 33.3× | CP(28.6315,77.2167)→Gurugram(28.495,77.089): car-AC 10.8, car-open 19.7, bike 24.9, bus 28.3, auto 32.1, metro+walk 42.9, bus-GTFS 89.5 ("Bus 729 → UTTAMNAGAR(T)"), cycle 159.2, walk 359.1 | `POST /v2/plan` |
| option-count RANGE | 19–24 | three calls inside minutes: 23 (IG→Huda), 24 (CP→Ggn), 19 (CP→Huda) — range confirmed live; docs keep saying "range, never an exact count" | `POST /v2/plan` ×3 |
| plan latency | ~47 ms warm / ~6–8 s fresh | IG→Huda warm `took_ms` 47.4; first-hit on the fresh OD `took_ms` 6,807 | `POST /v2/plan` timing fields |
| reach km | ~109 / ~477 / ~83,642 | walk@25 = 109.1 km (1,801 edges); walk@50 = 476.7 km (8,624); car@25 = 83,641.8 km (939,807 edges, `edge_partial:true`) | `GET /v2/reach` |
| why-history span | −6.0 µg / 5.7 h / 29 snapshots | trend: evaluated, 29 snapshots, −6.0 µg over 5.7 h (88.5→82.5); `cannot_tell: []` | `GET /v2/why` |
| stagnation (why) | VC ~1,252 m²/s | BLH 845.8 m + wind 1.48 m/s → VC ~1,252 vs ~3,000 typical; fires refused `carrying:false` (S wind 138°) | `GET /v2/why` |
| GRAP line | stage 0, indicative-only | `/aqi` `grap.indicative_stage: 0` (basis_pm25 83.3, "indicative only — legal GRAP stage is declared by CAQM"); `/v2/day` `equivalent_stage 0, aqi 110`; `/v2/city` `equivalent_stage 0, aqi 92` — both carry "computed from today's air, not the official CAQM declaration" | `GET /aqi?lat=28.6315&lon=77.2167`, `/v2/day?lat&lon`, `/v2/city` |
| blend claim | "blended onto the live field" — never flat "beats persistence" | `forecast.live_anchor.blend` on `/depart` + `/v2/plan` wires: `hold_h 2.0, end_h 40.0, w_h11 0.763, fitted_on "served-vs-recorded archive pairs, 2026-10-05/06 IST"`. Claim status per docs/lanes/forecast-skill-report.md: EARNED pooled (blend 11.21 < persistence 13.07 < pre-blend 39.21 µg/m³; ≤ persistence h+1–4; strictly better h+5+). Own quick-check on `/v2/archive` cells: raw hour-to-hour persistence h+1 MAE ≈ 6.0 µg (1,210 cell-pairs) — consistent with the report's persistence 6.1 at h+1; inside the 2 h hold blend IS persistence by construction (w=1). | `GET /depart`, `POST /v2/plan`, `GET /v2/archive` |
| skill | 80 pairs, h+1..h+9 graded | h+1 MAE 12.2 / +9.4 (72.2% cell, 72.7% hour); h+2 21.4; h+3 31.7; h+4 37.0; h+5 44.9; h+6 51.0; h+7 54.5; h+8 60.2; h+9 63.6; h=0,h+10,h+11 `thin` | `GET /v2/skill` |
| archive | 15 snapshots | recording since 2026-10-05 20:00 IST → last 10:00 IST today; hours 0–10, 0 gaps | `GET /v2/archive` |
| depart | 28.7 → worst 102.7 / best 16.0 | CP→Gurugram: now 28.7, worst 102.7 @ +83 h, best 16.0 @ +51 h, 104 slots. IG→Huda: now 31.4, best 17.7 @ +52 h, worst 115.5 @ +83 h | `GET /depart` |
| day windows | evening-heavy | 14 h; mean 62.7; heavy ~19:30 → day end @ 76.0; cleanest 14:30–18:30 @ 52.7; 3 `decisions` rows; `?lat&lon` required (bare call 422s) | `GET /v2/day` |
| community | 22 obs / 14 contributors | 5 obs / 10.4 km / 432.4 µg avoided in 24 h; 725.9 µg all-time | `GET /community` |
| corridors | 10 publishable | `/v2/city.corridors` serves 10 k≥3 rows (docs said 12 — drifts) | `GET /v2/city` |
| moves | 39 trips/7d | car 82.1% + other 17.9%, 0 suppressed | `GET /v2/city/moves` |
| field | 24 stations / 72 samples | `/aqi` field.age_s 879, stale false; fire block live: 89 fires (22 belt, 76.8 MW), wind 135°, modifier 1.11; wind 5.1 km/h @138° | `GET /aqi` |
| grid/species | 484 cells, 10 live | pm25/no₂/us_aqi/pm10 all 484 cells @h0 and h12; `param=ammonia` 0 features (honest empty); pm25↔no₂ cell corr r=+0.55 (was +0.34); us_aqi range 91→166 | `GET /grid` variants |
| edge band | widens with distance | /aqi NE corner (28.85,77.85): pm25 54.2, band 10.7–97.7 at nearest_sample_km 11.1 | `GET /aqi` edge |
| strip | 82 samples, 1.27× | re-minted on the recommended car row IG→Huda (`route_id 2d14284c3e03`): 82 samples @250 m, pm2.5 64.5→82.2, dose-share Delhi-Gurugram Expressway 29.6% / Sardar Patel Marg 19.5% — the least-smoke `rd` row still strips 'unnamed road' | `GET /v2/strip` |
| tiles | ok | `ok:true`, 22.7 MB, z0–14 — matches `warm_task.py`'s expected tail | `GET /tiles/health` |
| ECS | ACTIVE 1/1 FARGATE_SPOT :178 | `describe-services`: ACTIVE, running 1/1, `capacityProviderStrategy FARGATE_SPOT weight=1 base=1`; `describe-tasks`: `capacityProviderName FARGATE_SPOT`; task-def `:178` cpu 1024/mem 3072, osrm sidecar `memory:1024` (the bump-runbook warning holds) | boto3 describe-services/tasks/task-definition (read-only) |

## Verbatim blocks — dry-verified, all still correct

- **T-60 flip** (`aws ecs update-service … FARGATE … --force-new-deployment` + wait + describe-tasks `capacityProviderName`): pre-state re-verified live (Spot weight=1 base=1, 1/1). Post-verify commands still match the API shapes returned today.
- **`tools/warm_task.py` T-40**: walks /health, /aqi, /grid, POST /v2/plan on 12 NCR ODs until `steps_source:"endpoints"`, /reports, /v2/city, /grid?h=12, /v2/day?lat&lon, /v2/reach walk@25/50+car@25, /v2/outlook, /v2/why, /v2/skill, /v2/archive, /community, /tiles/health. Exit 0 = warm. All surfaces exist on the wire today.
- **`scripts/verify_numbers.sh` paths**: GETs + one POST /v2/plan on CP→Gurugram only — inside probe rules; needs python ≥3.12 (f-string nesting; `server/.venv312/bin/python3` fallback).
- **`scripts/public-repo.sh` FIRST-step squash-baseline**: flags `<url> [--ref <branch>] [--dry-run] [--force]` verified against the script; guardrails >100MB abort / >50MB warn / secrets scan live; default ref `base/v2` on divergence — verified benign: base/v2 vs main differ only in 5 doc files (product trees identical), so the default picks the correct product state. Dry-run exercised.
- **`docs/plan/aws-console-shotlist.md`**: exists; saves as `~/video/beats/80_aws.mov`, beat 6 (2:05–2:30) — matches `scripts/video/assemble.sh` wiring (`80_aws.mov|mp4`).

## Named honestly — not verifiable this pass

- `/admin/api/status` internals (`archive.snapshots_total`, sources table) — token-gated; read the console at T-45 instead. The public surfaces covering the same story were all probed.
- `?hours=120` slot-count on `/depart` — not re-probed (default window read 104 slots ~87 h; the "forecast-limited" phrasing is kept).
- `verify_numbers.sh` not executed end-to-end — this box's python3 is 3.9 (needs ≥3.12; the repo venv path is the documented fallback). Header/flags/paths reviewed + every endpoint it hits was probed live.
- The divergence numbers (alt1/alt2/rd %) from prior passes not re-derived — marked "earlier field" in the doc, as before.
- APK binary `0b11123` — not re-driven on-device this pass (docs-only lane); timings quoted from the apk-final report (14/14 PASS, +452 ms cold-open, ~3.5 s first number). The sparse-hero and dose-gap render paths were re-read from source (HomeScreen ~L1095, CompareSheet ~L405).

## Files changed

`docs/demo-day.md`, `docs/plan/demo-script.md`,
`docs/plan/judge-qa-v2.md`, `docs/lanes/demo-day-final-report.md` (this).
