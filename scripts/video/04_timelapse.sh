#!/usr/bin/env bash
# Beat 4/showpiece — /city 'watch the day': warm the 12 hourly /grid
# frames first (tlDeep), then press play — cells re-paint h+0..h+11 on
# the real forecast surfaces while district fills keep reading live.
# Recording covers the play itself; trim head/tail in assembly. ~22s.
. "$(dirname "$0")/lib.sh"
prep_window

# pre-actions: warm every hour's frame so playback doesn't stall on
# first-play fetches (~12 fetches, each ~0.5-1.5s over the NLB).
cat > /tmp/act_tl_pre.json <<JSON
[
 {"scroll_el":"#tl"},
 {"eval":"(typeof tlDeep==='function')?(tlDeep(),'warming'):'tl-missing'"},
 {"wait":14},
 {"eval":"JSON.stringify(Object.keys(TL.cache).map(Number).sort((a,b)=>a-b))"}
]
JSON

cat > /tmp/act_tl.json <<JSON
[
 {"eval":"document.getElementById('tlPlay').click();'playing'"},
 {"wait":19}
]
JSON

"$PY" "$VIDEO_DIR/cdp_rec.py" \
  --url "$NLB/city" \
  --out "$OUT_DIR/04_timelapse.mov" \
  --pre 5 --dur 21 \
  --pre-actions /tmp/act_tl_pre.json \
  --actions /tmp/act_tl.json \
  --shot "$OUT_DIR/04_timelapse.png"
check_beat "$OUT_DIR/04_timelapse.mov"
