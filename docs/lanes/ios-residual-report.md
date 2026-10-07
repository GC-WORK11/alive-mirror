# iOS cold-first-tap SIGSEGV — residual quantified + killed

Lane: ios-residual. Rig: macOS box, iPhone 17 sim (EDD9B083, iOS 26.5), dev-client
built from source (`RCT_USE_PREBUILT_RNCORE=0`, `ios.buildReactNativeFromSource`),
Debug-iphonesimulator, Metro JS, prod API `http://65.2.28.40`.
Parent-fix context: 3c24a5e jsi-destructor funnel (docs/lanes/sigsegv-coldfix-report.md).

## TL;DR — numbers

| Build | Rig | Cold cycles | Kills | Rate | Wilson 95% |
|---|---|---|---|---|---|
| HEAD 1dcac64 (3c24a5e only) | this rig | 30 | 12 | **40.0%** | [24.6%, 57.7%] |
| +Promise-call hop (this lane) | this rig | 30 | 0 | **0%** | [0%, 11.4%] upper bound |

Two-proportion z ≈ 3.87, p ≈ 5e-5 (Fisher exact ≈ 2e-4). Same rig, same harness,
minutes apart — the hop is the only variable that changed.

**Judge-card line**: "cold-first-tap residual on reference rig: 0/30 post-hop
(was 12/30 pre-hop on the same rig); independent rig had measured 2/24 on the
pre-hop build." 0/30 does NOT prove zero — it bounds the rate ≲11% (95%).

## Answering the outstanding question (pre/post-fix SHA)

`git show 34053b8` (addendum-3 in ios-cold-drive-report.md): the 22/24 residual
run was on `dc6d0cc` — **post-3c24a5e**, `[coldfix]` marker live in its boot log.
So the residual was measured *after* the destructor funnel. Honest headline:
the funnel took 40%→~8-14% on one rig, ~40% residual remained on this rig;
this lane's second hop closed it here.

## Harness (n=60 total)

Per cycle: `simctl terminate` → `simctl launch` → lldb attached
(`SIGSEGV -s true -p true -n false`, `-k 'bt all' -k 'detach'`) → poll
`simctl io screenshot` until device screen stops being a tiny all-black PNG
(render detection, ~10-14s) → real CoreGraphics click on the "Where to?" pill
→ drag across map → click sheet close → 3s settle → `launchctl list` liveness
check → terminate. Unified log streamed to file the whole run (launchd_sim +
runningboardd + process + MTLCompilerService senders). Cycles logged to
`ios-residual-logs/cycles.tsv`; lldb `bt all` per kill in
`ios-residual-logs/lldb-C*.txt`.

Prior-lane taps during the black pre-render window hit SpringBoard and launched
other sim apps (the "Fitness" interference); this harness waits for a rendered
screen first, so taps always land on the app.

## Crash signature — same class, wider family

All 11 lldb-captured kills: victim `com.facebook.react.runtime.JavaScript`,
`EXC_BAD_ACCESS (code=1)`, every other thread parked (`__psynch_cvwait`,
runloop, MapLibre workers). Walk sites:

| Kill | Victim frame | Fault addr |
|---|---|---|
| C04 | `IdentifierHashTable::lookupString+196` ← `rehash` | 0xac5e |
| C09 | `HadesGC::OldGen::search+692` | 0x1514102a8 |
| C11 | `IdentifierHashTable::lookupString+196` | 0xd5d6 |
| C12 | `HadesGC::OldGen::search+692` | 0x15580c670 |
| C18 | `HadesGC::OldGen::search+692` | 0x150c12158 |
| C21 | `HadesGC::OldGen::search+692` | 0x15500eb08 |
| C22 | `OrderedHashMapBase::get+228` (JSMapImpl) | 0x800000028 |
| C25 | `StringPrimitive::computeHash+144` | 0x2f |
| C26 | `HadesGC::OldGen::search+692` | 0x15540f508 |
| C29 | `HadesGC::OldGen::search+692` | 0x14d410890 |
| C31 | `CardBoundaryTable::updateBoundaries+16` | 0x15580351a |

(C01 killed before lldb was attached — runningboardd `code:SIGSEGV(11)` only.)

**Five distinct Hermes structures** walked into death — the "corruption is
constant, the walker varies" model at maximum breadth. Where the stack is deep
enough to see it (C04/C09/C12), the JS thread is inside
`jsinspector::consoleTaskRun` ← `consoleCreateTask` `$_0` — React DEV's
`console.createTask` wrapper around renders, i.e. the heaviest allocator during
cold mount. The victim is whoever allocates next.

## Root cause of the residual — the call, not the destructor

§7 of sigsegv-coldfix-report funneled jsi *destructors* and explicitly left
"`Promise::resolve_.call(runtime_,…)` on a module queue" untouched as
"architecturally allowed". `TurboModuleUtils::Promise::resolve`/`reject`
execute `resolve_.call` / `reject_.call` — and reject builds a `jsi::Object` +
`jsi::String` — on whatever module queue finishes the async turbomodule call.
That is a full off-JS-thread runtime mutation: identifier interning,
IdentifierHashTable rehash, GC bookkeeping — exactly the structures observed
dying. Cold boot is peak promise-churn (fetch completions, module init,
MapLibre, AsyncStorage), matching the ~10-20s kill window.

## Fix (sim-only, one surgical hop)

`TurboModuleUtils.cpp/.h` — added to `Mobile/patches/react-native+0.86.3.patch`:

- `Promise` gains `std::enable_shared_from_this<Promise>` (sole ctor site is
  `make_shared<Promise>` in `createPromiseAsJSIValue` — verified).
- `resolve`/`reject`: when the collection's CallInvoker is registered (the
  plumbing 3c24a5e added), the entire call — including reject's Object/String
  construction — hops onto the JS thread via `invokeAsync`; the captured
  `shared_ptr` self keeps the promise alive until the hop runs. No invoker →
  stock inline call, same fallback shape as `allowRelease`.
- `#if TARGET_OS_SIMULATOR` only; device builds unchanged.
- `result` is cloned once via `jsi::Value(runtime_, result)` — a pinned-value
  refcount++, not the list mutation identified as corruptor. Accepted risk,
  stated honestly.
- Binary-verified: `invokeAsync` reachable in `Promise::resolve`/`reject`
  symbols of the shipped `ALive108.debug.dylib`.

## Caveats / what this does NOT prove

- The mutator is inferred (open §7 hole + 0/30 post-hop + matching structures),
  not caught red-handed — lldb sees the victim, never the writer.
- Other off-thread jsi touches could still exist (MapLibre native internals,
  third-party modules). If a residual survives on another rig, diff the walk
  site against this table.
- `shared_from_this()` throws `bad_weak_ptr` if a Promise is ever constructed
  outside `shared_ptr`; no such site exists today.
- Kill-window asymmetry: D-series rendered ~12-13s vs C-series ~18s — boot
  settles faster post-hop (fewer racing queues), observed not claimed.

## Files

- `ios-residual-logs/cycles.tsv` — all 60+ cycle marks
- `ios-residual-logs/lldb-C*.txt` — `bt all` + registers per kill
- `ios-residual-logs/stream-sigsegv-lines.txt` — runningboardd
  `code:SIGSEGV(11)` exits + MTLCompilerService XPC lines for the run window
