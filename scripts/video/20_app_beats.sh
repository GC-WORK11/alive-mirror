#!/usr/bin/env bash
# Shotlist beats 2 + journey proof — app surfaces, cut from the real
# device recordings already on disk (no re-shoot on this lane).
#
# Android merged.mp4 timeline (pts-scanned): part 1 = pts 0-44.65s
# (onboarding -> DayScreen -> search -> pick). Part 2 = ~1,300 nav
# frames all stamped pts=44.653 (collapsed pts in the merge — select
# by frame index n, not time). Part 3 = pts 198.9-208.1s (compare
# sheet -> drawer -> Trips ledger). Cuts verified by frame scrubs:
#   nav TBT w/ live dose counters:  n ~380-1560
#   "You'll arrive" + receipt card: n ~1560-1692
#   compare sheet (depart strip):   pts ~198.9-201.5
#
#   20_yourday.mp4  <- pts 15-23.5: "< your day" DayScreen — day-ahead
#                      strip (heaviest ~22:30-7pm =185 µg/m³, no clean
#                      slot — lightest is 50), sparse YOUR DAY,
#                      breath/eyes/energy check-in, tiles, "216 µg
#                      left of 216" budget card.
#   25_journey.mp4  <- search "India Gate" (pts 39.5-43) -> compare
#                      sheet w/ depart sparkline (pts 199.3-201) ->
#                      turn-by-turn w/ counters n=1300-1330 -> the
#                      "You're here" receipt n=1664-1690 -> Trips
#                      ledger pts 205-207. Real frames, resequenced.
#
# Usage: ANDROID_MP4=<path> bash 20_app_beats.sh
. "$(dirname "$0")/lib.sh"
SRC="${ANDROID_MP4:-$HOME/attachments/ac0425d5-137a-4ba9-9c68-a50e8e2d352d/merged.mp4}"
[ -f "$SRC" ] || { echo "android recording not found: $SRC"; exit 1; }
W="$HOME/video/work_app"; mkdir -p "$W"

# sparse-VFR source — -ss/-to AFTER -i seek on real pts; select-filter
# trims by pts or by decoded frame index n (needed for the pts-44.653
# collapsed block).
cut() { ffmpeg -y -v error -i "$SRC" -ss "$2" -to "$3" \
        -c:v libx264 -preset fast -crf 20 -an "$1"; }
sel() { ffmpeg -y -v error -i "$SRC" -vf \
        "select='gte(t,$2)*lte(t,$3)',setpts=PTS-STARTPTS" -vsync 0 \
        -c:v libx264 -preset fast -crf 20 -an "$1"; }
# frame-indexed select for the collapsed-pts block: all those frames
# carry pts=44.653, so retime them at the source ~8.5fps or the clip
# muxes to zero duration.
seln() { ffmpeg -y -v error -i "$SRC" -vf \
        "select='gte(n,$2)*lte(n,$3)',setpts=N/(8.5*TB)" -vsync 0 \
        -c:v libx264 -preset fast -crf 20 -an "$1"; }

cut  "$W/day.mp4"     15     23.5   # ends on the budget card, before the sheet
cut  "$W/search.mp4"  39.5   43
sel  "$W/compare.mp4" 199.3  201
seln "$W/nav.mp4"     1300   1330
seln "$W/receipt.mp4" 1664   1690
sel  "$W/trips.mp4"   205    207

cat > "$W/journey.txt" <<EOF
file '$W/search.mp4'
file '$W/compare.mp4'
file '$W/nav.mp4'
file '$W/receipt.mp4'
file '$W/trips.mp4'
EOF
# all five are CFR h264 re-encodes — concat demuxer is safe
ffmpeg -y -v error -f concat -safe 0 -i "$W/journey.txt" \
  -c:v libx264 -preset fast -crf 20 -an "$OUT_DIR/25_journey.mp4"
cp "$W/day.mp4" "$OUT_DIR/20_yourday.mp4"

check_beat "$OUT_DIR/20_yourday.mp4"
check_beat "$OUT_DIR/25_journey.mp4"
