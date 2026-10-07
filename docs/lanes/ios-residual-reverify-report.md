# iOS cold-launch residual — RE-VERIFY at HEAD 72a3d9a

Lane: ios-residual-reverify. Question from the tasking: does the 9fbd851
0/30 hold after `e2ff634` (chooser beat) + `b633a2d` (notify-path wiring)?
Same rig as ios-residual: iPhone 17 sim EDD9B083 (iOS 26.5), dev-client built
from source, Debug-iphonesimulator, Metro JS, prod API `http://65.2.28.40`.

## TL;DR — the 0/30 does NOT hold

| Build | Rig | Cold cycles | Kills | Rate | Wilson 95% |
|---|---|---|---|---|---|
| 1dcac64 pre-hop | this rig | 30 | 12 | 40.0% | [24.6%, 57.7%] |
| 9fbd851 (Promise hop) | this rig | 30 | 0 | 0% | [0%, 11.4%] |
| **72a3d9a HEAD (post e2ff634+b633a2d)** | this rig | **30** | **14** | **46.7%** | **[30.2%, 63.9%]** |

HEAD vs post-hop 0/30: two-proportion z ≈ 4.3, p ≈ 1e-5 (Fisher ≈ 1e-4) —
massively significant regression. HEAD vs pre-hop 12/30: χ² ≈ 0.26, p ≈ 0.61 —
**statistically indistinguishable from the un-fixed build**. The residual is
back at full pre-fix rate with the identical crash signature. **P0.**

Auxiliary cycles from the same session (harness bring-up + targeted
exercises, method details below): +1 crash in 8 additional cold launches
(rev1 1/5 valid + targeted 0/3) → 15 kills / 38 total cold launches ≈ 39%.

## Crash signature — identical to the pre-hop class

All 14 kills share the known signature. lldb attached per cycle
(`SIGSEGV -s true -p true -n false`, `bt all`, `-b` batch so traces flush):

- victim thread `com.facebook.react.runtime.JavaScript` (threads #9/#10) —
  same victim as pre-hop
- walk sites (all observed across the 14): `HadesGC::OldGen::search +692`
  (`ldr x10, [x8, #0x4000]` — reads past a GC segment end), 6 cycles;
  `CardBoundaryTable::updateBoundaries +16` (`strb` write fault), 3;
  `hermesFatalErrorHandler` (fatal abort addr=0x0), 1; rest same family
- victim context: every trace shows `jsinspector_modern::consoleTaskRun`
  (dev-inspector console replay) → `jsi::Function::call` → bound call →
  interpreter → `IdentifierTable::getOrCreateIdentifier` /
  `OrderedHashMapBase::doInsert` → OldGen alloc → dead on the walk
- runningboardd confirms each: `RBSProcessExitStatus domain:signal(2)
  code:SIGSEGV(11)` for the launched pid (stream.log)
- fault addrs vary (0x15bc0db58, 0x15e00224c, 0x15ec023a4, 0x16100ec28, …) —
  poisoned-heap reads/writes, not a fixed stale pointer
- kill timing: render ~7s then death during the exercise/settle window —
  launch+13–16s, inside the original 10–20s kill window

Canonical trace (cycle 01, `~/residual/logs-rev3/lldb-01.txt`):

```
* thread #9, name = 'com.facebook.react.runtime.JavaScript',
  stop reason = EXC_BAD_ACCESS (code=1, address=0x15ec023a4)
  frame #0  CardBoundaryTable::updateBoundaries +16        strb w8, [x0, x9]
  frame #1  HadesGC::OldGen::search +472
  frame #2  HadesGC::OldGen::allocSlow +48
  frame #3  IdentifierTable::allocateDynamicString +208
  frame #4  IdentifierTable::getOrCreateIdentifier +204
  frame #5  IdentifierTable::getSymbolHandle +32
  frame #6  RuntimeModule::createSymbolFromStringIDMayAllocate +224
  frame #8  Interpreter::interpretFunction +6104
  frame #12 HermesRuntimeImpl::call +760
  frame #13-15 jsi::Function::call (jsi-inl.h)
  frame #16 consoleTaskRun @ RuntimeTargetConsole.cpp:556
  frame #17 consoleCreateTask::$_0
  frame #31 Task::execute → frame #32-34 RuntimeScheduler_Modern event loop
  frame #63 RCTJSThreadManager runRunLoop → pthread
```

## The patch is present AND active in the binary

Checked `ALive108.debug.dylib` directly (this was my suspicion — a silently
lost patch was the cleanest explanation; it is NOT what happened):

- `Promise : enable_shared_from_this` in the class decl
- `Promise::resolve` disasm: `LongLivedObjectCollection::get` → `invoker()` →
  `weak_ptr<CallInvoker>::lock` → `shared_from_this` → `Promise::resolve::$_0`
  lambda built and dispatched through the CallInvoker vtable — the hop IS
  compiled in and executing
- `Promise::reject` disasm: same invoker machinery
- `npx patch-package` applied `react-native+0.86.3.patch` cleanly
  (TurboModuleUtils.cpp: 2× invokeAsync call sites present in source)

So the hop survives, and the residual still kills ~1-in-2 cold launches.
Honest read: **the JS-thread hop fixed one writer (or reduced one window);
the corruption now comes through a path the hop does not cover.**

## Targeted exercises of the touched paths (lldb-wrapped, 1 run each)

- **e2ff634 chooser beat**: CP → Noida International Airport, plan landed,
  options revealed with the staggered beat (Car AC 77.99km ≈18µg winner,
  windows-down/bike/bus/auto/cycle/foot candidates). Survived.
- **b633a2d remind-off (disarmDepart→cancelDeparture)**: Settings →
  "Leave-later reminders" ON→OFF. Fired the wired path; survived. NOTE:
  the full arm→cancel loop could not be staged — the depart-offer row needs
  `departSavedPct > 8` and today's Delhi curve is flat ("no meaningful window
  today"), so no OD pair offered a ping to arm. disarmDepart still executed
  the cancel machinery on nothing-armed.
- **b633a2d brief arm→cancel (cancelDailyBrief)**: "morning air alert"
  OFF→ON (real daily brief armed — the switch entered its disabled-arming
  state then read [checked=true]) → OFF. Survived.
- **b633a2d deleteAll** (disarmDepart + cancelDailyBrief + clearAllData):
  sidebar → "Delete my data" → confirm "delete". Full wipe executed — vehicle
  prompt re-appeared, state reset — survived.

One manual run does not clear these paths — it means the touched code itself
ran without dying once. The cold-launch residual dominates the risk picture
regardless of which path is exercised.

## Method — matched to ios-residual-report, deltas listed honestly

Same: sim, UDID, iOS, build recipe, Metro+prod API, terminate→launch→lldb
lifecycle, wait-for-render-before-tapping, `kill -0` liveness at checkpoints,
verdict table, Wilson reporting.

Deltas (all harness-side, none touch the app):
- render-detect now requires app-content (cream home-sheet >65% of pixels)
  not just >100KB — SpringBoard's wallpaper also exceeds 100KB and caused
  false instant "renders" plus the classic Fitness-interference tap when a
  cycle-5 crash left SpringBoard front-most
- taps fire as double-clicks (single taps get eaten while sheets settle —
  measured, not guessed) and each tap is pid-liveness-guarded
- a SpringBoard modal blocking render triggers one `launchctl kickstart -k
  system/com.apple.SpringBoard` respring + retry (needed once: the
  Fitness-notification dialog after the rev1 crash)
- lldb runs `-b` batch so `bt all` actually flushes before detach/quit

Artifacts: `~/residual/cycles-rev3.tsv` (30 rows), `~/residual/logs-rev3/lldb-*.txt`,
`~/residual/logs-rev1/stream.log` (unified log incl. SIGSEGV exit contexts),
`~/residual/autocycle.sh`, `~/residual/renderdetect.py`.

## Interpretation — why is it back?

Verified facts:
1. Patch present + active (disasm above). Not a lost patch.
2. Crash rate ≈ pre-hop (p≈0.61 vs 12/30), signature byte-for-byte
   characteristic — same victim thread, same walk sites, same
   consoleTaskRun context, same timing window.
3. The corruptor is never on-stack at the stop — the write is latent; the
   JS thread dies walking the poisoned OldGen/IdentifierTable structures.

Candidate corruptors (ranked, not proven):
a) **Other off-JS-thread jsi writes the hop doesn't cover.** The hop only
   wraps `TurboModuleUtils::Promise::{resolve,reject}`. Expo modules resolve
   through `ExpoModulesJSI::JavaScriptPromise` (Swift, present in the binary —
   337 related symbols). It dispatches via its own `JavaScriptActor`, not
   CallInvoker — a different code path with its own thread discipline.
   b633a2d wired more expo-notifications calls (cancelDeparture,
   cancelDailyBrief, disarm in deleteAll) — more expo-side async traffic at
   exactly the neighborhood of the residual.
b) **Module-queue jsi beyond resolve/reject** — `invokeInner`/`callSync`/
   CxxModule legacy calls, LongLivedObject lifetimes.
c) **The 0/30 itself was underpowered** — if the true rate post-hop was ~8%,
   0/30 happens ~8% of the time. Combined with (a)/(b) widening the window,
   this reconciles the two measurements cleanly.
d) jsinspector console-replay volume grew (dev-only victim site — Release
   builds don't run consoleTaskRun; see demo caveat).

## Demo-readiness caveat (do not overclaim)

The victim is `consoleTaskRun` — the DEV-inspector console replay that only
exists in Debug/dev-client builds. A Release/demo build has no consoleTaskRun,
so this specific victim disappears. BUT the corruptor (off-thread jsi write
into Hermes structures) is build-config independent — if it survives, it
finds a different victim or corrupts silently. The honest statement for the
demo: **iOS dev-client cold launches are currently ~47% fatal on this rig;
treat the 9fbd851 fix as re-opened. Whether Release crashes is unmeasured —
not a safe assumption either direction.**

## Repro

```
cd ~/residual && ./autocycle.sh <label> 30 std   # ~6.5 min
# evidence: cycles-<label>.tsv, logs-<label>/lldb-NN.txt
```

## Follow-ups (for the owner / next lane)

- The clean experiment: revert `b633a2d`+`e2ff634` on a branch, rerun 30 —
  isolates whether the regression is content (new jsi traffic) or the 0/30
  baseline was underpowered all along.
- Extend the hop to `ExpoModulesJSI` promise resolution if expo-side is the
  writer (binary audit shows JavaScriptActor handles its own hop — verify).
- A 60-cycle run would tighten the bound, but the verdict is already
  decisive at n=30: the residual is back.
