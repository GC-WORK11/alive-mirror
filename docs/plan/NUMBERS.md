# NUMBERS.md — the canonical numbers ledger

**Every figure the product, docs, or video quotes — one ledger, one verifier.**

Run `scripts/verify_numbers.sh` to re-derive all of it live. It GETs the
endpoints (plus the one allowed `POST /v2/plan`), prints each figure's current
value beside the surfaces quoting it, and flags contradictions. Every number
below was re-derived from a live response or a committed artifact on
**2026-10-05 ~16:20 UTC** (`/health` `build_sha: cb862533` — matching the
deployed image tag; `/admin/api/status` still stamps `ec51c882`, so the
BUILD_SHA wart is live again. Earlier same-day audit: `07cadfdd`, with
`ad9367d5` an hour before it — the churn is exactly why this file exists).

Baseline for the demo OD: **Connaught Place (28.6315, 77.2167) → Gurugram
(28.495, 77.089)** — same OD as `scripts/smoke_live.sh`.

## Reading the classes

- **`static`** — structural; only moves on a graph/corpus/artifact rebuild.
  Safe to quote verbatim.
- **`artifact`** — a number baked into a committed file (validation run,
  calibration JSON, bench log). It does not drift with the field, but it is
  only true of that artifact — keep the citation attached.
- **`drift`** — field-dependent; moves on every 15-min reprice. Quote with
  "about"/"~N"/"today reads", or stamp the read. Never pin it.
- **`wart`** — a number two surfaces legitimately disagree about; know why
  before quoting.

---

## 1 · Structural (quote verbatim)

| figure | value | derived from | quoted on |
|---|---|---|---|
| road graph edges | **1,070,459** | `route_graph.meta.json` `.edges`; `/health.routing.edges`; `/admin/api/status.routing.edges` | README, demo-day, writeup, repo-readme, demo-script, video-shotlist, landing (live) |
| road graph nodes | **819,846** | `route_graph.meta.json` `.nodes`; `/admin/api/status` (not on `/health`) | README, master-plan |
| edges priced per reweight | **903,058** | `/health.routing.edges_priced`; `/admin/api/status` | README ("903k"/"0.90M" live-rendered), demo-day, writeup, demo-script |
| reweight cadence | **≤600 s** (10 min TTL) | `/admin/api/status.routing.reweight_ttl_s` = 600.0 | README, demo-day, master-plan |
| OSM turn-ban tuples | **230** | `route_graph.bin.gz` ARG2 ban table (`nb`); `route_graph.meta.json` `.bans` | README, demo-day, master-plan, HANDOFF |
| access-override edges | **3,428** | `route_graph.bin.gz` — edges whose ARG2 access-deny byte ≠ 0 (re-counted 2026-10-05) | README, master-plan, HANDOFF |
| one-way edges | **107,193** | same blob — `e_ow` byte ≠ 0 ("~107k") | test_legality_corpus docstring |
| graph points / names | 2,324,796 / 4,450 | `route_graph.meta.json` | — |
| graph_sha | `83ef9b91051bbd29` | meta `.pbf_sha256`; `/admin/api/status.routing.graph_sha` | demo-day |
| `/grid` lattice | **484 cells** default (`cells=22` → 22×22); **1,600** at `cells=40` (landing/admin read this) | `main.py` `field_grid(cells: int = 22, le=40)` | demo-day, writeup |
| reach paint cap | **90,000 edges** | `server/v2/reach.py` `EDGE_SERVE_MAX = 90_000` | video-shotlist ("paints only the nearest 90,000") |
| reach state cap | 2,000,000 | `reach.py` `REACH_MAX_STATES` — `partial:true` on big budgets means it hit this | — |
| districts chips | **28** = 15 NCR districts + 13 Delhi sub-areas | `GET /v2/districts` `.districts` length | demo-day |
| reach presets | modes walk/cycle/auto/car × budgets 25/50/100 µg | `/city` frontend presets | — |
| species served | 10 channels (pm25, pm10, no₂, o₃, co, so₂, nh₃, dust, aod, us_aqi) — **nh₃ honestly empty today** | `/aqi` keys | demo-script |
| cigarettes constant | **316 µg PM2.5 ≈ 1 cigarette** (Berkeley Earth) | `server/v2/city.py`, Mobile `theme.ts` | README, copy-r4 |
| dose sampling stride | ~250 m along polyline | dose code path | demo-day |
| corridor privacy window | k≥3 riders, 72 h window | `admin_agg` `CORRIDOR_WINDOW_S=72*3600`, `k_min=3` | writeup, demo-day |
| history stations | **125** stations in climatology | `/health.history.stations`; `delhi_climatology.json.gz` `.stations` | writeup, repo-readme |
| gazetteer rows | **124,311** bundled on-device (`Mobile/assets/delhi-gazetteer.json`) / **123,934** server-side copy (`server/data/delhi-gazetteer.json`, the deployed fallback) | file lengths, both counted | README (stale 124,334 → fixed), demo-day, master-plan |
| corpus entries | **97,447** incl. **16,949** address rows | `server/data/corpus/STATS.md` | README, master-plan, demo-day |
| search acceptance | 67/67 fixed queries top-3 | `tests/search_queries.txt` + `STATS.md` | README |
| forecast horizon | **120 h** (outlook `horizon_days` 5 / `horizon_hours` 101 served) | `/v2/outlook`, forecast code | demo-day, writeup |
| field refresh | **900 s** TTL, stale after 2,700 s | `field.py` | demo-day |

### committed-artifact figures (cite the file, don't drift)

| figure | value | artifact |
|---|---|---|
| held-out validation | **3,550 pairs / 85 stations**: MAE **22.0**, RMSE **29.3**, bias **+15.5 µg (+51.6%)** | `server/data/field_validation.md` headline |
| σ-band coverage | **95.2% measured vs 95.4% nominal** @ ±2σ (median \|err\|/σ = 0.94) | same file |
| LOO live-instrument calibration | MAE **46.1 µg/m³**, bias **+0.3**, n=**94** stations | `server/data/field_calibration.json`; also served live in `/aqi.calibration` |
| "9M station-hours" | build-log count from `history_builder.py` (`nrows`) — **not re-derivable from the committed quantile artifact**; the honest line is "125 stations × 10 years of archive, medians by month×hour" | `delhi_climatology.json.gz` |
| benches (C++ vs Python) | search ~88× p50 · dose ~13× p50 · emission ~3.3× · lookups ~6.8× | `docs/plan/bench-results.md` — static artifact, re-runnable via `tools/bench_*.py` |
| cost | ~$46/mo worst case; ~$36 event window | `docs/18*` — artifact estimate |

---

## 2 · Drift-prone (re-check T-45; never pin)

Live reads **2026-10-05 ~16:20 UTC**, build `cb862533`. Ranges observed across
the week are in the notes column — quote the range, not the point.

| figure | now | observed swing | surfaces quoting it |
|---|---|---|---|
| stations live (WAQI) | **24** | 16 (cold task) → 24 | README, demo-day, writeup |
| model samples | **71** | ~41 cold → ~72 | demo-day, video-shotlist, writeup |
| field age | **~14 min** (825–831 s) | 3–14 min | demo-script, writeup |
| fires total / in-belt | **79 / 17** | 33 → 70 → 79 (daily) | demo-day, video-shotlist, HANDOFF |
| smoke modifier @CP | **×1.09** | absent ↔ ×1.27 | demo-day, video-shotlist |
| PM2.5 @CP breathing / ambient | **85.2 / 78.1 µg/m³** | 59–85 breathing | demo-script |
| US AQI @CP | **163** | ~150–163 | demo-script |
| wind | **3.1 km/h from 126°** | 0.6–7.3 km/h | demo-script |
| plan options (demo OD) | **22** | 16 → 20 → 22 (transit rows drop on cold GTFS) | writeup, repo-readme, demo-script |
| plan `took_ms` | **~1,700 warm / ~6,100 cold** | 0.5–1.7 s warm; 2–8 s unseen OD; one 60 km call hit the 20 s budget | demo-day, demo-script |
| **dose ladder, demo OD (mid µg)** | car-AC **10.1** · car-open **18.3** · bike **23.2** · bus **26.4** · auto **29.9** · metro+walk **38.7** · bus-GTFS **60.8** · cycle **148.3** · walk **334.6** | walk has run 190–360; car 2.9–11.7 | every surface |
| **spread walk÷car** | **33.1×** (slowest/best **35.6×**) | **31–45×** across ODs all week | demo-day, writeup, judges-faq, shotlist, pitch |
| annualized (landing, live-rendered) | **167 mg walk vs 5.0 mg car** | 129–167 mg vs 3.9–5.0 mg | landing.html (`mid × 2 legs × 250 days ÷ 1000`), pitch |
| `/v2/day` heavy window | **null tonight** — rising evening remainder, no ≥2 h run either side | null ↔ onset 21:30–22:30; peak 105–247 | writeup, repo-readme, shotlist |
| `/v2/day` cleanest window | **null tonight** | null ↔ 17:30–19:30 ~94 | writeup, repo-readme |
| `/v2/day` decisions | **`[]` on build cb862533** when both windows are null (plain-words extrema fallback fixed in code, rides next image) | — | writeup, shotlist |
| `/v2/day` day mean | **90.2 µg/m³** | 90–177 | writeup, repo-readme |
| `/depart` now → worst | **29.8 → 92.1 µg (3.1×)** | 3.1–8.3× | writeup |
| `/v2/city` next_hours pm25 | **79.0 → 195.4** | ~76 → 231 evening peak | writeup |
| `/v2/reach` walk @25 µg | **2,293 edges / 98.1 km** | 2,293–4,200 edges | writeup, repo-readme, shotlist |
| `/v2/reach` walk @50 µg | **8,927 / 448.8 km** | 8,927–15,100 | same |
| `/v2/reach` car @25 µg | **835,831 / 69,527 km** (partial — hit 2M cap; paints nearest 90,000) | 69,527–94,000 km | same |
| `/v2/reach` car @100 µg | 1,029,263 / 99,503 km (partial) | the 2M-state cap binds before budget does — @50/@100 converge to the same frontier | pitch, shotlist |
| corridors publishable / tracked | **10 / 54** | grows with donations | writeup, shotlist, demo-day |
| community ledger | 24 h: **4 obs / 12.9 km / 137.3 µg avoided** · all-time: **19 obs / 12 contributors / 333.5 µg avoided** | drifts with donations | writeup, demo-script, admin |
| breath a day (mid) | **944 µg (≈2.99 cig)** | ~550–944 | shotlist |
| `/v2/outlook` today | **90.2 µg/m³ mid, Moderate** (heavy hour ~23:30 IST) | band flips Moderate↔Poor | — |
| field archive | **2 snapshots** since 2026-10-05 20:00 IST (hours 20,21 recorded; 0–19 honest gaps) — grows hourly | — | shotlist, admin |
| build_sha | **`cb862533`** on `/health`; `/admin/api/status` reads `ec51c882` — wart is live | wart — see below | go-nogo, demo-day |

### the build_sha wart

`/health.build_sha` and `/admin/api/status.build_sha` disagree across deploys
(the stamp is baked at a different pipeline step than the image tag). Today
`/health` says `07cadfdd`. On stage: **say the ECR image tag**, or say "the
deploy from this afternoon" — never let two screens show two shas without
knowing which is which.

---

## 3 · The derived claims, verified

### "35×" — the dose gap
`POST /v2/plan` demo OD tonight: best walk 334.6 µg ÷ best car-AC 10.1 µg =
**33.1×**; slowest-vs-best = 359.9 ÷ 10.1 = 35.6×. Earlier reads on this OD:
33.2× (Oct 5 afternoon), 31× (Oct 1), ~33–35× (Oct 5 am), 32.7× and 38.5× on
two other ODs. **Honest phrasing: "~35× on a Delhi commute" / "about
thirty-five times"** — the range brackets it and it's what the claims-ledger
allows. Never say a bare "35×" as if fixed.

### "148 mg vs 4.3 mg a year"
`landing.html` computes `mid × 2 × 250 ÷ 1000` mg from the live plan response
— "five round-trips a week for a year". With tonight's ladder that renders
**167 mg vs 5.0 mg** (walk 334.6, car 10.1). The 129/3.9 figure was a read
when walk ≈259 / car ≈7.8. The copy is **live-rendered so it never lies** —
but note the math reads 250 days ≈ 50 weeks, a ~4% conservative understatement
of "5 round-trips/week × 52"; fine as-is (conservative direction), just know it.

### "3,550 station-hours"
Real: `field_validation.md` headline — 3,550 station-hour pairs over 85
stations on the clean post-monsoon window. Not a live number; cite the file.

### "90,503 km reachable" / corridor "706 km"
Neither string appears in the repo — they were earlier `/v2/reach`
`distance_km` reads (auto@100 read 90,406 km; car@100 tonight 99,503 km
partial). Tonight's reads: walk@25 → **98.1 km**, walk@50 → **448.8 km**,
car@25 → **69,527 km** (partial). Rule: never quote a reach km figure without
its mode+budget+timestamp — it breathes with the field.

### "~N options priced in N s"
`landing.html` line ~1086 renders `opts.length` and `took_ms` from the live
response — honest by construction. Tonight: 22 options, ~1.7 s warm (~6.1 s
server-side right after a reprice, ~9.5 s wall over the NLB). Cold-start
fragility is real for GTFS transit rows — verify the count T-45.

---

## 4 · Contradictions found & fixed (this pass)

| surface | said | truth (live/file) | fix |
|---|---|---|---|
| README L78 | "MAE 47.1, bias +45.1" citing `field_validation.md` | MAE **22.0**, bias **+15.5 (+51.6%)** | corrected to file |
| README L94 | "+150.6% bias on the validated window" | **+51.6%** | corrected |
| README L17 | gazetteer "124,334 rows" | bundle **124,311** (server copy 123,934) | corrected to 124,311 |
| README L92 | "stations are offline until the key lands" | **24 WAQI stations live** | rewrote — WAQI live; OpenAQ key still pending |
| demo-day L73 | "~33× today — 5.7 vs 189.7 µg" | **7.8 vs 258.8 µg (~33×)** | refreshed pair + "re-check T-45" |
| demo-day L86-87 | "~70 fires … ×1.27 at CP" | **79 fires (17 belt), ×1.09 at CP** | refreshed |
| video-shotlist L69-75 | reach "~4,200 edges/187 km; ~15,000/880 km; ~94,000 km" | **3,020/131.5; 10,756/576.1; 958k/86,879 (partial)** | refreshed the drift table |
| writeup + repo-readme | "16 options", ladder 5.7–189.7, day "~247/~94/~177", depart "~17/~104 ~6×", reach "2,473/107 km; 9,524/490 km; ~580k/39,500 km" | today's values (see §2) | refreshed + stamped "measured 2026-10-05" |
| master-plan L15 | "16,952 address rows", "124,334-row gazetteer" | **16,949** / **124,311** | corrected |
| judges-faq L32 | "walk ~190–212 µg / car ~6 (~33×)" | **~259 / ~8 (~33× today)** | refreshed |
| HANDOFF.md / plan/handoff.md | dated session logs ("33 fires", "101.2 µg median") | point-in-time records | left — dated logs are snapshots, not claims |
| demo-day L73 + shotlist beats 3–4 (refresh pass 2026-10-05 ~16:20 UTC, build `cb862533`) | "7.8 vs ~259 µg", options "16–20", reach "~131 / ~576 / ~86,879 km", breath "~735 µg", day windows "~22:30→end ~122, lightest 68, mean 103" | ~10.1 vs ~334.6 µg (33.1×), **22** options, reach 98.1 / 448.8 / 69,527 (car@100 → 99,503) km, breath **944 µg**, both windows **null** (rising evening — no ≥2 h run), mean 90.2 | refreshed to live + stamped |
| `/v2/day` on `cb862533` | docs said `decisions[]` carries the story when windows are null | live returns `decisions: []` on a non-flat no-window remainder — the fallback didn't exist | **code fix**: `server/v2/day.py` `_decisions` gains a plain-words extrema line (`test_no_window_still_speaks`); rides the next image |
| `/v2/trip` mode sanitizer | `_MODE_RE` allowed `a-z0-9_\- ` only | planner emits `metro+walk` — its own token got dropped (live donations show `"unknown": 2`) | **code fix**: `+` added to the class (`test_trip_mode_metro_plus_walk_survives`) |
| `/v2/trip` `switched` wire | ledger/admin count "trips switched lighter" | app sent `avoided_ug` but never `switched` — stat dead at 0 forever | **code fix**: `Mobile/src/nav/engine.ts` sends `switched` when the plan offered a real worst-dose alternative |

---

## 5 · Phrasing rules

1. **Static figures**: quote verbatim, cite source.
2. **Drift figures**: "about", "~N", "today reads N", or a range. On camera,
   say "about a thirty-five-times spread" — the 31–45× band keeps you honest.
3. **Artifact figures**: always carry the citation; they describe one
   measured window, not the field right now.
4. **Never** let a doc state a drift number as if it were a constant without
   a timestamp or a tilde.
5. On stage: `scripts/verify_numbers.sh` output beats this file. Re-run at
   T-45 and read the live column.
