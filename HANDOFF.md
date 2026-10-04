# ALive-108 — session handoff (2026-10-04, refreshed)

State of the world for whoever picks this up in Devin Cloud. Everything below is
verified in-tree, not aspirational. **`main` is the trunk** — PR #4 merged
`base/v2`; `base/v2` stays the working lane, merged to `main` at milestones.
`base/v2` HEAD ~`2b1eb3e` (753+ server tests, deployed on AWS).

## Live deployment (AWS, ap-south-1)

- NLB `alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com` → ALB TG → ECS
  Fargate SPOT service `alive108` (1 task, 1 vCPU/2 GB). Task-def ~`:63`,
  October actuals $0.00. C++ `alive_core` serves kriging, field views, dose
  sampling, emission integration, `/v2/search` (compound/fuzzy/alias index),
  and `PathEngine` — the least-inhalation A* over a 1.07M-edge 2-zone
  Delhi-NCR graph (northern+central Geofabrik), edge cost = length × local
  PM2.5 off a live-field raster reweighted ≤10 min (~903k edges priced),
  edge-state sid=(e<<1|rev) enforcing 230 OSM turn bans + 3,428 access
  overrides, corridor-diverse alternatives (<85% shared length gate),
  `engine_dose_ug` (Σ priced costs) on the wire.
- Deploy: `bash scripts/deploy.sh` — zips `server/` to S3, CodeBuild
  builds+tags `:<sha>`+`:latest`, registers task-def, force-new-deploy,
  verifies TG health. ~5-6 min. AWS creds are org secrets (auto-injected —
  do NOT override `AWS_*` env vars or the deploy can't auth). Commits only —
  `git archive HEAD:server` means uncommitted work never ships. Two racing
  deploys serialize on the service — last-in wins.
- Admin token: Secrets Manager `alive108/admin-token`
  (`Authorization: Bearer` on `/admin/api*`).
- Zero required third-party keys: CAMS/open-meteo (10 species, 15-min refresh)
  + NASA FIRMS + OSRM demo are all keyless. `OPENAQ_API_KEY` secret exists but
  the stored key is dead (401) — stations honestly read 0; WAQI adapter
  (`ingest_waqi.py`) activates if a free aqicn.org token is ever provided.
- Aggregates + device ledger are DURABLE — DynamoDB `alive108-agg`
  (`AGG_TABLE` set on the task; 30-day cell TTL). Donations survive deploys.
- `/v2/plan` error payloads carry stable `code:"outside_service_area"`;
  dose `coverage` (0-1) flows to the wire; `/v2/city` adds `species{}` +
  `typical` (decade-norm from the openaq archive); fires warm at boot.

## What ALive-108 is

Delhi/NCR pollution-aware navigation: for every trip, show the smoke you will
breathe and the emissions your vehicle produces — before, during, and after the
trip — and anonymously aggregate everyone's trips into a live picture of what
Delhi breathes. Expo/React Native app + FastAPI backend + optional C++ `alive_core`.

## Hard rules (user's, non-negotiable)

- **Nothing environmental is fabricated.** No hardcoded current PM2.5/AQI/fire/
  traffic values anywhere. Live upstream fetch or honest `null`/`unavailable`/
  `stale` — never a silent fallback number.
- Sources must carry provenance: `source`, `fetched_at`, `age_s`, `status`,
  `n` (samples), upstream HTTP status verbatim (`unavailable: HTTP 401`,
  `unavailable: ConnectError: ...`).
- Historical OpenAQ climatology (`server/history.py`) is context only — label it,
  never present it as now. Dose coefficients are cited physics constants.
- Light theme app + light basemap. Muted editorial ramp (bronze→brick→wine);
  no emoji in UI; no cheap amber/red.
- No secrets in git. Keys go in `server/.env` (gitignored; `.env.example`
  documents every var).
- Shared checkout hazard: multiple agent lanes have run on this repo and moved
  `HEAD`. Before committing always `git branch --show-current` — commit on
  `base/v2`, push.

## Verification (all re-run in main tree)

- `cd server && PYTHONPATH=core/build312:. .venv312/bin/python -m pytest tests -q` → **753 passed, 5 skipped** (needs `cmake --build core/build312` after C++ changes — a stale .so fails tolerance/parity tests)
- `cd Mobile && npx tsc --noEmit` → clean; `npx expo lint` → clean
- `uv run pytest tests/test_parity*.py` → 72 (C++ dose/emission bit-identical)
- Live e2e: `LIVE=1 uv run pytest tests/test_e2e_live.py` → real uvicorn, real
  upstreams: field_age 4290s→11s, `/v2/plan` 9 options/158ms, 33 NASA FIRMS fires.
- `/aqi` live: pm25 69.9 (61–79 band), pm10 245, no2 17.7, o3 147, co 705,
  so2 20, us_aqi 171, dust 322, aod 0.44, field `age_s: 5`, `stations: 0 (no key)`.

## Architecture map

- `server/airfield.py` — serving field: snapshot load, `refresh()` TTL 15min,
  kriging/IDW, `/aqi` payload assembly (10 pollutants + weather + fires + status)
- `server/airindex.py` — field build: H3 res-8 grid (h3 4.x `LatLngPoly`/
  `polygon_to_cells` — verified 14,155 cells), `_describe_error` surfaces
  verbatim upstream failures, `_fetch_stations_once` counts per-location failures
- `server/ingest_worker.py` — 15-min builder, writes `data/field/snapshots/`
- `server/main.py` — lifespan starts ingest daemon thread (`ALIVE_INGEST_IN_APP`,
  default on; tests set 0). `load_dotenv()` wired
- `server/ingest_cpcb.py` — data.gov.in CPCB feed, bounded retries, verbatim
  ConnectError reasons. NOTE: `api.data.gov.in` is TCP-refused from non-India
  egress — only works on India-region deploys
- `server/ingest_openaq.py` — OpenAQ v3 stations, needs `OPENAQ_API_KEY`
- `server/forecast.py` — depart curve anchored to live field (9h exp decay,
  `ANCHOR_MAX_AGE_S=3h` freshness gate)
- `server/exposure.py`, `emissions.py` — dose/emission math (Python fallback)
- `server/core/` — `alive_core` C++: `dose_series`, `emission_g_km`, krige.
  `tools/gen_ef_table.py` generates the mode table from `emissions.py` at
  configure (hexfloat literals — bit-identical). `ref_series.py` is the oracle
- `server/v2/ledger.py` + `DeviceLedger` (v2/store.py) — GET /v2/ledger?
  token= returns a device's own trip history + totals (sanitized summaries
  only, hashed-token key, newest-first; /v2/trip writes it alongside the
  k>=3 community aggregates). `agg_ddb.DDBDeviceLedger` gives it DynamoDB
  durability in the shared alive108-agg table (pk=ledger#<hash> query
  reads, 90d ttl) via the same env-chain selector as TRIPS
- `server/ingest_waqi.py` — WAQI (aqicn.org) measured-stations adapter,
  the fallback for OpenAQ in BOTH paths (airindex._fetch_stations for the
  15-min index, airfield._grab_openaq for the live blend). Env WAQI_API_KEY;
  free token, no region lock, republishes CPCB/DPCC. Bundle source stamps
  the winning feed; the loser's status rides as openaq_status/waqi_status
- `/admin/api/status` gains `ledger{backend, devices_tracked, error}`
- `server/v2/strip.py` `roads[]` — strip chunks split across OSRM step
  spans (plan.py stores steps on the RouteStore record), consecutive
  same-name steps merged → {name, dist_m, samples, avg_pm25, dose_share}
- FieldStatus refresh honesty — `refresh_in_s`/`refresh_ttl_s` in
  airfield.status(), surfaced as `field_refresh_in_s`/`field_stale` in
  /health
- `server/admin.html` + `admin_agg.py` — ops dashboard (light, no emoji):
  per-source live age/stale, mode-share, k≥3 corridors
- `Bridge/contract.ts` + `server/tests/test_contract_sync.py` — wire contract,
  49 tests verify every emitted key is declared
- `Mobile/` — Expo SDK dev-client required (MapLibre native; no Expo Go).
  `EXPO_PUBLIC_API_URL`, Android emulator fallback `http://10.0.2.2:8000`.
  `src/map/style.ts` `v2StyleUrl()`: `EXPO_PUBLIC_TILES_URL` → local
  `delhi.pmtiles` → bundled `v2-light.json` on hosted tiles
- `docs/plan/realtime-status.md` — per-source truthfulness matrix
- `server/routegraph.py` + `server/core/src/path.cpp` — PathEngine: the
  1.07M-edge Delhi-NCR graph (`data/route_graph.bin.gz`, `load_blob` gunzips;
  `.meta.json` carries build provenance + sha). Edge-state A* sid=(e<<1|rev)
  handles turn bans + reversed traversal; `path_engine()` lazy singleton
  (alive_core PathEngine else PyPathEngine — bit-identical parity asserted).
- `server/v2/plan.py` — the options pipeline: `_ENG_PACK=(fv,sig_fn)` priced
  raster (56×56 resampled off `/grid` BBOX, reweighted ≤10min/field-epoch),
  `_dose_surface(F)` picks ONE estimator per response (priced raster →
  `_snap_fv` → live), `_options_bounded` = PLAN_BUDGET_S wall (asyncio.wait,
  partial arms survive), engine rows carry `engine_dose_ug` (Σ priced
  costs = the minimized objective) + `via_names` + `alternative_index`.
- `server/v2/search.py` + `server/core/src/search.cpp` + `tools/` corpus
  pipeline — the 120k-row index: padded-trigram + bounded-DL fuzzy (all-digit
  /≤2-char atoms exact-only), lead-prefix boost (sector rows rank-1),
  kind+place compounds (~90 kind phrases incl Hinglish; anchor ≤1.5 km,
  cov≥0.75 gate, fires only when the name path is weak), 34+ real alias
  surfaces; `/v2/reverse` gazetteer-first ≤150 m → Amazon → 404
  `dropped_pin:true`.
- `server/v2/city.py` — `/v2/city` public aggregates (field lattice stats,
  decade-norm typical, next_hours forecast), `/v2/districts` 13-district
  NCR choropleth with field-keyed 120 s cache (`cached_s` emitted).
- `server/forecast.py` — CAMS horizon + semi-Lagrangian advection (parcels
  translate with real met wind, capped 45 km, calm→undisplaced); the
  live-anchor delta evaluates at the advected origin (2b1eb3e fix — a
  query-point delta could crush a clean parcel to a clamped 0.0).
- `server/admin_agg.py` + `server/admin.html` — ops board: district chips
  (CPCB palette), corridor table + `co2_g_per_100m`, donation days bars,
  species pills re-painting `/grid?param=`, pipeline panel (constants
  served by `/admin/api/model`), wind arrow, forecast scrubber,
  `/admin/api/timing` measured per-route latency. Banned-key guard: never
  emit lat/lon/coord/trajectory/user/route(=path) keys — tests scan every
  endpoint recursively.
- `server/observability.py` — `REGISTRY` histograms (alive_request_
  duration_ms{route} etc.) under `_lock`; `/metrics` Prometheus text.

## Remaining work (in priority order)

1. **Owner keys** (`server/.env`, not chat): `OPENAQ_API_KEY` (explore.openaq.org
   → API Keys) flips stations 0→N and the field label modelled→measured;
   `CPCB_API_KEY` (data.gov.in, India-egress only); `FIRMS_MAP_KEY` optional;
   `ALIVE_OTD_API_KEY` for GTFS-RT buses; `ALIVE_ADMIN_TOKEN` for /admin.
2. **Release signing** — the shipped APK is debug-signed (sideloads fine);
   a store build needs a real keystore (owner).
3. **Self-hosted OSRM** — SHIPPED as a Fargate sidecar (osrm-routed +
   Delhi-NCR MLD graph in the same task, `OSRM_URL=127.0.0.1:5000`,
   `docs/plan/osrm-selfhosted.md`). Public demo is now only the flagged
   fallback; refresh the graph image via `alive108-osrm-build`.
4. **Android TTS/jank** — wired (500/150/0 m thresholds); unverifiable on
   the macOS box (no KVM for the emulator; iOS sims lack a TTS stack) —
   needs a Linux KVM box or a physical phone.
5. **iOS upstream crash** — MapLibre render-thread SIGSEGV on virtualized-
   GPU sims only (~1/45 interactions, ~9 s state-preserving relaunch;
   upstream bug, not ours). Demo day: Android live or iOS recorded-take /
   bare-metal Mac. `docs/demo-day.md`.
6. **Physical-device map render check** — emulator proves plumbing; a real
   phone proves tile paint.

## Key files to read first

`HANDOFF.md` (this), `docs/plan/realtime-status.md`, `server/.env.example`,
`server/main.py`, `server/airfield.py`, `server/airindex.py`,
`server/tests/test_e2e_live.py`, `Mobile/App.tsx`, `Mobile/src/map/style.ts`,
`Bridge/contract.ts`.
