# Lane-E — edge/honesty hunt report

**Date:** 2026-10-07 00:00–00:25 UTC · **Lane:** Lane-E of `docs/lanes/oct7-test-plan.md` (edge/honesty hunt, live prod, GETs + the plan/reroute exception) · **Verdict: CLEAN, with 1 P1 + 2 P2 honesty nits — no P0**

**Prod:** `http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com` · build `ce01ec5c` · all numbers below are live curl outputs, not code inference.

## Probe table — input → response → verdict

### `/aqi` (GET `?lat&lon`)

| Input | Response | Verdict |
|---|---|---|
| `lat=0&lon=0` (Null Island, ocean) | `{pm25:null, error:"outside service area — dose field covers Delhi/NCR only"}` | ✓ honest reject |
| `28.6139,77.2090` (Delhi centre) | `pm25:59.4, ambient 55.0, lo–hi 44.2–74.6, nearest_sample 1.8km, field age 122s` | ✓ live + banded |
| `51.5074,-0.1278` (London) | `pm25:null, outside service area` | ✓ honest reject — the old "London gets Delhi air" trap is gated |
| `40.7128,-74.0060` (NYC) | same OUT_OF_AREA | ✓ |
| `-33.86,151.2` (Sydney) | same OUT_OF_AREA | ✓ |
| `90,180` / `lat=999` / `lat=28.5&lon=999` | same OUT_OF_AREA | ✓ bounds-checked |
| `lat=nan&lon=nan` | `pm25:null, error:"non-finite coordinate"` | ✓ boundary guard (`_finite_coords`) |
| `lat=abc` | HTTP 422 (FastAPI type check) | ✓ |
| `28.9,77.0` (NCR fringe, in-grid) | `pm25:79.6, band 24.6–134.6, nearest_sample 11.6km` | ✓ sparse disclosed via sigma + ns_km |
| `28.30,76.90` (SW sparse corner) | `pm25:72.0, band 22.3–121.8, ns 7.8km` | ✓ |
| `29.10,77.21` (~17km past grid edge) | `pm25:65.0, ns 28.1km, band 4.5–125.6` | ✓ clamp disclosed |
| `29.50,77.21` (~61km out) | `pm25:62.5, ns 72.3km` | see P2 below |
| `30.20,77.21` (~139km out, inside 2° margin) | `pm25:62.4, ns 149.9km, band 0.3–124.5` | see P2 below |
| `30.96,77.21` (0.01° past the margin) | `pm25:null, outside service area` | ✓ service-area math exact (28.95+2.0=30.95) |

### `/v2/plan` (POST — allowed by the test-plan exception)

| Input | Response | Verdict |
|---|---|---|
| CP→CP same point | 8 options; motor modes `distance_km:0.0, dose:null`; `degraded:["engine"]` declared | ✓ honest zero + declared degrade |
| ocean origin `(0,0)` | `{options:[], error:OUT_OF_AREA, code:"outside_service_area", took_ms:0.1}` | ✓ fast reject |
| London→Delhi | same OUT_OF_AREA + code | ✓ |
| `{}` / only `from` | `error:"from: need {lat,lon} or [lon,lat]"` / `"to: need ..."` | ✓ structured, not 500 |
| array/string/non-JSON body | HTTP 422 with `detail` | ✓ |
| 1km past service edge → Delhi | OUT_OF_AREA + code | ✓ both endpoints gated |
| Jaipur→Delhi (~220km, inside margin, outside field) | 7 options, every dose: `confidence:"low", basis:"est. · dose covers the served segment only — route begins ~174km from the requested origin at the field edge"`; `degraded:["engine"]` | ✓ exemplary — the best honest-degrade found tonight |
| `depart_at:"2001-01-01"` | plans + echoes verbatim | ✓ past dates plan (documented echo contract) |
| `depart_at:"3000-12-31"` | plans + echoes | ✓ |
| `depart_at:"banana"` | plans; echoes `"banana"`; transit falls back to `Metro + walk (approx.)` labelled `approximate:true, "station-to-station model", dose.confidence:"low"` | degrades honestly on the option, but the malformed datetime itself is never flagged — see P2 |
| `vehicle:"submarine"` | `vehicle:"car"` served + `vehicle_requested:"submarine"` echoed | ✓ deliberate remap-echo contract |

### Rate behaviour (the only "hard" probe)

| Probe | Result | Verdict |
|---|---|---|
| `/v2/city` ×20 sequential | 20×200 | ✓ under 10 rps sustained limit |
| `/health` ×20 | 20×200 | ✓ `/health` is exempt by design |
| `/v2/city` ×60 @20-way | 60×200 | within burst 30 + refill |
| `/v2/city` ×150 @40-way | 150×200 | **no 429 observed** — infra note below |

### `/v2/why` vs wind (the fires-claim check)

Tonight's live read: `wind {speed 6.6 km/h, from 125° (SE), age 430s, known:true}`; `smoke_modifier: 1.08`.

| Check | Result | Verdict |
|---|---|---|
| Line says "the air is barely moving" | wind 1.8 m/s + stagnation driver `vc 387 m²/s vs ~3,000 ref`, BLH 215m | ✓ text matches data |
| Fires claim vs wind direction | drivers = `[stagnation]` only — no fires driver tonight; and `smoke_modifier 1.08` = exactly the ×0.3 downscale of a 1.27 base for wind ∉ NW quadrant (270–360°) | ✓ guard exercised live in the "don't claim" direction |
| Belt detections | `/fires` returns VIIRS rows but `belt:false` on them; `SMOKE_MIN_BELT=10` not met | ✓ code bars confirmed (`CARRY_FROM 270–360`, `CARRY_MIN_KMH 4.0`, `WIND_GONE_S 3600`) — the "does claim fires" direction untestable tonight |
| `/v2/why?lat=0&lon=0` / London | **same Delhi line + identical `vc_m2s 377.5` (clamped cell)** | see P1 below |

### Freshness watch (`field_age_s` vs `stale_after_s`)

| t (UTC) | field_age_s | refresh_in_s | stale |
|---|---|---|---|
| ~00:04 | 484 | 416 | false |
| 00:15 | 650 | 250 | false |
| 00:21 | **10** | 890 | false |

The 900 s refresh cycle lands on schedule — age never approached `stale_after_s:2700`. A field that *did* stall would flip `stale:true` and `/health.field_stale` — the marker exists and was observed cycling correctly.

## Findings

**P1 — `/v2/why` answers confidently for out-of-area coordinates.** `/aqi` rejects the same coords (`outside service area`) but `/v2/why` silently clamps the ventilation read to an edge cell and returns the Delhi line with no marker that the point isn't Delhi. The endpoint *is* city-scale by design ("drivers are city-scale" docstring), so the answer isn't wrong — but the contract is inconsistent with `/aqi`, and the silent cell clamp means a caller can't tell the read isn't local. Fix is small: either apply the same `in_service_area` gate, or echo `{"point_in_area": false}` so the "this is Delhi's read, not yours" is explicit.

**P2 — `/aqi` past the field edge serves a confident-looking point.** At 139 km outside the kriged grid (still inside the 2° service margin) the response is the literal edge cell (`pm25 62.4` ≈ the 29.5 read's `62.5`), disclosed only by `nearest_sample_km:149.9` and a 0.3–124.5 sigma band a consumer can ignore. Not confident-*wrong* — the band is enormous and ns_km is loud — but a `beyond_field_edge` flag (or null pm25 with the band) would be safer than a plausible head figure at >50 km from evidence. `/v2/plan` already does this right via the `basis` string.

**P2 — `depart_at` is never validated.** Garbage strings echo verbatim into the response; the GTFS arm throws inside `plan_transit` and quietly falls back to the labelled `(approx.)` station-model option — so a typo'd departure silently plans for an undefined time. The option-level labelling keeps it from being *wrong*, but nothing in the response says "couldn't parse your time". A `depart_at_parsed:false` marker (or 400) is the honest version.

**Infra note (not a finding)** — no 429s at 150 concurrent GETs on `/v2/city`. The configured limiter (10 rps + 30 burst per client, `/health` exempt) never visibly tripped — either the path is exempt or the per-client bucket never saturates through the LB. Harmless for a demo; worth knowing if judges hammer it.

## What's confirmed clean (no action)

- Every malformed/edge input hits a structured error or a declared degrade — no 500s, no silent zeros.
- `degraded:["engine"]` observed live twice (same-point plan, Jaipur plan) — the incomplete-arm disclosure works in production, not just in code.
- The option-level honesty chain (`confidence`, `sparse`, `basis`, `approximate`, `vehicle_requested` echo, `puc_calibrated`) is wired end to end.
- Service-area math verified at the exact margin (30.20 in / 30.96 out).
- Winds-and-fires logic verified by code + live modifier both directions it could be tonight.
- Field freshness observed cycling 484→650→10 s against a 2700 s budget.

No writes, no POSTs outside `/v2/plan`, prod untouched.
