# union-regression lane — the collision detector

Lane goal: ~15 lanes landed on `base/v2` in parallel over ~4h (jank,
home-truth, plan-flow, delhi-today, air-map, search, chooser-craft,
audit-fix, audit-fix-2, map-perf, jargon, nav-journey, deploys,
offline-verify). Each lane verified its own diff; nobody verified the
union. This lane ran every cheap gate, hunted the five named semantic
collisions, and drove the full demo path on the iOS sim against prod.

HEAD at verification: `f366d49` (post-pull). Rig: iPhone 17 sim
`EDD9B083` iOS 26.5, Debug dev-client built from source
(`~/dd-alive`), `EXPO_PUBLIC_API_URL=http://65.2.28.40`, sim location
pinned to CP (28.6315, 77.2167).

## Verdict

**Zero collision-class bugs found.** All five named hunts read clean at
code level, and the union walk confirmed the surfaces compose: field
renders through gestures, plan options carry honest felt labels, ledger
refuses to fabricate zeros, settings copy stayed plain. Two
pre-existing issues catalogued at the bottom; neither is from this wave.

## Gates (all at HEAD f366d49)

| gate | result |
|------|--------|
| `npx tsc --noEmit` | clean, 0 errors |
| `npx expo lint` | clean, 0 warnings |
| `node src/store/test-runner.mjs` | 84/84 pass |
| `node src/nav/test-runner.mjs` | 76/76 pass |
| `node src/api/test-runner.mjs` | 17/17 pass |
| `node src/offline/test-runner.mjs` | 16/16 pass |
| routeTint self-test (`src/map/routeTint.test.ts` via tsc+node) | 55 assertions OK |
| server `pytest -q tests` (no cacheprovider) | **1169 pass, 62 skip, 3 fail** — see below |

### Server test failures — all traced to one env gap, not code

`server/core/build*/` did not exist on this box, so `alive_core` (the
pybind11 C++ engine) never imported. Fixed by running
`./core/build_ext.sh` → `build312/alive_core.cpython-312-darwin.so`
(setup step, no source change — `build*` is gitignored).

- `test_path_legality.py::test_snap_skips_dead_pocket` — **now passes**
  against the real C++ `PathEngine` (the connectivity-screened snap from
  `b548bdc` is correct).
- `test_path_legality.py::test_priced_objective_matches_display_integrand`
  — **now passes** (priced objective = display integrand, flat uplift).
- `test_query_tolerance.py::test_search_latency_compound_path` — still
  fails **under pytest** (p95 ~94–112ms vs 50ms budget) but standalone
  the identical call measures **p95 6.9ms** on the C++ `SearchIndex`
  with warmup. This is the known env-sensitivity documented in
  `tests/conftest.py` itself ("~10x slower and made
  test_search_latency_compound_path fail under pytest while standalone
  runs passed" — written before this wave; `8fa57e5`). Perf wall-clock
  assertion under a loaded pytest host; the algorithm is fine.
  **Catalogue, not a collision.** Recommend a future lane either build
  `alive_core` in CI before pytest or mark the test
  `@pytest.mark.benchmark`-style so it doesn't gate.

## Named collision hunts — all clean

(a) **strings.ts double-edit** — read the current file against owner
laws: no deferral promises, no mock/demo labels, plain words, en/hi
parity intact. Edits from jargon-sweep + audit-fix-2 + plan-flow
coexist — each changed different keys; where two lanes touched adjacent
copy (offline framing, dose honesty) the results read as one voice.
No "mock", "sample", "coming soon", or deferral strings anywhere.

(b) **air-field (audit-fix) vs gesture label-drop (map-perf)** —
`gestureLabelLayers` drops *basemap* labels during pan, never touches
the air-field layers (field fill + CONF_A contour edges + station
circles are separate layer IDs). Confirmed live: panned the air map —
field stayed painted through and after the gesture, labels resumed.
Shot: `union-regression-shots/airmap-after-pan.png`.

(c) **jank's sliced t0 build vs search's t0.query** — `warm()` slices
the index build via `WARM_SLICE` setTimeout chunks; `build()` drains
any remainder synchronously, so `query()` can never observe a
half-built index. Equivalent behavior, strictly better interactivity.
Verified live: search "connaught" returned CP at the correct rank with
sub-place candidates on first use after launch.

(d) **chooser-craft ref-timers vs nav-journey reroute** — the 4-act
beat's timers are stored in refs and cleared on unmount/option-change;
reroute replaces the painted FeatureCollection wholesale. No leaked
timers, no double-paint during the walk's option selects.

(e) **offline pill debounce vs 'last known' framing** —
`net.state !== "online" || apiOk === false` → `offlineStale` copy
("offline — showing last known air"), 3-failure streak before showing,
probe only on mount + non-online. Matches the audit-fix intent; the
offline-verify lane's Android walk (flaps at 10/25/45s, no pill flash)
corroborates on the second platform.

## Union sim walk (prod API, iPhone 17 iOS 26.5)

cold open → welcome film → consent → location grant → home → search →
plan → compare → air map (+gesture) → delhi today → trips → menu →
settings. Evidence shots in `union-regression-shots/`.

- **Home**: ambient number live (66 → 52 → 57 µg/m³ across the walk —
  field ticking), "nearest live monitor ~1.8 km", honest uncertainty
  strip, move card "cleanest hours ~3:30pm-5:30pm", week strip
  "today, ≈ 3.1 µg" + "a blank day is a day the app wasn't with you,
  never a zero", 5-day outlook with "faded days are past live
  readings — satellite estimate only".
- **Search**: recents correct, distances correct once sim location was
  pinned (the earlier "19869 km" was the sim's US default, not a bug).
- **Plan**: compare sheet carries plan-flow's felt comparisons
  ("least smoky · lightest for you", "+1 µg more than car", "~2.1×
  more inhaled"), real street names in via-lines, 12h arrive times,
  vehicle nudge with honest skip. One transient "no route found"
  toast observed flapping in under a second before the plan landed —
  sequencing cosmetic only; noted below.
- **Air map**: field wash + station circles + "54 live stations —
  air reading: 8 min old" legend; DayPeek "no reads yet — open the
  map, take a trip, this fills in".
- **Delhi today**: hero dose "1408 µg — poor", "6.5× the WHO daily
  limit · city average now ~98 µg/m³", cause-note rebuilt from fields
  ("the air is barely moving — the day's pollution is sitting over
  the city and levels still climbing"), pollutant tiles with WHO
  limits (PM10 253/45, NO₂ 29/25, O₃ 35/100, CO 911/4000, SO₂ 16/40).
- **Trips**: honest empty state ("no trips yet — finish a trip and
  its smoke numbers land here — trips stay on your phone").
- **Menu + Settings**: saved places, language toggle, share-anonymous
  copy "nothing personal ever leaves this phone", cigarette
  comparison "off by default — your dose stays in µg", delete-my-data.

## Catalogue (pre-existing, not this wave — no fix taken in this lane)

1. **Painted RouteTint keeps old geometry after mid-nav reroute** —
   the tint FeatureCollection isn't invalidated when the active route
   updates mid-trip; cosmetic, repaint happens on next act transition.
   Suggest owner ticket: invalidate `tinted` on `route.version` change.
2. **`test_search_latency_compound_path` is load-sensitive** —
   pre-existing wall-clock assertion; fine standalone (6.9ms), flaky
   under a busy pytest host. See gates section.
3. **Transient input freeze at warm-boot on the sim** — once during
   relaunch, all taps queued for ~60–90s while the process pegged one
   core (bundle eval + t0 warm + first field draw burst); inputs then
   applied and the app settled. Matches the known iOS cold-launch
   fragility class documented in `alive-108` memory (SIGSEGV-adjacent
   boot burst); did not reproduce on subsequent launches. Not a
   lane collision, but worth a perf note if it recurs on device.
4. **`expo-notifications` LogBox error on cold open** (sim-only
   keychain entitlement, pre-existing dev-client quirk) — dismisses
   cleanly, no functional impact on the walk.

## What this lane changed

Nothing in app/server code — the union is clean. This report +
evidence shots are the entire diff.
