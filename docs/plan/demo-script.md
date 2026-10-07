# ALive-108 — demo-day stage script (≤3:00) — v2

*Verified end-to-end against the live service **2026-10-05, 16:05–16:50 IST**
(build `951eeb3c`, ECS `ap-south-1`, task-def `alive108:141`, FARGATE_SPOT,
deployment COMPLETED — confirmed via `aws ecs describe-services`).
Dose model is the re-anchored one (walk/auto ME 1.30, seated VE 10.0–10.5) —
numbers below replace the pre-re-anchor pass.*
*Re-rehearsed 2026-10-05 ~23:55 UTC → Oct 6 ~00:15 UTC on live build
`37e55668` (a deploy rolled mid-pass — earlier reads were on `3711ccd0`;
figures below are the newest build's). Every verbatim re-phrased to
tonight's reads (walk ~430, metro+walk ~80, depart worst ~100); see
Passes 4–5 in the rehearsal log and
`docs/lanes/demo-rehearse-v2-report.md`.*
*demo-day-final re-verify 2026-10-06 ~05:10–05:30 UTC on live build
**`f4139b24`** (the persistence-blend deploy — the forecast now carries a
fitted nowcast blend on the wire; image tag == `build_sha`). Beats and
the numbers sheet re-phrased to this morning's reads (walk ~359 on the
script OD / ~430–450 on the India Gate→Huda demo OD, depart worst ~103,
skill 80 pairs); see Pass 6 in the rehearsal log and
`docs/lanes/demo-day-final-report.md`.*
*demo-reverify-v2 2026-10-06 ~11:07–11:40 UTC on live build
**`4eb9e1e8`** (task-def `:181`; `/health` == image == `/admin/api/status`
token-probed). **Fire story flipped**: `/v2/why` now claims stubble smoke
(NW wind 315° inside the gate, 14/60 belt fires, modifier ×1.24) — the
stage verbatim still works but the fires aside is now "carrying", not
"refused". Numbers sheet re-phrased to this afternoon's reads (walk ~293
on the script OD / ~355 on IG→HCC, day windows null — flat moderate,
skill 131 pairs all horizons graded, archive 21 snapshots); see
`docs/lanes/demo-reverify-v2-report.md`.*
*submission-sync re-pin 2026-10-07 ~11:00 UTC on live build **`698cf808`**
(the ship wave: cinematic route chooser `e2ff634` — folded into beat 3
below — `cause_note` parali-watch `795ff3b`, admin sign-in `b563da2`,
map depth `b47ffd4`, iOS residual kill `9fbd851`, codebase-truth
`1627a13`/`b633a2d`, landing v6, deploy.sh verified ×2). **Fire story
flipped back to refused**: SW wind → `carrying:false`, ×1.06 — and
`/v2/why` now also serves `cause_note` (the parali-watch line); trend
primary today (−13.7 µg/5.8 h). **`/admin` now opens on a gate card —
sign in via `POST /v2/admin/login` at T-30, never paste the token on
camera.** Numbers sheet re-pinned to this morning's reads (walk ~238
script OD / ~255 demo OD, 17/16 opts, skill 304 pairs, community
44/24/1,278.9).*
Every number below was read off the wire during rehearsal — most twice,
across a field refresh, so the drift is documented. Numbers marked ⟳
**drift** — the verbatim lines are phrased to survive it ("about",
"over", "under"), and the T-45 `curl $NLB/health` re-read is mandatory.
Nothing here is seeded or faked.*

`NLB = http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com`

---

## Beats (total 2:50, 10 s of slack)

| # | time | on screen | say this (verbatim) | verified number behind it |
|---|------|-----------|---------------------|---------------------------|
| 1 | 0:00–0:12 | `/` landing — live raster + wind arrow | "Delhi's air has a price per street. What you're looking at isn't a video — it's the live pollution field over NCR, right now — the arrow is today's real wind, and this scrubber walks the next twelve hours of it." | landing canvas = real `/grid` cells on true NCR geography · wind arrow ~5 km/h @ ~315° (NW — drifts) · '▶ watch the day' scrubs real `/grid?h=0..12` forecast surfaces ⟳ |
| 2 | 0:12–0:30 | `/aqi` at Connaught Place | "US AQI in the 150s — Unhealthy — built minutes ago from fifty-two live instruments blended with a satellite model, kriged by our own C++ engine, with about forty NASA fire detections feeding a smoke modifier. And this is a countdown — the field refreshes on a 15-minute heartbeat you can watch tick." | us_aqi **154** today at CP, pm2.5 breathing **64.5** / ambient **60.8** (LOO calibration 8.8/12.7/70/+0.2 on the wire), stations **52 — WAQI + DPCC both `ok`** (`source:"waqi+dpcc"`, drift band 52–54) + **~97** CAMS/model samples, fires **44** today (12 belt, 26.2 MW, modifier **×1.06 — SW wind, refused**; ×1.24 NW-carrying at the Oct-6 read), `engine: alive_core`, field age ~7 min at probe, `refresh_in_s` observed counting down ⟳ |
| 3 | 0:30–1:05 | `/v2/plan` India Gate → Huda City Centre compare sheet — **the cinematic route chooser now runs this beat** (`e2ff634`, live since Oct 7: let it play — candidates draw as equals, camera fits them all, the winner settles bold ~1.5 s in, and the verdict pill pins the server's own reason line: "cleanest · N% less than fastest". The judge types "huda city centre"; it resolves to the metro station; the old CP→Gurugram script OD kept as backup) | "India Gate to Huda City Centre — about twenty options in under two seconds — watch them draw as equals before the winner settles and names why. All 1.07 million road edges were re-priced off that live field. Same road, same minutes: on foot you inhale about two hundred and fifty micrograms; in an auto, about twenty-three; metro plus walk — when the trains are running — about fifty — and here's the honest surprise: a sealed AC car at about seven beats the metro, because the clean coach is bookended by road-level walks. That's more than a thirty-times spread the map you use today never tells you." | **demo OD reads (re-pinned Oct-7 ~11:00 UTC, live build `698cf808`):** 16 opts on the warm hit (a cold post-refresh hit served 9 + `degraded:["engine"]` — narrate the honesty if it happens; count drifts 9–24), car-AC **7.4**, walk **255.0** → **~34.5×**; **metro+walk 53.2 present** (car beats it ~7.2×); auto 22.8, bus 19.4, bike 17.7, car-open 13.5, cycle ~113; warm `took_ms` ~1.2 s (the fresh hit ~9.2 s server — reprice); edges 1,070,459 (903,058 priced); dose `coverage: 1.0`; alternates measured **96%/55%/19% divergent** (spec ≥15%, earlier field); script-OD CP→GGN backup read same pass: 17 opts, car-AC **7.2** / walk **237.9** → **33.0×**, **metro+walk 32.5 present** ⟳ |
| 4 | 1:05–1:30 | `/depart` curve (the app's window is the next **24 h** — quote what's on the curve, not the old 4-day numbers) | "When you leave matters as much as how. Same trip now: about twenty micrograms. This curve is that same trip re-priced for every departure hour — it climbs overnight; by tomorrow morning's rush it runs more than twice the easy hour. The city breathes on a schedule — the lattice itself swings a third across the next twelve hours — and the same forecast reaches about four days out, blended onto the live field where the observation is freshest." | **24 h window on the demo OD, car (live `698cf808`, Oct-7 ~11:05 UTC):** now **20.7** → overnight climb to worst **45.2 @+19 h** (tomorrow ~06:00 IST, ~2.2×); dip **17.3 @+23 h** — `pct_less_vs_now` **16** → the leave-later row IS present on the demo OD today (gate >8; it reads 0 — absent — on the script OD: honest per-trip behaviour, re-check T-45). `live_anchor.blend` served on the wire: the 'beats persistence' claim is EARNED pooled on the fitted night, strictly better h+5+; inside the 2 h hold it IS persistence — say "blended onto the live field", never "beats persistence" flat; `/v2/city.next_hours` swing **60.8→78.2 (~29%)** today ⟳ |
| 5 | 1:30–1:55 | `/v2/city` + `/admin` + `/community` | "Every donated trip becomes a live sensor. Twenty-four contributors have logged about thirty kilometres in the last day — the engine counts over three hundred micrograms of smoke they didn't breathe in that window, almost thirteen hundred all-time. And the air varies street to street: along this one drive the field runs from about fifty-two to about eighty-six — and one expressway stretch carries nearly a third of the trip's dose. Streets only publish after three different riders cross them; the privacy is in the math." | contributors **24**, km_today **31.4**, avoided_ug_all **1,278.9** (today 312.9), obs **44** (5 today); 12 of 55 corridors publishable on the wire today; strip numbers re-mint on the day — mint the strip on the tagged *recommended* row (the least-smoke `rd` engine row resolves to 'unnamed road'); `/v2/city/moves` 44 trips, suppression field live; `/admin` now opens on the **gate card** — sign in at T-30 (`POST /v2/admin/login` → HttpOnly cookie ~8 h; Bearer kept for ops curls) ⟳ |
| 6 | 1:55–2:20 | **AWS console** — ECS `alive108` service | "Real infrastructure, not a laptop demo: ECS Fargate in Mumbai behind a Network Load Balancer — one service, one task, healthy, Spot-priced. CodeBuild ships every deploy, DynamoDB holds only aggregates, S3 keeps the last good field snapshot. Net zero billed this week inside the event credits." | `describe-services` ACTIVE · 1/1 · FARGATE_SPOT · rollout COMPLETED; `/health` `build_sha` `698cf808` == image `alive108-api:698cf808` (ECR tag is truth — read the live task-def off the console, never a memorized revision); ops account 185708268748: 3 CloudWatch alarms OK + SNS confirmed + $0.00 net/7d (ops-handover) ⟳ |
| 7 | 2:20–2:40 | `/admin` field map — species pills | "We hold one rule: no fake precision. The uncertainty band is *measured* — 95.2 percent coverage at two-sigma over 3,550 held-out station-hours across 85 stations. Ten pollutants ride the same lattice — an eleventh, ammonia, is honestly empty today — and they're chemically different maps: PM2.5 and NO₂ correlate at only plus point-one-four. Click NO₂, the pattern changes; it's not a relabeled layer. Far from a sensor the band honestly widens; outside Delhi it refuses to answer." | band coverage **95.2% @±2σ / 3,550 held-out h, 85 stations** (field_validation.md); 10 species live today (ammonia param served but empty); pm25↔no₂ cell corr **r=+0.14 today** (484 cells — was +0.55/+0.34 at prior reads; it drifts); us_aqi grid range drifts (91→166 at the last pinned read); edge band 10.7–97.7 at 11.1 km (NE corner — widens with distance); Mumbai → typed `outside_service_area` |
| 8 | 2:40–2:50 | back to `/` | "Exposure and emissions, measured end-to-end — dose every 250 metres for the rider, emissions per mode for the city. ALive-108 — the map that prices the air." | `step_m: 250.0` live on `/v2/strip`; pitch per docs/demo-day.md |

## The AWS console moment (required — no console, no score)

**Primary:** ECS console, already signed in, pinned tab —
`https://ap-south-1.console.aws.amazon.com/ecs/v2/clusters/alive108/services/alive108/health`
(service card: ACTIVE, running 1/1, Fargate). Pan to **Tasks** if they linger.
Task definition family `alive108`, live revision **:181** today.

**CLI understudy (verified live 2026-10-05):**

```bash
AWS_DEFAULT_REGION=ap-south-1 \
aws ecs describe-services --cluster alive108 --service alive108 \
  --query 'services[0].{status:status,running:runningCount,taskDef:taskDefinition,capacity:capacityProviderStrategy}'
```

→ `ACTIVE · 1/1 · alive108:181 · FARGATE_SPOT`. Do **not** log in live on stage.

## Contingency beats

| If this stalls | do this on stage |
|---|---|
| `/v2/plan` > ~4 s | Engine re-pricing after a field refresh — wait ~12 s once, never spam; rehearsed OD lands warm in ~0.6 s. Rehearse on the SAME OD you'll demo (fresh unseen ODs measured 2.3–6.7 s server-side; one 60-km cold call hit the 20 s planner budget → honest `options:[] + error:"planner timed out"`). `python3 tools/warm_task.py` at T-40 is load-bearing. |
| `degraded:["engine","transit"]` on the wire | Narrate it: "the API names which arm timed out — we'd rather show a missing arm than a fabricated answer." Router rows still render. |
| Any endpoint > 8 s twice | Cut to pre-recorded ride video (docs/demo-day.md backups); keep narrating — numbers were live-verified today. |
| `/health` `field_stale:true` | Say it tells the truth; read the real age aloud. |
| Hall Wi-Fi dead | Phone hotspot (NLB is HTTP :80 only; captive portals break it). Bundled 124k-row gazetteer keeps search alive offline. |
| Numbers drifted since morning | They will — the field refreshes every 15 min. Quote the ranges ("mid-160s", "over 200", "about 6"); the drift column below shows the observed swing. |

## Numbers sheet (re-pinned 2026-10-07 ~11:00 UTC on `698cf808`; prior passes' drift kept for swing context)

**Field & air**
- engine `alive_core` · routing **1,070,459 edges / 903,058 priced** · `osrm-local` router (self-hosted, ~15 ms)
- field: **~97** model samples today · **52** instruments — **WAQI + DPCC both `ok`** (`source:"waqi+dpcc"`, drift band 52–54; stations drift stale mid-day, recover) · age ~7 min (TTL 900 s) · `stale:false` · `refresh_in_s` visibly counting down on the wire · history.stations_climatology **125**
- fires: **44** today (12 in-belt, 26.2 MW), FIRMS public CSV · smoke modifier **×1.06** at CP (SW wind — **refused** today; **×1.24 NW-carrying at the Oct-6 read** — echo on `/v2/plan`+`/v2/reroute`) · wind ~9.9 km/h from ~241°
- CP now: pm2.5 **64.5** breathing / **60.8** ambient · **US AQI ~154** today · LOO calibration MAE 8.8 / RMSE 12.7 / n=70 / bias +0.2 · GRAP-indicative stage 0 · vs decade norm for the hour at CP (name the basis)
- city: pm25 mean **43.2** / median 43.3 / max 55.0 · typical Oct median 56.9 (**−24.0%**) · GRAP stage 0, aqi 73 · next-12h swing **60.8→78.2 (~29%)** — a mild day, don't quote the old ~4×
- outlook @CP: today Moderate 67.5 → **Thu Poor ~107** → **Fri–Sun Very Poor ~135–177** (confidence "lo" — say the shape, not the digits); cleanest windows Sat ~10:30–18:30 ~77, Sun ~10:30–16:30 ~64
- breath: day-inhaled **~620 µg mid ≈ 1.96 cigarettes** (22 µg/m³-day ≈ 1 cig, ~14.4 m³/day — scales with the day's field mean; evening reads ran ~2.5–3.7 cig this week)
- `/v2/day` @CP: day_mean **67.5** · both windows honestly `null` (flat moderate 61–75) · `decisions` carries the plain-words row

**Routing & dose**
- **demo OD India Gate→Huda City Centre (24.7 km — the OD the judge flow types; re-pinned Oct-7 ~11:00 UTC on `698cf808`):** **16 options** on the warm hit (a cold post-refresh hit served 9 + `degraded:["engine"]`; the count swings 9–24 across reads minutes apart), warm `took_ms` **~1.2 s** (fresh-OD hit ~9.2 s server — reprice; one 60-km cold call timed out at the 20 s budget → honest empty) · doses: car-AC **7.4** · car-open 13.5 · bike 17.7 · bus 19.4 · auto 22.8 · **metro+walk 53.2 PRESENT** · cycle ~113 · **walk 255.0 µg → ~34.5× car** · script OD CP→Gurugram (23.7 km) backup: 17 opts, car-AC **7.2** / walk **237.9** → **33.0×**, metro+walk 32.5 present
- **µg/km ladder** (demo-OD reads ÷ 24.7 km): car-AC ~0.3 · car-open ~0.5 · bike ~0.7 · bus ~0.8 · auto ~0.9 · metro+walk ~2.2 · cycle ~4.6 · **walk ~10**
- **the honest surprise**: metro+walk ≈ **7.2× car-AC** dose on the demo OD today (53.2 vs 7.4; ~4.5× on the script OD, 32.5 vs 7.2) — GTFS ride is clean, road-level access walks aren't. It's GTFS-service-hours dependent — if the row is absent at T-45 the clause dies with it
- **the route chooser (`e2ff634`)**: candidates draw as equals (≤3, staggered 220 ms) → camera unions all bounds → winner settles bold ~1.4–1.7 s → verdict pill pins `chooserVerdict` (the server's `reason_line` verbatim — "cleanest and fastest" / "cleanest · N% less than fastest") at `pointAtFrac(geometry,0.45)`, hold 4.2 s
- corridor alternates measured divergent: alt1 **96%**, alt2 **55%**, rd **19%** of length (spec: ≥15%) — real different routes
- per-street air on one trip (strip, `step_m` 250): re-mint on the day — last pinned 82 samples · 52.2→85.9 (1.65×) on `4eb9e1e8` · **mint strip on the tagged recommended row — least-smoke `rd` engine rows resolve to 'unnamed road'**
- emissions: car CO₂ 1.8–5.2 kg (mid 2.82) + PM2.5 tailpipe up to 3.18 g · metro+walk 0.42 kg CO₂, **zero PM** · curve params (`co2_g_km`, idle, cold-start) served for client-side 1 Hz ticking
- other ODs (earlier-field, ambient-basis reads — the ratios hold on the bz basis, re-mint absolutes on the day): India Gate→Noida car 2.4 vs walk 78.4 (**32.7×**, 24 opts); KG→Faridabad car 6.5 vs walk 250.0 (**38.5×**, 21 opts — first cold call timed out at 20 s, retry answered in 6.7 s); CP→India Gate walk 47.5 µg on 4.7 km (car 1.5, metro+walk 15.7) — the spread holds, the factor doesn't (say "30–40×")

**Search & corpus**
- corpus truth (STATS.md): **91,931,396 OSM nodes + 8,888,227 ways scanned → 97,447 entries, 16,949 real address rows** (house numbers + interpolations) · app bundles **124,311-row gazetteer** → offline search
- battery of 174 real Delhi queries live: **172/174 top-1 (98.9%), p50 471 ms / p95 704 ms / max 1.5 s** over NLB · misses: '25 rajinder nagar' (→ '25-K Rajinder Nagar' substring artefact), 'panipat' (honest empty — outside coverage) · the 25-query stage subset still lands 25/25 · engine itself ~1 ms C++

**Honesty**
- band coverage **95.2% @±2σ over 3,550 held-out station-hours, 85 stations** (`σ=√(krige_sd²+(0.12·µ)²) × SIGMA_CAL 3.2`; MAE 22.0, bias +51.6% on clean-air window — source: `server/data/field_validation.md`)
- LOO calibration: MAE **8.8 µg/m³**, bias **+0.2**, n=70 live WAQI+DPCC instruments (krige refit per held-out station — served live at `/aqi.calibration`)
- grid confidence: hi 33% / med 62% / lo 4% — thin cells paint honest (drifts a few pts with the field)
- edge /aqi 11.1 km from nearest sample (NE corner): band widens 10.7–97.7 · Mumbai → typed `outside_service_area`, zero fabricated route · in-bounds budget timeout → `options:[] + error:"planner timed out"`, degraded arm named
- `/community`: **44 obs · 24 contributors · 31.4 km today · 1,278.9 µg avoided all-time (312.9 today)** · corridors publish only at k≥3 devices — suppression mechanism on the wire (`mode_share_suppressed_trips`)
- self-grade (`/v2/skill`): **304 pairs** — h+0 MAE 3.8 / band-hit 90.2% → h+11 MAE 37.2 / 37.7% (hour_band_hit 47.8%; error widening honestly with horizon)
- why (`/v2/why`): **trend primary today** (−13.7 µg over 5.8 h, 33 recorded builds); **`cause_note` live since `795ff3b`** — *"12 fires in the Punjab–Haryana belt — the wind isn't carrying it this way right now · city mean 60.6 → 46.8 µg/m³ over 5.8 h"* — fires evaluated 44/12 belt/26.2 MW but SW wind → `carrying:false`, refused (a NW day flips it back to claimed); VC ~3,468 vs ~3,000 typical; `cannot_tell` empty. Re-check `curl $NLB/v2/why` on the day
- archive: today recorded [1,3–16] · honest gaps {0,2} · pending 17–23 (grows hourly — dozens by demo morning)
- reach: walk@25 **3,767 edges / 167.9 km** · walk@50 11,409/618.0 km · car@25 **993,344/92,805.9 km `edge_partial:true`** (cap-pinned — say "the whole priced graph")
- forecast blend: `live_anchor.blend` on the plan/depart wire (w=1 → h+2, linear→0 at h+40, w_h11 0.763, fitted on served-vs-recorded archive pairs 2026-10-05/06 IST) — 'beats persistence' is EARNED pooled on the fitted night (blend 11.2 < persistence 13.1 < pre-blend model 39.2 µg/m³), strictly better h+5+; inside the 2-h hold it IS persistence by construction — phrase it "blended onto the live field", never a flat "beats persistence"
- `/v2/city/moves`: **44 trips · 12 of 55 corridors publishable** · min_k 3 on the wire
- `/v2/outlook` @CP: today Moderate 67.5 → **Oct-8 Poor 107.2 → Oct-9 Very Poor 176.9 → Oct-10 134.1 → Oct-11 136.8** (Fri–Sun confidence "lo"); cleanest windows Sat 10:30–18:30 ~77.5, Sun 10:30–16:30 ~64.3
- admin sign-in (`b563da2`): `POST /v2/admin/login` → `alive_admin=v1.<exp>.<sig>` HttpOnly+SameSite=Strict cookie, 8 h, Secure-on-TLS · login bucket (0.2,5) · sessionStorage token + prompt() deleted · guests land on a gate card · Bearer kept for ops curls

**AWS**
- ECS `alive108` ACTIVE · running 1/1 · FARGATE_SPOT (weight=1, base=1) · rollout COMPLETED; image `alive108-api:698cf808` == `/health` `build_sha 698cf808` — task-def revision rides the deploys, read it off the console (Spot→on-demand flip = T-60 runbook step); ops-handover account 185708268748 verified: 3 alarms OK, SNS confirmed, $0.00 net/7d

## Do-not-say list (failed verification — never on stage)

- ~~"plans answer in ~70 ms"~~ — full plan: ~1.1–1.2 s warm on the rehearsed ODs today (don't quote a bare ms: cold fresh ODs run 2.3–9.2 s server, post-refresh first hit can reprice ~9 s, one 60-km cold call hit the 20 s planner budget → honest empty). Say "about a second to two on the rehearsed trip".
- ~~"62-station DMRC registry"~~ — real GTFS now (263 stations / 37 routes).
- ~~"~55–57 fires"~~, ~~fixed AQI/pm2.5 values~~ — everything drifts each 15-min refresh; say ranges (60 fires/14 belt at this afternoon's read).
- ~~"97,452 corpus / 16,952 addresses"~~ — exact truth: **97,447 / 16,949**.
- ~~"7,240 held-out station-hours"~~ — the deployed validation says **3,550** held-out station-hours over **85** stations; 95.2% coverage is the number that holds.
- ~~"11 live species"~~ — **10** today; the ammonia param is served but honestly empty.
- ~~"metro is the clean option"~~ — on the demo OD metro+walk doses ~7.2× car-AC today (53.2 vs 7.4; ~4.5× on the script OD). The clean claim is per-leg (coach), not per-trip.
- ~~"corridors diverge ≥15%"~~ as the quote — measured **19–96%**; quote the measured number.
- ~~"walk ~205–228 µg / ~34×"~~ — and every prior stamp aged the same way: today's reads are **238 µg / 33.0× on the script OD, 255 µg / ~34.5× on the demo OD** — quote the wire you just read, never a memorized figure.
- ~~"fires checked and refused"/~~ ~~"fires claimed"~~ — **drifts with the wind, and `/v2/why` now also serves `cause_note`** (the parali-watch line — say what it reads): today SW wind → `carrying:false`, refused (44 fires / 12 belt / ×1.06); Oct-6 was claimed at ×1.24 on a 315° NW wind. Re-check `curl $NLB/v2/why` before stage and say the live line.
- ~~"all ODs answer ~1.8 s"~~ — fresh ODs measured 2.3–6.7 s server (`took_ms`), one cold far-OD timed out at the 20 s budget. Rehearse on the demo OD.
- ~~"24 ms reroute / 100+ concurrent"~~ — single-user path only; the 1-vCPU task pinned at 100% CPU under parallel load in testing.
- ~~absolute "Delhi AQI is 150"~~ — that's Connaught Place; city lattice mean ~55 this morning (~36–62 across this week). Always name the place.
- ~~"/admin/api tiles"~~ — the whole `/admin` board sits behind the sign-in now (`b563da2`): guests land on a gate card; sign in at T-30 (`/v2/admin/login` → HttpOnly cookie ~8 h), never paste the token on camera; `/v2/city` + `/community` carry the same aggregates for stage.

## Rehearsal logs

**Pass 1 (12:20 IST):** beats in stage order — landing 0.71 s · health 0.48 · aqi 0.48 · plan 1.80 (took_ms 354) · depart 0.48 · community 0.48 · city 0.69 · moves 0.52 · grid-40 1.47 · edge-aqi 0.49 · admin 0.94 · describe-services 1.61 → **~10 s network in a 170 s script.**

**Pass 2 (12:55–13:15 IST, deep probes):** search battery 25/25, p50 474 ms; plan warm p50 346 ms; unseen-OD plans 4.0 s / 6.3 s server; strip `step_m` 250 live; corridor divergence 44–97% measured; species corr −0.05; refresh countdown ticking.

**Pass 3 (16:05–16:50 IST, post-re-anchor re-verify):** *(numbers stamped at pass time — fires/modifier/option counts drift; `verify_numbers.sh` T-45)* build `951eeb3c` (`:141`); demo OD now 20 opts, walk 189.8–211.6 µg ≈ 33–35× car; fresh-OD plans 2.3–6.7 s; KG→Faridabad cold call hit the 20 s planner budget → `options:[] + "planner timed out"` (retry 6.7 s, 21 opts); fires 70/16 ×1.27; wind 7.3@308; species 10 live (ammonia empty); pm25↔no₂ r=+0.34; held-out truth = 3,550 station-hours/85 stations; search battery 172/174 (98.9%) p50 471 ms.

**Pass 4 (2026-10-05 ~23:55 UTC → Oct 6 ~05:30 IST, `verify_numbers.sh` + live probes on build `3711ccd0`):** options 19→24 within minutes on a field reprice — metro+walk 81.6 + GTFS "Bus 859" 147.7 present ~05:30 IST; warm plan 378–490 ms server (~2.1 s wall ex-India), post-refresh first hit 5.4–6.1 s; walk 405.7–410.5 → **33.1–33.3×** (39.7× slowest/best); fires 83/19 ×1.10; depart (hours=120): now 33.1 → worst +89 h 100.6 (3.0×), best +10 h 13.9, 96 slots over ~95 h; breath 1,064 µg ≈ 3.4 cig; skill 35 pairs (h+3/h+4 now graded); archive 10 snapshots; reach walk@25 2,945/128.7 km; strip on the tagged recommended row: 77 samples, full street names, pm2.5 68.5→84.3 (1.23×) — the least-smoke `rd` engine row strips as 'unnamed road' (mint on the recommended row); surfaces verified live: why-line on `/city` + `/admin` + landing, species pills, `/city` 'what happened' recorded flip, landing `a→b` + `whyLine`. Report: `docs/lanes/demo-rehearse-v2-report.md`.

**Pass 5 (Oct 6 ~00:15 UTC, re-read after deploy roll — live build `37e55668`):** all figures re-verified on the new build; ledger-floor/why-parallel/ingest-parallel `0fdd597`/`3aea78f`/`5ec1f2f` confirmed live. Plan: 24 opts, car-AC 12.9 / walk 429.2 → 33.3× (40.1× slowest/best), warm took_ms ~610 ms (~2.1 s wall), post-refresh first hit ~8 s; fires 89/22 ×1.11; us_aqi 161, pm25 83.3/75.1; depart 24 h: now 34.4 → worst 100.6 (2.9×), best 14.9; `?hours=120` 109 slots; breath 1,165 µg ≈ 3.7 cig; next_hours 36.8→151.6 (4.1×); skill 34 pairs, h+1..h+4 graded (14.2/+11.2, 26.3/+24.5, 42.0, 49.0); why trend HISTORY LIT (34 snapshots, +0.3 µg/5.8 h); strip 77 samples pm2.5 69.7→90.3 (1.30×), SP Marg 29.5%; reach w25 ~84 km / w50 ~396 km / c25 ~54,350 km edge_partial; day windows swung back to evening (22:30→end @160.5) — windows move with the field; **`/v2/day` now requires lat/lon**; `/v2/city` uses `trips.days` (moves endpoint still serves: 39 trips/7 d); archive 10 snapshots; community unchanged. All verbatim lines re-phrased to these reads.

**Pass 6 (Oct 6 ~05:10–05:30 UTC — demo-day-final truth pass, live build `f4139b24` == image `alive108-api:f4139b24`, task-def `:178`):** persistence-blend deploy live — `live_anchor.blend` on the wire (hold_h 2.0, end_h 40.0, w_h11 0.763, fitted_on 2026-10-05/06 archive pairs); the 'beats persistence' claim is now EARNED pooled (11.2 vs 13.1 vs 39.2 pre-blend; strictly better h+5+; IS persistence inside the 2-h hold — judge-qa §7 rewritten). Plan: demo OD IG→Huda 19→23 opts, car-AC ~12 / walk ~430–450 → **~36×**; script OD 24 opts, 10.8/359.1 → 33.3×, metro+walk 42.9, GTFS "Bus 729" 89.5; warm took_ms ~47 ms (rehearsed OD), fresh OD ~6.8 s. Depart now 28.7 → worst 102.7 (+83 h)/best 16.0 (+51 h), 104 slots. Day windows moved to evening (heavy ~19:30→end @76.0 / cleanest 14:30–18:30 @52.7 / mean 62.7). Skill 80 pairs, h+1..h+9 graded (12.2/+9.4 … 63.6). Why: stagnation VC ~1,252 m²/s (BLH 846 m — morning layer), fires refused S 138°, history −6.0 µg/5.7 h/29 snapshots. Archive 15 snapshots. Breath ~795 µg ≈ 2.5 cig. Reach w25 ~109 km / w50 ~477 / c25 ~83,642 edge_partial. Strip re-minted: 82 samples, 64.5→82.2 (1.27×), Delhi-Gurugram Expressway 29.6%. Community 24h: 5 obs/10.4 km/432.4 µg. pm25↔no₂ r=+0.55; us_aqi grid 91→166; edge band 10.7–97.7 @11.1 km; ammonia empty. Full evidence: `docs/lanes/demo-day-final-report.md`.

**Cold-path observation:** first three plan calls (engine re-price + transit arm cold) hit ~12 s arm timeouts → `degraded:["engine","transit"]` with 7 real rows still served; recovered to 17 opts once warm. A later full-budget timeout on KG→Faridabad produced the honest empty wire (`degraded:["planner"]`). This is the only latency cliff — `warm_task.py` + rehearsed OD is the mitigation.

| check | verdict |
|---|---|
| every quoted number read off the wire | GO |
| all 8 beats inside budget (2:50/3:00) | GO |
| plan latency on rehearsed OD | GO — warm only |
| fresh-OD latency | NOTE — 4–8 s; stick to rehearsed OD or accept the pause |
| drift safety of verbatim lines | GO — phrased in ranges, T-45 re-read mandated |
| AWS console / CLI proof | GO — verified |
| corrupt-data risk (public POSTs) | GO — GET-only probing + /v2/plan |
