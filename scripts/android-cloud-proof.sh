#!/usr/bin/env bash
# android-cloud-proof.sh — reproduce the cloud Android runtime proof for Alive.
#
# What it does, end to end:
#   1. fixes /dev/kvm perms (needs sudo once)
#   2. boots the Pixel_7 AVD headless (SwiftShader, 1536MB)
#   3. waits for sys.boot_completed=1
#   4. starts the FastAPI backend on :8000 (app hits http://10.0.2.2:8000)
#   5. npm ci + removes the foojay toolchain resolver (JDK is local)
#   6. builds + installs the debug APK via `npx expo run:android --no-bundler`
#   7. starts Metro (CI mode) + `adb reverse tcp:8081`
#
# Maven Central 429s on this egress: the repo's settings.gradle already lists
# the Google mirror first, but INCLUDED builds under node_modules have their
# own pluginManagement — use scripts/gradle-init-mirror.gradle:
#   cp scripts/gradle-init-mirror.gradle ~/.gradle/init.d/gradle-init-mirror.gradle
# (picked up by every gradle invocation, including inside `expo run:android`),
# or pass `./gradlew -I ../scripts/gradle-init-mirror.gradle <tasks>` directly.
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p ~/.gradle/init.d
cp scripts/gradle-init-mirror.gradle ~/.gradle/init.d/gradle-init-mirror.gradle

AVD="${AVD:-Pixel_7}"
EMU_MEM="${EMU_MEM:-1536}"

sudo chmod 666 /dev/kvm || true

if ! adb devices | grep -q emulator; then
  setsid nohup "$ANDROID_HOME/emulator/emulator" -avd "$AVD" -no-window \
    -gpu swiftshader_indirect -no-snapshot-load -no-audio -no-metrics \
    -no-boot-anim -memory "$EMU_MEM" > /tmp/emulator.log 2>&1 &
fi
adb wait-for-device
until [ "$(adb shell getprop sys.boot_completed | tr -d '\r')" = "1" ]; do sleep 5; done
echo "[ok] emulator booted"

(cd server && setsid nohup .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 \
  > /tmp/uvicorn.log 2>&1 &)
until curl -sf -m 3 localhost:8000/health > /dev/null; do sleep 2; done
echo "[ok] backend healthy on :8000"

cd Mobile
npm ci
# JDK 17 is installed locally; the foojay toolchain resolver's impl jar only
# exists on Maven Central (no mirror carries it) and 429s — drop the plugin.
sed -i.bak '/foojay-resolver-convention/d' \
  node_modules/@react-native/gradle-plugin/settings.gradle.kts

npx expo run:android --no-bundler
adb reverse tcp:8081 tcp:8081
setsid nohup env CI=1 npx expo start --port 8081 > /tmp/metro.log 2>&1 &
sleep 10
adb shell am force-stop com.anonymous.app || true
adb shell am start -n com.anonymous.app/.MainActivity
echo "[ok] app launched — drive it with adb input/uiautomator"
