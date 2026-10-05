#!/usr/bin/env bash
# Shotlist beat 3 — the dose gap (0:35-1:05): a→b on the landing field.
# Arms a→b, picks Connaught Place -> Gurugram — the real /v2/plan call
# paints the route arc + per-mode dose ladder + the annualized honesty
# line + the /depart dose-by-hour sparkline. ~31s capture, cut to ~26s.
. "$(dirname "$0")/lib.sh"
prep_window

cat > /tmp/act_ab.json <<'JSON'
[
 {"scroll_el":"#raster"},
 {"eval":"document.querySelector('#msel button[data-m=\"ab\"]').click();'ab-armed'"},
 {"wait":1.0},
 {"click_geo":[77.2167,28.6315]},
 {"wait":1.2},
 {"click_geo":[77.0266,28.4595]},
 {"wait":8.0},
 {"scroll_el":"#departline"},
 {"wait":6.0},
 {"scroll_el":"#ladder"},
 {"wait":8.0},
 {"scroll_el":"#raster"},
 {"wait":5.0}
]
JSON

"$PY" "$VIDEO_DIR/cdp_rec.py" --rec "${REC:-auto}" \
  --url "$NLB/" \
  --out "$OUT_DIR/30_dosegap.mp4" \
  --pre 6 --dur 31 \
  --actions /tmp/act_ab.json \
  --shot "$OUT_DIR/30_dosegap.png"
check_beat "$OUT_DIR/30_dosegap.mp4"
