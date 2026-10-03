# ALive-108

**A Delhi navigation app that prices every trip in two numbers most maps don't show: the smoke you will breathe, and the smoke your ride puts into the air** — before you leave, live while you travel, and as a receipt when you arrive. Anonymous trip aggregates feed a live picture of what Delhi breathes and emits on its roads.

Built for the AWS × WeMakeDevs Environmental Hacks hackathon, Air track. Delhi-only by design.

Live API (ECS Fargate + NLB, `ap-south-1`): `http://65.2.28.40` — `GET /health` is public; current builds report field age and per-source status.

## What it is

You type FROM → TO. The server returns real options — road modes via a router, metro via DMRC GTFS — each with an ETA, an estimated inhaled-PM2.5 **dose band**, and an estimated **emission band** for the vehicle class you declared. During the trip the app ticks both counters at 1 Hz off a route strip the server hands it; on arrival you get a receipt. Both numbers are always bands with a stated basis, never point truth — see "What it does not claim" below, which is load-bearing.

## How it works

```
┌─ Android / iOS app (Expo, MapLibre) ─────────────────────────────┐
│ T0 search — bundled Delhi gazetteer (26,545 places), on-device   │
│ dark map — OpenFreeMap tiles today; Amazon style when key lands  │
│ live trip — dose + emission counters tick locally at 1 Hz off    │
│             the route strip; no per-second network               │
└──────────────┬───────────────────────────────────────────────────┘
               │ HTTPS
┌──────────────▼────────────── AWS ap-south-1 ─────────────────────┐
│ NLB → FastAPI on ECS Fargate                                     │
│                                                                  │
│  /v2/search  T1: alive_core C++ index over the OSM-NCR corpus    │
│              T2: Amazon Location Suggest   [needs API key]        │
│  /v2/plan    options: ETA + dose band + emission band + reason   │
│  /v2/strip   field sampled along a route → the live counters     │
│  /v2/trip    anonymous trip summary in (no user table)           │
│  /v2/city    city aggregates out · /admin ops board              │
│                                                                  │
│  alive_core: C++20 pybind11 module — search index, field         │
│  sampling, dose + emission integrators. A pure-Python            │
│  reference (alive_core_ref.py) is the fallback: if the C++       │
│  import fails the API still serves, just slower.                 │
└──┬──────────────────────────────────┬────────────────────────────┘
   │ ~every 15 min (EventBridge)       │ aggregates only
   ▼                                  ▼
┌───────────────────────────┐  ┌────────────────────────────┐
│ air index (airindex.py)   │  │ DynamoDB alive108-agg      │
│ CAMS grid + NASA FIRMS    │  │ trips / km / µg / g per    │
│ fires + stations* + wind/ │  │ mode-day; corridor cells   │
│ BLH → QC → Kalman →       │  │ TTL 30 d. No user rows.    │
│ kriging ±σ → snapshot→S3  │  └────────────────────────────┘
└───────────────────────────┘
  *stations need OPENAQ_API_KEY — without it the field still
   builds (model + lagged public archive) and says so in its
   provenance block. See "What it does not claim".
```

## Measured numbers

Everything below traces to a file in this repo. Where a row says "bench", the protocol and both builds are in `docs/plan/bench-results.md`.

| What | Number | Source |
|---|---|---|
| Search index (T1), C++ vs Python | p50 0.189 ms vs 16.623 ms → **~88× p50** (~100× p95), build 45 ms vs 142 ms | `docs/plan/bench-results.md` |
| Field lookups + dose integration | ~6.8× lookups (174,618 vs 25,849/s); **~13× dose p50** (46.0 µs vs 607.3 µs) | `docs/plan/bench-results.md` |
| Emission integrator | ~3.3× p50 (11.2 µs vs 37.3 µs) | `docs/plan/bench-results.md` |
| Search corpus | 26,545 bundled gazetteer; 53,298 OSM-NCR corpus entries; 77,963 merged gazetteer | `server/data/corpus/STATS.md` |
| Search acceptance | 20/20 fixed Delhi queries in top-3 with alias table (17/20 without) | `server/data/corpus/STATS.md`, `tests/search_queries.txt` |
| Field leave-one-out vs live instruments | MAE 46.1 µg/m³, bias +0.3, n=94 stations | `server/data/field_calibration.json` |
| Field vs station archive (3,550 pairs, 85 stations) | MAE 47.1 µg/m³, bias +45.1 — **over-reads in clean post-monsoon air** | `server/data/field_validation.md` |
| Served field size | 14,628 grid cells in the benched snapshot | `docs/plan/bench-results.md` |
| Mode exposure ratios | walking ≈28×, rickshaw ≈5× the metro per km inhaled PM2.5 — measured on Delhi roads (published studies) | `docs/plan/10-claims-ledger.md`, `server/exposure.py` header |
| Cigarette equivalence on receipts | 316 µg PM2.5 ≈ 1 cigarette (Berkeley Earth), always shown as "≈" | `docs/plan/10-claims-ledger.md` |

C++ result parity is asserted bit-exact against the Python reference in `server/tests/`.

## What it does not claim

This section is a feature, not a disclaimer.

- **Phones measure nothing.** The app traverses a model field; it never says "your phone measured the air." User traversals adjust *dose estimates*, never the underlying field.
- **Emissions are class-level estimates.** "Vehicles like yours (2016 petrol car, BS-IV): ~1.1–1.6 kg CO₂" — a band from published factors, never "your car emitted 42.0 g." Per-vehicle truth is unknowable; PUC doesn't measure PM.
- **Stations are offline until the key lands.** OpenAQ v3 needs `OPENAQ_API_KEY`; without it the field is model + public S3 archive (1–2 days lagged) and the provenance block says so. No CPCB public JSON endpoint is reachable from the deployment network (documented in `server/data/field_validation.md`).
- **Amazon Location is optional.** With `ALIVE_LOCATION_KEY` you get T2 suggestions, traffic-aware routes, and the Amazon dark style. Without it the app still works: T0+T1 search, public OSRM demo routing, OpenFreeMap tiles.
- **The field is honest about its own error.** It over-reads in clean air (+150.6% bias on the validated window); the LOO calibration and σ bands are served next to the data, not hidden.
- **No outcome claims.** We can count "N trips switched to a lower-smoke option" — a countable behaviour — but not "Delhi got cleaner because of ALive."

## Quickstart

Server (Python ≥3.11; also `uv venv && uv pip install …`):

```bash
cd server
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt pytest
.venv/bin/python -m uvicorn main:app --port 8080
```

Tests — offline unit suite, then the live end-to-end suite (no mocks):

```bash
cd server
.venv/bin/python -m pytest tests/                      # offline
.venv/bin/python test_api.py --base http://localhost:8080   # hits real upstreams
```

Mobile (Expo SDK 57, npm — `package-lock.json` is the lockfile):

```bash
cd Mobile
npm install
npx expo start        # dev server; npx expo lint · npx tsc --noEmit to check
```

Search corpus (self-hosted geo data — downloads Geofabrik OSM, builds the corpus, emits the mobile gazetteer, scores the 20-query list into `STATS.md`):

```bash
./tools/setup-corpus.sh
```

AWS infra (one-time / drift repair — S3, DynamoDB, EventBridge schedules, CloudWatch, budget, Location key):

```bash
./infra/provision.sh --dry-run     # prints every command, executes nothing
./infra/provision.sh
```

Deploy (image → ECR → ECS redeploy → NLB target re-registration):

```bash
AWS_ACCESS_KEY_ID=… AWS_SECRET_ACCESS_KEY=… ./scripts/deploy.sh
```

## Status

Phases per `docs/plan/09-build-sequence.md` — honest checkboxes.

| Phase | State | Notes |
|---|---|---|
| 0 · Foundations + AWS | ◐ partial | `infra/provision.sh` + `scripts/deploy.sh` exist; schedules stubbed until owner exports target ARNs |
| 1 · Instant search | ✔ built | 3-tier search, C++ T1 index, corpus pipeline, 20/20 acceptance, benchmarks above |
| 2 · Dark map + shell | ◐ partial | OpenFreeMap dark map, hamburger sidebar, design tokens, hi/en strings shipped; Amazon Standard Dark style awaits the Location key |
| 3 · Plan: breath + smoke-out | ✔ built | `/v2/plan` returns ETA + dose band + emission band + ranking reason; emission integrator in C++ |
| 4 · Live trip | ◐ partial | `/v2/strip` + `/v2/trip` and nav chrome exist; on-device voice/reroute marked as seams in code |
| 5 · Air index + city + admin | ◐ partial | index builder, ingest worker, rollup, validation all exist; stations need the OpenAQ key; snapshots land locally until S3 ARNs are set |
| 6 · Polish + proof + submission | ◐ in progress | benchmarks above (kriging kernels pending); README (this file); video + writeup pending |

**Only the owner can unblock:** the OpenAQ (or data.gov.in) station key, the Amazon Location spend cap/key, AWS credentials for provisioning/deploy, real-phone Delhi test drives, and an Apple developer account (iOS stays simulator-only).

**Hackathon note.** Event rules require repo history inside the Oct 8–11 window. `scripts/public-repo.sh` squashes this private repo to one baseline commit on the day and pushes to the public repo; later commits land inside the window. We don't hide history — see `docs/plan/00-README.md` open items.

## Docs

The plan folder is the source of truth; `docs/plan/10-claims-ledger.md` governs every number this repo shows.

| Doc | Contents |
|---|---|
| `docs/plan/00-README.md` | Master plan, pillars, owner open items |
| `docs/plan/01` – `08` | Mission, UX, design, map/search/nav, backend, science, dashboard/privacy, C++ engine |
| `docs/plan/09-build-sequence.md` | Phases and acceptance criteria |
| `docs/plan/10-claims-ledger.md` | What we may say, what we never say |
| `docs/plan/bench-results.md` | All benchmark numbers, protocol + both builds |
| `docs/plan/runbook.md` | Deploy, rollback, secrets, health, cost |
| `server/data/field_validation.md` | Field vs 3,550 archived station-hours |
| `server/data/corpus/STATS.md` | Corpus build stats + search acceptance |

## Layout

`server/` — FastAPI dose engine + `server/core/` C++ (`alive_core`) + `server/v2/` API · `Mobile/` — Expo app · `Bridge/` — shared wire contract · `scripts/` `infra/` `tools/` — deploy, provisioning, corpus · `tests/search_queries.txt` — the fixed 20-query acceptance list · `docs/plan/` — the plan.
