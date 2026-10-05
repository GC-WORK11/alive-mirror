# strip-bz — stays ↔ plan/strip basis unification (report)

**Basis decision: breathing-zone (bz) everywhere, engine-side.** The
stays ledger keeps `ambient × FIRES.smoke_modifier`; `/v2/plan` and
`/v2/strip` now price that same field. Removing the modifier from stays
was rejected — it is physically real and already the product's public
number.

## Why bz is the honest basis (not display-only)

- `fires.smoke_modifier` (server/fires.py) is a measured quantity:
  FIRMS belt detections vs the seasonal 48h baseline, gated by wind
  quadrant (270–360° — plume actually advecting toward Delhi), floored
  at 1.0 when the feed is stale. It is not a cosmetic bump.
- `/aqi` already serves `pm25 = ambient × mod` as the public
  "what you breathe" number (`pm25_ambient` carries the raw field), and
  `/v2/why` attributes stubble smoke with the same gate. Stays counting
  bz while trips counted ambient meant the *server disagreed with
  itself about tonight's air*.
- Bridge/contract.ts already documented `avg_conc_ugm3` as
  "breathing-zone average" — the wire intent was always bz; the
  implementation had drifted.
- mod is a city-wide scalar, so it commutes exactly through
  `exposure.dose`'s Σc·ME·VE·t and **cannot change the priced argmin**:
  a uniform factor scales every route's cost identically and cancels
  in `_dose_key`'s ratio. No re-raster needed — route choice is
  untouched, only the reported basis moves.

## Live reproduction (prod, ~03:00 IST, 6 Oct)

`smoke_modifier = 1.09` (17 belt fires, wind 149°, feed age ~53 min).

| read | ambient | bz (×1.09) |
|---|---|---|
| `/aqi` at CP | `pm25_ambient` 69.1 | `pm25` 75.4 |
| `/v2/plan` CP→Saket `car_open` `avg_conc_ugm3` | 60.5 | — (was ambient) |
| `/v2/strip` route f0768a41cea5, 53 samples mean | 61.8 | 70.1 equivalent |
| strip sample nearest CP | 64.3 | 70.1 equivalent |

Trip counters integrated 61.8-class numbers while a stay at the same
spot recorded 75.4-class — the ~+9% gap the ledger-audit flagged.

## After

Same request path now reads the bz field: `avg_conc_ugm3`,
`dose.{lo,mid,hi}`, strip `samples[].pm25` and `engine_dose_ug` all
multiply the identical ambient reads by the same `smoke_modifier`, so
on tonight's numbers plan/strip land at 66.0/67.4-class — the same
basis stays count (75.4 at CP itself; route mean differs only by where
the route actually goes, as before). Both `/v2/plan` and `/v2/reroute`
echo `smoke_modifier` in the response so a client can prove basis
parity; `/v2/strip` echoes it too. When the fires feed is down mod =
1.0 and everything degrades to ambient on both sides — still
consistent, nothing invented.

Verified by `server/tests/test_strip_bz.py` (MOD=1.25 stub): dose bands
scale by exactly mod, `None` sigma/coverage stays `None`, a garbage
modifier (None/str/NaN/≤0) falls back to 1.0, strip samples equal
`F.value × mod`, and the stay-vs-trip test asserts a strip sample, an
`/aqi` pm25 and `pm25_ambient × mod` agree on one street-hour — the
judge's comparison.

## Files

- `server/v2/plan.py` — `_smoke_mod()` (guarded FIRES read), `_bz_field()`
  (pair re-base, None-preserving); wired into `_dose_band`,
  `_leg_dose`, `_dose_via_core` (incl. an `_Fbz` proxy for the dormant
  field-object attempt) and the transit station-model call;
  `engine_dose_ug` reported ×mod; `smoke_modifier` echoed on
  `/v2/plan` + `/v2/reroute`. The priced raster itself stays ambient —
  only the argmin matters there, and it is provably unchanged.
- `server/v2/strip.py` — `samples[].pm25/lo/hi` ×mod; `smoke_modifier`
  echoed. `pm25_g*` emission bands untouched (tailpipe mass ≠ inhaled
  concentration).
- `server/tests/test_strip_bz.py` — 9 tests locking the basis above.
- `Bridge/contract.ts` — `smoke_modifier` added to
  `V2PlanResponse`/`V2StripResponse`/`V2RerouteResponse` (additive);
  `avg_conc_ugm3`/strip `pm25`/`engine_dose_ug` documented as
  breathing-zone.
- `Mobile/src/nav/strip.ts` — doc comment: `samples[].pm25` is the bz
  basis (ambient × smoke_modifier), same field `/aqi` and the stays
  ledger read. No client math changed — the server now serves what the
  contract already claimed.

## Boundaries noted (deliberately not in scope)

- `/v2/city` `pm25_stats` is the city-overview ambient mean — the
  "city's air" number, not "your dose"; stays never read it.
- `/v2/day` + `/v2/outlook` are forecast-basis (future hours) — a
  different, correctly-different basis.
- The A* priced raster stays ambient; only reported values re-base.

## Gates

- `cd server && PYTHONPATH=core/build312:. .venv312/bin/python -m pytest -q tests`:
  9/9 strip-bz tests green; contract-sync + engine-options tests green.
  Full suite: 1101+9 passed, 13 pre-existing failures from the stale
  `core/build312` native build (`alive_core.PathEngine` missing `reach`,
  C++/Py dose-table drift ×0.75) — identical on the unmodified baseline
  (verified via stash). One `test_privacy_fuzz` flake: a random
  response ID containing the substring `77.2`, probabilistic, unrelated.
- Mobile: `npx tsc --noEmit` clean. `npx expo lint` reports a
  pre-existing `expo-device` unresolved-import error in
  `src/map/cam.ts` (eslint resolver quirk — module is installed and tsc
  resolves it; present on baseline before my change).
- No deploy (lane rule). No fake data anywhere — every scaled number
  multiplies a real read by the real modifier.
