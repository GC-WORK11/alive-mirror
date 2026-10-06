# demo-rehearse-v2 — lane report

Mandate: `docs/lanes/demo-rehearse-v2.md`. Re-verified
`docs/plan/demo-script.md` + `docs/demo-day.md` against live
`http://65.2.28.40` on **2026-10-05 ~23:55 UTC → Oct 6 ~00:15 UTC**
(`scripts/verify_numbers.sh` + hand GETs: `/v2/why`, `/v2/skill`,
`/v2/archive`, `/v2/city` (+`/v2/city/moves`), `/v2/strip`,
`/depart?hours=120`, HTML of `/city` `/admin` `/`). GETs + `/v2/plan`
only — never POSTed elsewhere, never deployed. Python:
`server/.venv312/bin/python3` (3.12).

## Deploy rolled mid-pass — live build is now `37e55668`

Probes at ~23:55 UTC ran on **`3711ccd0`** (the app-stress deploy).
A new image deployed during the pass (`handoff.md` cont.45 +
`/health` re-check at ~00:15 UTC): **`37e55668` is now live**, which
puts `5ec1f2f` (ingest parallel fetch), `0fdd597` (ledger dedupe
removal + `/v2/trip` floors), `3aea78f` (why parallel snapshot fetch),
and `416a195` (hi i18n) on the wire. All doc figures were re-read on
`37e55668`; the drift table keeps both columns where they differ.

Schema deltas observed on `37e55668` (vs what the docs assumed):
- `/v2/day` **now requires `lat`/`lon`** — bare call 422s (docs fixed).
- `/v2/skill` horizons carry `status`/`cells`/`band_hit_pct`/
  `hour_band_hit_pct` (key names differ from an older shape).
- `/v2/city` exposes `trips.days` (per-day ledger); `/v2/city/moves`
  still serves the 7-day mode-share view (39 trips, `min_k:3`,
  `mode_share_suppressed_trips` on the wire).
- `/v2/reach` no longer returns `n_edges` on these reads (distance_km
  + `edge_partial` only).
- `/v2/plan` option rows keep `dose{lo,mid,hi,coverage,basis}` +
  `label`/`tag`/`reason_line`; `via_names` not present on these rows.

## Beat × verdict

| # | beat | verdict |
|---|------|---------|
| 1 | `/` landing — live raster + wind arrow + scrubber | **HOLDS.** Raster/`a→b`/scrubber/`whyLine` present in served HTML; wind now 3.6 km/h @171° |
| 2 | `/aqi` at CP | **HOLDS with new numbers.** US AQI 161, pm25 83.3/75.1, 24 stations + 70 samples, fires 89/22, modifier ×1.11, `engine: alive_core`, `refresh_in_s` ticking |
| 3 | `/v2/plan` compare sheet | **REWRITTEN.** 24 opts (count swung 19→24 inside minutes); walk 429.2, car-AC 12.9, metro+walk 79.5 PRESENT, GTFS "Bus 859 → UTTAMNAGAR" 144.1; warm ~610 ms; spread 33.3× (40.1× slowest/best) |
| 4 | `/depart` curve | **REWRITTEN.** now 34.4 → worst 100.6 (~2.9×, 24 h view), best 14.9 (−57%); `?hours=120` serves **109 slots** (forecast-limited) |
| 5 | `/v2/city` + `/admin` + `/community` | **REWRITTEN.** Community counters unchanged (14 contributors / 14.1 km / 477.3 µg 24 h / 725.9 all-time; 12 corridors of 54). Strip: 77 samples @250 m on the recommended row, pm2.5 69.7→90.3 = **1.30×**; SP Marg 29.5% dose-share. Caveat stands: mint strip on the *recommended* row — the `rd` engine row resolves 'unnamed road' |
| 6 | AWS console | **HOLDS** — no AWS CLI on this box; script already says "read it off the console". `/health` stamps `37e55668` |
| 7 | `/admin` field map + species pills | **HOLDS.** pills markup present; `/aqi` serves 10 params live; `nh3: null` — "eleventh honestly empty" is literal truth tonight |
| 8 | `/` close | **HOLDS** — `step_m: 250.0` on a fresh `/v2/strip` |
| — | demo-day phone flow (compare → nav → receipt → ledger → Delhi Today) | **HOLDS.** Verified in `Mobile/` HEAD + green suites + landing-lane sim runs + **apk-drive-v4 report (new tonight): `alive108-609a6ef.apk` 9/9 PASS** — designed sparse hero on Android, metro-pick→metro-nav, cold-open 1023 ms, consent-OFF pcap zero POSTs, hi zero tofu. Receipt copy ("added anonymously…" / "saved — will send when back online" / "{n} saved to send") unchanged in `strings.ts`. App surfaces not re-driven on a device this pass |

## Drifted figures (doc-says → live `3711ccd0` ~23:55 → `37e55668` ~00:15)

| figure | doc said | `3711ccd0` | `37e55668` (docs now quote this) |
|---|---|---|---|
| build_sha | `80a15258`/`951eeb3c` | `3711ccd0` | `37e55668` |
| options | 23 (16–23) | 19→24 | 24 |
| walk mid | 358.3 µg | 405.7–410.5 | **429.2** (rd 469.4) |
| car-AC | 10.8 | 12.2–12.4 | **12.9** |
| car-open | 19.6 | 22.2–22.5 | 23.5 |
| bike | 24.8 | 28.1–28.4 | 29.7 |
| bus (router) | 28.3 | 32.0–32.4 | 33.9 |
| auto | 32.0 | 36.2–36.6 | 38.3 |
| metro+walk | absent / ~40 | 81.6 | **79.5** |
| bus-GTFS | 69.3 | 147.7 | 144.1 |
| cycle | 158.8 | 179.8–181.9 | 190.2 |
| spread | 33.2× (38.7 max) | 33.1–33.3× (39.7 max) | **33.3×** (40.1 max) |
| warm plan took_ms | ~56 | 378–490 | ~610 (first hit ~8 s) |
| depart now→worst | 29.2→79.7 (2.7×) | 33.1→100.6 +89 h | **34.4→100.6 (2.9×)** |
| depart best | +12 h 14.5 | +10 h 13.9 | 14.9 |
| depart slots@120h | ~100 | 96 | **109** |
| reach walk@25 | 141.2 km | 128.7 km | **84.3 km** |
| reach walk@50 | 553.9 | 514.5 | 395.5 |
| reach car@25 | 75,822 edge_partial | 62,494 | **54,350** edge_partial |
| day windows | heavy 22:30→end @~159 | heavy 07:30–09:30 @171 (morning!) | heavy 22:30→end @160.5 |
| day mean | ~105 | 108.4 | 105.9 |
| breath | 885 µg / 2.8 cig | 1,064 / 3.4 | **1,165 / 3.7 cig** |
| next_hours | 38.8→151.1 (3.9×) | 33.7→180.4 (5.4×) | **36.8→151.6 (4.1×)** |
| city moves | 36 trips/7 d | 39/7d car 82.1% | 39/7d (3 active days) |
| fires | 79/17, 72.1 MW | 83/19, 74.1 | **89/22, 76.8 MW** |
| smoke_modifier | ×1.09 | ×1.10 | **×1.11** |
| pm25 @CP | 76.1/69.8 | 81.1/73.8 | 83.3/75.1 |
| US AQI @CP | ~158 | 160 | 161 |
| wind | 4.3 @182° | 4.2 @187° | 3.6 @171° |
| skill pairs | 21 | 35 | **34**; h+1 14.2/+11.2 (72.7/85.7%) h+2 26.3/+24.5 h+3 42.0 h+4 49.0 |
| archive | 8 snaps | 10 | 10 |
| why trend | cannot_tell | +2.8µg/2.7h, 15 snaps | **+0.3µg/5.8h, 34 snaps — history LIT** (`3aea78f` working live) |
| strip span | 1.7× | 1.23× (68.5→84.3) | **1.30×** (69.7→90.3) |

## Held (no drift)

graph 1,070,459/903,058 · stations 24 · samples 70 · corridors 12/54 ·
community 22/14/725.9+477.3 · field_validation 95.2% measured /
3,550 pairs / 85 stations · LOO 46.1/+0.3/n=94 · gazetteer
124,311+123,934 · districts 29 · step_m 250 · NH3 empty ·
`degraded` absent on healthy plan hits · `smoke_modifier` echoed on
plan · `mode_share_suppressed_trips` on the wire · receipt/queue/pill
copy unchanged · nav store suites green (68/68, 18/18).

## Timings on `37e55668` (this box → ap-south-1)

| call | server took_ms | wall |
|---|---|---|
| `/v2/plan` post-refresh first hit | ~8.0 s | ~9 s |
| `/v2/plan` warm ×2 | 610–622 ms | ~2.1–2.3 s |
| `/v2/reach` car@25 | 1,370 ms | — |
| `/v2/why` | — | 0.46 s |

"Under two seconds" for a rehearsed warm plan is honest server-side;
the first hit after a reprice lands ~8 s — the contingency row already
covers it.

## Caveats for stage

- **Never quote an exact options count** — it swung 19→24 inside
  minutes on one field reprice.
- **Strip the recommended row** (`recommended:true`), not a `rd` row.
- **`/depart?hours=120` serves ~109 slots**, not 120 — forecast-limited.
- **Day windows move with the field** — tonight saw both a morning and
  an evening peak within an hour; read the live `decisions`/`hours`.
- **`/v2/day` requires lat/lon** on the live build.
- Lane-doc path drift: the brief says `tools/verify_numbers.sh` +
  `docs/demo-script.md`; real paths are `scripts/verify_numbers.sh` +
  `docs/plan/demo-script.md`.

## Files touched

- `docs/plan/demo-script.md` — pass-4/5 stamps, beats 1–6 verbatim +
  numbers, numbers sheet, do-not-say, rehearsal log
- `docs/demo-day.md` — dated drift-note, all inline claims re-stamped
  to `37e55668`
- `docs/lanes/demo-rehearse-v2-report.md` — this file
