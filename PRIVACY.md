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

1. **A donated trip** (`POST /v2/trip`), sent once when a guided trip
   completes — and only while sharing is enabled (the `shareEnabled`
   gate sits on the only code path that calls it,
   `Mobile/src/nav/engine.ts:309`). The payload is:

   | field | what it is |
   |---|---|
   | `summary` | trip numbers: mode, distance_km, duration_s, dose_ug (estimated inhaled PM2.5 in µg), co2/pm25 mids, optional CO2 phase split — no location fields |
   | `trajectory` | the route geometry (the client pre-trims 300 m at both ends too, `Mobile/src/nav/engine.ts` TRAJ_TRIM_M) — the server re-trims and folds it into cells immediately, see below |
   | `device_token` | a random id the phone made up: `"anon-"` + 16 hex chars from a CSPRNG (`expo-crypto`), stored in `contributor.txt` as `{id, ts}` and **rotated every 30 days** (`Mobile/src/community.ts`) |

   (`POST /observe`, the pre-pipeline raw-coords endpoint, is retired —
   it answers **410 Gone**.)

2. **A hazard report** (`POST /report`) — a dust/smoke/burning/clean pin
   at a point. The server stores it snapped to ~110 m (3 decimals) with
   no contributor id at rest; reports expire after 6 hours. (No shipped
   UI posts to it today — the endpoint exists, the pin flow is
   unwired.)

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

**The community layer — aggregates only at rest** (`server/community.py`):

- `observe()` folds each donation **at ingest** into per-cell, per-hour,
  per-day and lifetime counters. There is no per-trip row anywhere in
  the store, the snapshot file, or the S3 object — a reader of any of
  them sees `{"trips": n, "dose_sum": …, "dev_all": [hashes], …}` per
  ~500 m cell, never an ordered chain or a journey (`community.py:52-58,
  _fold`).
- per-cell k-gate state: a set of hashed device ids (for the k≥3
  distinct-device rule) plus freshest-traversal timestamps — the
  minimum the publish contract needs;
- hazard reports `{ts, kind, lat, lon}` — snapped to **3 decimals ≈
  110 m** at ingest (`community.py` `report()`);
- reviews `{ts, stars, note, build}` — no token, no device id; note
  text passes a coordinate-pattern redactor before it can persist
  (`community.py` `add_review`/`_redact_note`);
- kept in memory, snapshotted to `server/data/community.json`, and —
  when `COMMUNITY_BUCKET` is set — pushed to our own S3 bucket at most
  once a minute (`community.py` `_save`). Legacy snapshots written
  before this layout fold once at load and are re-written as
  aggregates the moment they're read (`_apply`/`_migrate_obs`).

**Your own history, keyed by a token only you hold:** `DeviceLedger`
(`server/v2/store.py:355`) keeps the sanitized per-trip summary rows
*your* device donated (km, dose, mode, ts — never cells, never
coordinates) so `/v2/ledger` can answer "what did I breathe". Reading
or deleting it requires the raw `device_token`, sent in the
`X-Device-Token` **header** — never the query string, so it cannot land
in access logs or browser history (`server/v2/ledger.py`).

**Plan-time cache:** `RouteStore` (`server/v2/store.py:22-57`) holds route
geometries your `/v2/plan` request produced — origin→destination included —
keyed by a random `route_id`, for at most **1 hour**, capped at 500
entries. It exists so the in-trip strip can resample your route; it is UI
state, in memory only, never linked to a token.

## What the server never stores

- Accounts, names, phone numbers, contacts — none are collected anywhere.
- Raw trajectories and raw device tokens — both are unreachable to any
  store (enforced by test, see verify doc).
- Any per-trip donation record at rest: the community store holds
  cell/hour/day/lifetime aggregates only — after `observe()` returns,
  nothing that could single out one traversal exists in the process.
- Request coordinates in logs: uvicorn's access log is disabled
  (`--no-access-log` in `server/Dockerfile`); the app's own request log
  (`server/observability.py`) writes path **templates** only, with
  `lat`, `lon`, `token`, `query_string` on a denylist and a scrubber
  that rounds any >2-decimal number out of the line.

## Retention

- `/v2/trip` aggregates: held in process memory — no TTL is coded; a
  restart or redeploy clears them. The 72 h constant (`_cell_window_s`,
  `store.py:68`) is a **display** filter for corridors, not deletion.
- Community-layer aggregates: cell/hour/day buckets persist across
  restarts via the snapshot; hour buckets evaporate after **7 days**
  and stale implied-concentration samples die at **72 h**
  (`_HOUR_KEEP_S`, `_OBS_FRESH_S`, `_prune_agg`, `community.py`).
- Hazard reports: **6 h TTL** (`_REPORT_TTL_S`, `community.py`).
- RouteStore records: **1 h TTL** (`store.py:23`).
- The device-side contributor id itself rotates every **30 days**
  (`Mobile/src/community.ts` ID_TTL_MS), capping how long any donation
  chain can key to one id.

## Deletion — said plainly

- **On your phone:** Settings → "Delete my data" removes the ledger,
  settings, contributor id and intro flag — real files, really deleted
  (`Mobile/src/components/shell/settings.ts:45-52`, wired at
  `Mobile/App.tsx:95-98`).
- **On the server — your per-device ledger:** `DELETE /v2/ledger` with
  your `X-Device-Token` header wipes every trip row keyed to your
  hashed id. The app calls exactly this on "Delete my data"
  (`Mobile/App.tsx`).
- **On the server — corridor/city aggregates:** cannot be un-donated —
  after hashing + aggregation there is no record that maps back to
  you, and retracting a cell's counters would let fresh identities
  game the k≥3 threshold. That is the point of the design, and we say
  it plainly.

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
| AWS S3 (`COMMUNITY_BUCKET`) | our own snapshot of the community store | the aggregate counters described above (`server/community.py` `_save`) |
| OpenFreeMap tiles (`tiles.openfreemap.org`) | map style/tiles, fetched **by the app** | your IP and the map viewport you browse — inherent to any tile host (`Mobile/App.tsx:37`) |

Honest note on logs: the container runs uvicorn with
`--no-access-log` — request lines carrying `?lat=…&lon=…` (asked
during live navigation) are **not** written to stdout/CloudWatch. The
only request logging is `server/observability.py`: path template +
status + ms, with coordinates and tokens on an explicit denylist. The
TLS terminator/NLB still sees request lines in transit — we don't
claim no infrastructure ever sees them; we claim we never write them
down.

## Known gaps vs the design spec

We publish this list instead of overclaiming — `docs/privacy/verify.md`
shows how to confirm each item:

1. **Sybil resistance is honest, not strong.** Donations are
   unauthenticated — three fresh device tokens can mint a corridor
   cell, and an attacker who *joins* a 2-device cell forces it to
   publish. k≥3 is a real gate (verified by count-difference probing
   on a local instance) but it is not differential privacy; a
   motivated adversary with free identity minting sits outside what a
   hackathon build can close.
2. **The device token is a bearer key.** Whoever holds a raw
   `device_token` reads that device's `/v2/ledger`. Headers keep it
   out of URLs and logs, but it is not authenticated beyond
   possession — same model as a private photo-share URL.
3. **Aggregates are still aggregates.** A corridor cell's hashed-
   device set exists at rest (the k≥3 gate needs it); the sets are
   never published, but they exist — the honest statement is "no
   per-trip records", not "no device-keyed state".

Closed since this list was first written: the app donates to `/v2/trip`
(`/observe` returns 410), the contributor id is CSPRNG-random and
rotates every 30 days, the community store holds aggregates only (no
per-trip rows exist at rest), hazard pins snap to ~110 m, review notes
are coordinate-redacted at ingest, the uvicorn access log is off, the
device token travels in a header not the URL, both corridor stores
enforce the ≥3 distinct-device rule (`store.py` and `community.py`),
and `/admin/api*` requires `Authorization: Bearer <ALIVE_ADMIN_TOKEN>`
— 401 without it, verified live; `/admin` itself is a public shell
carrying no data.
