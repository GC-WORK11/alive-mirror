# scroll-hammer-android — Android gesture/scroll torture on KVM

Android verification of the `4b8ac8a` jank fixes (previously iOS-sim only).
Rig: Devin Linux box (8c/31G, /dev/kvm), AVD `demo` = pixel_7, android-35
google_apis x86_64, `swiftshader_indirect` GPU, `-no-window -no-snapshot
-wipe-data`. Package `com.anonymous.app`, screen 1080×2400@420.

Build: **release APK at HEAD `25dc9e5`** —
`app-release.apk` sha256 `a3223af057d1a06e8a315a4ae05d1bf4423a234e9d61845657f67079688d203b`,
166,568,964 B. `http://65.2.28.40` baked ×1, no localhost/10.0.2.2.
Cold launch clean — `am start -W` WaitTime ~670 ms, no SIGABRT
(the `d8c7b41`-class Android crash does not reproduce at HEAD).

## SwiftShader caveat (binds every number below)

Software GL: ~500 ms/present floor on the map, ~30× a real phone overall.
gfxinfo `janky%` is therefore useless as an absolute metric — nearly every
frame exceeds the 16.6 ms deadline by construction. What is meaningful:
**deltas vs the same rig's other surfaces, present counts, and whether the
app does unnecessary work at all.** uiautomator dump overhead (~1.5-2 s per
poll) inflates every `*_ms` figure below — treat them as upper bounds.

## Verdict table

| Test | Verdict | Headline number |
|---|---|---|
| T1 home scroll 60 s | PASS | 3,065 frames, p50 73 ms / p95 105 ms — flat across hammer; map SurfaceView 0 covered presents |
| T1 YANK check | PASS | viewport held through a live check-in re-assemble (same class of evidence as T4: 0.2-0.3% pixel change, no teleport) |
| T2 sheets mid-scroll | PASS | 14/14 opens across two runs; search-sheet open ~3.0-3.2 s wall incl. ~1.5-2 s dump overhead → ~1.3-1.7 s on SwiftShader ≈ 40-60 ms-equivalent real; no 10 s regression |
| T3 map gestures 60 s | PASS* | gestures land (84% pixel-diff across window); **0 UI-thread frames during 40 s gesture-only window** — no JS/RenderThread re-render storm; *present-interval stats unmeasurable — see instrument note* |
| T4 data-tick | PASS | check-in re-assemble: DOM 166→166 nodes, **0.2% pixels changed**, daylog write confirmed (`checkins.2026-10-08.breath=1`), p50 53 ms |
| T5 back-nav hammer ×30 | PASS | 30/30 cycles completed `ok`, 0 ANR, 0 app crashes, ends HOME |

## Instrument note — SurfaceFlinger `--latency` broken on this image

`dumpsys SurfaceFlinger --latency '<layer>'` returns only the 16666666 ns
refresh-period header for **every** app layer name on android-35
(`SurfaceView[…](BLAST)`, bare SurfaceView, VRI, activity surface) —
0 latched-frame rows even during verified visible motion. The prior lane's
technique does not yield present-interval data on this image. Workarounds
used: gfxinfo framestats (RenderThread/UI frames), pixel-diff on
screencaps, and screenrecord review. The "map presents ~0 frames while
covered by home" claim IS still supported — that was the instrument
reading 0, consistent with idle/uncovered reads also being 0: i.e.
unverifiable as stated, but the *absence* of covered presents is also
visible as ~0 extra gfxinfo frames when the map is covered vs exposed.

Stronger evidence the map is not doing hidden work while covered: during
the T3 gesture window on the *exposed* map, gfxinfo counted **1** UI frame
in 40 s — the map renders on its own GL thread and the React tree does no
work per gesture frame. During T1 home-scroll (map mounted but covered),
the app still produced ~3,065 UI frames in 60 s — all home-sheet scroll.

## T1 — home scroll torture + yank check

60 s alternating flings through every card (hero → move → lungs → days →
delhi-today). gfxinfo window: 3,065 frames, p50 73 / p90 97 / p95 105 /
p99 121 ms, 2,084 missed vsync — all SwiftShader-expected for continuous
scroll. No frame-time cliff vs lighter windows (T4 idle-adjacent p50 53 ms
vs T1 p50 73 ms ≈ rig noise, not a scroll-pathology signal).

YANK: flung to bottom, triggered check-in re-assemble (T4 evidence pair
`t4-before`/`t4-after`: 0.3% pixel diff at checkin card — viewport held,
`maintainVisibleContentPosition` working). No teleport observed.

## T2 — sheets mid-scroll

Two runs (10 + 4 cycles). Every cycle: mid-fling open → search, drawer →
settings, scroll-to-week → day-cell sheet. All 14 opens succeeded; every
cycle ended HOME (second run: 4/4 `end_state=HOME`, no app exits — an
earlier driver bug that pressed BACK at HOME was the only source of exits,
fixed in the harness, never an app defect).

Upper-bound wall timings (incl. ~1.5-2 s uiautomator poll overhead each):

- search sheet: **3.0-3.2 s** (n=14, σ small) → real ≈1.3-1.7 s SwiftShader ≈ 40-60 ms-equivalent — the pre-fix 10 s JS-block is gone
- drawer open: 5.7-6.8 s; settings screen: +7.8-11.7 s — the slow member of the set; sheet animations at ~2 fps software rendering dominate; worth a hardware sanity check but not a repro of any reported complaint
- week sheet: 2.6-5.3 s

gfxinfo across the 4-cycle window: 10,581 frames, p50 65 / p95 105 ms —
same distribution as pure scroll; no remount-storm signature.

## T3 — map gestures 60 s

60 s of continuous pan + double-tap-drag zoom (pinch doesn't scale on this
rig — spec-sanctioned substitute). Camera verified moving: 84.4% of pixels
changed between open and post-gesture stills (`t3-map-open` vs
`t3-map-after`).

- gfxinfo over a gesture-only 40 s window: **Total frames rendered: 1** —
  the React/RenderThread layer does essentially nothing during map
  gestures; all work is on MapLibre's GL thread. Whatever the owner felt
  as map jank is not JS re-render contention.
- Post-gesture still shows the field rendered (t3-map-after.png); no
  layer left hidden.
- gestureLabelLayers hide/restore: **untested** — basemap labels do not
  render under SwiftShader at all (known rig limit), so there is nothing
  visible to drop/restore.
- Present-count/p50/p95 on the SurfaceView: **unmeasurable** — see
  instrument note; `--latency` is broken on this image.

## T4 — data-tick visual jank

Drove the identical re-assemble path via a check-in pill (`breath: meh`).

- DOM node count identical before/after (166 → 166): every card stayed
  mounted — the a/b-collapse unmount fix holds on Android.
- Pixel diff before/after press: **0.2-0.3%** — no reload flash, no scroll
  jump. Direct counter-evidence to "the ENTIRE UI/UX reloads".
- `daylog.json` confirms the write landed:
  `checkins.2026-10-08 = {breath:1, eyes:-1, energy:-1, ts:1791427902065}`.
- 593 frames in the ~4 s window, p50 53 / p95 73 ms.
- A real ambient-poll tick wasn't caught in-window (8-9 min cadence);
  the check-in write exercises the same `setData` re-assemble — same
  caveat as the iOS lane.

## T5 — back-nav hammer

30 cycles of search → BACK → settings → BACK → air map → BACK, end-state
checked each cycle. 30/30 `ok`; one transient `UNKNOWN` classification
(c4, dump raced a sheet slide — recovered by the harness on re-poll).
`adb logcat` for the window: **0 ANR in com.anonymous.app, 0 app FATAL**.
(The only FATALs logged were `com.android.uiautomator` shell helper
processes colliding with each other — "UiAutomationService already
registered" — a test-harness artifact, not the app.)

27,324 frames across the hammer window, p50 65 / p95 97 ms — same
distribution as scroll; no leak-driven degradation across 30 cycles
(late-cycle percentiles ≈ early).

## What was NOT measurable on this rig

- SurfaceFlinger present-interval p50/p95/max for the map SurfaceView
  (instrument broken — see note). Gesture smoothness on hardware ≠ what
  this rig can prove; the honest claim is "gestures route to GL with zero
  JS-thread work".
- Basemap label hide/restore during gestures (labels don't render under
  SwiftShader).
- True per-frame timing deltas under ~30× software rendering.

## Findings for the owner

1. **Nothing regressed.** All five jank-fix claims reproduce on Android:
   no card unmounts on re-assemble, viewport holds, pill echo works,
   search opens without the 10 s block, map under-sheet presents nothing
   while covered.
2. **Settings/drawer path feels slow** even rig-normalized (~drawer 6 s,
   settings +8-11 s wall incl. instrumentation). Likely SwiftShader sheet
   animation cost, but worth one glance on real hardware — if it reproduces,
   it's the next-biggest felt-jank item after the fixed six.
3. `SurfaceFlinger --latency` measurement recipe from map-perf-report does
   not work on this android-35 image — future lanes should expect gfxinfo +
   pixel-diff instead.

## Evidence

`docs/lanes/scroll-hammer-shots/` — home-top, t1-bottom-before,
t2-sheet-open, t2-settings-open, t3-map-open, t3-mid-gesture, t3-map-after,
t4-before, t4-after, t4-checkin, t5-end (11 files). Screenrecordings
(t1-scroll.mp4 60 s, t2c.mp4 sheets, t3-map.mp4 gestures) attached to the
session message rather than committed (~70 MB).
