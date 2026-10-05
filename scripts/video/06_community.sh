#!/usr/bin/env bash
# Beat 5c — /community: contributors, donated km, corridors gated k>=3.
# ~12s scroll through the honest feed states.
. "$(dirname "$0")/lib.sh"
prep_window
cat > /tmp/act_comm.json <<JSON
[
 {"wait":4},
 {"scroll":500},
 {"wait":3.5},
 {"scroll":500},
 {"wait":4}
]
JSON
"$PY" "$VIDEO_DIR/cdp_rec.py" \
  --url "$NLB/community" \
  --out "$OUT_DIR/06_community.mov" \
  --pre 5 --dur 15 \
  --actions /tmp/act_comm.json \
  --shot "$OUT_DIR/06_community.png"
check_beat "$OUT_DIR/06_community.mov"
