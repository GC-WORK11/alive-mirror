# realtime-status — what's actually live right now

> **Superseded (2026-10-06, docs-truth pass):** this is a 2026-10-03
> snapshot — major deltas since: stations live via **WAQI + DPCC (54
> instruments, `/health.sources.stations`)**, routing runs on a
> **self-hosted OSRM sidecar** (`OSRM_URL=127.0.0.1:5000`; the public
> demo is a flagged fallback), the dosimeter surfaces (`/v2/day`,
> `/v2/outlook`, `/v2/reach`, `/v2/why`, `/v2/skill`, `/v2/archive`,
> `/v2/city/moves`, `/community`) shipped after this was written, and
> `POST /observe` now answers **410 Gone**. Canonical ledger:
> `docs/plan/NUMBERS.md` (re-verified ~23:30 UTC 2026-10-06, build
> `ce01ec5c`).

Written 2026-10-03, verified the same day by `server/tests/test_e2e_live.py`
(a real uvicorn boot on a test port, `ALIVE_INGEST_IN_APP=1`, zero mocks —
run log below). [V] = observed this session against the live box.

Reproduce:

```bash
cd server
LIVE=1 ./.venv/bin/python -m pytest tests/test_e2e_live.py -q -s
# or without pytest:
LIVE=1 ./.venv/bin/python tests/test_e2e_live.py
```

Skip-by-default: the suite runs `pytest tests -q` in CI without `LIVE=1`
and the five tests skip cleanly. Every upstream hit is real — Open-Meteo,
NASA FIRMS, the public OSRM demo — so this test is the freshness proof,
not a simulation of one.

## Verified live (this session)

| Source | Path | Status | Observed 2026-10-03 ~06:53 UTC |
|---|---|---|---|
| CAMS model field | Open-Meteo air-quality API, no key | **live** | 48-sample NCR grid; pm25 70.6 µg/m³ at Delhi centre (ambient 61.4 × smoke modifier 1.15), pm10 238.4, no2 7.2, o3 178.9, co 473.4, so2 18.2; us_aqi 171.8; nearest sample 2.6 km; kriging on |
| Met (wind/BLH) | Open-Meteo forecast API, no key | **live** | wind 1.76 m/s (6.3 km/h) from 277°, BLH 270 m, VC 475.2 m²/s |
| Fires | FIRMS public 24h CSVs, no key | **live** | source `firms-public-csv`/`nasa-firms-public-csv`; 33 detections in the NCR+150 km ring, 9 in the NW burn belt → smoke modifier **1.15** |
| Routing | public OSRM demo, no key | **live** | `/v2/plan` returned 9 options in 157.9 ms (`osrm-freeflow` road options, `gtfs` metro option — the cached feed under `server/data/gtfs/` is in use, `estimated` slow modes) |
| In-app ingest | `main._start_ingest_loop` → `ingest_worker.run_forever` | **live** | `/health` `field_age_s` went 4290 s (stale snapshot at boot) → **11 s** after the thread's first `run_index_once`; snapshot `data/field/snapshots/2026/10/03/0653.json.gz` (built_at 06:53:33Z, 14,628 cells, build 7.7 s) |
| `/v2/strip` | route_id resampling | **live** | 13 samples @ 250 m on a real route_id, pm25 55.6–57.4 |
| `/v2/city/moves` | TripAggregates | **live, honestly empty** | `insufficient_data: true`, `n_trips: 0`, `min_k: 3`, corridors 0/72 h — an empty store, not fabricated zeros |

## Needs a key (wired, degrading honestly)

| Key | Source | Without it |
|---|---|---|
| `OPENAQ_API_KEY` | OpenAQ v3 → CPCB/DPCC instruments blended into the field at 3× weight | `provenance.stations = "unavailable: no key"`, `station_readings: 0` — field stays model-only and says so. **The one real gap** (00-README open item #1): nothing measured enters the live field today |
| `CPCB_API_KEY` | data.gov.in OGD realtime AQI (`ingest_cpcb.py`) | same gap, alternate path; also needs an India-routable IP — the key only works on the deployed ap-south-1 box, not a foreign dev machine |
| `FIRMS_MAP_KEY` | FIRMS area API (~3 h VIIRS NRT) | public 24 h CSVs already live — the key buys latency, not coverage |
| `ALIVE_OTD_API_KEY` | Delhi OTD GTFS-RT (DTC/cluster buses) | transit runs on the static GTFS cache; no realtime bus positions |
| `ALIVE_LOCATION_KEY` | Amazon Location (suggest/geocode/routes, HERE data) | search falls back to Photon, routing to public OSRM, `location.up: false` in /health |
| `ALIVE_AIR_BUCKET` + AWS creds | S3 snapshot archive + CloudWatch metrics | snapshots write to `data/field/snapshots/` locally (gitignored); `store_blob` degrades s3→local; metrics report `skipped` |

## Freshness mechanics (how the field stays real-time)

Four layers, each one honest about which one is serving:

1. **In-app ingest thread** — `main._start_ingest_loop()` (lifespan)
   spawns daemon thread `alive-ingest` → `ingest_worker.run_forever(
   interval_s=INDEX_PERIOD_S=900)`. Each iteration is a full
   `airindex.build_field()`: fetch model/met/fires/stations with
   per-source retry+backoff (`RETRY_ATTEMPTS` 3/3/2/2), station QC
   (stale >3 h, flatline, >5σ spike), Kalman smoothing, regression
   kriging onto the grid, then `serialize` → `store_blob` (S3 when
   `ALIVE_AIR_BUCKET` + credentials resolve, else local) → rotate
   (keep newest 96 = 24 h) → `FIELD.load_snapshot()`.
   `ALIVE_INGEST_IN_APP=0` disables it for boxes that run
   ingest_worker as a separate container. Failures back off
   exponentially (5 s base, 300 s cap) and are logged, never fatal.
2. **Request-driven refresh** — `FIELD.refresh(client)` on the read
   path (`/aqi`, `/route`, `/grid`, `/v2/*` via `deps.field_refresh`),
   15-min TTL (`CACHE_TTL`). Fetches the full pollutant set
   (pm2_5/pm10/no2/o3/co/so2/nh3/aqi/dust/aod) at the ~40-point
   station+fill grid, blends OpenAQ stations when keyed, directional
   IDW with upwind gain + kriging sigma.
3. **Snapshot fallback / warm start** — `FIELD.load_snapshot()` at
   import and on every ingest result: newest usable `*.json.gz` under
   `data/field/snapshots/` wins by (embedded built_epoch clamped to
   ≤mtime+120 s, mtime, path); corrupt files skipped and counted in
   `load_warnings`. The snapshot serves while it's the freshest thing
   held (`_serving_snapshot`: snap_epoch ≥ last live fetch) — before
   the first request refresh or after a newer ingest build. Snapshot
   cells carry pm25 + lo/hi + sigma + n_stations_within_10km; other
   pollutants return honest `None` on the snapshot path.
4. **Stale flags** — `field.status()` reports `serving` ∈
   {snapshot, live, none}, `age_s`, `stale` (age > `STALE_AFTER_S` =
   45 min, the doc-05 §6 alarm threshold), `stale_after_s`,
   `sigma_coverage`, `coverage.bbox`. `/v2/city` derives
   `freshness.label` live|stale|unknown at `2×CACHE_TTL` = 30 min.
   `/health.field_age_s` is the same number ops alarms on.

## Observed quirks (reported, not fixed — read-only lane)

- **`/health.sources.model.up` is `false` while the snapshot serves.**
  It reads `bool(fstat["samples"])` = the count of *request-refresh*
  samples, so an idle app serving a fresh ingest snapshot reports
  model down (and `fires`/`stations` cold until a request warms them).
  `field_age_s` is the trustworthy signal; the per-source `up` flags
  only describe the live-fetch layer. Cosmetic, but an on-call reader
  could misread it.
- **`airindex._h3_cells()` never fires on h3-py 4.5.0.** It calls
  `h3.Polygon`, which was renamed — `LatLngPoly` exists and produces
  14,155 res-8 cells. The build silently degrades to
  `latlon-fallback` (14,628 cells) and `grid.note` says "h3 not
  installed", which is wrong: h3 is installed, the API name drifted.
  Field still builds and serves correctly; the H3 grid just never
  engages.
- **Snapshot `provenance.*.age_s` is negative** (`-7`, `-1` observed):
  `build_field` captures `now` at entry but stamps each source's
  `fetched_at` when its fetch *returns* inside the build, so
  `age_s = now - fetched_at` goes negative by the fetch duration.
- **`nh3` is `null` on the live path.** Open-Meteo returns no ammonia
  for the NCR grid; the key is present and honest-null, matching the
  "never invent a number" rule. co/so2/o3 — the widened coverage from
  the realtime-field commit — all return real values.
- **`/v2/plan` car option won the recommendation** in the observed run
  (`recommended: ["car"]`) — expected mid-day when the field is
  uniform; not a defect.

## Test-run transcript (2026-10-03, `pytest -q -s`, LIVE=1)

```
5 passed in 20.81s   (uvicorn boot → first fresh snapshot ≈ 11 s age)

health_at_boot     field_age_s=4290  (stale 05:42Z snapshot; model up=false)
health_after_ingest field_age_s=11   sources: model cams / stations 0 /
                                     fires 0 (cold until first request)
aqi  pm25 70.6 (ambient 61.4)  pm10 238.4  no2 7.2  o3 178.9
     co 473.4  so2 18.2  nh3 null  us_aqi 171.8  smoke_modifier 1.15
     field: serving=live age_s=8 samples=48 kriging=on
     fire: live, firms-public-csv, 33 ring / 9 belt, wind 277°
plan 9 options (car/car_open/bike/auto/bus/metro+walk/cycle/walk)
     eta_models: osrm-freeflow + gtfs + estimated, took_ms 157.9
strip 13 samples @250 m, pm25 55.6–57.4, serving=live
city/moves  insufficient_data=true, n_trips=0, min_k=3  (honest empty)
```
