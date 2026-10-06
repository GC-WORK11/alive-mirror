#!/usr/bin/env bash
# Shotlist beat 0 — the overhauled landing top fold (cut7).
# Hero stat tile (.hnum: LIVE chip + serif cigarettes-a-day numeral +
# provenance caption), serif headline, the two door tiles
# (.door / .door alt), then a slow pass over the daybars strip and the
# band-washed district chips (.dscroll .dchip). ~18s capture, cut to ~8s.
. "$(dirname "$0")/lib.sh"
prep_window

cat > /tmp/act_landing.json <<'JSON'
[
 {"eval":"window.scrollTo(0,0);'top'"},
 {"wait":5.0},
 {"scroll":520},
 {"wait":2.5},
 {"scroll_el":"#dscroll"},
 {"wait":3.0},
 {"eval":"(document.querySelector('.dchip')||{scrollIntoView:()=>0}).scrollIntoView({block:'nearest',inline:'center'});'chip'"},
 {"wait":3.0},
 {"scroll":420},
 {"wait":3.5}
]
JSON

"$PY" "$VIDEO_DIR/cdp_rec.py" --rec "${REC:-auto}" \
  --url "$NLB/" \
  --out "$OUT_DIR/05_landing.mp4" \
  --pre 6 --dur 18 \
  --actions /tmp/act_landing.json \
  --shot "$OUT_DIR/05_landing.png"
check_beat "$OUT_DIR/05_landing.mp4"
