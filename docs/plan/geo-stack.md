# geo-stack — self-hosted Delhi NCR geo, zero AWS geo spend

Replaces Amazon Location (maps + routes) with a Delhi-only stack that is
**objectively better for our use**: offline-capable, zero marginal cost,
~300× lower route latency, no rate limits. Built and measured on the dev
box (12 cores, 15 GB RAM, Docker 29).

## Architecture

```
                 ┌─────────────────────── this box ───────────────────────┐
                 │                                                        │
                 │  data/geo/ (gitignored, rebuildable via scripts/geo)   │
                 │  ┌──────────────────────────────────────────────────┐  │
                 │  │ delhi-ncr.osm.pbf   35 MB  (Geofabrik northern-  │  │
                 │  │                              zone → osmium clip) │  │
                 │  │ delhi.pmtiles       22 MB  (tilemaker, OMT       │  │
                 │  │                              schema, z0–14)      │  │
                 │  │ delhi.mbtiles       27 MB  (same tiles, alt pkg) │  │
                 │  │ osrm/{driving,walking,cycling}/  ~1.3 GB total   │  │
                 │  └──────────────────────────────────────────────────┘  │
                 │                                                        │
 phone ──HTTP──► │  FastAPI  server/tiles.py   ┌─ docker: alive-osrm-* ─┐ │
                 │   GET /tiles/tilejson.json  │ driving  :5001  302 MB │ │
                 │   GET /tiles/delhi/{z}/{x}/ │ walking  :5002  206 MB │ │
                 │        {y}.mvt  (~1 ms)     │ cycling  :5003  204 MB │ │
                 │   GET /tiles/delhi.pmtiles  │  (osrm-routed, MLD)    │ │
                 │        (HTTP Range → 206)   └────────────────────────┘ │
                 │  server/routing_local.py ──► OSRM_URL (:5001/2/3)      │
                 │                            └─► fallback public demo    │
                 │                                 flagged loudly         │
                 └────────────────────────────────────────────────────────┘
```

## Pipeline (all idempotent, all re-runnable)

| script | does | env knobs |
|---|---|---|
| `scripts/geo/tools.sh` | provisions osmium-tool (apt download + `dpkg -x`, **no root**), planetiler jar, go-pmtiles, docker images into `data/geo/tools/` | — |
| `scripts/geo/fetch_extract.sh` | Geofabrik `northern-zone-latest.osm.pbf` (224 MB, refreshed daily) → `osmium extract --bbox 76.80,28.20,77.90,28.95 --strategy smart` → `delhi-ncr.osm.pbf` (35 MB) | `EXTRACT_SOURCE=bbbike` for a 37 MB pre-clipped BBBike NewDelhi extract; `FORCE=1` |
| `scripts/geo/build_tiles.sh` | tilemaker docker → `delhi.pmtiles` (OpenMapTiles schema, gzip tiles, z0–14) | `FORCE=1`, `TILEMAKER_IMAGE` |
| `scripts/geo/build_osrm.sh` | `osrm-extract -p {car,foot,bicycle}.lua → partition → customize` (MLD) per profile | `FORCE=1`, `OSRM_IMAGE` |
| `scripts/geo/run_stack.sh` | starts 3 `osrm-routed` daemons on :5001/:5002/:5003, waits healthy, prints env | `start`/`stop`/`status` |

NCR bbox `76.80,28.20,77.90,28.95` matches `server/v2/deps.py:NCR_BBOX`.

## Measured artifacts (this box, 2026-10-03)

| artifact | size | build time | peak RAM during build |
|---|---|---|---|
| `delhi-ncr.osm.pbf` | 35 MB | osmium clip: 3 s | — |
| `delhi.pmtiles` | 22.6 MB, 1645 tiles z0–14 | tilemaker: 10 s | 27 MB RSS |
| `delhi.mbtiles` | 27 MB | (same run, alt output) | — |
| `osrm/driving` | 489 MB | extract+MLD: ~45 s | 800 MB (extract), 509 MB (partition) |
| `osrm/walking` | 397 MB | ~40 s | ~800 MB |
| `osrm/cycling` | 399 MB | ~40 s | ~800 MB |
| **osrm-routed running** | — | — | **302 MB driving / 206 MB walking / 204 MB cycling** (docker stats, idle) |

## Measured latency (curl, localhost, this box)

| query | local stack | public equivalent |
|---|---|---|
| route CP→AIIMS driving, full geometry | **1.5–2.2 ms** (:5001) | 555–635 ms (router.project-osrm.org) |
| route CP→AIIMS walking | ~2 ms (:5002) | ~600 ms public demo |
| vector tile z14/11705/6831.mvt | **0.8–1.3 ms** (uvicorn :8011) | 793–1081 ms (tiles.openfreemap.org, remote) |
| `GET /tiles/tilejson.json` | <1 ms, valid TileJSON 3.0 | — |
| `GET /tiles/delhi.pmtiles` `Range: bytes=0-126` | **HTTP 206** + `content-range` | — |

Verified real routes: CP→AIIMS driving 10.1 km / 13.6 min; walking 9.4 km;
cycling 10.4 km — all through the actual Delhi extract.

## Cost comparison (Amazon Location list prices, aws.amazon.com/location/pricing)

| | Amazon Location | this stack |
|---|---|---|
| map tiles | ~$0.040 / 1,000 tiles (GetTile; style descriptor + glyphs free) | **$0** — one 22 MB file, HTTP Range |
| routes | ~$0.50 / 1,000 `CalculateRoutes` (Core bucket: Car/Pedestrian/Transit; Scooter=Advanced) | **$0** — local osrm-routed |
| free tier | 500k tiles + 10k routes/mo, **first 3 months only** | n/a |
| 10k plans/day × 3 modes + ~50 tiles/session × 5k sessions | ≈ $15 + $10 / day ≈ **$750/mo** | **$0 marginal** (box already paid) |
| network | internet RTT ~500-800 ms ap-south-1 edge | loopback ~2 ms |

Zero marginal cost also means **offline/demo-safe**: the stack works with
the WAN cable out — a real judging-floor advantage.

## Honest gap list

- **No traffic.** Self-hosted OSRM returns free-flow durations only; Amazon
  Routes v2 returns live traffic ETAs. MLD graphs *can* absorb live speeds
  later (`osrm-customize --segment-speed-file`) if we get a speed feed —
  the partition/customize pipeline is already MLD, ready for it.
- **No scooter profile.** OSRM ships car/foot/bicycle; scooter ≈ cycling
  graph with speed tweaks (could add a `scooter.lua` copy later).
- **Geocoding beyond the gazetteer** still needs the expanded corpus lane —
  this stack covers tiles + routing only, not search.
- **HERE POI/building detail** in Delhi is richer than OSM's (doc 04 §1) —
  that stays a data gap; tiles render what OSM knows.
- **Outside NCR bbox nothing exists** — routes that leave the extract fail
  honestly (osrm returns `NoRoute`); the app must degrade to "outside
  service area", not hang.
- **No SLA** — a single box; `run_stack.sh` restarts after reboot but there
  is no redundancy, health-checking, or paging.
- **Public-demo fallback is rate-limited and ToS-restricted** — it exists
  only as a loud emergency path (`demo_rate_limited: true` in the route).
- Freshness: Geofabrik extract is ≤24 h old; rerun the pipeline weekly.

## Server integration (owned by other lanes — do not merge blindly)

- **Tiles:** mount `server/tiles.py` in `server/main.py` next to the /v2
  mount (exact 5-line block in the file's docstring). Env `ALIVE_PMTILES`;
  absent → honest 503 pointing at `scripts/geo/build_tiles.sh`.
- **Routing:** `server/v2/deps.py` `osrm_route()` — the 3-line swap is in
  `server/routing_local.py`'s docstring. Set `OSRM_URL*` envs (run_stack.sh
  prints them).

## Mobile integration note

The app already renders MapLibre (`@maplibre/maplibre-react-native` 11.x,
`App.tsx` `STYLE_URL = https://tiles.openfreemap.org/styles/dark`).

**Recommended path — plain TileJSON, zero new deps.** In the map style
JSON the `sources.openmaptiles` entry becomes:
```json
"openmaptiles": { "type": "vector", "url": "http://<host>:8000/tiles/tilejson.json" }
```
The tilejson advertises `/tiles/delhi/{z}/{x}/{y}.mvt` (gzip MVT — RN's
native HTTP stack decodes it fine; verified bytes round-trip). Keep the
openfreemap style body and re-point only the source URL, or consume our
tilejson from a locally-built OMT-schema style (map-style lane).

`pmtiles://` is **not** the simplest path here: the `pmtiles` npm package +
`addProtocol` are maplibre-gl-js APIs; maplibre-react-native has no
protocol-adapter hook, so RN would need a native bridge. For **web**
clients (admin/debug pages on maplibre-gl-js) `pmtiles://` *does* work
against `GET /tiles/delhi.pmtiles` — we serve raw HTTP Range (verified
206) for exactly that use.

Glyphs/sprites: the style's font/sprite URLs still point wherever the
style JSON says — the tile swap doesn't touch them.
