"""Lane probe — warm-cycle + per-request RSS on the real dev server.

Usage:
  ALIVE_RATE_LIMIT=0 .venv312/bin/python -m uvicorn main:app --port 8099 &
  PYTHONPATH=core/build312:. .venv312/bin/python tools/lane_req_rss.py <pid>
"""
import json
import sys
import time
import urllib.request

import psutil

BASE = "http://127.0.0.1:8099"


def get(path, timeout=120):
    t = time.time()
    try:
        with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
            body = r.read()
            return r.status, len(body), time.time() - t
    except Exception as e:
        return getattr(e, "code", 0), 0, time.time() - t


def post(path, payload, timeout=120):
    t = time.time()
    try:
        req = urllib.request.Request(
            BASE + path, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            return r.status, len(body), time.time() - t
    except Exception as e:
        return getattr(e, "code", 0), 0, time.time() - t


def rss(p):
    return p.memory_info().rss / 1e6


def main():
    proc = psutil.Process(int(sys.argv[1]))
    print(f"pid {proc.pid}  rss now {rss(proc):.0f} MB", flush=True)

    # wait for the app to finish warming (NLB grace ~150 s; warm fleet
    # takes ~2-4 min locally: graph load + 5-mode solve warm)
    print("waiting for warm: polling /aqi until field ready...", flush=True)
    for i in range(90):
        code, n, dt = get("/aqi?lat=28.61&lon=77.21")
        if code == 200:
            try:
                with urllib.request.urlopen(
                        BASE + "/health", timeout=10) as r:
                    h = json.loads(r.read())
                if h.get("engine_warm") or i > 30:
                    break
            except Exception:
                pass
        time.sleep(5)
    print(f"warm-ish  rss {rss(proc):.0f} MB", flush=True)

    matrix = [
        ("/aqi?lat=28.61&lon=77.21", "GET"),
        ("/v2/city", "GET"),
        ("/grid", "GET"),
        ("/v2/search?q=connaught+place&lat=28.61&lon=77.21", "GET"),
        ("/v2/day?lat=28.61&lon=77.21", "GET"),
        ("/depart?from=28.61,77.21&to=28.65,77.19&kind=fastest", "GET"),
        ("/v2/reach?lat=28.61&lon=77.21&mode=car&minutes=20", "GET"),
    ]
    plan_body = {"from": {"lat": 28.6139, "lon": 77.2090},
                 "to": {"lat": 28.5355, "lon": 77.3910},
                 "when": "now", "modes": ["auto"]}

    for path, _ in matrix:
        r0 = rss(proc)
        code, n, dt = get(path)
        r1 = rss(proc)
        print(f"{path:70s} {code} {n:>8}B {dt:6.1f}s "
              f"rss {r0:7.0f} -> {r1:7.0f} ({r1 - r0:+.0f})", flush=True)

    # /v2/plan is POST
    for i in range(3):
        r0 = rss(proc)
        code, n, dt = post("/v2/plan", plan_body)
        r1 = rss(proc)
        print(f"POST /v2/plan #{i}                                          "
              f"{code} {n:>8}B {dt:6.1f}s rss {r0:7.0f} -> {r1:7.0f} "
              f"({r1 - r0:+.0f})", flush=True)

    # sustained loop — leak check: RSS should plateau, not climb
    print("leak check: 24x mixed loop", flush=True)
    r_start = rss(proc)
    for i in range(8):
        get("/aqi?lat=28.61&lon=77.21")
        get("/grid")
        post("/v2/plan", plan_body)
        print(f"  round {i}: rss {rss(proc):.0f} MB", flush=True)
    r_end = rss(proc)
    print(f"leak check delta over 8 rounds: {r_end - r_start:+.0f} MB",
          flush=True)


if __name__ == "__main__":
    main()
