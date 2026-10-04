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
Shipped and live this session (verified by curl + ECS logs, not vibes):
- engine-arm shared solves (5805620): `_solve_join` memoizes/dedupes engine primaries + corridor alts per (rounded OD, _ENG_T pricing epoch). Live under 6 concurrent fast+full calls: fast paint took_ms ~77–100 (was 1.6–3 s), full plans 0.8–4.5 s with all 15 engine rows, zero "engine timed out". Logs show owner solves 1.6–6.6 s then repeat calls 2–10 ms. ECS pool now 3 workers (joined callers park on an Event, no CPU).
- deploy verified: build_sha 58056209 on the NLB.
- cold-task first plan: 15 options in 19.3 s (inside the 20 s budget — the 34 s bug stays fixed).
- 40-OD engine audit live on 7e92660 (tools/audit_engine_quality.py): 11/40 ODs have a least-smoke row saving ≥10% dose for ≤15% extra time vs the fast row (was 10), 17/40 vs same-mode (was 16), 0 absurd detours. 108 "worse-dose" rows are mostly the known duration-model gap (engine ~27 km/h vs OSRM freeflow ~55 — dose integrates field×ventilation×time). The depth lane (new SWE-2 Max child) owns splitting that number honestly.
- main merged at 54e2ed2 (no-ff) — includes engine dedupe, search fixes, probe+audit tools, location lane query-tolerance leg. Full suite 809 passed.
- deploy verified: build_sha 0a3c3140 on the NLB.
- live 174-query battery on 0a3c3140 (lead re-run): 172/174 top-1 (98.9%), p50 473ms; only misses are the two documented honest ones (panipat ceiling, 25 rajinder nagar substring artefact).
- deploy verified: build_sha 89e34132 on the NLB — contains the WAQI-first stations chain, `_warm_static` (gazetteer+climatology parsed off-loop at boot), and Android lane's hindi turn-by-turn + polish commits.
- Android UI/UX lane COMPLETE (efb8721d, verified numbers): gfxinfo janky 42.27% → 29.07% (−31%), p99 150→93ms; TTS verified with 6 real utterances on a teleported 3.8km drive; 9 polish commits; release APK on 65a8619 (135.8MB, debug-signed, NLB verified in bundle). Gaps it flagged honestly: dose "0 µg" on teleport (real — ~zero dwell; untested at driving speed), occasional eaten adb taps in search ScrollView, metro legs untested, PUC verified on earlier build.
- Route-quality truth DONE (depth lane, 1588dc3): dose-ratio decomposition over the 108 worse-dose rows — 0 rows genuinely smokier per metre; the count is the router's freeflow-duration overstatement (bike implied 56–75 km/h). docs/plan/engine-quality-decomp.md.
- STATIONS = 0 live — root-caused + verdict (2026-10-04): OpenAQ key dead (401, owner banned). Probed every alternative from a one-off Fargate task in the prod VPC: api.data.gov.in CONNECTION REFUSED even from ap-south-1 India egress (the India-egress assumption was wrong — dead with or without a key); CPCB dashboard timeout; SAFAR TLS-connects-then-hangs (broken host); WAQI `demo` token silently serves SHANGHAI (fake — rejected); aqicn pages proxy keyed api.waqi.info only. ONLY real path = a WAQI token (owner, 30s signup at aqicn.org/data-platform/token/ with his email — temp-inbox signups got no activation mail; form is captcha-gated).
- Stations chain rewired WAQI→CPCB-keyed→OpenAQ live (43f0099 in 89e34132): `WAQI_API_KEY` injected from Secrets Manager `alive108/waqi` (placeholder `REPLACE_ME` — adapter skips honestly; /health `sources.stations.feeds` reports per-feed verdicts). Flip when the token lands = `put-secret-value` + `force-new-deployment`, zero code.
- STATIONS LIVE (owner's WAQI token, tools/flip_waqi_token.sh, 2026-10-04): `/health` `stations.count=24, source=waqi`; /admin/api/status field=`waqi-stations+open-meteo/cams`, 68-71 samples, station_readings=24 inside the krige; /city 13 districts live CPCB colours. Adapter keeps only fresh CPCB readings — count varies honestly (24 → 5 seen overnight, CPCB stations go stale for hours).
- Debias fix live (depth lane ce101e5): `_debias` scales ONLY pm2_5 by ratio b; pm10 += pm2_5*(b-1) additively; gases/AQI/dust/aod raw CAMS. Verified live: o3 ~166-176 (was 575 absurd), aqi 173-192 sane.
- ADMIN BOARD FIX (1436c2d, live + browser-verified): my one-prompt commit 868789c introduced a syntax bug (`{headers:'Bearer '+tok}}` — missing `authorization:` + stray `}`) that killed the whole script — page dead "connecting", no prompts at all. Fixed to `{headers:{authorization:'Bearer '+tok}}` + wrapped `.map(u=>getJSON(u))` (`.map(getJSON)` passed array index as `retried`). Verified in a fresh Chrome: exactly ONE prompt → full board (1436C2D4, 24 stations, 13 districts, 26 trips, 6 corridors).
- main merged at 06b6c3f (no-ff) — admin fix + lanes' lands (Mobile polish, airfield debias + tests). Suite 833 passed.
- Depth lane legs all in base/v2: 1588dc3 (dose decomp harness), 0a90a0a (_warm_field at boot — field serving no longer request-driven, saves ~60s cold), cc3bdef (tools/warm_task.py + FARGATE_SPOT→on-demand runbook in docs/demo-day.md), d03f051 (claims-audit §4/§7 privacy+honesty).
- Depth lane then landed 3ef3677: admin feed + recent_journeys k≥3-device hour buckets (per-trip rows dropped — privacy).
- DEPLOY VERIFIED 2026-10-04: build_sha 3ef36777 live; stations 24/waqi; fresh-task plan 5 engine rows 1.5s.
- EXPOSURE TRUTH verified on live 3ef36777 (lead recompute): dose = c_eff × VE × minutes reproduces every row's dose.mid within rounding; microenv×VE ordering metro 3.4 < car 4.1 < bus 5.6 < walk 14 < 2W 9.9 < cycle 24.2; engine_dose_ug ≈ dose.mid ±2% on all 5 rows (priced objective = displayed integrand holds post-dedupe); bands lo<mid<hi ≈ ±13% (krige σ linear sum).
- iOS DEMO TAKE edited+verified: /Users/devin/ios-take/ios_e2e_clean.mp4, 241s/12.4MB — launch→permission→onboarding→consent→map→search→results→vehicle wizard→PUC→compare (leave-later histogram)→turn-by-turn nav→receipt→drawer→settings (cigarettes OFF)→Delhi today. Take-2 crashed 3× (sim-only MapLibre vGPU kill — ZERO .ips reports = GPU kill not app bug); take-1 edited with 3 cuts (LogBox era 3.5–43s, tips-overlay ~71–72s, dead-dwell+Safari ~95–186s on CFR-normalized timeline). VFR→CFR normalization required before cuts (-ss domain drifts ~4% vs wall).
- ENGINE MANDATE assigned to depth lane (139507b4, in-session continuation): priced=displayed under dedupe (3 cases: owner solve/memo-hit/fast-vs-full), legality on live routes (230 turn restrictions + 3,428 access overrides + 1.6× detour bound + bbox), engine timeout under concurrent load post-dedupe, duration-model decision (calibrate vs label).
- BACKEND LANE spawned (29adb480, SWE-2 Max): field/species units audit, dose math e2e, admin "insufficient data" tiles verdict, /v2/plan robustness under load, error/edge paths, forecast anchor truth.
- UI/UX LANE (Android exhaustive + admin border-level + recorded E2E) brief written at /Users/devin/uiux-lane-prompt.txt — spawn BLOCKED by 5-SWE-2 org cap; retry when any running session settles.
- Elevation-tile storm noted: app fetches terrarium PNG hillshade tiles every pan/zoom — bandwidth/battery flag for UI/UX lane.
- ROLLUP/VALIDATE JOBS WIRED END-TO-END (daa0571 + live-verified): three stacked causes fixed — Dockerfile CMD honors ALIVE_JOB (`rollup_lambda.py <job>`; the scheduled RunTask previously booted a duplicate API), ingest_worker.sync_rollup_outputs() mirrors `s3://alive108-air/{daily,validation}/*` → `server/data/field/*` (admin_agg only reads local mirror), main._start_rollup_mirror daemon (boot pull + every 30min). rollup.py ships validation/field_validation.md to S3. Schedules ENABLED on task-def FAMILY: rollup-daily 00:30 IST, validate-weekly Sun 20:00 IST (ingest-15min stays DISABLED — in-app loop owns it). Schedule network config corrected to real subnet/SG (stale provision values would never have launched).
- One-off jobs ran exit-0 live: rollup → daily/2026-10-03.json (2.8MB, 83 snapshots); validate → weekly-2026-W40.{json,md} + 2026-W40.json + field_validation.md (9.6KB).
- ADMIN/CITY BORDER-LEVEL SWEEP BY LEAD (browser-verified): every tile renders real or honest-empty. Two real bugs fixed: (a) headline "model error" card rendered "insufficient data" while archive_replay mae 52.5 sat in the week block — now falls back labelled "model error · archive replay (mae)" (b47d5c9); (b) /city ticker rendered raw floats "317.1261538242962 µg/m³" — rounds to 1dp/int (3c7f86d).
- DEPLOY VERIFIED 2026-10-04: build_sha 3c7f86d8 live; /admin/api/validation {status:ok, daily 2026-10-03 median 101.16µg 14155 cells, weekly archive_replay mae 52.5 rmse 56.34 bias +50.7 (7240 pairs), report_md true}; browser shows the card + rounded ticker.
- Suite 843 passed; main merged at 7568376 (no-ff).
- SWE-2 slot truth: org cap 5 running — mine 2 (depth 139507b4 engine mandate, backend 29adb480) + Pocket Rig 3 (main + 2 subs) = full. efb8721d exited (its Android overhaul complete). UI/UX combined lane spawn retries on settle; location 1cb3ac27 suspended.
- Next: UI/UX lane spawn when a slot frees; LOSO needs held-out-station snapshots to populate (validation infrastructure gap — backend lane owns).

Open gaps, ranked (from master-plan.md):
1. Owner's testing overhaul mandate: exhaustive per-feature Android + admin sweep (every screen/button/border) + recorded E2E vs live API — UI/UX lane briefed (/Users/devin/uiux-lane-prompt.txt), spawn blocked at 5-SWE-2 cap; backend lane covers admin API; lead verified admin+city+exposure on live 3ef36777.
2. Cold-start residual — _warm_field + _warm_static shipped and live; depth lane verifying the fresh-task numbers.
3. Android: physical-finger pass on search taps; dose-at-driving-speed untested (teleport only); PUC re-verify on final APK — all in UI/UX lane brief.
4. Demo morning: switch Spot → on-demand, warm the task 10 min early (tools/warm_task.py ships, verified live), run the demo on a physical Android phone. iOS = recorded take (ios_e2e_clean.mp4 done).
5. Keep main merged at checkpoints (last: 7568376).
6. Rollup jobs wired + schedules enabled (daa0571) — daily 00:30 IST, weekly Sun 20:00 IST; one-off runs verified exit-0; admin tiles show real rollup data; LOSO held-out tile honest-empty until station-held-out snapshots exist.

## Every session ever run for this project
Active right now:
- 139507b46df84f939b68d447735ea203: engineering-depth lane on SWE-2 Max, Linux — legs done (route-quality truth, cold-start warmers, demo-day ops, privacy) + 3ef3677 k≥3 admin feed. NOW ON the engine mandate: priced=displayed under dedupe, live-route legality, load timeouts, duration-model decision. https://app.devin.ai/sessions/139507b46df84f939b68d447735ea203
- 29adb48022764f489dc2eb86e15fe8b0: BACKEND lane on SWE-2 Max — field/species units audit, dose e2e, admin tiles verdict, /v2/plan robustness, edge-path tests, forecast anchor truth. https://app.devin.ai/sessions/29adb48022764f489dc2eb86e15fe8b0
- 1cb3ac27d94642f29952845945934fc3: Location-depth lane — SUSPENDED (inactivity + SWE-2 5-session cap; resume message queued, 429 until a slot frees). Its lands through 0a3c3140 are live (172/174). Remaining: Hinglish, compound queries. https://app.devin.ai/sessions/1cb3ac27d94642f29952845945934fc3
- UI/UX lane: brief written, spawn pending on SWE-2 slot.
- efb8721d915f40d0807595b4bec3fa6d: Android UI/UX overhaul on SWE-2 Max — COMPLETE + TERMINATED (jank −31%, TTS verified, 9 polish commits, APK on 65a8619; follow-ups carried into the UI/UX lane brief: APK upload + PUC re-verify + tap-cadence pass). https://app.devin.ai/sessions/efb8721d915f40d0807595b4bec3fa6d
Terminated (out of Ultra quota; work either pushed or handed off):
- 13283940d1854cd4bf2ff691c4bd9bb7: the previous lead session — this session (93b8804d) is its successor as lead. https://app.devin.ai/sessions/13283940d1854cd4bf2ff691c4bd9bb7
- 30c986e2137942488c8060da708ef40b: Android UI/UX on ULTRA — died at setup, superseded by efb8721d. https://app.devin.ai/sessions/30c986e2137942488c8060da708ef40b
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
