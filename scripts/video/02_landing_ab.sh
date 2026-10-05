#!/usr/bin/env bash
# Beat 3 — a→b on the landing field: scroll the map in, arm a→b, pick
# Connaught Place -> Gurugram — the real /v2/plan call paints the
# corridor + dose ladder + /depart dose-by-hour sparkline. ~36s.
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
 {"wait":7.0},
 {"scroll_el":"#departline"},
 {"wait":7.0},
 {"scroll_el":"#ladder"},
 {"wait":7.0},
 {"scroll_el":"#raster"},
 {"wait":4.0}
]
JSON

"$PY" "$VIDEO_DIR/cdp_rec.py" \
  --url "$NLB/" \
  --out "$OUT_DIR/02_landing_ab.mov" \
  --pre 6 --dur 37 \
  --actions /tmp/act_ab.json \
  --shot "$OUT_DIR/02_landing_ab.png"
check_beat "$OUT_DIR/02_landing_ab.mov"
