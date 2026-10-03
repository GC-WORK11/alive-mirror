# ALive-108 — session handoff (2026-10-03)

State of the world for whoever picks this up in Devin Cloud. Everything below is
verified in-tree, not aspirational. Integration branch: **`base/v2` @ `d210bdd`**,
pushed to `<owner>/Delhi-Air-108`. `main` is stale.

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

- `cd server && uv run pytest -q` → **602 passed, 5 skipped, 1 xfailed**
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
  k>=3 community aggregates)
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

## Remaining work (in priority order)

1. **Android E2E on this cloud box** — KVM available. Build the dev client,
   boot AVD headless, run backend on same box (app hits `10.0.2.2:8000`),
   drive search→plan→nav→receipt, verify freshness chip shows real seconds-age,
   screenshots to prove light theme + map paint. Prior session `7feb6b7d` did
   this partially then became unreachable — redo cleanly.
2. **Owner keys** (`server/.env`, not chat): `OPENAQ_API_KEY` (explore.openaq.org
   → API Keys) flips stations 0→N and the field label modelled→measured;
   `CPCB_API_KEY` (data.gov.in, India-egress only); `FIRMS_MAP_KEY` optional;
   `ALIVE_OTD_API_KEY` for GTFS-RT buses; `ALIVE_ADMIN_TOKEN` for /admin.
3. **Physical-device map render check** — emulator proves plumbing; a real
   phone proves tile paint.
4. **Deploy** — needs AWS creds; `scripts/deploy.sh` + `infra/` exist. CPCB
   feed then becomes reachable from ap-south-1.
5. `health.py` could surface provenance `n` (one-liner; provenance already
   carries it).

## Key files to read first

`HANDOFF.md` (this), `docs/plan/realtime-status.md`, `server/.env.example`,
`server/main.py`, `server/airfield.py`, `server/airindex.py`,
`server/tests/test_e2e_live.py`, `Mobile/App.tsx`, `Mobile/src/map/style.ts`,
`Bridge/contract.ts`.
