#!/usr/bin/env bash
# Shotlist beat 7 — the close (2:30-2:50): back to the landing hero.
# The claim and the live field, held quietly. ~10s capture, cut to ~6s.
. "$(dirname "$0")/lib.sh"
prep_window
cat > /tmp/act_close.json <<'JSON'
[
 {"eval":"window.scrollTo(0,0);'top'"},
 {"wait":9}
]
JSON
"$PY" "$VIDEO_DIR/cdp_rec.py" \
  --url "$NLB/" \
  --out "$OUT_DIR/90_close.mp4" \
  --pre 6 --dur 10 \
  --actions /tmp/act_close.json \
  --shot "$OUT_DIR/90_close.png"
check_beat "$OUT_DIR/90_close.mp4"
