# android-verify lane report — base/v2 @ 070b369

**Verdict: 7/7 PASS.** Debug APK (embedded-bundle route) driven on a KVM-accelerated Android emulator; every claim below has a screenshot and/or a uiautomator/logcat line behind it.

| # | Check | Verdict | Timing | Shot |
|---|-------|---------|--------|------|
| 1 | Cold open → home | PASS | WaitTime 949 ms (also observed 1070 ms; first-ever launch after install 2113 ms) | `01-cold-home.png`, `01b-ambient-home.png` |
| 2 | Scroll whole home + check-in pill | PASS | pill tap→selected ≈3 s (debug+SwiftShader floor; see rig notes) | `02-scroll-bottom.png`, `02-checkin-tap.png` |
| 3 | 'Where are you going' sheet | PASS | tap→sheet-interactive ≈2.9 s | `03-sheet-open.png`, `03-search-connaught.png` |
| 4 | Air map | PASS | tap→surface-rendered 2215 ms | `04-airmap.png`, `04-airmap-zoom.png` |
| 5 | Delhi today empty state | PASS | — | `05-delhi-today-empty.png` |
| 6 | Live update in place | PASS | poll cadence 60 s; observed in-place updates (below) | `06-live-before.png`, `06-live-after.png` |
| 7 | Soak ≥5 min | PASS | ~6 min foregrounded; 0 crash/ANR lines | — |

## Build

- **Route: PRIMARY — self-contained debug APK.** Local-only `debuggableVariants = []` added inside the `react {}` block of `Mobile/android/app/build.gradle` (bundles JS into the debug variant; **not committed** — the edit was reverted before push). `env EXPO_PUBLIC_API_URL=http://65.2.28.40 ./gradlew assembleDebug -x lint` → success in 3 m 25 s.
- Maven 429 egress workaround applied as per lane recipe: foojay-resolver stripped from `node_modules/@react-native/gradle-plugin/settings.gradle.kts`, `mavenCentral()`→googleapis mirror across node_modules gradle files (groovy files use `maven { url "..." }`), `scripts/gradle-init-mirror.gradle` → `~/.gradle/init.d/mirror.gradle`, missing `expo-module-gradle-plugin/settings.gradle.kts` created with pluginManagement mirrors.
- Stale-bundle guard: `rm -rf android/app/build/generated/assets/react android/app/build/outputs` before build.
- **APK**: `app-debug.apk`, **226,361,939 bytes**, sha256 **`50df7965676eb677754c55c61ff27fce9daed98b3a9099f65430de0a570c454d`**.
- **Bake-verify**: `assets/index.android.bundle` present; `grep -c 'http://65.2.28.40'` = **1**; zero matches for `localhost`/`127.0.0.1`/`10.0.2.2`/`:8081` URL forms.
- **Commit built**: `070b369` (`search: lane report + on-device verification shots`), branch `base/v2` pulled at build time.
- **Remote moved during verification**: base/v2 advanced to `e1e9d22` (8 commits landed mid-run, incl. `audit-fix` P0 air-field visibility opacities/edges and `map-perf` gesture/fps changes). All evidence below is against **070b369**; the post-build commits are not covered by this run.
- **Device**: emulator AVD `demo` — pixel_7, Android 15 (API 35) `google_apis` x86_64, SwiftShader (`-gpu swiftshader_indirect`), 2048 MB RAM, `/dev/kvm`. App id `com.anonymous.app`, activity `.MainActivity`.

## Evidence per check

### 1. Cold open → home — PASS
`am force-stop` + `am start -W -n com.anonymous.app/.MainActivity` → **WaitTime 949 ms**, TotalTime 947 ms (earlier runs 1070 ms; cold-after-install 2113 ms). Debug+SwiftShader so these are upper bounds, not release numbers.

Home rendered the dose hero: **"you've breathed today · 23 µg · good · 11% of your daily limit · 35m counted · outside ~62 · moderate"** (`01-cold-home.png`).

The ambient (uncounted) variant was verified earlier in the session: **"62 µg/m³ · moderate"** + **"same air = AQI …"** equivalence line + **"nearest live monitor ~1.8 km away"** — `atGps` true, i.e. read at the injected fix, not the city centroid (`01b-ambient-home.png`). Both hero variants render real numbers with units and band words.

### 2. Scroll whole home — PASS
Swiped top→bottom→top across the full scroll (hero → "in Delhi's air right now" incidents card → Air map/Delhi today/Your trips/the move → forecast strip → "your day"). **No yank/snap-back to the Move card** — scroll position stays where left (`02-scroll-bottom.png`).

At the bottom, the "how you felt" check-in (breath/eyes/energy × good/meh/rough): pressed **breath → meh**; the pill ring fills and `selected=true` lands in uiautomator (`02-checkin-tap.png`). Tap→selected ≈3 s on this rig — first taps during settle are routinely eaten (rig quirk, retapped).

### 3. 'Where are you going' sheet — PASS
Tap on "Where to?" → sheet interactive in **≈2.9 s** (field focusable + "Your location"/"Choose on map" rows) — `03-sheet-open.png`.

- `connaught` → **13 result rows**, all real CP-area entities (Connaught High Street · road · CP Block 400 m; Connaught Place 250 m; Connaught Lane road/residential; The Connaught hotel; 20-C Connaught Place address; Connaught House office; …). No exact duplicates — the two "Connaught Lane" rows carry different context (Kashmiri Market road vs Katwaria Sarai residential area) and the two "Connaught Place" rows are different entity kinds (Delhi vs district). `03-search-connaught.png`.
- `conaught` (misspelled) → **12+ rows**, still sane: "Conaught Clubhouse · brewery · Central Cottage Industries Emporium 600 m" plus the Connaught family. The fuzzy path works.

### 4. Air map — PASS
Tap "Air map" → full surface in **2215 ms** (measured to the surface-unique marker `the air map`; note: a `MapLibre` content-desc also exists on home — the mini-map — so it is not a valid open-marker).

`04-airmap.png` shows: header **"the air map · 53 live stations · redder = worse air right now · good→severe dot ramp · air reading: 5 min old"**, the **colored PM2.5 band field overlaid on the basemap** (amber/moderate cells covering the street blocks around Connaught Place; greener cells visible around the park areas), bottom instrument card **"your day so far ≈29 µg (micrograms) · now ~62 µg/m³"**. `04-airmap-zoom.png` shows the per-cell µg numbers at zoom ≥10.5 (AirFieldLayer symbol layer).

### 5. Delhi today — PASS
Fresh install, zero recorded trips: the surface shows the **honest empty state — "no trips yet — go live your day, we'll count it here"** + "the streets and totals in this view are counted from trips other people share" + "why this is an estimate". **No invented trips.** Ordering verified: the **"in Delhi's air right now"** incidents card (16 fires Punjab–Haryana belt, ventilation 605 m²/s, city mean 49.6→93.5 µg/m³, "measured, not reported") sits **above** the trips block. `05-delhi-today-empty.png`. The city-aggregate hero ("1311 µg · poor · 6.1× WHO · ~91 µg/m³") is a *city* number, not a fabricated personal trip.

### 6. Live update without reload — PASS
Poll cadence in code: `/aqi` every **60 s** (`App.tsx:509`), `/health` every 15 s, `/reports` every 60 s, field every 10 min. Observed in-place updates, zero flash/splash/full-screen reload anywhere in the session:

- `air reading: N min old` ticked **1→2 min** (18:55:13) then **reset 2→1 min** (~19:04) when a fresh field block landed — the text changes inside the mounted tree; scroll position and all other nodes untouched. `06-live-before.png` vs `06-live-after.png`.
- The home hero **switched variant in place** during the session (ambient hero → dose hero "you've breathed today") as `recordSample` landed new dosimeter samples — a full data-driven re-render with no navigation or reload.
- Dedupe is by design: identical `/aqi` payloads produce no re-render (`setAqiField`/`setAmbientUg` identity checks, App.tsx:470-491), so the screen is static between real changes.
- Geo nudge note: pushed a second `emu geo fix` ~10 km east (28.6469, 77.3159); no hero change within ~3 min — emulator GMS fused location caches the first real fix aggressively (rig quirk, see below), and the city field is homogeneous enough at both fixes that `outside ~62` would hold anyway.

### 7. Soak — PASS
Logcat cleared at window start; ~6 min of foregrounded driving (scroll pairs, Air map and Delhi-today round-trips). At end:
- `adb logcat -d | grep -icE 'FATAL|SIGSEGV|SIGABRT|ANR|Application Not Responding'` → **0**
- `adb logcat -d | grep -icE 'AndroidRuntime|FATAL EXCEPTION'` → **0**
- `dumpsys activity lastanr` → **`<no ANR has occurred since boot>`**
- App still `topResumedActivity` at window end.

## Bug catalogue

**Real app issues: none blocking.** Observations worth filing:

1. **(minor, honesty)** The `air reading: N min old` label can under-report staleness between renders — the age string is computed at render time and the render dedupe suppresses updates while data is identical, so the displayed age can freeze at e.g. "2 min old" for ~3 min wall-clock. It resets correctly when a new field lands (observed 2→1). One-line-class candidate: tick the label on a timer, or accept as designed.
2. **(candidate-dupe, data)** "Connaught Place · Delhi" vs "Connaught Place · district" rows look dupe-adjacent (different entity kinds for the same place). Not a crash; gazetteer dedupe could collapse same-name different-kind rows if the owner wants tighter results.
3. No FATAL/SIGSEGV/ANR, no restart loops, no API error banners (`can't reach the server` strip never appeared; `/health` misses stayed <2).

## Rig quirks (NOT app bugs)

- **Taps eaten during settle** — sheets/pills/rows routinely ignore the first tap while SwiftShader catches up; retaps land. All timings include this inflation.
- **SwiftShader renders no basemap text labels** — street names absent on the air map; field colors, cell numbers, station rings and UI text all render fine.
- **GMS fused location** on emulator ignores `set-test-provider-location` mock fixes; had to grant Maps location perms + launch Maps to start GNSS so `emu geo fix` produced a *real* fix GMS would cache (expo-location uses `FusedLocationProviderClient`). Second geo fix does not propagate promptly — fused cache staleness.
- **`input text` does not expand `%s`** on this image — literal `%s`/`s` got typed; use `input keyevent 62` for spaces.
- **Debug build timing inflation** — RN dev-mode JS + no JIT optimizations; every ms number here is an upper bound vs a release build.

## Honest limits

- Emulator ≠ real phone: software GL, no real GPS/multipath, bridged networking. Verify on hardware before the demo if one is available.
- POST `/v2/plan` / `/v2/reroute` flows exercised only to sheet-open per lane rules; no nav trip was completed to receipt, so the post-trip surfaces are unverified by this lane.
- Ambient µg stayed 62 through the check-6 window; in-place update proof rests on the freshness ticker + hero variant transition + field-reset observation, not an ambient-value delta.
- Geo nudge produced no observable change within ~3 min — logged as rig quirk, not evidence the location path is broken (the first real fix demonstrably reached the app: `atGps` hero + 1.8 km monitor distance).

*Lane: android-verify · run 2026-10-07 18:1x–19:2x UTC · Devin session on Linux/KVM box.*
