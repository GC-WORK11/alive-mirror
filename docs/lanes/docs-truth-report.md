# docs-truth-report — docs-vs-reality sweep

Lane: `docs-truth`. Pass date **2026-10-06 ~23:30 UTC** (≈05:00 IST Oct 7).
Ground truth: live `GET`s against prod build **`ce01ec5c`** (HTTP :80 only —
no POSTs per lane rules), `docs/lanes/*.md` evidence, and the code itself.
236 markdown files exist under `docs/`; ~150 content docs + ~85 lane logs.

Scope rule applied: canonical/current docs were **fixed in place with an
evidence pointer**; dated lane reports, handoff entries, stamped "tonight"
reads and design-phase research docs were **left as snapshots** and flagged
below instead of rewritten. Nothing was deleted; no number was invented —
every corrected figure traces to the live wire, a lane report, or code.

## 1. Numbers verified against live (2026-10-06 ~23:30 UTC, `ce01ec5c`)

| claim | live truth | source |
|---|---|---|
| stations | **54 = 24 WAQI + 30 DPCC**, `source:"waqi+dpcc"`, feeds `ok` | `GET /health` |
| model samples | **100**, `waqi+dpcc-stations+open-meteo/cams` | `GET /health` |
| routing edges | **1,070,459 total / 903,058 priced**, engine `alive_core` | `GET /health` |
| field | age ~10 min (`field_age_s` 625), `stale:false` | `GET /health` |
| fires | **67 total / 15 belt / 35.8 MW FRP**, wind 6.7 km/h @134° (SE) | `GET /aqi` |
| smoke modifier @CP | **×1.08** (SE wind marginal; NW ×1.24 at earlier reads) | `GET /aqi` |
| PM2.5 @CP | breathing 68.9 / ambient 63.8 µg/m³, us_aqi ~155, `nh3:null` | `GET /aqi` |
| `/v2/why` | drivers[0]=**stagnation** (BLH 224.1 m + wind 1.65 m/s → VC ~370 m²/s) | `GET /v2/why` |
| `/v2/day` | heavy 19:30→day end ~104.4 · cleanest 12:30–16:30 ~58.1 · mean ~75 · 3 decisions | `GET /v2/day` |
| `/depart` | now 23.6 → best 21.3 @+10h (−10%), worst 45.5 @+19h | `GET /depart` |
| `/v2/outlook` | Oct-7 ~75 Moderate · Oct-8 ~123.4 Poor · Oct-9 ~158.8 Very Poor | `GET /v2/outlook` |
| `/v2/archive` | recorded[1,3,4] · gaps[0,2] · pending[5..23] (young tonight) | `GET /v2/archive` |
| `/v2/reach` | walk@25 4,103 edges/182.5 km · walk@50 12,353/676.2 km · car@25 951,130/85,612.6 km `edge_partial` | `GET /v2/reach` |
| `/v2/city/moves` | min_k **3** · 39 trips/7d · corridors 12/54 · suppressed_trips 0 | `GET /v2/city/moves` |
| `/community` | 22 obs · 14 contributors · 725.9 µg avoided all-time · 0 obs/24h | `GET /community` |
| `/v2/skill` | **210 pairs, h+0..h+11 all `ok`** — h+0 MAE 4.2, h+1 8.5, h+2 14.4, h+3 22.8 … h+11 54.9 | `GET /v2/skill` |
| `/v2/districts` | **29 rows** (16 district cells + 13 Delhi sub-areas) | `GET /v2/districts` |
| transit feeds | `real_feeds {metro:true, bus:true}` — real GTFS (263 metro stations/37 directions; ~6.3k bus stops/~2.9k routes) | `GET /health` + `server/transit_real.py` header |
| k≥3 privacy gate | `_K_MIN_DEVICES = 3`, `_CELL_WINDOW_S = 72*3600` | `server/community.py`, `server/v2/store.py` |
| `/observe` | **410 Gone** (donations → `POST /v2/trip`) | `server/main.py:1247-1258` |
| MAE vs DPCC holdout | former-GAP **22.8 → 10.5**, all-30 **27.1 → 6.2 µg/m³** | `docs/lanes/accuracy-holdout-report.md` → `holdout-reverify-report.md` |
| deploy task | 1 vCPU / **3 GB** + `osrm-routed` sidecar (`OSRM_URL=127.0.0.1:5000`); secrets `alive108/openaq`+`alive108/waqi`+`alive108/admin-token`; env `ALIVE_DPCC_INGEST=1`, `AGG_TABLE=alive108-agg` | `scripts/deploy.sh` L155-215 |
| EventBridge | rollup-daily (00:30 IST) + validate (20:30 IST) **enabled live** on one-off Fargate tasks; ingest-15min stays DISABLED (in-app `ALIVE_INGEST_IN_APP=1` owns the 15-min cadence). The committed `infra/schedules/*.json` are DISABLED scaffolds — see flag below | `docs/plan/handoff.md` cont.69/148 + `server/main.py:1888-1899` + `infra/schedules/` |
| tests | 981 `def test_` across `server/tests/`; `server/test_api.py` = 53 `check(` calls | grep |
| climatology | "125 stations × ~10 years" honest phrasing; "9.04M measurements" = raw-row count never independently re-verified (not served on the wire) | `GET /health` `history.source` = `openaq-data-archive`, 125 stations |

Wire quirk kept verbatim: `/aqi.calibration` still serves the committed
`server/data/field_calibration.json` — `method:"leave-one-out over live
OpenAQ instrument readings", n_stations:94, mae_ug:46.1`. Docs quoting it
are wire-accurate; the artifact's **label** is stale (predates the DPCC
feed). Flagged for the code lane — see §4.

## 2. Docs fixed in place (before → after)

| doc | before | after |
|---|---|---|
| `README.md` | diagram `HTTPS`; `13-district NCR choropleth`; ingest "~every 15 min (EventBridge)"; footnote "stations need OPENAQ_API_KEY… field still builds"; "24 live WAQI instruments"; "3 EventBridge schedules kept disabled"; "stations await the OpenAQ key"; owner-unblock listed OpenAQ/data.gov.in | `HTTP (NLB :80)`; `NCR choropleth (29 rows)`; in-app ingest + EventBridge rollup/validate; "54 instruments via WAQI+DPCC (OpenAQ dormant)"; "54 stations live"; "rollup-daily + validate enabled"; "54 stations live via WAQI + DPCC"; owner-unblock notes data.gov.in TCP-refused |
| `HANDOFF.md` | task `1 vCPU/2 GB`; "OSRM demo keyless… `OPENAQ_API_KEY` dead — stations honestly read 0"; `/v2/districts` "13-district"; owner-keys line "OPENAQ_API_KEY flips stations 0→N" | `1 vCPU/3 GB + osrm-routed sidecar`; stations LIVE 54 (24 WAQI + 30 DPCC) via `alive108/waqi`; 29 rows; "would widen beyond today's 54" |
| `docs/10-shipped.md` | "105 live CPCB/DPCC/HSPCB instruments (OpenAQ v3)"; OSRM "public demo only has driving graph"; "62 stations (Overpass)"; fires "needs FIRMS_MAP_KEY… no-key"; community "persisted to S3" | 54 live (24 WAQI + 30 DPCC), OpenAQ path dormant; self-hosted sidecar + fallback phrasing; real DMRC GTFS 263/37/~128k; firms-public-csv keyless today (67/15 tonight); DynamoDB `alive108-agg` + S3 mirror |
| `docs/17-submission-writeup.md` | "9-million-measurement climatology"; `server/deploy-aws.sh`; "Secrets Manager holds the OpenAQ key"; "9M" S3 line; AWS list missed DynamoDB/EventBridge; "41-assertion suite" | superseded-by `docs/submission/writeup.md` banner added; "125 stations × ~10 years (9.04M = raw-row count, unverified)"; `scripts/deploy.sh` + shim note; secrets list openaq+waqi+admin-token; DynamoDB + EventBridge bullets added; "53-check live suite + 981-test pytest" |
| `docs/18-aws-architecture.md` | "1 vCPU / 2 GB"; "9M-measurement decade product"; S3-only community persist; secrets = openaq only; externals "OSRM / OpenAQ-v3"; IAM "community/* only"; `deploy-aws.sh` | 1vCPU/3GB + osrm-routed sidecar (MLD 4.4M edges); 125×10yr phrasing; DynamoDB agg row; secrets openaq+waqi+admin-token; EventBridge rollup/validate + ingest-15min-disabled note; externals incl FIRMS-public-csv + aqicn; IAM scope per deploy.sh L155-162 |
| `docs/19-submission-checklist.md` | "the OpenAQ feed already covers CPCB stations"; FIRMS key as the only fire upgrade | FIRMS public-csv already live; "WAQI + DPCC cover CPCB stations — 54 live; data.gov.in TCP-refused" |
| `docs/submission/writeup.md` | "EventBridge drives the 15-minute field-rebuild cadence plus daily rollup and weekly validation" | rollup-daily + validation enabled on one-off tasks; 15-min cadence = in-app `ALIVE_INGEST_IN_APP=1`; ingest-15min disabled |
| `docs/submission/repo-readme.md` | diagram label "EventBridge: every 15 min" | "in-app ingest: every 15 min" |
| `docs/builder-center/article-draft.md` | abstract "EventBridge-scheduled rebuilds"; AWS list "15-minute field-rebuild cadence…" | "EventBridge-scheduled rollup/validation jobs"; in-app ingest loop named |
| `docs/demo-day.md` | fires "60 today, 14 belt… ×1.24 NW wind"; "WAQI measured stations LIVE: up to 24 instruments… (13–24 on the wire)"; "(9M station-hours)"; sources "(WAQI, N instruments)"; skill "131 pairs … MAE 2.2…54.5"; honest-limit "CPCB dormant…24 instruments live"; checklist "24 WAQI…13…~61–72 samples" | fires 67/15, ×1.08 SE-marginal tonight (×1.24 NW read kept as prior); **54 instruments — 24 WAQI + 30 DPCC**; "(decade climatology, 125 stations × ~10 years)"; "(waqi+dpcc — 54 tonight)"; **210 pairs** h+0 4.2…h+11 54.9 (131 kept as afternoon read); "OpenAQ dormant…54 live"; checklist updated to 54 + waqi+dpcc |
| `docs/plan/demo-script.md` | beat 2 "two dozen live instruments… stations 13–24 WAQI + ~61–72 CAMS samples… 60 fires/×1.24"; numbers-sheet field/fires/CP rows; skill "131 pairs"; why "stubble_smoke"; archive "21 snapshots"; reach "~136 km/~551 km/~93,721 km" | verbatim line → "fifty-four live instruments… about sixty-five NASA fire detections"; numbers sheet re-read tonight (54 waqi+dpcc, ~100 samples, 67/15/35.8 MW, ×1.08, pm25 68.9/63.8, AQI ~155, wind 6.7@134°); skill 210 pairs; why stagnation tonight; archive recorded[1,3,4]; reach 4,103/182.5 · 12,353/676.2 · 951,130/85,612.6 |
| `docs/plan/judges-faq.md` | example `/health` "24 WAQI… 79 fires"; source string `waqi-stations+…`; "9.04M OpenAQ measurements"; `/v2/skill` example all-thin; "CPCB dormant"; quick-table stations/skill/archive/species rows | example re-annotated 54 (waqi+dpcc) + ~100 samples + 67 fires; `waqi+dpcc-stations+…`; honest 125×10yr phrasing; skill example marked superseded (all-ok, 210 pairs tonight); "OpenAQ dormant — 54 via waqi+dpcc"; quick-table rows refreshed with stamps |
| `docs/plan/judge-qa-v2.md` | `calibration` curl block quoted without caveat; "9.04M OpenAQ measurements"; "WAQI is the only live stations feed" | curl kept verbatim + annotation that the artifact label/n=94 predates DPCC (flagged for code lane); honest climatology phrasing; "**DPCC now feeds 30 alongside WAQI's 24** — single-feed failure degrades, doesn't empty" |
| `docs/plan/go-nogo.md` | T-45 check "WAQI feed ok + count ≥20 (24 after warm)"; cold-window "~16 WAQI → 24" | `source:"waqi+dpcc"` + count ≥40 (54 tonight); cold-window climb to 54 noted |
| `docs/plan/master-plan.md` | "13-district NCR choropleth"; gap #5 "Public OSRM dependency" | 29 rows (16+13, `/v2/districts`); gap #5 marked CLOSED — self-hosted sidecar shipped |
| `docs/plan/NUMBERS.md` | §2 stamped "11:07–11:40 UTC `4eb9e1e8`": stations 24→13 WAQI, samples 61–72, fires 60/14 ×1.24 NW, PM2.5 84.9–88.2/69–71, AQI 158–159, wind 315–322°, day null/null/1-row/75.6, depart 20.9→113.2, why stubble_smoke, reach 136.1/550.6/93,720.8 km, community 24h 3obs, skill 131 pairs, archive 21 snaps, build 4eb9e1e8 | re-stamped "23:30 UTC `ce01ec5c`": 54 (24+30), 100, 67/15 ×1.08 SE, 68.9/63.8, ~155, 6.7@134°, day 19:30/~104.4 · 12:30–16:30/~58.1 · 3 rows · ~75, depart 23.6→45.5@+19h best 21.3@+10h, why stagnation, reach 182.5/676.2/85,612.6, community 0 obs/24h, skill 210, archive recorded[1,3,4], build ce01ec5c. POST-dependent rows (plan options, dose ladder, breath) keep the afternoon stamp marked ⟳prev — never re-invented |
| `docs/plan/realtime-status.md` | reads as "what's actually live right now" (written Oct-3) | dated **Superseded** banner naming the deltas (waqi+dpcc 54, OSRM sidecar, dosimeter surfaces, `/observe` 410) + pointer to NUMBERS §2 |
| `docs/plan/00-README.md` | open item "Live station data key" — field runs model-only without OpenAQ/data.gov.in | struck + "Resolved differently 2026-10-06: WAQI + DPCC = 54 live; OpenAQ would only widen" |
| `docs/plan/alive-depth.md` | "live field (24 stations + model + fires)" | "(54 instruments — 24 WAQI + 30 DPCC — + model + fires)" |
| `docs/plan/runbook.md` | step-3 secrets `alive108/openaq` + `alive108/cpcb` only; task-def secret list `OPENAQ_API_KEY` only | dated update note (stations live via waqi+DPCC; cpcb dead path; admin-token needed); secrets list now openaq+waqi+admin-token per `deploy.sh` L195-215 |
| `docs/api/REFERENCE.md` | generated Oct-3; lists `POST /observe` live; OpenAQ-era bodies | dated drift note listing all known diffs vs `ce01ec5c` (observe→410, waqi+dpcc feed, new v2 surfaces); `/observe` marked 410 in index + section (regen blocked — server needs py≥3.10, box has 3.9; POSTs to prod forbidden) |
| `docs/11-demo-script.md` | "live field from CPCB anchors + CAMS grid"; secrets beat names `alive108/openaq` only | "WAQI+DPCC anchors"; secrets list openaq+waqi+admin-token |
| `docs/20-hackathon-playbook.md` | "105 real CPCB/DPCC/HSPCB stations" (×2) | "54 live instruments (24 WAQI + 30 DPCC)" (×2) |
| `docs/23-delhi-data-inventory.md` | OpenAQ v3 "✅ primary live feed + archive"; WAQI "⚠️ cross-check only"; climatology "(9.04M rows)"; "~105 live… instruments" | OpenAQ "⚠️ dormant (key 401); archive still powers climatology"; WAQI "✅ primary measured feed today"; "125 stations × ~10 years (9.04M raw rows unverified)"; "30 DPCC + 24 WAQI live today" |
| `docs/24-design-language-spec.md` | "instruments blended (105 live @ 3×)" | "54 live — 24 WAQI + 30 DPCC @ 3×" (the "125 CAAQMS" veil line stays — it names the registry) |
| `docs/26-honest-impact.md` | "`/observe` donations" | "`/v2/trip` donations" |
| `docs/28-pitch.md` | '"9M station-hours" / "125-station climatology" stats' | '"125-station × decade climatology" stats' |
| `docs/30-live-tracking.md` | "~105 live CAAQMS instruments" | "54 live instruments — 24 WAQI + 30 DPCC" |
| `docs/00-executive-thesis.md` | "published free via CPCB/data.gov.in and OpenAQ"; "46 stations hourly" as field claim; "(CPCB stations timestamped ≤60 min)" | data.gov.in-dead + 54-live parenthetical; "the NCR instrument network (54 live today)"; "real instruments timestamped on the wire" |
| `docs/01-data-sources.md` | CPCB/OpenAQ marked "Primary live feed"; WAQI "cross-check only; do NOT build the DB on it" — inverted vs shipped reality | Roles corrected in place: data.gov.in **dead path** (DPCC adapter carries its 30 stations), OpenAQ **dormant**, WAQI **is the live measured feed** (24 instruments, EPA-breakpoint inversion) |
| `docs/12-lung-ledger.md` | "medians over 9.04M measurements" | "the decade archive (125 stations × ~10 years)" |
| `docs/claims-audit.md` | undated header | dated audit header + pointer to NUMBERS §2 for current figures |
| `docs/submission/video-shotlist.md` | drift table "13–24 WAQI + ~61–72 model samples" | "54 instruments (24 WAQI + 30 DPCC)… ~100 samples tonight" |
| `PRIVACY.md` | egress table: "OSRM public demo" as the routing path; "OpenAQ | reference station readings" | OSRM = self-hosted sidecar primary (demo = flagged fallback — coords stay in-AWS); OpenAQ marked dormant + WAQI/DPCC live-feed row added |
| `SECURITY.md` | rate-limit list included `/observe`; token "`anon-` + 8 base36 chars, regenerated only on data delete"; "/observe … still stores the raw token per row" | `/observe` dropped from list; token corrected to "**`anon-` + 16 hex chars, 64-bit CSPRNG** (`Mobile/src/community.ts:8-11`), rotated every 30 days"; `/observe` → **410 Gone** |

## 3. Flagged — snapshots/design docs left as written (not rewritten)

Per the sweep rules these are either dated evidence (never edited) or
design-phase docs whose claims never shipped — rewriting them would falsify
the record. Each entry: what it says vs shipped truth.

| doc | what it claims/describes | shipped truth |
|---|---|---|
| `docs/03-models.md` | "~46 stations" throughout | 54 live instruments (24 WAQI + 30 DPCC) — design doc |
| `docs/04-architecture.md` | CPCB data.gov.in ingest pipeline, Postgres/PostGIS schema | data.gov.in dead; ingest runs in-app into the raster store — design-era architecture |
| `docs/06-mvp-roadmap.md` | 46 stations; PostGIS/Redis/OTP2 stack | none of that stack shipped (FastAPI + in-process C++) — design doc |
| `docs/07-experiments.md` | kriging "honest at 46 stations" | design-phase — leave |
| `docs/09-transit.md` | 62-station hand-rolled DMRC registry narrative | updated in-place already by the transit lane (§"what's real now": 263 stations/37 directions) — historical sections stand |
| `docs/12-lung-ledger.md` | fixed in §2 above | — |
| `docs/22-breakthrough-research.md` | 3× "105 stations" research assumptions | research doc — leave |
| `docs/25-peak-physics.md` | "At 105 stations…" regime claim | research doc — leave |
| `docs/plan/01-mission-and-pitch.md` | `/observe` in the requirements map; "CPCB/OpenAQ stations"; Amazon Location listed as live AWS | plan-series pitch doc — `/observe` is 410; stations waqi+dpcc; Location key unset (`location.up:false` on `/health`) |
| `docs/plan/05-backend-architecture.md` | "Every 15 minutes (EventBridge → worker)"; `GET /v2/admin` basic-auth | in-app ingest loop owns 15-min; admin API is Bearer `/admin/api` — design doc |
| `docs/plan/07-city-dashboard-and-privacy.md` | "dark" Delhi-today; "38 stations" label; `/admin` "basic-auth" | surfaces shipped light-theme; 54 instruments; Bearer — design doc |
| `docs/plan/09-build-sequence.md` | "Ingest worker on EventBridge" | in-app loop; EventBridge = rollup/validate only — build-plan doc |
| `docs/plan/cpcb-source.md` | dated source investigation | leave (dated) |
| `docs/plan/vision-audit.md` | "(24 WAQI instruments…)" paragraph | stamped 2026-10-04 audit — leave |
| `docs/plan/red-team.md` | "24 WAQI + ~71 CAMS samples" verification row | stamped 2026-10-05/06 on build `033aa866` — leave |
| `docs/plan/handoff.md` | dated continuation log (cont.N) | evidence ledger — never edited |
| `docs/plan/offline.md` | `/observe` + `/report` outbox rows | design/spec doc — `/observe` is 410; flag only |
| `docs/lanes/*` (~85 files) | every stamped number | evidence by definition — never edited |
| `docs/plan/NUMBERS.md` §4 + reconciliation history | past-pass figures | history — leave |
| `docs/claims-audit.md` body rows | stamped claims | dated banner added; rows left |
| `docs/submission/submission-checklist.md` | already correct (waqi+dpcc, final APK `alive108-c3bb731.apk`) | verified — no change needed |
| `docs/02,05,08,13,14,15,16,20-design-research,21,27,29,31,32,33` + `docs/plan/(remaining ~45)` | competitive/research/design content | no stale shipped-truth numbers found in sweep — clean |
| `docs/privacy/{data-flow,verify}.md` | k≥3/72 h/`/v2/trip` mechanics | verified against code — accurate as written |
| `docs/assets/*` (images/logs) | screenshots, logcat | static artifacts — leave |

## 4. Flagged for the CODE lane (drift on the wire / in tooling — not docs)

1. **`server/data/field_calibration.json`** — served verbatim at
   `/aqi.calibration`: `method` still says "live OpenAQ instrument
   readings" and `n_stations:94` predates the waqi+dpcc feed (54). The
   numbers are a real pre-DPCC audit; the *label* is what lies. Code lane
   should re-label (or re-run) — docs that quote it were annotated, not
   "fixed".
2. **`scripts/verify_numbers.sh`** — matcher regexes still pin the old
   world: L161 `24 (live )?(WAQI|instruments|stations)` + label
   "stations live (WAQI)", L318 `f"{count} WAQI stations live"`, plus
   fired "~7[0-9]" fires pattern. Needs `54|waqi+dpcc`-era patterns or
   the T-45 verifier will false-flag correct docs.
3. **`infra/schedules/*.json`** — all committed `"State":"DISABLED"`
   scaffolds, but handoff cont.69/148 says rollup-daily (00:30 IST) and
   validate (20:30 IST) are ENABLED live. Repo↔AWS state disagree; either
   commit the live states or annotate the scaffolds as placeholders.
   (ingest-15min correctly DISABLED — in-app loop owns it.)
4. **`scripts/gen_api_docs.py` refresh** — REFERENCE.md drift note covers
   it meanwhile; regen needs Python ≥3.10 (server uses `X | None` syntax;
   this box is 3.9) and a live target that accepts POSTs.

## 5. Verified correct — no edit needed

Edges 1,070,459/903,058 · MAE 22.8→10.5 / 27.1→6.2 chain (landed
39a161c) · k≥3/72 h privacy constants · districts 29 rows · history
`openaq-data-archive` 125 stations · gazetteer 124,311 / corpus 97,447 /
16,949 address rows · transit GTFS 263/37/~128k + bus ~6.3k/~2.9k ·
`transit.real_feeds {metro,bus}:true` · `/v2/ledger` token-gated 422 ·
`community` aggregates-only store.
