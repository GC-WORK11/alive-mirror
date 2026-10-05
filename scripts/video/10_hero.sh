#!/usr/bin/env bash
# Shotlist beat 1 — hero (0:00-0:12): landing claim + the live field.
# The plume visibly drifts: after tlDeep warms the hourly /grid frames
# (pre-actions, off-tape), the recording steps h+2→h+10 then back to now —
# every repaint is a real forecast surface. ~15s capture, cut to ~11s.
. "$(dirname "$0")/lib.sh"
prep_window

cat > /tmp/act_hero_pre.json <<'JSON'
[
 {"scroll_el":"#raster"},
 {"wait":1.5},
 {"eval":"(typeof tlDeep==='function')?(tlDeep(),'warming'):'tl-missing'"},
 {"wait":13},
 {"eval":"JSON.stringify(Object.keys(TL.cache||{}).map(Number).sort((a,b)=>a-b))"}
]
JSON

cat > /tmp/act_hero.json <<'JSON'
[
 {"wait":2.5},
 {"eval":"tlSetHour(2);tlShow(2);'h2'"},
 {"wait":1.4},
 {"eval":"tlSetHour(4);tlShow(4);'h4'"},
 {"wait":1.4},
 {"eval":"tlSetHour(6);tlShow(6);'h6'"},
 {"wait":1.4},
 {"eval":"tlSetHour(8);tlShow(8);'h8'"},
 {"wait":1.4},
 {"eval":"tlSetHour(10);tlShow(10);'h10'"},
 {"wait":1.4},
 {"eval":"tlSetHour(0);tlShow(0);'now'"},
 {"wait":4.5}
]
JSON

"$PY" "$VIDEO_DIR/cdp_rec.py" \
  --url "$NLB/" \
  --out "$OUT_DIR/10_hero.mp4" \
  --pre 6 --dur 15 \
  --pre-actions /tmp/act_hero_pre.json \
  --actions /tmp/act_hero.json \
  --shot "$OUT_DIR/10_hero.png"
check_beat "$OUT_DIR/10_hero.mp4"
