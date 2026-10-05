# Video shotlist — ≤3:00 audit of docs/plan/demo-script.md

*Cross-checked against live on 2026-10-05 ~16:30 IST (build `d08d9f74`,
task-def `alive108:142`). The stage script totals **2:50 — inside the 3:00
rule with 10 s of slack**. The AWS-console beat is non-negotiable (no
console = no score). Every beat below lists: keep/trim verdict, the drift
in its quoted numbers, and the fix.*

## Beat-by-beat verdict

| # | beat | time | verdict | notes |
|---|------|------|---------|-------|
| 1 | `/` landing — live raster + wind | 0:00–0:12 | KEEP | wind now 7.7 km/h @ 309° (was 7.3 @ 308°) — verbatim doesn't quote it ✓ |
| 2 | `/aqi` at CP | 0:12–0:30 | KEEP (tighten to ~12 s if over) | US AQI ~149 today (was ~153) — "around 150" holds ✓. Say "**about 70** fire detections" (now 71) not "70". Instruments line "two dozen" holds (24) ✓ |
| 3 | `/v2/plan` CP→Gurugram | 0:30–1:05 | **KEEP — never trim, it's the product** | Options drifted 20 → **17** warm today (dose table below). Change "twenty options" → "**around twenty**". Doses held: walk ~178–198 vs car ~5.4 → "**about 35×**" still true (~33–37×). Warm `took_ms` 382 ms today ✓ |
| 4 | `/depart` curve | 1:05–1:30 | KEEP (compress to 15 s if over) | **Basis mismatch to flag:** script quotes car (~5.5 → 44.7); default `vehicle=auto` reads 15.7 → 130.7 worst today. "~8× evening peak" holds either way — make the screen's vehicle match the narration, or say "about eight times". Lattice swing 43.5→297.9 = ~6.8× (was 6.5×) — "over six times" holds ✓ |
| 5 | `/v2/city` + `/admin` + `/community` | 1:30–1:55 | KEEP | 12 contributors / 18.1 km / 333.5 µg still exact today ✓ (aggregates move slowly — low drift risk). The "1.7× across one drive" strip number depends on field+geometry — re-verify at T-45 or say "air varies street to street — here almost twice" |
| 6 | **AWS console — ECS** | 1:55–2:20 | **KEEP — non-negotiable** | Task-def now **`:142`** (script says :141 — drifts per deploy; the line "one service, one task, healthy" is revision-agnostic ✓). Pre-signed console + CLI understudy armed per go-nogo #7 |
| 7 | `/admin` species pills | 2:20–2:40 | KEEP (first cut if over — merge into beat 5) | 95.2% coverage is file-stable ✓. "Ten pollutants, eleventh honestly empty" verified today (nh3=null) ✓. pm25↔no₂ corr r=+0.34 is recomputed per field — say "**about plus 0.3**". Edge band 19–81.5 drifts with field |
| 8 | close — pitch line | 2:40–2:50 | KEEP | — |

## Trim plan if the take runs long (cut in this order)

1. **Beat 7 → 5 s overlay.** Kill the species-pill click-through (visual
   garnish). Keep the two money lines as voiceover over beat 5's admin
   footage: "the uncertainty band is *measured* — 95.2 % coverage over
   3,550 held-out station-hours" + "the species are chemically different
   maps, not a relabeled layer." Saves ~15 s.
2. **Beat 4 → 15 s.** Keep "leave now vs tonight — about eight times
   worse" + "the city breathes on a schedule." Drop the "best hour this
   week is barely better" nuance. Saves ~10 s.
3. **Beat 6 → 15–18 s.** Console card (ACTIVE · 1/1 · Fargate) + one pan
   to Tasks. Move the DynamoDB/S3 narration over the same shot. Saves ~7 s —
   keep ≥10 s of unmistakably-console footage.
4. **Beat 5 → 18 s.** Keep contributors/km/avoided + the k≥3 line. Drop
   the single-drive 1.7× detail (it's the drift-iest number). Saves ~7 s.
5. **Beat 2 → 12 s.** Keep "two dozen live instruments + satellite model,
   kriged by our own C++ engine." Drop the countdown tick. Saves ~6 s.

Never cut: beat 3 (the dose table is the submission), beat 6 below ~10 s
(DQ rule), beat 8 (the pitch lands the name).

## Numbers that WILL drift — say ranges, not figures

| field | verified value → now | safe phrasing |
|---|---|---|
| US AQI at CP | ~153 → 149 | "around 150 — Unhealthy" |
| fire detections | 70 (16 belt) → 71 (16) | "about 70 NASA fire detections" |
| plan option count | 20 → 17 | "around twenty options" |
| mode dose spread | 33–35× → 33–37× | "about a 35-times spread" |
| model samples | 72 → 68 | don't quote; "live model grid" |
| wind | 7.3@308 → 7.7@309 | don't quote; "today's real wind" |
| city 12-h swing | 6.5× → ~6.8× | "over six times" |
| CP pm25 | 73.9/59.6 → 69.8/55.0 | don't quote; the band is on screen |
| depart worst hour | 44.7 µg (car) → 130.7 (auto) | "~8× worse" + match vehicle to screen |
| task-def rev | :141 → :142 | never quote the revision |
| build_sha | 951eeb3c → d08d9f74 | never quote |

Already drift-safe (slow movers): contributors 12, km 18.1, avoided 333.5 µg,
corridors 10/54, 95.2% coverage, 3,550 station-hours / 85 stations, edges
1,070,459/903,058, 124k gazetteer, $46/mo.

## Re-verify at T-45 (mandatory, per go-nogo #3/#12)

`curl $NLB/health` (build_sha, field_stale:false, engine:alive_core) +
`/aqi` CP once — any figure that moved outside its range gets the range
version of the line, never the stale number. The deployed build moved to
`d08d9f74`/`:142` after the script's 16:05 IST verification pass — confirm
the build you demo is the build the script header names, or re-read.
