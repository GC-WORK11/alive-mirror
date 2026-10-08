# apk-v7 — FINAL release APKs on air-gate HEAD `90bc055`

Lane: apk-v7 · date: 2026-10-08 · build host: this macOS arm64 box · smoke rig: Linux KVM child (`devin-2ff1f6da…`)

Build: `base/v2` HEAD = **90bc055** — air-gate (plain basemap by default; PM2.5 field paints ONLY on air intent; route polylines flat: picked=forest, alternates=grey; air numbers/deltas intact). Rides stays+playtime `c5ba61c0`, routes-delta, e2e-residual `ec2ed08`, and the full v5-verified base (`270be81`: scorer + polish).

## Artifacts

| what | value |
|---|---|
| APK (release candidate, real devices) | `alive-90bc055-arm64.apk` · **108,318,735 B (~108.3 MB)** — arm64-v8a only — https://app.devin.ai/attachments/9af3be9a-b067-48e1-adc5-7aaa1670b7e9/alive-90bc055-arm64.apk |
| APK (universal, incl. x86 emulators) | `alive-90bc055-universal.apk` · **188,869,392 B (~188.9 MB)** — 4 ABIs — https://app.devin.ai/attachments/b3773c76-a29a-41a0-b222-26b987429306/alive-90bc055-universal.apk |
| arm64 sha256 | `c6282daf2d8e7c5e330d7ff762a5cbe08398dd37045ff7af3f6bbc8b77c76fe3` |
| universal sha256 | `776540987ca732d52dbd7677a2950d47961911157901177b6771c94749c2c849` |

## P1 release config applied (local-only, same convention as v5/v6 lanes)

`npx expo prebuild --clean -p android` regenerated the native tree from app.json+plugins — then these edits were applied on top of the generated `android/` (NOT committed — the checked-in tree stays untouched):

- `hermesFlags = ["-O", "-fstrip-function-names", "-g0"]` in the `react{}` block of `android/app/build.gradle` — the "minify.hermes + strip.debugLineNumbers" pair: optimized bytecode, function-name string table stripped, **zero debug info/line numbers in the .hbc** (default was `["-O","-output-source-map"]`).
- `ndk { abiFilters(*(findProperty('reactNativeArchitectures') ?: 'arm64-v8a').split(',')) }` in `defaultConfig` + `reactNativeArchitectures=arm64-v8a` in `gradle.properties` — the abiFilters arm64-only lever, property-driven so the universal pass (`-PreactNativeArchitectures=armeabi-v7a,arm64-v8a,x86,x86_64`) still emits all four ABIs.
- `android:usesCleartextTraffic="true"` **re-added** to the application tag — see trap below.

## Bake verification (bundle inside the shipped APKs)

- arm64 `unzip -p assets/index.android.bundle | grep -c 'http://65.2.28.40'` → **1** ✓ ; universal → **1** ✓ (prod API baked; `EXPO_PUBLIC_API_URL` was in the env of both builds).
- dev-URL grep `localhost:[port]` / `10.0.2.2` / `192.168.*` / `*.local` → **0 real hits**; bare `localhost<name>` POI-name concatenations in the gazetteer corpus — same documented benign false-friend class as v4/v5/v6.
- ABI arm64: **18** `lib/arm64-v8a/` entries, 0 `x86*`/`armeabi*` — true arm64-only. Universal: 4 ABI dirs ✓.
- Badging: `com.anonymous.app` v1.0.0 (code 1), minSdk 24, targetSdk/compileSdk 36, label `Alive`. `usesCleartextTraffic=0xffffffff` (true) verified in the built binary manifest.
- Signing: existing debug-keystore recipe (release block signs `signingConfigs.debug`) — same as every prior lane, no secrets touched.
- Size delta vs v6 arm64 (`alive-ec2ed08`, 108,705,019 B): **−386,284 B** — the `-g0`/`-fstrip-function-names` hermes flags shaving the 43 MB bundle.

## Build traps hit (write-up for the next lane)

1. **`prebuild --clean` destroys `usesCleartextTraffic` on Android.** The checked-in manifest had it hand-added; `plugins/withCleartext.js` is iOS-only (`withInfoPlist` NSAppTransportSecurity) — nothing regenerates the Android flag. Without it the release APK cannot reach `http://65.2.28.40` at all (cleartext blocked → every API call fails). Re-add to `android/app/src/main/AndroidManifest.xml` after every prebuild, or a `withCleartextAndroid` config plugin is the durable fix.
2. **The checked-in `android/` tree was stale vs app.json.** Regeneration changed splash wiring (MainActivity + styles for current expo-splash-screen), added manifest `uses-permission` lines (location perms resolve via manifest-merger anyway), notification meta-data, fresher icon webps. APK built from the regenerated tree; the committed tree left as-is (drift is pre-existing, not this lane's to rebase).
3. **Fresh box had NO Android SDK** — the v5-lane `~/Android/Sdk` provision did not carry to this snapshot. Reprovisioned: cmdline-tools-mac-13114758 + `platform-tools 37.0.1` + `platforms;android-36` + `build-tools;36.0.0` + `ndk;27.1.12297006` + `cmake;3.22.1` (~6 min) + `sdk.dir` in `local.properties` (gitignored).
4. `npm ci` needed first — `expo-build-properties` was missing from node_modules again.
5. Build times: arm64 `assembleRelease` **2m58s** cold (355 tasks), universal **+1m05s** incremental (bundle UP-TO-DATE — same .hbc, only the 3 extra ABI native compiles re-ran). Init script `-I ../../scripts/gradle-init-mirror.gradle` — zero maven 429s.

## Boot smoke — `demo` AVD pixel_7 · Android 15 google_apis x86_64 · `-accel on` KVM + SwiftShader — **ALL PASS**

(universal APK — the device-deliverable arm64 is its twin; x86_64 needed for the KVM image. sha256+size re-verified on the rig before install. Shots: `docs/lanes/apk-v7-shots/` — re-verified frame-by-frame on the coordinator box.)

| step | verdict | evidence |
|---|---|---|
| install → cold launch | **PASS** | `am start -W` COLD **TotalTime 1563ms** |
| onboarding → home | **PASS** | consent pages render ("Skip" top-right, "Skipping counts as sharing on — either way, one tap in Settings undoes it"); location granted while-using; home hero live **87 µg/m³ moderate** (86→87 on camera), provenance "nearest live monitor ~2 km away · air reading: 12 min old" at the injected Delhi fix — `s1-onboarding.png`, `s2-home.png` |
| 'air around me' → field paints | **PASS** | "air answers → the air map near you" intent row → kriged PM2.5 field across the viewport + "the air map · redder = worse air right now · **53 live stations** · air reading: 14 min old" + tap readout "85 µg/m³ — moderate · Jai Prakash Narayan National Park" — `s4-airmap.png`. **The 90bc055 air-gate verified end-to-end: field on air intent only.** |
| where-to → flat route | **PASS** | Connaught Place: 3.02 km · 4 min · ~1.8 µg. Picked polyline solid dark-forest, alternate grey dashed — ZERO rainbow/band tint on geometry (bands live only in the air-by-hour chart = correct flattening); basemap plain — `s7-route-flat.png` |
| cleartext prod reachability | **PASS** | `ss -tnp` on-device: ESTAB → `65.2.28.40:80` |
| logcat crash sweep | **PASS** | 0× FATAL EXCEPTION / SIGSEGV / tombstone / ANR across the whole session |

Rig: Linux KVM child `devin-2ff1f6daf83f464687f743bf97a784f5` (~15 s emulator boot on KVM; Delhi geo injected via `adb emu geo fix 77.21 28.61`).

## Verdict

Ship `alive-90bc055-arm64.apk` as the FINAL install binary; `alive-90bc055-universal.apk` is the emulator/fallback twin (byte-identical JS+config, 4 ABIs). All 90bc055 air-gate behaviors confirmed on real boot: plain maps by default, field on air intent, flat route geometry.
