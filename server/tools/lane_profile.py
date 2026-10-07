#!/usr/bin/env python3
"""Sequential-request timing harness for the server-harden lane.

Times /aqi, /v2/city, /v2/plan (full + fast) with N sequential requests
each against a locally running server; prints per-request ms + p50/p95
so the slowest quintile is visible, not averaged away.
"""
import json
import statistics
import sys
import time
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8014"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 20

# Connaught Place -> Cyber City Gurugram: a real NCR commute OD.
LAT1, LON1 = 28.6315, 77.2167
LAT2, LON2 = 28.4593, 77.0724

CALLS = {
    "aqi": ("GET", f"/aqi?lat={LAT1}&lon={LON1}", None),
    "city": ("GET", "/v2/city", None),
    "plan": ("POST", "/v2/plan", {
        "from": {"lat": LAT1, "lon": LON1},
        "to": {"lat": LAT2, "lon": LON2},
        "vehicle": "car"}),
    "plan_fast": ("POST", "/v2/plan", {
        "from": {"lat": LAT1, "lon": LON1},
        "to": {"lat": LAT2, "lon": LON2},
        "vehicle": "car", "fast": True}),
}


def one(method, path, body):
    t0 = time.perf_counter()
    if body is None:
        req = urllib.request.Request(BASE + path)
    else:
        req = urllib.request.Request(
            BASE + path, data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            payload = r.read()
            took_server = None
            try:
                took_server = json.loads(payload).get("took_ms")
            except Exception:
                pass
            return (time.perf_counter() - t0) * 1000.0, took_server, len(payload)
    except Exception as e:
        return (time.perf_counter() - t0) * 1000.0, f"ERR {e}", -1


def run(name):
    method, path, body = CALLS[name]
    wall, srv, sizes = [], [], []
    for _ in range(N):
        ms, took, sz = one(method, path, body)
        wall.append(ms)
        srv.append(took)
        sizes.append(sz)
    w = sorted(wall)
    s = sorted(x for x in srv if isinstance(x, (int, float)))
    print(f"\n=== {name} ({method} {path}) n={N} bytes~{max(sizes)}")
    print("  wall ms : " + " ".join(f"{x:.0f}" for x in wall))
    print(f"  wall    : p50={w[len(w)//2]:.0f} p80={w[int(len(w)*0.8)]:.0f} "
          f"max={w[-1]:.0f} mean={statistics.fmean(w):.0f}")
    if s:
        print(f"  took_ms : p50={s[len(s)//2]:.0f} p80={s[int(len(s)*0.8)]:.0f} "
              f"max={s[-1]:.0f}")


if __name__ == "__main__":
    which = sys.argv[3].split(",") if len(sys.argv) > 3 else list(CALLS)
    for name in which:
        run(name)
