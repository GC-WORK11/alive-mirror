# demo-reverify-v2 — every-beat truth pass on the demo docs

Date: 2026-10-06, ~11:07–11:40 UTC (16:37–17:10 IST).
Live build at probe time: **`4eb9e1e8`** (`/health` `build_sha`), ECS
`alive108` task-def `:181`, image `alive108-api:4eb9e1e8` (boto3
describe-services + describe-task-definition — image tag == `/health`
`build_sha` == `/admin/api/status` `build_sha`, the last one probed
**with** the token this pass — `alive108/admin-token` pulled from
Secrets Manager). The lag wart is resolved on this revision.
Base: `http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com`
(NLB hostname, HTTP :80). Probe rules honoured: **GETs + POST /v2/plan +
POST /v2/reroute + GET /v2/strip only** — no /v2/feedback, /observe or
/v2/trip writes. No deploys, no server/app code touched — docs only.

## Headlines this pass

1. **The fire story flipped.** `/v2/why` `drivers[0]` is now
   **`stubble_smoke`** — line: *"stubble smoke drifting in on the
   north-west wind"*. 60 fires on the wire, 14 inside the NW burn belt
   (34.0 MW FRP), wind 4.8–5.0 km/h @315–322° — inside the NW gate →
   `carrying:true`. Modifier math verified against `server/fires.py`:
   idx = 14/160 = 0.0875 → `1 + 0.0875 × 2.75 = 1.24` — `smoke_modifier
   1.24` echoes on `/aqi`, `/v2/plan` and `/v2/reroute`. Every doc line
   that said "fires refused / honestly not claimed" is updated
   (operative text; stamped pass-history left alone). The gate still
   exists — a southerly wind flips it back; T-45 re-check stays.
2. **The admin flow changed shape.** `/admin` is a **public board** —
   no `prompt()` on load; public panels (field map, district chips, KPI
   tiles) render immediately with honest "gated" marks on internals.
   The masthead **"operator sign in"** chip prompts on demand, flips to
   "sign out" (`sessionStorage.alive_admin_tok`, `alive_admin_tok_no`
   opt-out). `/admin/api/*` returns 401 without Bearer — all 8
   endpoints probed 200 with the token.
3. **Every horizon on the scorecard is graded now** — `/v2/skill` 131
   pairs, h+0..h+11 all carry MAE/bias/band-hit (no `thin` left).

## Beat-by-beat verification — `beat | doc claim | live value | verdict`

| beat | doc claim | live value (evidence) | verdict |
|---|---|---|---|
| landing `/` | live raster + wind arrow + scrubber | 200, 82,834 B; canvas/`/grid`/wind-arrow/`watch-the-day`/`a→b` all present | OK |
| `/aqi` @CP | US AQI ~160, 24 instruments + ~70 samples, fires feed modifier | us_aqi **158–159**; pm2.5 breathing 84.9–88.2 / ambient ~69–71; stations 24→13 mid-pass (staleness, honest); samples 61–72; fires 60/14 belt/34.0 MW; modifier **1.24**; grap indicative_stage 0 | UPDATED (fires/modifier/station range) |
| dose gap `/v2/plan` CP→Gurugram | "~35×", ~11 vs ~359, 23–24 opts | car-AC **8.8** · car-open 16.1 · bike 20.3 · bus 23.1 · auto 26.2 · metro+walk **37.5** · cycle 130.0 · walk **293.2** → **33.3×** (slowest/best 37.4×); 20 opts | UPDATED |
| dose gap `/v2/plan` IG→HCC (demo OD) | ~12 vs ~430–450, ~36× | car-AC **9.9** / walk **355.0** → **35.9×**; 21 opts; metro+walk 43.9 | UPDATED |
| plan latency | ~47 ms warm / ~6–8 s fresh | warm `took_ms` **55.8** (IG→HCC), **660.5** (CP→Ggn warm re-hit); fresh OD **6.6–7.4 s** | UPDATED (still "under 2 s on the rehearsed trip") |
| `/v2/why` | stagnation + fires refused (all prior passes) | **`stubble_smoke` claimed** — `carrying:true`, 14 belt/34.0 MW, wind 315° NW, ×1.24; stagnation VC ~2,485 m²/s; trend lit +5.4 µg/5.9 h/28 snaps; `cannot_tell: []` | **FLIPPED — docs updated** |
| `/v2/day` GRAP | stage 0, indicative-only, `?lat&lon` required | `equivalent_stage 0, aqi 152`, basis "cpcb aqi of day_mean_pm25", "computed from today's air, not the official CAQM declaration"; bare call 422s | OK (copy rule holds) |
| `/v2/day` windows | both populated, 3 decision rows | **both null** — flat moderate all day (71–82); `decisions` 1 row ("no meaningful window today" — the `88e37d5` fallback line); day mean **75.6** | UPDATED |
| `/v2/city` | breath ~795 µg ≈2.5 cig; grap stage 0 | breath **576 µg mid / 1.82 cig**; grap `equivalent_stage 0, aqi 65`; `next_hours` 71.1→86.2 | UPDATED |
| `/v2/city/moves` | 39 trips/7d, car 82.1% | 39 trips, car 82.1% + other 17.9%, **0 suppressed**, corridors 12/54 | OK |
| `/v2/districts` | 29 chips (16 districts + 13 sub-areas) | 29 rows | OK |
| `/admin` public board | (stale: "paste token on load") | public board live; "operator sign in" chip; `/admin/api/*` 8/8 → 401 without token, 200 with | **FLOW UPDATED** |
| `/admin/api/*` internals | sources/donations/corridors/model/timing | sources: model 61 samples + WAQI 13 readings + met 5.0 km/h @322°; donations 39 trips/167.6 km/104.1 µg/12.73 kg CO₂/4 switched; corridors 12 rows k≥3 (hanuman lane 13 trips/10 devices …); model card microenv+VE tables; timing p50 ≤10 ms on hot paths; LOSO n=24 MAE 11.31 bias −0.26 | OK (probed with token this pass) |
| `/v2/skill` | 80 pairs, h+1..h+9 graded | **131 pairs — h+0..h+11 ALL graded**: h+0 2.2/+1.0 (93.4% cell/100% hr), h+1 9.4/+6.6, h+11 54.5 | UPDATED |
| `/v2/archive` | 15 snapshots | **21** (Oct-5 20:00 → Oct-6 16:00 IST); today 17/17 hours, **0 gaps** | UPDATED |
| `/depart` 120 h | now ~29 → worst ~103, 104 slots | now **20.9** → worst **113.2** @+63 h (5.4×); best **15.5** @+47 h; **109 slots** | UPDATED |
| `/escape` | escape-veil lattice | best cell **27.2 µg/m³** @ 27.5 km — **62% less than here** (71.1); 16×12 lattice, photon reverse-name live | OK |
| `/directions` | plain-English OSRM steps | 23.7 km / 28 min / **12 steps**, osrm-local, depart/arrive preserved | OK |
| `/community` | 22 obs / 14 contrib / 725.9 µg | all-time unchanged; 24 h: **3 obs / 4.6 km / 392.4 µg** avoided | UPDATED (24h reads) |
| `/v2/reach` | ~109/~477/~83,642 km | w@25 **3,105 edges/136.1 km**; w@50 **10,436/550.6 km**; car@25 **996,064/93,720.8 km** `edge_partial:true` | UPDATED |
| `/v2/strip` | 82 samples, ~1.27× span | re-minted `4eb9e1e8` recommended car row (route_id `99f4a4528229`): **82 samples @250 m**, pm2.5 **52.2→85.9** (1.65×) | UPDATED |
| `/v2/reroute` | fresh route_id, expiry ~1 h | 200 — new route_id minted | OK |
| `/grid` default | 484 cells, gzip ~9–11 KB | 484 cells, **8,525 B** gzipped, ~0.49 s | UPDATED |
| `/grid` species pills | 10 live, ammonia empty | `param` without `h`: pm10/no₂/o₃/co/so₂/dust/aod/us_aqi all **484/484**; `ammonia` **0 features** (honest empty upstream). `?h=N` is pm2.5-only forecast by design — pill probes must omit `h` | OK (probe note documented) |
| pm25↔no₂ | r=+0.55 (was +0.34) | r=**+0.47** over 484 cells — drifts; "the maps are chemically different" claim holds | UPDATED |
| us_aqi grid | 91→166 | **82→158** | UPDATED |
| grid confidence | hi 31/med 62/lo 7% | hi 33/med 62/lo 4% | UPDATED |
| `/tiles/health` | ok, 22.7 MB, z0–14 | `ok:true`, 22.7 MB, z0–14 | OK |
| fires feed | 89/22/76.8 MW | **60/14/34.0 MW** | UPDATED |
| ECS/AWS | ACTIVE 1/1 FARGATE_SPOT `:178` image f4139b24 | ACTIVE 1/1 FARGATE_SPOT (weight=1, base=1), task-def **`:181`** cpu 1024/mem 3072, osrm sidecar mem:1024, image `alive108-api:4eb9e1e8`, task RUNNING since ~10:58 UTC | UPDATED |
| gazetteer flag | 123,934 vs 124,311 dual-count | verify_numbers.sh flag re-checked — known dual-count (server copy 123,934 ≠ bundled 124,311); flag wording stands ("say which") | OK (known wart) |

`scripts/verify_numbers.sh` was run end-to-end against live this pass
(`server/.venv312/bin/python3`, 3.12.14) — full figure table printed;
2 flags, both benign: the gazetteer dual-count (above) and a `×1.27`
smoke figure in `demo-script.md` Pass-3 history (stamped, correct as
history).

## Docs changed

- `docs/demo-day.md` — header stamp → this pass/`4eb9e1e8`/`:181`; new
  drift-note block; admin demo flow rewritten (public board +
  "operator sign in" chip); why beat → stubble_smoke claimed with the
  14/160→×1.24 math; T-45 checklist: spread, ladder, day windows
  (null today), fires/modifier, archive 21, options 20–21, build_sha
  (status token-probed), skill 131/all-graded, why line, stations
  13–24, breath 576/1.82 cig, reach 136/551/93,721; pitch line ~9 vs
  ~293; judge's-90-seconds ≈10/≈355; why-chip description; task-def
  `:181`; WAQI 24→"up to 24 (13–24 on the wire)"; grid gzip ~8.5–11 KB.
- `docs/plan/NUMBERS.md` — §2 header + every drift row re-read on
  `4eb9e1e8`; build_sha wart section (resolved, admin status
  token-probed); §3 dose-gap/annualized/reach/option-count refreshed;
  §4: two rows added (fires-flip, admin public-board flow).
- `docs/submission/repo-readme.md` — dose ladder table (8.8→293.2,
  metro+walk 37.5 live), spread 33.3×/35.9× demo OD, day windows →
  flat-moderate "no meaningful window" (mean ~76), reach caption 136
  km, stations 13–24 + samples 61–72 + fires 60/14 ×1.24, build_sha
  wart → resolved on `4eb9e1e8`/`181`.
- `docs/submission/video-shotlist.md` — why beat verbatim →
  stubble-smoke-claimed + flip-back caveat; admin-beat pipeline numbers
  (13–24 WAQI, 61–72 samples, fires 60/14); archive tile 21/17-of-17;
  skill card 131 all-graded; breath ticker 576; trim-plan reach 136
  km/~690×; drift table rows (ladder, day windows, reach, field age,
  fires/modifier, breath/community, why, build_sha, skill, archive).
- `docs/plan/demo-script.md` — header re-verify note; beat-1 wind
  ~315° NW; beats 2/3/4/5/6 verbatim + verified columns re-read;
  numbers sheet (re-verified stamp, field/air, routing, honesty, AWS
  rows); do-not-say list: fires-refused line + fires range + walk reads
  updated.
- `docs/plan/judge-qa-v2.md` — the fires worked-example rewritten to
  tonight's real math (14/160 = 0.0875 → ×1.24, NW no downscale; gate
  still real, re-check on the day).

## Named honestly — not verifiable this pass

- APK binary `0b11123` — not re-driven on-device this pass (docs-only
  lane); timings quoted from the apk-final report.
- The corridor-divergence numbers (96/55/19%) from prior passes not
  re-derived — kept labelled "earlier field".
- Wind direction will drift — the fires-claimed state is tonight's;
  `curl $NLB/v2/why` before stage is mandatory.
