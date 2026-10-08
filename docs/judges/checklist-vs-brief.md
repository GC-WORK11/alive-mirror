# Checklist vs the brief — shipped / partial / absent

Audited 2026-10-08 ~17:45 UTC, `base/v2` `c2f63c9`, live prod GET-only.
"Evidence" is a live wire field or a file:line you can check.

## The judges' brief

| Brief line | Status | Evidence |
|---|---|---|
| CPCB/OpenAQ live sources | **Partial** — same instruments, different pipes | 52 live CPCB/DPCC CAAQMS readings on prod via WAQI republish + DPCC pages (`/health` → `sources.stations` {count 52, feeds waqi+dpcc ok}). Direct `api.data.gov.in` TCP-refused from our egress (probe: `docs/plan/cpcb-source.md`), OpenAQ key revoked — both adapters coded, stay in the chain, report dark (`ingest_cpcb.py:264`, `airindex.py:574-666`). Upgrade path: `source-upgrade-rfc.md`. |
| Freshness transparency | **Shipped** | `/health` → `field_age_s` (462 s at read), `field_refresh_in_s`, `field_stale`, per-feed `age_s`; stale readings >3 h dropped (`airindex.py:106`, `:286`); DPCC rows >90 min dropped (`ingest_dpcc.py:93`). Gap named: per-station ages not yet on the wire. |
| Sparsity transparency | **Shipped** | `/aqi` → `nearest_station_km`, `field.stations[]` (52 named, real positions); `/grid` per-cell `conf`; `/v2/districts` → `confidence:"sparse"`, `cells_covered`, `centroid_read` (Jhajjar live example); `beyond_field_edge`/`outside_service_area` refusals. |
| Concrete exposure-drop | **Shipped** | `/compare` IG→HUDA: Car AC 14.0 µg vs on-foot 501.3 (36×); dose per mode priced from the live field; quieter-route logic in `main.py:753-870`. |
| Time penalty | **Shipped** | `/compare` per-option `duration_min` alongside dose (metro 74 min vs car 31 min); `/depart` re-prices a trip per departure hour; `/v2/outlook` names cleanest windows per day. |
| Who-it-helps | **Shipped** | `/shift` @CP 8 h two-wheeler: dose 402.9 µg ≈ 1.3 cigarettes, **+380% vs desk** — the delivery-rider/rider-class answer in one number; `/v2/city` breath section (today's mean → ~3.7 cig/day at the mid). |
| Sparse-station honesty ("transparency reads as competence") | **Shipped** | Band on every number (`/aqi` lo 49.1 / hi 110.0), band *measured* — 95.2% coverage at ±2σ over 3,550 held-out station-hours (`server/data/field_validation.md`, `SIGMA_CAL` `airfield.py:57-76`); sparse flags named above; every tried-but-dark source leg prints its verbatim verdict (`stations_status`, `waqi_status/cpcb_status/openaq_status`). |
| 3-min demo | **Shipped** | `docs/judges/demo-script.md` — 6 beats, every number a live GET re-readable by `scripts/research/freshness_probe.py`. |
| Visible AWS usage | **Shipped** | ECS Fargate task serving `/health` (`platform fargate`, `build_sha`); field snapshots → `s3://{ALIVE_AIR_BUCKET}/field/…` (`ingest_worker.py:112-151`); keys in Secrets Manager `alive108/*` (`scripts/deploy.sh`); rebuild metrics → CloudWatch `ALive-108` (`ingest_worker.py:276-304`); climatology built from public `s3://openaq-data-archive` (`history.py`). |
| One working feature > five half-built | **Shipped** | One pipeline — instruments → de-biased field → dose — powers every surface (`/aqi`, `/compare`, `/shift`, `/escape`, `/v2/*`). Nothing on the wire is a mock. |

## What was announced on X (Day-1)

| Announced | Status | Evidence |
|---|---|---|
| Purest-route picker, live air + all routes | **Shipped** | `/compare`: 8 options, dose + minutes each, best flagged; route set blends live field over all GTFS/OSRM paths (`main.py:753-870`, `v2/plan.py`). |
| Best hour to go out and play | **Shipped** | `/v2/today` (typical-day hourly curve @ the point, min ~64 at 17:00 IST tonight) + `/v2/outlook` (per-day cleanest windows: tomorrow 11:30–14:30 ~63.9) + `/v2/day` + `/depart`. |
| Live instruments — AQI / PM2.5 / PM10 | **Shipped** | 52 named instruments live (`/health` count, `/aqi` `field.stations[]`); `/aqi` @CP: us_aqi 160, pm25 79.6, pm10 195.2. |
| Hotel/stay with least average pollution | **Partial** | The field answers "where's cleanest" today: `/escape` (Cedar Avenue 55.6, −25% vs CP), `/v2/districts` per-district pm25 with coverage honesty. A dedicated stay-picker surface is not at this HEAD — sibling lane may land it tonight; if it doesn't, `/escape` is the truthful demo for the claim. |

*Nothing marked "shipped" is a mock, a fixture, or a fallback demo
value; "partial" lines name exactly what the surface does today.*
