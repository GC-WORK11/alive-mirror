# ALive-108 — FULL HANDOFF (you are the new lead session; keep working for hours)

Repo: <owner>/Delhi-Air-108. Working branch: base/v2. main is merged up to base/v2 as of this handoff. Work on base/v2: `git pull --rebase origin base/v2`, make small focused commits with `git commit -m`, `git push origin HEAD:base/v2`. Merge base/v2 → main (no-ff) at stable checkpoints after the tests pass. Never force-push. PR #4 (https://github.com/<owner>/Delhi-Air-108/pull/4) is the historical full-product PR. The owner wants direct pushes, no new PRs.

Owner: govinda (<owner>). He is building this for the AWS×WeMakeDevs Environmental Hacks, Track 01 Air, Oct 8–11 2026. The prize and the Amazon fast-track matter a lot to him. He wants you to work continuously and not stop after 1–2 hours. Message him with concise, honest progress.

## Product (one line)
Type from and to: in milliseconds a C++ engine searches Delhi/NCR's 1.07M road edges, each priced by the smoke on it this minute, and returns the route your lungs pay least for, with an honest uncertainty band.
It has two faces: (1) the personal mobile app (Android = the released product; iOS = demo only), and (2) a light-theme admin dashboard plus a public /city page giving Delhi/NCR exposure and emissions overview, aggregates only.

## Owner's non-negotiable rules (from the full prompt history)
- No dummy code, no dummy data, no fake features, no fake "live" counters, no fabricated numbers. Every number must be real or explicitly labeled as an estimate with a band.
- The core is a least-INHALATION decision: the route is chosen by estimated inhaled dose on the real-time field (PM2.5 + other species), over legal, sane roads. Time and distance tradeoffs stay visible. No LLM for the core decision: deterministic physics is the explainable answer.
- Cigarette equivalents are OFF by default and are never a headline. They exist only behind a settings toggle. Default framing is estimated µg with bands. Never write "actually breathed".
- Emissions are calibrated from the user's vehicle PUC certificate (one-time setup: BS class + CO%/HC/smoke readings), not from generic fleet guesses.
- Admin shows aggregates only ("we had N journeys"). Never show who, from where, to where, or per-user cigarettes. Corridors need k≥3 distinct devices over 72h. A banned-key test guards every admin endpoint (token/lat/lon/coord/trajectory/points/geometry/route/contributor/user/uid/uuid/device_id/ip; use "path" not "route" in timing output).
- Admin is LIGHT theme (he loves it). Use the official CPCB AQI colours and the 13-district NCR choropleth. Animated data elements must be driven by real changing data.
- Coverage is the NCR commute-shed, not just the NCT: Delhi + Ghaziabad/UP + Noida/Greater Noida + Gurugram/Faridabad/Sonipat (Haryana). Field bbox is 76.8–77.9°E × 28.2–28.95°N. Panipat is outside the corpus and is an honest coverage ceiling.
- Search must reach every house and landmark, home-to-home, in milliseconds: bundled on-device gazetteer (124,334 rows, <5 ms) plus server tiers (~97k corpus, 16,952 address rows). Never fabricate a location; honest empty/ambiguous is fine.
- $0 this month: Cost Explorer showed $0.00 for Oct 1–4 (credits). ECS runs on FARGATE_SPOT. Do not add paid APIs or infra without asking him. Self-hosted OSRM (~$10–15/mo) is HIS decision.
- DO NOT touch the Pocket Rig project or its 2 agents (separate repo <owner>/remote).
- Never expose secrets. He was told to rotate the OpenAQ key and the Devin API key he once pasted in chat.

## Live system
- NLB: http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com (HTTP port 80 ONLY; never :8000 or https). EIP 65.2.28.40.
- AWS ap-south-1, ECS cluster `alive108` / service `alive108`, TG alive108-tg, log group /ecs/alive108, CodeBuild alive108-build.
- Deploy: `bash scripts/deploy.sh` (zips server/ → CodeBuild → ECR → new task def → ECS → TG verify). As of 76e46b4 it gates on the PRIMARY rolloutState and picks the task on the new task def. That fixed a race that evicted the fresh target. Verify with `curl $NLB/health` (build_sha) after every deploy.
- Admin token: AWS Secrets Manager `alive108/admin-token`. Locally it's in ~/.alive_admin_token if present, otherwise read it from Secrets Manager. Use it as a Bearer header on /admin/api*.
- Key endpoints: /health, /aqi, /grid, /v2/plan (POST; `fast:true` = engine-only rows, `partial:true`), /v2/reroute, /v2/search, /v2/reverse, /v2/districts, /v2/strip, /v2/trip (donation), GET+DELETE /v2/ledger, /city, /admin, /admin/api, /admin/api/status, /admin/api/timing.

## Code map
- server/ — FastAPI. v2/plan.py (planner: motor/slow/engine/transit arms raced with asyncio.wait; PLAN_BUDGET_S 20, ENGINE_BUDGET_S 8, TRANSIT_BUDGET_S 12; `_engine_options` least-inhalation rows with `engine_dose_ug`; `_dose_surface` = one raster for every row), airfield.py (live kriged field + σ), forecast.py (semi-Lagrangian advection; anchor tau 9h; future-hour overshoot falls back to the model value, hour-0 live zero stays zero), community.py (k≥3 corridors, `_obs_km/_obs_cells` legacy-safe), admin_agg.py + admin.html (board), emissions.py (`_puc_calib`), routegraph.py (Python twin), core/ (C++ alive_core PathEngine, pybind; rebuild `server/core/build312` via server/core/build_ext.sh after C++ changes).
- Mobile/ — Expo SDK ~57, RN 0.86, MapLibre. READ Mobile/AGENTS.md first. Never hand-edit android/ or ios/. Check before every push: `cd Mobile && npx tsc --noEmit && npx expo lint`. Shell state machine: src/components/shell/useShellFlow.ts (engine-first paint + `refining`), CompareSheet.tsx, ReceiptSheet.tsx; screens: SearchScreen, DelhiToday, LedgerScreen, SettingsScreen, VehicleSheet (PUC), OnboardingScreen; search: src/search/t0.ts; strings: src/i18n/strings.ts (en+hi).
- Bridge/contract.ts — shared wire types (server/tests/test_contract_sync.py enforces them).
- Tests: `cd server && PYTHONPATH=core/build312:. .venv312/bin/python -m pytest -q tests`. Last full run: 788 passed, 5 skipped, 1 xfailed. The focused plan/hardening/contract suites (112) passed after the latest changes.

## Docs to read (in this order)
docs/plan/master-plan.md (latest mandate matrix + ranked gaps, written this session), docs/plan/00-README.md … 10-claims-ledger.md (master plan set), docs/plan/runbook.md, docs/plan/test-commands.md, docs/plan/probe-audit.md (174-query search battery), docs/plan/judge-lens.md, docs/claims-audit.md, docs/demo-day.md (iOS sim crash verdict + demo protocol), docs/plan/map-vs-google.md, docs/18-aws-architecture.md, docs/19-submission-checklist.md, docs/20-hackathon-playbook.md, docs/28-pitch.md, docs/17-submission-writeup.md.

## Where we are (latest)
Shipped and live this session:
- engine-first paint (c1d9629). The app paints least-smoke engine rows first, then swaps in the full set, keeping the user's pick.
- fast paint uses primaries only (d6ea7b7).
- motor/slow row dosing moved off the event loop (734dbb9). Fixes a 34s cold first plan against the 20s budget. COMMITTED; VERIFY THE DEPLOY IS LIVE (build_sha ≥ 734dbb9) and re-measure a fresh-task first plan.
- deploy race fix (76e46b4).
- /admin/api 500 on legacy snapshots (879d291).
- forecast anchor fixes.
- copy overclaims removed (eacc413).
- search: house numbers + multi-anchor + dedupe (4a4854a, location agent).
Measured live: the fast plan returns 15 engine rows in ~1.6–3s server time when idle. The engine arm is 0.15–0.3s idle but 3–7s under concurrent load on 1 vCPU. Gurugram→Ghaziabad fast once hit "engine timed out" at 8s under load. NEXT: make the engine arm robust under concurrency: in-flight dedupe/memo per (rounded OD, vehicle, field epoch) so the fast and full calls share primaries, and/or the full plan reusing fast primaries.

Open gaps, ranked (from master-plan.md):
1. Plan latency and engine robustness under load (above).
2. Search: "aiims" returns platform rows only, with the hospital missing from the top. "lodhi garden" ranks a platform above the park, plus Lodhi/Lodi duplicates. "b-12 lajpat nagar" ignores the anchor and returns Sanwal Nagar (a regression). The location agent has been told; verify live.
3. Android TTS (500/150/0m cues) + gfxinfo jank are still unmeasured. The Ultra UI/UX agent on Linux is doing it.
4. Route-quality stats for the pitch: % of least-smoke rows saving ≥10% dose for ≤15% extra time, and absurd detours >1.6× distance, over 40 real ODs.
5. Fresh release APK on the final HEAD (NLB baked; check it in the JS bundle; debug-signed. Real signing needs his keystore).
6. Demo morning: switch Spot → on-demand, warm the task 10 min early, run the demo on a physical Android phone. iOS = recorded take (an upstream MapLibre-on-vGPU sim crash, sim-only).
7. Keep main merged at checkpoints.

## Every session ever run for this project
Active right now:
- 30c986e2137942488c8060da708ef40b: Android UI/UX overhaul on ULTRA, Linux. Peak polish + smoothness, gfxinfo before/after, TTS check, APK. KEEP IT RUNNING; collect its report. https://app.devin.ai/sessions/30c986e2137942488c8060da708ef40b
- 1cb3ac27d94642f29952845945934fc3: Location-depth lane (gazetteer, address/house numbers, reverse geocode, aliases, Hinglish, compound queries, live 174-query battery). Currently fixing aiims / lodhi garden / b-12 lajpat nagar. https://app.devin.ai/sessions/1cb3ac27d94642f29952845945934fc3
Closed for slot reasons (its work is pushed):
- 3fa2600978ae46c18e5e5502253269e6: Routing-depth lane. Shipped corridor alternatives, field-epoch invalidation, legality audit, OSM turn restrictions (230) + access overrides (3,428), connectivity-screened snap, bike cap 40, and the 40-OD audit (98 anomalies, 0 teleports; the engine-vs-OSRM dose gap is mostly a duration model, engine ~27 km/h vs OSRM freeflow ~55). YOU now own its next leg (route-quality stats, item 4).
Finished / suspended earlier (read their messages via devin_session_interact get_messages if needed):
- 472a750080d34ba8ae50ef8cff88f76a: macOS continuation (early build)
- 5aba7ff24c5b4c2da3df26926b66d03d: app live-data wiring + light theme audit
- cd33585f169d4244a11a51768b53724d: Android E2E user-journey verification
- f3a3b24db92d4613831afbee168cc5c8: backend lane: C++ wiring + AWS + admin
- 73311a0a9d3a4bbf8165faaa3f71ef1e: app-as-user E2E on the Android emulator
- 14a79dc157af4b64af6ee1e51bafac5d: admin-as-operator E2E + API sweep
- c4cd4e86db554b29a095d0af5d6275b1: map/app lane, Google-grade UX depth (62-layer bilingual basemap; children b60bd7e9248a454bafa51fd960ad12ff, 516ac825f30e42939e52ec405c96fc21 = Android forensic drive)
- 78bacf12be3b41e6861662fd3547321b: audit lane, mandate matrix + judge/competitor check (33 mandates, 28 verified)
- d8b82045dedd45aca28c43147b9d73ea: Android lane, TTS/jank + cigarettes-off + PUC
- 84038795d9cd466a9a6ad935b7909dd9: city-landing + admin overhaul, NCR choropleth
- Earlier research/build sessions referenced in docs: 8284a8670ec24473a81ea6e9723958ad (original thesis/research), 279d45cca87d4f039ff49f85deffa57f, 0d2a3f4b5304485ab359a62a75b63048 (marathon deploy + APKs), 506fd9dd5e3349a8b89114515c3193b3 (first Android proof)
- Previous lead session (the one writing this): https://app.devin.ai/sessions/13283940d1854cd4bf2ff691c4bd9bb7

## Environment gotchas
- The macOS box cannot run an Android emulator (no nested virt). Use Linux + KVM. Maven Central returns 429 → add a Google mirror via ~/.gradle/init.gradle (don't commit it). Gradle OOM next to the emulator.
- iOS sim: typing drops characters → use `xcrun simctl pbcopy` + paste. Set the sim location BEFORE launch.
- The server needs Python 3.12 (.venv312) + Eigen for the krige extension; rebuild the C++ ext after core changes.
- The timing middleware strips the /v2 prefix in labels (cosmetic).
- The public OSRM demo is driving-only and slow. Engine rows cover car/bike/auto/cycle/walk without it.

## How to work
Loop: pick the top gap → fix with a test → run the affected tests (full suite before merging to main) → push base/v2 → deploy → verify live with curl (numbers, not vibes) → message the owner briefly → next. Delegate UI-driven Android testing to the Ultra agent. Never claim "done" without saying how it was verified: local, live AWS, Android, or iOS sim.
