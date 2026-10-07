#!/usr/bin/env bash
# Assemble the Oct-8 cut: cards + beats -> 1920x1080/30fps/h264.
# Arc per docs/video/shotlist.md (winner pattern: felt cold-open first,
# live product, architecture + honesty cards at the end):
#   cold felt card -> title -> landing hero field -> /city ledger ->
#   dose gap ladder -> app journey -> receipt -> ledger -> settings
#   provenance -> AWS console -> admin scorecard tail -> honesty card
#   -> end card.
# Target ~2:40 (cap 3:00); trim order if long: city dwell (-5s),
# dosegap depart dwell (-4s), ledger (-3s). Protect the AWS slot.
# Skips missing beats cleanly. The AWS slot takes 80_aws.mov|mp4 when
# the owner drops his console footage in; otherwise a marked 25s
# placeholder card holds the timeline.
# @@BUILD@@/@@CIGS@@/@@UG@@/@@DATE@@ are filled live off the service so
# the cards never disagree with the tape.
# Usage: assemble.sh [beats_dir] [out.mp4]
set -euo pipefail
cd "$(dirname "$0")"
. "$(dirname "$0")/lib.sh"
D="${1:-$HOME/video/beats}"
OUT="${2:-$HOME/video/cut7.mp4}"
NLB="http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com"
W="$HOME/video/work"; mkdir -p "$W"

# cut8 beats arrive prefixed (c8_20_home.mp4 …) — link them onto the
# canonical slot names the concat list below expects. No-op for
# already-canonical names.
for f in "$D"/c8_*.mp4; do
  [ -f "$f" ] || continue
  ln -sf "$f" "$D/$(basename "$f" | sed 's/^c8_//')"
done

# live numbers -> cards (build sha, cold-open cigarette count, IST date)
SHA=$(curl -s "$NLB/health" | "$PY" -c 'import json,sys;print(json.load(sys.stdin)["build_sha"])')
CITY=$(curl -s "$NLB/v2/city")
CIGS="about $(echo "$CITY" | "$PY" -c "import json,sys;print(f'{json.load(sys.stdin)[\"breath\"][\"cigarettes\"][\"mid\"]:.1f}')")"
UG=$(echo "$CITY" | "$PY" -c "import json,sys;print(round(json.load(sys.stdin)['breath']['day_inhaled_ug']['mid']))")
DATE="$(TZ=Asia/Kolkata date +"%-d %b" | tr "[:upper:]" "[:lower:]") · morning"
for c in title cold close end; do
  sed -e "s/@@BUILD@@/$SHA/g" -e "s/@@CIGS@@/$CIGS/g" \
      -e "s/@@UG@@/$UG/g" -e "s/@@DATE@@/$DATE/g" \
      "cards/$c.html" > "$W/$c.html"
done
echo "build_sha=$SHA cigs=$CIGS ug=$UG date=$DATE"

# cards -> png (CDP shot at 1920x1080 via device-metrics override)
cardshot() { # cardshot <in.html> <out.png>
"$PY" - "$1" "$2" <<'PYEOF'
import asyncio,base64,json,sys,urllib.request,urllib.parse
CDP="http://localhost:29229"
def http(p,m="GET"):
    return json.load(urllib.request.urlopen(urllib.request.Request(CDP+p,method=m),timeout=10))
async def shot(url,out,w=1920,h=1080):
    t=http("/json/new?"+urllib.parse.quote(url,safe=""),m="PUT")
    import websockets
    async with websockets.connect(t["webSocketDebuggerUrl"]) as ws:
        mid=0
        async def send(m,p=None):
            nonlocal mid;mid+=1
            await ws.send(json.dumps({"id":mid,"method":m,"params":p or {}}))
            while True:
                r=json.loads(await ws.recv())
                if r.get("id")==mid:return r.get("result",{})
        await send("Emulation.setDeviceMetricsOverride",
                   {"width":w,"height":h,"deviceScaleFactor":1,"mobile":False})
        await send("Page.navigate",{"url":url})
        await asyncio.sleep(1.2)
        d=await send("Page.captureScreenshot",{"format":"png"})
        open(out,"wb").write(base64.b64decode(d["data"]))
    try: http("/json/close/"+t["id"])
    except Exception: pass
asyncio.run(shot("file://"+sys.argv[1],sys.argv[2]))
PYEOF
}
cardshot "$W/title.html"  "$W/title.png"
cardshot "$W/cold.html"   "$W/cold.png"
cardshot "$W/close.html"  "$W/close.png"
cardshot "$W/end.html"    "$W/end.png"

# norm <in> <out> <target_secs> — VFR-safe: fps=30 fills capture gaps,
# setpts re-anchors, tpad freezes the last frame to hit target exactly.
norm() {
  ffmpeg -y -v error -i "$1" \
    -vf "scale=1920:1080:force_original_aspect_ratio=decrease,\
pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=#FAFAF7,\
fps=30,setpts=PTS-STARTPTS,tpad=stop=-1:stop_mode=clone,format=yuv420p" \
    -t "$3" -c:v libx264 -preset fast -crf 20 -an "$2"
}
card() { # card <png> <out.mp4> <secs>
  ffmpeg -y -v error -loop 1 -t "$3" -i "$1" \
    -vf "scale=1920:1080,fps=30,format=yuv420p" \
    -c:v libx264 -preset fast -crf 20 -pix_fmt yuv420p "$2"
}

card "$W/cold.png"  "$W/00_cold.mp4"  7
card "$W/title.png" "$W/01_title.mp4" 4
card "$W/close.png" "$W/97_close.mp4" 11
card "$W/end.png"   "$W/99_end.mp4"   6

# placeholder card for the owner-filmed AWS console slot (paper register)
cat > "$W/aws_ph.html" <<'EOF'
<!doctype html><body style="margin:0;background:#FAFAF7;display:flex;align-items:center;justify-content:center;height:100vh">
<div style="font-family:Georgia,'New York',serif;color:#16181D;font-size:42px;text-align:center">AWS console — owner footage<br><span style="font:18px ui-monospace,Menlo,monospace;color:#6E7278">docs/plan/aws-console-shotlist.md · 80_aws.mov drops in here on demo morning</span></div></body>
EOF

LIST="$W/concat.txt"; : > "$LIST"
add(){ [ -f "$1" ] && { norm "$1" "$W/$2.mp4" "$3"; echo "file '$W/$2.mp4'" >> "$LIST"; } || echo "skip missing $1"; }
# addoff <in> <name> <secs> <seek_off> — tail-cut a longer tape
addoff(){ [ -f "$1" ] && { ffmpeg -y -v error -ss "$4" -i "$1" \
  -vf "scale=1920:1080:force_original_aspect_ratio=decrease,\
pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=#FAFAF7,\
fps=30,setpts=PTS-STARTPTS,tpad=stop=-1:stop_mode=clone,format=yuv420p" \
  -t "$3" -c:v libx264 -preset fast -crf 20 -an "$W/$2.mp4" \
  && echo "file '$W/$2.mp4'" >> "$LIST"; } || echo "skip missing $1"; }

echo "file '$W/00_cold.mp4'" >> "$LIST"        # 0:00 felt line — 7am Delhi
echo "file '$W/01_title.mp4'" >> "$LIST"       # 0:07 brand answers the punch
add "$D/10_hero.mp4"        10_hero        12   # live field + watch-the-day scrub
add "$D/40_city.mp4"        40_city        20   # city ledger: why-line + reach + corridors
add "$D/30_dosegap.mp4"     30_dosegap     18   # a→b ladder — the dose gap
add "$D/25_journey.mp4"     25_journey     22   # app: compare→pick→Start→nav ticking dose
add "$D/26_receipt.mp4"     26_receipt      8   # "You're here." — µg receipt
add "$D/27_ledger.mp4"      27_ledger       8   # on-phone ledger
add "$D/28_today.mp4"       28_today        9   # settings→about provenance line
AWS_SRC=""; [ -f "$D/80_aws.mov" ] && AWS_SRC="$D/80_aws.mov"; [ -f "$D/80_aws.mp4" ] && AWS_SRC="$D/80_aws.mp4"
if [ -n "$AWS_SRC" ]; then
  add "$AWS_SRC"            80_aws         25   # ECS → task def → CW → NLB → DynamoDB (owner film)
else
  cardshot "$W/aws_ph.html" "$W/aws_ph.png"
  card "$W/aws_ph.png" "$W/80_aws.mp4" 25
  echo "file '$W/80_aws.mp4'" >> "$LIST"
  echo "aws console slot = placeholder (25s)"
fi
addoff "$D/50_admin.mp4"    50_admin_tail   8 11  # scorecard + archive strip (tape tail)
echo "file '$W/97_close.mp4'" >> "$LIST"       # honesty ledger card
echo "file '$W/99_end.mp4'" >> "$LIST"         # repo + live URL + AWS + AI disclosure

ffmpeg -y -v error -f concat -safe 0 -i "$LIST" -c copy "$OUT"
echo "== $OUT =="
ffprobe -v error -show_entries format=duration,size -of default=nw=1 "$OUT"
