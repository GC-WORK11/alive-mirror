#!/usr/bin/env bash
# Shared env + helpers for the ALive-108 video capture toolkit.
# Every beat records real pixels of the live service — nothing faked.
set -euo pipefail

NLB="http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com"
VIDEO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${OUT_DIR:-$HOME/video/beats}"
PY="${VIDEO_PY:-/Users/devin/repos/Delhi-Air-108/server/.venv312/bin/python}"
TOK_FILE="$HOME/.alive_admin_token"

mkdir -p "$OUT_DIR"

# Position Chrome so the page viewport lands on a fixed 1600x900 rect.
# Window chrome (tabs+omnibox) is ~87px; viewport = window minus that.
# bounds {0,140,1600,1127} -> viewport {0,227,1600,900}.
prep_window() {
  osascript <<'OSA' >/dev/null 2>&1 || true
tell application "Google Chrome"
  activate
  set bounds of front window to {0, 140, 1600, 1127}
end tell
OSA
  sleep 0.6
}

# Verify a beat file is real: non-trivial size + a decoded frame.
check_beat() {
  local f="$1" sz dur
  sz=$(stat -f%z "$f")
  dur=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$f")
  printf "  %s  %.1fs  %dB\n" "$(basename "$f")" "$dur" "$sz"
  ffmpeg -y -v error -ss 1 -i "$f" -frames:v 1 "${f%.mov}_check.png"
  if [ "$sz" -lt 30000 ]; then
    echo "  !! $(basename "$f") suspiciously small ($sz B) — check frame"
    return 1
  fi
}

tok() { cat "$TOK_FILE"; }
