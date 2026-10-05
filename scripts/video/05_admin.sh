#!/usr/bin/env bash
# Beats 5b/7 — /admin: token -> KPI tiles -> district chips -> the live
# field map with fires overlay, then click the NO2 species pill and hold
# on the repainted map (physically different pattern, same lattice).
# ~30s. Token comes from ~/.alive_admin_token (Secrets Manager copy).
. "$(dirname "$0")/lib.sh"
prep_window
TOK=$(tok)

cat > /tmp/act_admin_pre.json <<JSON
[
 {"wait":2},
 {"eval":"sessionStorage.setItem('alive_admin_tok','$TOK');location.reload();'tok-set'"},
 {"wait":7}
]
JSON

cat > /tmp/act_admin.json <<JSON
[
 {"scroll_el":"#distmap"},
 {"wait":3.5},
 {"scroll_el":"#fieldmap"},
 {"wait":4},
 {"eval":"fmPick('nitrogen_dioxide');'no2'"},
 {"wait":4},
 {"eval":"fmPick('us_aqi');'usaqi'"},
 {"wait":3},
 {"eval":"fmPick('pm2_5');'pm25'"},
 {"wait":3},
 {"scroll_el":"#pipe"},
 {"wait":3},
 {"scroll_el":"#corridors"},
 {"wait":4}
]
JSON

"$PY" "$VIDEO_DIR/cdp_rec.py" \
  --url "$NLB/admin" \
  --out "$OUT_DIR/05_admin.mov" \
  --pre 4 --dur 34 \
  --pre-actions /tmp/act_admin_pre.json \
  --actions /tmp/act_admin.json \
  --shot "$OUT_DIR/05_admin.png"
check_beat "$OUT_DIR/05_admin.mov"
