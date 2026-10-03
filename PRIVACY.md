# Privacy — ALive-108

One paragraph: **ALive has no accounts.** No names, no phone numbers, no
email — there is literally no sign-up. The app works fully offline of any
identity. If you leave "Share anonymous trip data" on (it is on by default,
one tap to stop), a completed trip donates an anonymized record of the
route it took — and the server is built so that what persists can only
ever be city-wide aggregates. This document describes exactly what the
code does, where it falls short of the design spec today, and how to
check both claims yourself (`docs/privacy/verify.md`).

---

## What leaves the phone

**Nothing, until you use it.** The only user-originated uploads are:

1. **A donated trip** (`POST /observe`), sent once when you pick an option
   on the compare screen — and only while sharing is enabled
   (`Mobile/src/components/shell/useShellFlow.ts:168`). The payload is:

   | field | what it is |
   |---|---|
   | `vehicle` | mode you chose (`car`, `bike`, `metro`, …) |
   | `coords` | the **planned route geometry** for that option, index-thinned to ~60 points — *not* a live GPS trace, and currently **not** endpoint-trimmed |
   | `duration_s`, `dose_ug`, `avoided_ug` | trip summary numbers (dose = estimated inhaled PM2.5 in µg) |
   | `contributor` | a random id the phone made up: `"anon-"` + 8 random characters, generated once and stored in `contributor.txt` (`Mobile/src/community.ts:8-22`) |

2. **A hazard report** (`POST /report`) — a tap on dust/smoke/burning/clean
   at a point, with the same contributor id. Reports expire after 6 hours.
   (The client defines this call; verify current UI wiring in
   `Mobile/src/community.ts:44`.)

Everything else the app fetches is **read-only**: search suggestions,
routes, AQI at a point, reports, city totals. Those requests carry the
parameters you typed or tapped (a search string, a coordinate) — they are
not stored as user data, see "third parties" and the honesty note on
server access logs below.

## The transform chain (the /v2/trip pipeline)

The hardened donation endpoint — `POST /v2/trip`, implemented server-side
in `server/v2/trip.py` — enforces the documented privacy pipeline **on the
server**, treating the client as hostile or buggy:

| step | rule | where |
|---|---|---|
| 1. trim | drop the first **and** last **300 m** of the path, measured along the trajectory | `TRIM_M`, `server/v2/trip.py:28,82-85` |
| 2. thin | keep at most one point per **~100 m** | `THIN_M`, `server/v2/trip.py:29,87-91` |
| 3. round | coordinates rounded to **4 decimals ≈ 11 m** | `ROUND_DP`, `server/v2/trip.py:30,90` |
| 4. cell | each kept point becomes an **H3 res-8 cell key** immediately (fallback: a 4-decimal lat/lon grid key — same idea, finer granularity) | `server/v2/trip.py:33-44,107` |
| 5. discard | the raw payload is **never stored, never logged** — only the cell list survives the request | `server/v2/trip.py:106-114` |
| token | `device_token` is SHA-256'd (16 hex chars) **before it can touch a store or a log** | `server/v2/trip.py:109-110` |

## What the server stores

**On the /v2/trip path — aggregates only** (`TripAggregates`,
`server/v2/store.py:60-141`, in-memory):

- per-day counters: `trips, km, dose_ug, co2_kg_mid, pm25_g_mid, switched,
  modes{…}` (`store.py:75-87`) — the summary fields above, summed per UTC
  day;
- per-H3-cell: traversal `count`, summed `dose_ug`, the **set of hashed
  tokens** (for the k≥3 threshold), `last_ts` (`store.py:89-97`).

**On the /observe path — what the app uses today** (`server/community.py`):

- one row per donation: `{ts, vehicle, duration_s, dose_ug, avoided_ug,
  contributor, points[]}` — points are the donated coordinates rounded to
  5 decimals (~1 m), capped at 400 (`community.py:112-121`);
- kept in memory, snapshotted to `server/data/community.json`, and — when
  `COMMUNITY_BUCKET` is set — pushed to our own S3 bucket at most once a
  minute (`community.py:33-37,83-99`). The store keeps the last 20,000
  observations and 2,000 reports (`community.py:57-58`).

**Plan-time cache:** `RouteStore` (`server/v2/store.py:22-57`) holds route
geometries your `/v2/plan` request produced — origin→destination included —
keyed by a random `route_id`, for at most **1 hour**, capped at 500
entries. It exists so the in-trip strip can resample your route; it is UI
state, in memory only, never linked to a token.

## What the server never stores

- Accounts, names, phone numbers, contacts — none are collected anywhere.
- On the `/v2/trip` path: raw trajectories and raw device tokens — both
  are unreachable to the store (enforced by test, see verify doc).
- Any per-person history on the `/v2/trip` path: `TripAggregates` has no
  per-token row; a hashed token can only ever be *one member of a cell's
  token set*.

## Retention

- `/v2/trip` aggregates: held in process memory — no TTL is coded; a
  restart or redeploy clears them. The 72 h constant (`_cell_window_s`,
  `store.py:68`) is a **display** filter for corridors, not deletion.
- `/observe` observations: no expiry — they persist (rolling 20k cap)
  until the file/bucket is cleared; their *influence* on the citizen field
  stops after 72 h (`_OBS_FRESH_S`, `community.py:221`).
- Hazard reports: **6 h TTL** (`_REPORT_TTL_S`, `community.py:27`).
- RouteStore records: **1 h TTL** (`store.py:23`).

## Deletion — said plainly

- **On your phone:** Settings → "Delete my data" removes the ledger,
  settings, contributor id and intro flag — real files, really deleted
  (`Mobile/src/components/shell/settings.ts:45-52`, wired at
  `Mobile/App.tsx:95-98`).
- **On the server (`/v2/trip`):** aggregates cannot be un-donated — after
  hashing + aggregation there is no record that maps back to you. That is
  the point of the design, and we say it plainly instead of pretending a
  delete endpoint exists.
- **On the server (`/observe`):** rows carry the contributor id, so a
  delete-by-id would be technically possible — **but no such endpoint
  exists today.** Deleting the app's `contributor.txt` orphans your id;
  the donated rows stay in the aggregate store.

## Third parties

No trip data goes to any third party. The backend proxies these services;
what each one can see is listed:

| service | used for | what it receives |
|---|---|---|
| OSRM public demo (`router.project-osrm.org`) | route geometries | the from/to coordinates you asked to route between (`server/main.py:39`, `server/v2/deps.py:84`) |
| Photon (komoot, EU) | place autocomplete / reverse geocode fallback | your search text + a Delhi-biased position (`server/main.py:38,250-275,935`) |
| Amazon Location Service (`geo-places`/`geo-routes`, ap-south-1) | search, reverse-geocode, traffic-aware routes — when `ALIVE_LOCATION_KEY` is set | search text, positions, route endpoints — inside our AWS account (`server/location_client.py:25-26`) |
| Open-Meteo | air-quality model + wind field | a fixed NCR grid — never your location (`server/airfield.py:19-20`) |
| OpenAQ | reference station readings | station queries, no user data (`server/airfield.py:21`) |
| IITM EWS (`ews.tropmet.res.in`) | the SAFAR/WRF model bulletin | fetch only, no user data (`server/iitm_probe.py:46`) |
| NASA FIRMS | satellite fire detections | public CSV / keyed area fetch, no user data (`server/fires.py:47`) |
| AWS S3 (`COMMUNITY_BUCKET`) | our own snapshot of the `/observe` store | the donated rows described above (`server/community.py:33-37`) |
| OpenFreeMap tiles (`tiles.openfreemap.org`) | map style/tiles, fetched **by the app** | your IP and the map viewport you browse — inherent to any tile host (`Mobile/App.tsx:37`) |

Honest note on logs: the app code writes no access log tying you to
coordinates, but like any web service, request lines (e.g. `GET
/aqi?lat=…&lon=…`, asked during active navigation) pass through the
server's HTTP stack and TLS terminator. We don't retain or mine them;
we don't claim no infrastructure ever sees them.

## Known gaps vs the design spec

We publish this list instead of overclaiming — `docs/privacy/verify.md`
shows how to confirm each item:

1. **The app donates to `/observe`, not `/v2/trip`** — the hardened
   300 m/100 m/4 dp/H3 pipeline is implemented server-side but the client
   still posts to the older endpoint (no client calls `/v2/trip` yet).
2. `/observe` does **not** trim 300 m or thin by distance, rounds to
   **5 dp** (not 4), and **persists** donated points — the "no raw
   trajectories at rest" rule is only true of the `/v2/trip` path today.
3. The contributor id is random but **never rotates** (spec says 30 days)
   and is stored per-row, so a per-device donation history is
   reconstructible from the `/observe` store; it is also surfaced on
   `/admin/api`.
4. The **k≥3 distinct-device** corridor rule exists only on the `/v2/trip`
   path (`store.py:106-107`); the `/observe` corridor read-out has no
   per-device threshold.
5. `/admin` and `/admin/api` are served **without the basic-auth** the
   spec calls for, and they expose contributor ids.
