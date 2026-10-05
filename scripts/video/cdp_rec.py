#!/usr/bin/env python3
"""Record one browser beat of the live ALive-108 product to .mov.

Drives the already-running Chrome over CDP (localhost:29229), computes
the page viewport's screen rect, and records exactly that rect with
`screencapture -C -R x,y,w,h -V<dur>` while a JSON action list runs —
so every frame on tape is real page pixels of the live service.

Usage:
  cdp_rec.py --url <u> --out <beat.mov> --dur <secs>
             [--pre <secs>]          # settle time before recording
             [--pre-actions f.json]  # actions run BEFORE recording
             [--actions f.json]      # actions run DURING recording
             [--rect x,y,w,h]        # override viewport rect
             [--keep]                # leave the tab open
             [--shot f.png]          # also grab a still at the end

Action DSL (JSON array):
  {"wait": s}                 — sleep
  {"eval": "js expr"}         — Runtime.evaluate (awaited)
  {"click_el": "#selector"}   — click element center (viewport coords)
  {"click_xy": [x, y]}        — click viewport coords
  {"click_geo": [lon, lat]}   — click a landing/city map cell by lon,lat
                                (uses the page's own toX/toY projection)
  {"scroll_el": "#selector"}  — el.scrollIntoView({block:'center'})
  {"scroll": px}              — window.scrollBy
  {"type": "text"}            — Input.insertText into focused field
  {"key": "Enter"}            — raw key event
  {"set_tok": "admintoken"}   — sessionStorage.alive_admin_tok + reload

Requires: websockets (server/.venv312/bin/python).
"""
import asyncio, base64, json, os, subprocess, sys, time
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

    async def connect(self):
        import websockets
        self.ws = await websockets.connect(self.ws_url,
                                           max_size=64 * 1024 * 1024)
        self.reader = asyncio.get_event_loop().create_task(self._read())
        await self.send("Page.enable")
        await self.send("Runtime.enable")

    async def _read(self):
        while True:
            m = json.loads(await self.ws.recv())
            if m.get("method") == "Page.javascriptDialogOpening":
                # auto-decline prompt() (admin gate) — a real 'cancel'
                await self.ws.send(json.dumps({
                    "id": 90000 + self.mid,
                    "method": "Page.handleJavaScriptDialog",
                    "params": {"accept": False}}))
                continue
            if "id" in m and m["id"] in self.pending:
                self.pending.pop(m["id"]).set_result(m)

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


async def main():
    args = sys.argv[1:]
    opt = {"pre": 5.0, "dur": 15.0, "rect": None, "keep": False,
           "shot": None, "pre_actions": [], "actions": []}
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

    tab = Tab(url)
    await tab.connect()
    await asyncio.sleep(opt["pre"])

    if opt["pre_actions"]:
        await run_actions(tab, opt["pre_actions"])

    rect = opt["rect"] or await tab.viewport_rect()
    x, y, w, h = rect
    print("RECT>", x, y, w, h)

    try:
        os.remove(out)          # screencapture refuses to overwrite
    except OSError:
        pass
    proc = subprocess.Popen(
        ["screencapture", "-C", "-R%d,%d,%d,%d" % rect,
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
