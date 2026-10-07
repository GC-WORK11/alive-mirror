# sigbus-release lane report — early-search SIGBUS on iOS Release (sim)

Lane scope (dispatch): reproduce nav-journey's Release SIGBUS at early
search-sheet open, capture the stack, root-cause the uncovered Release
path, fix the general mechanism, verify 30+ cycles + cold path, check
Android, tsc+lint, report, push to `base/v2`.

## Verdict

**0/40 crashes** on the final Release binary (`fix5`) under the full
repro — fresh install, early search-sheet exercise while tiles settle.
Before the fix set: **9/35** (~26%) on the same harness. The fault class
is closed on the sim build; the corrupting event was identified by
elimination + A/B: **Hermes young-gen semi-space copies** (see below).

## Reproduction

Harness: `~/residual/autocycle.sh <label> N reinstall` — per-cycle
`simctl install` of the Release app (`~/dd-rel/…/Release-iphonesimulator/
ALive108.app`) on iPhone 17 sim `EDD9B083` (iOS 26.5), launch under lldb
with a SIG* stop-hook (registers + backtrace + thread list), scripted
taps: search CTA ~5–9 s post-launch while map tiles settle — the
nav-journey trigger. Taps are not required (`NOTAP=1` cycles crash too);
the sheet open only widens the window.

## Stacks (captured)

All crashes share one victim: the JS thread inside
`TimerManager::callTimer` → `Task::execute` → `TimerCallback::invoke` →
`HermesRuntimeImpl::call` → `interpretFunction` — the `t0.warm()`
`setTimeout(step, 0)` slice loop.

Fault forms:

1. `doGetByIdSlowPath_RJS+84` — `ldr x12, [x10, #0x18]` faulting at
   `0x{19,3d,…}00000068` (SIGBUS code=2). `x10 = base+0x50` — a pointer
   at `4MB-aligned segment base + 0x50`, i.e., into a Hermes
   `AlignedHeapSegment`'s head region whose page is PROT_NONE
   (`protectMetadata`) — the young-gen from-space after a scavenge.
   `~/residual/logs-fix3/lldb-{27,28,29,30,34}.txt`.
2. Same site, `x10` = tagged garbage (`0xfffd00010b0d33d0`,
   `lldb-32.txt`, `logs-ts1/lldb-04.txt`) or a **raw double bit pattern**
   (`0x3ff199999999999a` = `1.1`, `logs-fix4/lldb-05.txt`) used as a
   pointer — a live HermesValue slot that stopped being a pointer
   under the collector's feet (or a slot re-pointed at scavenged memory).
3. `CardBoundaryTable::updateBoundaries` inside
   `FixedSizeHeapSegment::setCellHead` ← `OldGen::search` ← `allocSlow`
   ← `materializeLazyIdentifier` — corrupted old-gen metadata
   (`lldb-09.txt`).

`gcdbg` (os_log GC callback in `HermesInstance.cpp`) records **only
`GC Young Gen` events** in every crash window — the damaging event is
always a young-gen scavenge.

## Root cause — proven shape

What was eliminated (each shipped anyway, real bugs):

- Off-thread jsi destructs on the Swift side → all hop to the JS thread
  (DeferredJSIBox box-and-hop; earlier `deallocate`/`dealloc`/
  `contextDeallocator`/SharedObject-releaser hops retained). Crashes
  persisted.
- `@JavaScriptActor` continuation hops via `RuntimeScheduler.
  scheduleTask` (`enqueue`) — persisted.
- **All virtual `jsi::Runtime`/`IRuntime` calls serialized** —
  `makeThreadSafeHermesRuntime` wraps the runtime (213 decorated
  virtuals; `HermesJSRuntime` gets `HermesRuntime&` via
  `getUnsafeRuntime()`). Crashes persisted at ~26% (1/4 sanity).
- `warm()` burst timing: stubbed → **12/12 clean**; deferred +15 s →
  **14/14 + 2/17** (partial mitigation only — the burst remains
  vulnerable whenever it runs while YG exists).

The discriminator: **`withAllocInYoung(false)`** — all allocations go
straight to old gen, the young-gen collector is never armed, no
semi-space copies ever happen → **40/40 clean**. Since every captured
fault is a stale pointer into a just-scavenged semi-space segment and
gcdbg only ever shows `GC Young Gen` in-window, the corruptor is a
scavenge that loses/duplicates a pointer (a GC-root miss or sim-specific
copy bug inside Hermes 0.17); with no scavenges there is nothing to
corrupt. Old-gen compaction (Hades) evidently does not produce it.

## Fix set (all sim-gated)

1. `HermesInstance.cpp` (react-native patch): `withAllocInYoung(false)`
   inside the existing `#if TARGET_OS_SIMULATOR` gcConfig block — **the
   mechanism fix**; deliberately no `RevertToYGAtTTI` (the deferred
   burst lands post-TTI and would re-arm YG). Plus the
   `makeThreadSafeHermesRuntime` wrap (kept — closes the whole
   off-thread-*call* class) and the coldfix heap sizing/metadata
   protection/gcdbg.
2. `src/search/t0.ts`: `warm()`'s first call schedules the burst at
   `WARM_DEFER_MS = 15000` (idempotent; later calls no-op). With
   OG-only alloc this is belt-and-suspenders, kept because it removes
   the one giant early burst from the busiest window; queries before
   it finishes use the existing lazy `buildSlice` path.
3. `expo-modules-jsi+57.1.1.patch`: DeferredJSIBox + deinit hops +
   `enqueue`/`destroyOnJavaScriptThread`/`reactorScheduleHook` (mechanism
   coverage for the off-thread-destruct class — real bugs fixed this
   lane even though not THE corruptor).
4. `expo-modules-core+57.0.20.patch`: SharedObject releaser hop.

All three patches regenerate clean vs pristine npm sources
(`/tmp/expo-pristine/*`, `patch --dry-run` verified).

## Verification

- `cycles-fix5.tsv`: **40/40 alive** — fresh install, CTA tap ~5 s,
  sheet open/type while tiles settle, each cycle ~35 s (covers the
  deferred 15 s warm burst).
- Cold path unaffected: render ~5–6 s unchanged; all exercise taps pass;
  search warm still completes (deferred) and lazy-builds on demand.
- Gates: `npx tsc --noEmit` clean, `npx expo lint` clean.
- A/B table below is the evidence chain.

| run | binary | cycles | crashes |
|-----|--------|--------|---------|
| baseline (hops v1) | Release | ~28 | 4 |
| fix2 dealloc hops | Release | 16 | 4 |
| fix3 deferred-destroy | Release | 35 | 9 |
| notap | Release | 8 | 1 |
| ts1 ThreadSafe only | Release | 4 | 1 |
| bisect-nowarm | Release+TS, warm() stubbed | 12 | 0 |
| bisect-defer | Release+TS, warm deferred | 14 | 0 |
| fix4 TS+defer (gate) | Release | 17 | 2 |
| **fix5 TS+defer+OG-alloc** | **Release** | **40** | **0** |

## What remains (honest risk)

- OG-only allocation means every alloc goes to Hades old gen — full GCs
  still possible in very long sessions; with 512 MB init / occupancy 0.9
  none fired in any cycle (gcdbg silent on fulls). Sim-only; device keeps
  stock generational Hermes (crash class never observed on device).
- The corruptor is pinned to YG scavenges but not to a single instruction
  — if a fault ever reproduces with `AllocInYoung=false`, next step is a
  hardware watchpoint on `segment-base+0x50`/`+0x18` during a scavenge.
- warm()'s defer trades a little first-search latency in the 10–15 s band;
  index lazy-builds meanwhile, results stay complete.
- Android KVM: no Android SDK/emulator on this VM — the same race could
  not be exercised here; no lane has ever observed it on Android.
  Recorded as unknown-clean, not verified-clean.
- ThreadSafe lock is hermes' re-entrant `RuntimeSharedMutex`; 40 cycles
  incl. full host-function coverage show no deadlock.

## Files

- Patches: `Mobile/patches/react-native+0.86.3.patch` (regenerated —
  includes AllocInYoung + ThreadSafe + coldfix gcConfig),
  `expo-modules-jsi+57.1.1.patch`, `expo-modules-core+57.0.20.patch`.
- Source: `Mobile/src/search/t0.ts` (`WARM_DEFER_MS`).
- Logs: `~/residual/logs-{fix3,ts1,fix4,fix5}/`,
  `~/residual/cycles-*.tsv`, harness `~/residual/autocycle.sh`.
