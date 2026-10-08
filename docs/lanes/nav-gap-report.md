# nav-gap-fix — lane report

Lane scope (dispatch): the lifecycle lane catalogued a dose-honesty bug —
backgrounded 4.6 min mid-nav → ONE resumed tick accrued the whole silent
stretch at the last-known driving speed (dose 0.2→2.1 µg, emissions
19→172 g ≈ 0.9 km of "driving" while parked, nothing disclosed). Fix it so
fix-gaps integrate honestly: dose at a rest profile (the air kept hitting),
distance + emissions paused until fixes resume; teleports don't mint
distance; the strip + receipt disclose the pause.

## What shipped

**`src/nav/gap.ts`** (new, pure) — the two decisions, importable by tests:

- `classifyGap(realDtS, fixAgeS)` — the stream is blind when either clock
  says fixes stopped: `realDt > FIX_GAP_S` (the ticker itself slept —
  background → foreground catch-up) or `fixAgeS > FIX_GAP_S` (ticker ran
  but the watcher starved — parked, GNSS dead, the 5 m distance filter
  swallowing a standstill) or `fixAgeS == null` (no fix yet at all).
  `FIX_GAP_S = 45` sits inside the brief's 30–60 s band.
- `jumpCreditM(advM, fixDtS)` — each fix's distance credit capped at
  `JUMP_CREDIT_MPS × fixDtS` (45 m/s ≈ 160 km/h — the most a Delhi ride
  can physically do). A resume-fix landing km ahead after dead time
  credits real riding (cap scales with the gap); a teleport in seconds
  drops the impossible part.

**`src/nav/counters.ts`** — `tick(dtS, v, ddM, conc, curve, mode, gap)`:
during a gap, dose integrates at `REST_VE_LPM = 10` (floor, not zero —
you sat there breathing) and the emissions ledger early-returns after
`travelledM += ddM`, so parked-time emits nothing and mints no distance.

**`src/nav/engine.ts`** — wires both: `pendM` accumulates
`jumpCreditM(adv, fixDt)` per fix; each tick computes `fixAgeS` from the
last fix timestamp, calls `classifyGap`, accrues `pausedSRef += realDt`
while blind, flips `gapActive` only on transitions, and passes `gap`
into `c.tick`. `NavSummary.pausedS` surfaces it; donation stays gated at
`distanceKm >= 0.1` (server `MIN_TRIP_KM`, else 422 → outbox drop).

**Disclosure** — plain words, no jargon element:

- live: a strip pill `navPaused` "ride meters paused — still counting
  the air" (gated: running + snapped + on-route + inside field); meta
  suffix "· paused ~{n} min" once `pausedS >= 45`.
- receipt: `receiptPaused` "ride meters paused ~{n} min — the air count
  kept going" in the provenance foot when `pausedMin != null`
  (producer-side 45 s floor — display stays dumb).
- en + hi for all three keys (hi parity is compiler-enforced).

**Not changed**: stop-and-go traffic. Fixes keep flowing → `fixAgeS`
stays young → never a gap → idle-rate emissions + full-VE dose keep
counting. Only FIX-GAPS pause. Verified by test below.

## How it's verified

**Node, real call path — 94/94** (`cd Mobile && node src/nav/test-runner.mjs`,
plus store 84 / api 17 / offline 16, `tsc --noEmit` + `expo lint` clean):

`src/nav/gap.test.ts` replays the exact bug through the same calls the
engine makes (`classifyGap` → `c.tick(…, gap)`, `jumpCreditM` → `pendM`):

- 60 s riding → 300 s silent → one catch-up tick: `gap=true`, dose grows
  at rest-VE, `co2G` and `travelledM` unchanged — no 172 g phantom.
- Ticker alive while fixes dead (parked, screen on): every second still
  `gap` until a fix lands; meters unpause on the next real fix.
- Teleport: 2 km in ~1 s credits 45 m; 2 km after 300 s dead credits all.
- Stop-and-go: 120 s idling at a light with fixes flowing → `gap=false`,
  full-VE dose + idle emissions accrue — real exposure stays real.
- `counters.test.ts` updated two pre-existing expectations to the new
  per-km emission form (`ef·max(ddKm, v·dt)` — resume-credited km emits
  per-km in its landing tick instead of a 1-s sliver).

**Simulator evidence** — iOS sim E0224A22 (iPhone 17, iOS 27.0),
Release build at HEAD. The scripted run survived end-to-end **3/3**
once `fda1083`/`585a717` (prebuilt-chunk index — `query()` never
sync-builds) removed the alloc-burst crash class that killed ~110
earlier attempts. Shots in `docs/lanes/nav-gap-shots/`.

Script (`~/navgap-cycle.sh`, window-anchored CGEvent taps): launch →
home → where-to → India Gate → compare → Start → drive ~310 m
(`~/nav-gap-drive.sh` steps 0–28, ~11 m/s) → **fix-gap injected by
`simctl location clear`** (the sim keeps redelivering the last point
on Cmd-Shift-H backgrounding — timers never sleep and fixes never gap,
so a simulated background-park exercises neither `realDt` nor `fixAgeS`;
`location clear` dries the stream exactly like "parked, GNSS dead") →
park ~130 s → `location set` + drive ~520 m (steps 29–75) → end trip.

**Verified live** (`driving-before-park.png`, `pill-live-during-gap.png`,
`meta-suffix-after-resume.png`, `receipt-paused-line.png`):

- ~45 s into the park the strip pill appears: **"ride meters paused —
  still counting the air"** — the fixAge-gap path firing on-device.
- After fixes resume: meta reads **"6 min · 3.1 km left · arrive
  8:49 pm · paused ~1 min"** — paused seconds (≈85 s) disclosed in the
  glance line.
- Receipt foot: **"ride meters paused ~1 min — the air count kept
  going"** — same number end-to-end (an earlier run that stayed
  fix-dead to the end read "~6 min", matching its longer blind stretch).
- Counters honest: distance 0.5 km total (~310 m ridden + a capped
  155 m reposition credit — **not** ~2 km of parked "driving"; the
  original bug minted ~0.9 km in 4.6 parked minutes); emissions tracked
  the ridden metres only (87→93 g across a 55 s park in the first run);
  dose kept accruing at the rest profile (≈0.2→1.3 µg) — the air kept
  hitting, nothing claimed it was riding.

**Bonus fix found during verification** — the meta row never rendered
its `· arrive` segment (or the new paused suffix) anywhere: the
template literal embedded a real newline before the `·`, and
`numberOfLines={1}` truncated everything past it. `NavChrome` now
builds `meta` by single-line concat — arrive shows for the first time
("· arrive 8:49 pm" in the shots).

## Rig history (context, resolved mid-lane)

This lane spent ~5 h unable to reach nav on sim: ~110 launches/cycles,
every transition ~50 % fatal (`EXC_BAD_ACCESS` `0xEC…` zap in Hermes,
same class sigbus/residual lanes catalogue). Two remote landings
cleared it: `9a0799a` (boot-storm `cap()` fix) then `fda1083`/`585a717`
(prebuilt-chunk index — the alloc burst the crashes rode on is gone;
ios-warm-reverify measured 15/15 warm alive). On the new arch the
script above passed 3/3 fresh-boot cycles; the earlier 40-cycle grind
on the old build completed 0.

## Residual / notes for other lanes

- **Sim backgrounding does NOT exercise the gap fix** — Cmd-Shift-H on
  the iOS sim neither suspends the JS timers nor starves the location
  watch (the last `set` point keeps re-delivering). To test fix-gaps
  on-sim use `xcrun simctl location <udid> clear` mid-nav — the real
  "parked, GNSS dead" shape. Real-device suspension still maps to the
  `realDt` catch-up path (unit-tested, not reproducible on this rig).
- One unexplained counter observation, flagged not fixed: in a run that
  ended while still fix-dead, emissions crept ~+96 g over ~2 min idle
  post-resume. `pendM` only grows inside `onFix`, so something was
  still delivering fixes (periodic re-delivery of the `set` point with
  adv>0 vs the last stale fix?) — worth a look if any lane owns the
  location-watch lifecycle on sim.
- `Mobile/patches/` must be applied to `node_modules` by hand on this
  box: `npm ci`/`npm install` postinstall is allowScripts-blocked and
  `npx patch-package` chokes on the `-x` exclude flags in the patch
  headers. `for p in patches/*.patch; do (cd node_modules/$(basename $p
  | sed 's/+.*//') && patch -p1 < ../../$p); done` — without it the app
  dies at launch ~100%. (The patches landed in `9a0799a` are already
  applied to this checkout's node_modules — verified via
  `patch --forward` reporting "previously applied".)
- iOS AX/`simctl ui` automation is unreliable on this box: iOS AX binds
  the first booted sim only, and RN Pressables don't respond — drive
  the sim via CGEvent taps anchored to the Simulator window instead
  (`~/simtap` + `osascript` window-bounds lookup; see
  `~/navgap-cycle.sh` for the working harness).
