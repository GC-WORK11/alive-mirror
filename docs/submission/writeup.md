# ALive-108 — Builder Center written submission

*Draft for the AWS × WeMakeDevs Environmental Hacks (Track 01 · Air) submission
form and the Builder Center long-form post. Every number below was read off the
live service or traced to a repo file on 2026-10-05 — re-verified ~22:15 UTC on
build `80a15258`, then extended 2026-10-06 on build `ce01ec5c` (the DPCC-ingest
deploy: **54 ground instruments live** — `GET /health` reports
`sources.stations.count=54`, `source:"waqi+dpcc"`; the independent-holdout
section is new). Grep-able sources in brackets.
`docs/plan/NUMBERS.md` is the canonical ledger;
`scripts/verify_numbers.sh` re-derives every figure live. Nothing is invented.*

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
take — and we never take a trip: donations fold into cell/hour/day aggregates
at ingest, so **no per-trip row exists in memory, on disk, or in S3**
[`docs/plan/alive-depth.md`; `PRIVACY.md`; `server/community.py`;
`GET /v2/city/moves` — live].

Exposure-aware routing is one feature inside it — the proof that the field and
the dose math are real enough to decide with.

## The architecture: field → engine → dose → ledger

- **Field.** A concentration surface rebuilt every 15 minutes from **54
  live ground instruments — 24 WAQI + 30 DPCC** (the second adapter shipped
  Oct 6 after our own holdout found the blind spots — see the holdout
  section below) + **~70 CAMS/open-meteo model samples** +
  **NASA FIRMS fire detections** (67 at last read, 15 in the NW belt; the
  claim is wind-gated — ×1.24 while the NW fetch carried, downscaled to
  ×1.08 and named-but-refused once the wind turned easterly), kriged with a
  real σ band per cell.
  Age on the wire at this read: ~2 min [`GET /health`, `GET /aqi` — live
  2026-10-05 ~22:15 UTC]. And once
  an hour the served field itself is written to durable storage — the archive
  snapshots the real served surface into S3 + a local mirror, hour-bucketed in
  IST: Delhi's air is *history*, not just forecast. `GET /v2/archive` replays
  a day hour-by-hour (`basis:"recorded"`); a missing hour stays an honest gap,
  never backfilled [`server/archive.py`, `server/v2/archive.py` — live].
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
  is trimmed on-device, then re-trimmed + thinned + rounded **server-side** and
  folded into ~500 m cells at ingest — no per-trip row exists in any store.
  Per-device history is readable only by the holder of the raw device token,
  and `DELETE /v2/ledger` wipes it [`server/v2/trip.py`, `server/v2/ledger.py`,
  `PRIVACY.md`].

## What the dosimeter answers today

Three questions, three shipped surfaces:

- **"What did today cost me?"** — the ledger: every trip's inhaled µg, on the
  phone, with the receipt (µg + CO₂ band + where it accumulated). The city side
  of the same ledger is public — a live counter (`GET /community`): 14
  contributors / 22 trips all-time, ~14.1 km / 477.3 µg *avoided* in the last
  24 h, and 725.9 µg of smoke counted as *avoided* all-time
  [`GET /community` — live, read Oct 6 ~03:50 IST — it grows daily].
- **"When is tomorrow's air worth going out in?"** — `GET /v2/day`: the
  morning card for a point — today's heavy window and cleanest slot with a
  real band each, plus the decisions they change. Live at Connaught Place
  tonight: cleanest slot **12:30–18:30 IST at ~45 µg/m³** against a ~105
  day mean, and the heavy stretch runs **22:30 IST → day end at ~159**
  ("open ~12:30–18:30; shut from ~22:30 IST" — three decision rows on the
  wire) [`GET /v2/day?lat&lon` — live].
- **"Where can my lungs go inside my budget?"** — `GET /v2/reach`: a bounded
  Dijkstra over the same directed-edge-state search as the router — no
  heuristic, no destination — settling every edge whose inhaled dose stays
  under `budget_ug`. The returned set is the real Dijkstra frontier as
  polylines, never a smoothed circle. Live tonight: a **25 µg walking budget
  from Connaught Place settles 3,211 road segments (~141 km of street —
  directed edges, so a two-way street counts in both directions)**;
  ≤50 µg walks 10,510 segments (~554 km); a sealed car on a **25 µg**
  budget settles ~891k edges, ~75,822 km (`edge_partial:true` — the
  2M-state cap binds; the veil paints the nearest 90,000)
  [`GET /v2/reach` — live;
  `server/v2/reach.py`; painted as the "where can your lungs go?" veil on
  `/city`].

## The feature the judges will poke: dose-priced routing

Same city, same minutes — the mode you pick decides what you inhale. Measured
live on the demo trip (Connaught Place → Gurugram, 23.7 km) tonight, 23 options
[`POST /v2/plan` — live, read 2026-10-05 ~22:16 UTC on build `80a15258`,
breathing-zone basis (`smoke_modifier: 1.09` on the wire); the count drifts
16–23 as transit rows come and go]:

| mode | inhaled dose (µg PM2.5, mid) | ≈µg/km |
|---|---|---|
| sealed AC car | **10.8** | ~0.5 |
| car, windows open | 19.6 | ~0.8 |
| bike / scooter | 24.8 | ~1.0 |
| bus | 28.3 | ~1.2 |
| auto-rickshaw | 32.0 | ~1.4 |
| metro + walk | — *(absent tonight — outside transit service hours)* | — |
| bus (GTFS timetable row) | 69.3 | ~2.9 |
| cycle | 158.8 | ~6.7 |
| **walk** | **358.3** | ~15 |

**~35× on a Delhi commute** (33.2× measured tonight; 31–45× across ODs this
week — it is a living ratio, not a constant) — and
it matches published Delhi measurements: walking inhales ≈28× the metro per
km, an auto-rickshaw ≈5× (Sci. Total Environ. 2021; Discover Atmosphere 2025 —
`server/exposure.py` header, `docs/03-models.md`). The honest surprise the
table shows on daytime reads: **metro+walk doses ~4× a sealed car** — the
coach is clean,
the road-level walks at both ends are not. The engine also returns least-dose
corridor alternates that must diverge ≥15% of length to count (measured
19–96% divergent) — "via Outer Circle vs via Vivekanand Marg", not one blessed
path [`docs/plan/demo-script.md` numbers sheet].

## What nobody else does

- **A field that moves.** `/v2/city` serves the next 12 hours hour-by-hour —
  tonight the lattice runs ~70 → ~151 µg/m³ into the ~03:00 IST peak, then
  falls to ~39 by ~09:00, driven by a
  120-hour CAMS forecast anchored to the live field (τ=9 h)
  [`GET /v2/city → next_hours`; `GET /depart` — live]. `/depart` answers
  "leave now or later?" in micrograms: same trip, ~29 µg now vs ~80 µg at
  tomorrow's worst hour, ~15 µg at the +12 h best (**~2.7×** now→worst
  tonight — it has run ~8× this week).
- **Privacy as architecture, not policy.** Donations fold into
  cell/hour/day aggregates at ingest — *no per-trip row exists in memory, on
  disk, or in S3*, so there is nothing per-person to leak, lose, or subpoena.
  The raw-coords `/observe` endpoint is retired (**410 Gone**); uvicorn's
  access log is off and the app's own request log writes path templates only,
  with coordinates and tokens on a denylist; the contributor id is a 64-bit
  CSPRNG that rotates every 30 days. And k≥3 everywhere: 12 of 54 tracked
  corridor cells are publishable today; the other 42 are honestly suppressed,
  the suppression field (`mode_share_suppressed_trips`) ships on the wire
  [`PRIVACY.md`; `server/community.py`, `server/observability.py`;
  `GET /community`, `GET /v2/city/moves` — live].
- **History, not just forecast.** Once per IST hour the API snapshots the
  field it is actually serving — mid, σ band, confidence, source counts —
  into durable storage (`archive/field-YYYYMMDDHH.json.gz` on S3 + a local
  mirror). `GET /v2/archive` replays a day hour-by-hour; gaps are serialized
  as gaps, never interpolated. Recording since Oct 5 — the `/admin` archive
  tile shows it live [`server/archive.py`; `GET /v2/archive` — live].
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
| Live instruments feeding the field | **54 stations** — 24 WAQI + 30 DPCC (`source:"waqi+dpcc"` on the wire since Oct 6) + ~70 model samples, field age ~8 min, 15-min refresh visible | `GET /aqi`, `GET /health` |
| LOO calibration vs live instruments | MAE 46.1 µg/m³, bias +0.3, n=94 | `GET /aqi → calibration` |
| Archive replay (clean-air window) | MAE 22.0 µg/m³, bias +51.6 % — we publish that we over-read in clean air | `server/data/field_validation.md` |
| Plan latency | ~0.8 s warm measured today; fresh unseen ODs ~2–8 s | `POST /v2/plan → took_ms` |
| Reach latency | ~1–2 s wire on walk budgets ≤50 µg; ~5–10 s for a ~890k-edge car reach (partial — 2M-state cap) | `GET /v2/reach` |
| Mode dose gap, CP→Gurugram | **~35× on a Delhi commute** — 33.2× live tonight (build `80a15258`, bz basis); 31–45× across ODs this week | live probe + `docs/plan/demo-script.md` |
| Search | 97,447 corpus entries (16,949 real address rows); 172/174 top-1 in a live battery (98.9 %), p50 ~470 ms over the NLB; bundled on-device gazetteer 124,311 rows | `server/data/corpus/STATS.md`, `docs/plan/demo-script.md` |
| Engine speed | C++ search index p50 0.189 ms — ~88× the Python twin, asserted bit-identical | `docs/plan/bench-results.md` |
| Self-hosted basemap | 22.7 MB pmtiles built from Geofabrik OSM, z0–14, live at `/tiles/health` | `GET /tiles/health` |
| Landmark-truth sweep | 23 fabricated landmark geocodes purged; top-3 of every flagship query must land within 1.5 km of truth — pinned by `test_search_quality.py` | commit `2c4cab4` |

## The holdout we ran on ourselves — and what we did about it

On the evening of Oct 6 we audited the served field against **30 government
DPCC stations** — a different instrument network than anything the field
ingests — classifying each site by whether the field provably cannot see it
(`nearest_sample_km ≥ 1.0` = blind). Three probe rounds, 81 observations,
nothing tuned, nothing filtered [`docs/lanes/accuracy-holdout-report.md`]:

| class | stations | obs | MAE µg/m³ | RMSE | bias |
|---|---|---|---|---|---|
| GAP — provably blind (1.5–5.8 km) | 7 | 16 | **22.8** | 26.5 | +3.2 (+6%) |
| LIVE-ADJ — instrument in the blend | 6 | 16 | **16.4** | 19.3 | −9.2 |
| ANCHOR — model point on-site | 17 | 49 | **31.9** | 39.8 | −24.6 |
| **All 30 sites** | 30 | 81 | **27.1** | 34.2 | −16.0 |

The blind sites were the *best-behaved* class (~23 MAE, ~zero bias) — but the
misses were real at anchors: Jahangirpuri read 143 while we served 73 (−68),
Sonia Vihar −63, Rohini −53. Local hotspots flare up to 2× past a blend built
from instruments elsewhere; that's exactly why the API serves a band plus the
distance to the nearest real reading, not a confident point.

Then we closed them: `server/ingest_dpcc.py` ingests those same DPCC 5-min
pages behind `ALIVE_DPCC_INGEST` — the site's nav bar hides a 30-station
superset whose 6 unlisted stations were precisely our blind spots (IGNOU, JNU,
CWG Akshardham, NSUT West, Talkatora, SBV Delhi Cantt). Unit tokens are
asserted per row (µg/m³ refused if the site ever switches to indices); stale
and physically impossible rows (PM2.5 > PM10) are dropped. **Live since Oct 6
(build `ce01ec5c`): all 7 former blind spots now carry an instrument at ~0 km**
[`docs/lanes/ingest-dpcc-report.md`].

And a second live watch ran the same evening — 14 probes across ~8 h of the
parali ramp, through three mid-watch deploys: the stubble-fire claim followed
the wind *both* directions (claimed ×1.24 at 344°, refused ×1.07–1.08 at
15°→139° easterly, math re-derived per probe), the trend recorder caught the
regime flip live (−7.5 → +35.7 µg over ~6 h), and one dose-ratio flag
decomposed to a verified spatial gradient, not a scaling bug
[`docs/lanes/field-watch-2-report.md`].

## Where AWS fits (deployed, not claimed)

- **ECS Fargate** (ap-south-1, FARGATE_SPOT, 1 vCPU / 3 GB) runs the FastAPI
  service + C++ pybind engine + osrm-local router sidecar — one service, one
  task; the deploy reports `build_sha ce01ec5c` (the DPCC-ingest build) on
  the open wire [`GET /health` — live; the ECR image tag is the commit
  sha].
- **Network Load Balancer + Elastic IP** gives the stable public URL above
  (`alive108-….elb.ap-south-1.amazonaws.com`, resolving to 65.2.28.40) — it
  survives every redeploy; each deploy re-registers the live task's IP.
- **CodeBuild → ECR → task definition**: every deploy builds the image in
  AWS (`buildspec.yml` → docker build → push → `update-service`).
- **S3** keeps the last-good field snapshot (the field survives task
  restarts), the community aggregate state, the hourly field archive
  (`archive/field-*.json.gz`), and the pmtiles artifact that
  hot-swaps into running tasks.
- **DynamoDB** (`alive108-agg`) holds only aggregate trip counters — no user
  rows exist anywhere.
- **Secrets Manager** holds the admin token + upstream keys — nothing in the
  repo.
- **EventBridge Scheduler** (`alive108` group) drives the 15-minute
  field-rebuild cadence plus a daily rollup and a weekly validation schedule
  [`infra/provision.sh`].
- **CloudWatch + Budgets** — a field-age alarm (missing data breaches, not
  just errors), the ops dashboard, and a $50/month budget alarm.
- **OpenAQ's public S3 archive** is the decade climatology source
  (125 stations × a decade of hourly readings, medians by month×hour,
  baked into the image).
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
- Community data is young — 14 contributors, ~14.1 km / 6 donated trips in
  the last 24 h (22 trips all-time; read Oct 6 ~03:50 IST — live counters
  at `GET /community`).
  The k≥3 floor means the corridor table is honestly sparse.
- `/v2/day` is the morning card's *data* — the card surface itself rides the
  app's ledger today; the endpoint is public JSON for the same answer.
- One task, one region (NCR-only), HTTP :80 only — no custom domain yet.
- CPCB live feeds are geo-blocked from our network (documented in
  `field_validation.md`) — WAQI + DPCC carry the measured-instrument role
  meanwhile; the CPCB adapter reports itself dormant rather than pretend.
- The met-wind feed intermittently reports `known:false` for a refresh or two
  (upstream Open-Meteo reachability) — it says so on the wire instead of
  serving a stale vector.

## Impact, provably

We can't claim "Delhi got cleaner." We can and do show: an individual's
inhaled dose cut by about thirty-five times on the same trip (~35× on a
Delhi commute; 33.2× measured tonight) and the cleanest hours of
their day named with a real band; N trips switched to a lower-smoke option,
counted and auditable on the dashboard; and the first street-level, per-hour
picture of what Delhi commuters actually breathe — aggregate,
privacy-floored, and growing with every donated trip.
