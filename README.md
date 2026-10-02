# Delhi-Air-108

**Exposure-aware trip engine for Delhi.** You type FROM → TO. It returns real routes — road *and* metro — ranked by estimated inhaled pollution dose, with honest uncertainty and the time cost of breathing cleaner.

Built for [AWS × WeMakeDevs Environmental Hacks](https://www.wemakedevs.org/aws/env), Track 01 (Air). Delhi-only by design.

## Why this exists

Every AQI app in India tells you the air is bad. None of them tell you what to **do** about it on a Tuesday at 8:40 AM when you have to get from Rohini to Nehru Place. This product answers one question:

> *Which way of moving through Delhi exposes me to the least pollution — and what does it cost me in time?*

## The core insight (measured, not modeled)

Published Delhi microenvironment studies show the mode you choose matters more than the road you take:

- Inhaled PM2.5 per km: **walking ≈ 28×, auto-rickshaw ≈ 5× the metro** ([sources](docs/03-models.md))
- AC car / metro / AC bus are the lowest-exposure modes; bicycle is the highest
- Morning rush hour is the worst dose window of the day

So the highest-leverage "route" in Delhi is often **not a different road — it's a different mode**. Existing clean-air routers (incl. the 2026 LEAP study on Delhi) only re-route cars. We route *decisions*.

## What's built (live, verified)

**Public API on AWS:** `http://65.2.28.40` (ECS Fargate + NLB + Elastic IP,
`ap-south-1`). Open `http://65.2.28.40/health` in a browser — live now.

`server/` — the dose engine (FastAPI, real data only):

- `GET /compare` — one trip, every mode ranked by inhaled PM2.5.
- `GET /decide` — safety-first ranking: dose + MoRTH-anchored mode risk +
  time, with a plain-English reason per option ("breathes least").
- `GET /depart` — the same trip across the next 120 h of forecast field +
  boundary-layer stagnation physics.
- `GET /shift` — occupational dose for Delhi's gig drivers: an 8-hr
  two-wheeler shift ≈ 1.1–1.5 cigarette-equivalents on heavy days.
- `GET /aqi` — interpolated PM2.5 at any NCR point + dust, AOD, US-AQI,
  rain/visibility, wind, GRAP-indicative stage, and the **leave-one-out
  calibration** of the field itself (MAE 46 µg/m³, bias +0.3, n=94
  real instruments — honest error, served next to the data).
- `GET /grid` (+`?h=0–120`) — the PM2.5 field as a forecast surface;
  `GET /today` — the 24h decade-median curve at a point.
- `GET /search` `/reverse` `/route` — real OSM/Photon geocoding + OSRM
  routes with per-route dose and synthesized quieter-road alternates.
- `GET /reports` `/community` `/observe` `/report` — the contribution
  layer: anonymized traversals + hazard reports, corridor analytics.
- `GET /admin` `/admin/api` — live ops board (users, journeys, km,
  µg avoided, corridors, recent feed).

The field blends **105 live CPCB/DPCC/HSPCB instruments** (OpenAQ v3)
with the CAMS model grid — model samples spatially de-biased against
the instruments before interpolation (CAMS under-reads Delhi 2–8× at
hotspots; LOO proved it, then we fixed it).

`Mobile/` — iOS + Android (Expo/RN, MapLibre): FROM→TO search with real
suggestions, dose-ranked mode card with per-segment dose-colored route,
Lung Ledger (daily µg → cigarette-equivalents, budget %, avoided total,
24h typical sparkline), journeys drawer (week bars, streak, city rollup),
Ambient Mode (always-on glance), horizon scrubber (now→+24h field),
live-location puck + recenter, hazard reporting, quieter-road lever.

`Bridge/` — the shared wire contract so app and server can never drift.

**Tests:** `server/.venv312/bin/python test_api.py` — 41 assertions
against live upstreams (no mocks).

## Docs

| Doc | Contents |
|---|---|
| [00 · Executive thesis](docs/00-executive-thesis.md) | Problem, Delhi opportunity, differentiation, product definition |
| [01 · Data sources](docs/01-data-sources.md) | Every verified API/dataset: URL, limits, license, fallback |
| [02 · Competitive landscape](docs/02-competitive-landscape.md) | What exists, what's solved, what's genuinely open |
| [03 · Models](docs/03-models.md) | Pollution field, exposure/dose, emissions, route optimization — with feasibility verdicts |
| [04 · Architecture](docs/04-architecture.md) | System design, DB schema, pipelines, API, frontend, performance, privacy |
| [05 · Validation & impact](docs/05-validation-impact.md) | Back-testing plan, metrics, honest impact model, failure modes |
| [06 · MVP & roadmap](docs/06-mvp-roadmap.md) | Exact MVP, rejected features, demo flow, phased build plan |
| [07 · Experiments](docs/07-experiments.md) | Advanced methods scored: hypothesis → cost → verdict |
| [08 · Verdict](docs/08-verdict.md) | The brutally-honest product call this build follows |
| [10 · Provenance](docs/10-shipped.md) | Where every number on screen traces to — measured vs modelled |

## Zero-fake-data rule

Every number the product shows must trace to a measured observation, a published factor, or a labeled model estimate with uncertainty. If we can't defend it, we don't show it.
