# routes-delta lane report

Base: `b097879` → rebased onto `c5ba61c` (stays+playtime lane landed mid-hunt; clean rebase, no conflicts).

## Part A — route-exposure delta (judges' feature 1)

Every `/v2/plan` and `/v2/reroute` option now carries `delta` — est exposure kept
(`dose.mid`, already computed), the DELTA vs an honest baseline, and minutes added:

- `server/v2/plan.py` `_route_deltas()` (~L1256): runs post-rank. Baselines, all real:
  - engine/router **alt** row → same-mode **default** row, `basis:"route"` (the
    judges' purest-vs-default compare)
  - **primary** (default) row → same-mode purest alt when one exists, `basis:"default"`
  - single-route modes → global fastest option, `basis:"fastest"`
  - global fastest → `basis:"self"` (explicit zeros — itself, not a hidden compare)
  - eta-less engine rows (fast:true path) → `delta:null` — unmade stays unmade, no
    fabricated compare
- `band_drop` counts CPCB band crossings (30/60/90/120/250 breaks) so the app can
  say "clears a band" honestly.
- `Bridge/contract.ts` `V2RouteDelta` + `V2PlanOption.delta?`; mobile
  `src/components/shell/types.ts` + `api/plan.ts` mapper validates basis ∈
  {route,default,fastest,self}, coerces numbers, non-objects → null.
- Chooser rows (`CompareSheet.tsx` `deltaLine` ~L406-489) headline the delta —
  `−38% air · +6 min` shape — and append a verdict only where honest:
  - band cleared without heavier dose, or dose cut ≥25% → `— worth it for the
    school run` (per-mode who: schoolRun/rider/commute/rideIn/walkThere/visitor)
  - same air but slower, or heavier → `— take the fast one`
  - default that is also faster AND lighter → `the default — fastest AND the
    lighter air today`
  - purest row that IS the lightest → `lightest you can pick` (self)
- 16 new i18n keys, en+hi parity compiler-checked (`hi: Record<StringKey,string>`).

### Live wire numbers (local uvicorn :8080, PyPathEngine fallback, CP→IGI, field_mean ~95)

13 options returned; sampled deltas — car alt `+1.6µg/+11.5%/+2.6min` (route),
car default `−1.6µg/−10.3%/−2.6min` (default), bike alt `+10.2µg/+32.6%/+7.5min`,
walk alt `−24.5µg/−5.4%/−13.1min`. Today's field makes detours mostly heavier, so
"take the fast one" dominates — the honest outcome IS the feature.

### Sim (iPhone 17 sim, local server)

Compare sheet CP→IGI on camera, all rows carrying real deltas:
- `Car (AC)` — `the default — fastest AND the lighter air today`, ≈14 µg 7–21 · 24 min
- `Car (AC) · alt 1` — `+11% air · +3 min — take the fast one` (engine alt, route basis)
- `Car (windows down)` — `−17% air · +1 min`
- `Bike / scooter` — `the default — fastest AND the lighter air today`, ≈31
Shot: `routes-delta-compare.png`. While verifying, sim inspection caught a real
interpolation bug — `{p}` rendered literally (`+169{p}% air`) because the pct was
concatenated onto the template instead of passed as a var; fixed at
`CompareSheet.tsx:435` (`t("delta_airPct", lang, {p: "±N"})`), re-verified live
(`+11% air`, `−17% air` now render).

## Part B — e2e-sweep P1s (cited: `docs/lanes/e2e-sweep-report.md` @6659e14)

- **P1-1 "CountUp false-zero dose"** (`ui.tsx:96-118`): report caught hero `0 µg`
  for ~25–30 s on offline cold start and every option card `≈0` for ~60 s while
  its real range rendered — `useState(reduceMotion ? value : 0)` + rAF-starved
  step painted a fabricated zero. Fix: mount now paints the real `value`
  (`useState(value)`, `cur = useRef(value)`); the rAF tween only re-animates on
  value *change* and writes `cur.current`/`setDisp` inside the frame callback;
  `reduceMotion` renders `value` directly. Restructure also cleared
  `react-hooks/set-state-in-effect`. Verified on camera: cold starts painted
  real `87`/`89`/`16 µg · 17m counted` immediately, 4 launches, zero false zeros.
- **P1-2 "opposite-direction alert pair"** (`store/events.ts`, sweep #2): dedupe
  was per-kind-per-day so `outlook_heavy` AND `outlook_light` both fired the same
  day ~3 min apart on a verdict flip. Fix: `outlookToldDir(seen, day)` in
  `events-core.ts` (~L430) reads the direction already claimed that day; the
  outlook block (~L400) fires only `toldDir == null || toldDir === move` — an
  opposite-direction same-day flip is suppressed, a same-direction ≥15 µg
  revision still fires through the shared ladder. Unit-tested in `events.test.ts`
  (heavy→heavy ✓, light→light ✓, cross suppressed, stale-day null).
- **P2-4 "kind localization"** (sweep #4): `overture:rental_service` leaked raw on
  recents and PlaceSheet printed EN "airport" where search localized "एयरपोर्ट".
  `localizeKind` (~strings.ts L2623) now strips `^[a-z]+:` namespace prefixes and
  falls back to `kind_place`; PlaceSheet subtitle uses `localizeKind` directly.
  Live: search rows and PlaceSheet both show `aerodrome`, and `en` gains
  `kind_rentalService` (`hi` mirror) so the exact sweep string can't leak again.

## Gates

- `npx tsc --noEmit` clean; `npx expo lint` clean (post-merge, both)
- store runner 0 fails · api runner 0 fails (nav/offline/search runners green
  pre-merge; changes don't touch them)
- server `.venv/bin/python -m pytest tests/test_v2_plan.py
  tests/test_contract_sync.py` — **122 pass** post-rebase (incl. 2 new:
  `_route_deltas` baselines/honest-nulls, engine-only-rows-stay-null; contract
  sync diffs `V2RouteDelta` both directions)

## Notes / known edges

- `alternative_index` is `alt_i or None` — None on alt_i=0, so alts are detected
  via `engine == "alive_core-path"` or the `· alt N` label, matching the
  `_engine_merge` precedent at plan.py:2167.
- Prod (`:80` ECS) won't serve `delta` until a deploy lane ships this — deploy
  is out of scope here; sim proof ran against the local engine.
- P2 #3 (post-wipe location-page press-eating) and #5 (keychain toast on
  unsigned sim) left alone — #3 needs an OS-dialog-state repro, #5 is sim-only.
