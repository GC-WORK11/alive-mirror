# whereto-rebuild — lane report

Where-to flow rebuilt to the Google-Maps register: instant open, per-keystroke
local suggestions, fly-to-pin settle sheet, honest "Your location" routing, and
the chosen route painted in AQI-band segments with a time/dose bubble. Verified
on iPhone 17 sim (iOS 26.5), Delhi fix at CP (28.6315, 77.2167), destination
Saket metro via recents rail.

## Measured timings (sim, dev build, PERF_ON marks — last clean run)

| stage | ms | note |
|---|---|---|
| `search.tap` → `search.open` | **93 ms** | suggestion index pre-warmed on home's first frame (`afterFirstFrame → getPlaces()`); T0 rows + recents painted with the sheet |
| `search.idxReady` → `search.open` | **1.3 ms** | earlier run — index was already warm |
| keystroke → `search.rows` | per-key marks live | rows re-render from the local index each keystroke, bold-matched substring |
| row tap → `place.show` | ~2.0 s | synchronous `pick()` → place phase → 120 ms → `whenMapDrawFree` → 700 ms camera fly (zoom 15) → half-sheet |
| `dir.tap` → `plan:req` | ~2.7 s | `posNowDetailed()` real-fix race (skipped when `from` already set; `mark("loc.fix")` fires on the fresh-fix path) |
| `plan:req` → `plan:first` (engine rows) | **489 ms** | engine-first fast path — inside the ~2 s spec |
| `dir.tap` → engine rows on sheet | ~3.1 s | locating + commit + engine |
| `plan:req` → `plan.chooser` (route painted) | ~6.6 s | includes the chooser's choreographed ~3.5–5 s reveal beat |
| `plan:req` → full 24-option set | ~10.7 s | alts + transit + walk land behind the engine rows |

Compare: the owner's complaint was "takes minutes" — search open went from
seconds to **93 ms**; engine rows land in **~0.5 s** of the plan request.

## The honest-location path

`posNowDetailed()` in `net.ts`: 9 s race of `getCurrentPositionAsync(Balanced)`
→ `fresh:true`. Falls back to `getLastKnownPositionAsync` **only** when the fix
is inside NCR and ≤15 min old → `fresh:false`. Anything else → null, no fix
claimed.

- fresh fix → origin label `fixName()` = "Your location"
- stale fix → "near {locality}" / "last known spot · N min old" — never labelled GPS
- no fix → the Directions commit refuses out loud (`locPickFailed`), the `from`
  slot arms on the search sheet; the place preview survives so a typed `from`
  returns straight to the sheet
- destination within 50 m of origin → `pickTooClose`, stays on the sheet
- server empty-options path (stale origin outside service area) → "no route
  found between those two places" — verified earlier (`ss_no_route_honest.jpg`)

`locating…` is the CTA's label while the fix resolves — a dead-tap is
impossible. Verified honest-refusal in all three failure modes this session:
can't-read, outside-NCR, stale-origin.

## Route paints air — the root-cause fix

**The old route never painted at all.** `options={deferredOptions}` fed
MapTree's tint sources through `useDeferredValue` — under the compare sheet's
mount churn the deferred lane **never committed** (options stayed `[]` at the
source while the flow held 24). Evidence: `[tint] opts 0` across minutes of
renders while `[plan-bounds] 24 opts` logged in `show()`.

Fix: `options` goes to the tint sources directly (the deferred mount's only
purpose was de-prioritizing a pure-JS chunk build; every native-style commit
already rides the beat's own `whenMapDrawFree` timers). After the fix:
`tintSel 12` segments → beat completes → `stagedSel 12, alts 271` — the route
paints.

What the user sees now (`ss_abd50005.jpg`, `ss_zoom_13f4aaa8.jpg`):

- **chosen route = AQI-band-colored segments** on the road — `collectionsFor`
  chunks each option at `TINT_STEP_M` and probes the field per segment
  (the same serve dose math uses) — 6 px color over a 9 px `V2T.bg` casing
- **time/dose bubble on the path** — `{m} min · ~{d} µg` parked as a `holdPill`
  marker on the selected route
- **camera frames the whole route** — `fitBounds` over every option's geometry
  (padding top 200 / bottom 340), fires after the sheet's enter spring inside
  `whenMapDrawFree`
- alts draw as faint band-colored hairlines, gated off during nav

## Live travel — road ahead re-tints

`engine.navTint` = `{geometry, strip, alongM}` memo pushed to MapTree via
`deferredNavTint` (a single-burst update — the starvation class didn't apply).
`navCollectionsFor()` re-chunks the geometry and splits it at the odometer:
`ahead` keeps the CPCB bands, `behind` paints the travelled span dimmed
(`routeTintBehind` source, 9 px casing + 6 px color @ 0.45). `onFix` bumps
`alongM` at ≥60 m cadence; strip refreshes recolor in place; `loadRoute`
resets `navStrip`/`navAlongM`/`navAlongShownRef` so a reroute never bands new
geometry from the old strip.

Sim-verified: `simctl location set` walked the fix along the route —
`inNav true`, navTint re-memo'd and re-rendered per fix bump, camera followed,
"10.2 km left · ≈0.4 µg" strip live (`ss_d605fe25.jpg`, `ss_3757436e.jpg`).

## Flow phases

`Phase` = `idle | search | place | compare | nav`. Row tap → `place` (fly +
pin + half-sheet w/ name, locality, honest substitute metadata, live field
read, `locating…`/`Directions` CTA) → `goDirections` → `compare` → `nav`.
`pickTailGate`: stay = search|place, advance = search|compare|place —
synchronous to-picks reach settle; nav picks still blocked. Back handler and
`closePlace` unwind the phase stack cleanly.

## i18n

9 new keys × en+hi (parity compiler-enforced): `locating`, `placeNearLocality`,
`placeSubstCat`, `placeSubstArea`, `placeNearAnchor`, `placeAirNow`,
`placeAirNone`, `routeBubble` ("{m} min · ~{d} µg"), plus the honest-failure
strings already in place.

## Gates

- `npx tsc --noEmit` — clean
- `npx expo lint` — 0 errors
- `node src/{store,nav,api,offline}/test-runner.mjs` — 89 + 100 + 37 + 16 = **242 pass, 0 fail**
- `routeTint.test.ts` self-test — **62 assertions OK** (incl. `navCollectionsFor`
  ahead/behind: 0 m → all ahead; mid-route → behind segs; 1e9 → 0 ahead; null → empty)

## Evidence (`whereto-rebuild-shots/`)

| shot | shows |
|---|---|
| `ss_fe842230.jpg` | home, Delhi fix live ("read at your location") |
| `ss_f128ec2c.jpg` | settle: camera flown to Saket, pin + half-sheet (name · locality · "air there now ~44 µg/m³" · Directions) |
| `ss_43a7542a.jpg` | compare sheet, engine rows (Car AC · least smoky · dose range) |
| `ss_abd50005.jpg` | route framed by fitBounds + "20 min · ~71 µg" bubble on path |
| `ss_c2ef2c9d.jpg` | compare after vehicle pick — bubble tracks selection |
| `ss_zoom_13f4aaa8.jpg` | zoom: band-segmented route + bubble + endpoint dot |
| `ss_d605fe25.jpg` | nav live: "Head out" + dose strip |
| `ss_3757436e.jpg` | nav tracking sim'd travel — "10.2 km left · ≈0.4 µg", re-tint per fix |
| `ss_no_route_honest.jpg` | honest empty-options state |

## Crash-class discipline kept

No autofocus, no RN Modal, parked markers only (child-swap visibility), one
camera move per phase window, JS-driver animations, every staged write rides
a timer, drawHold-wrapped commits. Zero SIGSEGV across the whole lane's sim
driving.

## Coordination notes

- Rebased onto `da8b18d` (deploy-17) — onboarding-gate + landing-restore lanes
  landed mid-work; no conflicts (additive files).
- pick-race sibling: `pickGate.ts` + `pickRace.test.ts` gates updated for the
  new `place` phase — stay/advance allowlists assert `"place"` explicitly.
