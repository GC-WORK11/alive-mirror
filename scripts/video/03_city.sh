#!/usr/bin/env bash
# Beat 5a — /city: the live district choropleth + stamp line; a slow
# drift lets the district numbers + confidence read. ~12s.
. "$(dirname "$0")/lib.sh"
prep_window
cat > /tmp/act_city.json <<JSON
[
 {"wait":4},
 {"scroll":420},
 {"wait":3},
 {"scroll":420},
 {"wait":4}
]
JSON
"$PY" "$VIDEO_DIR/cdp_rec.py" \
  --url "$NLB/city" \
  --out "$OUT_DIR/03_city.mov" \
  --pre 5 --dur 15 \
  --actions /tmp/act_city.json \
  --shot "$OUT_DIR/03_city.png"
check_beat "$OUT_DIR/03_city.mov"
