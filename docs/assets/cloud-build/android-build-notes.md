# Android build + runtime proof — feat/c-build

Captured 2026-10-03 UTC on a cloud Linux VM (Ubuntu, KVM). Commit `c0dcf5e`
(branch `feat/c-build`, base `origin/base/v2`). No app source code was modified.

## What ran

| Step | Command | Result |
|---|---|---|
| Checkout | `git fetch origin && git checkout feat/c-build` | OK (`c0dcf5e`) |
| Emulator | `$ANDROID_HOME/emulator/emulator -avd Pixel_7 -no-window -gpu swiftshader_indirect -no-snapshot-load -no-audio -no-metrics -no-boot-anim -memory 1536` | OK — existing AVD reused, `sys.boot_completed=1`, 1080x2400 |
| Backend | `python3 -m venv .venv && pip install -r requirements.txt && .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000` | OK — `GET /health` → `{"ok":true,"version":"v2","build_sha":"c0dcf5e"}`, 125-station climatology loaded |
| App install | `npm ci` | OK |
| Debug build | `npx expo run:android --no-bundler` | OK after two fixes below — `BUILD SUCCESSFUL in 2m 10s`, installed + launched |
| JS bundle | `CI=1 npx expo start --port 8081` + `adb reverse tcp:8081 tcp:8081` | OK — `packager-status:running` |
| Release build | `cd android && ./gradlew assembleRelease -x lint` | OK — `BUILD SUCCESSFUL in 2m 1s`, 352 tasks |

## Environment

- **AVD**: `Pixel_7` — Android API 35, google_apis/x86_64 (pre-provisioned; no new AVD created)
- **SDK**: `~/Android/Sdk`; had to add `platforms;android-36`, `build-tools;36.0.0`, `ndk;27.1.12297006`, `cmake;3.22.1` (RN 0.86 / Expo SDK 57 requirements — only android-35 was installed)
- **App**: `com.anonymous.app`, RN 0.86.3, new arch (Fabric), Hermes
- **API wiring**: app falls back to `http://10.0.2.2:8000` on Android (`src/search/client.ts`, `src/components/shell/net.ts`) — the emulator's host loopback; `EXPO_PUBLIC_API_URL` was not set, so the release APK bakes in that same emulator fallback

## Build fixes required (no repo code changes)

1. **foojay-resolver-convention** — `org.gradle.toolchains:foojay-resolver:1.0.0`
   exists only on Maven Central (no mirror carries it) and this egress gets
   HTTP 429 from `repo.maven.apache.org`. Deleted the plugin line in
   `node_modules/@react-native/gradle-plugin/settings.gradle.kts` (it only
   resolves JDK toolchains; JDK 17 is already installed). Must be re-applied
   after every `npm ci`.
2. **Maven Central 429 inside included builds** — the project's own
   `settings.gradle` already puts the Google mirror first, but the included
   builds (`@react-native/gradle-plugin`, `expo-gradle-plugin`) have their own
   `pluginManagement` blocks with bare `mavenCentral()` first, so
   `org.jetbrains.kotlin.jvm` 2.1.20 plugin resolution still hit the
   rate-limited host. Fixed with a Gradle init script that rewrites
   central/portal URLs to mirrors across the whole composite
   (`gradle.beforeSettings` — `settingsEvaluated` is too late for `plugins{}`).
   Canonical copy committed by the sibling lane at
   `scripts/gradle-init-mirror.gradle` (copy it to `~/.gradle/init.d/` so
   `expo run:android` picks it up, or pass `-I` to gradlew).

## APKs produced (under `Mobile/android/app/build/outputs/apk/`)

| File | Size | Variant | Signing |
|---|---|---|---|
| `debug/app-debug.apk` | 65 MB | debug, x86_64 | debug keystore |
| `release/app-release.apk` | 123 MB | release, all 4 ABIs, Hermes `index.android.bundle` embedded (3.6 MB) | **debug keystore** (`CN=Android Debug`, SHA-256 `fac61745…`) |

**Signing gap (honest):** the release APK is signed with the stock Expo/RN
debug keystore (`signingConfigs.debug` wired into the release build type).
It installs and runs, but is NOT a Play-Store-grade signature — a real
release keystore still needs to be generated and wired before distribution.

`usesCleartextTraffic="true"` confirmed in the built APK manifest (needed for
the http:// backend).

## Runtime proof (screenshots in this directory)

- `android-home-map.png` — dark MapLibre basemap over Delhi, "Where to?" pill
- `android-search-open.png` — search sheet with keyboard, Your location / Choose on map
- `android-search-results.png` — typed "connaught place" → live results from
  the backend over `10.0.2.2:8000` (Photon geocoder)
- `android-plan-options.png` — route drawn to Connaught Place pin; ranked
  modes: Car (AC) "lightest for you" 8 min, Car (windows down), Metro + walk
  15 min (Udyog Bhawan→Rajiv Chowk), Bus 13 min, Auto-rickshaw 10 min,
  Bike/scooter 7 min; "leave 14:30 → breathe ~81% less" depart-later chip
- `android-plan-metro.png` — Metro + walk selected, transit polyline on map

Flow exercised end-to-end on-device: search → geocode → plan → per-mode dose
ranking — all against the locally running FastAPI backend.

## logcat (`android-logcat.txt`)

No JS exceptions, no `RCTFatal`, no crashes. Notable benign lines:

- `ReactNoCrashSoftException … onWindowFocusChange while context is not ready`
  — RN startup race, self-heals, non-fatal.
- `StatusBarModule: Ignored status bar change, current activity is edge-to-edge`
  — cosmetic.
- `Mbgl-HttpRequest: Request failed due to a permanent error: Canceled` —
  normal tile-request cancellation on viewport changes.
- `Default FirebaseApp failed to initialize` — no google-services.json; expected.
- One-time `Unable to load script` red screen at first launch — the APK
  opened before Metro/`adb reverse` were up; resolved by
  `adb reverse tcp:8081` + force-stop + relaunch (ordering artifact, not a
  code bug).

## Reproduce

`scripts/android-cloud-proof.sh` automates the whole lane (KVM perms → AVD
boot → backend → npm ci → foojay sed → mirror init script → run:android →
Metro + adb reverse → relaunch).
