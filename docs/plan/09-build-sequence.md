# 09 · Build sequence, acceptance, testing

Ordered so the product is demoable after every phase. Each phase ends with: lint + typecheck (mobile), pytest (server), live API suite against AWS, and a recorded run on the iOS simulator + Android device/emulator.

## Phase 0 · Foundations (owner unblocks + infra)
- Owner: station-data key, rule re-check, spend cap (doc 00).
- Create Amazon Location API key (maps + places), S3 `alive108-air`, DynamoDB `alive108-agg`, EventBridge schedules, CloudWatch dashboard + alarms, AWS Budget alarm.
- Deploy script registers NLB targets automatically.
**Accept:** `/health` shows sources + field age; dashboard visible in console.

## Phase 1 · Search that feels instant
- Server `/v2/search` with T2 (Amazon Suggest) + reverse geocode; drop Photon from hot path.
- C++ `alive_core.search` T1 + corpus build; benchmark.
- App: new search screen (doc 02 S2) with T0 + server merge, cancellation, recents.
**Accept:** on a real Android phone on 4G in Delhi, 20 test queries (list in `tests/search_queries.txt`: malls, blocks, gates, metro exits, restaurants, Hinglish typos) — first row <16 ms, correct place in top 3 for ≥18/20, full list <300 ms p95.

## Phase 2 · Dark detailed map + new shell
- Amazon Standard Dark style with overrides (doc 03), new pins, puck, buildings.
- Design tokens, Inter, icon set; delete everything on the doc 02 delete list.
- New hamburger sidebar (structure only, real data where present).
**Accept:** side-by-side screenshots vs Google Maps dark at 5 Delhi locations; pixel review on iPhone 17 sim + Android phone (safe areas, notch, gesture bar, 130% type).

## Phase 3 · Plan: options with breath + smoke-out
- Vehicle question (S8) and storage.
- `/v2/plan`: Routes v2 (traffic) + GTFS + walk/cycle; dose band; emission chain; ranking rule; one-line reason.
- Options sheet (S4), trip preview (S5).
**Accept:** 10 fixed Delhi O-D pairs produce sane options (metro wins both on long trips; tags correct on a constructed trade case); unit tests for emission chain reproduce ARAI reference values.

## Phase 4 · Live trip
- Navigation engine (doc 04 §4), voice, reroute, two counters, background tracking, receipt (S7), `/v2/trip` upload with privacy rules.
**Accept:** a real 20-minute drive or ride in Delhi: puck stays on road, ≥1 reroute handled, counters tick smoothly, receipt numbers equal server recomputation from the uploaded summary within band.

## Phase 5 · Live air index + Delhi today + admin
- Ingest worker on EventBridge, H3 index, S3 snapshots, daily rollup, validation job.
- Consumer "Delhi today" page; admin rebuild on aggregates.
**Accept:** 24 h of continuous snapshots in S3 with no gap >30 min; dashboard numbers equal a recomputation from DynamoDB.

## Phase 6 · Polish, proof, submission
- Hindi strings, accessibility pass, battery measurement on a real phone (1 h nav), crash-free run.
- Bench results doc; validation doc; README rewrite against doc 10.
- Video per doc 01 arc; Builder Center writeup; public repo per the event-date rule decision.

## Testing matrix
| Layer | How |
|---|---|
| Server | pytest unit + `test_api.py` live suite (extend for /v2) |
| C++ | Catch2 + parity vs Python + benchmarks |
| Mobile | `npx expo lint`, `npx tsc --noEmit`; iOS simulator scripted runs; Android release APK on a physical phone |
| Search quality | fixed 20-query list, scored every build |
| Science | reference-value tests (ARAI, Delhi mode ratios) |

## Effort (our throughput)
Phases 0–2 ≈ 1 session; 3–4 ≈ 1 session; 5–6 ≈ 1 session. External waits: owner keys, real-phone test drives in Delhi (owner), Apple account (not available — iOS stays simulator-only).
