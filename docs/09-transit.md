# 09 — Metro leg: the biggest dose lever on the board

`server/transit.py` adds the metro option to `/compare`. This page is the
provenance and assumption register for it.

## Station registry — real data, embedded

62 DMRC-family stations (all interchanges + all terminals + the busiest
stops per line, covering all 12 lines: Yellow, Blue, Violet, Pink,
Magenta, Red, Green, Green branch via Ashok Park Main, Orange/Airport,
Aqua/NMRC, Grey, Rapid Metro Gurgaon). Coordinates are real, pulled live
from OpenStreetMap/Overpass:

```
[out:json][timeout:20];
node["railway"="station"](28.20,76.80,28.95,77.90);
out;
```

POST to `overpass-api.de/api/interpreter` (served by the `lz4` mirror
during build; `kumi`/`private.coffee` mirrors timed out — retry with
mirrors if re-fetching), filtered to `network ∈ {Delhi Metro, Noida
Metro, Rapid Metro Gurgaon}` (274 nodes → 62 selected). Stations mapped
as one node per line at interchanges (e.g. `Hauz Khas (Yellow Line)` /
`(Magenta Line)`) are merged into one entry at averaged coordinates.

Not included: RapidX/RRTS (NCRTC regional rail, not the DMRC 12) and
`Meerut Metro` nodes — flagged, not silently mixed in.

## Assumptions (constants in `transit.py`, shown to the user in `assumptions`)

| Constant | Value | Basis |
|---|---|---|
| `METRO_DETOUR` | 1.35 | Track distance ≈ 1.35× the crow-flies inter-station distance. Heuristic circuity factor — honest approximation until per-line geometries are routed. |
| `METRO_SPEED_KMH` | 32 | DMRC commercial speed including dwell (published ~32 km/h). |
| `ACCESS_WAIT_MIN` | 5 | Entry + average headway wait + one interchange allowance. Folded into the metro leg's duration *and* dose (concourse ≈ metro microenv). |
| `WALK_SPEED_KMH` | 5 | Same as `MODE_SPEED_KMH["walking"]` in `main.py`. |
| `MAX_ACCESS_KM` | 2.5 | Gate: beyond this, "metro + walk" is not a credible option → `None`, not a fake number. |

Walk legs and the metro trunk are straight-line geometries — same
straight-line convention the app already uses for non-driving OSRM
modes. Upgrading a leg to a real pedestrian route (OSRM foot profile
self-hosted, or OTP2 + Delhi OTD GTFS for a true itinerary with line
numbers) is a drop-in change to `_walk_leg`/`_metro_leg`.

## Why the walk legs carry most of the dose — the honest story

Per minute, a walking commuter inhales ~4.1× what a metro rider does:

- microenv: 1.00 (roadside) vs 0.45 (enclosed) — measured, exposure.py [2]
- ventilation: 14 L/min vs 7.5 L/min — published, exposure.py [3]

So a 2-minute walk to the gate can out-dose a 30-minute ride. Two
consequences we surface, not hide:

1. **Metro still wins the trip.** The road-mode alternative breathes the
   roadside for the *whole* distance — Karol Bagh → Noida Sec 18 at a
   150 µg/m³ field: metro+walk ≈ 28 µg vs auto-rickshaw ≈ 75 µg.
2. **The last mile is where dose concentrates.** The next real lever is
   the access mode (walk vs bus vs auto to the station) — deliberate
   follow-up, not missing code.

## Known limits (labeled in the response as `duration_model: "estimated"`)

- No real line routing or interchange counting — the 5-minute access/wait
  constant covers it coarsely.
- Straight-line walks miss detours; dose could be ±20% on the walk legs.
- No service hours, crowding, or frequency — a 2 AM query still gets a
  metro answer.

## Tests

`server/tests/test_transit.py` — 9 cases, fully offline (embedded data +
constant field): registry ≥30 stations in-bbox, Connaught Place → Rajiv
Chowk < 1 km, Karol Bagh → Noida sane 3-leg option with closed-form dose
check, `None` when an endpoint is >2.5 km from the network.

```
cd server && .venv312/bin/python -m unittest tests.test_transit -v
```
