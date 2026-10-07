# Lane report — fix-edge-honesty: the three markers landed

**Date:** 2026-10-07 · **Lane:** fix the 1 P1 + 2 P2 from
`docs/lanes/edge-honesty-report.md` (Lane-E probe, build `ce01ec5c`)
· **Verdict: all three fixed, additive-only, suite green, pushed to
`base/v2`**

Constraint held throughout: additive honest markers — nothing removed,
every key optional, clients that never read them see the same payload.

## Probe → before → after

Before-numbers are the live-prod curls from the edge-honesty report;
after-numbers are the same requests against a local uvicorn serving
the patched code (real HTTP, field seeded with 5 live-mode samples —
deploy is a separate lane, prod could not be re-probed).

### P1 — `/v2/why` answered confidently for out-of-area coordinates

| | |
|---|---|
| Probe | `GET /v2/why?lat=51.5074&lon=-0.1278` (London) |
| Before | same Delhi line as an in-area call; ventilation read silently clamped to an edge cell (`vc_m2s 377.5` identical to `lat=0`), no marker |
| After | `200` — answer kept (drivers are city-scale), now with `point_in_area:false` + `note:"point outside the Delhi/NCR service area — this is the city-wide read, not a local one for this point"` |
| In-area | `GET /v2/why?lat=28.6315&lon=77.2167` → `point_in_area:true`, `note` absent |

Implementation: `build_why()` emits `point_in_area` from the same
`airfield.in_service_area` gate `/aqi` applies — marker, not rejection,
because the endpoint is city-scale by design (`/v2/city` calls it at
the Delhi centre and is unaffected). `server/v2/why.py`.

### P2 — `/aqi` past the field edge served a confident-looking point

| | |
|---|---|
| Probe | `GET /aqi?lat=30.20&lon=77.21` — inside the 2° service margin, ~170 km past the seeded field extent |
| Before | `pm25:62.4` = the literal edge cell, disclosed only by `nearest_sample_km:149.9` + a sigma band a consumer can ignore |
| After | `200` — `pm25:167.8` kept (numeric response unchanged in kind), now `beyond_field_edge:true` beside `nearest_sample_km:171.9` |
| In-extent | `GET /aqi?lat=28.60&lon=77.20` → `beyond_field_edge:false`, `ns_km 3.7` |

Implementation: `FIELD.beyond_field_edge(lat,lon)` compares the point
to the served field's own coverage bbox — `_snap_bbox` (the kriged
grid's real extent) on snapshot serving, the live samples' extent on
live serving; same record `status()` reports. Emitted on the success
path only; the `outside service area` and `field unavailable` bodies
are unchanged. `server/airfield.py`, `server/main.py`.

### P2 — `depart_at` never validated

| | |
|---|---|
| Probe | `POST /v2/plan {…, "depart_at":"banana"}` |
| Before | `"depart_at":"banana"` echoed verbatim; the GTFS arm threw inside `plan_transit` and silently served the labelled `(approx.)` station model — nothing said the time was never read |
| After | `200` — echo contract kept (`depart_at:"banana"`), now `depart_at_parsed:false`; option-level `approximate:true` labelling unchanged |
| Valid | `depart_at:"2026-10-07T08:30:00+05:30"` → `depart_at_parsed:true`; absent → key absent |

Implementation: `_depart_at_parsed()` reuses `transit_v2._to_ist` —
the GTFS arm's own parser — so the flag reports exactly the acceptance
the transit leg applied; it can never disagree with what the leg did.
Emitted on `/v2/plan` and `/v2/reroute` (same silent hole), including
reroute's no-options error body. `server/v2/plan.py`.

## Contract declarations

`Bridge/contract.ts`: `AqiResponse.beyond_field_edge?: boolean`,
`V2PlanResponse.depart_at_parsed?: boolean`,
`V2RerouteResponse.depart_at_parsed?: boolean` — the two-direction
contract-sync test (`test_no_uncontracted_server_fields`) would fail
on any undeclared wire key; it passes. `/v2/why` has no contract
interface (not fetched by the app) — no declaration needed.

## Regression tests (12 new, suite style)

| Fix | Test | File |
|---|---|---|
| P1 | `test_endpoint_marks_point_outside_service_area` / `_inside_service_area` / `test_endpoint_default_point_marks_in_area` | `tests/test_v2_why.py` |
| P2a | `test_aqi_beyond_field_edge_marked`, `test_aqi_inside_field_extent_not_beyond_edge`, `test_beyond_field_edge_empty_field_is_false` | `tests/test_v2_hardening.py` |
| P2b | `test_depart_at_unparseable_flagged_on_response`, `test_depart_at_parseable_marked_true`, `test_depart_at_absent_omits_marker`, `test_depart_at_parsed_mirrors_transit_parser` | `tests/test_v2_plan.py` |
| P2b | `test_reroute_depart_at_unparseable_flagged`, `test_reroute_depart_at_parseable_marked_true` | `tests/test_v2_reroute.py` |

## Verification — how each fix was proven

1. **Real HTTP against a local uvicorn** (`lifespan=off`, field seeded
   with the suite's 5-sample live field) — output:

```
=== P1 /v2/why London (out of area) (HTTP 200)
  point_in_area: False
  note: 'point outside the Delhi/NCR service area — this is the
         city-wide read, not a local one for this point'
=== P1 /v2/why Connaught Place (in area) (HTTP 200)
  point_in_area: True        note: <absent>
=== P2 /aqi 30.20N (inside margin, past field edge) (HTTP 200)
  beyond_field_edge: True    nearest_sample_km: 171.9    pm25: 167.8
=== P2 /aqi 28.60N (inside field) (HTTP 200)
  beyond_field_edge: False   nearest_sample_km: 3.7      pm25: 160.6
=== P2 /v2/plan depart_at='banana' (HTTP 200)
  depart_at: 'banana'        depart_at_parsed: False
=== P2 /v2/plan depart_at=ISO (HTTP 200)
  depart_at_parsed: True
=== P2 /v2/plan no depart_at (HTTP 200)
  depart_at: None            depart_at_parsed: <absent>
=== P2 /v2/reroute depart_at='banana' (HTTP 200)
  depart_at_parsed: False
```

2. **Unit + endpoint regression tests** (above) — `12 passed`.
3. **Full suite** —
   `cd server && PYTHONPATH=core/build312:. .venv312/bin/python -m pytest -q tests`
   → **see tail below** (run at HEAD before push).
4. **Live prod re-probe not possible** — deploy is a separate lane; the
   verified artifact is the code + local-server output above.

## Notes for the next lane

- `beyond_field_edge` deliberately does NOT suppress `pm25` — the demo
  may want the number; it just stops looking confident. If product
  wants a hard null past the edge, that's a product call, not honesty.
- `/v2/why`'s `note` joins `cannot_tell`/`honesty` as the third
  disclosure key — all additive, all optional on the wire.
- `depart_at_parsed` judges with the transit arm's parser; if the app
  ever sends epoch seconds or another `_to_ist`-accepted shape, the
  flag still agrees — that's why the parser was reused instead of
  duplicated.
