# ALive-108 — Builder Center written submission

*Draft for the AWS × WeMakeDevs Environmental Hacks (Track 01 · Air) submission
form and the Builder Center long-form post. Every number below was read off the
live service or traced to a repo file on 2026-10-05 — grep-able sources in
brackets. Nothing is invented.*

**Live now:** http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com
(public API + dashboards; `GET /health` is open)

---

## The lede

Google Maps optimizes for minutes. ALive-108 optimizes for breaths.

Delhi is the most polluted megacity on earth — winter PM2.5 runs 10–20× the WHO
guideline through October–February, and every resident commutes through it twice
a day [`docs/00-executive-thesis.md`]. The tools people have today all stop at
information: AQI dashboards, colour-coded maps, "stay indoors" advisories.
None of them answers the question a commuter actually faces — *which way do I
go, and what does each option cost my lungs?*

## The build

ALive-108 is an exposure-aware routing engine for Delhi NCR. You give it
FROM→TO; it returns every real way to make the trip — car (AC/open), auto,
bus, metro+walk on live GTFS, bike, cycle, walk — each with an ETA and a
measured estimate of **inhaled PM2.5 in micrograms**, not an AQI colour.

The dose math is honest physics, not a lookup:

> dose = concentration (µg/m³) × micro-environment factor × ventilation rate
> (L/min) × time — integrated every ~250 m along the actual route geometry.

The concentration field underneath is rebuilt every 15 minutes from **24 live
WAQI ground instruments** + **68 CAMS/open-meteo model samples** + **NASA FIRMS
fire detections** (71 today, 16 inside the smoke belt → ×1.27 smoke modifier),
kriged by our own C++ engine (`alive_core`) with a real σ band per cell
[`GET /health`, `GET /aqi` — live]. That field re-prices **1,070,459 road edges
(903,058 priced)** so the least-dose path is a first-class routing criterion,
not a post-hoc annotation [`GET /health → routing` — live].

## What changes for a commuter

Same city, same minutes — the mode you pick decides what you inhale. Measured
live on the demo trip (Connaught Place → Gurugram, 23.7 km) today
[`POST /v2/plan` — live]:

| mode | inhaled dose (µg PM2.5) | ≈µg/km (same 23.7 km) |
|---|---|---|
| sealed AC car | **5.4** | ~0.2 |
| car, windows open | 9.7 | ~0.4 |
| bus | 14.0 | ~0.6 |
| auto-rickshaw | 15.8 | ~0.7 |
| metro + walk | 24.5 | ~1.0 |
| cycle | 78.7–84.3 | ~3.5 |
| **walk** | **177.5–198.4** | ~8 |

**~33–37× spread on one trip** (up to ~38× measured on other ODs) — and it
matches published Delhi measurements: walking inhales ≈28× the metro per km,
an auto-rickshaw ≈5× (Sci. Total Environ. 2021; Discover Atmosphere 2025 —
`server/exposure.py` header, `docs/03-models.md`). The honest surprise the
table shows: **metro+walk doses ~4.5× a sealed car** — the coach is clean, the
road-level walks at both ends are not. No map tells you that today.

## What nobody else does

- **A field that moves.** `/v2/city` serves the next 12 hours hour-by-hour —
  today the lattice swings ~43 → ~298 µg/m³ (**~6.8×**) between morning and the
  evening peak, driven by a 120-hour CAMS forecast anchored to the live field
  (τ=9 h) [`GET /v2/city → next_hours`; `GET /depart` — live]. `/depart`
  answers "leave now or at 6 pm?" in micrograms: same trip, 15.7 µg now vs
  130.7 µg at the evening peak (**~8×**).
- **The mode-dose ladder.** Per-mode micro-environment and ventilation factors
  anchored to measured Delhi commuter literature (Goel 2015, Apte 2011,
  Zuurbier 2009) — not defaults — give the dose-per-mode table above, and a
  live "breathing" counter while you ride.
- **Privacy as math, not policy.** Every donated trip becomes an aggregate
  reading — but nothing publishes below **k=3 distinct devices over 72 h**
  (`min_k`, `mode_share_suppressed_trips` are literally on the wire). 10 of 54
  tracked corridors are publishable today; the other 44 are honestly
  suppressed, not hidden [`GET /community`, `GET /v2/city/moves` — live].
- **Emissions alongside dose.** Each option carries a CO₂ + tailpipe-PM2.5
  band on real Delhi fleet factors (BS-class, fuel, idle, cold-start) —
  metro+walk: 0.42 kg CO₂, zero tailpipe PM; car: 1.8–5.2 kg CO₂
  [`docs/plan/demo-script.md` numbers sheet, verified on the wire].

## Working execution — the numbers we measured, not claimed

| claim | value | source |
|---|---|---|
| Held-out uncertainty-band coverage | **95.2 %** at ±2σ over **3,550 station-hours / 85 stations** (nominal 95.4 %) — σ is measured, not tuned | `server/data/field_validation.md` |
| Live instruments feeding the field | **24 WAQI stations** + 68 model samples, field age ~5 min, 15-min refresh visible on the wire | `GET /aqi`, `GET /health` |
| LOO calibration vs live instruments | MAE 46.1 µg/m³, bias +0.3, n=94 | `GET /aqi → calibration` |
| Archive replay (clean-air window) | MAE 22.0 µg/m³, bias +51.6 % — we publish that we over-read in clean air | `server/data/field_validation.md` |
| Plan latency | ~0.4 s warm measured today (0.55–0.63 s in rehearsal); fresh unseen ODs 2–7 s | `POST /v2/plan → took_ms` |
| Mode dose gap, CP→Gurugram | **~33–37×** walk vs sealed car (live today); 32.7× and 38.5× on two other ODs | live probe + `docs/plan/demo-script.md` |
| Search | 97,447 corpus entries (16,949 real address rows); 172/174 top-1 in a live battery (98.9 %), p50 471 ms over the NLB | `server/data/corpus/STATS.md`, `docs/plan/demo-script.md` |
| Engine speed | C++ search index p50 0.189 ms — ~88× the Python twin, asserted bit-identical | `docs/plan/bench-results.md` |
| Self-hosted basemap | 22.7 MB pmtiles built from Geofabrik OSM, z0–14, live at `/tiles/health` | `GET /tiles/health` |

## Where AWS fits (deployed, not claimed)

- **ECS Fargate** (ap-south-1, FARGATE_SPOT, 1 vCPU/2 GB) runs the FastAPI
  service + C++ pybind engine + osrm-local router sidecar — one task, one
  container, verified `ACTIVE 1/1` on task-def `alive108:142`.
- **Network Load Balancer + Elastic IP** (65.2.28.40) gives the stable public
  URL above — it survives every redeploy.
- **CodeBuild → ECR → task definition**: every deploy builds the image in
  AWS (`buildspec.yml` → docker build → push → `update-service`).
- **S3** keeps the last-good field snapshot (the field survives task
  restarts) and the community aggregate state (survives redeploys —
  Fargate's filesystem is ephemeral, the layer is not).
- **DynamoDB** (`alive108-agg`) holds only aggregate trip counters — no user
  rows exist anywhere.
- **Secrets Manager** holds the admin token + upstream keys — nothing in the
  repo.
- **OpenAQ's public S3 archive** is the decade climatology source
  (9M station-hours, 125 stations, baked into the image).
- Cost: ~**$46/month** worst case inside the $200 event credits; Fargate Spot
  runs it near-zero outside demo windows.

## Design & usability

A judge can use it without us: `/` is a live map (real `/grid` cells on true
NCR geography, real wind vector, a 12-hour scrubber that walks actual forecast
surfaces); pick a→b and it draws the least-dose route. The consumer app
(Android + iOS, one Expo codebase) is FROM→TO→ranked modes — one tap to the
answer. `/admin` is a live ops board (28-district choropleth, species layers,
corridor table). Public JSON endpoints are self-describing — every estimate
carries its band, its basis ("est."), and the field's own age.

## What we do not claim (this is a feature, not a disclaimer)

- Phones measure nothing — traversals adjust dose *estimates*, never the
  field. Per-vehicle emissions are fleet-class bands; per-vehicle truth is
  unknowable.
- The forecast is CAMS + stagnation physics, not ground truth — and the field
  says so itself: `coverage < 1` at the edge, `confidence:"low"` on thin cells,
  a typed `outside_service_area` for Mumbai instead of a fabricated route.
- Community data is young — 12 contributors, ~18 km donated in the last day.
  The k≥3 floor means the corridor table is honestly sparse.
- One task, one region (NCR-only), HTTP :80 only — no custom domain yet.
- CPCB live feeds are geo-blocked from our network (documented in
  `field_validation.md`) — WAQI carries the measured-instrument role meanwhile.

## Impact, provably

We can't claim "Delhi got cleaner." We can and do show: an individual's
inhaled dose cut by up to ~37× on the same trip; N trips switched to a
lower-smoke option, counted and auditable on the dashboard; and the first
street-level, per-hour picture of what Delhi commuters actually breathe —
aggregate, privacy-floored, and growing with every donated trip.
