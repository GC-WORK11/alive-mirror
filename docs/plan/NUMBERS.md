# NUMBERS.md — the canonical numbers ledger

**Every figure the product, docs, or video quotes — one ledger, one verifier.**

Run `scripts/verify_numbers.sh` to re-derive all of it live. It GETs the
endpoints (plus the one allowed `POST /v2/plan`), prints each figure's current
value beside the surfaces quoting it, and flags contradictions. Every number
below was re-derived from a live response or a committed artifact on
**2026-10-05 ~16:20 UTC**, refreshed ~19:30 UTC, then re-run ~22:15 UTC
on the **strip-bz build** (`/health` `build_sha: 80a15258` — plan/strip/
reroute now price on the breathing-zone basis, ambient ×
`smoke_modifier` = ×1.09 tonight; the modifier echoes on the `/v2/plan`
+ `/v2/reroute` wire). `/admin/api/status` not probeable without the
admin token on this pass. Earlier same-day audits: `6e82f290`,
`cb862533`, `07cadfdd`, `ad9367d5` — the churn is exactly why this file
exists). Demo-proof caveat for `verify_numbers.sh`: needs
python ≥3.12 (stock macOS 3.9 dies on an f-string) and crashes
`mid(None)` when a probed plan mode is absent (metro+walk drops after
transit service hours) — read the partial table.

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
| districts chips | **29** = 16 district rows (15 NCR + Delhi NCT) + 13 Delhi sub-areas | `GET /v2/districts` `.districts` length (re-counted 19:30 UTC) | demo-day |
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

Live reads **2026-10-06 ~11:07–11:40 UTC** (≈16:37–17:10 IST Oct 6),
build **`4eb9e1e8`** — the demo-reverify pass: `/v2/plan`, `/v2/strip` and
`/v2/reroute` price on the breathing-zone basis (`ambient ×
smoke_modifier` = ×1.24 this afternoon, echoed as `smoke_modifier` on the plan/
reroute wire). Dose µg below are bz-basis; identical ambient numbers
divide by 1.24. Ranges observed across the week are in the notes column —
quote the range, not the point.

| figure | now | observed swing | surfaces quoting it |
|---|---|---|---|
| stations live (WAQI) | **24 → 13** mid-pass (stations go stale mid-day; honest drift, recovers) | 13 (stale) ↔ 24 | README, demo-day, writeup |
| model samples | **61–72** (field rebuilt mid-pass) | ~41 cold → ~72 | demo-day, video-shotlist, writeup |
| field age | **~4–11 min** at probe | 3–14 min | demo-script, writeup |
| fires total / in-belt | **60 / 14** (belt FRP 34.0 MW) | 33 → 70 → 79 → 89 → 60 (daily) | demo-day, video-shotlist, HANDOFF |
| smoke modifier @CP | **×1.24** — **NW wind carrying tonight** | absent ↔ ×1.27 | demo-day, video-shotlist; now also on `/v2/plan`,`/v2/reroute` wire |
| PM2.5 @CP breathing / ambient | **84.9–88.2 / ~69–71 µg/m³** | 59–88 breathing | demo-script |
| US AQI @CP | **158–159** | ~150–164 | demo-script |
| wind | **4.8–5.0 km/h from 315–322°** (**NW — inside the gate, fires carrying**) | 0.6–7.3 km/h | demo-script |
| plan options (demo OD) | **20–21** this afternoon (metro+walk live — 37.5 on script OD / 43.9 on IG→HCC) | 16 → 24 (metro+walk absent after transit service hours — honest, not `degraded`) | writeup, repo-readme, demo-script |
| plan `took_ms` | **~56–660 ms warm** this afternoon (fresh unseen OD ~6.6–7.4 s server) | 0.06–1.7 s warm; 2–8 s unseen OD; one 60 km call hit the 20 s budget | demo-day, demo-script |
| **dose ladder, demo OD (mid µg, bz basis)** | car-AC **8.8** · car-open **16.1** · bike **20.3** · bus **23.1** · auto **26.2** · metro+walk **37.5** · bus-GTFS absent this read · cycle **130.0** · walk **293.2** | walk has run 190–418; car 2.9–11.8 | every surface |
| **spread walk÷car** | **33.3×** on CP→GG (slowest/best **37.4×**); IG→HCC demo OD **35.9×** (9.9 vs 355.0) | **31–45×** across ODs all week | demo-day, writeup, judges-faq, shotlist, pitch |
| annualized (landing, live-rendered) | **147 mg walk vs 4.4 mg car** | 129–182 mg vs 3.9–5.5 mg | landing.html (`mid × 2 legs × 250 days ÷ 1000`), pitch |
| `/v2/day` heavy window | **null today** — flat moderate all day (71–82) | null ↔ onset varies | writeup, repo-readme, shotlist |
| `/v2/day` cleanest window | **null today** — "no meaningful window" | null ↔ 17:30–19:30 ~94 | writeup, repo-readme |
| `/v2/day` decisions | **1 row this afternoon** (the plain-words extrema line); the `decisions:[]` wart is RESOLVED on the deployed build (`88e37d5` in `0908d9ad`+) | `[]` only on older builds | writeup, shotlist |
| `/v2/day` day mean | **75.6 µg/m³** | 63–177 | writeup, repo-readme |
| `/depart` now → worst | **20.9 → 113.2 µg (5.4×, @+63 h); best 15.5 @+47 h (−26%)** — 109 slots | 2.7–8.3× | writeup |
| `/v2/city` next_hours pm25 | **71.1 → 86.2** (mild rise into evening) | ~39 → 231 evening peak | writeup |
| `/v2/why` tonight | **stubble_smoke** primary — *"stubble smoke drifting in on the north-west wind"* — fires **claimed** (`carrying:true`: 14 belt fires / 34.0 MW, wind 315° NW inside gate → uplift ×1.24); stagnation VC ~2,485 m²/s; trend **lit** +5.4 µg/5.9 h/28 snapshots; `cannot_tell` empty | drivers swap with the weather — southerly wind flips fires back to refused | demo-day, shotlist |
| `/v2/reach` walk @25 µg | **3,105 edges / 136.1 km** | 2,150–4,200 edges | writeup, repo-readme, shotlist |
| `/v2/reach` walk @50 µg | **10,436 / 550.6 km** | 8,608–15,100 | same |
| `/v2/reach` car @25 µg | **996,064 / 93,720.8 km** (`edge_partial:true` — hit 2M cap; paints nearest 90,000) | 67,349–94,000 km | same |
| `/v2/reach` car @100 µg | (cap-pinned like @25 — same frontier class) | the 2M-state cap binds before budget does — @50/@100 converge to the same frontier | pitch, shotlist |
| corridors publishable / tracked | **12 / 54** | grows with donations | writeup, shotlist, demo-day |
| community | **22 obs all-time · 14 contributors · 725.9 µg avoided**; last 24 h: 3 obs / 4.6 km / 392.4 µg avoided | donation-dependent | writeup, demo-script |
| breath a day (mid) | **576 µg (≈1.82 cig)** | ~550–1,099 | shotlist |
| `/v2/skill` | **131 pairs — h+0..h+11 ALL graded**: h+0 MAE 2.2/+1.0 (93.4% cell / 100% hour), h+1 9.4/+6.6, h+2 18.5/+14.2, h+3 27.1 … h+11 54.5; no `thin` horizons left | grows with the archive | demo-day, shotlist |
| `/v2/outlook` today | **~76 µg/m³ mid · Moderate** (partial day) | band flips Moderate↔Poor | — |
| field archive | **21 snapshots** since 2026-10-05 20:00 IST — today 17/17 hours, 0 gaps | grows hourly | shotlist, admin |
| build_sha | **`4eb9e1e8`** on `/health` == image `alive108-api:4eb9e1e8` on task-def `:181` == `/admin/api/status` (token-probed) | wart — see below | go-nogo, demo-day |

### the build_sha wart

`/health.build_sha` and `/admin/api/status.build_sha` disagree across deploys
(the stamp is baked at a different pipeline step than the image tag). The
wart recurred across 2026-10-05's deploys (`07cadfdd`/`cb862533`
vs `ec51c882`, `c7df5db5` vs image `1e93b9f2`) but is **resolved on the
last two revisions** — `f4139b24` matched its image, and this afternoon
`4eb9e1e8` matches `/health` == image `alive108-api:4eb9e1e8` (task-def
`:181`) == `/admin/api/status` (probed *with* the token this pass). On
stage: **say the ECR
image tag**, or say "the deploy from this afternoon" — never let two
screens show two shas without knowing which is which.

---

## 3 · The derived claims, verified

### "35×" — the dose gap
`POST /v2/plan` demo OD this afternoon (build `4eb9e1e8`, breathing-zone basis):
best walk 293.2 µg ÷ best car-AC 8.8 µg = **33.3×** on the script OD
(CP→Gurugram); the demo OD (India Gate→Huda City Centre) reads
355.0 ÷ 9.9 = **35.9×**; slowest-vs-best on the script OD = 37.4×.
Earlier reads on the script OD: 33.1–33.3× (Oct 5–6), 31× (Oct 1),
38.5× on another OD. **Honest phrasing: "~35× on a Delhi commute" / "about
thirty-five times"** — the range brackets it and it's what the
claims-ledger allows. Never say a bare "35×" as if fixed.

**Does the bz basis move the ratio?** No — verified tonight, and provably:
`smoke_modifier` is a city-wide scalar applied at the dose-callable seam
(`plan.py _bz_field`), so it divides out of walk÷car exactly
(358.3÷10.8 = 328.7÷9.9 = 33.2× in either basis). What a uniform scalar
*cannot* do is change which route wins (the priced argmin is untouched).
The 33.2→33.3 drift between reads is the field moving, not the basis —
but re-derive on the morning either way: modes differ in ME·VE·t and the
ratio is a field-statement, not a constant.

### "148 mg vs 4.3 mg a year"
`landing.html` computes `mid × 2 × 250 ÷ 1000` mg from the live plan response
— "five round-trips a week for a year". With this afternoon's ladder that renders
**147 mg vs 4.4 mg** (walk 293.2, car 8.8). The 129/3.9 figure was a read
when walk ≈259 / car ≈7.8. The copy is **live-rendered so it never lies** —
but note the math reads 250 days ≈ 50 weeks, a ~4% conservative understatement
of "5 round-trips/week × 52"; fine as-is (conservative direction), just know it.

### "3,550 station-hours"
Real: `field_validation.md` headline — 3,550 station-hour pairs over 85
stations on the clean post-monsoon window. Not a live number; cite the file.

### "90,503 km reachable" / corridor "706 km"
Neither string appears in the repo — they were earlier `/v2/reach`
`distance_km` reads (auto@100 read 90,406 km; car@100 read 99,503 km
partial). This afternoon's reads (build `4eb9e1e8`): walk@25 → **136.1 km**,
walk@50 → **550.6 km**, car@25 → **93,720.8 km** (edge_partial — the 2M-state
cap binds; paints nearest 90,000).
Rule: never quote a reach km figure without
its mode+budget+timestamp — it breathes with the field.

### "~N options priced in N s"
`landing.html` line ~1086 renders `opts.length` and `took_ms` from the live
response — honest by construction. This afternoon (`4eb9e1e8`): 20–21 options,
~56–660 ms warm; fresh unseen ODs ~6.6–7.4 s server-side. Cold-start
fragility is real for GTFS transit rows — verify the
count T-45.

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
| demo-day + shotlist (demo-proof pass ~19:30 UTC, build `6e82f290`) | "~10 vs ~335 µg", "28 chips", "22 options", reach "~98 km", breath "~944 µg", skill "7 pairs / MAE 18.4 / +18.1 / 55.6%", archive "2 snapshots", "decisions:[] rides next image", "what-happened flip NOT deployed", "via Outer Circle vs Vivekanand Marg" | ~11.1 vs ~363.5 µg (32.7×), **29** chips (16 districts + 13 sub-areas), **19/20** options, reach **92.5** / 428.1 / 67,349 km, breath **997 µg (3.16 cig)**, skill **11 pairs / MAE 26.2 / +25.8 / 43.3%**, archive **6**, decisions populated (3 rows), flip **deployed** (`4ad9e0c` in `0908d9ad`+), corridors "Outer Circle–Radial 7" vs "Sansad Marg–Rafi Marg" | refreshed + stamped; **why beat added** to the admin walk + shotlist beat 4 |
| `verify_numbers.sh` itself | assumed run-anywhere | crashes on stock macOS python3.9 (f-string backslash) and on `mid(None)` when a probed plan mode is absent | documented workaround in demo-day T-45; script is code — code lane's call |
| /admin grid species layers | "all species pills paint" | verified: all 7 pills serve 100/100 cells **on the live layer** — `h=0`/`h>0` is the forecast horizon, pm2.5-only by design; NH₃ honestly empty upstream | narrate pills on the live map, never during a forecast scrub |
| `/v2/day` on `cb862533` | docs said `decisions[]` carries the story when windows are null | live returns `decisions: []` on a non-flat no-window remainder — the fallback didn't exist | **code fix**: `server/v2/day.py` `_decisions` gains a plain-words extrema line (`test_no_window_still_speaks`); NOW DEPLOYED (`88e37d5` in `0908d9ad`+) — tonight returns 3 rows |
| `/v2/trip` mode sanitizer | `_MODE_RE` allowed `a-z0-9_\- ` only | planner emits `metro+walk` — its own token got dropped (live donations show `"unknown": 2`) | **code fix**: `+` added to the class (`test_trip_mode_metro_plus_walk_survives`) |
| `/v2/trip` `switched` wire | ledger/admin count "trips switched lighter" | app sent `avoided_ug` but never `switched` — stat dead at 0 forever | **code fix**: `Mobile/src/nav/engine.ts` sends `switched` when the plan offered a real worst-dose alternative |
| fires claim (2026-10-06 demo-reverify pass) | every pass to date: `/v2/why` fires `carrying:false` — "checked and refused, wind outside NW gate" | **flipped tonight**: wind 315° NW → `carrying:true`, `drivers[0]=stubble_smoke`, modifier ×1.24 (1 + 14/160 × 2.75 — `fires.py`) | all operative "fires refused" lines updated in demo-day/shotlist/demo-script/this file |
| `/admin` flow (2026-10-06 pass) | "Open /admin (token in Secrets Manager…)" implied a token prompt | public board: no prompt on load; masthead "operator sign in" chip prompts on demand; `/admin/api/*` 401 without Bearer | demo-day.md admin flow rewritten |

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
