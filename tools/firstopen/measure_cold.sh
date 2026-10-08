#!/bin/bash
# Cold-open measurement for Alive on iOS sim.
# Usage: measure_cold.sh <run_label> [app_path]
# Does: uninstall -> install -> record video + log stream -> launch -> 75s capture
# Outputs: /tmp/cold_runs/<label>/ {video.mp4, frames/, appfiles.txt, logstream.txt, timing.txt}
set -u
LABEL="${1:?run label}"
APP_PATH="${2:-/Users/devin/Library/Developer/Xcode/DerivedData/ALive108-dxbimuptlimlloavlvjxaaxccpoh/Build/Products/Release-iphonesimulator/ALive108.app}"
UDID="D0B64A8A-D5F1-4668-8FFC-A86B400AF527"
BUNDLE="com.anonymous.app"
OUT="/tmp/cold_runs/$LABEL"
mkdir -p "$OUT/frames"

echo "== $LABEL =="
xcrun simctl uninstall "$UDID" "$BUNDLE" 2>/dev/null
# app container dirs are gone after uninstall; find app dir root for mtime watching
SIMDATA=$(xcrun simctl get_app_container "$UDID" "$BUNDLE" data 2>/dev/null || true)

t_install0=$(python3 -c 'import time;print(f"{time.time():.3f}")')
xcrun simctl install "$UDID" "$APP_PATH" > "$OUT/install.log" 2>&1 || { echo "install FAILED"; cat "$OUT/install.log"; exit 1; }
t_install1=$(python3 -c 'import time;print(f"{time.time():.3f}")')

# start log stream (async)
/usr/bin/log stream --device "$UDID" --predicate 'process == "ALive108"' --style compact > "$OUT/logstream.txt" 2>/dev/null &
LOGPID=$!

# start video capture (async)
xcrun simctl io "$UDID" recordVideo --codec=h264 --force "$OUT/video.mp4" > "$OUT/vid.log" 2>&1 &
VIDPID=$!
sleep 0.6   # let recorder spin up; frames before launch = black screen reference

t_launch=$(python3 -c 'import time;print(f"{time.time():.3f}")')
xcrun simctl launch "$UDID" "$BUNDLE" >> "$OUT/install.log" 2>&1
t_launchret=$(python3 -c 'import time;print(f"{time.time():.3f}")')
echo "launched at $t_launch"

# capture window
sleep 40
kill -INT "$VIDPID" 2>/dev/null; sleep 2
kill "$LOGPID" 2>/dev/null

# extract frames 4fps + luminance curve
ffmpeg -loglevel error -i "$OUT/video.mp4" -vf fps=4 "$OUT/frames/f%04d.png"
ffmpeg -loglevel error -i "$OUT/video.mp4" -vf "fps=4,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-" 2>/dev/null | grep -E "frame|YAVG" > "$OUT/luma.txt" || true

# app files + mtimes
SIMDATA=$(xcrun simctl get_app_container "$UDID" "$BUNDLE" data 2>/dev/null || true)
{ echo "SIMDATA=$SIMDATA"; find "$SIMDATA" -type f -newermt "@$(( ${t_install0%.*} - 60 ))" 2>/dev/null | while read -r f; do
    echo "$(stat -f '%m %Sm' "$f") $f";
  done | sort -n; } > "$OUT/appfiles.txt"

printf "install: %.2fs\nlaunch_ret: +%.3fs\n" "$(echo "$t_install1 - $t_install0" | bc)" "$(echo "$t_launchret - $t_launch" | bc)" | tee "$OUT/timing.txt"
echo "video: $OUT/video.mp4  frames: $(ls "$OUT/frames" | wc -l)"
