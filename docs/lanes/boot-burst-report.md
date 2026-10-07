# boot-burst-probe lane report — the warm-boot "input freeze" is a process death

Lane scope (dispatch): characterize the union-regression's "transient
~60-90s input freeze at warm-boot (queued then applied — known
boot-burst class)"; measure time-to-interactive on KVM Android with an
iOS-sim comparison; bound the freeze window (gate the t0 warm + pack
prefetch past first interactive frame / priority to input); honest
BEFORE/AFTER TTI table; push to `base/v2`.

## Verdict

**The freeze is REAL but it is a crash, not a stall.** On the iOS sim
the deferred `t0.warm()` burst kills the app **~17-24 s post-launch in
7/7 warm relaunches** (SIGBUS ×3, SIGSEGV ×4) — inside the same
Hermes young-gen/old-gen corruption class the sigbus lane chased
(`sigbus-release-report.md`). With `warm()` no-op'd the identical rig
survives **2/2** full 95 s probes. Early taps DO land (~1.5-4 s); the
"queued then applied" observation is taps landing on a corpse then on
SpringBoard. The 15 s defer didn't close the class — it moved the
detonation to t+15 s+, outside the sigbus lane's own repro window
(their cycles exercise search at 5-9 s, before the deferred burst fires).

## Boot order (base/v2, verified in code)

1. `index.ts` marks → `App.tsx` eval+mount; map mounts under splash
   immediately (not font-gated).
2. Boot effect: `/health` ping, `/reports` poll, `loadTrips`,
   `loadSettings`, `fieldBootRetry` → `fetchAirField` (`/grid?cells=28`
   ≈ 235 KB), `aqiPoll`, `loadConsent`.
3. `afterFirstFrame(1200).then(() => setTimeout(warmSearchIndex, 900))`
   — jank's boot-idle + 900 ms kickoff; `warm()` itself defers
   `WARM_DEFER_MS = 15000` (sigbus lane) before slicing.
4. `onDidFinishRenderingMapFully` → `warmBasemap` →
   `OfflineManager.createPack` `delhi-ncr-z9-13-r2` (NCR z9-13,
   `${API_BASE}/v2-light.json`).
5. Sim only: `drawHold.ts` `BOOT_WATCH_MS = 100000` holds the map pump
   at ~2 fps and makes mount commits wait for a draw-idle gap — a
   ~100 s window that makes ALL sim input look heavier than device
   (a second confounder in the union observation; `Device.isDevice`
   gates it off hardware).

## Measurement rig (iOS)

- iPhone 17 sim `EDD9B083` (iOS 26.5), Release build via xcodebuild,
  `EXPO_PUBLIC_API_URL=http://65.2.28.40`, all three npm patches
  verified inside `main.jsbundle`/node_modules.
- Probe: `simctl terminate → launch` (true warm relaunch, consent saved
  so no onboarding), `cliclick` pixel taps on the home "Where to?" door
  (real coords calibrated against the bezel-mapped window: door
  `827,314`, back `674,265`), screenshots 1 Hz + 4-shot bursts after
  each tap, `ps %CPU` 1 Hz, `runningboardd` stream for exit signals.
- lldb attach for stack capture (`SIGBUS/SIGSEGV stop`).

## iOS results — TTI and the death window

CPU signature every warm-enabled run: launch burst t+1-5 (~90-150%),
idle t+6-16, then the deferred `warm()` ramp (~17 s) → **process exit**
1-8 s into the burst. With `warm()` disabled: flat ~0-30% throughout,
no ramp, alive at 95 s.

| build (all warm relaunches)           | taps ≤15 s | at ~17-24 s         |
|---------------------------------------|------------|---------------------|
| BEFORE stock JS (probe2 r1, r2)       | land ~2-4 s| SIGSEGV, SIGSEGV    |
| AFTER input-yield, 0-gap (r3, r4)     | dialog-confounded* | SIGBUS, SIGBUS |
| AFTER trickle 50 ms gap (r1, r2)      | land       | SIGSEGV ~24 s, ~22 s|
| AFTER = 9e75472 (r5)                  | land; tap@20 s opens search ~0.5-1 s mid-burst | SIGBUS ~24 s |
| DIAG warm() no-op (r1, r2)            | land       | **alive 95 s+**     |
| AFTER first cold launch (probe-v1)    | search open ~2.5-3.5 s | **survived** (burst ran 17-34 s, then pack prefetch ~100% CPU to 95 s) |

\* r3/r4 early taps were eaten by a stray OS "Fitness" notification
dialog — tap data void for those runs; the crashes still count.

Tap-landing summary (valid runs): tap@1.5 s → search open by ~3-4 s;
taps at ~7-20 s → land, including one tap at ~20 s that opened search
in <1 s DURING the trickle burst (the input-yield working). After the
~17-24 s crash, everything lands on SpringBoard — the "freeze".

### Crash stacks (lldb)

- r-a: `hermes::vm::JSObject::getNamedDescriptorUnsafe` —
  `EXC_BAD_ACCESS code=1`, JS thread (`com.facebook.react.runtime.JavaScript`).
- r-b: `hermes::vm::HadesGC::OldGen::search` —
  `EXC_BAD_ACCESS code=2` at a `str x9, [x8, #0x4000]` store, JS thread.

Same victims the sigbus report catalogued (corrupted heap read inside
property access / old-gen metadata write). `indexRow()` does
~30 allocations/row × 124k rows — the burst is a young-gen scavenge
furnace; the corruption is in the alloc pattern itself, not the
macrotask length: 12 ms slices die, 50 ms-spaced trickle dies, only
not-running survives.

## What shipped (9e75472)

Input-priority for boot bursts — helps wherever the process survives
(Android pending; iOS lucky windows):

- `src/startup/idle.ts`: `noteUserInput()` / `msSinceInput()` — the
  root view's `onTouchStart` (both `App.tsx` branches) marks every
  touch-down; zero render cost, no responder steal.
- `search/t0.ts`: `buildSlice(maxRows, maxMs=Infinity)` — per-slice
  wall-time early-out (`WARM_SLICE_MS=12`); warm loop pauses
  `INPUT_YIELD_MS=1200` after any touch and spaces slices
  `STEP_GAP_MS=50` (~4× more idle headroom vs back-to-back timers).
- `map/tileWarm.ts`: `warmBasemap` waits for `INPUT_QUIET_MS=2000` of
  input quiet before creating the pack (still lazy, never deleted).

Honest limits: none of this prevents the Hermes corruption — measured.
It bounds input latency while the app lives and widens the survival
odds by keeping burst work off the input path.

## Recommended next moves (not this lane)

- **The real fix**: stop building the index at runtime. Emit a
  ready-to-query compact index at bundle time
  (`scripts/build_mobile_gaz.py` already produces the corpus) — the
  "124k-row parse + ~4M-alloc build" becomes a cheap load, the whole
  crash class and the burst both disappear.
- sigbus lane: their `fix5` harness exercised search at 5-9 s — the
  15 s defer moved detonation outside that window. Re-run their
  reproducer with a ≥40 s dwell to see the residual (this report's
  lldb frames match their fault forms 1 and 3).
- iOS testers: a "frozen" app at ~17-25 s post-launch is the dead
  process — check SpringBoard/pid before calling it a stall.

## Android (KVM)

Measurement rig: child session `fc1bc70f` (linux platform, pixel_7
android-35 AVD), warm-relaunch taps + uiautomator markers + per-thread
top + logcat ANR/crash watch — SAME protocol, BEFORE then AFTER at
9e75472. **In flight** — table lands here when the rig reports.
