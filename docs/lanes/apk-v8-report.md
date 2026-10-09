# apk-v8 — FINAL release APKs on splash HEAD `aa724bb`

Lane: apk-v8 · date: 2026-10-09 · build host: this macOS arm64 box · smoke rig: fresh Linux KVM child ([devin-c0abb64cbdf848aaa31e2bdd9cf3e6c1](https://app.devin.ai/sessions/c0abb64cbdf848aaa31e2bdd9cf3e6c1))

Build: `base/v2` HEAD = **aa724bb** — splash 'a → alive' launch wordmark (per-letter spring sweep, first-run only). Rides `c88bb0f` trip-flow (From/To rows + 'finding the purest route' + multi-route chooser + 'start journey' + nav easeTo z16.6/pitch55 + starved-spring tap fix), `98fd8ba` stays/playtime v2 sheets, `3f9245f` air-map haze restyle, `90bc055` air-gate, and the full v7-verified base. Prod is already on this SHA (deploy-28 `:235 = aa724bb4`).

## Artifacts

| what | value |
|---|---|
| APK (release candidate, real devices) | `alive-aa724bb-arm64.apk` · **108,333,163 B (~108.3 MB)** — arm64-v8a only — https://app.devin.ai/attachments/c4d4c755-b57d-481e-b846-381e6ac493e1/alive-aa724bb-arm64.apk |
| APK (universal, incl. x86 emulators) | `alive-aa724bb-universal.apk` · **188,883,820 B (~188.9 MB)** — 4 ABIs — https://app.devin.ai/attachments/c0d40028-b053-4d1a-b908-dc5a458e0570/alive-aa724bb-universal.apk |
| arm64 sha256 | `35d1ba9f0d67d14d09384229265fb6653b6a685a364229fdb28f2a3161da77e9` |
| universal sha256 | `d198bed905ab51c4181b1b0be65c1c86174d84892e629ab719689af7fab8c2e6` |

## Release config applied (local-only, same convention as v5/v6/v7 lanes)

`npx expo prebuild --clean -p android` regenerated the native tree from app.json+plugins — then these edits were applied on top of the generated `android/` (NOT committed — the checked-in tree stays untouched; worktree restored post-build):

- `hermesFlags = ["-O", "-fstrip-function-names", "-g0"]` in the `react{}` block of `android/app/build.gradle` — optimized bytecode, function-name string table stripped, zero debug info/line numbers in the .hbc.
- `ndk { abiFilters(*(findProperty('reactNativeArchitectures') ?: 'arm64-v8a').split(',')) }` in `defaultConfig` + `reactNativeArchitectures=arm64-v8a` in `gradle.properties` — property-driven so the universal pass (`-PreactNativeArchitectures=armeabi-v7a,arm64-v8a,x86,x86_64`) still emits all four ABIs.
- `android:usesCleartextTraffic="true"` **re-added** to the application tag — the `prebuild --clean` trap persists (checked-in manifest loses it; `plugins/withCleartext.js` is iOS-only). Without it the release cannot reach `http://65.2.28.40`.

## Bake verification (bundle inside the shipped APKs)

- arm64 `unzip -p assets/index.android.bundle | grep -c 'http://65.2.28.40'` → **1** ✓ ; universal → **1** ✓ (`EXPO_PUBLIC_API_URL=http://65.2.28.40` in the env of both builds).
- dev-URL grep `localhost:[port]` / `10.0.2.2` / `192.168.*` / `*.local` → **0 hits** — clean this corpus rev.
- Commit-marker greps (UTF-8 + UTF-16LE byte scan — hermes stores non-ASCII strings like the '…' ellipsis UTF-16, so plain grep misses them): `'finding the purest route for you'` (c88bb0f) =1, `'start journey'` =1, `'where to stay'`/`'each number is the next-24 h air at that address'`/`'tap a stay to pin it on the air map'`/`'stays, lightest air first'` (98fd8ba) =1 each, `'the air map'` =4. Both bundles byte-identical: **66,718,944 B** each.
- ABI arm64: **18** `lib/arm64-v8a/` entries, 0 `x86*`/`armeabi*` — true arm64-only. Universal: **72** lib entries across `arm64-v8a, armeabi-v7a, x86, x86_64` ✓.
- Badging: `com.anonymous.app` v1.0.0 (code 1), minSdk 24, targetSdk/compileSdk 36, label `Alive`. `usesCleartextTraffic=0xffffffff` (true) in the built binary manifest of both APKs.
- Signing: existing debug-keystore recipe (release block signs `signingConfigs.debug`) — same as every prior lane, no secrets touched.
- Size delta vs v7 arm64 (`alive-90bc055`, 108,318,735 B): **+14,428 B** — splash component + trip-flow/stays-v2 additions. Universal delta identical (same .hbc growth).
- Build times: arm64 `assembleRelease` **2m18s** (355 tasks), universal **+1m08s** incremental (bundle UP-TO-DATE — same .hbc). Init script `-I ../../scripts/gradle-init-mirror.gradle` — zero maven 429s.

## Build traps hit (delta vs v7 report)

1. `local.properties` belongs at `Mobile/android/local.properties`, not `Mobile/` — first build failed "SDK location not found" on the wrong path.
2. Fresh snapshot lost `~/Android/Sdk` again (v7's note stands) — reprovisioned: cmdline-tools-mac-13114758 + platform-tools + `platforms;android-36` + `build-tools;36.0.0` + `ndk;27.1.12297006` + `cmake;3.22.1`.
3. The v7 KVM child session belongs to the other org — not messageable from this one (403). Spawned a fresh Linux child for the rig instead; it provisioned the whole stack in ~4 min.

## Boot smoke — `demo` AVD pixel_7 · Android 15 google_apis x86_64 · `-accel on` KVM + SwiftShader — **ALL PASS**

(universal APK — the device-deliverable arm64 is its twin; x86_64 needed for the KVM image. sha256+size re-verified on the rig before install. Shots `docs/lanes/apk-v8-shots/` pushed as `9201986`; coordinator re-verified frames below frame-by-frame.)

| step | verdict | evidence |
|---|---|---|
| install → cold launch | **PASS** | `am start -W` COLD **TotalTime 1342 ms** |
| splash 'a'→'alive' sweep | **PASS** | 'a' alone → mid-sweep partial → held 'alive' wordmark, first-run branch only — `s01..s03` |
| consent → Skip → location | **PASS** | Skip top-right; location granted while-in-use — `s04/s05` |
| home hero live | **PASS** | **98 µg/m³ poor** · "nearest live monitor ~1.6 km · air reading 11 min" at the injected Delhi fix — `s06` |
| 'air around me' → field | **PASS** | haze field paints all streets, "the air map · **52 live stations** · 12 min old"; tap readout "100 µg/m³ — poor · Connaught Place" — `s07/s08`. 90bc055 air-gate intact: field on air intent only |
| where-to → journey → nav | **PASS** | From/To two-row card → 'finding the purest route for you…' spinner → chooser (forest picked / grey alt, plain basemap, 2 min · ~1.1 µg, air-by-hour strip) → 'start journey' → nav easeTo z~16.6 pitch~55 "20 m Continue on Outer Circle" + breathe/emit counters — `s09..s12` |
| stays | **PASS** | "where to stay" — air-scored hotel rows ~109 µg each, lighter-lead deltas (0.6/0.5 µg) vs 'same air' — `s13` |
| playtime | **PASS** | "when to go out" — 24h banded curve, least-bad window 09:30–19:30 ~94 µg vs heaviest ~127 µg, 24h avg ~110 — `s14` |
| cleartext prod reachability | **PASS** | `ss -tnp` on-device: ESTAB → `65.2.28.40:80` caught live |
| logcat crash sweep | **PASS** | 0× FATAL EXCEPTION / SIGSEGV / tombstone / ANR across **17,588 lines** |

Geo: fused mock + GNSS at 28.6315,77.2167. Bonus observed: mini-journey registered on the dosimeter — "you've breathed today 0.4 µg · 15m counted".

## Verdict

Ship `alive-aa724bb-arm64.apk` as the FINAL install binary; `alive-aa724bb-universal.apk` is the emulator/fallback twin (byte-identical JS+config, 4 ABIs). Every HEAD-carried behavior confirmed on real boot: splash wordmark, air-gated haze field, From/To trip flow through nav, stays + playtime sheets.
