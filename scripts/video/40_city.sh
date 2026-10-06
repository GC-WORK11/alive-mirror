#!/usr/bin/env bash
# Shotlist beat 4 — lung reach + city ledger (1:05-1:35): /city (cut7).
# Holds the hero + why-tonight callout on tape, plays real h+0..h+11
# forecast repaints, then arms 'where can your lungs go?' and taps
# Connaught Place — walk reach solves on the server; an await-eval polls
# #rchCap until 'segments drawn' (or an honest error) instead of a fixed
# wait, so the ink-vein paint is always on tape. Ends with a paged pan
# through the days-ahead band-washed tiles and the live corridor table
# (sections reveal via IntersectionObserver — single jumps leave blanks).
# ~55s capture, cut to ~20s.
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
 {"eval":"window.scrollTo(0,0);'top-hero-whyline'"},
 {"wait":4.0},
 {"scroll_el":"#tl"},
 {"eval":"document.getElementById('tlPlay').click();'playing'"},
 {"wait":8.5},
 {"eval":"document.getElementById('tlPlay').click();'paused'"},
 {"wait":0.8},
 {"scroll_el":"#rch"},
 {"eval":"document.getElementById('rchArm').click();'armed'"},
 {"wait":0.8},
 {"click_svg":[77.2167,28.6315]},
 {"eval":"(async()=>{const t0=performance.now();while(performance.now()-t0<28000){const c=(document.getElementById('rchCap')||{}).textContent||'';if(/segments drawn|reach —|outside|warming|still warming/.test(c))return 'cap:'+c.slice(0,140);await new Promise(r=>setTimeout(r,400))}return 'poll-timeout:'+((document.getElementById('rchCap')||{}).textContent||'').slice(0,140)})()"},
 {"wait":3.0},
 {"scroll_el":"#days"},
 {"wait":3.5},
 {"scroll":560},
 {"wait":2.2},
 {"scroll":560},
 {"wait":2.2},
 {"scroll_el":"#corridors"},
 {"wait":5.0}
]
JSON

"$PY" "$VIDEO_DIR/cdp_rec.py" --rec "${REC:-auto}" \
  --url "$NLB/city" \
  --out "$OUT_DIR/40_city.mp4" \
  --pre 5 --dur 55 \
  --pre-actions /tmp/act_city_pre.json \
  --actions /tmp/act_city.json \
  --shot "$OUT_DIR/40_city.png"
check_beat "$OUT_DIR/40_city.mp4"
