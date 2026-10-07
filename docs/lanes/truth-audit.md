# truth-audit — NUMBERS & demo-day integrity audit

Lane: `truth-audit`. Pass window **2026-10-07 00:20–00:40 UTC** (≈05:50–06:10
IST Oct 7). Ground truth: live `GET`s against prod `alive108-…elb.ap-south-1`
build **`ce01ec5c`** (HTTP :80 only — zero POSTs per lane mandate; the one
POST-dependent claims are marked ⟳not-probed), direct fetches of the DPCC
5-min pages (the holdout truth source), and the code at `base/v2` HEAD
`10e3ff9`.

`verify_numbers.sh` was **not** run: it POSTs `/v2/plan` (forbidden here) and
needs python ≥3.12 (this box: 3.9). Every figure below was re-derived with
direct `curl` — same evidence the script prints.

**The demo-morning liar is `scripts/verify_numbers.sh` itself** — its matchers
still pin the 24-WAQI world (`r"24 (live )?(WAQI|instruments|stations)"` L162,
`"{count} WAQI stations live"` L318, fires `~?7[0-9]` L165), so the T-45
integrity pass will **false-flag correct docs** and burn the checklist window.
Already flagged by docs-truth §4.2; still unfixed at HEAD. Second liar:
**deploy lag** — prod runs `ce01ec5c`, 26 commits behind HEAD, and the delta
includes the admin/city/community/landing HTML overhauls + `server-harden`
retry gates. The surfaces a judge will compare against the repo are not the
surfaces prod serves.

## The claims ledger

Legend: MATCH = live/file agrees at probe time · DRIFT = moved with the field
(class preserved — quote ranges, not points) · ARTIFACT = true of the cited
file/commit · STALE = stated value no longer true · BROKEN = wire contradicts
claim · UNVERIFIABLE = can't check under GET-only/no-token rules.

| # | claim | where stated | live value NOW (probe) | verdict |
|---|---|---|---|---|
| 1 | 54 instruments = 24 WAQI + 30 DPCC | NUMBERS §2; README; demo-day; writeup | `/health.sources.stations` 00:20Z: `count:54`, `source:null`, **`feeds:{waqi:"ok"}` only** — dpcc key absent mid-failed-refresh; healed by 00:39Z to `feeds:{waqi:"ok",dpcc:"ok"}`; `/aqi.field` `station_readings:54`, `stations_src:"waqi+dpcc"`, `stations_status:{waqi:ok,dpcc:ok}` | **MATCH + wart** — count/source honest; `feeds` map went transiently inconsistent with count (54 can't come from WAQI alone) while a refresh was overdue (age 946 s > 900 s TTL). Code path: `_stations_status` is written per-feed during `_grab_stations` (`airfield.py:436-489`); a mid-grab abort between the WAQI status write (L440) and the DPCC status write (L474) leaves exactly this partial dict — while `_station_count` stays sticky from the last good grab. Self-heals on the next successful build (~4 s later here). |
| 2 | ~903,058 of 1,070,459 edges priced | NUMBERS §1; README live-rendered; demo-day | `/health.routing` 00:20Z: `edges:1,070,459`, `edges_priced:903,058`, `engine:"alive_core"` | **MATCH** |
| 3 | field rebuild ~15 min | demo-day, writeup | `/aqi.field` `refresh_ttl_s:900`; observed ages 946→23 (forced rebuild 00:20:53) →429 s (next build ~00:32) — cadence real | **MATCH** |
| 4 | holdout MAE: former-GAP 22.8→10.5, all-30 27.1→6.2 | `docs/lanes/holdout-reverify-report.md` (probed 02:05–02:29 IST on same build); writeup/README | this pass, 6 sites: truth from DPCC pages 05:45–05:55 IST vs `/aqi.pm25_ambient` ~06:00 IST → JNU 63.1→49.4 (13.7), DelhiCantt 12.45→29.0 (16.6), Talkatora 45.8→57.6 (11.8), IGNOU 11.28→23.0 (11.7), AnandVihar 41.0→45.8 (4.8), Mundka 55.0→57.1 (2.1); **mean \|err\| ≈ 10.1**; `nearest_sample_km:0.0` at all 6 | **ARTIFACT + DRIFT caveat** — the pinned numbers were true at their probe; tonight's sample reads the same class but up to ~17 µg single-site on a moving morning field (Kalman smooth lags a falling edge; the artifact's own rule compares same-minute reads). Quote "single-digit to low-teens µg at instrumented sites", not a bare 6.2. |
| 5 | LOO calibration MAE ~46.1, n=94 | `/aqi.calibration`; writeup | serves `server/data/field_calibration.json` verbatim: `mae_ug:46.1`, `n_stations:94`, `method:"leave-one-out over live OpenAQ instrument readings"` | **MATCH-artifact** — label still says "OpenAQ" (predates the waqi+dpcc feed): stale-label wart already flagged docs-truth §4.1, still unfixed. Not contradictory with #4 — LOO measures spatial generalization to *unseen* stations; holdout measures fidelity *at* instruments. A judge conflating them is the risk, not the numbers. |
| 6 | fires claim gated by wind | `server/fires.py`; demo-day; judge-proof | code: NW quad `270≤deg≤360` full modifier `1+min(idx,1)*2.75`, outside → ×0.3 (`fires.py:212-217`). Live 00:39Z: 80 fires/20 belt/42.1 MW, wind 108° (SE) → `modifier:1.10` = (1+20/160·2.75)×0.3 = 1.10 ✓ arithmetic checks; `/v2/why` `carrying:false`, drivers[0]=stagnation (BLH 231.6 m × wind 1.74 m/s → VC 403 vs ~3,000 ref) | **MATCH** — gate logic and live arithmetic consistent |
| 7 | fires count/belt | NUMBERS §2 (67/15, ×1.08, "tonight") | moved **mid-audit**: 67/15/35.8 MW (00:21Z, age_s 14,576 on the 6-h cache) → 80/20/42.1 MW (00:39Z, fresh fetch at ~00:32) | **DRIFT** — the feed re-fetched inside the probe window; any doc quoting 67/15 is already stale by hours. `age_s` honest on wire. |
| 8 | k≥3 corridors, 72 h window | writeup, demo-day, PRIVACY | `/v2/city/moves` 00:21Z: `min_k:3`, `window_h:72`, corridors `active:12/tracked:54`, 39 trips/7d, suppressed_trips 0; `/v2/city` corridor rows all `devices ≥3` (observed 3–10); code `K_MIN=3`, `CORRIDOR_WINDOW_S=72*3600` (`admin_agg.py:64-65`), `_K_MIN_DEVICES=3`, `_CELL_WINDOW_S` (`community.py:89-90`), serve-time `assert devices≥K_MIN` | **MATCH** |
| 9 | budgets: PLAN 20 s, ENGINE 9 s, TRANSIT 12 s | docs, handoff `ddf3c19` | `plan.py:1147` `PLAN_BUDGET_S=20.0`; `:1324` `ENGINE_BUDGET_S=9.0`; `:1152` `TRANSIT_BUDGET_S=12.0`; plus `FIELD_REFRESH_BUDGET_S=10`, `REACH_BUDGET_S=9` (`reach.py:40`), `why _REFRESH_BUDGET_S=6` | **MATCH** |
| 10 | "no uploads" — `/observe` 410, donation-only | SECURITY, writeup, judge-qa | `GET /observe` → **405** (route is POST-only); `POST /observe` → **410 Gone** per `main.py:1272-1284` (raises 410 unconditionally — code-verified, not probed per mandate). Donations only via `POST /v2/trip`; `POST /report` = hazard flags (separate, non-tracking write). `GET /v2/ledger` → 422 `device token required` (token-gated). `/community` = aggregates only (22 obs/14 contributors — small consistent with a private beta) | **MATCH** — the GET→405 is expected (POST-only route); nothing fabricated. |
| 11 | build_sha = deployed image | go-nogo, demo-day, NUMBERS wart | `/health.build_sha` = `ce01ec5c`; base/v2 HEAD = `10e3ff9` → **prod is 26 commits behind**, including `77941dc server-harden` (retry gates in airfield/fires/forecast + city.py) and the admin/city/community/landing HTML overhauls (066c129, dc889cd, 6c36219, 10e3ff9) | **STALE-by-design (deploy lag)** — the sha-image wart is resolved this revision, but repo ≠ prod. Every surface listed above serves the *pre-overhaul* version. |
| 12 | `/grid` lattice 484 cells | demo-day, writeup | `/grid` → 484 features | **MATCH** |
| 13 | districts 29 rows | demo-day | `/v2/districts` → 29 | **MATCH** |
| 14 | breath ~576 µg ≈ 1.8 cig (afternoon) | NUMBERS, shotlist | `/v2/city.breath` 00:23Z: mid **820 µg ≈ 2.6 cig** | **DRIFT** — inside the documented 550–1,099 evening range; the afternoon pin is stale as usual. |
| 15 | `/v2/skill` 210 pairs all `ok` | NUMBERS | 00:39Z: **227 pairs**, h+0 3.9 … h+11 49.2, all `ok` | **DRIFT** — grows with the archive; quote "n, all graded" not the pin. |
| 16 | community 22 obs/14 contributors/725.9 µg | NUMBERS, demo-script | exact: `obs_total:22`, `contributors:14`, `avoided_ug_all:725.9`, 0 obs/24 h, `latest_obs_age_min:1626` | **MATCH** |
| 17 | corridors 12/54 publishable/tracked, 39 trips | NUMBERS | exact on `/v2/city/moves` | **MATCH** |
| 18 | reach: walk@25 ~4,103/182.5, walk@50 ~12,353/676, car@25 partial ~85,612 km | NUMBERS | 00:22Z: walk@25 **4,094/182.1 km**, walk@50 **12,318/676.1 km**, car@25 **935,698 / 83,036.6 km** `edge_partial:true` (2M-state cap binds; `took_ms:1247` inside the 9 s budget) | **DRIFT** — same class; car figure is cap-pinned so quote "the whole priced graph", not a number. |
| 19 | field_validation 3,550/85, MAE 22.0, RMSE 29.3, +15.5 (+51.6%), σ 95.2/95.4 | README, writeup | `server/data/field_validation.md` headline row identical | **ARTIFACT-MATCH** |
| 20 | gazetteer 124,311 mobile / 123,934 server | NUMBERS, demo-day | file lengths: mobile `124,311`, server `123,934` | **MATCH** |
| 21 | corpus 97,447 / 16,949 addr | STATS.md, README | `STATS.md`: 97,447 entries, 16,949 addr rows | **MATCH** |
| 22 | bans 230, graph_sha 83ef9b91051bbd29 | NUMBERS, HANDOFF | `route_graph.meta.json`: `bans:230`, `pbf_sha256:83ef9b91051bbd29`, nodes 819,846, points 2,324,796 | **MATCH** |
| 23 | reach caps: 90,000 serve / 2M states | shotlist, code | `reach.py:37-38` `EDGE_SERVE_MAX=90_000`, `REACH_MAX_STATES=2_000_000` | **MATCH** |
| 24 | 316 µg = 1 cigarette | README, copy, code | `city.py:49` `CIG_UG=316.0`, `DAY_M3=316/22` | **MATCH** |
| 25 | history 125 stations, openaq-data-archive | writeup, repo-readme | `/health.history.stations:125`, `source:"openaq-data-archive…"`; gz `stations:125` | **MATCH** — "9M station-hours" stays honest phrasing (raw-row count, not on wire). |
| 26 | transit real feeds | NUMBERS, docs-truth | `/health.transit.real_feeds:{metro:true,bus:true}`, on_disk true | **MATCH** |
| 27 | Amazon Location | `/health.sources.location` | `up:false`, `key:"unset"` — **but search does not break**: `/search?q=connaught place` → 8 results in **1.9 s** (Photon fallback — code `main.py:533-567` races AWS+Photon, 8 s grace when AWS is thin); `/reverse` → "Indira Chowk, Connaught Place" 0.57 s | **MATCH-degrades** — only coverage/latency degrade; up to ~8 s worst-case search latency vs LAN-fast AWS. |
| 28 | `/tiles/health` (warm_task last line) | demo-day T-40 | `ok:true`, 22.7 MB pmtiles | **MATCH** |
| 29 | `/reports` | demo flow | 200, empty FeatureCollection — `active_reports:0` on `/community` — honest empty | **MATCH** |
| 30 | plan options 16–24 / dose ladder ~33–45× spread / took_ms | NUMBERS, demo-day, pitch | **⟳not-probed** — POST `/v2/plan` forbidden by lane mandate. Code-verified instead: arms race at `PLAN_BUDGET_S−2.0`, missing arms → `degraded:[names]` on the wire, total timeout → `{options:[], error:"planner timed out", degraded:["planner"]}` (`plan.py:1215,1275-1314,2024`); `smoke_modifier` echoed on the response | **UNVERIFIABLE (by rule)** — the honest-degrade mechanics are real in code; the demo-OD numbers carry the ⟳prev stamps in NUMBERS §2/§3 and must be re-derived at T-45 by a lane allowed to POST. |
| 31 | cold task ~60–100 s to priced engine; first plan ~9 s | demo-day, NUMBERS | warm task now — `field_age_s` cycling normally; nothing measurable without a task swap | **UNVERIFIABLE tonight** — rests on `docs/plan/cold-path.md` + measured runs in demo-day; the warm path (`_warm_field`/`_warm_fires`/`_warm_forecast` at boot, `main.py:55-90`) and `tools/warm_task.py` exist and are current. |
| 32 | Spot capacity | demo-day T-60 | no AWS creds on this box; last verified `FARGATE_SPOT` running 1/1 on 2026-10-06 ~05:10 UTC via boto3 (demo-day §FARGATE) | **UNVERIFIABLE tonight** — must be re-run at T-60 by whoever holds creds. |
| 33 | iOS-sim SIGSEGV ~12.5%/sheet-open residual | `search-fix-verify-report.md`, NUMBERS | artifact: 1/8 on "Where to?" sheet + a 2nd crash on compare-sheet mount, post-`b869bd0`; ~40%→~12.5% | **ARTIFACT** — and demo-day.md already carries the honest stage plan (prefer Android/recorded take/bare-metal Mac). |
| 34 | outlook horizon 5 days / ~101–120 h | NUMBERS | `/v2/outlook`: `horizon_days:5`, `horizon_hours:109`; days 2026-10-07→11 read **73.7 Moderate → 127.9 Poor → 165.2 VP → 132.8 VP → 136.5 VP** | **MATCH + demo-window note** — Oct-8..11 (demo days) all Poor/Very Poor on tonight's read; the "dirty air" pitch will be easy to show, the "cleanest window" beat may be thin. |
| 35 | `/v2/day` windows + decisions | NUMBERS | 00:22Z: heavy **19:30→day end ~100.4**, cleanest **14:30–17:30 ~59.0**, day_mean **74.6**, `decisions` **3 rows** (plain-words extrema present — the `decisions:[]` wart stays fixed) | **MATCH** (drifted from last night's 104.4/58.1 stamps — normal) |
| 36 | `/depart` 23.6→45.5 worst/21.3 best | NUMBERS | 00:22Z: now **22.8** → best **21.1 @+11 h (−7%)**, worst **42.8 @+16 h** | **DRIFT** |
| 37 | `/v2/city` next_hours | NUMBERS | 12 h served, ~63.9 at anchor → ~59.5–60.1 tail (evening dip, monotone) | **DRIFT** |
| 38 | `/v2/archive` recorded[1,3,4] gaps[0,2] | NUMBERS | 00:36Z: today recorded **[1,3,4,5,6]**, gaps **[0,2]**, pending [7…] — honest-gap convention holding (hour-5/6 landed during the audit) | **MATCH+DRIFT** |
| 39 | `/v2/why` drivers[0]=stagnation | NUMBERS | stagnation primary, `carrying:false`, trend +2.4 µg over 6 h/25 snapshots, `cannot_tell` carries trend | **MATCH** |
| 40 | `/observe`→410 & `/v2/trip` mode sanitizer/switched | NUMBERS §4 | `/observe` row above; `metro+walk` token fix `test_trip_mode_metro_plus_walk_survives` + `switched` wire fix are in the deployed build's history (pre-ce01ec5c) | **MATCH** |
| 41 | "1 vCPU/3 GB + osrm-routed sidecar" | docs-truth, deploy.sh | `scripts/deploy.sh` L164-197: sidecar `osrm-routed` in same task (mem 1024/res 512), task `--cpu 1024 --memory ${TASK_MEMORY:-2048}` — repo default 1 vCPU/2 GB; live sizing env-overridable (demo-day notes a 2 vCPU/4 GB bump pending) — "3 GB" is plausible-but-unverified. Self-hosted daemon first, public OSRM fallback (`admin_agg.py:162-173`) | **MATCH-code / UNVERIFIABLE-infra** |
| 42 | EventBridge rollup+validate enabled, ingest-15min disabled | docs-truth §1.40 | repo↔AWS drift stands: `infra/schedules/*.json` all `"State":"DISABLED"` scaffolds vs handoff saying two are enabled live | **UNVERIFIABLE tonight** (no AWS access); the *discrepancy itself* is confirmed and still unfixed — flag stays open from docs-truth §4.3. |
| 43 | 981 `def test_` / 53 `check(` | docs-truth | grep-verified convention stands (not re-run — suite env varies) | **MATCH-file** |

## Demo-day failure modes

Ordered by how badly each can embarrass live on stage. "What the surface
shows" = verified tonight against the live wire or the serving code.

1. **Deploy lag (repo ≠ prod)** — prod `ce01ec5c` vs HEAD `10e3ff9`: **the
   admin, city, community, and landing pages a judge sees on the wire are the
   pre-overhaul versions**, plus `server-harden` retry gates absent. If the
   demo script or the judge's repo read was written against HEAD, the browser
   will contradict it. *Mitigation already in runbook:* redeploy or narrate
   "the deployed build from <date>"; decide at T-45 whether web surfaces get
   a fresh image. This is the #1 "says one thing, shows another" risk.
2. **`verify_numbers.sh` false-flags at T-45** — matchers pin "24 (live)
   WAQI/stations" and "~7x fires"; live is 54/waqi+dpcc and fires are
   volatile (67→80 inside this audit). The FLAGS block will light up on
   *correct* docs, inviting 2 AM doc-thrashing or, worse, someone "fixing"
   true lines. Also needs py ≥3.12 (stock macOS 3.9 dies) and crashes
   `mid(None)` when a transit mode is absent. *Fix exists:* docs-truth §4.2
   — update patterns to `54|waqi+dpcc`-era or run this audit's table instead.
3. **iOS-sim SIGSEGV on the demo spine** — residual ~1-in-8 per sheet-open on
   this box's simulator. The beats that touch sheets are exactly the spine:
   "Where to?" search sheet (destination pick), CompareSheet (the dose
   ladder), ReceiptSheet (the donation close). Cold launches are clean —
   risk is mid-demo sheet churn. *Stage plan already in demo-day.md:* prefer
   the recorded iOS take or bare-metal Mac; Android release target has never
   crashed in E2E; relaunch recovers in ~9 s with all state persisted.
4. **DPCC stall ~02:00 IST → count 54→24** — observed pattern (29/30 pages
   pinned, Alipur advancing). Tonight the site is **live** (fetched pages
   stamped 05:45–05:55 IST, fresh). If it stalls overnight: ~90 min after the
   pin, `ingest_dpcc`'s `MAX_AGE_S=5400` guard drops every stale row →
   `/health.feeds.dpcc:"unavailable"`, `stations.source` loses `+dpcc`,
   `count:24`; `/aqi.station_readings:24`; `nearest_sample_km` climbs off
   0.0 at the 30 cells; the field keeps blending on the 24-instrument WAQI
   backbone + model — every surface degrades *honestly*, nothing hangs, and
   `status()` says exactly what happened. The wart to watch: during a failed
   refresh the `feeds` map can transiently lose the `dpcc` key entirely
   while `count` stays sticky at 54 (observed 00:20:49Z, healed on next
   build) — a judge reading `/health` in that window sees an internally
   inconsistent line, not a lie but an ugly one.
5. **Spot reclaim mid-demo** — service verified `FARGATE_SPOT` 1/1 as of
   Oct-6 ~05:10 UTC. A reclaim kills the task with ~2 min warning; the
   replacement boots cold — ~2 min to priced engine even with warm-up
   (graph ~36 s + first field fetch). Any `/v2/plan→/v2/strip` pair minted
   on the dead task 404s on the new one (route_ids are in-memory). The
   T-60 FARGATE flip + `warm_task.py` runbook is the answer — but it *is* a
   manual step owned by whoever holds AWS creds; if it isn't run, demo is
   exposed.
6. **Cold-task first-hit latency** — a fresh task needs ~60–100 s to a priced
   engine (lane-measured); first plan while the engine reprices ~9 s and can
   hit the 20 s budget on long ODs. `/aqi`-class surfaces are behind the
   same cold path until the boot warm fleet lands. *Mitigation exists:*
   `_warm_field/_warm_fires/_warm_forecast` at boot + `tools/warm_task.py`
   (exit 0 = warm) — the failure mode is *skipping* it after any task
   replacement inside the T-60 window.
7. **Plan >20 s budget → honest degrade** — verified in code: arms wait
   `PLAN_BUDGET_S−2`, missing arms surface as `degraded:["engine"/"transit"/
   "motor"/"slow"]` on the wire, total timeout returns `error:"planner timed
   out"` + `options:[]` — CompareSheet renders the named-arm banner, no
   hang, no fabricated rows. One 60 km call hit the budget this week. On
   stage: the road-mode rows still carry the spread line; narrate the
   `degraded` key if it appears — it IS the honesty story.
8. **Transit service-hours absence** — `metro+walk`/`bus` rows are honestly
   absent outside GTFS service hours (observed all week). Probing at ~06:00
   IST now sits right at the metro start boundary; a pre-service-hours
   probe shows road modes only. Not flagged `degraded` — legitimate absence.
   If a judge runs `/v2/plan` late-night, the transit story is thin — say
   "outside service hours" with the `/health.transit.real_feeds` row.
9. **Amazon Location key unset** — `/health.sources.location.up:false`. What
   breaks: the AWS arm of `/search` silently returns [] (boto call throws,
   caught); Photon (Europe) carries it alone — still real answers (~1.9 s
   tonight) but with the 8 s grace window when AWS is thin, worst-case a
   search takes ~8 s. `/reverse` works. No surface fakes coverage.
10. **`field_stale:true` window** — stale after `STALE_AFTER_S=2,700 s`. On
    the wire: `/health.field_stale:true` + real `field_age_s`; app
    FreshnessChip goes muted/stale ≥30 min ("no live reading" when no age);
    plan responses keep serving the last field *with* `field.age_s` telling
    the truth. Nothing freezes — every surface keeps answering while
    honestly reporting age. The failure is only optical: a stale flag during
    the demo needs the line "the field is N minutes old, still serving".
11. **Fires feed staleness** — `CACHE_S=6 h`, `stale_after_s=22,500`: the
    feed can legitimately serve ~6-h-old fire data (observed age 4 h+
    tonight before the ~00:32 refresh). `age_s` is on the wire — honest —
    but a fires beat should check `fire.age_s` before quoting counts, since
    the count moved 67→80 on one fetch tonight.
12. **`decisions`/windows null on a flat day** — the `decisions:[]` wart is
    fixed (3 rows tonight), but `heavy_window`/`cleanest_window` can still
    be `null` on flat air — the honest fallback is `hours[]` + `day_mean`
    read out loud ("moderate all day, ~74 rising to ~100 after 19:30").
    Rehearse that line — nulls look like breakage if un-narrated.
13. **HTTP :80 + captive portal** — NLB speaks HTTP only; venue Wi-Fi
    captive-portal pages break it. Phone hotspot is the verified-safe path
    (already in checklist; worth a T-30 dry run).
14. **`/admin/api/status` vs `/health` two-sha risk** — the sha wart is
    resolved on this revision, but `/admin/api/status` needs the admin
    token (401 tonight without it — correct). If both screens are ever
    shown, say the ECR image tag, never the stamp.
15. **Public-repo history disqualifier** — unchanged and disqualifying if
    missed: private history predates Oct 8; `scripts/public-repo.sh` squash
    must be the FIRST step on Oct 8.

## Clean bill

Everything the product claims that *can* lie was probed and is telling the
truth tonight: 54 instruments / 903,058 priced edges / 900 s field cadence /
k≥3+72 h corridor gate enforced at serve-time asserts / PLAN-20 ENGINE-9
TRANSIT-12 budgets in code / `POST /observe` = 410 with donations folded
server-side only / Photon covers the unset Location key / `degraded[]` arms
are honest on the wire and in the app / every static artifact (graph meta,
gazetteer, corpus, climatology, field_validation, calibration JSON,
reach/cigarette constants) matches its docs. The drift numbers (fires,
skill pairs, breath, reach km, day windows) moved in real-time during this
audit — within their documented ranges.

**What is NOT verified (by mandate or by missing credentials):** the POST
dose ladder/spread/options/took_ms (⟳carry the stamped NUMBERS values;
re-derive at T-45), Spot/task-def/aws-schedule state (needs creds),
`admin/api` token paths (401 by design), and the iOS crash rate (artifact
evidence only — no sim run tonight).
