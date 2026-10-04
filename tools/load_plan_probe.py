#!/usr/bin/env python3
"""Concurrency probe for /v2/plan — mimics the app's fast+full pattern.

Fires N concurrent pairs of {fast:true, full} plan calls for the same
OD and reports per-call server took_ms, option counts, engine-row
counts and errors. Also a second OD in parallel to cross-check.

    python3 tools/load_plan_probe.py [API_BASE] [N_PAIRS]
"""
import json
import sys
import threading
import time
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else
        "http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com")
N = int(sys.argv[2]) if len(sys.argv) > 2 else 4

OD = ((28.4595, 77.0266), (28.6712, 77.2935))      # Ggn29 -> Shahdara
OD2 = ((28.6315, 77.2167), (28.5479, 77.2511))    # CP -> NehruPlace


def post(body):
    req = urllib.request.Request(
        BASE + "/v2/plan", data=json.dumps(body).encode(),
        headers={"content-type": "application/json"}, method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return time.time() - t0, json.load(r)
    except Exception as e:
        return time.time() - t0, {"error": repr(e)}


def run(tag, a, b, fast):
    wall, r = post({"from": {"lat": a[0], "lon": a[1]},
                    "to": {"lat": b[0], "lon": b[1]},
                    "vehicle": "car", "fast": fast})
    opts = r.get("options") or []
    eng = sum(1 for o in opts if o.get("engine") == "alive_core-path")
    print(f"{tag:12s} fast={str(fast):5s} wall={wall:5.1f}s "
          f"took_ms={r.get('took_ms', 0):7.0f} opts={len(opts):2d} "
          f"eng={eng:2d} err={r.get('error')}", flush=True)


def pair(i, od):
    a, b = od
    run(f"pair{i}-fast", a, b, True)
    run(f"pair{i}-full", a, b, False)


threads = []
for i in range(N):
    threads.append(threading.Thread(target=pair, args=(i, OD)))
threads.append(threading.Thread(target=pair, args=("X", OD2)))
t0 = time.time()
for t in threads:
    t.start()
for t in threads:
    t.join()
print(f"all done in {time.time() - t0:.1f}s wall")
