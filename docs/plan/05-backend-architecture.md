# 05 · Backend architecture

## 1. Services (all in ap-south-1)
```
            ┌──────── Amazon Location (Maps / Places / Routes) ───────┐
 phone ──▶ NLB ──▶ ECS Fargate: api (FastAPI + alive_core C++)        │
                     │   ├─ /search  (T1 C++ index + T2 Location)     │
                     │   ├─ /plan    (routes + transit + scoring)     │
                     │   ├─ /strip   (field along a route)            │
                     │   ├─ /trip    (POST summary)                   │
                     │   └─ /city, /admin (aggregates only)           │
                     ├─ worker: air-index builder (every 15 min)
                     │
  EventBridge Scheduler ─▶ worker tasks (ingest, daily rollup)
  S3: alive108-air  (field snapshots, daily index, validation)
  DynamoDB: alive108-agg (aggregate counters, corridor cells)
  Secrets Manager: data keys      CloudWatch: logs, metrics, alarms
```
Kept from today: ECS service `alive108`, NLB, ECR, CodeBuild. Added: Amazon Location resources, S3 air bucket, DynamoDB table, EventBridge schedules, CloudWatch dashboard + alarms, budget alarm.

## 2. The live air index of Delhi
**Grid:** H3 resolution 8 (~0.74 km² per cell) over the NCR bbox already used (76.75–77.95 E, 28.15–28.98 N) → roughly 12k cells NCR, ~2k inside Delhi NCT (computed at build time; exact count published).

**Every 15 minutes (EventBridge → worker):**
1. Pull inputs, each stamped with its own age: CAMS/Open-Meteo grid (model), CPCB/OpenAQ station readings (needs key — see 00 open items), NASA FIRMS fires (public CSV), Open-Meteo wind + boundary-layer height.
2. Station QC: drop flatlines, spikes >5σ vs neighbours, stale >3 h.
3. Kalman-smooth each station; regression-kriging residuals onto the H3 grid with variance → `pm25`, `lo`, `hi`, `n_stations_within_10km`, `nearest_km`.
4. Blend community corridor cells only where ≥3 distinct trips in 72 h (existing rule) — affects **dose estimates**, never presented as a measurement.
5. Write snapshot `s3://alive108-air/field/YYYY/MM/DD/HHmm.json.gz` + update in-memory field.
6. Emit CloudWatch metrics: stations used, field age, mean σ.

**Daily (00:30 IST):** roll up to `daily/YYYY-MM-DD.json` — per-cell mean/max and worst hours; city summary (median, % cells above WHO 24 h 15 µg/m³ and CPCB 60 µg/m³); ventilation coefficient (BLH × wind) per hour.

**Validation (weekly):** leave-one-station-out error vs CPCB/OpenAQ archive → `validation/` and shown on `/city`.

## 3. API (v2, versioned `/v2`)
| Endpoint | Purpose | Notes |
|---|---|---|
| `GET /v2/search?q&lat&lon` | 3-tier merged suggestions | T1 inline; T2 merged; `took_ms` per tier in response |
| `GET /v2/place/{id}` | resolve suggestion | Amazon GetPlace, cached |
| `GET /v2/reverse?lat&lon` | address for a point | Amazon ReverseGeocode |
| `POST /v2/plan` | `{from,to,depart_at,vehicle}` → options with route, ETA (traffic), dose band, emission band, tags, one-line reason | doc 06 ranking |
| `GET /v2/strip?route_id` | field along a route every 250 m + emission curve | for live counters |
| `POST /v2/reroute` | from current fix | |
| `POST /v2/trip` | trip summary + thinned trajectory, anonymous device token | doc 07 |
| `GET /v2/city` | live city summary + H3 field (gz) | consumer "Delhi today" |
| `GET /v2/admin` | aggregates, ingest health | basic-auth |
| `GET /health` | build sha, field age, sources up/down | |

Old endpoints stay until the app migrates, then removed.

## 4. Storage
- **S3**: snapshots, daily index, validation reports (cheap, auditable, judge-browsable).
- **DynamoDB (on-demand)**: aggregate counters only: `PK=day#2026-10-09`, `SK=mode#metro` → trips, km, breath µg sum, emission g sum, switched-count; corridor cells `PK=cell#<h3>` with traversal count + rolling exposure mean, TTL 30 days.
- No user table. Device token is a random UUID that never maps to a person.

## 5. Performance targets (measured, reported in `/health`)
| Path | p50 | p95 |
|---|---|---|
| `/v2/search` server time | 25 ms | 80 ms (T2 bound) |
| `/v2/plan` server time | 600 ms | 1.5 s (Routes + GTFS bound) |
| `/v2/strip` | 5 ms | 20 ms |
| Field rebuild | <10 s | |

## 6. Ops
CloudWatch dashboard "ALive-108": request rate, p95 per endpoint, field age, stations used, ingest failures. Alarms: field age >45 min, 5xx >1%, budget 80%. Deploy: CodeBuild from `server/` root zip (known gotcha), ECS rolling update; NLB target registration automated in the deploy script (the manual IP re-register is a known failure).
