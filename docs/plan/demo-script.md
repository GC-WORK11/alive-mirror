# ALive-108 — demo-day stage script (≤3:00) — v2

*Verified end-to-end against the live service **2026-10-05, 16:05–16:50 IST**
(build `951eeb3c`, ECS `ap-south-1`, task-def `alive108:141`, FARGATE_SPOT,
deployment COMPLETED — confirmed via `aws ecs describe-services`).
Dose model is the re-anchored one (walk/auto ME 1.30, seated VE 10.0–10.5) —
numbers below replace the pre-re-anchor pass.*
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
| 1 | 0:00–0:12 | `/` landing — live raster + wind arrow | "Delhi's air has a price per street. What you're looking at isn't a video — it's the live pollution field over NCR, right now — the arrow is today's real wind, and this scrubber walks the next twelve hours of it." | landing canvas = real `/grid` cells on true NCR geography · wind arrow 7.3 km/h @ 308° · '▶ watch the day' scrubs real `/grid?h=0..12` forecast surfaces ⟳ |
| 2 | 0:12–0:30 | `/aqi` at Connaught Place | "US AQI around 150 — Unhealthy — built minutes ago from two dozen live instruments blended with a satellite model, kriged by our own C++ engine, with 70 NASA fire detections feeding a smoke modifier. And this is a countdown — the field refreshes on a 15-minute heartbeat you can watch tick." | us_aqi ~149–153 at CP, pm2.5 breathing 73.9 / ambient 59.6 (band 59.0–88.7 ≈30 µg wide), stations 24 WAQI + 72 CAMS samples, fires 70 (16 belt, modifier ×1.27), `engine: alive_core`, field age 3–7 min, `refresh_in_s` observed counting down ⟳ |
| 3 | 0:30–1:05 | `/v2/plan` CP → Gurugram compare sheet | "Connaught Place to Gurugram — twenty options in under two seconds. All 1.07 million road edges were re-priced off that live field. Same road, same minutes: on foot you inhale around 200 micrograms; in an auto, about 17; metro plus walk, 25 — and here's the honest surprise: a sealed AC car at about 6 beats the metro, because the clean coach is bookended by road-level walks. That's about a 35-times spread the map you use today never tells you." | 20 opts; walk 189.8–211.6 µg, auto 16.9, metro+walk 25.2 (`mode:"metro+walk"`, `steps_source: gtfs`, "Take Yellow from Rajiv Chowk to Sikanderpur — 18 stops"), car-AC 5.7–6.0, car-open 10.4, bike 13.1, bus 15.0, bus-GTFS-729 49.1, cycle 84.1–90.0 → **~33–35×**; edges 1,070,459 (903,058 priced); warm `took_ms` ~0.55–0.63 s; dose `coverage: 1.0`; alternates measured **96%/55%/19% divergent** (spec ≥15%) |
| 4 | 1:05–1:30 | `/depart` curve | "When you leave matters as much as how. Same trip now: about six micrograms. Wait seven hours — tonight's commute — and it's eight times worse: 45. The best hour this week is barely better than now, so the curve's message is leave early. The city breathes on a schedule — the lattice itself swings over six times across the next twelve hours — and this runs on a 120-hour forecast fused to the live field." | now 5.5 → best +72 h 4.6 (**−16%**, `pct_less_vs_now:16`), worst +7 h 44.7 (**~8.1×**); 110 slots over 120 h, aq+met 48 pts each, `live_anchor` on (tau 9 h), forecast age ~8 min; `/v2/city.next_hours` swing **45.7→297.8 (6.5×)** ⟳ |
| 5 | 1:30–1:55 | `/v2/city` + `/admin` + `/community` | "Every donated trip becomes a live sensor. Twelve contributors have logged about 18 kilometres in the last day — the engine counts 333 micrograms of smoke they didn't breathe. And the air varies street to street: this one drive crosses air 1.7 times dirtier at one end than the other — Outer Circle at 55, the far end at 32. Streets only publish after three different riders cross them; the privacy is in the math." | contributors 12, km_24h 18.1, avoided_ug 333.5, obs 20 (7 in 24 h, latest 272 min old); 10 corridors publishable of 54 tracked (top 'Punjab National Bank' 3/3; hanuman lane 12 trips/9 dev); strip: 77 samples @250 m, route pm2.5 min 32.3 → max 55.8 (**1.7×**), road dose-share Outer Circle 54.9 vs Mother Teresa Crescent 32.6; `/v2/city/moves` 33 trips/7 d, car 78.8%; suppression field live ⟳ |
| 6 | 1:55–2:20 | **AWS console** — ECS `alive108` service | "Real infrastructure, not a laptop demo: ECS Fargate in Mumbai behind a Network Load Balancer — one service, one task, healthy, Spot-priced. CodeBuild ships every deploy, DynamoDB holds only aggregates, S3 keeps the last good field snapshot. About forty-six dollars a month." | `describe-services` ACTIVE · 1/1 · `alive108:141` · FARGATE_SPOT · rollout COMPLETED ⟳ |
| 7 | 2:20–2:40 | `/admin` field map — species pills | "We hold one rule: no fake precision. The uncertainty band is *measured* — 95.2 percent coverage at two-sigma over 3,550 held-out station-hours across 85 stations. Ten pollutants ride the same lattice — an eleventh, ammonia, is honestly empty today — and they're chemically different maps: PM2.5 and NO₂ correlate at only plus 0.34. Click NO₂, the pattern changes; it's not a relabeled layer. Far from a sensor the band honestly widens; outside Delhi it refuses to answer." | band coverage **95.2% @±2σ / 3,550 held-out h, 85 stations** (field_validation.md); 10 species live today (ammonia param served but empty); pm25↔no₂ cell corr **r=+0.34**; us_aqi grid range 78→149; edge band 19.0–81.5 at 17.6 km; Mumbai → typed `outside_service_area` |
| 8 | 2:40–2:50 | back to `/` | "Exposure and emissions, measured end-to-end — dose every 250 metres for the rider, emissions per mode for the city. ALive-108 — the map that prices the air." | `step_m: 250.0` live on `/v2/strip`; pitch per docs/demo-day.md |

## The AWS console moment (required — no console, no score)

**Primary:** ECS console, already signed in, pinned tab —
`https://ap-south-1.console.aws.amazon.com/ecs/v2/clusters/alive108/services/alive108/health`
(service card: ACTIVE, running 1/1, Fargate). Pan to **Tasks** if they linger.
Task definition family `alive108`, live revision **:141** today.

**CLI understudy (verified live 2026-10-05):**

```bash
AWS_DEFAULT_REGION=ap-south-1 \
aws ecs describe-services --cluster alive108 --service alive108 \
  --query 'services[0].{status:status,running:runningCount,taskDef:taskDefinition,capacity:capacityProviderStrategy}'
```

→ `ACTIVE · 1/1 · alive108:141 · FARGATE_SPOT`. Do **not** log in live on stage.

## Contingency beats

| If this stalls | do this on stage |
|---|---|
| `/v2/plan` > ~4 s | Engine re-pricing after a field refresh — wait ~12 s once, never spam; rehearsed OD lands warm in ~0.6 s. Rehearse on the SAME OD you'll demo (fresh unseen ODs measured 2.3–6.7 s server-side; one 60-km cold call hit the 20 s planner budget → honest `options:[] + error:"planner timed out"`). `python3 tools/warm_task.py` at T-40 is load-bearing. |
| `degraded:["engine","transit"]` on the wire | Narrate it: "the API names which arm timed out — we'd rather show a missing arm than a fabricated answer." Router rows still render. |
| Any endpoint > 8 s twice | Cut to pre-recorded ride video (docs/demo-day.md backups); keep narrating — numbers were live-verified today. |
| `/health` `field_stale:true` | Say it tells the truth; read the real age aloud. |
| Hall Wi-Fi dead | Phone hotspot (NLB is HTTP :80 only; captive portals break it). Bundled 124k-row gazetteer keeps search alive offline. |
| Numbers drifted since morning | They will — the field refreshes every 15 min. Quote the ranges ("mid-160s", "over 200", "about 6"); the drift column below shows the observed swing. |

## Numbers sheet (verified 2026-10-05, drift across two field refreshes shown)

**Field & air**
- engine `alive_core` · routing **1,070,459 edges / 903,058 priced** · `osrm-local` router (self-hosted, ~15 ms)
- field: **72** CAMS/model samples · **24** WAQI instruments · age 3–7 min, TTL 900 s · `stale:false` · `refresh_in_s` visibly counting down on the wire
- fires: **70** (16 in-belt), FIRMS public CSV, ~7 min old · smoke modifier ×1.27 at CP · wind 7.3 km/h @ 308°
- CP now: pm2.5 **73.9** breathing / **59.6** ambient · band width ~30 µg · **US AQI ~153** · PM10 ~198 · GRAP-indicative stage 0 · +27% vs decade norm for the hour at CP (lattice mean −36% vs same norm — name the basis)
- city: 28 districts, live pm2.5 **27.4–40.8** spread · lattice mean 36.3 · `us_aqi` grid **78→149** across cells · next-12h swing **45.7→297.8 (6.5×)**
- breath: day-inhaled **520 µg mid ≈ 1.64 cigarettes** (hi 3.58; 316 µg/cig, opt-in)

**Routing & dose**
- CP→Gurugram (23.7 km): **20 options**, warm `took_ms` 550–631 (cold fresh OD 2.3–6.7 s; one 60-km cold call timed out at the 20 s budget → honest empty) · doses ⟳: car-AC 5.7–6.0 · car-open 10.4 · bike 13.1 · bus 15.0 · auto 16.9 · metro+walk 25.2 · bus-GTFS-729 49.1 · bicycle 84.1–90.0 · **walk 189.8–211.6 µg → ~33–35× car**
- **µg/km ladder** (verified): car-AC 0.24 · car-open 0.44 · bike 0.55 · bus 0.63 · auto 0.71 · metro+walk 0.95 · bicycle 3.55 · **walk 8.0**
- **the honest surprise**: metro+walk ≈ 4.4× car-AC dose on this OD — GTFS ride is clean, road-level access walks aren't
- corridor alternates measured divergent: alt1 **96%**, alt2 **55%**, rd **19%** of length (spec: ≥15%) — real different routes
- per-street air on one trip (strip, `step_m` 250): 77 samples · Outer Circle 54.9 vs Mother Teresa Crescent 32.6 dose-share · route spans **1.7×** air · street `dose_share` attribution on the wire
- emissions: car CO₂ 1.8–5.2 kg (mid 2.82) + PM2.5 tailpipe up to 3.18 g · metro+walk 0.42 kg CO₂, **zero PM** · curve params (`co2_g_km`, idle, cold-start) served for client-side 1 Hz ticking
- other ODs: India Gate→Noida car 2.4 vs walk 78.4 (**32.7×**, 24 opts); KG→Faridabad car 6.5 vs walk 250.0 (**38.5×**, 21 opts — first cold call timed out at 20 s, retry answered in 6.7 s); CP→India Gate walk 47.5 µg on 4.7 km (car 1.5, metro+walk 15.7) — the spread holds, the factor doesn't (say "30–40×")

**Search & corpus**
- corpus truth (STATS.md): **91,931,396 OSM nodes + 8,888,227 ways scanned → 97,447 entries, 16,949 real address rows** (house numbers + interpolations) · app bundles **124,334-row gazetteer** → offline search
- battery of 174 real Delhi queries live: **172/174 top-1 (98.9%), p50 471 ms / p95 704 ms / max 1.5 s** over NLB · misses: '25 rajinder nagar' (→ '25-K Rajinder Nagar' substring artefact), 'panipat' (honest empty — outside coverage) · the 25-query stage subset still lands 25/25 · engine itself ~1 ms C++

**Honesty**
- band coverage **95.2% @±2σ over 3,550 held-out station-hours, 85 stations** (`σ=√(krige_sd²+(0.12·µ)²) × SIGMA_CAL 3.2`; MAE 22.0, bias +51.6% on clean-air window — source: `server/data/field_validation.md`)
- LOO calibration: MAE **46.1 µg/m³**, bias **+0.3**, n=94 live instruments (pre-refresh audit — keep labelled as such if quoted)
- grid confidence: hi 31% / med 62% / lo 7% — thin cells paint honest
- edge /aqi at 17.6 km from nearest sample: band widens 19.0–81.5 · Mumbai → typed `outside_service_area`, zero fabricated route · in-bounds budget timeout → `options:[] + error:"planner timed out"`, degraded arm named
- `/community`: 20 obs · 12 contributors · 18.1 km/24 h · 333.5 µg avoided · corridors publish only at k≥3 devices — suppression mechanism on the wire (`mode_share_suppressed_trips`)

**AWS**
- ECS `alive108` ACTIVE · running 1/1 · task-def `:141` · FARGATE_SPOT · rollout COMPLETED (Spot→on-demand flip = T-60 runbook step)

## Do-not-say list (failed verification — never on stage)

- ~~"plans answer in ~70 ms"~~ — full plan: ~0.6 s warm on the rehearsed OD / 2.3–6.7 s fresh OD / one 60-km cold call hit the 20 s planner budget (honest empty). Say "under two seconds on the rehearsed trip".
- ~~"62-station DMRC registry"~~ — real GTFS now (263 stations / 37 routes).
- ~~"~55–57 fires"~~, ~~fixed AQI/pm2.5 values~~ — everything drifts each 15-min refresh; say ranges (70 fires/16 belt at last read).
- ~~"97,452 corpus / 16,952 addresses"~~ — exact truth: **97,447 / 16,949**.
- ~~"7,240 held-out station-hours"~~ — the deployed validation says **3,550** held-out station-hours over **85** stations; 95.2% coverage is the number that holds.
- ~~"11 live species"~~ — **10** today; the ammonia param is served but honestly empty.
- ~~"metro is the clean option"~~ — on this OD metro+walk doses ~4.4× car-AC. The clean claim is per-leg (coach), not per-trip.
- ~~"corridors diverge ≥15%"~~ as the quote — measured **19–96%**; quote the measured number.
- ~~"walk ~205–228 µg / ~34×"~~ — post-re-anchor truth on this OD: **189.8–211.6 µg, ~33–35×**; on a smoke-heavy field the same OD will read higher again.
- ~~"all ODs answer ~1.8 s"~~ — fresh ODs measured 2.3–6.7 s server (`took_ms`), one cold far-OD timed out at the 20 s budget. Rehearse on the demo OD.
- ~~"24 ms reroute / 100+ concurrent"~~ — single-user path only; the 1-vCPU task pinned at 100% CPU under parallel load in testing.
- ~~absolute "Delhi AQI is 150"~~ — that's Connaught Place; city lattice mean ~36. Always name the place.
- ~~"/admin/api tiles"~~ — needs the owner token; the public `/admin` page + `/v2/city` + `/community` carry the same aggregates for stage.

## Rehearsal logs

**Pass 1 (12:20 IST):** beats in stage order — landing 0.71 s · health 0.48 · aqi 0.48 · plan 1.80 (took_ms 354) · depart 0.48 · community 0.48 · city 0.69 · moves 0.52 · grid-40 1.47 · edge-aqi 0.49 · admin 0.94 · describe-services 1.61 → **~10 s network in a 170 s script.**

**Pass 2 (12:55–13:15 IST, deep probes):** search battery 25/25, p50 474 ms; plan warm p50 346 ms; unseen-OD plans 4.0 s / 6.3 s server; strip `step_m` 250 live; corridor divergence 44–97% measured; species corr −0.05; refresh countdown ticking.

**Pass 3 (16:05–16:50 IST, post-re-anchor re-verify):** build `951eeb3c` (`:141`); demo OD now 20 opts, walk 189.8–211.6 µg ≈ 33–35× car; fresh-OD plans 2.3–6.7 s; KG→Faridabad cold call hit the 20 s planner budget → `options:[] + "planner timed out"` (retry 6.7 s, 21 opts); fires 70/16 ×1.27; wind 7.3@308; species 10 live (ammonia empty); pm25↔no₂ r=+0.34; held-out truth = 3,550 station-hours/85 stations; search battery 172/174 (98.9%) p50 471 ms.

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
