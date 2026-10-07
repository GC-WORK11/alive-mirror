# iOS cold-launch residual — RELEASE config measurement

Lane: ios-release. Question from the lead: does the **Release** iOS build
actually crash? Context: the 72a3d9a dev-client residual re-verified at
14/30 (46.7%) — but every kill's victim thread was mid-`consoleTaskRun`,
the React DEV inspector's console-replay task, which does not exist in a
Release build. This lane measures the release binary directly.

Rig: this macOS box, iPhone 17 sim EDD9B083-63F1-44E6-9A7B-0A6964CC2561
(iOS 26.5) — same device identity as ios-residual / reverify rigs.
HEAD `c86074f` (Mobile code unchanged since 72a3d9a: only docs + a
server-side cache commit landed after).

## TL;DR — Release does not reproduce the residual

| Build | Rig | Cold cycles | Kills | Rate | Wilson 95% |
|---|---|---|---|---|---|
| Debug dev-client @72a3d9a (reverify) | prior rig | 30 | 14 | 46.7% | [30.2%, 63.9%] |
| **Release-iphonesimulator @c86074f** | this box | **30** | **0** | **0%** | **[0%, 11.4%]** |
| **Release-iphonesimulator @c86074f (batch 2)** | this box | **30** | **0** | **0%** | — |
| Release combined | this box | 60 | 0 | 0% | [0%, 6.0%] |

Release 0/30 vs Debug 14/30: two-proportion z ≈ 4.3, Fisher one-sided
p ≈ 8.4e-6 — **the release rate is decisively different from the dev
rate**. Release is NOT merely "same residual, worse luck".

**Demo-honest statement**: "the iOS release demo build survived 60/60
cold launches on the reference rig (dev-debug build fails ~47% of cold
launches — the crash victim is a dev-inspector task that doesn't exist
in release builds)." Whether the underlying corruptor is gone or just
finds no victim is unproven — see §Interpretation. A **device** release
build is unmeasured — the RN patch is `#if TARGET_OS_SIMULATOR` only and
this rig has no device.

## Build recipe (what was measured)

```
cd Mobile/ios && pod install          # RCT_USE_PREBUILT_RNCORE=0 (RN from source)
xcodebuild -workspace ALive108.xcworkspace -scheme ALive108 \
  -configuration Release -sdk iphonesimulator \
  -destination 'platform=iOS Simulator,id=EDD9B083-…' \
  -derivedDataPath ~/dd-rel CODE_SIGNING_ALLOWED=NO build
simctl install EDD9B083 …/Release-iphonesimulator/ALive108.app
```

Environment: `EXPO_PUBLIC_API_URL=http://65.2.28.40` baked at bundle time
(verified: `main.jsbundle` embedded in .app, 11.4 MB, contains the IP once;
no Metro needed/used). Hermes: prebuilt release xcframework tarball.
Notifications + location permissions granted once; onboarding completed
once so every cycle lands on the real home UI. One-time box fixes:
`npm install` restored missing `expo-build-properties` (the classic
partial-node_modules `PluginError` in the EXConstants app.config phase)
and `npx patch-package` re-applied `react-native+0.86.3.patch` (verified
in-source; the hop's `RuntimeSchedulerCallInvoker::invokeAsync` symbols
are present in the Release dSYM).

## Method — matched to ios-residual, deltas listed

Per cycle (n=30/batch): `simctl terminate` → `simctl launch` (fresh pid)
→ poll `simctl io screenshot` until app-content (light-pixel fraction
≥0.55; home screen measures 0.23, app screens 0.92 — recalibrated from
the >100KB rule which SpringBoard wallpaper false-positives) → exercise
→ liveness guard through launch+22s (covers the dev kill window of
13–16s plus margin) → `simctl terminate`.

Oracles (three, independent):
- pid liveness `kill -0` per cycle through the window — 0 deaths
- runningboardd unified-log stream: every observed exit is
  `domain:frontboard code:force-quit(0xfbfbfbfb)` (my terminate).
  `domain:signal code:SIGSEGV(11)` count for the run window: **0**
- `~/Library/Logs/DiagnosticReports/ALive108-*.ips`: **0 files**

Honest deltas vs the dev-build harness:
- No per-cycle lldb attach. Nothing crashed, so there was nothing to
  attach to; .ips would have been the capture path (none produced).
- Exercise is `simctl location set 28.6139,77.2090` per cycle (fires real
  CoreLocation → ExpoModulesJSI promise traffic — the same corruptor
  class suspected in reverify) instead of CoreGraphics UI taps — this
  box has no scripted-tap path wired and taps were never the trigger;
  boot churn is.
- Release renders in ~2s (embedded bundle) vs ~7s on Metro — launch-to-
  death window observed is the same clock time regardless.

## Interpretation

Verified facts:
1. Same app code, same RN patch (compiled in — sim-only by design),
   same sim, same prod backend. Only the build config changed.
2. 60 release cycles, zero kills; dev-debug was ~1-in-2 fatal.
3. The dev victim was always `consoleTaskRun` — a jsinspector task that
   only runs while a CDP inspector is attached (dev-client + Metro).
   Release never runs it.

Consistent model: the corruptor's writes were probably still racing the
JS thread in dev (the 9fbd851 hop only covered TurboModuleUtils::Promise),
but the *walk* that died was consoleTaskRun's render-wrap allocation —
in release that allocator simply doesn't exist, and the ordinary boot
allocators didn't hit the poisoned structures in 60 tries. The
alternative — the corruptor itself is inspector-driven (console replay
IS heavy off-thread jsi traffic) — is equally consistent with the data.
Neither can be distinguished without instrumenting the writer, which the
reverify already noted is never on-stack.

## Follow-ups / open caveats

- Device is the remaining unknown: patches are TARGET_OS_SIMULATOR-gated,
  so a device release build carries neither the fix nor the dev victim.
  Demo on the sim → clean; if anyone shows it on a device, it is
  unmeasured (no device on this rig).
- Second arm (instrument ExpoModulesJSI::JavaScriptPromise thread
  discipline) is unnecessary for the demo claim and deferred — the
  release question is answered.
- If the demo must use the dev-client (Metro features), the 46.7%
  cold-launch residual still stands — release binary is the honest demo
  vehicle.

## Artifacts / repro

- `~/residual/autocycle.sh` — cycle driver (release-adapted)
- `~/residual/cycles-release.tsv`, `cycles-release2.tsv` — 60 marks
- `~/residual/logs-release/stream.log` — runningboardd stream (all exits
  force-quit; zero signal exits)
- `~/residual/renderdetect.py` — app-content render detect (light-px)

```
cd ~/residual && bash autocycle.sh release 30
```
