# /v2/plan `segments` — shipped wire shape (c152760)

Per-option pollution paint for the map's band-colour route ramp —
Google-traffic-style per-stretch PM2.5, **aligned to the served
geometry**, additive and optional.

Producer: `server/v2/plan.py::_option_segments` (attached in `_option()`
under `try/except`, paint failure never sinks a row).
Consumer: `Mobile/src/map/routeTint.ts` (accepts this shape and the
legacy strip seam).
Contract: `Bridge/contract.ts::V2PlanSegment`, `V2PlanOption.segments?`,
`V2RerouteResponse.segments?`.

## Shape

```json
"segments": [
  {
    "geometry": { "type": "LineString",
                  "coordinates": [[lon, lat], …] },
    "pm25": 142.3,
    "band": "Poor",
    "start_frac": 0.0,
    "end_frac": 0.083,
    "dist_m": 5120.0
  },
  …
]
```

| field | meaning |
|---|---|
| `geometry` | literal LineString slice of the option's own path — cut at vertex boundaries |
| `pm25` | breathing-zone field read at the span's own arc midpoint, µg/m³; `null` where the field can't read |
| `band` | CPCB category of that read (`Good`…`Severe`); `"No data"` when `pm25` is `null` |
| `start_frac`/`end_frac` | span's share of the whole path length, [0,1] |
| `dist_m` | span's actual path length |

## Invariants the renderer can rely on

- `segs[0].start_frac == 0`, `segs[-1].end_frac == 1` — the spans cover
  the whole served path.
- Consecutive spans share a boundary vertex:
  `a.geometry.coordinates[-1] == b.geometry.coordinates[0]` and
  `a.end_frac == b.start_frac`. No gaps, no overlaps.
- Every span coordinate list is a contiguous slice of
  `option.geometry.coordinates` — the paint can never drift off the
  drawn polyline.
- `pm25` is the **ambient breathing-zone** read (same chain the dose
  block priced: engine raster → snapshot cells → live estimator,
  `_bz_field`-wrapped) — *not* microenv-scaled. The ramp shows where
  the air is dirty; mode scaling stays in dose.
- `pm25: null` is honest absence — never a neighbour's value, never a
  fabricated ramp.

## Count & cost

`n = max(1, min(SEG_N=12, total_m // SEG_MIN_M=150))` — ≤12 spans per
option, so a 65 km OD paints ~5.4 km spans (deliberately coarse: the
ramp is a summary, not field resolution). ~0.68 ms per option on the
priced raster (~230 reads per full plan response ≈ +20 ms end-to-end —
see `route-segments-report.md` §1).

## Where it appears / doesn't

- `/v2/plan` → `options[].segments` — present whenever the option has
  ≥2-vertex geometry and a callable field; key omitted otherwise.
- `/v2/reroute` → top-level `segments` (flattened selected option) and
  `option.segments` / `options[].segments`.
- Transit options: spans follow the merged walk/ride geometry — the
  paint is ambient field at position, not per-leg dose; rail stretches
  read the surface field like everything else.
- Absent entirely → old clients unaffected (additive key, `try/except`
  guarded).

## Worked example

```bash
curl -s $BASE/v2/plan -H 'content-type: application/json' -d '{
  "from": {"lat": 28.6139, "lon": 77.2090},
  "to":   {"lat": 28.5708, "lon": 77.3260},
  "vehicle": "car"}' | jq '.options[0] | {mode, segments: (.segments | length)}'
# {"mode": "car", "segments": 12}
```

First span of a CP→IGI car row (local, climatology field):

```json
{"geometry": {"type": "LineString", "coordinates": [[77.2090,28.6139], …]},
 "pm25": 108.6, "band": "Moderate",
 "start_frac": 0.0, "end_frac": 0.0947, "dist_m": 1104.2}
```
