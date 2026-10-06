#!/usr/bin/env bash
# Assemble the dosimeter-arc cut: cards + beats -> 1920x1080/30fps/h264.
# cut7 order (the overhaul pass): title -> landing top fold (hero stat
# tile + door tiles + band-washed districts) -> field watch-the-day ->
# app home (paper doors) -> app door taps -> app journey -> receipt ->
# ledger -> DelhiToday -> dose gap (a->b) -> city (why-line + reach +
# day tiles + corridors) -> community -> admin engine room -> AWS
# console -> close -> end card.
# Target <=2:55; trim order if long: city reach line (-15s), admin
# field-map pan (-10s), app journey (-5s).
# Skips missing beats cleanly. The AWS slot takes 80_aws.mov|mp4 when
# the owner drops his console footage in; otherwise a marked 25s
# placeholder card holds the timeline.
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
add "$D/05_landing.mp4"     05_landing      7   # overhauled top fold: hero stat + doors + districts
add "$D/10_hero.mp4"        10_hero        10   # live field + watch-the-day scrub
add "$D/20_home.mp4"        20_home        13   # app dosimeter home — paper doors + tinted chips
add "$D/22_doors.mp4"       22_doors        7   # door taps (the air map / Delhi today / your trips)
add "$D/25_journey.mp4"     25_journey     15   # search→compare→pick→Start→nav (pick persists)
add "$D/26_receipt.mp4"     26_receipt      7   # arrival receipt + ledger (dedupe gone)
add "$D/27_ledger.mp4"      27_ledger       5   # ledger dose hero
add "$D/28_today.mp4"       28_today        7   # DelhiToday clay hero + why-line
add "$D/30_dosegap.mp4"     30_dosegap     18   # a→b priced corridor + dose ladder
add "$D/40_city.mp4"        40_city        20   # why-line + reach + day tiles + corridors
add "$D/65_community.mp4"   65_community    7   # ledger stats + corridor cells
add "$D/50_admin.mp4"       50_admin       19   # engine room — kchips/caps + field map
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
