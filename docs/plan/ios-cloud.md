# iOS + Android builds in CI (cloud proof lane)

Why this file: our dev VMs can't do both platforms. Linux boxes run the
Android emulator but have no Xcode; macOS boxes build iOS but can't run the
Android emulator (no nested HVF). GitHub-hosted runners close the gap —
`ubuntu-latest` ships the Android SDK, `macos-latest` ships Xcode + the iOS
Simulator runtimes.

## Workflows

### `.github/workflows/ios-sim.yml` — build the app and run it on a simulator

Runs on `macos-latest`:

1. checkout, Node 22 (`npm ci` in `Mobile/`), JDK 17
2. `pod install` in `Mobile/ios` with `LANG=en_US.UTF-8` (CocoaPods fails
   under a non-UTF-8 locale)
3. `xcrun simctl create "iPhone 15" "iPhone 15"` + `simctl boot` — creating
   the device is required because runner images don't guarantee an
   "iPhone 15" device exists, only the device *type*
4. `xcodebuild -workspace ios/app.xcworkspace -scheme app
   -configuration Release -destination 'platform=iOS Simulator,name=iPhone 15'`
   — Release config so the JS bundle is embedded; a Debug build would look
   for a Metro server at launch and show a red error screen
5. start `server/` uvicorn on `:8000` (the app calls `localhost:8000`; the
   simulator shares the host network) — best effort, app still renders
   without it
6. `xcrun simctl install booted <derivedData>/Release-iphonesimulator/app.app`,
   `simctl launch booted com.anonymous.app`, then
   `xcrun simctl io booted screenshot` + app logs into `artifacts/`
7. `upload-artifact` → **ios-sim-proof** (screenshots, video clip, sim log)

### `.github/workflows/android-apk.yml` — build installable + release APKs

Runs on `ubuntu-latest` (Android SDK preinstalled):

1. checkout, Node 22, JDK 17, `npm ci` in `Mobile/`
2. `./gradlew assembleDebug assembleRelease` in `Mobile/android`
   (not `expo run:android --variant release`: expo tries to install/launch
   on a device and fails on a runner with no emulator)
3. `upload-artifact` → **android-apks**
   - `app-debug.apk` — signed with the debug key, installable on a device
   - `app-release-unsigned.apk` — unsigned; cannot install until signed
     with a real keystore (signing gap is documented, not fixed, here)

Both trigger on `workflow_dispatch` and on pushes that touch `Mobile/**`.

## How to run

- Actions tab → `ios-sim` or `android-apk` → **Run workflow** → pick the
  branch. Artifacts appear on the run page when it finishes.
- First iOS run downloads ~5 GB of dependencies (pods, Xcode build) — expect
  30–50 min. Android is ~10–20 min depending on gradle cache warmth.

## Cost caveat — private repos

GitHub Actions minutes are **free on public repos**. On private repos they
draw down the plan's included minutes, and the **macOS runner multiplies
minutes ×10** (Linux ×1, Windows ×2). A 40-minute iOS job ≈ 400 billed
minutes — keep `ios-sim` on `workflow_dispatch` and don't point it at every
push if the repo ever goes private.

## What CI does NOT cover yet

- Android emulator + `adb` UI screenshots (runs on our Linux Devin boxes —
  see `docs/assets/cloud-build/` for real captures). GitHub runners can do
  it via `reactivecircus/android-emulator-runner` if ever needed.
- App-store signing for either platform (keystore / Apple provisioning).
