#!/usr/bin/env python3
"""CDP screenshot/eval helper for the running Chrome (localhost:29229).

Usage:
  python cdp_shot.py <url> <out.png> [--w 375] [--h 700] [--wait 4]
                     [--eval 'js expr'] [--scroll y] [--click x,y]
                     [--key Enter] [--dpr 2] [--mobile]

Opens a NEW tab in the user's Chrome, navigates, optionally emulates a
device viewport, runs evals / clicks / keys, then screenshots the
viewport. The tab is left open or closed with --close.
"""
import asyncio, base64, json, sys, urllib.request

CDP = "http://localhost:29229"


def http(path):
    return json.load(urllib.request.urlopen(CDP + path, timeout=10))


async def main():
    import websockets
    args = sys.argv[1:]
    url, out = args[0], args[1]
    opt = {"w": 1024, "h": 768, "wait": 3.0, "dpr": 1, "mobile": False,
           "close": True, "fullpage": False}
    evals, clicks, keys, scrolls, types = [], [], [], [], []
    i = 2
    while i < len(args):
        a = args[i]
        if a in ("--w", "--h", "--dpr"):
            opt[a[2:]] = int(args[i + 1]); i += 2
        elif a == "--wait":
            opt["wait"] = float(args[i + 1]); i += 2
        elif a == "--mobile":
            opt["mobile"] = True; i += 1
        elif a == "--fullpage":
            opt["fullpage"] = True; i += 1
        elif a == "--keep":
            opt["close"] = False; i += 1
        elif a == "--eval":
            evals.append(args[i + 1]); i += 2
        elif a == "--type":
            types.append(args[i + 1]); i += 2
        elif a == "--click":
            clicks.append(tuple(float(v) for v in args[i + 1].split(","))); i += 2
        elif a == "--key":
            keys.append(args[i + 1]); i += 2
        elif a == "--scroll":
            scrolls.append(int(args[i + 1])); i += 2
        else:
            i += 1

    # new tab
    tab = json.load(urllib.request.urlopen(
        urllib.request.Request(CDP + "/json/new?" + url, method="PUT"),
        timeout=10))
    ws_url = tab["webSocketDebuggerUrl"]
    tid = tab["id"]

    mid = 0
    pending = {}

    async def send(ws, method, params=None):
        nonlocal mid
        mid += 1
        fut = asyncio.get_event_loop().create_future()
        pending[mid] = fut
        await ws.send(json.dumps({"id": mid, "method": method,
                                  "params": params or {}}))
        m = await fut
        return m.get("result", {})

    try:
        async with websockets.connect(ws_url, max_size=64 * 1024 * 1024) as ws:
            async def reader():
                while True:
                    m = json.loads(await ws.recv())
                    # prompt()/alert() would block the page forever under
                    # automation — auto-cancel (matches 'declined' paths)
                    if m.get("method") == "Page.javascriptDialogOpening":
                        await ws.send(json.dumps({
                            "id": 90000, "method":
                                "Page.handleJavaScriptDialog",
                            "params": {"accept": False}}))
                        continue
                    if "id" in m and m["id"] in pending:
                        pending.pop(m["id"]).set_result(m)
            rt = asyncio.get_event_loop().create_task(reader())
            await send(ws, "Page.enable")
            await send(ws, "Runtime.enable")
            if opt["w"] != 1024 or opt["h"] != 768 or opt["mobile"]:
                await send(ws, "Emulation.setDeviceMetricsOverride",
                           {"width": opt["w"], "height": opt["h"],
                            "deviceScaleFactor": opt["dpr"],
                            "mobile": opt["mobile"]})
                await send(ws, "Page.reload")
            await asyncio.sleep(opt["wait"])
            for s in scrolls:
                await send(ws, "Runtime.evaluate", {
                    "expression": f"window.scrollTo(0,{s})"})
                await asyncio.sleep(0.7)
            for (cx, cy) in clicks:
                for t in ("mousePressed", "mouseReleased"):
                    await send(ws, "Input.dispatchMouseEvent", {
                        "type": t, "x": cx, "y": cy,
                        "button": "left", "clickCount": 1})
                await asyncio.sleep(0.9)
            for k in keys:
                await send(ws, "Input.dispatchKeyEvent", {
                    "type": "keyDown", "key": k})
                await send(ws, "Input.dispatchKeyEvent", {
                    "type": "keyUp", "key": k})
                await asyncio.sleep(0.6)
            for t in types:
                await send(ws, "Input.insertText", {"text": t})
                await asyncio.sleep(0.4)
            for e in evals:
                r = await send(ws, "Runtime.evaluate", {
                    "expression": e, "returnByValue": True,
                    "awaitPromise": True})
                res = r.get("result", {})
                print("EVAL>", json.dumps(res.get("value"))[:1200])
                if res.get("subtype") == "error" or "exceptionDetails" in r:
                    print("ERR>", json.dumps(r)[:1200])
            cap = {"format": "png"}
            if opt["fullpage"]:
                m = await send(ws, "Page.getLayoutMetrics")
                h = int(m["cssContentSize"]["height"])
                await send(ws, "Emulation.setDeviceMetricsOverride",
                           {"width": opt["w"], "height": min(h, 12000),
                            "deviceScaleFactor": opt["dpr"],
                            "mobile": opt["mobile"]})
                await asyncio.sleep(0.5)
            shot = await send(ws, "Page.captureScreenshot", cap)
            with open(out, "wb") as f:
                f.write(base64.b64decode(shot["data"]))
            print("SAVED", out)
    finally:
        if opt["close"]:
            urllib.request.urlopen(
                urllib.request.Request(CDP + "/json/close/" + tid),
                timeout=5).read()


asyncio.run(main())
