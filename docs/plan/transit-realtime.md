# Transit realtime — what Delhi actually publishes

Lane: feat/r3-gtfsrt. Every row below was probed with `curl` from this
box on **2026-10-03**; nothing here is asserted from hearsay.

## What exists

| Source | Endpoint | Evidence | Verdict |
|---|---|---|---|
| **OTD Delhi** (Dept. of Transport NCT + IIIT-Delhi) — DTC + DIMTS cluster bus GPS | `https://otd.delhi.gov.in/api/realtime/VehiclePositions.pb?key=KEY` | `HTTP 401` without key (`nginx/1.18.0`); portal and docs return 200 | **Real feed, key-gated.** The only documented realtime endpoint — GTFS-RT `VehiclePositions` snapshot, regenerated ~10 s |
| OTD API-key request form | `https://otd.delhi.gov.in/data/realtime/` | `HTTP 200` | Works; free-form request (name/email/phone/purpose, commercial or not) |

## What's dead or never existed

| Claim | Evidence | Verdict |
|---|---|---|
| OTD `TripUpdates.pb` | `curl https://otd.delhi.gov.in/api/realtime/TripUpdates.pb` → **HTTP 404**; docs list only VehiclePositions | Never offered — **no schedule-delay feed for Delhi buses** |
| OTD `ServiceAlerts` | not in `/documentation/`; undocumented guesses 404 | Never offered |
| OTD static GTFS download | `/data/static` + `/data/staticDMRC` → **301 → 200** (portal pages, not direct zips) | Static available via portal; our static cache already uses the Mobility-DB/transitland mirrors |
| Community mirror `server.nikhilvj.co.in/delhirt/VehiclePositions.pb` (announced 2020 on gtfs-realtime group) | **HTTP 404** — host alive, archive gone | Dead |
| `opendata.iiitd.edu.in` (OTD alias) | `curl .../api/realtime/VehiclePositions.pb` → **connection failure (000)** | Dead domain |
| `traffickarma.iiitd.edu.in:9010` (linked from OTD agency page) | connection failure (000) | Dead |
| Mobility Database worldwide catalog | `bit.ly/catalogs-csv` fetched (1.18 MB, HTTP 200) — **zero `gtfs_rt` rows for India** | No India realtime feed is catalogued anywhere |
| DMRC metro realtime | no endpoint documented anywhere; Mobility DB has none; DMRC site exposes only schedule/fare info | **Does not exist publicly.** Metro "realtime" would need a DMRC partnership, not a URL |

## Consequence — what the server ships

`server/transit_rt.py` is a **capability shim**, not a fake feed:

```python
feed_status(live=False)  # {source: {status, http_status, evidence, ...}}
                         # status ∈ reachable | key-gated | dead | unknown
refresh()                # polls whatever is usable; per-source report
vehicle_positions(route_id=None)  # [{vehicle_id, route_id, lat, lon, ...}]
delays(route_id=None)             # [{trip_id, stop_id, delay_s, ...}]
alerts(route_id=None)             # [{route_ids, active_period, header, ...}]
status()                 # /health snapshot incl. "delays_basis" string
```

Honesty contract: **with no API key every query returns `[]`** and
`status()["delays_basis"]` says exactly why. Entities are TTL'd at 120 s —
stale positions die rather than linger. The GTFS-RT parser is real and
tested (self-contained protobuf wire decoder; uses
`google.transit.gtfs_realtime_pb2` when installed — same row shapes).
Delhi has no TripUpdates feed at all, so `delays()` will stay `[]` even
with a key until OTD adds one — that is the data's limit, not a bug.

## What the owner can unlock

1. **Request an OTD key**: fill the form at
   <https://otd.delhi.gov.in/data/realtime/> (institution + purpose;
   non-commercial fits). Historically keys were approved manually —
   allow days. Note from the gtfs-realtime thread (2020): some issued
   keys reportedly didn't work against the documented URL — verify with
   `curl -i "https://otd.delhi.gov.in/api/realtime/VehiclePositions.pb?key=$KEY"`
   (expect 200 + protobuf) before deploying.
2. **Set `ALIVE_OTD_API_KEY`** in the ECS task secrets. Nothing else to
   wire — `transit_rt.refresh()` picks it up (call from a scheduler or
   on-demand; `POLL_MIN_S = 15` throttles).
3. **Metro realtime**: no public path. If it matters, the ask is an
   official DMRC data-sharing request — not something code can fix.
4. Optional: `pip install gtfs-realtime-bindings` makes the parser use
   official protobuf bindings (falls back to the built-in decoder
   automatically; not required).
