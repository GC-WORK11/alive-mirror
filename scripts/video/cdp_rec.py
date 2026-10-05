#!/usr/bin/env python3
"""Record one browser beat of the live ALive-108 product.

Drives the already-running Chrome over CDP (localhost:29229) and records
the page while a JSON action list runs — so every frame on tape is real
page pixels of the live service.

Recorders (auto = screencast on Linux/headless, screencapture on macOS):
  screencast     — Page.startScreencast at an emulated WxH viewport;
                   frames carry real compositor timestamps (VFR), then a
                   concat list + ffmpeg writes a sparse-VFR .mp4.
  screencapture  — macOS `screencapture -C -R<rect> -V<dur>` (original).
  x11grab        — ffmpeg -f x11grab on the window's viewport rect.

Usage:
  cdp_rec.py --url <u> --out <beat.mp4> --dur <secs>
             [--rec auto|screencast|screencapture|x11grab]
             [--size 1920x1080]        # emulated viewport (screencast)
             [--pre <secs>]           # settle time before recording
             [--pre-actions f.json]   # actions run BEFORE recording
             [--actions f.json]       # actions run DURING recording
             [--rect x,y,w,h]         # override viewport rect (screen recs)
             [--keep]                 # leave the tab open
             [--shot f.png]           # also grab a still at the end

Action DSL (JSON array):
  {"wait": s}                 — sleep
  {"eval": "js expr"}         — Runtime.evaluate (awaited)
  {"click_el": "#selector"}   — click element center (viewport coords)
  {"click_xy": [x, y]}        — click viewport coords
  {"click_geo": [lon, lat]}   — click a landing map cell by lon,lat
                                (page toX/toY projection over #raster)
  {"click_svg": [lon, lat]}   — click a /city SVG map point by lon,lat
                                (X()/Y() + svg.getScreenCTM)
  {"scroll_el": "#selector"}  — el.scrollIntoView({block:'center'})
  {"scroll": px}              — window.scrollBy
  {"type": "text"}            — Input.insertText into focused field
  {"key": "Enter"}            — raw key event
  {"set_tok": "admintoken"}   — sessionStorage.alive_admin_tok + reload

Requires: websockets (server/.venv/bin/python on Linux,
server/.venv312/bin/python on the macOS box).
"""
import asyncio, base64, json, os, platform, subprocess, sys, tempfile
import urllib.parse, urllib.request

CDP = "http://localhost:29229"


def http(path, method="GET"):
    req = urllib.request.Request(CDP + path, method=method)
    return json.load(urllib.request.urlopen(req, timeout=15))


class Tab:
    def __init__(self, url):
        self.tab = http("/json/new?" + urllib.parse.quote(url, safe=""),
                        method="PUT")
        self.tid = self.tab["id"]
        self.ws_url = self.tab["webSocketDebuggerUrl"]
        self.mid = 0
        self.pending = {}
        self.frames = []          # (ts, jpeg-bytes) screencast frames
        self.sc_session = None
        self._closed = False

    async def connect(self):
        import websockets
        self.ws = await websockets.connect(self.ws_url,
                                           max_size=256 * 1024 * 1024)
        self.reader = asyncio.get_event_loop().create_task(self._read())
        await self.send("Page.enable")
        await self.send("Runtime.enable")

    async def _read(self):
        try:
            while True:
                m = json.loads(await self.ws.recv())
                if m.get("method") == "Page.javascriptDialogOpening":
                    # auto-decline prompt() (admin gate) — a real 'cancel'
                    await self.ws.send(json.dumps({
                        "id": 90000 + self.mid,
                        "method": "Page.handleJavaScriptDialog",
                        "params": {"accept": False}}))
                    continue
                if m.get("method") == "Page.screencastFrame":
                    p = m["params"]
                    self.frames.append((p["metadata"]["timestamp"],
                                        base64.b64decode(p["data"])))
                    await self.ws.send(json.dumps({
                        "id": 500000 + len(self.frames),
                        "method": "Page.screencastFrameAck",
                        "params": {"sessionId": p["sessionId"]}}))
                    continue
                if "id" in m and m["id"] in self.pending:
                    self.pending.pop(m["id"]).set_result(m)
        except Exception:
            self._closed = True

    async def send(self, method, params=None):
        self.mid += 1
        fut = asyncio.get_event_loop().create_future()
        self.pending[self.mid] = fut
        await self.ws.send(json.dumps(
            {"id": self.mid, "method": method, "params": params or {}}))
        m = await fut
        return m.get("result", {})

    async def eval(self, expr):
        r = await self.send("Runtime.evaluate", {
            "expression": expr, "returnByValue": True,
            "awaitPromise": True})
        res = r.get("result", {})
        if res.get("subtype") == "error" or "exceptionDetails" in r:
            print("EVAL-ERR>", json.dumps(r)[:600])
        return res.get("value")

    async def click(self, x, y):
        await self.send("Input.dispatchMouseEvent", {
            "type": "mouseMoved", "x": float(x), "y": float(y)})
        await asyncio.sleep(0.35)
        for t in ("mousePressed", "mouseReleased"):
            await self.send("Input.dispatchMouseEvent", {
                "type": t, "x": float(x), "y": float(y),
                "button": "left", "clickCount": 1})

    async def viewport_rect(self):
        v = await self.eval(
            "JSON.stringify({x:screenX,y:screenY,ow:outerWidth,"
            "oh:outerHeight,iw:innerWidth,ih:innerHeight})")
        g = json.loads(v)
        return (int(g["x"]), int(g["y"] + (g["oh"] - g["ih"])),
                int(g["ow"]), int(g["ih"]))

    async def shot(self, path):
        d = await self.send("Page.captureScreenshot", {"format": "png"})
        with open(path, "wb") as f:
            f.write(base64.b64decode(d["data"]))

    def close(self):
        try:
            http("/json/close/" + self.tid, method="GET")
        except Exception:
            pass


async def run_actions(tab, actions):
    for a in actions:
        if "wait" in a:
            await asyncio.sleep(a["wait"])
        elif "eval" in a:
            print("EVAL>", json.dumps(await tab.eval(a["eval"]))[:500])
        elif "click_el" in a:
            r = await tab.eval(
                "(()=>{const e=document.querySelector(%s);"
                "if(!e)return null;const r=e.getBoundingClientRect();"
                "return JSON.stringify([r.left+r.width/2,r.top+r.height/2])"
                "})()" % json.dumps(a["click_el"]))
            if r:
                x, y = json.loads(r)
                await tab.click(x, y)
            else:
                print("MISS>", a["click_el"])
        elif "click_xy" in a:
            await tab.click(a["click_xy"][0], a["click_xy"][1])
        elif "click_geo" in a:
            lon, lat = a["click_geo"]
            r = await tab.eval(
                "(()=>{const c=document.getElementById('raster')||"
                "document.querySelector('canvas');if(!c)return null;"
                "const r=c.getBoundingClientRect();"
                "return JSON.stringify([r.left+toX(%f),r.top+toY(%f)])"
                "})()" % (lon, lat))
            if r:
                x, y = json.loads(r)
                await tab.click(x, y)
            else:
                print("MISS> click_geo", lon, lat)
        elif "click_svg" in a:
            # /city map: X(lon)/Y(lat) are SVG user units — convert to
            # client coords through the live CTM so the tap is real.
            lon, lat = a["click_svg"]
            r = await tab.eval(
                "(()=>{const s=document.getElementById('ncr')||"
                "document.querySelector('svg');"
                "if(!s||typeof X!=='function')return null;"
                "const ctm=s.getScreenCTM();if(!ctm)return null;"
                "const p=s.createSVGPoint();p.x=X(%f);p.y=Y(%f);"
                "const q=p.matrixTransform(ctm);"
                "return JSON.stringify([q.x,q.y])})()" % (lon, lat))
            if r:
                x, y = json.loads(r)
                await tab.click(x, y)
            else:
                print("MISS> click_svg", lon, lat)
        elif "scroll_el" in a:
            await tab.eval(
                "(()=>{const e=document.querySelector(%s);"
                "if(e)e.scrollIntoView({block:'center',behavior:'instant'});"
                "return !!e})()" % json.dumps(a["scroll_el"]))
            await asyncio.sleep(0.8)
        elif "scroll" in a:
            await tab.eval("window.scrollBy(0,%d)" % a["scroll"])
            await asyncio.sleep(0.7)
        elif "type" in a:
            await tab.send("Input.insertText", {"text": a["type"]})
            await asyncio.sleep(0.4)
        elif "key" in a:
            for t in ("keyDown", "keyUp"):
                await tab.send("Input.dispatchKeyEvent",
                               {"type": t, "key": a["key"]})
            await asyncio.sleep(0.5)
        elif "set_tok" in a:
            await tab.eval(
                "sessionStorage.setItem('alive_admin_tok',%s);"
                "location.reload();'reloading'"
                % json.dumps(a["set_tok"]))
            await asyncio.sleep(a.get("wait", 5))


def mux_screencast(frames, out, dur):
    """Write VFR frames (ts, jpeg) to an mp4 via the concat demuxer."""
    if not frames:
        print("WARN> screencast captured 0 frames")
        return False
    d = tempfile.mkdtemp(prefix="scast_")
    listf = os.path.join(d, "list.txt")
    t0 = frames[0][0]
    with open(listf, "w") as lf:
        lf.write("ffconcat version 1.0\n")
        for i, (ts, data) in enumerate(frames):
            fp = os.path.join(d, "f%05d.jpg" % i)
            with open(fp, "wb") as f:
                f.write(data)
            nxt = frames[i + 1][0] if i + 1 < len(frames) else t0 + dur
            gap = max(1.0 / 60.0, min(4.0, nxt - ts))
            lf.write("file '%s'\nduration %.4f\n" % (fp, gap))
        # concat demuxer needs the last file listed twice to hold it
        lf.write("file '%s'\nduration %.4f\n" % (fp, 0.5))
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
         "-i", listf, "-vsync", "vfr", "-c:v", "libx264",
         "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p", out],
        check=True)
    return True


async def main():
    args = sys.argv[1:]
    opt = {"pre": 5.0, "dur": 15.0, "rect": None, "keep": False,
           "shot": None, "pre_actions": [], "actions": [],
           "rec": "auto", "size": "1920x1080"}
    url = out = None
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--url":
            url = args[i + 1]; i += 2
        elif a == "--out":
            out = args[i + 1]; i += 2
        elif a in ("--dur", "--pre"):
            opt[a[2:]] = float(args[i + 1]); i += 2
        elif a == "--rect":
            opt["rect"] = [int(v) for v in args[i + 1].split(",")]; i += 2
        elif a == "--rec":
            opt["rec"] = args[i + 1]; i += 2
        elif a == "--size":
            opt["size"] = args[i + 1]; i += 2
        elif a == "--actions":
            opt["actions"] = json.load(open(args[i + 1])); i += 2
        elif a == "--pre-actions":
            opt["pre_actions"] = json.load(open(args[i + 1])); i += 2
        elif a == "--keep":
            opt["keep"] = True; i += 1
        elif a == "--shot":
            opt["shot"] = args[i + 1]; i += 2
        else:
            i += 1
    assert url and out, "need --url and --out"

    rec = opt["rec"]
    if rec == "auto":
        rec = "screencapture" if platform.system() == "Darwin" \
            else "screencast"

    tab = Tab("about:blank")
    await tab.connect()
    if rec == "screencast":
        w, h = (int(v) for v in opt["size"].split("x"))
        await tab.send("Emulation.setDeviceMetricsOverride",
                       {"width": w, "height": h, "deviceScaleFactor": 1,
                        "mobile": False})
    await tab.send("Page.navigate", {"url": url})
    await asyncio.sleep(opt["pre"])

    if opt["pre_actions"]:
        await run_actions(tab, opt["pre_actions"])

    if rec == "screencast":
        await tab.send("Page.startScreencast", {
            "format": "jpeg", "quality": 85,
            "maxWidth": int(opt["size"].split("x")[0]),
            "maxHeight": int(opt["size"].split("x")[1]),
            "everyNthFrame": 1})
        await asyncio.sleep(0.4)
        if opt["actions"]:
            await run_actions(tab, opt["actions"])
        else:
            await asyncio.sleep(opt["dur"])
        await tab.send("Page.stopScreencast")
        print("frames>", len(tab.frames))
        ok = mux_screencast(tab.frames, out, opt["dur"])
        if not ok:
            sys.exit(1)
    else:
        rect = opt["rect"] or await tab.viewport_rect()
        x, y, w, h = rect
        print("RECT>", x, y, w, h)
        try:
            os.remove(out)
        except OSError:
            pass
        if rec == "x11grab":
            proc = subprocess.Popen(
                ["ffmpeg", "-y", "-v", "error", "-f", "x11grab",
                 "-framerate", "30", "-video_size", "%dx%d" % (w, h),
                 "-i", ":0+%d,%d" % (x, y), "-t", "%.1f" % opt["dur"],
                 "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                 "-pix_fmt", "yuv420p", out])
        else:
            proc = subprocess.Popen(
                ["screencapture", "-C", "-R%d,%d,%d,%d" % tuple(rect),
                 "-V%.1f" % opt["dur"], out])
        await asyncio.sleep(0.6)          # recorder warm-up
        if opt["actions"]:
            await run_actions(tab, opt["actions"])
        try:
            proc.wait(timeout=opt["dur"] + 90)
        except subprocess.TimeoutExpired:
            proc.terminate()
            print("WARN> recorder killed after timeout")
    if opt["shot"]:
        await tab.shot(opt["shot"])
    if not opt["keep"]:
        tab.close()
    print("SAVED", out)


asyncio.run(main())
