# docs/17 — Submission writeup (draft)

Paste-ready for the hackathon submission form: problem, build, where AWS fits.

> **Status note (2026-10-06):** the canonical submission text now lives in
> `docs/submission/writeup.md` — use that. This draft is kept for its
> framing; several figures below were corrected in place (stations, IAM,
> secrets, deploy path) but the polished prose moved on.

## Problem

Delhi is the most polluted megacity on earth — winter PM2.5 regularly
runs 10–20× the WHO guideline. Every resident commutes through it twice
a day, and until now the cost was invisible: Google Maps, Uber and
Rapido optimise for time and money, never for what the trip puts in
your lungs. Delhi also has a coverage problem — government monitors
sparsely cover NCR, so most streets have no measurement at all.

## Build

ALive-108 is a consumer app (Android + iOS, one codebase) that puts an
air price on every trip: pick FROM→TO and see the actual PM2.5 you'd
inhale by car, auto, bus, metro, bike or on foot — ranked by a
safety-first decision engine (50% dose + 30% mode crash-risk anchored
to MoRTH fatality shares + 20% time). Underneath is a real physics
stack, not an AQI lookup: live station/CAMS field kriged in our own C++
engine with a fitted nowcast blend on the wire, breathing-zone
microenvironment factors measured on
Delhi roads, per-segment dose colouring, a 120-hour forecast with a
"leave later" optimizer, and a climatology built from 125 NCR stations
× ~10 years of public archive data (`/history.source` — the honest
description; "9.04M measurements" was the raw-row count, never
independently re-verified). The Lung Ledger turns every trip into
cigarette-equivalents and avoided-µg. And every journey donates an
anonymous traversal to a shared community layer — commuters become the
sensor grid covering streets no station can see, plus live hazard flags
(dust/smoke/burning/clean). An ops dashboard (/admin) shows the city
breathing in real time.

## Where AWS fits (deployed, not claimed)

- **ECS Fargate** (serverless containers) runs the FastAPI decision
  engine in `ap-south-1` — `server/Dockerfile` + `scripts/deploy.sh`
  (`server/deploy-aws.sh` is a deprecated shim that execs it). One task
  carries the API plus a self-hosted `osrm-routed` sidecar
  (`OSRM_URL=127.0.0.1:5000`).
- **Network Load Balancer + Elastic IP** give a stable public URL that
  survives redeploys: `http://65.2.28.40` (live now).
- **Secrets Manager** holds `alive108/openaq`, `alive108/waqi` and
  `alive108/admin-token`, injected into the task — no credentials in
  the repo (`scripts/deploy.sh` secrets block).
- **ECR** hosts the container image; **CodeBuild** builds it in-cloud
  (the video can literally watch the build run).
- **S3** stores the climatology the decade-typical numbers come from
  (125 NCR stations × ~10 years; OpenAQ's archive is itself S3).
- **DynamoDB** (`alive108-agg`) holds the community aggregates — trips,
  corridor cells, per-device ledger (30-day TTL on cells).
- **EventBridge** runs the daily rollup + field-validation jobs on
  one-off Fargate tasks (`infra/schedules/`, enabled live per
  `docs/plan/handoff.md`; the 15-min ingest schedule stays disabled —
  the in-app `ALIVE_INGEST_IN_APP` loop owns that cadence).

## Validation — the part most projects skip

We measured the field against itself: leave-one-out over the 70 live
WAQI+DPCC instruments — a krige refit per held-out station — gives
**MAE 8.8 µg/m³, mean bias +0.2**; at an instrument the field reads
the instrument itself. CAMS alone under-reads Delhi 2–8× at hotspots;
the server de-biases every model sample against nearby instruments
before interpolating. Numbers served live at `/aqi` → `calibration`.

53-check live suite (`server/test_api.py` — 53 `check(` calls) plus a
981-test pytest suite (`server/tests/`) hit every endpoint against
live upstreams — no mocks.

## Impact

Honest scope: the app cannot remove Delhi's emissions — no app can.
What it does and proves: cuts an individual's inhaled dose by up to ~30×
on the same trip (live, verified numbers), converts avoidance into a
countable ledger (µg avoided, city-wide), and builds the first
community traversal map of exposure in NCR — data that exists nowhere
else and grows with every user.
