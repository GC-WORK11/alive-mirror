# ALive-108 — a personal PM2.5 dosimeter for Delhi (no hardware)

**Your lungs' ledger for Delhi: what you breathed today, where it cost you,
and when tomorrow's air is worth going out in — no device, no uploads.**
ALive-108 reconstructs personal exposure the way the research literature
does — timeline × concentration field → individual dose — but on the phone
you already carry, not on a $200 gadget. Your day is reconstructed
**on-device**; the only things that ever leave it are consented, k≥3
privacy-floored aggregates.

Exposure-aware routing is one feature inside it — the proof that the field
and the dose math are real enough to decide with.

**Live now (no install):**
`http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com`

Built for the AWS × WeMakeDevs Environmental Hacks hackathon, Track 01 (Air),
Oct 8–11, 2026. Delhi-only by design.

<!-- SCREENSHOT 1 — PENDING CAPTURE: `/` dosimeter landing — "a personal
     dosimeter for Delhi air" hero over the live pollution field with the
     "watch the day" scrubber. File: docs/assets/readme/hero-landing.png
     (docs/assets/readme/ is not yet populated — capture on demo morning) -->
![ALive-108 landing — a dosimeter, not a lookup](docs/assets/readme/hero-landing.png)

## What it does (60 seconds)

Three questions, three shipped surfaces:

1. **"What did today cost me?"** — every trip receipts in inhaled µg and
   lands in `ledger.json` on the phone (500-trip cap, delete-all, no
   account). Donation is opt-in and aggregate-only — `min_k` is literally
   on the wire.
2. **"When is today's air worth going out in?"** — `GET /v2/day` returns
   the morning card for a point: today's heavy stretch and cleanest slot
   with real σ bands, plus the decisions they change.
3. **"Where can my lungs go inside my budget?"** — `GET /v2/reach` runs a
   bounded Dijkstra over dose and paints every road edge you can reach
   under `budget_ug` — the real search frontier, not a smoothed circle.

And the feature judges will poke — **dose-priced routing**. Same city, same
minutes; the vehicle decides what you inhale. Measured live today
(Connaught Place → Gurugram, 23.7 km, 18 options — the count drifts
16–20 as GTFS transit rows come and go):

| mode | dose (µg, mid) | | mode | dose (µg, mid) |
|---|---|---|---|---|
| car AC | **7.8** | | metro+walk | 33.0 |
| car open | 14.2 | | cycle | 114.7 |
| bike | 17.9 | | walk | **258.8** |
| bus | 20.4 | | auto | 23.1 |

A **~33× spread the map you use today never shows you** — and it matches
published Delhi measurements (walk ≈28× metro per km; Sci. Total Environ.
2021). `GET /v2/day` at the same point today: heavy stretch **22:30 IST →
day end ~122 µg/m³**, honestly **no clean slot left** (lightest ~68), day
mean ~103 — the card says when the doors should be open.

<!-- SCREENSHOT 2 — PENDING CAPTURE: `/city` lung-reach veil — "where can
     your lungs go?" frontier over streets + the district ledger.
     File: docs/assets/readme/city-reach.png -->
![/city — a 25 µg walking budget from Connaught Place: ~131 km of street](docs/assets/readme/city-reach.png)

*(reach edge-lengths are over directed edges — a two-way street counts in
both directions; 3,020 edges ≈ 131 km at 25 µg, 10,756 ≈ 576 km at 50 µg —
today's read; it drifts with the field)*

Underneath: a live field rebuilt every 15 min from 24 WAQI instruments +
~71 CAMS/open-meteo model samples + NASA FIRMS fires, kriged with a real
σ band by our own C++ engine — that re-prices all **1.07M road edges** so
dose is a routing criterion, not an annotation. Plus a 120-hour forecast,
per-mode emissions bands (CO₂ + tailpipe PM on Delhi fleet factors), and a
privacy-floored community layer — streets publish only after **3 different
devices** cross them.

<!-- SCREENSHOT 3 — PENDING CAPTURE: `/admin` engine room — pipeline
     provenance, sources trust table, FIRMS detections on the field map.
     File: docs/assets/readme/admin-engine.png -->
![/admin — the engine room: every number has a source](docs/assets/readme/admin-engine.png)

The Android app is real and captured — shipped-build screenshots live in
`docs/assets/cloud-build/` (home map, route options, search, receipts):

| | |
|---|---|
| ![home map](docs/assets/cloud-build/android-home-map.png) | ![plan options](docs/assets/cloud-build/android-plan-options.png) |

## Try it — a judge's quickstart (public, GET-only)

```bash
NLB=http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com

# the live engine + field status
curl -s $NLB/health            # engine:"alive_core" · 1,070,459 edges · field age

# PM2.5 at Connaught Place — value + σ band + calibration + fire modifier
curl -s "$NLB/aqi?lat=28.6315&lon=77.2167"

# the morning card for a point — heavy window, cleanest slot, decisions
curl -s "$NLB/v2/day?lat=28.6315&lon=77.2167"

# the dose table above, computed live
curl -s -X POST $NLB/v2/plan -H 'content-type: application/json' \
  -d '{"from":{"lat":28.6315,"lon":77.2167},"to":{"lat":28.495,"lon":77.089}}'

# where a 25 µg walking budget can actually take you
curl -s "$NLB/v2/reach?lat=28.6315&lon=77.2167&mode=walk&budget_ug=25"

# the next 12 hours of Delhi's air, per hour
curl -s $NLB/v2/city

# the privacy floor on the wire: min_k=3, suppressed buckets named
curl -s $NLB/v2/city/moves
```

Browser surfaces: `/` (dosimeter landing + field map + a→b), `/city`
(districts, day-in-dose ticker, lung reach), `/community` (donation
ledger), `/admin` (engine room) — all public, all live.

## Architecture

```
Mobile app (Expo, Android+iOS) ──┐            ┌─ every 15 min ──────────┐
  · dose ledger ON-DEVICE        │            │  WAQI stations + CAMS    │
  · only k≥3 aggregates leave ───┤            │  + NASA FIRMS + met wind │
Web surfaces / judges ──────────┤ HTTP :80   │  → krige field → S3      │
                                ▼           │    snapshot (last-good)  │
        NLB + Elastic IP 65.2.28.40         └──────────────────────────┘
                │
                ▼
   ECS Fargate (ap-south-1, 1 vCPU/3 GB)
   FastAPI + alive_core C++ (pybind) + osrm-local sidecar
   ├─ /v2/plan   dose-priced routing over 1.07M edges (+GTFS metro arm)
   ├─ /v2/day    the morning card: heavy/cleanest windows + decisions
   ├─ /v2/reach  bounded-Dijkstra lung reach (C++/Python parity-tested)
   ├─ /v2/ledger per-device sanitized trip summaries + DELETE-all
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
- Engine parity is tested, not claimed: `server/tests/test_reach.py`
  asserts the C++ and Python reach settle the *identical* edge set;
  dose/emission kernels are pinned to 1e-9 ("bit-identical in practice") —
  `test_parity_dose.py`, `test_parity_series.py`. Benches in
  `docs/plan/bench-results.md` (C++ search p50 0.189 ms).
- Landmark-truth sweep: 23 fabricated landmark geocodes purged; top-3 of
  every flagship query must land within 1.5 km of truth
  (`test_search_quality.py`).

## Honest limitations

- **NCR only.** Outside the service area you get a typed
  `outside_service_area`, never a fabricated route.
- **One Fargate task, one region, HTTP :80.** Cold far-OD plans can hit a
  20 s budget and honestly return `options:[]`; degraded arms are named
  (`degraded:["engine","transit"]`), never faked.
- **The forecast is a model** (CAMS + stagnation physics anchored to live),
  not ground truth — thin cells say `confidence:"low"` and bands widen.
- **The met-wind feed intermittently reports `known:false`** for a refresh
  or two (upstream reachability) — it says so on the wire instead of
  serving a stale vector.
- **`/v2/day` is API + web today** — the app's day view is the on-device
  ledger; the card's own surface is still web-side.
- **Community layer is young** — a corridor appears only after 3 distinct
  devices cross it; early on, that table is honestly sparse.
- **CPCB live feeds are geo-blocked** from the deployment network (WAQI
  carries measured stations meanwhile); the OpenAQ live-key path is wired
  but dormant — documented in `server/data/field_validation.md`.
- **`/health` `build_sha` can lag the deployed image** by a deploy — the
  ECR task image tag is the truth (today: `alive108-api:1e93b9f2`).

## Repo layout

`server/` — FastAPI engine + `alive_core` C++ (pybind11) + public pages ·
`Mobile/` — Expo app (Android release target; iOS dev-only) — the
on-device dose ledger lives in `Mobile/src/store/ledger.ts` ·
`infra/` `scripts/` `tools/` — AWS provisioning, deploy, corpus, warm-up ·
`docs/` — the research + verification corpus (`docs/plan/` is the source of
truth; `docs/plan/10-claims-ledger.md` governs every number we show;
`docs/plan/alive-depth.md` is the dosimeter thesis).

*AI tools used are disclosed in the submission writeup.*
