# Lane report — route-render layer (plan options → per-segment band paint)

Owner ask: multiple routes appear as an animated suggestion sequence,
settle to the chosen one; the route line is colored **per segment** like
traffic (CPCB band ramp only); smooth live-follow; real paths only.
Land on `base/v2`, honest separate commits.

## What shipped — 4 commits on `base/v2`

### 1. `c152760` server: additive per-segment field paint on options
`server/v2/plan.py` — each option's served geometry is cut into ~10–15
equal-length, vertex-boundary spans (`SEG_N=12` budget, `SEG_MIN_M=150`
floor); one breathing-zone field read per span midpoint, resolved on the
SAME chain the dose block just priced (`_dose_surface` priced raster →
`_snap_fv` → `F.value` → `field_fn`, wrapped by `_bz_field`) — the
per-part breakdown the dose sweep already computes, exposed, no new
math. CPCB band per span via `districts.cpcb_band(cpcb_aqi(pm))`.
Additive + `try/except`-guarded (a paint failure never sinks a row);
`dose` semantics untouched. Declared in `Bridge/contract.ts`
(`V2PlanSegment` + `V2PlanOption.segments`).

Wire shape per span:
`{geometry: LineString, pm25, band, start_frac, end_frac, dist_m}` —
spans share boundary vertices so the painted ramp tiles the path with
no gaps; `pm25:null` + `band:"No data"` on an unreadable span (never
faked).

### 2. `dc6796a` mobile: CPCB ramp + the segments seam
`Mobile/src/map/routeTint.ts` — `option.segments` now accepts the new
`{geometry, pm25, band}` shape alongside the legacy `{coords,
avg_conc_ugm3}` strip seam; served band name wins over re-binning.
Colours moved off the lane's 4-band editorial `MAP_*` ramp onto the
app's CPCB ramp (`theme.bandColor`/`bandColorIdx`) — design law: band
colours only where colour means air. Null reads → `MAP_QUIET` grey.
`bandIdxForName` mirrored locally (the module's node-test graph stays
net-free). `Seg` type + `plan.ts toOption` wire the field through —
absent on old servers → flat `dose.avg_conc_ugm3` tint (the documented
fallback; old-server compat kept).

### 3. `495957b` mobile: staggered suggestion sequence + tap-swap settle
`Mobile/src/components/RouteTint.tsx` — on a new option set the
recommended route asserts immediately (9px casing + 6px line) while
each alternative fades in through three `op` steps over ~460 ms,
staggered ~280 ms apart in option order. Tap-swap: the new choice
settles into bold over ~300 ms and the demoted route fades down into
the alternatives over ~450 ms. Mechanism: feature `op` props stepped
on timers into the two always-mounted sources — data-driven
`line-opacity` animates, nothing unmounts (the SIGSEGV class), every
write rides a timer past `whenMapDrawFree`, `useReduceMotion`
collapses all staging to the final state.

### 4. `f932acc` nav: camera-follow ease inside the commit cadence
`Mobile/src/nav/engine.ts` — the 650 ms commit gate vs a 900 ms easeTo
meant every follow fix cancelled the in-flight move mid-flight (the
jump the ask names). 600 ms settles inside the gate; teleports keep
their 1600 ms stretch. No state-machine touch.

## Verification — what was actually run

- `server`: `pytest -q tests` → **1203 passed, 5 skipped** (added 4
  segment tests: response shape + contiguous tiling, values in field
  range + band ∈ CPCB categories, unit count/gradient/degenerate
  honesty, field-dead → every span null + "No data").
- `Mobile`: `npx tsc --noEmit` clean; `npx expo lint` clean;
  `routeTint` node self-test 41 assertions green (CPCB colors, dual
  seg-shape, band-name priority, null honesty); node runners
  store 29 / api 8 / offline 6 pass; nav 72/74 — the 2 counters
  cold-start uplift fails are **pre-existing on clean base/v2**
  (stash-verified; another lane's VE re-anchor drift, dose-math
  internals are out of this lane's scope).
- Live server: `uvicorn` on `127.0.0.1:8042` (real CAMS ingest);
  `POST /v2/plan` CP→Karol Bagh and Hauz Khas→Model Town → every
  option carries 10–11 contiguous spans (`start_frac 0.0 →
  end_frac 1.0`, shared boundary verts), real midpoint reads
  (~93–96 µg/m³, "Poor" — tonight's field is genuinely uniform over
  these corridors; variation is honest, not synthesized).
- `route-render-shots/*.png` — the served wire painted with the
  app's own ramp constants and layer model (alts 3px @ 50%, selected
  9px casing + 6px) — the same colours/widths `RouteTint.tsx` feeds
  MapLibre. Evidence for the data→paint contract, not a device shot.

## iOS sim — crash, noted not fought

Fresh `expo run:ios` build on iPhone 17 (iOS 26.5) pointing at the
local server: app boots, real field data renders ("575 µg/m³ severe",
"least-bad hours ~20:30–07:30 around 463 µg/m³"). On the "Where to?"
search-sheet mount the process dies to the home screen — twice, ~1.6s
class, no JS error, no .ips — the documented mount-vs-draw SIGSEGV on
this sim (see search-fix-verify-report; it fires upstream of any
route-render work — the sheet mounts before options exist). Per the
90s rule, noted and not fought; no device screenshots of the animated
sequence could be captured on this box.

## Residual / honest gaps

- No on-device screenshot of the stagger (sim crash above); the
  staging is exercised by code review + timer mechanics only — first
  device run should eyeball it once.
- Segment colors are real but tonight's field is band-uniform on the
  tested corridors — a heavier gradient day will show multi-band
  stretches end-to-end (unit tests cover the gradient path).
- nav counters cold-start tests red on base/v2 before this lane —
  flag to the lane that owns `nav/counters.ts` VE constants.
- `strips` still wired optionally at App.tsx:186; when present,
  `option.segments` outranks them (documented priority).

Files: `server/v2/plan.py`, `server/tests/test_v2_plan.py`,
`Bridge/contract.ts`, `Mobile/src/components/shell/types.ts`,
`Mobile/src/api/plan.ts`, `Mobile/src/map/routeTint.ts`,
`Mobile/src/map/routeTint.test.ts`, `Mobile/src/components/RouteTint.tsx`,
`Mobile/src/nav/engine.ts`.
