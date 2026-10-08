# cold-soak-android lane report — does Android reproduce the iOS warm()-death class?

Lane scope (dispatch): the crash story was never directly tested on
Android. All SIGBUS/SIGSEGV hunts to date ran on iOS sim; the owner's
real device is Android. Prove it either way on a RELEASE APK built at
`base/v2` HEAD, running the cold-launch / warm-relaunch / early-input /
lifecycle protocol that kills iOS.

## Verdict

**Android does NOT reproduce the iOS warm()-death class.** 73 staged
events, zero app crashes, zero ANRs, zero tombstones, zero app-owned
FATAL lines:

| phase | scenario | n | crashes | ANR/stall | Wilson 95% upper (0 events) |
|---|---|---|---|---|---|
| A | cold launch + 42 s dwell through t+15 s warm() window | 33 | 0 | 0 | **10.4%** |
| B | warm relaunch (BACK → immediate restart), 42 s dwell | 20 | 0 | 0 | 6.8% (A+B=53) |
| C | early-input hammer: t+2 s sheet + typed query into sync build() | 10 | 0 | 0 | — |
| D | lifecycle: screen off/on ×4, rotate ×3, memory pressure ×3 | 10 | 0 | 0 | — |
| **all** | | **73** | **0** | **0** | **5.0%** |

`dumpsys activity lastanr` at end of run: **`<no ANR has occurred since boot>`**.
`/data/tombstones/` empty across the whole session (baseline-checked
before and swept after). Every `am_kill com.anonymous.app` in the
events buffer is this harness's own `am force-stop` (signs as
"stop com.anonymous.app due to from pid <shell>").

The deferred burst does fire on Android — per-cycle `top` samples inside
the t+15..42 s window sit at a median **74%** CPU and peak **107%** on
every single cold launch (iOS showed the same ~100% ramp immediately
before SIGBUS/SIGSEGV death). The process rides through it every time.
Hermes on Android simply survives the burst that Hermes-on-iOS-sim did
not: all native mitigations (`allowRelease` hop, deferJsi queue, Hermes
GC sizing) are `#if TARGET_OS_SIMULATOR` iOS-only and absent here, so
this is the real no-mitigation datapoint.

## APK provenance

| field | value |
|---|---|
| commit built | `9a0799a` (base/v2 HEAD at build time, Thu Oct 8 ~00:44 UTC) |
| sha256 | `78ad6c420436babcf7994e0e260be7df2887046e5c4a7f0a99766718fcd70997` |
| size | 137,213,192 B |
| bundle bake | `http://65.2.28.40` ×1; dev URLs (localhost/127.0.0.1/10.0.2.2/:8081) = 0 real hits (one benign `…Hospital`+`ocalhost` data substring) |
| flavor | release, `assembleRelease -x lint`, NDK 27.1.12297006, SDK 36 |

Commits landing on base/v2 AFTER this build (binary does **not** cover
them): `869ae21`, `ea5dfb9`, `b7bf20b` (deploy-8 + audits — server side,
app-neutral), `fda1083` (**index-prebuild: chunked prebuilt t0 index —
query() never sync-builds, lazy-build fallback**), `25dc9e5` (its lane
report). `fda1083` removes exactly the synchronous `build()` that Phase
C measured — rerun Phase C on it for the new number; the crash verdict
is unaffected in kind (strictly less synchronous index work ⇒ strictly
less exposure, not more).

## Phase detail

**A — 33 cold launches.** `am force-stop` → `am start -W` → 42 s dwell
(straddles the whole 17–24 s iOS death window) → scroll + open/close
"Where to?" → oracle. WaitTime: min 414 / median 514 / max 662 ms.
Every pid sampled alive at t+15/20/25/30/35/42, same pid at end.
0 FATAL EXCEPTION, 0 fatal signal, 0 ANR, 0 lmk kills of the app.

**B — 20 warm relaunches.** Same pid (10847) across all 20 cycles —
expected and load-bearing evidence: Android keeps the process + JS heap
alive through BACK/HOME, so the deferred burst runs **once per process
lifetime** and does not re-arm on relaunch. iOS dies because it
jetsams the process on backgrounding, making every "warm" relaunch a
fresh burst; Android's equivalent fresh-burst condition is what Phase A
measures. Warm WaitTime: min 143 / median 180 / max 251 ms. CPU still
runs 55–107% in the dwell window (tile/map work) — survives every time.

**C — early-input hammer, 10 cycles.** Force-stop → launch → tap "Where
to?" at t+2 s → focus search field → `input text connaught`. Result:
first result row at **15.9–16.2 s** after the keystroke, **10/10
cycles**, zero crashes, zero ANRs. The synchronous unbounded `build()`
in `t0.ts` (`while (!built) buildSlice(1<<30)`) blocks the JS thread
~16 s on this rig (iOS sim: ~10 s). **No ANR fires because the block is
JS-thread-only** — the EditText consumes and echoes keystrokes natively
on the UI thread; the user sees typed text sit idle ~16 s before rows
paint. Bad UX, not a crash. Post-`fda1083` this wait disappears
(prebuilt chunked index).

**D — lifecycle stress, 10 cycles.** Screen off/on mid-window ×4,
portrait↔landscape ×3, background + Chrome/Maps pressure ×3. All resume
alive (fresh pids where force-stopped by protocol; process killed-and-
restarted under real memory pressure is expected and not counted).

## Crash/ANR event table

None. No `FATAL EXCEPTION` or `fatal signal` line in the run names
`com.anonymous.app`; no tombstone was ever written; no `ANR in` or
`Input dispatching timed out` for the package; no Watchdog kill.

## Rig-quirk vs app-bug classification

| observation | class | note |
|---|---|---|
| `UiAutomationService … already registered` FATAL EXCEPTION bursts | **rig artifact** | `uiautomator dump` polled at ≤0.5 s collides with its own stale registration; the crashing pids are the dump tool, not the app. Fixed by ≥2.5 s poll spacing (phaseC2). Never a com.anonymous.app stack. |
| `am_kill com.anonymous.app … due to from pid …` | **rig artifact** | the harness's own `am force-stop`. |
| `empty #N` am_kills of chrome/webview/etc. | **rig artifact** | normal LMK trimming of background packages; app never appears on these lines. |
| `NativeAnimatedNodesManager: Illegal node ID set as an input for Animated.multiply node` | **app log noise (non-fatal)** | E-level, caught inside RN's guarded frame callback; sheet/list animations continue; seen once per search-sheet open. Worth a look someday — not a crash. |
| No basemap text labels under SwiftShader | known rig quirk | upstream maplibre-native; geometry/colors/UI text fine. |
| Location-permission dialog flashes at some launches | app behavior | runtime request even when granted; auto-resolves ~170 ms. |
| consent Skip writes `sharing:"on"` | documented app behavior | per dispatch; left ON (Settings undo not flipped — owner already knows the toggle exists). |

## Honest limits

- Emulator, not the owner's real handset: x86_64 KVM, google_apis
  android-35, SwiftShader GL. A real-device run (arm64, Adreno/Mali,
  OEM memory manager) is the remaining unknown — this report bounds the
  Android *emulator* behavior at ~5% (95% conf) worst-case crash rate.
- Phase B warm relaunches share one pid by Android's design; the
  fresh-process warm-burst condition on Android is cold launch (Phase A),
  which is what iOS "warm relaunch" degenerated into anyway.
- n=73 gives Wilson ~5% upper bound on any per-event crash probability —
  "substantially confirmed, not proven zero" phrasing applies.
- Phase C's first pass (phaseC/) produced two garbage `type_to_result`
  rows (58 s/134 s) from a broken field-focus flow + uiautomator self-
  crashes; superseded by phaseC2 (10/10 clean, 16 s). The phaseC raw
  logs stay on the box for audit; CSV rows marked accordingly.

## Evidence on this box

`~/coldsoak/{phaseA,phaseB,phaseC2,phaseD}/` — per-cycle full logcat
dumps + `results.csv`; combined CSVs and logcat excerpts committed next
to this report (`android-coldsoak-cycles.csv`,
`android-coldsoak-input-lifecycle.csv`,
`android-coldsoak-logcat-excerpt.txt`).

Rig: JDK 17 + node 20.19.4 + SDK36/NDK27.1 + AVD `demo`
(pixel_7, android-35 google_apis x86_64, 1536 MB, swiftshader).
