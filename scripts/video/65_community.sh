#!/usr/bin/env bash
# Supplementary — /community corridors (folds into the ledger stretch of
# the cut, just before the engine room). Hero -> ledger rows ->
# k>=3 corridor table. ~14s capture, cut to ~8s.
. "$(dirname "$0")/lib.sh"
prep_window
cat > /tmp/act_comm.json <<'JSON'
[
 {"wait":4},
 {"scroll":560},
 {"wait":4},
 {"scroll":560},
 {"wait":5}
]
JSON
"$PY" "$VIDEO_DIR/cdp_rec.py" --rec "${REC:-auto}" \
  --url "$NLB/community" \
  --out "$OUT_DIR/65_community.mp4" \
  --pre 5 --dur 14 \
  --actions /tmp/act_comm.json \
  --shot "$OUT_DIR/65_community.png"
check_beat "$OUT_DIR/65_community.mp4"
