# ALive-108 — a personal PM2.5 dosimeter for Delhi (no hardware)

**Your lungs' ledger for Delhi: what you breathed today, where it cost you,
and when tomorrow's air is worth going out in — no device, no uploads.**
ALive-108 reconstructs personal exposure the way the research literature
does — timeline × concentration field → individual dose — but on the phone
you already carry, not on a $200 gadget. Your day is reconstructed
**on-device**; the only things that ever leave it are consented aggregates —
folded into cell/hour/day counters at ingest, so **no per-trip record exists
anywhere on the server**; nothing publishes below k=3 distinct devices over
72 h.

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
   account). Donation is opt-in and aggregate-only at ingest — `min_k` is
   literally on the wire, and the privacy model is written down verifiably
   in `PRIVACY.md` (no per-trip row in memory, on disk, or in S3; the
   raw-coords endpoint answers **410**; request logs scrub coordinates; the
   contributor id is a 64-bit CSPRNG rotating every 30 days).
2. **"When is today's air worth going out in?"** — `GET /v2/day` returns
   the morning card for a point: today's heavy stretch and cleanest slot
   with real σ bands, plus the decisions they change.
3. **"Where can my lungs go inside my budget?"** — `GET /v2/reach` runs a
   bounded Dijkstra over dose and paints every road edge you can reach
   under `budget_ug` — the real search frontier, not a smoothed circle.

And the feature judges will poke — **dose-priced routing**. Same city, same
minutes; the vehicle decides what you inhale. Measured live
(Connaught Place → Gurugram, 23.7 km, 20–21 options — the count drifts
16–24 as GTFS transit rows come and go; breathing-zone basis,
`smoke_modifier: 1.24` claimed while the NW wind carried belt smoke —
it was downscaled to ×1.08 and named-but-refused once the wind turned
easterly; build `4eb9e1e8`):

| mode | dose (µg, mid) | | mode | dose (µg, mid) |
|---|---|---|---|---|
| car AC | **8.8** | | metro+walk | 37.5 |
| car open | 16.1 | | cycle | 130.0 |
| bike | 20.3 | | walk | **293.2** |
| bus | 23.1 | | auto | 26.2 |

A **~35× spread on a Delhi commute the map you use today never shows you**
— 33.3× measured today (35.9× on the India Gate→Huda City Centre demo OD),
31–45× across ODs this week — and it matches
published Delhi measurements (walk ≈28× metro per km; Sci. Total Environ.
2021). `GET /v2/day` at the same point today: flat moderate all day — no
meaningful heavy or clean window (`decisions` names it: "no meaningful
window today", day mean ~76, hours 71→82)
— the card says when the doors should be open.

<!-- SCREENSHOT 2 — PENDING CAPTURE: `/city` lung-reach veil — "where can
     your lungs go?" frontier over streets + the district ledger.
     File: docs/assets/readme/city-reach.png -->
![/city — a 25 µg walking budget from Connaught Place: ~136 km of street](docs/assets/readme/city-reach.png)

*(reach edge-lengths are over directed edges — a two-way street counts in
both directions; 3,105 edges ≈ 136 km at 25 µg, 10,436 ≈ 551 km at 50 µg —
today's read; it drifts with the field)*

Underneath: a live field rebuilt every 15 min from **54 ground
instruments — 24 WAQI + 30 DPCC** (the DPCC adapter shipped after our own
independent holdout caught the blind spots — see Validation below) +
~70 CAMS/open-meteo model samples + NASA FIRMS fires (67 at last read,
15 in the NW belt — the smoke claim is gated by wind direction), kriged
with a real
σ band by our own C++ engine — that re-prices all **1.07M road edges** so
dose is a routing criterion, not an annotation. Plus a 120-hour forecast,
an hourly **archive** recording the served field itself — `GET /v2/archive`
replays what Delhi actually breathed, hour by hour, history not just
forecast — per-mode emissions bands (CO₂ + tailpipe PM on Delhi fleet
factors), and a privacy-floored community layer — streets publish only
after **3 different devices** cross them, and donations fold to aggregates
at ingest.

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

# the field's own history — Delhi recorded hourly, replayed per day
curl -s "$NLB/v2/archive?day=2026-10-05"
```

Browser surfaces: `/` (dosimeter landing + field map + a→b), `/city`
(districts, day-in-dose ticker, lung reach), `/community` (donation
ledger), `/admin` (engine room) — all public, all live.

The audit trail behind every claim is committed: independent validation
against government instruments in `docs/lanes/accuracy-holdout-report.md`,
the blind-spot closure in `docs/lanes/ingest-dpcc-report.md`, a live
evening watch in `docs/lanes/field-watch-2-report.md`, and the statistical
validation corpus in `server/data/field_validation.md`.

## Architecture

```
Mobile app (Expo, Android+iOS) ──┐         ┌─ in-app ingest: every 15 min ┐
  · dose ledger ON-DEVICE        │         │  24 WAQI + 30 DPCC stations │
  · only k≥3 aggregates leave ───┤ HTTP :80│  + CAMS + NASA FIRMS + wind │
Web surfaces / judges ──────────┤         │  → krige field → S3 snapshot │
                                ▼         └─────────────────────────────┘
        NLB alive108-….elb.ap-south-1.amazonaws.com (Elastic IP 65.2.28.40)
                │
                ▼
   ECS Fargate (ap-south-1, 1 vCPU/3 GB)
   FastAPI + alive_core C++ (pybind) + osrm-local sidecar
   ├─ /v2/plan   dose-priced routing over 1.07M edges (+GTFS metro arm)
   ├─ /v2/day    the morning card: heavy/cleanest windows + decisions
   ├─ /v2/reach  bounded-Dijkstra lung reach (C++/Python parity-tested)
   ├─ /v2/ledger per-device sanitized trip summaries + DELETE-all
   ├─ /v2/archive served-field history — recorded hourly (basis:recorded)
   ├─ /v2/outlook + /aqi /grid /depart   field, forecast, leave-later
   ├─ /v2/search  C++ index over 97,447-entry OSM-NCR corpus
   └─ /v2/city /admin /community   aggregates, k≥3 everywhere
        │            │               │
      DynamoDB     S3            Secrets Manager
     alive108-agg  field snaps   admin + upstream keys
     (aggregates   + community    (nothing in repo)
      only)        + hourly field
                   archive
        ▲
   CodeBuild → ECR → task-def   (every deploy builds in AWS)
```

Self-hosted Delhi basemap: 22.7 MB pmtiles from Geofabrik OSM, z0–14
(`/tiles/health`). Decade climatology from OpenAQ's public S3 archive
(125 stations × a decade of hourly readings, medians by month×hour).
Cost: ~$46/mo worst case; Fargate Spot
outside demo windows.

## Validation (the part most projects skip)

- **Independent holdout vs 30 government DPCC stations the field never
  ingested** (Oct 6, three probe rounds, 81 observations): at the 7 sites
  the field provably cannot see (1.5–5.8 km), **MAE 22.8 µg/m³, +6%
  bias**; where a live instrument sits in the blend, MAE 16.4; all 30
  sites, 27.1. The misses are published, not hidden — Jahangirpuri read
  143 while we served 73 — then closed: `server/ingest_dpcc.py` now feeds
  those same 30 instruments into the blend. **Re-measured on prod a day
  later, same method: blind-site MAE 22.8 → 10.5 (bias +0.8), all-30
  agreement 27.1 → 6.2, worst single miss 19.1, every station at
  `nearest_sample_km = 0.0`** — the honest residuals kept in the table
  (JNU/IGNOU are instruments reading far off their own region, not
  blindness). The frontier is now the unmonitored NCR fringe, 5.5–15.7 km
  out. Full tables + per-station breakdown:
  `docs/lanes/accuracy-holdout-report.md`,
  `docs/lanes/ingest-dpcc-report.md`,
  `docs/lanes/holdout-reverify-report.md`.
- **A 14-probe live watch** across the parali evening ramp and three
  mid-watch deploys: the stubble-smoke claim followed the wind in both
  directions (claimed ×1.24 at 344°, refused ×1.07 once it turned), the
  trend recorder caught the −7.5→+35.7 µg regime flip live, degrades are
  named on the wire (`degraded:["engine"]`), never silent —
  `docs/lanes/field-watch-2-report.md`.
- **95.2 % measured coverage** of the served ±2σ bands over 3,550 held-out
  station-hours across 85 stations (`server/data/field_validation.md`) —
  the temporal validation σ was fitted on. The live admin tile shows a
  different, deliberately harder number: a weekly leave-one-station-out
  **spatial** holdout on this week's field (n=24, ~79%) — predicting a
  station the model never saw.
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
  `outside_service_area`, never a fabricated route. Inside NCR, the
  unmonitored fringe (Sonipat-side ~15.7 km, Bahadurgarh/Ghaziabad rims
  5.5–12.4 km) is extrapolation — `nearest_sample_km` reports the distance
  to the nearest real reading instead of hiding it.
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
- **CPCB live feeds are geo-blocked** from the deployment network (WAQI +
  DPCC carry measured stations meanwhile); the OpenAQ live-key path is
  wired but dormant — documented in `server/data/field_validation.md`.
- **`/health` `build_sha` can lag the deployed image** by a deploy — the
  ECR task image tag is the truth (today `alive108-api:ce01ec5c` ==
  `/health` `build_sha`, `sources.stations` = `waqi+dpcc`, count 54).

## Repo layout

`server/` — FastAPI engine + `alive_core` C++ (pybind11) + public pages ·
`Mobile/` — Expo app (Android release target; iOS dev-only) — the
on-device dose ledger lives in `Mobile/src/store/ledger.ts` ·
`infra/` `scripts/` `tools/` — AWS provisioning, deploy, corpus, warm-up ·
`docs/` — the research + verification corpus (`docs/plan/` is the source of
truth; `docs/plan/10-claims-ledger.md` governs every number we show;
`docs/plan/alive-depth.md` is the dosimeter thesis).

*AI tools used are disclosed in the submission writeup.*
