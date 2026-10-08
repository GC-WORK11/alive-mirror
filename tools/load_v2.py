#!/usr/bin/env python3
"""ALive-108 bounded load probe — demo-day lane.

HARD BOUNDS (per the lane mandate):
  * <=8 concurrent virtual clients, bursts <=30 s, whole run <=5 min
  * GETs + POST /v2/plan only — never /v2/feedback, /observe, /v2/trip
  * every virtual client carries its own x-device-token (the server rate
    limiter buckets per token; one token = one judge's client)
  * any 5xx aborts the running phase (reported, not retried)

Usage: python3 tools/load_v2.py [baseline|mix|all] [outfile] [base]
"""
import asyncio
import json
import os
import sys
import time

import httpx

BASE = (sys.argv[3] if len(sys.argv) > 3 else
        "http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "server"))
from admin_mount import ADMIN_MOUNT
CP = (28.6315, 77.2167)
GGM = (28.4595, 77.0266)

GETS = {
    "day":      f"/v2/day?lat={CP[0]}&lon={CP[1]}",
    "outlook":  f"/v2/outlook?lat={CP[0]}&lon={CP[1]}",
    "reach_w50": f"/v2/reach?lat={CP[0]}&lon={CP[1]}&mode=walk&budget_ug=50",
    "reach_c100": f"/v2/reach?lat={CP[0]}&lon={CP[1]}&mode=car&budget_ug=100",
    "grid0":    "/grid?h=0",
    "aqi":      f"/aqi?lat={CP[0]}&lon={CP[1]}",
    "city":     "/city",
    "admin":    ADMIN_MOUNT,
}
PLAN_BODY = {"from": {"lat": CP[0], "lon": CP[1]},
             "to": {"lat": GGM[0], "lon": GGM[1]}}

TIMEOUT = httpx.Timeout(30.0, connect=10.0)
CLIENT_N = 8          # absolute concurrency ceiling
BURST_S = 25.0        # per-phase wall cap (<30s bound)
RUN_DEADLINE_S = 300.0

_t0 = time.monotonic()
_state = {"stop": False, "err5xx": []}


def _tok(i: int) -> str:
    return f"lane-load-{i:02d}"


async def _one(client: httpx.AsyncClient, name: str, spec,
               tok_i: int) -> dict:
    t = time.perf_counter()
    rec = {"ep": name, "ok": False, "ms": None, "st": None, "wire": 0}
    try:
        if spec == "plan":
            r = await client.post("/v2/plan", json=PLAN_BODY,
                                  headers={"x-device-token": _tok(tok_i)})
        else:
            r = await client.get(spec,
                                 headers={"x-device-token": _tok(tok_i)})
        rec["ms"] = round((time.perf_counter() - t) * 1000.0, 1)
        rec["st"] = r.status_code
        rec["wire"] = len(r.content)
        rec["ok"] = r.status_code == 200
        try:
            rec["took_ms"] = r.json().get("took_ms")
        except Exception:
            pass
        if r.status_code >= 500:
            _state["err5xx"].append((name, r.status_code))
            _state["stop"] = True
    except Exception as e:
        rec["ms"] = round((time.perf_counter() - t) * 1000.0, 1)
        rec["err"] = type(e).__name__
    return rec


async def _seq(client, name, spec, n):
    out = []
    for _ in range(n):
        if _state["stop"] or time.monotonic() - _t0 > RUN_DEADLINE_S:
            break
        out.append(await _one(client, name, spec, 0))
    return out


async def _worker(client, name, spec, tok_i, until, bag):
    while time.monotonic() < until and not _state["stop"]:
        if time.monotonic() - _t0 > RUN_DEADLINE_S:
            break
        bag.append(await _one(client, name, spec, tok_i))


def _pct(v, p):
    if not v:
        return None
    s = sorted(v)
    k = min(len(s) - 1, max(0, int(round((p / 100.0) * (len(s) - 1)))))
    return round(s[k], 1)


def _summ(recs):
    ms = [r["ms"] for r in recs if r["ok"]]
    errs = [r for r in recs if not r["ok"]]
    took = [r["took_ms"] for r in recs if r.get("took_ms")]
    d = {"n": len(recs), "n_ok": len(ms), "n_err": len(errs),
         "p50": _pct(ms, 50), "p95": _pct(ms, 95), "max": _pct(ms, 100),
         "err_kinds": sorted({r.get("err") or str(r.get("st"))
                              for r in errs})}
    if took:
        d["srv_p50"] = _pct(took, 50)
        d["srv_p95"] = _pct(took, 95)
    return d


async def main():
    phase = sys.argv[1] if len(sys.argv) > 1 else "all"
    results = {"base": BASE, "phases": {}}
    limits = httpx.Limits(max_connections=CLIENT_N,
                          max_keepalive_connections=CLIENT_N)
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT,
                                 limits=limits) as client:
        # warm + liveness
        for _ in range(3):
            r = await client.get("/health")
            print("health", r.status_code)
        if phase in ("baseline", "all"):
            print("\n=== PHASE baseline (sequential) ===")
            order = [("day", GETS["day"], 20),
                     ("outlook", GETS["outlook"], 20),
                     ("reach_w50", GETS["reach_w50"], 15),
                     ("reach_c100", GETS["reach_c100"], 12),
                     ("plan", "plan", 15),
                     ("grid0", GETS["grid0"], 20),
                     ("aqi", GETS["aqi"], 20),
                     ("city", GETS["city"], 12),
                     ("admin", GETS["admin"], 12)]
            for name, spec, n in order:
                recs = await _seq(client, name, spec, n)
                results["phases"][f"seq_{name}"] = _summ(recs)
                print(f"seq {name:12s} {_summ(recs)}")
                if _state["stop"]:
                    break
        if phase in ("mix", "all") and not _state["stop"]:
            print("\n=== PHASE mixes (<=8 concurrent, <=25s) ===")
            mixes = {
                "mix_day_outlook":  [("day", GETS["day"])] * 4
                                    + [("outlook", GETS["outlook"])] * 4,
                "mix_reach_plan":   [("reach_w50", GETS["reach_w50"])] * 4
                                    + [("plan", "plan")] * 4,
                "mix_grid_day":     [("grid0", GETS["grid0"])] * 4
                                    + [("day", GETS["day"])] * 4,
                "mix_starve":       [("reach_c100", GETS["reach_c100"])] * 2
                                    + [("day", GETS["day"])] * 4
                                    + [("outlook", GETS["outlook"])] * 2,
            }
            for mname, spec_list in mixes.items():
                if _state["stop"]:
                    break
                until = time.monotonic() + BURST_S
                bag = []
                await asyncio.gather(*[
                    _worker(client, name, spec, i, until, bag)
                    for i, (name, spec) in enumerate(spec_list)])
                per = {}
                for name in {n for n, _ in spec_list}:
                    sub = [r for r in bag if r["ep"] == name]
                    per[name] = _summ(sub)
                results["phases"][mname] = per
                print(mname, json.dumps(per))
                if _state["err5xx"]:
                    print("5xx seen:", _state["err5xx"])
                    break
    results["elapsed_s"] = round(time.monotonic() - _t0, 1)
    results["err5xx"] = _state["err5xx"]
    print("\n" + json.dumps(results, indent=1))
    out = (sys.argv[2] if len(sys.argv) > 2 and not
           sys.argv[2].startswith("http") else "/tmp/load_v2_out.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=1)


if __name__ == "__main__":
    asyncio.run(main())
