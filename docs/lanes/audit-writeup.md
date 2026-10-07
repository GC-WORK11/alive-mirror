# audit-writeup — hostile cold-read of `docs/submission/writeup.md`

Lane: `audit-writeup`. Audit-only: no product code touched. Verified
2026-10-07 ~04:11–04:35 UTC against live prod
(`alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com`, **build
`44e5e97f`** on `/health` — two image rolls past the writeup's stamped
`ce01ec5c`) and `base/v2` HEAD `3c34cd6`. GET-only probes — no POSTs
(`/v2/plan` numbers judged against code + the `prod-numbers-card`
03:04 UTC reads + `NUMBERS.md`, not a fresh plan call).

Read standard: a judge with the GitHub link in one tab and the live wire
in the other, 60 seconds to decide what this thing is. "Overclaim" = P1,
"underclaim that undersells real proof" = P2, drift/consistency = P3.

**Verdict up front: no fabrication found. Two P2 phrasing invites
(plaintext-HTTP soft-pedaled; the self-grade surface never mentioned),
one P2 evidence-pointer self-own (EventBridge "enabled live" cites the
DISABLED committed JSONs), one lede overstatement ("no uploads"), and a
bundle of P3 drift staleness the stamps already half-cover. The writeup's
strongest habit — every claim carries a bracketed pointer — mostly holds;
the surfaces it fails to point at are `/v2/skill` and `/v2/why`.**

---

## 1 · Claim table

| # | claim (writeup §:line) | verified against | verdict | sev |
|---|---|---|---|---|
| 1 | "most polluted megacity… 10–20× WHO Oct–Feb" (lede:23) | `docs/00-executive-thesis.md:5` carries the same claim; WHO24h 15 µg vs observed live field ~60–87 → the multiple is real arithmetic | TRUE | — |
| 2 | Plume $200 dosimeter discontinued 2023; BreezoMeter killed twice (lede:26-27) | `docs/plan/alive-depth.md:10-14` — both claims in the depth doc | TRUE (cited) | — |
| 3 | k=3 distinct devices / 72 h, `min_k` on the wire (prod:39) | live `/v2/city/moves` → `min_k:3`, `corridors.window_h:72`; `community.py:119-120` `_K_MIN_DEVICES=3`, `_CELL_WINDOW_S=72*3600` | TRUE live | — |
| 4 | "no per-trip row exists in memory, on disk, or in S3" (prod:42; repeated :83, :163) | `community.py:20-28,56,383,952` (aggregate-only structures, per-trip rows "die on disk"); `agg_ddb.py` schema = `day#`/`hour#`/`area#`/`od#`/`sum` keys only, legacy `trip#` rows ignored + 72h-TTL'd (:271); live `/community` basis echoes "no per-trip records exist at rest" | TRUE | — |
| 5 | Field rebuilt every 15 min (arch:51) | `/health` `field_age_s` 240–313 observed across probes, `refresh_ttl_s:900`; NUMBERS §1 stale_after 2700 | TRUE | — |
| 6 | "54 live ground instruments — 24 WAQI + 30 DPCC" (arch:52, table:191, header:7) | live `/health.sources.stations.count` = **53** (one instrument aged out — per-instrument aging is designed churn); `/aqi.station_readings` = 53, `source:"waqi+dpcc"`, feeds both `ok` | DRIFTED (stale-low; honest stamp) | P3 — refresh to "~53–54" per prod-numbers-card phrasing |
| 7 | "~70 CAMS/open-meteo model samples" (arch:54) | live `/v2/day.field.samples` = **98**; NUMBERS §2 pinned 100 | DRIFTED stale-low | P3 |
| 8 | FIRMS "67 at last read, 15 in the NW belt; wind-gated ×1.24 carrying → ×1.08 refused easterly" (arch:55-57) | live `/v2/why.evaluated.fires` = **80 fires / 20 belt / 42.1 MW / modifier ×1.10 / carrying:false**; the claim-then-refuse arc verified in `field-watch-2-report.md` (×1.24 @344° → refused ×1.07–1.08 at 15°→139°) | TRUE mechanism; counts drifted | P3 |
| 9 | field age "~2 min" on the wire (arch:59) | observed 240–287 s (~4–5 min) — inside the honest range | DRIFT-fine | — |
| 10 | hourly archive to S3 + local mirror, IST-bucketed, gaps never backfilled, recording since Oct 5 (arch:60-65, diff:172-177) | live `/v2/archive`: hour 0 `status:"gap"`, hour 1 recorded w/ `station_readings:54`, `n_cells:484`, `band_convention` — honest-gap serialization observed; `archive.py:9-18` + `v2/archive.py:8` docstrings match | TRUE live | — |
| 11 | C++ engine + bit-exact Python twin; A* twin + bounded-Dijkstra settle identical edge set; dose kernels parity 1e-9 (arch:66-70) | `test_reach.py:3-9` ("parity means the SAME settled edge set"), `test_path_parity.py`, `test_parity_dose.py:31 REL=1e-9`, `test_parity_series.py:42` — files exist, conventions match claim | TRUE (cited tests exist; run = suite pass) | — |
| 12 | "1,070,459 road edges (903,058 priced)" (arch:72) | live `/health.routing.edges` = 1,070,459 / `edges_priced` = 903,058 — exact match | TRUE live | — |
| 13 | dose = C × microenv × VE × t, ~250 m integration, Goel/Apte/Zuurbier anchors (dose:75-79) | `exposure.py:3` formula; microenv table `metro .45 / car_ac .55 / auto 1.30 / walk 1.30` w/ measured citations `[1]-[6]`; citations names match (STE-2021, Discover-Atmos-2025, Zuurbier-2009, Goel-2015, Apte-2011) | TRUE | — |
| 14 | ledger.json on phone, 500-trip cap, delete-all, no account (ledger:80-82) | `Mobile/src/store/ledger.ts:10-11` (`ledger.json`, `MAX_TRIPS=500`); `daylog.json` separate; `strings.ts:296,352,465` delete-all + "kept on this phone only" copy | TRUE | — |
| 15 | donation trimmed on-device, re-trimmed/thinned/rounded server-side, ~500 m cells (ledger:82-83) | `trip.py:35-37` TRIM_M=300/THIN_M=100/ROUND_DP=4 (~11 m); `community.py:19` "~500 m cell traversals at ingest" | TRUE | — |
| 16 | "Per-device history readable only by holder of the raw device token", `DELETE /v2/ledger` wipes (ledger:84-86) | `ledger.py:36-51` — 422 without token, sha256[:16] key, "Only a holder of the raw device_token reads this ledger"; `:54` DELETE wipes device rows (corridor counts honestly NOT touched — disclosed in docstring) | TRUE | — |
| 17 | community counter "14 contributors / 22 trips all-time, ~14.1 km / 477.3 µg avoided 24 h, 725.9 µg all-time" (answers:94-97) | live `/community`: **40 obs / 22 contributors / obs_today 1 / avoided_all 1,028.5 µg** — writeup stamped "read Oct 6 ~03:50 IST — it grows daily" | DRIFTED stale-low (donations landed since — the stale direction is the *safe* one) | P3 — restamp |
| 18 | `/v2/day` @CP "cleanest 12:30–18:30 ~45 vs ~105 day mean; heavy 22:30→day end ~159; three decision rows" (answers:99-104) | live `/v2/day` @CP: day_mean **77.3**, cleanest **14:30–17:30 ~65.9**, heavy **20:30→end ~94.8**, decisions = 3 rows. Stamped Oct-5 read vs NUMBERS' Oct-6 stamp (58/~75) vs live now — three different reads of one endpoint | DRIFT class — internally consistent but writeup ≠ NUMBERS ≠ live | P3 — the two canonical docs quote different stamps of the same surface |
| 19 | `/v2/reach` walk 25 µg "3,211 segments ~141 km"; ≤50 µg "10,510 ~554 km"; car 25 µg "~891k edges ~75,822 km, edge_partial, 2M cap, veil paints nearest 90,000" (answers:105-117) | live: walk@25 **3,480 / 153.4 km**, walk@50 **11,132 / 600.1 km**, car@25 **899,743 / 77,159 km partial:true, exactly 90,000 polylines served**, took 1.2 s. Caps: `reach.py:37-38` REACH_MAX_STATES=2M / EDGE_SERVE_MAX=90k | TRUE mechanism, drifted counts | P3 — and "paints the **nearest** 90,000" misdescribes the mechanism: `reach.py:186-188` takes a *strided* subsample across the whole frontier (that change is why the veil shows the frontier, not a blob). Say "a 90,000-edge sample of the settled frontier" |
| 20 | plan table CP→Gurugram 23 options, dose ladder car-AC 10.8 → walk 358.3, "~35× (33.2× tonight, 31–45× across ODs)" (feature:122-140) | POST not re-run (lane is GET-only). Code path + prod-numbers-card 03:04 UTC pass: spread 33.0× best-vs-best, 24 options; NUMBERS §3 "31–45× all week, honest phrasing ~35×". Writeup carries the stamped read + range phrasing correctly | TRUE (stamped; consistent w/ NUMBERS) | P3 — "drifts 16–23" under-caps: observed max is 24; say "16–24" |
| 21 | "walking ≈28× metro per km, auto ≈5× — Sci. Total Environ. 2021 / Discover Atmosphere 2025" (feature:141-143) | `exposure.py:11-16` headers carry both citations | TRUE (cited) | — |
| 22 | "metro+walk ~4× sealed car" (feature:144-146) | arithmetic on prod-card ladder: 39.2 / 8.8 ≈ 4.5× ✓ | TRUE | — |
| 23 | alternates "must diverge ≥15%… measured 19–96%" (feature:147-149) | `demo-script.md:46,95` — alt1 96% / alt2 55% / rd 19% vs spec ≥15% | TRUE | — |
| 24 | corridor example "via Outer Circle vs via Vivekanand Marg" (feature:148) | `Vivekanand Marg` appears nowhere live — NUMBERS §4 shows this stale name was already refreshed once to "Outer Circle–Radial 7 vs Sansad Marg–Rafi Marg". Illustrative-but-dated | STALE nit | P3 |
| 25 | `/v2/city` next 12 h, "~70 → ~151 → ~39 by ~09:00" driven by "120-hour CAMS… τ=9 h" (nobody:153-160) | live `next_hours` = 12 rows 65.5→86.5 rising (drift — stamped read); `/v2/day.model` on the wire literally says "parcel-bias delta (decays ~9 h)" = τ=9 h ✓; horizon: served `horizon_hours:105` | TRUE mechanism; drifted shape | P3 — prod-numbers-card's phrasing rule: **say "5 days", not "120 hours"** (served horizon drifts) |
| 26 | `/depart` "~29 now vs ~80 worst, ~15 best ~+12 h — ~2.7× now→worst tonight, ~8× this week" (nobody:157-160) | live: now 27.5 → worst 46.1 @+22 h / best 25.6 @+7 h (**~1.7×**). NUMBERS logged range 2.7–8.3× — writeup's "tonight" stamp is honest, the "~8× this week" range is ledger-backed | DRIFT class | P3 |
| 27 | `/observe` retired 410 Gone (privacy:165) | `main.py:1277-1287` POST→410; GET→405 (method routing — the retired surface is POST) | TRUE | — |
| 28 | "uvicorn access log off, request log = path templates only, coords/tokens denylisted; contributor id = 64-bit CSPRNG rotating 30 d" (privacy:165-168) | `observability.py:83-96` denylist covers lat/lon/token/apikey + 2-dp coord floor; `community.ts:5-17` `anon-`+16-ch, 30-day TTL — the CSPRNG path uses `crypto.getRandomValues`; a `Math.random` fallback exists at `:38` (minor honesty nuance: id is crypto-strong where available) | TRUE | P3 nit |
| 29 | "12 of 54 tracked corridor cells publishable; the other 42 honestly suppressed; `mode_share_suppressed_trips` on the wire" (privacy:167-171) | live `/v2/city/moves`: **active 12 / tracked 55** → 43 suppressed; `mode_share_suppressed_trips:0` present on the wire | TRUE mechanism; count drifted | P3 |
| 30 | "CO₂ + tailpipe-PM2.5 band… metro+walk: 0.42 kg CO₂" (nobody:178-180) | `emissions.py:144-183` BS-class fleet tables real; the 0.42 figure is plan-computed (POST not run) — code-consistent | TRUE (code) | — |
| 31 | 95.2% @±2σ, 3,550 station-hours / 85 stations, nominal 95.4% (table:189) | `field_validation.md` headline table: exactly 3550/85/95.2/95.4 | TRUE artifact | — |
| 32 | holdout: "pre-ingest MAE 27.1 (blind 22.8) → post-ingest 6.2 (blind 10.5), all 30 at nearest_sample_km=0.0" (table:190, holdout:204-242) | `accuracy-holdout-report.md:38-41` (22.8/26.5/+3.2; 27.1/34.2/−16.0) + `holdout-reverify-report.md:26-35` (10.5/+0.8; 6.2; worst 19.1; all 0.0) — every figure matches verbatim | TRUE | — |
| 33 | LOO "MAE 8.8, bias +0.2, n=70" (table:192) | live `/aqi.calibration` = `{mae_ug:8.8, n_stations:70, mean_bias_ug:0.2, rmse:12.7}` == `field_calibration.json` (6ad7de6) byte-for-byte | TRUE live | — |
| 34 | archive replay "MAE 22.0, bias +51.6%" (table:193) | `field_validation.md`: +15.5 µg (**+51.6%**) — writeup quotes the % only, correctly labelled | TRUE | — |
| 35 | "Plan ~0.8 s warm; unseen 2–8 s; Reach ~1–2 s walk / ~5–10 s car; search 97,447 corpus / 16,949 addr / 172/174 (98.9%) p50 ~470 ms / gazetteer 124,311; engine p50 0.189 ms ~88×; pmtiles 22.7 MB z0–14; landmark purge 23 (2c4cab4)" (table:194-200) | `corpus/STATS.md:9,25` ✓; `bench-results.md:16,20` 0.189/~88× ✓; `demo-script.md:102` 172/174/471 ms ✓; `/tiles/health` live 22.7/z0-14 ✓; commits 2c4cab4 + test file exist ✓. Reach live was *faster* (0.4–1.2 s) — underclaim-safe | TRUE | P3 — reach latency claim is conservative vs live |
| 36 | DPCC ingest details: nav-bar 30-station superset, 6 unlisted = blind spots (IGNOU/JNU/CWG/NSUT/Talkatora/SBV), unit tokens asserted, PM25>PM10 dropped (holdout:223-230) | `ingest_dpcc.py:27-29` names all six verbatim; `:104-111,217-243` unit_mismatch + stale + pm25>pm10 plausibility drops | TRUE | — |
| 37 | "blind sites best-behaved… Jahangirpuri 143 vs served 73 (−68), Sonia Vihar −63, Rohini −53" (holdout:217-219) | `accuracy-holdout-report.md:59,74,77` — −68.1 / −63.2 / −53.3 | TRUE | — |
| 38 | "every cell ≤~4 km inside ring; rims 5.5–15.7 km; JNU 83.6 vs ~55–65; IGNOU 0.15 signature" (holdout:236-241) | `holdout-reverify-report.md:66,89-91,99-109` — all match | TRUE | — |
| 39 | "14 probes ~8 h; ×1.24→refused; trend −7.5→+35.7 over ~6 h; dose-ratio flag → spatial gradient" (holdout:244-250) | `field-watch-2-report.md:3` (14 probes 11:51–19:30 ≈ 7.7 h), probe 12 `+35.7`, `:223` "honest spatial gradient, not a dose-scaling bug" | TRUE | — |
| 40 | AWS list: ECS Fargate ap-south-1 SPOT 1vCPU/3GB, NLB+ElasticIP stable URL, CodeBuild→ECR→taskdef, S3 (snapshot+archive+pmtiles), DDB alive108-agg aggregates-only, Secrets Manager, EventBridge rollup/validation enabled, CloudWatch field-age alarm + $50 budget, OpenAQ S3 climatology 125 stns × decade (aws:252-284) | `deploy.sh:197` cpu 1024/mem 3072 + FARGATE compat; `:244-248` EIP allocation; `:210-215` secrets ARNs; `:204-207` AGG_TABLE/buckets; `:164-184` OSRM same-task sidecar; `provision.sh:12,60,188-225` field-age alarm (treat-missing breaching) + 5xx + $50 budget; `/health.history.stations` = 125 live; handoff:69-70 schedules enabled + jobs ran exit-0. `build_sha` on wire = deploy claim mechanism ✓ | TRUE — **except the citation flaw at §2.3 below** | — |
| 41 | "~$46/month worst case inside $200 credits; Fargate Spot runs it near-zero outside demo windows" (aws:282-283) | `docs/18:65-67` "~$46–50/mo run-rate"; checklist `$200` credits ✓. **"near-zero outside demo windows" is loose** — a running 24/7 Spot task ≈ $30–46/mo regardless of demo traffic; near-zero needs desired-count 0, which nothing documents | LOOSE cost phrasing | P3 |
| 42 | surfaces: `/` landing live field + 12-h scrubber + a→b; `/city` choropleth + ticker + corridors + reach veil; `/community` ledger; `/admin` engine room (design:287-297) | All four pages exist + serve (GETs 200); veil refs in `city.html`; admin pages real | TRUE | — |
| 43 | "the /admin archive tile shows it live" (nobody:176) | `/admin/api/*` is 401-gated for guests — a judge without the admin token sees the tile chrome, not live data | SMALL overstatement of public verifiability | P3 |
| 44 | "Community data is young — 14 contributors, ~14.1 km / 6 donated trips 24 h (22 all-time)" (not-claim:308-311) | live: 22 contributors / 40 obs / obs_today 1 — the honest-emptiness disclosure stands, numbers stale-low | TRUE disclosure; DRIFTED numbers | P3 restamp |
| 45 | "One task, one region (NCR-only), HTTP :80 only — no custom domain yet" (not-claim:314) | live: :80 answers, `deploy.sh:256` single TCP listener no cert; README:22 admits it | TRUE — but see §2.2: it's a soft disclosure of a hard attack | P2 phrasing |
| 46 | "CPCB geo-blocked… adapter reports itself dormant" (not-claim:315-317) | `/health` stations `source:"waqi+dpcc"` — CPCB absent, honest; `field_validation.md` documents geo-block | TRUE | — |
| 47 | "met-wind feed intermittently known:false… says so on the wire" (not-claim:318-320) | `field-watch-2` probes 6 logged "wind-null race"; mechanism documented | TRUE | — |
| 48 | "dose cut by about thirty-five times on the same trip" (impact:325) | consistent w/ row 20 — range-phrased, not pinned | TRUE | — |
| 49 | lede: "**no device, no uploads**" (lede:21) | "no device" TRUE. "no uploads" is absolutist — donated trips DO leave the phone (as trimmed aggregates, opt-in-default). The same doc spends a section on what gets uploaded. A hostile judge quotes the lede against the architecture | OVERSTATEMENT in the hook | **P2** — tighten to "no device, nothing personal leaves the phone" (the line the receipts already use) |
| 50 | "We can't leak what we never take — and we never take a trip" (prod:40-42) | At-rest: TRUE (row 4). In-transit: donations travel plaintext HTTP before folding — the "never take" claim is an at-rest truth only, and the doc discloses HTTP :80 300 lines later | TRUE with a gap the doc itself half-discloses | covered under §2.2 |
| 51 | header: "Every number below was read off the live service or traced to a repo file on 2026-10-05 — re-verified ~22:15 UTC on build 80a15258, then extended Oct 6 on ce01ec5c" | Stamps honest; every stamped number re-derived per above. But judges read it Oct 8–11 — three deploys later, half the drift-class figures no longer match the wire (53 stns, 40 obs, 12/55, ~98 samples, 80/20 fires) | STAMPED-TRUE, demo-stale | P3 — add "figures are stamped reads; the live wire drifts" one-liner or restamp T-1 |

---

## 2 · The four known weak spots — dodge or invite?

### 2.1 Citizen-layer emptiness → **INVITED, well-framed**
The writeup doesn't hide it: "Community data is young — 14 contributors…
k≥3 floor means the corridor table is honestly sparse" (not-claim §) and
"12 of 54… the other 42 are honestly suppressed" (privacy §). That is the
armed answer — emptiness reframed as the privacy gate working at real
scale, suppression field public. The numbers are stale-low (live: 22
contributors / 40 obs / 12-of-55) which weakens it slightly — refresh and
the frame gets *stronger*, not weaker. **Verdict: invite held. Only fix
the stale counts.**

### 2.2 Plaintext HTTP → **SOFT-DODGED**
Line 314 buries it as an infrastructure nit: "One task, one region
(NCR-only), HTTP :80 only — no custom domain yet." A security judge
doesn't hear "we know our privacy pillar rides cleartext" — they hear an
omission two sections after "We can't leak what we never take."
`judge-answers-v3` §2 already wrote the armed line: *"the transport is
plaintext today, and we don't pretend otherwise — what travels is a
trimmed aggregate, no credentials, no identity; closing it is a domain +
ACM cert + a 443 listener."* Put that sentence in the writeup and the
attack dies on contact. **P2 — name it, don't euphemize it.**

### 2.3 Decorative-AWS → **INVITED but one citation self-owns**
The AWS section is the strongest "deployed not claimed" writing in the
doc — NLB+ElasticIP, CodeBuild→ECR (build_sha on the open wire = image
tag), S3 archive that `/v2/archive` publicly reads back, secrets-by-ARN,
alarms, budget. Verified: every mechanism exists.
**But** the EventBridge line cites `infra/schedules/` — whose committed
JSONs all read `"State":"DISABLED"` with `${*_TARGET_ARN}` placeholder
ARNs. The claim is *defensible* (handoff.md:69-70,144,148 documents the
live `alive108` schedules enabled on corrected targets + one-off jobs
that ran exit-0 → `daily/2026-10-03.json`, `weekly-2026-W40`; the
committed files are provision templates) — but the bracketed pointer is
the one place a judge can click and see the opposite of the claim. Cite
`docs/plan/handoff.md` (or `infra/provision.sh`'s schedule path) instead.
Residual unverifiable-by-design: DynamoDB backend has a silent memory
fallback (`store.py:337-353`) invisible on public `/health` — the
writeup doesn't claim it's publicly checkable, so no flag; a judge who
asks gets the `agg_ddb.py` schema answer. **P2 — fix the pointer, keep
the claim.**

### 2.4 Forecast-decay self-grade → **DODGED BY OMISSION**
`/v2/skill` appears **zero times** in the writeup. The doc sells
"history, not just forecast" and a 12-hour next_hours narrative, but the
one surface where the forecast grades itself — and decays to ~30%
band-hit by h+11 — is never mentioned. The wire itself discloses it
(`basis:"self-graded"`, "the model grading itself" in the note field).
A judge who clicks the landing skillLine sees 248 pairs and a decay
ladder the writeup never framed; the armed answer ("self-grade vs its
own recorded field — we publish the ladder instead of hiding it; LOO
8.8 is the instrument-truth number") lives only in the lane docs.
**P2 — add one honest line; the surface is already honest, it just needs
a frame in the doc a judge actually reads.**

*(Also noted, not one of the four: the kriging-vs-IDW tie is nowhere in
the writeup — it sells "a real σ band" without claiming kriging wins on
MAE, which is exactly the defensible position. field_validation.md linked
from the landing does show the tie; acceptable.)*

---

## 3 · Numbers consistency — writeup vs NUMBERS.md vs prod-numbers-card

Post-LOO world check:

| figure | canonical now | writeup says | verdict |
|---|---|---|---|
| LOO calibration | **8.8 / n=70 / +0.2** (on the wire) | 8.8 / 70 / +0.2 | ✓ post-sweep, consistent |
| stations live | **53** (52–54 churn range) | 54 | drifted — say "~53–54" |
| dose spread | **~33× tonight / 31–45× range** | ~35× (33.2× tonight, 31–45×) | ✓ consistent phrasing |
| typical October delta | **"a third to a half below"** (−45.7% live) | not quoted | ✓ clean — no 46% pin anywhere |
| community | **40 obs / 22 contributors / 1,028.5 µg** | 14 / 22 / 725.9 | stale-low, restamp |
| corridors | **12 active / 55 tracked** | 12 / 54 | drifted |
| model samples | **~98–100** | ~70 | stale-low |
| fires | **80 / 20 belt / ×1.10 refused** | 67 / 15 | drifted, stamped |
| day windows @CP | **cleanest 14:30–17:30 ~66, heavy 20:30→end ~95, mean 77** | 12:30–18:30 ~45 / ~105 mean / 22:30→end ~159 | two different stamps — pick the latest or say "tonight read ~60s vs ~70s mean" |
| reach w25/w50/c25 | **3,480/153 km · 11,132/600 km · 899,743/77,159 km** | 3,211/141 · 10,510/554 · ~891k/75,822 | drifted, same class |
| options count | **16–24** | "drifts 16–23" | under-caps — say 16–24 |
| depart now→worst | **27.5 → 46.1 (~1.7×)** | ~29 → ~80 (~2.7×) | drifted; range claim still ledger-true |
| forecast horizon | **"5 days"** (105 served of ~120) | "120-hour CAMS forecast" | phrasing rule — say 5 days |
| build_sha | **`44e5e97f`** | `ce01ec5c` | stamped historical read — expected |
| field age | ~4–5 min | "~2 min" | drift-fine |
| community wire field names | `obs_today`/`km_today`/`avoided_ug_today` (post-e572f58) | prose only, no field names | ✓ safe |

Rule check per NUMBERS §classes: every `static` figure (edges, corpus,
gazetteer, pmtiles, bench, artifacts, 125 stations, ≥15% divergence spec)
is verbatim-safe and verified. Every miss above is `drift`-class with an
honest stamp — none is a `wart` or fabrication. The one structural nit:
writeup's stamped day-window read and NUMBERS §2's stamped read disagree
(they're different nights) — a meticulous judge comparing the two
canonical docs sees "45 vs 105" in one and "58 vs 75" in the other.

---

## 4 · Missing proof surfaces

Present and cited: `/health`, `/aqi` (+calibration), `/community`,
`/v2/city/moves`, `/v2/day`, `/v2/reach`, `/v2/city`→next_hours,
`/depart`, `/v2/archive`, `/tiles/health`, `verify_numbers.sh`,
NUMBERS.md, field_validation, corpus STATS, bench-results, 4 lane
reports (accuracy-holdout, holdout-reverify, ingest-dpcc, field-watch-2),
PRIVACY.md, commit shas.

**Absent, and it costs:**
- **`GET /v2/skill`** — the self-grade. Biggest gap (§2.4).
- **`GET /v2/why`** — the causal explainer ("the air is barely moving —
  boundary layer 647 m × wind 2.49 → ventilation 1,611 m²/s vs ~3,000")
  is the most differentiating live surface and carries its own evidence;
  never cited. P3 suggestion.
- **`GET /v2/outlook`** — the 5-day band view exists live; the writeup's
  day-card story could lean on it. P3.
- **`/reports`** (k≥3 corridors GeoJSON) — the public-shape proof that
  suppression means something; mentioned only indirectly. P3.
- The test suite itself (~1,190 tests; `server/test_api.py` live-upstream
  checks) is never waved at — "we measured, not claimed" lands harder
  with the suite count. P3 suggestion.

---

## 5 · Cold-read verdict (the 60-second test)

**Lands.** The lede is plain and does the job — "what you breathed
today, where it cost you, and when tomorrow's air is worth going out in"
needs no domain knowledge; "no device, no uploads" is the hook that a
deliberate judge then stress-tests (see row 49). "Your lungs' ledger"
recurs and stays consistent with the app copy ("kept on this phone
only"). "Dosimeter" arrives *after* the plain-English version, defined
by usage — the right order.

Jargon that survives a non-AQ judge: `kriged`, `σ band`, `Dijkstra`,
`edge_partial`, `breathing-zone basis` — all either parenthesized or
inside the architecture/table sections where a technical reader expects
them. Two unglossed terms worth fixing:
- **"the parali ramp"** (holdout §) — Punjabi for stubble-burning
  season; a non-Delhi judge can't parse it. One word fixes it:
  "the parali (stubble-burning) ramp". P3.
- **"bz basis"** in the dose-table footnote is fine as-is since it's
  labelled, but "breathing-zone" could take three extra words
  ("breathing-zone = what hits your face, not the rooftop sensor").

Structure holds: lede → product → architecture → three questions → the
feature judges poke → differentiators → measured table → the self-
holdout story → AWS → design → not-claims → impact. The holdout section
is the trust-builder — "we audited ourselves against a government
network we didn't ingest, published the misses, then closed them" is the
single most persuasive beat in the doc, and it's all verified verbatim.

One tension to smooth: "no uploads" (lede) vs "donations fold into
aggregates" (everywhere else). Fix the lede word, not the model.

## 6 · Track-01 / AWS fit

**Track fit: self-evidently Air** — the doc is end-to-end PM2.5 with WHO
multiples grounding the problem. ✓

**"Why AWS" is answered concretely, not aspirationally:** ECS Fargate
(SPOT, 1vCPU/3GB) + NLB on Elastic IP (stable public URL surviving
redeploys — verified resolving 65.2.28.40) + CodeBuild→ECR→taskdef (the
`build_sha` on the open wire is the image tag — a judge can prove the
deploy pipeline by curling `/health`) + S3 (field snapshot, archive,
pmtiles — `/v2/archive` publicly reads `alive108-air` objects back) +
DynamoDB (aggregate-only schema verified) + Secrets Manager + EventBridge
+ CloudWatch field-age alarm (missing-data = breaching — literal) + $50
budget + OpenAQ's public S3 as the climatology source. Cost claim
quantified (~$46/mo vs $200 credits).

What's missing is the *argument* line — one sentence on why this product
specifically needs durable-AWS rather than a VPS: the hourly field
archive is the differentiator ("history, not just forecast") and durable
object storage is its spine; keys live outside the image; aggregates
survive task replacement. Everything's there; the doc just doesn't say
"that's why AWS". P3 suggestion.

## 7 · Fix list, severity-ordered

**P2 — invite the attacks instead of dodging them:**
1. Plaintext HTTP: replace "HTTP :80 only — no custom domain yet" with
   the armed line (plaintext today + payload is already a trimmed
   aggregate + fix = domain+ACM+443, the one real gap we'd close first).
2. `/v2/skill`: add one line — the forecast grades itself hourly against
   its own recorded field and publishes the whole decay ladder; between-
   station LOO (8.8/n=70) is the instrument-truth number.
3. EventBridge citation: point at `docs/plan/handoff.md` (or note the
   committed `infra/schedules/*.json` are provision templates and the
   live group is enabled on corrected targets) — the current pointer
   shows DISABLED stubs.
4. Lede: "no device, no uploads" → "no device, nothing personal leaves
   this phone" (or keep "no uploads" only if it's immediately scoped —
   "no uploads of where you were" is still false since donated cells go
   out; prefer the personal-data frame).

**P3 — refresh/phrase:**
5. Restamp drift figures: stations (~53–54), community (22/40/1,028.5),
   corridors (12/55), samples (~98), fires (80/20), day windows, reach,
   depart, options "16–24". Or add the header line "stamped reads — the
   wire drifts."
6. "120-hour CAMS forecast" → "5-day forecast" (served horizon drifts).
7. "paints the nearest 90,000" → "a 90,000-edge sample of the settled
   frontier" (it's strided, `reach.py:186-188`).
8. "~$46/month worst case… near-zero outside demo windows" — the task
   runs 24/7; say "~$46/mo run-rate, near-zero if scaled down between
   demo windows."
9. "via Outer Circle vs via Vivekanand Marg" → current corridor pair
   (NUMBERS §4: "Outer Circle–Radial 7 vs Sansad Marg–Rafi Marg") or
   genericize.
10. "the /admin archive tile shows it live" — the tile is token-gated;
    say "/v2/archive is the public proof" (it is).
11. Gloss "parali ramp" once.
12. Suggest citing `/v2/why` + suite size somewhere in "measured, not
    claimed."

**Not flagged:** all static/artifact claims verified verbatim; the
"eleventh species" idiom is accurate (10 live channels + `nh3:null` on
the wire right now); `/observe`→410, ledger token gating, k≥3, ~500 m
folds, no-per-trip-row schema, microenv/VE citations, holdout tables —
all hold.
