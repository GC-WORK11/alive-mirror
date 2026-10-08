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

**Simulator evidence** — _see "On-device run" below._

## On-device run

**BLOCKED — rig-level crash, not a verdict on the fix.** The brief's
script (drive → background 5 min → foreground → resume) could not run:
the app cannot stay alive long enough on this box today.

Attempted on the patched Release build (jsbundle confirmed carrying
`navPaused`/`receiptPaused`), iPhone 17 sims EDD9B083 (iOS 26.5) and
E0224A22 (iOS 27.0):

- ~70 launches today: ~3 survived cold start; **0 survived the
  destination → plan render burst** (0/3 — needed before nav exists).
  Cold-start kills land at ~17–19 s inside the JS alloc storm; the two
  launches that beat it died at the plan tap (~60 s in) or ~286 s into
  light use. A full nav + background cycle never became reachable.
- Fresh-boot + quiet host is the only survival pattern found (2/2
  fresh-boot launches cleared cold start vs ~0/70 on warm-booted sims);
  crash debris churn (diagnosticd ~70 % CPU per kill) appears
  self-poisoning on warm sims.
- lldb attach on a Release launch caught
  `EXC_BAD_ACCESS addr=0xecececececececfa` in
  `hermes::vm::JSObject::getComputedPrimitiveDescriptor` on
  `com.facebook.react.runtime.JavaScript` — the `0xEC` freed-object zap,
  same UAF class `sigbus-release-report` and
  `ios-residual-reverify-report` pin to off-JS-thread jsi work racing
  young-gen scavenges. `gcdbg` still logs `GC Young Gen` in-window even
  with `[coldfix]` + `withAllocInYoung(false)` live in the binary.

What this leaves: the fix's tick semantics are node-verified through the
shipped call path (`gap.test.ts` feeds the real `classifyGap` /
`tick` / `jumpCreditM`); the platform behavior it intercepts — one
catch-up tick carrying the whole silent stretch at resume — was already
observed by the lifecycle lane (the 276 s tick, lifecycle-report). Still
unverified on-device: the paused pill + meta suffix + receipt line
rendering end-to-end. Re-run this script once the iOS-residual lane
closes the crash; the drive harness is `~/nav-gap-drive.sh` (UDID,
start, end — Rajpath line ~11 m/s) and the background step is
Cmd-Shift-H → wait → `simctl launch`.

## Residual / notes for other lanes

- **iOS sim rig is currently unusable for end-to-end runs** — this
  lane's own sim verification is the first casualty. ~70 launches
  today: ~97 % die in two windows (cold-start ~17–19 s; the
  destination → plan render burst 0/3). Patched Release build,
  `[coldfix]` confirmed live, reproduced on iOS 26.5 AND 27.0
  runtimes. The `sigbus-release` "MEASURED CLEAN 0/60" verdict does
  NOT hold in this session — the corruptor is worse than their
  residual estimate. Whoever owns iOS stability next: the plan-render
  burst is a second, separate kill zone distinct from cold start.
- lldb attach on one launch caught
  `EXC_BAD_ACCESS addr=0xecececececececfa` inside
  `hermes::vm::JSObject::getComputedPrimitiveDescriptor` on the JS
  thread — the `0xEC` freed-object zap pattern; the same class
  `sigbus-release-report` pinned to young-gen scavenges. Notably
  `gcdbg` still logs `GC Young Gen` events despite the lane's
  `withAllocInYoung(false)` — worth a second look: the config applies
  but YG still scavenges (their "what remains" caveat reproduced).
- Survival trick that worked twice: `simctl shutdown all` → fresh
  boot → quiet host → single launch. Warm-booted sims with crash
  debris churn (diagnosticd) went ~0/70.
- `Mobile/patches/` must be applied to `node_modules` by hand on this
  box: `npm ci`/`npm install` postinstall is allowScripts-blocked and
  `npx patch-package` chokes on the `-x` exclude flags in the patch
  headers. `for p in patches/*.patch; do (cd node_modules/$(basename $p
  | sed 's/+.*//') && patch -p1 < ../../$p); done` — without it the app
  dies at launch ~100%.
