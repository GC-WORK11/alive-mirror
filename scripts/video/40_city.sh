#!/usr/bin/env bash
# Shotlist beat 4 — lung reach + city ledger (1:05-1:35): /city.
# watch-the-day plays real h+0..h+11 forecast repaints, then arms
# 'where can your lungs go?' and taps Connaught Place — walk ≤50µg
# solves on the server and the veil paints the settled edge set.
# The car pill is then clicked for the shotlist's fragility contrast
# (same budget, engine-priced reach). Ends on the days-ahead strip +
# corridor table. ~38s capture, cut to ~28s.
. "$(dirname "$0")/lib.sh"
prep_window

# warm hourly frames + let the /v2/reach availability probe + outlook
# fetch settle before tape rolls (all off-recording)
cat > /tmp/act_city_pre.json <<'JSON'
[
 {"scroll_el":"#tl"},
 {"wait":1.5},
 {"eval":"(typeof tlDeep==='function')?(tlDeep(),'warming'):'tl-missing'"},
 {"wait":13},
 {"eval":"JSON.stringify({tl:Object.keys(TL.cache||{}).length,rch:!!document.getElementById('rch')&&!document.getElementById('rch').hidden,days:!!document.getElementById('days')&&!document.getElementById('days').hidden})"}
]
JSON

cat > /tmp/act_city.json <<'JSON'
[
 {"eval":"document.getElementById('tlPlay').click();'playing'"},
 {"wait":8.5},
 {"eval":"document.getElementById('tlPlay').click();'paused'"},
 {"wait":0.8},
 {"scroll_el":"#rch"},
 {"eval":"document.getElementById('rchArm').click();'armed'"},
 {"wait":0.8},
 {"click_svg":[77.2167,28.6315]},
 {"wait":7.0},
 {"eval":"(document.querySelector('#rchModes button[data-m=\"car\"]')||{click:()=>0}).click();'car'"},
 {"wait":5.0},
 {"scroll_el":"#days"},
 {"wait":3.5},
 {"scroll_el":"#corridors"},
 {"wait":5.0}
]
JSON

"$PY" "$VIDEO_DIR/cdp_rec.py" \
  --url "$NLB/city" \
  --out "$OUT_DIR/40_city.mp4" \
  --pre 5 --dur 38 \
  --pre-actions /tmp/act_city_pre.json \
  --actions /tmp/act_city.json \
  --shot "$OUT_DIR/40_city.png"
check_beat "$OUT_DIR/40_city.mp4"
