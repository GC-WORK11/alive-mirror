#!/bin/bash
# beat 07 — the live product on an iPhone (Safari, device-screen recording).
# Real capture of the live service on a phone canvas; no mocks.
# Re-run on demo morning: bash scripts/video/07_ios_journey.sh
set -u
cd "$(dirname "$0")" && source ./lib.sh

UDID="${SIM_UDID:-D0B64A8A-D5F1-4668-8FFC-A86B400AF527}"
OUT="$OUT_DIR/07_ios_journey.mp4"
DUR="${DUR:-20}"

STATE=$(xcrun simctl list devices | grep "$UDID" | grep -o Booted || true)
if [ -z "$STATE" ]; then
  echo "sim $UDID not booted — booting"; xcrun simctl boot "$UDID" || true; sleep 6
fi
open -a Simulator

# warm Safari BEFORE recording — kills the black lead-in.
# NOTE: on a fresh sim, Safari shows a one-time tip bubble ("View Bookmarks…");
# tap it away once by hand — it never returns on that sim install.
xcrun simctl openurl "$UDID" "$NLB/" 2>/dev/null || true
sleep 9

rm -f "$OUT"
# record the device screen
xcrun simctl io "$UDID" recordVideo --codec=h264 "$OUT" &
RPID=$!
sleep 3   # let recording warm up on the already-rendered hero

sleep 4
# page transitions are the motion — simctl recordVideo is VFR and a static
# page stops the timeline; each navigation yields fresh frames.
xcrun simctl openurl "$UDID" "$NLB/city" 2>/dev/null || true
sleep 6
xcrun simctl openurl "$UDID" "$NLB/community" 2>/dev/null || true
sleep 7

kill -INT $RPID 2>/dev/null || true
for i in $(seq 1 30); do kill -0 $RPID 2>/dev/null || break; sleep 1; done
wait $RPID 2>/dev/null || true
check_beat "$OUT"
