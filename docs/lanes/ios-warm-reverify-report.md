# ios-warm-reverify lane report — REFUTED: the storm was not the trigger; the prebuilt-index arch (585a717) killed the crash class

Lane scope (dispatch): at HEAD 9a0799a (boot-storm fix landed), prove or
refute "the storm's CPU saturation was the crash trigger" by re-running
the iOS sim death matrix: 30 warm relaunches, 15 cold launches, 10
early-typers — same Release scheme, same oracle as
sigbus-release-report.md / ios-residual-reverify-report.md
(RBSProcessExitStatus signal + SpringBoard-artifact check). If deaths
persist: capture the signature and take the next honest step.

## Verdict

**REFUTED.** The t+15-deferred `warm()` burst still kills warm
relaunches at 9a0799a — **30/30 dead at t+21-24** (27×SIGBUS(10),
3×SIGSEGV(11)) — same window, same signals, storm long gone (boot-storm
measured the CPU quiet by t≈111). The storm spike was never the trigger.

The trigger is the index-build alloc burst running **concurrently with
other work**: every fixed-time auto-trigger lands inside some window —
map + tile-prefetch churn at t+16, boot/permission/`/v2/city` churn at
t+5. The same build run by a real query in a quiet slot (t+6, home)
survived **10/10**; sliced builds on *idle* onboarding survived **16/16**.

**While this lane ran, `585a717` landed the prebuilt-chunk index**
(`hydrateNext` — 36 × ~0.9 MB shards, one bounded merge per macrotask;
`query()` no longer builds at all — it answers honest-miss until
`onIndexReady` replays). Rebased onto it and re-measured: the hydrate
burst survives the *same* warm-relaunch window **15/15 @dwell 50**, a
manual `karol` query at t+20 returns the full result list, 3/3 typer
cycles alive. The structural fix every lane kept flagging — prebuilt
index, no per-row alloc storm — is what actually closed the crash class.

**No sim gate ships in this commit.** It was built and verified on the
old arch (15/15 warm + 5/5 cold + 5/5 typer alive with
`warm()` → never-run when `!Device.isDevice`) but dropped on the rebase:
on the new arch `query()` never builds, so gating `warm()` would leave
the index permanently absent on simulators (search dead on sim) — and
the 15/15 shows it isn't needed anyway.

## Pre-fix matrix @9a0799a (evidence `~/warmreverify/`)

| phase | n | dead | when | signals |
|---|---|---|---|---|
| warm relaunch (home, door taps t+5/+8, dwell 32) | 30 | **30** | t+21–24 (12×21, 6×22, 11×23, 1×24) | 27×SIGBUS(10) + 3×SIGSEGV(11), all `RBSProcessExitStatus domain:signal(2)` |
| cold launch (fresh install → onboarding, dwell 34) | 15 | 0 | — | early-boot residual gone at HEAD (prior lanes: ~39–47%) |
| early-typer (door t+4.5, type `karol` → sync `build()` ~t+6) | 10 | 0 | — | survives; build preempts the deferred warm |

Oracle: `kill -0` 1 Hz + runningboardd `RBSProcessExitStatus` +
post-death screenshot classifier (SpringBoard-artifact check). No `.ips`
files are written for sim crashes on this rig — signatures below come
from lldb attach + `sample`.

## Signature (new captures this lane)

lldb attach at t+12 (survives the attach-perturbation, dies in-window):

- pid 26460 — thread **hades** (Hermes concurrent GC marker):
  `EXC_BAD_ACCESS (code=1, address=0xecececececc0f3b0)` at
  `HadesGC::MarkAcceptor::acceptHeap(GCCell*, void const*) + 76`
  (`ldr x11, [x8, x9, lsl #3]` — marker chasing a **0xEC-poisoned**
  cell-table entry).
- pid 26693 — thread **com.facebook.react.runtime.JavaScript**:
  `EXC_BAD_ACCESS (code=1, address=0xefefefefefefeffd)` at
  `JSObject::getComputedPrimitiveDescriptor + 288`
  (`ldrb w10, [x10, #0xe]` — reading a **0xEF-poisoned** object's
  descriptor storage).

`sample` during a dying window (pid 24924, dead t+22): the JS thread is
inside `TimerCallback::invoke → interpretFunction → arrayPrototypeMap →
stringPrototypeReplace → regExpExec → searchWithBytecode /
regex::Context::match` — i.e. the `indexRow` `nrm` normalize driven by
the warm() slice loop's `setTimeout` steps. gcdbg `GC Young Gen` events
run right up to every death — `withAllocInYoung(false)` still does not
suppress scavenges.

Both victim sites are **reads of poisoned/freed Hermes heap objects** —
the corruption is in the heap, whichever thread walks it next trips the
fault. Same class the coldfix/sigbus lanes catalogued.

## Mechanism experiments (dispatch step 4, old arch @9a0799a)

| build | when/where | pattern | result |
|---|---|---|---|
| deferred warm() | t+16, home | sliced | 30/30 dead t+21–24 |
| deferred warm() → `build()` | t+16, home | atomic | **11/11 dead t+18** (atomicity is not the fix) |
| `query()` → `build()` | t+15, home | atomic | 2/2 dead t+17–19 (timer-context not required) |
| deferred warm() → `build()` | t+5, onboarding fresh-install | atomic | 2/2 dead t+6.4 (notif prompt + `/v2/city` in flight) |
| deferred warm() | t+16, onboarding (consent pending) | sliced | 16/16 alive — near-empty run loop |
| `query()` → `build()` | ~t+6, home | atomic | 10/10 alive |

Reading: death needs the burst **plus** concurrent heap traffic. On
home, the t+16 burst collides with map/tile-prefetch work (tile prefetch
itself is non-lethal — typer cycles sat in it 10/10). On fresh-install
onboarding, t+5 collides with boot/dialog/fetch churn. Idle onboarding
has no cofactor → sliced builds survive there.

## What shipped instead

The lazy sliced build died because it created hundreds of thousands of
small objects (regex-normalized `indexRow` entries) inside a churn
window — the concurrency law above made every fixed-time trigger lethal.
`585a717` replaces it with `hydrateNext`: per chunk, one ~0.9 MB
`require` (a single native JSON parse — few large allocations) + Map
sets, then the shard is freed. Different alloc shape, and empirically
non-lethal in the same window.

## Verification @HEAD (585a717 arch, Release, this commit)

| phase | n | dead | notes |
|---|---|---|---|
| warm relaunch, dwell 50 s | 15 | **0** | hydrate runs in the t+15 window that killed 30/30 |
| warm relaunch + door taps, typer path | 3 | 0 | manual `karol` query at t+20 → full result list |
| (old arch + never-run gate, dropped) warm/cold/typer | 15/5/5 | 0 | evidence the gate worked — kept as fallback data point |

Evidence: `~/warmreverify/warm-h15/`, `typer-h3/` (cycles.tsv +
stream.log + shots/) and `warm-v15b/`, `cold-v5/`, `typer-v5/` for the
dropped gate. Rig: iPhone 17 sim EDD9B083 (iOS 26.5), Release `~/dd-rel`,
`com.anonymous.app`, consent completed once.
