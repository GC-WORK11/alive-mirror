#!/usr/bin/env bash
# Beat 1 — landing: hero claim, then scroll to the live field map
# (1,156 cells drifting on real wind + stations/edges stats row).
# ~14s.
. "$(dirname "$0")/lib.sh"
prep_window
cat > /tmp/act_landing.json <<'JSON'
[
 {"wait":4},
 {"scroll_el":"#raster"},
 {"wait":8}
]
JSON
"$PY" "$VIDEO_DIR/cdp_rec.py" \
  --url "$NLB/" \
  --out "$OUT_DIR/01_landing.mov" \
  --pre 6 --dur 14 \
  --actions /tmp/act_landing.json \
  --shot "$OUT_DIR/01_landing.png"
check_beat "$OUT_DIR/01_landing.mov"
