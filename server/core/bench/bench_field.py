#!/usr/bin/env python3
"""Benchmark — field lookups + dose integration, C++ alive_core vs Python ref.

Protocol per docs/plan/08 (field/dose section):
  - real snapshot: newest file under server/data/field/snapshots/
  - field: 100k random lookups (80% inside the NCR bbox, 20% outside)
  - dose: 1k generated NCR routes, per-call p50/p95/p99, all modes
Each implementation is benched in a fresh subprocess.

    PYTHONPATH=server:server/core/build python3 server/core/bench/bench_field.py
"""
import glob
import gzip
import json
import os
import random
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_SERVER = os.path.dirname(os.path.dirname(_HERE))
for _p in (_SERVER, os.path.join(_SERVER, "core", "build")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import alive_core_ref as ref  # noqa: E402
import exposure  # noqa: E402

BBOX = (76.75, 28.15, 77.95, 28.98)  # lon_min, lat_min, lon_max, lat_max
N_LOOKUPS = 100_000
N_ROUTES = 1_000
MODES = ["metro", "driving_car_ac", "driving_car_open", "bus",
         "driving_two_wheeler", "auto_rickshaw", "cycling", "walking"]


def latest_snapshot() -> dict:
    files = sorted(glob.glob(os.path.join(
        _SERVER, "data", "field", "snapshots", "**", "*.json.gz"),
        recursive=True))
    with gzip.open(files[-1], "rt", encoding="utf-8") as f:
        return json.load(f)


def gen_points(n, seed=108):
    rng = random.Random(seed)
    w, s, e, nn = BBOX
    pts = []
    for _ in range(n):
        if rng.random() < 0.2:  # outside-ish: coverage fallback path
            lat = s - 0.15 + rng.random() * (nn - s + 0.30)
            lon = w - 0.15 + rng.random() * (e - w + 0.30)
        else:
            lat = s + rng.random() * (nn - s)
            lon = w + rng.random() * (e - w)
        pts.append((lat, lon))
    return pts


def gen_routes(n, seed=42):
    rng = random.Random(seed)
    w, s, e, nn = BBOX
    out = []
    for _ in range(n):
        lon1 = w + rng.random() * (e - w)
        lat1 = s + rng.random() * (nn - s)
        lon2 = w + rng.random() * (e - w)
        lat2 = s + rng.random() * (nn - s)
        k = rng.randint(5, 60)
        coords = [[lon1 + (lon2 - lon1) * i / k + rng.gauss(0, 0.003),
                   lat1 + (lat2 - lat1) * i / k + rng.gauss(0, 0.003)]
                  for i in range(k + 1)]
        dur = rng.uniform(300, 3600)
        me = exposure.MICROENV[rng.choice(MODES)]
        ve = exposure.VENTILATION_LPM[rng.choice(MODES)] / 1000.0
        out.append((coords, me, ve, dur))
    return out


def pct(sorted_vals, q):
    return sorted_vals[min(len(sorted_vals) - 1, int(q * len(sorted_vals)))]


def bench_worker(impl: str) -> dict:
    rows = ref.field_rows(latest_snapshot())
    pts = gen_points(N_LOOKUPS)
    routes = gen_routes(N_ROUTES)

    if impl == "cpp":
        import alive_core
        fv = alive_core.FieldView(rows)
        dose = alive_core.integrate_dose
    else:
        fv = ref.PyFieldView(rows)
        dose = ref.integrate_dose

    t0 = time.perf_counter()
    hits = 0
    for lat, lon in pts:
        if fv.value(lat, lon) is not None:
            hits += 1
    lookup_s = time.perf_counter() - t0

    for c, me, ve, d in routes[:50]:
        dose(c, fv, me, ve, d)
    lat_us = []
    for c, me, ve, d in routes:
        t0 = time.perf_counter_ns()
        dose(c, fv, me, ve, d)
        lat_us.append((time.perf_counter_ns() - t0) / 1e3)
    lat_us.sort()
    return {
        "impl": impl,
        "n_cells": len(rows),
        "lookups": N_LOOKUPS,
        "lookup_hits": hits,
        "lookups_per_s": round(N_LOOKUPS / lookup_s),
        "dose_routes": N_ROUTES,
        "dose_p50_us": round(pct(lat_us, .50), 1),
        "dose_p95_us": round(pct(lat_us, .95), 1),
        "dose_p99_us": round(pct(lat_us, .99), 1),
    }


def main():
    env = dict(os.environ)
    pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(
        [_SERVER, os.path.join(_SERVER, "core", "build"), pp])

    rows = {}
    for impl in (["cpp"] if ref.HAVE_CPP else []) + ["py"]:
        out = subprocess.run(
            [sys.executable, os.path.abspath(__file__), "--worker", impl],
            capture_output=True, text=True, env=env, check=True)
        r = json.loads(out.stdout.strip().splitlines()[-1])
        rows[impl] = r
        name = "C++ alive_core" if impl == "cpp" else "Python ref"
        print(f"{name:14} cells {r['n_cells']:6}  "
              f"lookup {r['lookups_per_s']:>10,}/s "
              f"(hits {r['lookup_hits']}/{r['lookups']})  "
              f"dose p50 {r['dose_p50_us']:9.1f} us  "
              f"p95 {r['dose_p95_us']:9.1f} us  p99 {r['dose_p99_us']:9.1f} us")

    if "cpp" in rows:
        print(f"\nspeedup: lookup {rows['py']['lookups_per_s'] and rows['cpp']['lookups_per_s']/rows['py']['lookups_per_s']:.1f}x "
              f"dose p50 {rows['py']['dose_p50_us']/rows['cpp']['dose_p50_us']:.1f}x "
              f"p99 {rows['py']['dose_p99_us']/rows['cpp']['dose_p99_us']:.1f}x")
    print("\nJSON:", json.dumps(rows))


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--worker":
        print(json.dumps(bench_worker(sys.argv[2])))
    else:
        main()
