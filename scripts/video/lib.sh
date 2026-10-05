#!/usr/bin/env bash
# Shared env + helpers for the ALive-108 video capture toolkit.
# Every beat records real pixels of the live service — nothing faked.
set -euo pipefail

NLB="http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com"
VIDEO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$VIDEO_DIR/../.." && pwd)"
OUT_DIR="${OUT_DIR:-$HOME/video/beats}"

# python with websockets: repo venv (linux .venv, macOS .venv312) or $VIDEO_PY
if [ -n "${VIDEO_PY:-}" ]; then PY="$VIDEO_PY"
elif [ -x "$REPO_ROOT/server/.venv312/bin/python" ]; then PY="$REPO_ROOT/server/.venv312/bin/python"
elif [ -x "$REPO_ROOT/server/.venv/bin/python" ]; then PY="$REPO_ROOT/server/.venv/bin/python"
else PY="$(command -v python3)"; fi

TOK_FILE="$HOME/.alive_admin_token"

mkdir -p "$OUT_DIR"

# Position Chrome so the page viewport lands on a fixed 1600x900 rect
# (macOS recorder only — screencast mode emulates the viewport itself).
prep_window() {
  [ "$(uname -s)" = "Darwin" ] || return 0
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
  if [ "$(uname -s)" = "Darwin" ]; then sz=$(stat -f%z "$f");
  else sz=$(stat -c%s "$f"); fi
  dur=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$f" || true)
  printf "  %s  %.1fs  %dB\n" "$(basename "$f")" "${dur:-0}" "$sz"
  ffmpeg -y -v error -ss 1 -i "$f" -frames:v 1 "${f%.*}_check.png" || true
  if [ "$sz" -lt 30000 ]; then
    echo "  !! $(basename "$f") suspiciously small ($sz B) — check frame"
    return 1
  fi
}

tok() { cat "$TOK_FILE"; }
