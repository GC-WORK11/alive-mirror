# Lane report: route-segments (review + safe-path audit)

Lane: `route-segments` — re-scoped after the route-render lane shipped its
own segments implementation (`c152760`). Mandate: honest review of that
impl, then the original task-2 safe-path audit, then this report.

## 1. Segments implementation review — `c152760`

**Verdict: sound — ship as-is.** Two small real gaps fixed; no fake data
paths, no perf footgun.

### What it does

`server/v2/plan.py::_option_segments` cuts each option's `geometry` into
≤12 vertex-boundary spans (`SEG_N=12`, `SEG_MIN_M=150`) and emits per span
`{geometry, pm25, band, start_frac, end_frac, dist_m}` — a literal
LineString slice of the served path plus the breathing-zone field read at
the span's own arc midpoint. Attached in `_option()` under
`try/except: pass`, additive: paint failure never sinks a row.

### Alignment check — pass

Spans are cut at polyline vertices and share boundary vertices, so the
painted ramp tiles the option's own coordinate list with no gaps:
`segs[0].start_frac == 0`, `segs[-1].end_frac == 1`, consecutive spans
share `(a.end_frac == b.start_frac)` and `(a.coords[-1] == b.coords[0])`,
and every span's coords are a contiguous slice of `option.geometry`.
The renderer needs zero re-sampling — it gets real geometry slices, which
is strictly better than the index contract the original mandate sketched.
Verified live across ~960 options (audit) + extended the contract-sync
test to check row shape + tiling on the wire.

### Null-path honesty — pass

`fval` → `None` → `pm25: null` + `band: "No data"` (via
`districts.cpcb_aqi(None)` → `cpcb_band(None)`). Dead field → every span
null (`test_option_segments_field_empty_is_null_not_faked`). `fval is
None` → key omitted entirely. NaN/raises → null. No fallback ramps, no
neighbour reuse.

### Field chain — pass

Reads ride `field_fn or _dose_surface(F) or F.value`, `_bz_field`-wrapped —
the exact surface the dose block just priced on (engine raster → snapshot
cells → live estimator). The painted stretch and the shown dose cannot
disagree.

### Perf — no footgun

Measured local (`PYTHONPATH=core/build312`, TestClient, engine serving,
two ODs × 6 calls):

- `took_ms` mean 490 → 470 with `_option_segments` stubbed: **+20 ms
  mean (+4.3 %)** end-to-end.
- `_option_segments` itself: **0.68 ms mean, p95 1.85 ms, max 5.1 ms**
  per option (~12 midpoint reads + two O(coords) arc sweeps).
- ~19 options × ≤12 reads ≈ 230 raster reads/plan — µs each on the
  priced `FieldView`; the live-krige fallback is the same estimator dose
  already uses, so paint is never worse than the dose sweep.

### Real bugs found → fixed in this lane

1. **Reroute flatten missed `segments`.** `/v2/reroute` flattens the
   selected option (`geometry`, `steps`, `dose`, `mode`…) to top level
   but dropped `segments` — a client on the flattened surface (what
   `useShellFlow` reads post-reroute) lost the paint strip. Fixed:
   `"segments": best.get("segments")` + `segments?` on
   `V2RerouteResponse` in `Bridge/contract.ts`.
2. **Contract sync had no nested check for the new field.** Extended
   `test_contract_sync` — every served option's `segments` rows are now
   checked field-for-field against `V2PlanSegment` plus the two tiling
   invariants (frac contiguity + shared boundary vertex).

### Design notes (not bugs — flags for the owner)

- Span `pm25` is the **ambient breathing-zone** read, not
  microenv-scaled. Right call for a colour ramp: the ramp shows where the
  air is dirty; the mode multiplier belongs to dose. Stated here so the
  next lane doesn't "fix" a deliberate semantic.
- `SEG_N=12` is intentionally coarse (a 65 km OD paints ~5.4 km spans).
  Fine for the ramp; it is a *summary*, not the field-resolution truth.

## 2. Safe-path audit — "no jungle routes"

**Verdict: PASS.** 48 ODs × ~7–24 options, local + prod. **0 in-bbox
P0 routes.** Every served road-mode option sits on real graph roads.

### Battery

`tools/audit_safe_paths.py` — 48 ODs across classes (short / cross-town /
cross-boundary / fringe / outside-coverage incl. Rohini→Kundli,
CP→Manesar, CP→Sonipat, CP→Meerut, CP→Panipat, Gurugram→Sohna). Per
option: 250 m cadence sampling against a grid index over all 1,070,459
graph edges (`server/data/route_graph.bin.gz` — the actual routing
surface, not a second OSM). Verdicts per option: PASS / WARN / P0 /
DECLARED (synthetic legs declared as such) / COVERAGE (off-network only
beyond the commute-shed bbox). Full output:
`docs/lanes/safe-path-audit-local.json`, `safe-path-audit-prod.json`.

### Results

| surface | ODs | in-bbox P0 | verdict |
|---|---|---|---|
| local TestClient (osrm-public-demo + engine) | 48 | 0 | in-area PASS; edge/outside HONEST |
| prod ELB (osrm-local + engine) | 48 | 0 | same; osrm-local aligns tighter than the demo router |

- **Engine rows are literally on the graph** (max offset 0.0 m — they are
  the graph's own edge polylines). Router rows ≤13.5 m off, i.e.
  polyline-vs-graph decimation, not road-leaving.
- **Transit legs**: audit per-leg; ride legs are declared rail
  (off-road by design), walk legs audited against roads — PASS/DECLARED.
- **Coverage edge**: fringe ODs whose route leaves the graph bbox
  (Panipat at 29.39°N vs graph cap 29.07°N, Sonipat, Meerut) show a
  sustained "off-road" tail — that is the commute-shed boundary doing
  its job, not a phantom road. These pairs answer `conf=low/medium`
  with segment `pm25: null` on the uncovered tail → **HONEST**, not
  confident.

### Server bug found & fixed (the audit's one real catch)

`exposure.dose` reported `confidence: "high"` on `coverage ≈ 0.57`
(CP→Panipat locally) — confidence was keyed only on the midpoint's
nearest-station distance with a hard floor at `coverage < 0.5`. A route
whose breathing is 10–50 % unmeasured is not "high" confidence no matter
how dense the field at its midpoint. Fix (`server/exposure.py`):
`coverage < 0.9` caps confidence at `medium` (`low` when the nearest
read is also ≥15 km). Verified: Panipat now `medium`; covered pairs
unchanged (`test_partial_coverage_caps_confidence`).

### Routing-chain sanity floors — inventory

| floor | status |
|---|---|
| off-network snap | ✓ `SNAP_RADIUS_M = 1500` — endpoints refuse beyond 1.5 km |
| class deny per mode | ✓ motor modes deny track/cycleway/footway/path/steps/bridleway + `access` bits (motor_vehicle/bicycle/foot) — a car cannot be routed over a park footpath, period |
| oneway / turn bans | ✓ per-mode (`turn` masks; walk ignores vehicular bans) |
| park/field traversal | n/a-by-design: motors can't take those classes; walk legs on `footway`/`path` are legitimate walking infra |
| **path/direct ratio bound** | **✗ absent** — dose+time cost is the only detour brake |
| unlit-road avoidance | ✗ absent — graph build carries no `lit=*` tags; outside a pollution router's scope, flagged honestly |

**Proposed minimal honest guard** (proposal, not shipped — wire fields
are shared surface): when a served road option's `dist_m` exceeds
~4× crow-fly for urban-scale ODs, attach a typed marker —
`option["detour_ratio"] = round(dist_m / crow_fly_m, 2)` — only when the
ratio clears the threshold. Audit found **zero** such routes in ~960
options, so this is a floor gap, not an observed defect; per the owner
rule it must be a marker, never a silent drop.

## 3. Diff summary (this lane)

- `server/exposure.py` — coverage-cap on confidence (audit-found bug)
- `server/v2/plan.py` — reroute flattened `"segments"` (parity fix)
- `Bridge/contract.ts` — `segments?` on `V2RerouteResponse`
- `server/tests/test_exposure_v2.py` — `test_partial_coverage_caps_confidence`
- `server/tests/test_contract_sync.py` — nested `V2PlanSegment` wire check
- `tools/audit_safe_paths.py` — the audit battery (new)
- `docs/lanes/safe-path-audit-{local,prod}.json` — raw outputs
- `docs/lanes/route-segments-contract.md` — shipped wire shape doc

Suite: `env -u WAQI_API_KEY -u CPCB_API_KEY -u OPENAQ_API_KEY
.venv312/bin/pytest tests/ -x -q` — **1204 passed, 5 skipped**
(full run, 8m24s, on HEAD 7404090 + this diff).
