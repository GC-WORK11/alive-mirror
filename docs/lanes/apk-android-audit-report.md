# Lane report: apk-android-audit — Android-side anti-list + render audit

**Date:** 2026-10-06 · **Verdict: DRIVEN 18/18 surfaces — 7 violations (1 major, 4 minor, 2 nit) — search-open probe 20/20 CLEAN** · Drive: Linux/KVM Pixel_7 emulator child ([session](https://app.devin.ai/sessions/4e9dc61e94d145888e8a94a9af10bb0e)) · Binary `alive108-0b11123.apk` (base/v2 HEAD @ drive time, 137 MB, debug-signed, PRE-d791879 autofocus fix)

## Why

The app-overhaul-v2 redesign happens on iOS sim. Android renders
differently — `elevation` draws the native shadow path, expo-font fallback
is silent (a missed load shows Roboto, not the serif/mono voices),
420 dpi density shifts text metrics, and there is no blur library anywhere.
This pass is the violation list the rebuild verifies against, plus the
Android data point on the iOS SearchScreen SIGSEGV.

## APK facts (verified on the binary itself)

- Package `com.anonymous.app`; `usesCleartextTraffic=true`; ABIs arm64-v8a/armeabi-v7a/x86/x86_64 → native on the x86_64 KVM image, no ARM translation.
- **59 bundled .ttf assets** in `res/`; all four family names present in `assets/index.android.bundle` (Fraunces, IBM Plex Mono, Inter, Noto Sans Devanagari) — fonts ship + register correctly; any Roboto fallback would be a render-time failure, not packaging.
- Resources obfuscated (res/<2-char>.<ext>); no density-qualified drawable dirs visible — raster assets ship effectively single-density (icons still read crisp at 420 dpi — visually confirmed).

## The audit — violation table (Android-render)

| # | Surface | Severity | Anti-list / register item | What Android renders | Evidence |
|---|---------|----------|---------------------------|----------------------|----------|
| 1 | VehiclePicker | **major** | functional hit-target — "never forced" intent | **"skip — estimate for vehicles like yours" is a dead row in the armed path.** ~6 tap variants (center, offsets, swipe-tap, close-and-return) — zero response while option cards beside it respond. Root cause located in source: the sheet mounts `visible={vehicleOpen \|\| wizArmed}` (App.tsx:884) but skip/✕/back all call `onClose` → `setVehicleOpen(false)` only (App.tsx:701). When a plan without a saved vehicle arms the wizard (`needsVehicle` → `wizArmed`, App.tsx:262-267), `onClose` clears the wrong flag — sheet stays mounted; only completing the picker escapes. Platform-agnostic logic defect first caught on Android; contradicts the file's own "never forced" comment (VehicleSheet.tsx:392). | [21-after-skip](https://app.devin.ai/attachments/ae029e31-9370-4488-a249-b19b52fe9ff6/21-after-skip.png), [22](https://app.devin.ai/attachments/81777c91-f0dd-4bd7-9e78-9f102016c98c/22-after-skip2.png), [23](https://app.devin.ai/attachments/2fcf4e00-bdcf-457a-9f7f-442f9f3680ff/23-after-vehicle.png) |
| 2 | compare sheet | minor | density @420 dpi | **`arrive 08:…` tail-ellipsizes** — arrival minutes dropped entirely on cards whose right-side dose text is long (Bus 181A, Bicycle). `numberOfLines=1` + ellipsize-tail collision; same cards fit at iOS metrics. | [29-compare6](https://app.devin.ai/attachments/3d698d6a-a2d5-447a-97d8-1a603526a073/29-compare6.png), [31](https://app.devin.ai/attachments/dd08cb68-c512-456e-a66d-fb15f6cd7738/31-compare8.png) |
| 3 | Trips ledger | minor | density @420 dpi | Trip row meta truncates the time to **`8:1…`** on long mode names ("Car (windows down) · 8:1…") — same ellipsis class as #2. | [41-ledger-full](https://app.devin.ai/attachments/8b447309-0d84-4ac6-9c48-ba891c853738/41-ledger-full.png) |
| 4 | Trips ledger | minor | content hierarchy | OD title **`central Delhi → Conna…`** / `→ India …` tail-ellipsizes — destination identity lost on long place names (Delhi names are long). | [56-ledger2](https://app.devin.ai/attachments/716daf37-40b2-45e9-980a-1e85b04d5790/56-ledger2.png) |
| 5 | hi compare card | minor | density / Devanagari metrics | Recommended-card benefit line wraps 2 lines then truncates **`—…`** mid-sentence ("…सबसे हल्का उत्सर्जन —…"). Devanagari otherwise fits — no cut matras. | [48-hi-plan](https://app.devin.ai/attachments/c31aac87-f0f4-4386-ac48-09569a15f4e1/48-hi-plan.png) |
| 6 | compare sheet | nit | layering | Sheet close **X overlaps the top card's `≈5` dose numeral** at first scroll position (`≈ 5×` collision); clears after scroll. | [25-compare2](https://app.devin.ai/attachments/593de5ad-bca5-43d3-ac20-8758bfd1cfcd/25-compare2.png) |
| 7 | LayersSheet | nit | glass legibility | Sheet alpha sits low enough that the **day-card text behind bleeds through between layer rows** — designed tint, but text-over-text legibility degrades (glass-on-glass stack). | [60-layers](https://app.devin.ai/attachments/7ba7f06b-df14-41eb-a7bf-afa025fd3d5f/60-layers.png) |

## Anti-list audit — PASS items (verified on screenshots + binary)

- **Fonts really loading — PASS.** Fraunces' high-contrast serif + old-style figures render on every display surface (wordmark, "One choice — and it's yours.", "Trips" title, THE MOVE headline, ledger `≈1.1 µg`, receipt `≈0.7`, day-strip numerals, nav `≈0.5 µg`). IBM Plex Mono letterspaced on every eyebrow (YOU'VE BREATHED TODAY, TUESDAY · 08:15 · DELHI, THE DAYS AHEAD, LAYERS). Inter body throughout. **Zero Roboto fallback observed on any surface.** [05-hero](https://app.devin.ai/attachments/7bc3c375-c8d4-443b-8eae-b96951e6e994/05-hero.png), [45-hi-hero](https://app.devin.ai/attachments/715cf5f5-14b2-4d10-aa46-d08072d7f76f/45-hi-hero.png)
- **hi Devanagari — PASS, zero tofu** across drawer/hero/search/results/plan ([44-48](https://app.devin.ai/attachments/e7ae6367-5b65-40f2-baee-cef6fc8d88e6/44-hi-drawer.png)). Noto Sans Devanagari carries every hi slot; the hi display *headline* correctly falls back to Noto (Fraunces has no Devanagari) — loses the serif voice; flagged for the redesign to confirm intent.
- **Elevation ladder — PASS.** Sheets cast upward warm shadows over dimmed content (ledger/settings over drawer, layers over day-card); cards sit soft. No harsh flat default shadows — the V2Elev ladder reads as intended on the native shadow path.
- **Band-tone fidelity — PASS.** Muted CPCB ramp (sage → warm beige → mauve → wine) on day chips, dose rulers, polylines; deep-olive CTA. Reads muted-expensive — **zero neon/lime/washout** at 420 dpi on this display.
- **Glass panes — PASS** except stack case (#7): search bar, ETA chip, nav HUD tiles, drawer over live map all ghost the map through as designed warm-white tint — not flat-milky. [33-nav-start](https://app.devin.ai/attachments/08bd9e23-6855-4c8b-a8f3-19c4f9949bf6/33-nav-start.png)
- **SVG icons — PASS.** Back chevrons, menu glyph, search magnifier, nav-arrow pin, recenter, layers diamond, share arrows, dest pin, car/auto/bus/bicycle mode glyphs, flame/crash markers — all render; no blank squares or wrong-color glyphs.
- **No default-Android cheap — PASS.** Custom switches (sage on/grey off, not stock teal), custom muted-olive spinner, chunky pills, hairline separators, no stock ripple flashes, no unstyled inputs, status bar aligned.
- **Animation restraint — PASS.** Only sheet slides + camera transitions; nothing gratuitous.

## The crash data point — SearchScreen on Android

Two iOS lanes (video-v6, day-in-life) hit deterministic SIGSEGV opening
SearchScreen — since root-caused to the autofocus `focus()`/
becomeFirstResponder handoff inside the mount-commit window during a live
compare/camera transition → Hermes GC stomp (`d791879`, docs/lanes/
search-crash-report.md). This binary **predates that fix**, so it carries
the vulnerable code path on Android.

**Probe:** the exact iOS deterministic loop — open "Where to?" → type
`india` → tap first result → re-open "Where to?" **~700 ms into the
compare/camera transition** — 15 iterations, + 5 plain open/close baseline.

| attempts | crashed | evidence |
|---|---|---|
| 15 reopen-during-transition | **0** | every reopen rendered the sheet |
| 5 plain open/close | **0** | — |
| **20 total** | **0** | **0 tombstones (`/data/tombstones/` empty), 0 SIGSEGV / FATAL EXCEPTION / Abort / backtrace across 48,923 logcat lines; crash buffer empty** |

**Reading:** the identical pre-fix code ran the crash-deterministic
gesture 15/15 clean on Android. This is real evidence the race is
iOS-side — UIKit responder handoff + Hermes/iOS — not an app-logic defect
(the JS logic is identical; only the IME/window layer differs). Android's
WindowManager/IME path tolerates the autofocus-during-transition window.
The `d791879` fix remains correct stack-wide (the gate is free insurance
on Android), and the rebuilt binary should re-run this probe as a
regression guard.

## Reachability + by-design notes

- **LayersSheet exists** — only via the stacked-diamond FAB (bottom-left) on THE AIR MAP surface (hero footer), NOT in the drawer. Toggles verified: fires + crash spots flip, FAB active-green, markers draw. [59-airmap](https://app.devin.ai/attachments/1d4ee22f-de30-4cfe-9481-5072c07656f8/59-airmap.png), [61-layers-on](https://app.devin.ai/attachments/048b52af-5823-44f4-a603-de37d9ce62ea/61-layers-on.png)
- "How ALive works" / "What we store" are inline drawer/settings expanders, not panes — both verified. [57-howalive](https://app.devin.ai/attachments/99d2e408-38f8-463a-9e05-77d6e48a0ef3/57-howalive.png), [64-whatwestore](https://app.devin.ai/attachments/1ffa9e17-8c83-4209-989e-54120a68bb40/64-whatwestore.png)
- Map renders **vendor 3D building extrusions** in nav view (MapLibre tile style — not app decoration). The owner's "NO 3D" anti-list targets UI art; flagged in case the map style should flatten too.
- Receipt Share pill not exercised (opens OS share sheet; skipped to stay inside wire rules — the button is local, flag as unverified).
- DelhiToday first mount showed a transient "can't reach the server — trying again", self-recovered; server healthy via curl — likely a short fetch timeout on cold sheet open. Non-blocking.
- Status-bar square glyph is a system DEVELOPER notification (pkg=android), not the app — app posts no notifications.
- `hi` copy "0घ 31मि गिने" (counted 0h 31m) is grammatically stilted ordering — copy review, not a render bug.

## Rebuild android-checklist (must hold on this emulator)

Verify on Pixel_7-class density (1080×2400 @ ~420 dpi), KVM swiftshader:

1. VehiclePicker "skip — estimate for vehicles like yours" **tappable on first press in the armed path** — the `wizArmed`/`vehicleOpen` mount-flag split must not eat `onClose`. *(the one major)*
2. No tail-ellipsis on times at 420 dpi: `arrive HH:MM` on compare cards, `· H:MM am` on ledger rows.
3. Ledger OD titles preserve destination identity — middle ellipsis or two-line, never tail-clip to `Conna…`.
4. hi locale: benefit lines wrap fully or ellipsize cleanly (no `—…` artifacts); Devanagari matras/descenders uncut; confirm intended hi headline fallback to Noto vs a serif-capable Devanagari face.
5. Compare-sheet X clears card content at every scroll offset.
6. Stacked glass-on-glass (LayersSheet over day-card): effective alpha ≥ ~.85 under text rows, or bump backdrop.
7. Keep: all 4 font families visually loading (zero Roboto fallback), muted CPCB tones, upward sheet shadows, custom switches/spinner/pills, zero-tofu Devanagari.
8. **SearchScreen crash probe stays 20/20 clean on the rebuilt binary** — Android is clean pre-fix; this is the regression guard.
9. Decide: vendor 3D building extrusions in the map style — keep or flatten per register.
10. hi copy "0घ 31मि गिने" — copy review.

## Rules kept

Live API `http://65.2.28.40`: GETs + `POST /v2/plan` only. Consent/share OFF
the whole run — verified on-device (`consent.json {seen:true, sharing:"off"}`,
`settings.json share:false`, `daylog.json` local). Geo fixes fed ~1.1 s
cadence ON the route polylines — **zero `/v2/reroute`, zero `/v2/trip`,
zero non-GET posts**. No code changes anywhere. Never deployed.

Driver's full findings file + 64 screenshots live on the drive session;
this report embeds the probative ones. [android-findings.md](https://app.devin.ai/attachments/e9b6098d-0686-46e0-bf94-0abbda12b5f6/android-findings.md)
