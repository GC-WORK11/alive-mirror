# ALive-108 — Builder Center written submission

*Draft for the AWS × WeMakeDevs Environmental Hacks (Track 01 · Air) submission
form and the Builder Center long-form post. Every number below was read off the
live service or traced to a repo file on 2026-10-05 — grep-able sources in
brackets. Nothing is invented.*

**Live now:** http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com
(public API + dashboards; `GET /health` is open)

---

## The lede

**Your lungs' ledger for Delhi: what you breathed today, where it cost you, and
when tomorrow's air is worth going out in — no device, no uploads.**

Delhi is the most polluted megacity on earth — winter PM2.5 runs 10–20× the WHO
guideline through October–February [`docs/00-executive-thesis.md`]. Every tool
people have today sells *"how bad is it"* — an AQI lookup. The graveyard says
that doesn't retain: Plume Labs' $200 hardware dosimeter was discontinued in
2023; BreezoMeter's consumer app was killed twice [`docs/plan/alive-depth.md`].
What retains is *"what do I do"* — and nobody has ever shipped the personal
measurement that makes it answerable.

## The product

**ALive-108 is a personal PM2.5 dosimeter without hardware.** Personal-exposure
reconstruction — timeline × concentration surface → individual dose — is an
established research method that nobody ships to consumers; Plume needed a
device, we need nothing. The concentration field is already sampled per-cell
per-hour, and the phone already knows where it was. Your day is reconstructed
**on-device** — the only things that ever leave the phone are consented,
privacy-floored aggregates (nothing publishes below **k=3 distinct devices
over 72 h** — `min_k` is literally on the wire). We can't leak what we never
take [`docs/plan/alive-depth.md`; `Mobile/src/store/ledger.ts`;
`GET /v2/city/moves` — live].

Exposure-aware routing is one feature inside it — the proof that the field and
the dose math are real enough to decide with.

## The architecture: field → engine → dose → ledger

- **Field.** A concentration surface rebuilt every 15 minutes from **~23–24
  live WAQI ground instruments** + **~60–70 CAMS/open-meteo model samples** +
  **NASA FIRMS fire detections** (71 today, 16 inside the smoke belt → ×1.27
  modifier), kriged with a real σ band per cell. Age on the wire today: ~4 min
  [`GET /health`, `GET /aqi` — live].
- **Engine.** Our own C++ engine (`alive_core`, pybind) with a bit-exact Python
  twin — kriging, dose integration, and path search. The A* twin and the new
  bounded-Dijkstra reach are asserted to settle the *identical* edge set on
  both engines, and the dose/emission kernels are parity-tested to 1e-9
  ("bit-identical in practice") [`server/tests/test_reach.py`,
  `test_parity_dose.py`, `test_parity_series.py`]. That engine re-prices
  **1,070,459 road edges (903,058 priced)** so dose is a first-class routing
  criterion [`GET /health → routing` — live].
- **Dose.** Honest physics, not a lookup:
  > dose = concentration (µg/m³) × micro-environment factor × ventilation rate
  > (L/min) × time — integrated every ~250 m along the actual route geometry.
  Micro-environment and ventilation are anchored to measured Delhi commuter
  literature (Goel 2015, Apte 2011, Zuurbier 2009), not defaults
  [`server/exposure.py`, `docs/03-models.md`].
- **Ledger.** Trips receipt in µg and persist to `ledger.json` **on the phone**
  (500-trip cap, delete-all, no account). Donation is opt-in: a donated trip
  is trimmed on-device, hashed, and becomes an aggregate — per-device history
  is readable only by the holder of the raw device token, and `DELETE
  /v2/ledger` wipes it [`server/v2/ledger.py`, `server/v2/trip.py`].

## What the dosimeter answers today

Three questions, three shipped surfaces:

- **"What did today cost me?"** — the ledger: every trip's inhaled µg, on the
  phone, with the receipt (µg + CO₂ band + where it accumulated). The city side
  of the same ledger is public: 12 contributors, 18.1 km donated in the last
  24 h, 333.5 µg of smoke counted as *avoided* [`GET /community` — live].
- **"When is tomorrow's air worth going out in?"** — `GET /v2/day`: the
  morning card for a point — today's heavy window and cleanest slot with a
  real band each, plus the decisions they change. Live at Connaught Place
  today: heavy stretch **21:30–23:30 IST at ~247 µg/m³**, cleanest slot
  **17:30–19:30 at ~94**, against a ~177 day mean — "outdoor exercise:
  least-bad window ~17:30–19:30", "kids outdoors: before ~21:30", "windows
  open ~17:30–19:30, shut from ~21:30" [`GET /v2/day?lat&lon` — live].
- **"Where can my lungs go inside my budget?"** — `GET /v2/reach`: a bounded
  Dijkstra over the same directed-edge-state search as the router — no
  heuristic, no destination — settling every edge whose inhaled dose stays
  under `budget_ug`. The returned set is the real Dijkstra frontier as
  polylines, never a smoothed circle. Live today: a **25 µg walking budget
  from Connaught Place settles 2,473 road segments (~107 km of street —
  directed edges, so a two-way street counts in both directions)**;
  ≤50 µg walks 9,524 segments (~490 km); a sealed car on a **10 µg**
  budget settles ~580k edges, ~39,500 km [`GET /v2/reach` — live;
  `server/v2/reach.py`; painted as the "where can your lungs go?" veil on
  `/city`].

## The feature the judges will poke: dose-priced routing

Same city, same minutes — the mode you pick decides what you inhale. Measured
live on the demo trip (Connaught Place → Gurugram, 23.7 km) today, 16 options
[`POST /v2/plan` — live]:

| mode | inhaled dose (µg PM2.5, mid) | ≈µg/km |
|---|---|---|
| sealed AC car | **5.7** | ~0.2 |
| car, windows open | 10.4 | ~0.4 |
| bike / scooter | 13.1 | ~0.6 |
| bus | 15.0 | ~0.6 |
| auto-rickshaw | 16.9 | ~0.7 |
| metro + walk | 26.4 | ~1.0 |
| cycle | 84.1 | ~3.5 |
| **walk** | **189.7** | ~8 |

**~33× spread on one trip** (32.7× and 38.5× measured on two other ODs) — and
it matches published Delhi measurements: walking inhales ≈28× the metro per
km, an auto-rickshaw ≈5× (Sci. Total Environ. 2021; Discover Atmosphere 2025 —
`server/exposure.py` header, `docs/03-models.md`). The honest surprise the
table shows: **metro+walk doses ~4.6× a sealed car** — the coach is clean,
the road-level walks at both ends are not. The engine also returns least-dose
corridor alternates that must diverge ≥15% of length to count (measured
19–96% divergent) — "via Outer Circle vs via Vivekanand Marg", not one blessed
path [`docs/plan/demo-script.md` numbers sheet].

## What nobody else does

- **A field that moves.** `/v2/city` serves the next 12 hours hour-by-hour —
  today the lattice runs ~76 → ~231 µg/m³ into the evening peak, driven by a
  120-hour CAMS forecast anchored to the live field (τ=9 h)
  [`GET /v2/city → next_hours`; `GET /depart` — live]. `/depart` answers
  "leave now or tonight?" in micrograms: same trip, ~17 µg now vs ~104 µg at
  the evening peak (**~6×** today — it has run ~8× this week).
- **Privacy as math, not policy.** k≥3 everywhere: 10 of 54 tracked corridor
  cells are publishable today; the other 44 are honestly suppressed, and the
  suppression field (`mode_share_suppressed_trips`) ships on the wire
  [`GET /community`, `GET /v2/city/moves` — live].
- **Emissions alongside dose.** Each option carries a CO₂ + tailpipe-PM2.5
  band on real Delhi fleet factors (BS-class, fuel, idle, cold-start) —
  metro+walk: 0.42 kg CO₂, zero tailpipe PM [`/v2/plan` wire].
- **The ledger is yours.** On-device file, no account, opt-in donation,
  delete-all on the phone and `DELETE /v2/ledger` on the server — the
  receipt says "kept on this phone only" and means it.

## Working execution — the numbers we measured, not claimed

| claim | value | source |
|---|---|---|
| Held-out uncertainty-band coverage | **95.2 %** at ±2σ over **3,550 station-hours / 85 stations** (nominal 95.4 %) — σ is measured, not tuned | `server/data/field_validation.md` |
| Live instruments feeding the field | **~23–24 WAQI stations** + ~60–70 model samples, field age ~4 min, 15-min refresh visible on the wire | `GET /aqi`, `GET /health` |
| LOO calibration vs live instruments | MAE 46.1 µg/m³, bias +0.3, n=94 | `GET /aqi → calibration` |
| Archive replay (clean-air window) | MAE 22.0 µg/m³, bias +51.6 % — we publish that we over-read in clean air | `server/data/field_validation.md` |
| Plan latency | ~0.9 s warm measured today; fresh unseen ODs 2–8 s | `POST /v2/plan → took_ms` |
| Reach latency | 15–31 ms warm on walk budgets ≤50 µg; ~1.2 s for a ~580k-edge car reach | `GET /v2/reach → took_ms` |
| Mode dose gap, CP→Gurugram | **~33×** walk vs sealed car (live today); 32.7× and 38.5× on two other ODs | live probe + `docs/plan/demo-script.md` |
| Search | 97,447 corpus entries (16,949 real address rows); 172/174 top-1 in a live battery (98.9 %), p50 ~470 ms over the NLB; bundled on-device gazetteer 123,934 rows | `server/data/corpus/STATS.md`, `docs/plan/demo-script.md` |
| Engine speed | C++ search index p50 0.189 ms — ~88× the Python twin, asserted bit-identical | `docs/plan/bench-results.md` |
| Self-hosted basemap | 22.7 MB pmtiles built from Geofabrik OSM, z0–14, live at `/tiles/health` | `GET /tiles/health` |
| Landmark-truth sweep | 23 fabricated landmark geocodes purged; top-3 of every flagship query must land within 1.5 km of truth — pinned by `test_search_quality.py` | commit `2c4cab4` |

## Where AWS fits (deployed, not claimed)

- **ECS Fargate** (ap-south-1, FARGATE_SPOT, 1 vCPU / 3 GB) runs the FastAPI
  service + C++ pybind engine + osrm-local router sidecar — one service, one
  task, verified `ACTIVE 1/1` on task-def `alive108:147`, image tag
  `alive108-api:1e93b9f2` [`aws ecs describe-services` — live].
- **Network Load Balancer + Elastic IP** (65.2.28.40) gives the stable public
  URL above — it survives every redeploy.
- **CodeBuild → ECR → task definition**: every deploy builds the image in
  AWS (`buildspec.yml` → docker build → push → `update-service`).
- **S3** keeps the last-good field snapshot (the field survives task
  restarts), the community aggregate state, and the pmtiles artifact that
  hot-swaps into running tasks.
- **DynamoDB** (`alive108-agg`) holds only aggregate trip counters — no user
  rows exist anywhere.
- **Secrets Manager** holds the admin token + upstream keys — nothing in the
  repo.
- **OpenAQ's public S3 archive** is the decade climatology source
  (9M station-hours, 125 stations, baked into the image).
- Cost: ~**$46/month** worst case inside the $200 event credits; Fargate Spot
  runs it near-zero outside demo windows.

## Design & usability

A judge can use it without us: `/` is the dosimeter landing ("the field knows
what Delhi breathed — the app knows what you breathed") over a live field
canvas with a 12-hour scrubber and a→b dose routing; `/city` is Delhi's
public ledger — district choropleth, the day-in-dose ticker, corridors, and
the lung-reach veil; `/community` is the donation ledger; `/admin` is the
engine room (pipeline provenance, per-feed trust table, field map with real
FIRMS detections, engine internals). The consumer app (Android release,
one Expo codebase) is FROM→TO→ranked modes plus the on-device dose ledger.
Public JSON endpoints are self-describing — every estimate carries its band,
its basis ("est."), and the field's own age.

## What we do not claim (this is a feature, not a disclaimer)

- Phones measure nothing — traversals adjust dose *estimates*, never the
  field. Per-vehicle emissions are fleet-class bands; per-vehicle truth is
  unknowable.
- The forecast is CAMS + stagnation physics, not ground truth — and the field
  says so itself: `coverage < 1` at the edge, `confidence:"low"` on thin cells,
  a typed `outside_service_area` for Mumbai instead of a fabricated route,
  `null` where a feed serves nothing (ammonia today — the eleventh species
  is honestly empty).
- Community data is young — 12 contributors, ~18 km donated in the last day.
  The k≥3 floor means the corridor table is honestly sparse.
- `/v2/day` is the morning card's *data* — the card surface itself rides the
  app's ledger today; the endpoint is public JSON for the same answer.
- One task, one region (NCR-only), HTTP :80 only — no custom domain yet.
- CPCB live feeds are geo-blocked from our network (documented in
  `field_validation.md`) — WAQI carries the measured-instrument role
  meanwhile; the CPCB adapter reports itself dormant rather than pretend.
- The met-wind feed intermittently reports `known:false` for a refresh or two
  (upstream Open-Meteo reachability) — it says so on the wire instead of
  serving a stale vector.

## Impact, provably

We can't claim "Delhi got cleaner." We can and do show: an individual's
inhaled dose cut by up to ~33× on the same trip and the cleanest hours of
their day named with a real band; N trips switched to a lower-smoke option,
counted and auditable on the dashboard; and the first street-level, per-hour
picture of what Delhi commuters actually breathe — aggregate,
privacy-floored, and growing with every donated trip.
