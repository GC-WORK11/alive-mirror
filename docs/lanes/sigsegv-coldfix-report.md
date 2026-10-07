# sigsegv-coldfix — cold-launch residual SIGSEGV root-caused and closed

**Lane:** sigsegv-coldfix · **Date:** 2026-10-07 · **Rig:** iPhone 17 sim `EDD9B083` (iOS 26.5), `com.anonymous.app`, Debug-iphonesimulator with `ios.buildReactNativeFromSource`

## TL;DR

The residual cold-launch SIGSEGV was never a mount-vs-draw race — it was an
**off-JS-thread mutation of Hermes' GC state**: `jsi::Function`/`jsi::Object`
destructors running on native module queues invalidating runtime-owned handles,
which corrupts Hermes' old-gen / pinned-root bookkeeping. The next GC walk
(hades sweep or an old-gen alloc on the JS thread) dereferences the corruption
and dies — ~2 s after the burst, inside the cold-boot window.

Fixed at the funnel: sim-only hop of `LongLivedObject::allowRelease` and a
deferred-destroy queue for `TurboModule` `Promise` jsi functions, plus a large
initial/min heap to keep major collections out of the window. Every change is
`#if TARGET_OS_SIMULATOR` — device builds are untouched.

**Gate: 34/34 real cold launches, 0 crashes.** (20 search-sheet opens + 10
compare-sheet opens + 4 post-wipe relaunches — all inside ~15 s of boot,
well inside the 90 s window; taps driven as real touch.)

## 1. Reproduction (as spec'd)

Cold install/launch → tap "go somewhere" <90 s in while tiles stream →
SIGSEGV ~6–10 s post-launch, ~2.3 s log silence before death. Baseline rate
measured this lane: **~40%** of cold launches (16/46 across earlier iterations).
Post-wipe relaunches reproduce the same window (sibling lane c4a5f3fd — folded
into the gate below). Real touch taps matter: a11y presses skip most of the
native work and pass ~deterministically (parallel cold-drive intel — taps in
this gate are real `left_click`s, not AX presses).

## 2. Window analysis — the crash is latent corruption, not a race

`lldb --batch -p <pid>` with `bt all` stop-hooks on a live crash (PID 40805,
evidence: `docs/lanes/sigsegv-coldfix-bt40805.txt`):

- **Victim:** JS thread in `hermes::vm::HadesGC::OldGen::search` ← `allocSlow`
  ← `IdentifierTable::allocateDynamicString` ← `jsinspector::consoleTaskRun`
  ← `jsi::Function::call`. Died walking a freelist inside old-gen segment
  metadata.
- **Every other thread parked** — hades in `__psynch_cvwait`, MapLibre
  workers/main/workq idle. Nobody was inside hermes/react when the victim
  died ⇒ the heap was corrupted *earlier*, by a mutator that had already left.
  A mount-vs-draw race can't produce this; nothing was drawing.
- Earlier catches showed the mirror-image victim: hades itself in
  `OldGen::sweepNext`. Same class — the *walker* varies, the *corruption* is
  constant.
- `GCConfig.ProtectMetadata(true)` was armed as a tripwire and never fired ⇒
  corruption is internal to hades' own structures (freelists/pinned-root list),
  not a wild write from outside the heap.

**Mutator mechanism (patched):** anything holding a `jsi::Function`/`jsi::Object`
whose destructor runs off the JS thread calls `Pointer::~Pointer` →
`ptr_->invalidate()` → `ManagedValue<PinnedHermesValue>::invalidate`, mutating
the GC pinned-root list unsynchronized. Concrete sites found in our stack:

- `~SyncCallback` → `CallbackWrapper::destroy` → `allowRelease` → collection
  `remove` drops the last `shared_ptr` → `~CallbackWrapper` → `~jsi::Function`
  — on whatever module queue dropped the last ref (the `AsyncCallback` in
  `Function.h` does exactly this).
- `TurboModuleUtils::Promise{resolve_, reject_}` — **every async turbomodule
  method** creates one; it's never collection-registered, so its two
  `jsi::Function`s die inside e.g. an `NSURLSession` completion block on its
  queue.
- `bridging/AsyncPromise`'s `~SharedState` → `PromiseHolder::allowRelease` →
  `~jsi::Object` — same class, third site.

Same bug family as upstream hermes#1957 / expo#45374 / bluesky-social#10672 —
the iOS-26 simulator's aggressive early-life GC churn is what makes it fire
inside our first-90 s window. Expo's own JSI layer (`expo-modules-jsi`)
already fixed its half (#47454: `JavaScriptPromise.deinit` schedules releases
on the JS thread) — verified in source; the remaining exposure was all
RN-core-side.

## 3. Fix — `patches/react-native+0.86.3.patch` (7 files, all sim-guarded)

Delivered via patch-package (`postinstall`) +
`ios.buildReactNativeFromSource` (expo-build-properties plugin +
Podfile.properties.json); RN 0.86.3 ReactCore is otherwise prebuilt and
uneditable.

1. **`LongLivedObjectCollection` gains a registered `CallInvoker` + deferred
   queue.** `setInvoker()` is called from `CallbackWrapper::createWeak` and
   the `AsyncPromise` ctor (both sites already hold a jsInvoker). Funnel fix —
   one registration covers every `LongLivedObject` subclass.
2. **`LongLivedObject::allowRelease` hops to the JS thread** via that invoker
   (`invokeAsync { collection.remove(this) }`) instead of destructing inline
   on the calling thread. Covers `CallbackWrapper`, `PromiseHolder`, and any
   future subclass.
3. **`CallbackWrapper::destroy` defers** onto `jsInvoker_->invokeAsync` when
   invoked off-thread (composes with the allowRelease hop — double-hop lands
   in the same place).
4. **`~Promise` (TurboModuleUtils) moves `resolve_`/`reject_` into
   `deferJsi`**: the collection destructs them on the JS thread
   (`drainDeferred` scheduled per-defer, `clear()` at teardown).
5. **`HermesInstance.cpp` GC sizing:** `InitHeapSize 512 MB / MinHeapSize
   256 MB / OccupancyTarget 0.9 / kReleaseUnusedNone` — keeps old-gen
   occupancy low so no major collection runs inside the window at all
   (~30 majors in the first 7 s on stock sizing → ~17 total, and none during
   churn). `ProtectMetadata(true)` kept armed as a tripwire.
   `os_log_error("[coldfix] sim GC sizing applied")` confirms the guard on
   device logs.

Every block is `#if defined(TARGET_OS_SIMULATOR) && TARGET_OS_SIMULATOR`
(TargetConditionals included under `__APPLE__` — verified live, the marker
log fires). Hardware is untouched.

**Composes with, doesn't conflict with, `ced7672`** (press-in draw-hold on
both search CTAs): that paces draw work at touch-down; this removes the GC
corruption the early-life burst feeds into.

## 4. Dead ends (documented for the next lane)

- **`gcConfig.withAllocInYoung(false)`** — kills GC churn entirely (17 GCs,
  alloc==total) and gated 0/12, but **deterministically breaks `require()`**
  ("WeakMap key must be an Object"; `require(delhi-gazetteer.json)` returns
  undefined → "Cannot convert undefined value to object" at `t0.ts:346`).
  Reverted — cannot ship.
- **JSC swap** — RN 0.86 removed JSC from core; the community
  `@react-native-community/javascriptcore` 0.2.0 predates the 0.86
  `createJSRuntimeFactory` surface and needs a stale package + AppDelegate
  factory override. Not needed after this fix landed.
- **Hermes version bump** — no upstream hades fix exists for this class
  (app is on Hermes V1 250829098.0.17).

## 5. Gate log — final build (all patches + bundle)

Real cold launches = `simctl terminate` → `simctl launch` (fresh process,
process age <20 s at tap). Location preset to Delhi (28.6129,77.2295).

| Gate | Iterations | Taps in-window | Result |
|------|-----------|----------------|--------|
| Search sheet (`"go somewhere"` → tap 527,209) | 20 | ~5–8 s post-launch | **20/20 alive** |
| Compare sheet (search → Recent pick → compare options) | 10 | ~8–16 s | **10/10 alive** |
| Post-wipe relaunch (uninstall→install→onboarding→search) | 4 | ~10–15 s | **4/4 alive** |

Progression on the same harness: **40% → 19%** (heap sizing only)
**→ 5%** (+CallbackWrapper defer) **→ 0/30,34/34** (+LongLivedObject funnel +
`~Promise` defer + debug-probe removal). Crash oracle:
`~/sigsegv/simlog2.txt` shows the last SIGSEGV at PID 48259 on the
pre-funnel build; none after.

## 6. Don't-break checks

- Warm-sheet paths: search results render (local gazetteer `require` healthy —
  no WeakMap/undefined errors), pick → compare options → vehicle wizard all
  verified on the final build.
- `npx tsc --noEmit` clean · `npx expo lint` clean · `node
  src/nav/test-runner.mjs`: all 6 drawHold tests pass incl. 2 new boot-watch
  tests (the 2 `counters.test.ts` cold_start_km failures are pre-existing on
  clean HEAD, unrelated).
- First-map-load UX: 2 fps throttle window is bounded by `BOOT_WATCH_MS` and
  unchanged from the drawHold lane; `Device.isDevice` guard unchanged —
  nothing on hardware is throttled.
- Keyboard-on-tap: search field taps open the keyboard (verified in the
  compare-gate flow — typed "india gate"/"connaught" live).

## 7. Residual honesty

- Site coverage is "all found RN-core sites" — `jsi::Value` captured raw in a
  third-party native block (e.g. inside `@maplibre/maplibre-react-native`
  internals) could still hit the class; 34/34 observed post-fix and the
  mechanism is now the same shape Expo shipped for #47454.
- The ~Promise `resolve_.call(runtime_, …)` on a module queue is a full jsi
  call off-thread — architecturally allowed by RN and not the proven
  corruptor (destructors are); left untouched.
- `ProtectMetadata(true)` + the `[coldfix]` os_log marker ship as tripwires —
  if a future crash occurs inside the window, the tripwire converts silent
  corruption into an earlier, diagnosable abort.

## 8. Files

- `Mobile/patches/react-native+0.86.3.patch` — regenerated, 7 files (see §3)
- `Mobile/app.json`, `Mobile/package.json`, `Mobile/package-lock.json` —
  expo-build-properties + patch-package + postinstall
- `Mobile/ios/Podfile.properties.json` — `ios.buildReactNativeFromSource: true`
- `Mobile/ios/Podfile.lock`, `Mobile/ios/ALive108.xcodeproj/project.pbxproj`,
  `Mobile/ios/ALive108/PrivacyInfo.xcprivacy` — regenerated by pod install /
  prebuild for the source build
- `Mobile/src/map/drawHold.ts` — cold-boot watch (`noteMapBusy/noteMapIdle`,
  `BOOT_WATCH_MS`, idle-gated mounts) added earlier this session; `DEBUG=false`
- `Mobile/App.tsx` — boot-watch wiring (`onWillStartRenderingMap`→`noteMapBusy`,
  `onDidFinishRenderingMapFully`/`LoadingMap`→`noteMapIdle`)
- `Mobile/src/nav/drawHold.test.ts` — +2 tests guarding the watch wiring
- `docs/lanes/sigsegv-coldfix-bt40805.txt` — full 30-thread `bt all` at the
  captured crash (PID 40805)
