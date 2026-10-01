# 04 · System Architecture

Principle: boring, fast, honest. Precompute everything expensive; the hot path does lookups, not modeling.

## 1. Component map

```
                        ┌─────────────────────────── INGEST (hourly cron) ───────┐
                        │                                                        │
  CPCB data.gov.in ──►  │  ingest-worker (Python): fetch → validate → store      │
  OpenAQ v3 ─────────►  │  stamps: fetched_at, observed_at, provenance, flags    │
  Open-Meteo ────────►  │                                                        │
  NASA FIRMS ────────►  └───────────────┬────────────────────────────────────────┘
                                        │ writes
                                        ▼
   ┌─────────────────────────────────── STORES ───────────────────────────────────┐
   │ PostgreSQL+PostGIS (+Timescale ext)   Redis cache          S3/PMTiles        │
   │  · observations (hypertable)           · latest field tile   · basemap        │
   │  · station registry + reliability      · route-dose cache    · field rasters  │
   │  · grid cell features                  · autocomplete        · OTP/OSRM data  │
   │  · edge exposure cache                                                         │
   └───────┬─────────────────────────────────────┬────────────────────────────────┘
           │ hourly                              │ on query
           ▼                                     ▼
   field-builder (vectorized):          ┌──── api (FastAPI) ────────────────────┐
   regression-kriging per pollutant     │ /search  /route  /field-tile  /ledger │
   → grid surface + variance →          └────┬──────────────────────────────────┘
   precompute edge concentrations           │ calls
                                             ▼
                              ┌──── routing tier ────────────┐
                              │ OSRM (car/2W/cycle/walk)     │
                              │ OTP2 (transit multimodal)    │
                              │ Photon (geocode/autocomplete)│
                              └──────────────────────────────┘
                                             ▲
                              ┌──────────────┴───────────────┐
                              │  Web PWA — Vite+React+TS      │
                              │  MapLibre GL + PMTiles        │
                              │  FROM→TO → itineraries        │
                              └───────────────────────────────┘
```

## 2. Data flow — query path (the hot path)

`FROM text` → Photon (~30 ms) → `TO text` → Photon → POST `/route {o,d,mode_prefs,depart_at}`:
1. OTP2 returns ≤4 transit itineraries; OSRM returns ≤3 road routes per profile — parallel calls.
2. Each itinerary → legs with geometry + times.
3. Exposure scorer: for each leg, sample polyline at ~100 m; look up precomputed edge/cell concentration + mode factor + IR → leg dose + σ.
4. Pareto-rank on (dose, time, cost); pick recommendation; assemble explanation payload.
5. Response: itineraries with dose band, time, ₹ estimate, confidence, top factors.

Target p95 < 800 ms end-to-end (routers ~200–400 ms dominate; scorer <50 ms).

## 3. Data flow — ingest path (hourly)

1. CPCB Delhi fetch → validate (range checks, dup/stale detection) → `observations`.
2. OpenAQ for any stations CPCB missed + metadata refresh.
3. Open-Meteo per grid cell (wind, BLH, RH, temp) → `met_grid`.
4. FIRMS Punjab/Haryana bbox → fire count + FRP by upwind sector → `fire_daily`.
5. field-builder → grid surface + variance → raster tile to S3 + edge exposure cache refresh.
6. Health: stale-station list, ingest audit row. Fail soft — last-good field with "stale" badge, never fabricate.

## 4. Database schema (PostGIS + Timescale)

```sql
stations(id, source, name, geom, pollutants[], siting_flag, reliability_w, active)
observations(station_id, pollutant, value, observed_at, fetched_at, provenance)
met_grid(cell_id, ts, wind_u, wind_v, blh, temp, rh, precip)
fire_daily(day, sector_geom, count, frp_sum)
grid_cells(cell_id, geom, road_density, land_use, nearest_station_id)
field_surface(cell_id, pollutant, ts, mu, sigma2)         -- hourly output
edges(edge_id, geom, road_class, base_speed, len_m)       -- OSM-derived
edge_exposure(edge_id, pollutant, ts, mu_delta, sigma2)   -- increment layer
trips(id, anon_uid, o_geom, d_geom, ts, chosen_itin_json) -- opt-in, anonymized
itinerary_cache(hash, payload_json, expires_at)
ingest_audit(ts, source, rows, status, notes)
```

Spatial index: GIST on geoms; H3-9 cell ids for grid join; `observations` as hypertable on `observed_at`.

## 5. Historical pipeline

- OpenAQ S3 archive → bulk-load Delhi location_ids → `observations` (marks `provenance='openaq-archive'`).
- Open-Meteo archive → `met_grid` backfill.
- Product: `climatology(cell, pollutant, hour, dow, month)` table powering departure-time curves + validation back-tests.

## 6. API surface (FastAPI)

| Endpoint | Purpose | Latency budget |
|---|---|---|
| `GET /search?q=` | Photon passthrough w/ Delhi bias | <60 ms |
| `POST /route` | itineraries + dose + confidence | <800 ms p95 |
| `GET /field/tile/{z}/{x}/{y}` | PNG/vector tile of field surface | <100 ms (S3/CF cached) |
| `GET /now` | city snapshot: station freshness, GRAP stage, fire outlook | <100 ms |
| `POST /ledger` (opt-in) | log a taken route → avoided-dose estimate | <200 ms |
| `GET /meta/sources` | provenance + timestamps — trust page | <100 ms |

## 7. Frontend architecture

- **Vite + React + TypeScript**, PWA, mobile-first.
- **MapLibre GL** + **PMTiles** Delhi extract (self-hosted via S3+CloudFront) — no map API bills, no key.
- One screen hierarchy: search → compare → chosen route detail (dose curve along path + why).
- Design: calm light theme, one accent color (teal), tabular numerals for dose, cards only where they carry a decision. No dashboards, no gradient noise.
- State: URL-driven (shareable `?from=&to=&t=`), minimal client state.

## 8. Performance architecture

- Precompute: field surface hourly; edge exposure keyed (edge, hour-bucket); autocomplete index local.
- Cache: Redis for `/route` on (o,d,mode,bucket) 10-min TTL; CloudFront for tiles + static.
- Vectorized scoring (numpy over polyline samples); router calls in `asyncio.gather`.
- Rust: **not for MVP** — Python vectorized scoring hits the latency budget; Rust earns its place only if profiling proves scoring >150 ms or when we move to edge-side inference. Say this honestly in the doc so nobody thinks we're cargo-culting Rust.
- Measure: p50/p95 per endpoint logged; show them on `/meta/sources` — real observability as a feature.

## 9. Privacy / security

- No accounts for core flow → nothing to leak. Anonymous trip ledger only if user taps "log my trip"; stored as rounded coords (h3 ~500 m), no identity.
- Location: process in-request, don't persist raw traces; retention: ledger rows 90 days, aggregate thereafter.
- Secrets: AWS SSM/Secrets Manager; no keys in repo; rate-limit `/route` per IP; robots-respecting ingest only.
- HTTPS everywhere; CORS locked to our origin; no third-party trackers — it's a health product, act like it.

## 10. AWS deployment (eligibility: deployed on AWS ✔)

- **Frontend+tiles**: S3 + CloudFront (+ Route53).
- **API + workers**: App Runner (containerized FastAPI) or ECS Fargate; EventBridge hourly trigger for ingest.
- **DB**: RDS Postgres+PostGIS (free-tier size) or EC2 self-host; Redis → ElastiCache or container.
- **Routing tier**: EC2/Lightsail running OSRM+OTP2+Photon containers (RAM-heavy, cheap on Lightsail).
- **IAM-scoped**: ingest role, api role, no wildcards.
- Fits entirely inside free tier + the $200 new-account credits.

## 11. Local dev

`docker compose`: postgres+postgis, redis, osrm(Delhi pbf), otp2(Delhi OSM+GTFS), photon(Delhi), api, web. One command boots the whole Delhi stack.
