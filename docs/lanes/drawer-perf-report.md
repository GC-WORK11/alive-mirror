# drawer-perf — what actually costs under the ~6 s drawer / ~8–11 s settings on KVM

scroll-hammer flagged drawer open ~5.7–6.8 s and settings open ~7.8–11.7 s
wall on the KVM rig and asked whether anything real sits under the
SwiftShader/uiautomator tax. Answer: **most of it is rig-only machinery —
but there were three real costs, all now fixed** (`61fc84e`).

Rig (KVM measurements): Devin Linux child box (8c/31G, /dev/kvm), AVD
`demo` = pixel_7, android-35 google_apis x86_64, `swiftshader_indirect`,
`-no-window -no-snapshot`. Release APKs, `EXPO_PUBLIC_API_URL=http://65.2.28.40`
baked. iOS-sim functional run: Devin macOS box, iPhone 17 sim (iOS 26.5),
dev client at the same commits, `PERF_ON=true` local flip.

## Emulator tax vs real code — the decomposition

| Cost | Where | On KVM | On hardware |
|---|---|---|---|
| `holdMapDrawThen` defers every overlay commit one task + arms a 1.4 s/2.6 s draw-hold; in the first 100 s it also polls for map draw-idle (≤1.4 s) | `src/map/drawHold.ts` | Every drawer/settings open pays it | **dead code** — `Device.isDevice` → synchronous `cb()` |
| hold edges re-render `MapTree` (~40 map children, heaviest render in the app) via `useMapDrawHeld` | App.tsx | 2× per open (arm + release) | only when a hold actually arms |
| map `preferredFramesPerSecond` → 2 during every hold | MapTree | ~500 ms/present floor ⇒ hold window ≈ frozen map | n/a |
| uiautomator dump ~1.5–2 s/poll inside the measurement loop | rig | inflates every wall number (upper bounds) | n/a |
| SwiftShader ~65–500 ms/present | rig | ~30× a real phone | n/a |
| **SettingsScreen mounts ~450 elements in ONE commit per open** | `SettingsScreen.tsx` | big JS commit inside the hold window | **real** — stalls tap→first-frame |
| **Sidebar re-renders ~300 rows per `open` flip** (content is `open`-independent; flip only existed to re-fire the stagger) | `Sidebar.tsx` | inside the hold window | **real** — reconcile per open/close |
| **`setLayersOpen(false)` when already false armed a fresh hold + deferred commit per drawer open** | App.tsx `openSidebar` × `useHeldState` | extra hold edge per open | on hardware: a wasted state write (cheap but pointless) |
| 7× `useReduceMotion` AccessibilityInfo subscriptions (one per `Rise`) | `Sidebar.tsx` | 7 native calls per mount | real but boot-time only (drawer is always-mounted) |

Cleared suspects from the brief: `loadSettings` is mem-mirrored after the
first read (`shell/settings.ts`), `useDayData` doesn't re-run on a drawer
flip, `notifPerm()` is async off the mount path, t0 warm + `tileWarm` are
bounded input-gated slices, and all `perf.ts` probes are compiled no-ops.

## Fixes (all general-purpose — the codebase's own conventions)

1. **SettingsScreen two-frame mount** — `bodyReady` gates the
   ~450-element `SettingsSheet` one `requestAnimationFrame` after the
   backdrop+spring commit, re-armed per open via the sanctioned
   render-phase reset (`visible !== wasVisible`). This is literally
   SearchScreen's `bodyReady` convention; SettingsScreen just never got it.
2. **Sidebar split** — scroll content (sections, expanders, lists, all
   builders/memos) moved into `React.memo`'d `SidebarBody`; `Rise` reads
   `open`/`reduce` from a new `RiseCtx` context so the stagger re-fires
   without the body's ~300-row reconcile. `useReduceMotion` hoisted to the
   inner (one subscription instead of seven).
3. **`useHeldState` same-value skip** — the setter now resolves updater
   forms against a pending ref and no-ops when the value doesn't change:
   a no-op set mounts nothing, so it must not arm a map draw-hold.

## Evidence

**iOS sim (functional + render counts, `PERF_ON=true`, dev client):**
- `shell.SidebarBody` renders **0 times across every open/close flip**
  (previously `shell.Sidebar` did 8 full ~300-row reconciles in 4 flips).
  It re-renders only on real data changes (vehicle expand, settings patch).
- Staggered rise still re-fires on every reopen — verified on raw capture
  frames (mid-stagger frame shows top sections risen while the language
  card is ~50 % opaque).
- `settings.tap → settings.body` mark delta: **1.68 s / 1.87 s** on the sim —
  decomposes as ~1.2 s armed draw-hold (sim-only) + deferred commit +
  rAF + mount. The fix is visible in the wall number on a hold-free path.
- All 8 functional checks pass; vehicle grid expand + persist verified via
  `Documents/settings.json`; no crashes, Metro clean.

**KVM Android release — before/after wall times** (uiautomator-bounded;
raw numbers are upper bounds incl. ~1.5–2 s dump overhead, deltas are the
signal). BEFORE APK @ `8c1c723` sha256
`7688da989b4549efdb4c631e34921ab9f2065c63763f428b9ca77e57413040d3`
(169,297,436 B); cold-launch WaitTime ~470 ms.

| Metric | BEFORE `8c1c723` | AFTER `61fc84e` | Δ |
|---|---|---|---|
| drawer open, cold ×4 | med 6529 ms (3666–7220) | med 6226 ms (6109–6705) | ≈ flat (noise) |
| drawer open, steady ×10 | med 6224 ms (5296–6942) | med 5977 ms (5130–6676) | ≈ flat (noise) |
| settings open, cold ×4 | med 5896 ms (5189–6493) | med 5572 ms (5485–6867) | ≈ flat (noise) |
| settings open, steady ×10 | med 6330 ms (5479–7738) | med 6436 ms (5510–7670) | ≈ flat (noise) |
| **gfxinfo frames, drawer burst** | 220 f, 84.1 % janky, p50 73 / p95 93 | **122 f**, 75.4 % janky, p50 69 / p95 93 | **−45 % frames** |
| **gfxinfo frames, settings burst** | 231 f, 94.4 % janky, p50 93 / p95 125 | **103 f**, 92.2 % janky, p50 81 / p95 97 | **−55 % frames** |
| `drawer.open` jank (1.2 s probes) | avgGap ~34–41 ms, dropped 24–34, maxGap ≤ 196 | avgGap ~32–43, maxGap ≤ 139 | tail cut |
| `enter.settings` jank | avgGap ~42–55, dropped 22–30, maxGap ≤ 196 | avgGap ~40–52, maxGap ≤ 177 | tail cut |
| renders per open | `shell.Sidebar` +2–5/full reconcile | `shell.SidebarBody` **0 per flip** (shell still ticks 2–5) | ~300-row reconcile gone |
| `settings.tap`→`settings.body` | mark absent | **58–111 ms (med ~70)** | two-frame mount lands right after the spring commit |
| `enter.home` boot probe | avgGap 89.5–140, maxGap ≤ 313 | avgGap 64.3, maxGap 190 | boot smoother (1 reduce-motion sub + fewer holds) |
| cold WaitTime | ~393–544 ms | **298 ms** | faster first frame |

AFTER APK sha256 `0bc96e26b75d8611c305b3b21e8b2eec3e55d758d600b76711133831123b248d`
(169,299,980 B), same PERF_ON recipe, fresh-data install. Rise-in stagger
preserved on video; zero ANRs/crashes both builds.
Child session devin-514a99641340476e9369a5fa3e5d3b7a ran both drives;
videos `cold_cycle`/`steady_cycle` (before) and `after_cold`/`after_steady`
(after) attached there.

**Read the table honestly:** the wall-clock instrument cannot resolve the
fix — ~1.5–2 s of uiautomator dump per poll + the (sim-only) draw-hold
machinery + SwiftShader present floor dominate every row, so medians sit
inside each other's spread. The instruments that CAN see it all agree:
~45–55 % fewer presented frames per open burst, the body reconciles zero
times per flip on both rigs, and the new marks put settings tap→body at
~70 ms on the KVM build. On hardware the hold code is dead by
`Device.isDevice`, so the remaining real cost was always the
commit/reconcile work — that is exactly what these numbers show removed.

## What still costs on real hardware (honest tail)

- The drawer's ~300-element tree still mounts once at boot (always-mounted
  off-canvas by design — the scrim/scene needs it). Mounting it lazily on
  first open would trade boot time for open time and complicate the
  stagger; not worth it.
- `settings.tap → body` keeps the two-frame gap by design — the sheet
  must not commit ~450 views in the tap's own frame.
- Rise staggers are view-only (opacity/translateY) but still 7 native
  timing animations per open — cheap, and skipped entirely under
  reduce-motion.

## Repro

- iOS: dev client at `61fc84e`, `PERF_ON=true` flip, `perf_log.jsonl`
  in `Documents/` — filter `ticks>20` for the jank reads (idle-window
  rAF starvation shows as fake maxGaps).
- KVM: `docs/lanes/scroll-hammer-report.md` build recipe; pin `8c1c723`
  for BEFORE, the fix commit for AFTER; `PERF_ON` sed before bundling.
