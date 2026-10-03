#!/usr/bin/env python3
"""Benchmark — T1 search index, C++ alive_core vs Python reference.

Protocol per docs/plan/08: fixed corpus (the real 26.5k-place Delhi
gazetteer), 10k recorded-style queries (prefixes of real place names +
injected typos), per-query p50/p95/p99, index build time, RSS.

Each implementation is benched in a fresh subprocess so the RSS deltas are
not polluted by the other index's allocator state:

    PYTHONPATH=server:server/core/build python3 server/core/bench/bench_search.py
    PYTHONPATH=server:server/core/build python3 server/core/bench/bench_search.py 2000
"""

import json
import os
import random
import resource
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_SERVER = os.path.dirname(os.path.dirname(_HERE))
for _p in (_SERVER, os.path.join(_SERVER, "core", "build")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import alive_core_ref as ref  # noqa: E402

BIAS = (28.6139, 77.2090)
N_DEFAULT = 10_000
LIMIT = 10


def vmrss_mb() -> float:
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith("VmRSS"):
                return int(line.split()[1]) / 1024.0
    return 0.0


def typo(tok: str, rng: random.Random) -> str:
    op = rng.randrange(4)
    i = rng.randrange(len(tok))
    if op == 0:
        return tok[:i] + rng.choice("abcdefghijklmnopqrstuvwxyz") + tok[i + 1:]
    if op == 1:
        return tok[:i] + tok[i + 1:]
    if op == 2 and len(tok) > 2:
        i = rng.randrange(len(tok) - 1)
        return tok[:i] + tok[i + 1] + tok[i] + tok[i + 2:]
    return tok[:i] + rng.choice("abcdefghijklmnopqrstuvwxyz") + tok[i:]


def gen_queries(entries, n: int, seed: int = 108) -> list[str]:
    """Recorded-style: prefixes of real names, injected typos, multi-token."""
    rng = random.Random(seed)
    usable = [e for e in entries if ref.normalize(e["display"])]
    out = []
    while len(out) < n:
        e = rng.choice(usable)
        toks = ref.normalize(e["display"])
        kind = rng.randrange(10)
        if kind < 4:
            t = rng.choice(toks)
            out.append(t[: rng.randint(3, len(t))] if len(t) >= 3 else t)
        elif kind < 7:
            cand = [t for t in toks if len(t) >= 5]
            if not cand:
                continue
            out.append(typo(rng.choice(cand), rng))
        elif kind < 9:
            if len(toks) < 2:
                continue
            t2 = rng.choice(toks[1:])
            if len(t2) >= 5 and rng.random() < 0.5:
                t2 = typo(t2, rng)
            else:
                t2 = t2[: rng.randint(2, len(t2))] if len(t2) >= 2 else t2
            out.append(f"{toks[0]} {t2}")
        else:
            out.append(" ".join(toks))
    return out


def pct(sorted_vals, q):
    return sorted_vals[min(len(sorted_vals) - 1, int(q * len(sorted_vals)))]


def bench_worker(impl: str, n: int) -> dict:
    """Build + bench one index in this (fresh) process; return metrics."""
    entries = ref.entries_from_gazetteer()
    aliases = ref.load_aliases()
    queries = gen_queries(entries, n)

    if impl == "cpp":
        import alive_core
        build = lambda: alive_core.SearchIndex(  # noqa: E731
            entries, aliases, ref.W_PREFIX, ref.W_COVERAGE,
            ref.W_POPULARITY, ref.W_DISTANCE)
    else:
        build = lambda: ref.PySearchIndex(  # noqa: E731
            entries, aliases, ref.W_PREFIX, ref.W_COVERAGE,
            ref.W_POPULARITY, ref.W_DISTANCE)

    rss0 = vmrss_mb()
    t0 = time.perf_counter()
    idx = build()
    build_ms = (time.perf_counter() - t0) * 1e3
    rss1 = vmrss_mb()

    for q in queries[:500]:
        idx.query(q, *BIAS, LIMIT)

    lat = []
    for q in queries:
        t0 = time.perf_counter_ns()
        idx.query(q, *BIAS, LIMIT)
        lat.append((time.perf_counter_ns() - t0) / 1e3)
    lat.sort()
    peak_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    return {
        "impl": impl,
        "build_ms": round(build_ms, 1),
        "rss_delta_mb": round(rss1 - rss0, 1),
        "peak_rss_mb": round(peak_mb, 1),
        "p50_us": round(pct(lat, .50), 1),
        "p95_us": round(pct(lat, .95), 1),
        "p99_us": round(pct(lat, .99), 1),
    }


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else N_DEFAULT
    entries = ref.entries_from_gazetteer()
    print(f"corpus: {len(entries)} entries | queries: {n} (seed 108) "
          f"| bias {BIAS} | limit {LIMIT}")

    env = dict(os.environ)
    pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(
        [_SERVER, os.path.join(_SERVER, "core", "build"), pp])

    rows = {}
    for impl in (["cpp"] if ref.HAVE_CPP else []) + ["py"]:
        out = subprocess.run(
            [sys.executable, os.path.abspath(__file__), "--worker", impl,
             str(n)],
            capture_output=True, text=True, env=env, check=True)
        r = json.loads(out.stdout.strip().splitlines()[-1])
        rows[impl] = r
        name = "C++ alive_core" if impl == "cpp" else "Python ref"
        print(f"{name:14} build {r['build_ms']:8.1f} ms  "
              f"rss +{r['rss_delta_mb']:6.1f} MB  peak {r['peak_rss_mb']:6.1f} MB"
              f"  p50 {r['p50_us']:8.1f} us  p95 {r['p95_us']:8.1f} us  "
              f"p99 {r['p99_us']:8.1f} us")

    if "cpp" in rows:
        print(f"\nspeedup p50: {rows['py']['p50_us']/rows['cpp']['p50_us']:.1f}x "
              f"p95: {rows['py']['p95_us']/rows['cpp']['p95_us']:.1f}x "
              f"p99: {rows['py']['p99_us']/rows['cpp']['p99_us']:.1f}x")
    print("\nJSON:", json.dumps(rows))


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--worker":
        print(json.dumps(bench_worker(sys.argv[2], int(sys.argv[3]))))
    else:
        main()
