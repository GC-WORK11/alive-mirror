# ALive-108 — demo-day stage script (≤3:00) — v2

*Verified end-to-end against the live service **2026-10-05, 12:20–13:15 IST**
(build `34c3ca5a`, ECS `ap-south-1`, task-def `alive108:131`, FARGATE_SPOT,
deployment COMPLETED — confirmed via `aws ecs describe-services`).
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
| 1 | 0:00–0:12 | `/` landing — ASCII field drifting | "Delhi's air has a price per street. What you're looking at isn't a video — it's the live pollution field over NCR, right now, drifting on today's actual wind." | landing glyphs = real `/grid` cells advected on live wind 10.8 km/h from 296° ⟳ |
| 2 | 0:12–0:30 | `/aqi` at Connaught Place | "US AQI in the mid-160s — Unhealthy — built five minutes ago from two dozen live instruments blended with a satellite model, kriged by our own C++ engine, with 55 NASA fire detections feeding a smoke modifier. And this is a countdown — the field refreshes on a 15-minute heartbeat you can watch tick." | us_aqi 166–168, pm2.5 104.5–110 (band 87–128), stations 23–24 WAQI + 63–71 CAMS samples, fires 55 (14 belt), `engine: alive_core`, field age ~5 min, `refresh_in_s` observed counting down 432→423 s ⟳ |
| 3 | 0:30–1:05 | `/v2/plan` CP → Gurugram compare sheet | "Connaught Place to Gurugram — seventeen options in under two seconds. All 1.07 million road edges were re-priced off that live field. Same road, same minutes: on foot you inhale a little over 200 micrograms; in an auto, about 18; metro plus walk, 27 — and here's the honest surprise: a sealed AC car at about 6 beats the metro, because the clean coach is bookended by road-level walks. That's a 34-times spread the map you use today never tells you." | 17 opts; walk 205.7–228.6 µg, auto 18.0–19.9, metro+walk 27.0–28.0 (`steps_source: gtfs`, "Take Yellow from Rajiv Chowk"), car-AC 6.0–6.7 → **~34×**; edges 1,070,459 (903,058 priced); warm `took_ms` ~0.35 s; dose `coverage: 1.0`; alternates measured **97%/60%/44% divergent** (spec ≥15%) |
| 4 | 1:05–1:30 | `/depart` curve | "When you leave matters as much as how. Same trip now: about 6 micrograms. Leave in two hours: under 4 — forty-five percent less smoke for zero effort. Wait until 4 pm and it's six times worse. The city breathes on a schedule — tonight the same streets go nearly nine times dirtier between 9 am and 4 pm — and this runs on a 120-hour forecast fused to the live field." | now 6.6 → best +2 h 3.6 (**−45%**), worst +10 h 36.1; 102 slots over 120 h, aq+met 48 pts each, `live_anchor` on, forecast age ~8 min; `/v2/city.next_hours` swing **35.5→309.3 (8.7×)** ⟳ |
| 5 | 1:30–1:55 | `/v2/city` + `/admin` + `/community` | "Every donated trip becomes a live sensor. Twelve contributors have already logged 37 kilometres — the engine counts 334 micrograms of smoke they didn't breathe. And the air varies street to street: this one drive crosses air almost two times dirtier at one end than the other — Outer Circle at 73, the corridor minimum at 40. Streets only publish after three different riders cross them; the privacy is in the math." | contributors 12, km_24h 36.7, avoided 333.5 µg, obs 20; 10 corridors k≥3 (hanuman lane 12 trips/9 dev); strip: 77 samples @250 m, route pm2.5 min 40.1 → max 75.6 (**1.9×**), per-street avg 66.6–72.5, `dose_share` per road on the wire; `/v2/city/moves` 33 trips/7 d, car 78.8%; suppression field live ⟳ |
| 6 | 1:55–2:20 | **AWS console** — ECS `alive108` service | "Real infrastructure, not a laptop demo: ECS Fargate in Mumbai behind a Network Load Balancer — one service, one task, healthy, Spot-priced. CodeBuild ships every deploy, DynamoDB holds only aggregates, S3 keeps the last good field snapshot. About forty-six dollars a month." | `describe-services` ACTIVE · 1/1 · `alive108:131` · FARGATE_SPOT · rollout COMPLETED ⟳ |
| 7 | 2:20–2:40 | `/admin` field map — species pills | "We hold one rule: no fake precision. The uncertainty band is *measured* — 95.2 percent coverage at two-sigma over 7,240 held-out station-hours. Eleven pollutants ride the same lattice and they're chemically different maps — PM2.5 and NO₂ correlate at minus 0.05 today. Click NO₂, the pattern changes; it's not a relabeled layer. Far from a sensor the band honestly widens; outside Delhi it refuses to answer." | band coverage **95.2% @±2σ / 7,240 held-out h**; 11 species served; pm25↔no₂ cell corr **r=−0.05**; us_aqi grid range 88→165; edge band 12.8–109.4 at 17.6 km; Mumbai → typed `outside_service_area` |
| 8 | 2:40–2:50 | back to `/` | "Exposure and emissions, measured end-to-end — dose every 250 metres for the rider, emissions per mode for the city. ALive-108 — the map that prices the air." | `step_m: 250.0` live on `/v2/strip`; pitch per docs/demo-day.md |

## The AWS console moment (required — no console, no score)

**Primary:** ECS console, already signed in, pinned tab —
`https://ap-south-1.console.aws.amazon.com/ecs/v2/clusters/alive108/services/alive108/health`
(service card: ACTIVE, running 1/1, Fargate). Pan to **Tasks** if they linger.

**CLI understudy (verified live 2026-10-05):**

```bash
AWS_DEFAULT_REGION=ap-south-1 \
aws ecs describe-services --cluster alive108 --service alive108 \
  --query 'services[0].{status:status,running:runningCount,taskDef:taskDefinition,capacity:capacityProviderStrategy}'
```

→ `ACTIVE · 1/1 · alive108:131 · FARGATE_SPOT`. Do **not** log in live on stage.

## Contingency beats

| If this stalls | do this on stage |
|---|---|
| `/v2/plan` > ~4 s | Engine re-pricing after a field refresh — wait ~12 s once, never spam; next call lands warm in ~1.8 s. Rehearse on the SAME OD you'll demo (fresh unseen ODs measured 4–8 s server-side). `python3 tools/warm_task.py` at T-40 is load-bearing. |
| `degraded:["engine","transit"]` on the wire | Narrate it: "the API names which arm timed out — we'd rather show a missing arm than a fabricated answer." Router rows still render. |
| Any endpoint > 8 s twice | Cut to pre-recorded ride video (docs/demo-day.md backups); keep narrating — numbers were live-verified today. |
| `/health` `field_stale:true` | Say it tells the truth; read the real age aloud. |
| Hall Wi-Fi dead | Phone hotspot (NLB is HTTP :80 only; captive portals break it). Bundled 124k-row gazetteer keeps search alive offline. |
| Numbers drifted since morning | They will — the field refreshes every 15 min. Quote the ranges ("mid-160s", "over 200", "about 6"); the drift column below shows the observed swing. |

## Numbers sheet (verified 2026-10-05, drift across two field refreshes shown)

**Field & air**
- engine `alive_core` · routing **1,070,459 edges / 903,058 priced** · `osrm-local` router (self-hosted, ~15 ms)
- field: **63–71** CAMS/model samples · **23–24** WAQI instruments · age ~5–6 min, TTL 900 s · `stale:false` · `refresh_in_s` visibly counting down on the wire
- fires: **55** (14 in-belt), FIRMS public CSV, ~5 min old · smoke modifier ×1.24 · wind 10.8 km/h @ 296°
- CP now: pm2.5 **104.5–110.0** breathing / **84.3–88.7** ambient · band width ~35 µg · **US AQI 166–168** · PM10 ~231 · GRAP-indicative stage I · +21–28% vs decade norm for the hour
- city: 28 districts, live pm2.5 **44.4–50.5** spread · lattice mean ~48 · `us_aqi` grid **88→165** across cells · next-12h swing **35.5→309.3 (8.7×)**
- breath: day-inhaled **674 µg mid ≈ 2.13 cigarettes** (hi 4.68; 316 µg/cig, opt-in)

**Routing & dose**
- CP→Gurugram (23.7 km): **17 options**, warm `took_ms` 342–354 (p50 ~0.35 s server / 1.78 s wall) · doses ⟳: car-AC 6.0–6.7 · car-open 8.8–9.8 · bus 13.1–14.6 · bike 14.5–16.2 · auto 18.0–19.9 · metro+walk 27.0–28.0 · bicycle 118.5–131.7 · **walk 205.7–228.6 µg → ~34× car**
- **µg/km ladder** (verified): car-AC 0.25 · car-open 0.37 · bus 0.55 · bike 0.61 · auto 0.76 · metro+walk 1.02 · bicycle 5.00 · **walk 8.68**
- **the honest surprise**: metro+walk ≈ 4.5× car-AC dose on this OD — GTFS ride is clean, road-level access walks aren't
- corridor alternates measured divergent: alt1 **97%**, alt2 **60%**, rd **44%** of length (spec: ≥15%) — real different routes
- per-street air on one trip (strip, `step_m` 250): 77 samples · Outer Circle 72.5 vs Shaheed Bhagat Singh Marg 66.6 · route spans **1.9×** air · street `dose_share` attribution on the wire
- emissions: car CO₂ 1.8–5.2 kg (mid 2.82) + PM2.5 tailpipe up to 3.18 g · metro 0.42 kg CO₂, **zero PM** · curve params (`co2_g_km`, idle, cold-start) served for client-side 1 Hz ticking
- other ODs: India Gate→Noida car 2.5 vs walk 83.6 (**33×**, 24 opts); KG→Faridabad car 8.5 vs walk 362 (**43×**, 19 opts) — the spread holds, the factor doesn't (say "30–40×")

**Search & corpus**
- corpus truth (STATS.md): **91,931,396 OSM nodes + 8,888,227 ways scanned → 97,447 entries, 16,949 real address rows** (house numbers + interpolations) · app bundles **124,334-row gazetteer** → offline search
- battery of 25 real Delhi queries: **25/25 top-hit, wall p50 474 ms / p95 766 ms** over NLB · typo "conaught place"→Connaught Place · "559 udyog vihar"→real house-number address · engine itself ~1 ms C++

**Honesty**
- band coverage **95.2% @±2σ over 7,240 held-out station-hours** (`SIGMA_CAL ×3.2`; raw krige covered only 29% — we measured and widened)
- LOO calibration: MAE **46.1 µg/m³**, bias **+0.3**, n=94 live instruments
- grid confidence: hi 31% / med 62% / lo 7% — thin cells paint honest
- edge /aqi at 17.6 km from nearest sample: band widens 12.8–109.4 · Mumbai → typed `outside_service_area`, zero fabricated route
- `/community`: 20 obs · 12 contributors · 36.7 km/24 h · 333.5 µg avoided · corridors publish only at k≥3 devices — suppression mechanism on the wire (`mode_share_suppressed_trips`)

**AWS**
- ECS `alive108` ACTIVE · running 1/1 · task-def `:131` · FARGATE_SPOT · rollout COMPLETED (Spot→on-demand flip = T-60 runbook step)

## Do-not-say list (failed verification — never on stage)

- ~~"plans answer in ~70 ms"~~ — full plan: ~0.35 s warm / 4–8 s fresh OD / ~12 s degraded-cold. Say "under two seconds on the rehearsed trip".
- ~~"62-station DMRC registry"~~ — real GTFS now (263 stations / 37 routes).
- ~~"~57 fires"~~, ~~fixed AQI/pm2.5 values~~ — everything drifts each 15-min refresh; say ranges.
- ~~"97,452 corpus / 16,952 addresses"~~ — exact truth: **97,447 / 16,949**.
- ~~"metro is the clean option"~~ — on this OD metro+walk doses ~4.5× car-AC. The clean claim is per-leg (coach), not per-trip.
- ~~"corridors diverge ≥15%"~~ as the quote — measured **44–97%**; quote the measured number.
- ~~"all ODs answer ~1.8 s"~~ — fresh ODs measured 4.0–6.3 s server (`took_ms`), wall up to 8 s. Rehearse on the demo OD.
- ~~"24 ms reroute / 100+ concurrent"~~ — single-user path only; the 1-vCPU task pinned at 100% CPU under parallel load in testing.
- ~~absolute "Delhi AQI is 166"~~ — that's Connaught Place; city lattice mean ~48. Always name the place.
- ~~"/admin/api tiles"~~ — needs the owner token; the public `/admin` page + `/v2/city` + `/community` carry the same aggregates for stage.

## Rehearsal logs

**Pass 1 (12:20 IST):** beats in stage order — landing 0.71 s · health 0.48 · aqi 0.48 · plan 1.80 (took_ms 354) · depart 0.48 · community 0.48 · city 0.69 · moves 0.52 · grid-40 1.47 · edge-aqi 0.49 · admin 0.94 · describe-services 1.61 → **~10 s network in a 170 s script.**

**Pass 2 (12:55–13:15 IST, deep probes):** search battery 25/25, p50 474 ms; plan warm p50 346 ms; unseen-OD plans 4.0 s / 6.3 s server; strip `step_m` 250 live; corridor divergence 44–97% measured; species corr −0.05; refresh countdown ticking.

**Cold-path observation:** first three plan calls (engine re-price + transit arm cold) hit ~12 s arm timeouts → `degraded:["engine","transit"]` with 7 real rows still served; recovered to 17 opts once warm. This is the only latency cliff — `warm_task.py` + rehearsed OD is the mitigation.

| check | verdict |
|---|---|
| every quoted number read off the wire | GO |
| all 8 beats inside budget (2:50/3:00) | GO |
| plan latency on rehearsed OD | GO — warm only |
| fresh-OD latency | NOTE — 4–8 s; stick to rehearsed OD or accept the pause |
| drift safety of verbatim lines | GO — phrased in ranges, T-45 re-read mandated |
| AWS console / CLI proof | GO — verified |
| corrupt-data risk (public POSTs) | GO — GET-only probing + /v2/plan |
