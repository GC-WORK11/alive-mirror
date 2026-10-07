# map-perf lane — Android KVM measurement report

Frame numbers before/after the map-perf tune on the Android emulator rig.
**BEFORE = `1ada005`** (base/v2 pin). **AFTER = `d8c7b41` + `edc4666` cherry-picked** — see "the crash" below.

- Rig: AVD `demo` (pixel_7, android-35, google_apis x86_64), `emulator -gpu swiftshader_indirect -no-window`, `/dev/kvm`.
- BEFORE APK: 137,189,260 B, sha256 `40ca9b80f9f0eba391ec33016286acd2308ad9b197aedb8d8e5624c283d29298`.
- AFTER APK: 137,195,736 B, sha256 `418341ab84df2e8002ca4dd4ce47b3bb374974824a402cddd0e361efa08351bb`. Bundle grep `http://65.2.28.40` = 1.
- Measurement dir `~/mapperf/{before,after}/`: per-window `.mp4` + `-sf.txt` + `-sf-sorted.txt` + `-gfx.txt` + `-framestats.txt` + `-fence/-t0/-t1`. Scripts `~/rig/` (same bytes both runs).

## ⚠️ d8c7b41 crashes Android on launch — unmeasurable as pinned

`UnexpectedNativeTypeException: Value for value cannot be cast from Double to ReadableArray` in `MLRNStyleFactory.setIconPadding` at `onMapReady` — the gesture label-drop remounts the 14 basemap symbol layers as React `<Layer>` children, and `v2-light.json`'s spec-scalar `icon-padding` (10/8/6) hits MLRN-Android's float-array setter → **SIGABRT on every cold launch**. Reproduced on release APK (100%): splash → crash ~1s after map mount.

`edc4666` (offline-verify lane, landed after the pin) is the fix — a 22-line `rnSpec` wrap in `src/map/style.ts` that boxes numeric layout props into `[n]` for React-mounted layers only. AFTER was therefore measured at `d8c7b41` + that exact patch cherry-picked — zero behavioral delta besides "launches". If you want the as-landed number: **there is none; the build does not start on Android.**

## Instruments (named per row — per orchestrator correction)

| surface | instrument |
|---|---|
| map gestures (pan/zoom/slowpan/follow) | `dumpsys SurfaceFlinger --latency` on `SurfaceView[…MainActivity](BLAST)` — gfxinfo counts RenderThread only; MapLibre renders into its own GL SurfaceView, invisible to it |
| sheet UI (sheetcycle, homescroll) | `dumpsys gfxinfo` jank% + percentiles — RN UI goes through RenderThread; real |
| covered-cap | `/proc/<pid>/stat` utime+stime deltas → cores |

SF --latency = (desiredPresent, actualPresent, frameReady) ns; window frames = rows with actualPresent > fence-at-window-start. Interval stats computed on consecutive presents.

## Results

### Map-gesture windows — SF present-interval ms

| window | BEFORE frames | mean | p50 | p95 | max | AFTER frames | mean | p50 | p95 | max |
|---|---|---|---|---|---|---|---|---|---|---|
| a-pan | 49 | 502 | 501 | 519 | 531 | 48 | 502 | 501 | 519 | 527 |
| a-zoom | 63 | 510 | 502 | 518 | 832 | 65 | 502 | 501 | 513 | 523 |
| a-slowpan | 28 | 501 | 499 | 514 | 514 | 32 | 511 | 508 | 542 | 543 |
| b-pan | 48 | 502 | 501 | 516 | 521 | 48 | 502 | 501 | 517 | 526 |
| b-zoom | 63 | 510 | 501 | 532 | 780 | 64 | 502 | 500 | 517 | 521 |
| b-slowpan | 28 | 501 | 500 | 515 | 528 | 28 | 503 | 499 | 517 | 523 |
| **d-follow** | 45 | 502 | 501 | 518 | 522 | **96** | **191** | **153** | **603** | **818** |
| e-homescroll (map layer, covered) | 23 | 639 | 533 | 970 | 987 | **0** | — | — | — | — |

>16.7ms and >33.3ms share = 100% in every window on both builds (every present is a SwiftShader-slow frame).

### Sheet-UI windows — gfxinfo

| window | BEFORE frames | jank% | p50 | p95 | AFTER frames | jank% | p50 | p95 |
|---|---|---|---|---|---|---|---|---|
| a-sheetcycle | 285 | 80.0 | 77 | 101 | 7650* | 91.73 | 89 | 125 |
| b-sheetcycle | 151 | 82.78 | 73 | 113 | 1† | — | — | — |
| e-homescroll | 445 | 85.84 | 77 | 113 | 422 | 89.34 | 85 | 113 |

\* AFTER a-sheetcycle ran ~6min vs BEFORE ~60s — eaten-tap retap polling stretched the window; frame counts incomparable, percentiles indicative only.
† degenerate: every door tap eaten inside the window.

### Covered-cap CPU — cores (proc/stat, 15s)

| window | BEFORE | AFTER |
|---|---|---|
| covered-idle (home sheet up) | 0.63 | 0.70 |
| covered + sheet scrolls | 0.68 | 0.69 |
| exposed-idle (air map) | 0.01 | 0.01 |

## Read

**Honest headline: the SwiftShader floor (~501ms/present) swallows almost everything the tune does on this rig.** Present intervals are software-GL-bound at ~2fps, so pan/zoom/slowpan come out identical before/after to ±2%. That is the rig's ceiling, not a verdict on the tune.

Where the tune DOES show:

- **d-follow is the one window that broke the floor: 45→96 presents in a ~20s window, p50 501→153ms** (mean 502→191ms). Follow-mode camera tracking is a continuous region change — the label-drop fires there even without fingers. p95 603/max 818 show the old cost still appears on the slow tail (fix-step camera hops), but the median frame more than tripled its rate.
- **Covered-cap verified at layer level**: the map's SurfaceView presented 23 frames under the home sheet BEFORE vs **0** AFTER (e-homescroll; a/b-sheetcycle 0 on both). preferredFramesPerSecond=8 means the map stops offering buffers while occluded — exactly the intended behavior.
- **Covered-cap is CPU-neutral at proc/stat granularity** (0.63→0.70 core covered-idle, 0.68→0.69 scrolling — inside run-to-run noise). On SwiftShader the map was already nearly idle under the sheet (exposed-idle = 0.01 core both builds); the savings the cap targets are GPU-present savings, which this instrument can't see below noise. Expect the real win on-device, not here.

Where it does not show:

- **a/b pan/zoom/slowpan: unchanged** (~500ms all). Software rasterizer dominates; dropping symbol layout work doesn't dent a 500ms software fill/vertex cost. On a real-GPU phone the same layers would be the difference between 16ms and 8ms frames — unverifiable on this rig, honest negative.
- **Home-scroll jank unchanged** (85.8→89.3%, p50 77→85ms) — the sheet's own RN frames are the bottleneck; the map underneath was already contributing little either way.
- **Air field on/off indistinguishable** (a≈b everywhere, both builds) — ~780-cell field costs nothing measurable on SwiftShader.

## Scenario c — honest negative (both builds)

Route candidates unmeasurable on this rig (~2.5h total across both runs):

- `/v2/plan` never produced an options screen. Origin resolution: the app's own position read stays pinned to a stale far-away fix (Punjab, ~7200km shown on recents) even while `dumpsys location` proves fused delivers the mock (2397 locations to the app; `set-test-provider-location` works — `adb emu geo fix` delivers zero on this AVD, 53min observed). Every plan attempt → the app's honest "this trip sits outside Delhi NCR" verdict card. Cold-restart with CP mock pre-seeded → same verdict → it's the app's cached position, not the provider.
- Both-endpoints-via-search (orchestrator's route): From row never arms in this build's search (it appears only after a successful 'to' pick → compare, which the verdict preempts). "Choose on map" pin-drop works but the camera is parked on the stale region → pin lands outside NCR → same verdict.
- Search result-row taps: input-deaf on this rig — `input tap`, vertical+horizontal micro-drags, and sendevent all eaten except one CP recents pick ever landed. ~10 attempts on AFTER.
- Note: `c06f478` (post-pin) fixed "plan flow dead-ends when getCurrentPositionAsync fails — fall back to last-known fix" — likely related; the pos-cache staleness this rig hit may already be patched on tip.

RouteTint 11→8 commit-group change therefore has no numbers — also the confounder noted in the brief: `2590598` chooser-craft rewrote RouteTint between pins; any c measurement would have been combined-delta anyway.

## Rig caveats (reading guide)

- **SwiftShader = software GL: ~500ms/present floor on this style.** Absolute ms are ~30× a real phone GPU; BEFORE→AFTER deltas are the only signal, and deltas show up as *more presents per window* or tail-interval changes rather than lower p50.
- a used `iptables -A OUTPUT -d 65.2.28.40 -j DROP`; b flushed it + verified field paint (`b-field-check.png`).
- Sheetcycle windows are the ~10s-rapid-open/close ask from the tune brief — durations drifted between builds (eaten-tap retaps).
- Pinch→MapLibre-never-scales on this rig; zoom used double-tap-drag (QuickZoom) both sides, per protocol fallback.
- Videos attached per window; d-follow's = `d-follow2.mp4` (d-follow run 1 got eaten by a stray pin-card).

## Confounders between the pins

- `d8c7b41` map-perf tune + `2590598` chooser-craft RouteTint rewrite — only Mobile-touching commits in range (git log verified). All AFTER deltas carry both; none of e1e9d22+/later audit work included.
- AFTER build = d8c7b41 tree + `edc4666` style.ts patch (crash fix, verbatim upstream).
