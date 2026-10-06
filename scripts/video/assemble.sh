#!/usr/bin/env bash
# Assemble the dosimeter-arc cut: cards + beats -> 1920x1080/30fps/h264.
# Cut order follows docs/submission/video-shotlist.md:
#   title -> hero -> your-day (app) -> journey (app) -> dose gap (a→b)
#   -> city (reach + days + corridors) -> community corridors
#   -> admin engine room -> AWS console -> close -> end card.
# Target <=2:50; trim order if long: city reach line (-15s), admin
# field-map pan (-10s), your-day decision strings (-8s).
# Skips missing beats cleanly. The AWS slot takes 80_aws.mov|mp4 when
# the owner drops his console footage in; otherwise a marked 25s
# placeholder card holds the timeline.
# Usage: assemble.sh [beats_dir] [out.mp4]
set -euo pipefail
cd "$(dirname "$0")"
. "$(dirname "$0")/lib.sh"
D="${1:-$HOME/video/beats}"
OUT="${2:-$HOME/video/cut5.mp4}"
NLB="http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com"
W="$HOME/video/work"; mkdir -p "$W"

# live build sha -> title card
SHA=$(curl -s "$NLB/health" | "$PY" -c 'import json,sys;print(json.load(sys.stdin)["build_sha"])')
sed "s/@@BUILD@@/$SHA/" cards/title.html > "$W/title.html"
echo "build_sha=$SHA"

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
cardshot "$W/title.html"        "$W/title.png"
cardshot "$PWD/cards/end.html"  "$W/end.png"

# norm <in> <out> <target_secs> — VFR-safe: fps=30 fills capture gaps,
# setpts re-anchors, tpad freezes the last frame to hit target exactly.
norm() {
  ffmpeg -y -v error -i "$1" \
    -vf "scale=1920:1080:force_original_aspect_ratio=decrease,\
pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=#14181f,\
fps=30,setpts=PTS-STARTPTS,tpad=stop=-1:stop_mode=clone,format=yuv420p" \
    -t "$3" -c:v libx264 -preset fast -crf 20 -an "$2"
}
card() { # card <png> <out.mp4> <secs>
  ffmpeg -y -v error -loop 1 -t "$3" -i "$1" \
    -vf "scale=1920:1080,fps=30,format=yuv420p" \
    -c:v libx264 -preset fast -crf 20 -pix_fmt yuv420p "$2"
}

card "$W/title.png" "$W/00_title.mp4" 3
card "$W/end.png"   "$W/99_end.mp4"   5

# placeholder card for the owner-filmed AWS console slot
cat > "$W/aws_ph.html" <<'EOF'
<!doctype html><body style="margin:0;background:#14181f;display:flex;align-items:center;justify-content:center;height:100vh">
<div style="font-family:Georgia,serif;color:#e8e4d8;font-size:42px;text-align:center">AWS console — owner footage<br><span style="font:18px monospace;color:#9a9">docs/plan/aws-console-shotlist.md · 80_aws.mov drops in here on demo morning</span></div></body>
EOF

LIST="$W/concat.txt"; : > "$LIST"
add(){ [ -f "$1" ] && { norm "$1" "$W/$2.mp4" "$3"; echo "file '$W/$2.mp4'" >> "$LIST"; } || echo "skip missing $1"; }

echo "file '$W/00_title.mp4'" >> "$LIST"
add "$D/10_hero.mp4"        10_hero        11   # shotlist 1 — hero
add "$D/20_yourday.mp4"     20_yourday     10   # shotlist 2 — DayScreen
add "$D/25_journey.mp4"     25_journey     14   # compare→pick→Start→nav (pick persists)
add "$D/26_receipt.mp4"     26_receipt      8   # arrival receipt + ledger (dedupe gone)
add "$D/28_today.mp4"       28_today        8   # DelhiToday why-line (beat 4)
add "$D/30_dosegap.mp4"     30_dosegap     24   # shotlist 3 — a→b
add "$D/40_city.mp4"        40_city        24   # shotlist 4 — reach/days
add "$D/65_community.mp4"   65_community    8   # corridor cells
add "$D/50_admin.mp4"       50_admin       22   # shotlist 5 — engine room
AWS_SRC=""; [ -f "$D/80_aws.mov" ] && AWS_SRC="$D/80_aws.mov"; [ -f "$D/80_aws.mp4" ] && AWS_SRC="$D/80_aws.mp4"
if [ -n "$AWS_SRC" ]; then
  add "$AWS_SRC"            80_aws         25   # shotlist 6 — owner film
else
  cardshot "$W/aws_ph.html" "$W/aws_ph.png"
  card "$W/aws_ph.png" "$W/80_aws.mp4" 25
  echo "file '$W/80_aws.mp4'" >> "$LIST"
  echo "aws console slot = placeholder (25s)"
fi
add "$D/90_close.mp4"       90_close        6   # shotlist 7 — close
echo "file '$W/99_end.mp4'" >> "$LIST"

ffmpeg -y -v error -f concat -safe 0 -i "$LIST" -c copy "$OUT"
echo "== $OUT =="
ffprobe -v error -show_entries format=duration,size -of default=nw=1 "$OUT"
