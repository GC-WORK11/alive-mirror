#!/usr/bin/env bash
# Shotlist beat 5 — the engine room (1:35-2:05): /admin.
# Token -> live pipeline stamps -> engine internals (dose math, routing,
# measured latency, model scorecard) -> the field map with fire dots,
# NO2 repaint for contrast, then the k>=3 corridor wire table. ~33s
# capture, cut to ~24s. Token from ~/.alive_admin_token (Secrets
# Manager copy; GET-only reads).
. "$(dirname "$0")/lib.sh"
prep_window
TOK=$(tok)

cat > /tmp/act_admin_pre.json <<JSON
[
 {"wait":2},
 {"eval":"sessionStorage.setItem('alive_admin_tok','$TOK');location.reload();'tok-set'"},
 {"wait":8}
]
JSON

cat > /tmp/act_admin.json <<'JSON'
[
 {"scroll_el":"#pipe"},
 {"wait":3.0},
 {"scroll_el":"#stats"},
 {"wait":3.5},
 {"scroll_el":"#timing"},
 {"wait":2.5},
 {"scroll_el":"#fieldmap"},
 {"wait":4.0},
 {"eval":"(typeof fmPick==='function')?(fmPick('nitrogen_dioxide'),'no2'):'no-fmPick'"},
 {"wait":2.5},
 {"eval":"(typeof fmPick==='function')?(fmPick('pm2_5'),'pm25'):'no-fmPick'"},
 {"wait":2.0},
 {"scroll_el":"#corridors"},
 {"wait":3.0},
 {"scroll_el":"#skillwrap"},
 {"wait":4.5}
]
JSON

"$PY" "$VIDEO_DIR/cdp_rec.py" --rec "${REC:-auto}" \
  --url "$NLB/admin" \
  --out "$OUT_DIR/50_admin.mp4" \
  --pre 4 --dur 30 \
  --pre-actions /tmp/act_admin_pre.json \
  --actions /tmp/act_admin.json \
  --shot "$OUT_DIR/50_admin.png"
check_beat "$OUT_DIR/50_admin.mp4"
