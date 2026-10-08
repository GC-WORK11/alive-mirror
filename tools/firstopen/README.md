# first-open cold-install tooling (iOS sim)

Written for the Alive first-open lane (Oct 2026). Android emulator cannot run
on the macOS VM, so all of this targets the iOS Simulator.

## measure_cold.sh

```
tools/firstopen/measure_cold.sh <label> [path/to/ALive108.app]
```

Uninstall → install → `simctl io recordVideo` → launch → ~40 s capture →
`ffmpeg` frames at 4 fps into `/tmp/cold_runs/<label>/`. Daylog mtimes land
alongside for fetch timing. Default `.app` path is the Release-iphonesimulator
product in DerivedData.

## Release .app recipe (cold install without Metro)

```
cd Mobile
LANG=en_US.UTF-8 xcodebuild -workspace ios/ALive108.xcworkspace \
  -scheme ALive108 -configuration Release -sdk iphonesimulator \
  -derivedDataPath <DD> build
# JS bundle hot-swap (no rebuild needed for JS-only changes):
npx expo export --platform ios --dev false --output-dir /tmp/exp --clear
cp /tmp/exp/_expo/static/js/ios/*.hbc \
   <DD>/Build/Products/Release-iphonesimulator/ALive108.app/main.jsbundle
xcrun simctl install <udid> <DD>/Build/Products/Release-iphonesimulator/ALive108.app
```

`EXPO_PUBLIC_API_URL` is inlined at export time — pass it to `expo export`,
not to the install.

## Throttling (dnctl/pf dummynet does NOT work on this box)

```
python3 tools/firstopen/throttle_proxy.py   # listens :8790 -> 65.2.28.40:80, control :8791
curl 127.0.0.1:8791/rate/125000             # ~1 Mbps; /rate/0 unthrottles
# then export the bundle with EXPO_PUBLIC_API_URL=http://127.0.0.1:8790
```

Boot payloads are small (~12 KB total), so ~1 Mbps barely moves timings —
RTT, not bandwidth, is the cost. Verdicts above are what the throttle showed.

## Gotchas that cost this lane hours

- `expo export` caches transforms WITHOUT keying on `EXPO_PUBLIC_*` env vars.
  Always pass `--clear` when re-exporting with a different env.
- Pending iOS permission dialogs persist per bundle-id across
  uninstall/reinstall on a sim — a dialog from a previous run reappears on
  the new install's first launch. For clean cold runs:
  `xcrun simctl shutdown <udid> && xcrun simctl boot <udid>` plus
  `xcrun simctl privacy <udid> reset location <bundle-id>`.
- `simctl io recordVideo` produces irregular PTS (~1.5 fps effective, dup
  DTS). Frame-index math is unreliable — seek with `ffmpeg -ss <sec>` on
  the recording instead.
