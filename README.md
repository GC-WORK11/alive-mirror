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

## What's built (live, verified numbers)

`server/` — the dose engine (FastAPI, real data only):

- `GET /compare` — one trip, every mode ranked by inhaled PM2.5.
  Tonight's live answer for Karol Bagh→India Gate: Car AC **3.8 µg**,
  auto 11.3, bike 8.3, bus 8.3, bicycle 68.4, on foot **118.6 µg (~31×)**.
- `GET /depart` — the same trip across the next 120 h of forecast field +
  boundary-layer stagnation physics. Live answer: leave 12:30 IST,
  same trip, **86% less PM2.5**.
- `GET /route` — OSRM road routes with per-route dose.
- `GET /aqi` — the interpolated PM2.5 field at any NCR point, with
  provenance (`nearest_sample_km`, sample age, fire modifier).
- `GET /search` — every Delhi NCR address, real OSM/Photon autocomplete.

`Mobile/` — the iOS/Android app: liquid-glass FROM→TO card, the dose
ranking (every mode, what you actually breathe), the leave-later hint,
and a "why?" expander that shows the published factors behind each
number.

`Bridge/` — the shared wire contract so app and server can never drift.

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
