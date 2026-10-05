# ALive-108 — the map that prices the air

**Google Maps optimizes for minutes. ALive-108 optimizes for breaths** — an
exposure-aware routing engine for Delhi NCR that ranks every way to get
there by the PM2.5 you'd actually inhale, not just how fast it is.

**Live now (no install):**
`http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com`

Built for the AWS × WeMakeDevs Environmental Hacks hackathon, Track 01 (Air),
Oct 8–11, 2026. Delhi-only by design.

<!-- SCREENSHOT 1 — landing hero: `/` showing the live pollution field
     raster over NCR with the wind arrow + "watch the day" scrubber.
     File: docs/assets/readme/hero-landing.png -->
![ALive-108 landing — live PM2.5 field over Delhi NCR](docs/assets/readme/hero-landing.png)

## What it does (60 seconds)

You give it FROM→TO. It returns every real mode — sealed car, windows-open
car, auto, bus, metro+walk on live GTFS, bike, cycle, walk — each with an
ETA and the **inhaled PM2.5 dose in micrograms**, integrated every ~250 m of
the actual route:

> dose = concentration × micro-environment × ventilation × time

Same trip, measured live (Connaught Place → Gurugram, 23.7 km):

| mode | dose (µg) | | mode | dose (µg) |
|---|---|---|---|---|
| car AC | **5.4** | | metro+walk | 24.5 |
| car open | 9.7 | | cycle | ~80 |
| auto | 15.8 | | walk | **~190** |

That's a **30–40× spread the map you use today never shows you** — and it
matches published Delhi measurements (walk ≈28× metro per km; Sci. Total
Environ. 2021).

<!-- SCREENSHOT 2 — /city mid-timelapse: the next-12-hours lattice playing,
     showing the field swing (morning ~43 → evening ~298 µg/m³).
     File: docs/assets/readme/city-timelapse.png -->
![/v2/city — Delhi's air, hour by hour](docs/assets/readme/city-timelapse.png)

Underneath: a live field rebuilt every 15 min from 24 WAQI instruments +
CAMS/open-meteo model samples + NASA FIRMS fires, kriged with a real σ band
by our own C++ engine — that re-prices all **1.07M road edges** so the
least-dose path is a routing criterion, not an annotation. Plus a 120-hour
forecast (leave-later optimizer), per-mode emissions bands (CO₂ + tailpipe
PM on Delhi fleet factors), and a privacy-floored community layer — streets
publish only after **3 different devices** cross them.

<!-- SCREENSHOT 3 — /admin choropleth: 28-district NCR choropleth + field
     cells + fires overlay. File: docs/assets/readme/admin-choropleth.png -->
![/admin — the city breathing, aggregated](docs/assets/readme/admin-choropleth.png)

## Try it — a judge's quickstart (public, GET-only)

```bash
NLB=http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com

# the live engine + field status
curl -s $NLB/health            # engine:"alive_core" · 1,070,459 edges · field age

# PM2.5 at Connaught Place — value + σ band + calibration + fire modifier
curl -s "$NLB/aqi?lat=28.6315&lon=77.2167"

# the dose table above, computed live
curl -s -X POST $NLB/v2/plan -H 'content-type: application/json' \
  -d '{"from":{"lat":28.6315,"lon":77.2167},"to":{"lat":28.495,"lon":77.089}}'

# the next 12 hours of Delhi's air, per hour
curl -s $NLB/v2/city

# the privacy floor on the wire: min_k=3, suppressed buckets named
curl -s $NLB/v2/city/moves
```

Browser surfaces: `/` (live field map, a→b), `/admin` (ops board),
`/community`, `/v2/city` — all public, all live.

## Architecture

```
Mobile app (Expo, Android+iOS) ──┐            ┌─ every 15 min ──────────┐
Web surfaces / judges ──────────┤ HTTP :80   │  WAQI stations + CAMS    │
                                ▼           │  + NASA FIRMS + met wind │
        NLB + Elastic IP 65.2.28.40         │  → krige field → S3      │
                │                           │    snapshot (last-good)  │
                ▼                           └──────────────────────────┘
   ECS Fargate (ap-south-1, 1 vCPU/2 GB)
   FastAPI + alive_core C++ (pybind) + osrm-local sidecar
   ├─ /v2/plan   dose-priced routing over 1.07M edges (+GTFS metro arm)
   ├─ /aqi /grid /depart   field, forecast, leave-later
   ├─ /v2/search  C++ index over 97,447-entry OSM-NCR corpus
   └─ /v2/city /admin /community   aggregates, k≥3 everywhere
        │            │               │
      DynamoDB     S3            Secrets Manager
     alive108-agg  field snaps   admin + upstream keys
     (aggregates   + community    (nothing in repo)
      only)        state
        ▲
   CodeBuild → ECR → task-def   (every deploy builds in AWS)
```

Self-hosted Delhi basemap: 22.7 MB pmtiles from Geofabrik OSM, z0–14
(`/tiles/health`). Decade climatology from OpenAQ's public S3 archive
(9M station-hours / 125 stations). Cost: ~$46/mo worst case; Fargate Spot
outside demo windows.

## Validation (the part most projects skip)

- **95.2 % measured coverage** of the served ±2σ bands over 3,550 held-out
  station-hours across 85 stations (`server/data/field_validation.md`).
- LOO calibration vs live instruments: MAE 46.1 µg/m³, bias +0.3, n=94 —
  served on the wire at `/aqi → calibration`.
- Archive replay on clean air: MAE 22.0, bias +51.6 % — we publish that we
  over-read in clean air. The σ band is calibrated to cover it.
- C++ vs Python engines asserted bit-identical in `server/tests/`;
  benches in `docs/plan/bench-results.md`.

## Honest limitations

- **NCR only.** Outside the service area you get a typed
  `outside_service_area`, never a fabricated route.
- **One Fargate task, one region, HTTP :80.** Cold far-OD plans can hit a
  20 s budget and honestly return `options:[]`; degraded arms are named
  (`degraded:["engine","transit"]`), never faked.
- **The forecast is a model** (CAMS + stagnation physics anchored to live),
  not ground truth — thin cells say `confidence:"low"` and bands widen.
- **Community layer is young** — a corridor appears only after 3 distinct
  devices cross it; early on, that table is honestly sparse.
- **CPCB live feeds are geo-blocked** from the deployment network (WAQI
  carries measured stations meanwhile); the OpenAQ live-key path is wired
  but dormant — documented in `server/data/field_validation.md`.

## Repo layout

`server/` — FastAPI engine + `alive_core` C++ (pybind11) + public pages ·
`Mobile/` — Expo app (Android release target; iOS dev-only) ·
`infra/` `scripts/` `tools/` — AWS provisioning, deploy, corpus, warm-up ·
`docs/` — the research + verification corpus (`docs/plan/` is the source of
truth; `docs/plan/10-claims-ledger.md` governs every number we show).

*AI tools used are disclosed in the submission writeup.*
