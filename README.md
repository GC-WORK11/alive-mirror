# ALive-108

**A Delhi navigation app that prices every trip in two numbers most maps don't show: the smoke you will breathe, and the smoke your ride puts into the air** — before you leave, live while you travel, and as a receipt when you arrive. Anonymous trip aggregates feed a live picture of what Delhi breathes and emits on its roads.

Built for the AWS × WeMakeDevs Environmental Hacks hackathon, Air track. Delhi-only by design.

Live API (ECS Fargate + NLB, `ap-south-1`): `http://65.2.28.40` — `GET /health` is public; current builds report field age and per-source status.

## What it is

You type FROM → TO. The server returns real options — road modes via a router, metro via DMRC GTFS — each with an ETA, an estimated inhaled-PM2.5 **dose band**, and an estimated **emission band** for the vehicle class you declared. During the trip the app ticks both counters at 1 Hz off a route strip the server hands it; on arrival you get a receipt. Both numbers are always bands with a stated basis, never point truth — see "What it does not claim" below, which is load-bearing.

## How it works

```
┌─ Android / iOS app (Expo, MapLibre) ─────────────────────────────┐
│ T0 search — bundled Delhi gazetteer (124,311 rows), on-device    │
│ light bilingual map — 62-layer hi/en basemap, housenumbers/POIs  │
│ live trip — dose + emission counters tick locally at 1 Hz off    │
│             the route strip; no per-second network               │
└──────────────┬───────────────────────────────────────────────────┘
               │ HTTP (NLB :80 — no TLS terminator today)
┌──────────────▼────────────── AWS ap-south-1 ─────────────────────┐
│ NLB → FastAPI on ECS Fargate                                     │
│                                                                  │
│  /v2/search  alive_core C++ index over the OSM-NCR corpus        │
│              fuzzy typos · kind+place compounds (·hospital near  │
│              saket·) · Hinglish · sector-depth · aliases         │
│              T2: Amazon Location Suggest   [needs API key]        │
│  /v2/reverse gazetteer-first ≤150 m → honest 404 dropped_pin     │
│  /v2/plan    options: ETA + dose band + emission band + reason   │
│              + least-inhalation engine rows (below)              │
│  /depart     leave-now-vs-later dose curve · /decide pick        │
│  /v2/strip   field sampled along a route → the live counters     │
│  /v2/trip    anonymous trip summary in (no user table)           │
│  /v2/ledger  per-device dose/emission history (token-keyed)      │
│  /v2/city · /v2/districts  NCR choropleth (29 rows: 16 district │
│              cells incl Delhi NCT + 13 Delhi sub-areas)          │
│  /admin      ops board — corridors, species layers, api timing   │
│                                                                  │
│  alive_core: C++20 pybind11 module — search index, field         │
│  sampling, dose + emission integrators, and PathEngine:          │
│  an edge-state A* over a 1.07M-edge Delhi-NCR road graph,        │
│  edge cost = length × local PM2.5 (the live field raster,        │
│  repriced every ≤10 min — 903k edges), enforcing 230 OSM         │
│  turn-ban tuples + 3,428 per-way access overrides, returning     │
│  corridor-diverse alternatives with engine_dose_ug on the wire.  │
│  A pure-Python twin (alive_core_ref.py) is the fallback: if      │
│  the C++ import fails the API still serves, just slower; both    │
│  engines are asserted bit-identical in tests.                    │
└──┬──────────────────────────────────┬────────────────────────────┘
   │ every 15 min (in-app ingest loop; │ aggregates only
   │ EventBridge runs the daily rollup │
   │ + validation jobs on one-off      │
   │ tasks — `infra/schedules/*`)      │
   ▼                                  ▼
┌───────────────────────────┐  ┌────────────────────────────┐
│ air index (airindex.py)   │  │ DynamoDB alive108-agg      │
│ CAMS grid + NASA FIRMS    │  │ trips / km / µg / g per    │
│ fires + stations* + wind/ │  │ mode-day; corridor cells   │
│ BLH → QC → Kalman →       │  │ TTL 30 d. No user rows.    │
│ kriging ±σ → snapshot→S3  │  └────────────────────────────┘
└───────────────────────────┘
  *stations live today: 54 instruments via the WAQI + DPCC feeds
   (`/health.sources.stations` — OpenAQ stays a dormant keyed path).
```

## Measured numbers

Everything below traces to a file in this repo. Where a row says "bench", the protocol and both builds are in `docs/plan/bench-results.md`.

| What | Number | Source |
|---|---|---|
| Search index (T1), C++ vs Python | p50 0.189 ms vs 16.623 ms → **~88× p50** (~100× p95), build 45 ms vs 142 ms | `docs/plan/bench-results.md` |
| Field lookups + dose integration | ~6.8× lookups (174,618 vs 25,849/s); **~13× dose p50** (46.0 µs vs 607.3 µs) | `docs/plan/bench-results.md` |
| Emission integrator | ~3.3× p50 (11.2 µs vs 37.3 µs) | `docs/plan/bench-results.md` |
| Search corpus | 124,311 bundled gazetteer rows; 97,447 OSM-NCR corpus entries (incl. 16,949 real address rows — housenumbers + street interpolations) | `server/data/corpus/STATS.md` |
| Search acceptance | 67/67 fixed queries in top-3 (name, typo, compound, sector, alias) | `server/data/corpus/STATS.md`, `tests/search_queries.txt`, `server/tests/test_query_tolerance.py` |
| Search latency | C++ index p50 0.86 ms / p95 2.51 ms on 120k rows; live HTTP p50 ~3–7 ms | `docs/plan/bench-results.md`, live bench |
| Field leave-one-out vs live instruments | MAE 8.8 µg/m³, bias +0.2, n=70 WAQI+DPCC instruments (krige refit per held-out station) | `server/data/field_calibration.json` |
| Field vs station archive (3,550 pairs, 85 stations) | MAE 22.0 µg/m³, bias +15.5 µg (+51.6%) — **over-reads in clean post-monsoon air** | `server/data/field_validation.md` |
| Served field size | 14,628 grid cells in the benched snapshot | `docs/plan/bench-results.md` |
| Mode exposure ratios | walking ≈28×, rickshaw ≈5× the metro per km inhaled PM2.5 — measured on Delhi roads (published studies) | `docs/plan/10-claims-ledger.md`, `server/exposure.py` header |
| Cigarette equivalence | 316 µg PM2.5 ≈ 1 cigarette (Berkeley Earth) — OFF by default; opt-in toggle in app settings, always "≈" | `docs/plan/10-claims-ledger.md` |
| Path engine | 1,070,459 edges / 819,846 nodes; 903,058 edges priced per reweight; edge-state A* enforces 230 turn bans + 3,428 access overrides | `/admin/api/status` routing block |

C++ result parity is asserted bit-exact against the Python reference in `server/tests/`.

## What it does not claim

This section is a feature, not a disclaimer.

- **Phones measure nothing.** The app traverses a model field; it never says "your phone measured the air." User traversals adjust *dose estimates*, never the underlying field.
- **Emissions are class-level estimates.** "Vehicles like yours (2016 petrol car, BS-IV): ~1.1–1.6 kg CO₂" — a band from published factors, never "your car emitted 42.0 g." Per-vehicle truth is unknowable; PUC doesn't measure PM.
- **Stations: WAQI + DPCC are live (54 instruments); OpenAQ/CPCB-keyed still pending.** The field ingests 24 WAQI + 30 DPCC instruments across NCR today (count on `/health.sources.stations`, `source: "waqi+dpcc"` — live-verified 2026-10-06). OpenAQ v3 needs `OPENAQ_API_KEY` — without it that feed stays dark and the provenance block says so; no CPCB public JSON endpoint is reachable from the deployment network (documented in `server/data/field_validation.md`).
- **Amazon Location is optional.** With `ALIVE_LOCATION_KEY` you get T2 suggestions, traffic-aware routes, and Amazon reverse-geocode as a middle tier. Without it the app still works: bundled gazetteer + C++ search, public OSRM demo routing, gazetteer-first reverse.
- **The field is honest about its own error.** It over-reads in clean air (+51.6% bias on the validated window); the LOO calibration and σ bands are served next to the data, not hidden.
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

Search corpus (self-hosted geo data — downloads Geofabrik OSM, builds the corpus, emits the mobile gazetteer, scores the 67-query acceptance list into `STATS.md`):

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
| 0 · Foundations + AWS | ✔ built | NLB + ECS Fargate Spot + ECR + DynamoDB + Secrets Manager live; `$0` October actuals; EventBridge rollup-daily + validate enabled (ingest-15min stays disabled — the in-app loop owns it) |
| 1 · Instant search | ✔ built | C++ index over 120k rows, fuzzy/compounds/Hinglish/sectors/aliases, 67/67 acceptance, p50 <1 ms engine |
| 2 · Map + shell | ✔ built | light bilingual (hi/en) 62-layer basemap, housenumber/POI tiers, sidebar + design tokens |
| 3 · Plan: breath + smoke-out | ✔ built | `/v2/plan` options + least-inhalation engine rows + corridor alternatives + legality; `engine_dose_ug` on the wire |
| 4 · Live trip | ✔ built | `/v2/strip` + `/v2/trip`, turn nav chrome, voice cues wired (Android-verified path; iOS sim has an upstream render race — `docs/demo-day.md`), reroute served |
| 5 · Air index + city + admin | ✔ built | krige field + σ bands, ingest workers, rollup, NCR district + sub-area choropleth (29 rows), species layers, api timing, corridors CO₂/100 m, PUC calibration; 54 stations live via WAQI + DPCC (OpenAQ dormant) |
| 6 · Polish + proof + submission | ◐ in progress | benchmarks above; README (this file); videos shipped; store signing on owner |

**Only the owner can unblock:** a wider station key (OpenAQ would add instruments beyond the 54 live WAQI + DPCC; the data.gov.in path is TCP-refused even from ap-south-1 — documented in `docs/plan/handoff.md`), the Amazon Location spend cap/key, a release-signing keystore for the APK (the shipped build is debug-signed and sideloads fine), real-phone Delhi test drives, and an Apple developer account (iOS stays simulator-only).

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

`server/` — FastAPI dose engine + `server/core/` C++ (`alive_core`: search index, field/dose/emission integrators, PathEngine) + `server/v2/` API · `Mobile/` — Expo app · `Bridge/` — shared wire contract · `scripts/` `infra/` `tools/` — deploy, provisioning, corpus · `tests/search_queries.txt` — the fixed acceptance list · `docs/plan/` — the plan.
