#!/usr/bin/env python3
"""Real-world coverage probe battery (leg 4).

Runs tools/probe_battery.json against either the local search engine
(--local, offline pre-screen) or the live service (--live URL, e.g. the
NLB) and classifies each query: top1 / top3 / wrong / empty.

Usage:
    cd server && PYTHONPATH=core/build312:. ../tools/corpus-venv/bin/python \\
        ../tools/probe_battery.py --local --out /tmp/probe_local.json
    python3 tools/probe_battery.py --live http://host --out /tmp/probe_live.json \\
        --spacing 0.4 --limit 5

A hit counts when any `want` substring appears in the normalized
name+subtitle+kind+anchor of the row. `empty` means zero rows.
"""
import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request

_NORM = re.compile(r"[^a-z0-9 ]+")


def norm(s: str) -> str:
    return _NORM.sub(" ", (s or "").lower()).strip()


def blob(row: dict) -> str:
    parts = [row.get("name") or row.get("display") or "",
             row.get("subtitle") or "",
             row.get("kind") or row.get("category") or "",
             row.get("anchor") or ""]
    return norm(" ".join(str(p) for p in parts))


def classify(want, hits):
    if not hits:
        return "empty", -1
    wants = [norm(w) for w in want]
    for i, h in enumerate(hits[:3]):
        b = blob(h)
        if any(w and w in b for w in wants):
            return ("top1" if i == 0 else "top3"), i
    return "wrong", -1


def run_local(queries, limit):
    sys.path.insert(0, ".")
    import core_engine
    out = []
    for p in queries:
        t0 = time.time()
        hits = core_engine.search(p["q"], limit=limit) or []
        dt = (time.time() - t0) * 1000
        verdict, _ = classify(p.get("want", []), hits)
        out.append({"q": p["q"], "cat": p["cat"], "verdict": verdict,
                    "ms": round(dt, 2),
                    "hits": [{"name": h.get("display"),
                              "kind": h.get("category"),
                              "anchor": h.get("anchor"),
                              "compound": h.get("compound"),
                              "fuzzy": h.get("fuzzy"),
                              "score": round(h.get("score") or 0, 3)}
                             for h in hits[:5]]})
    return out


def run_live(queries, base, spacing, limit):
    out = []
    for i, p in enumerate(queries):
        url = (base.rstrip("/") + "/v2/search?q=" +
               urllib.parse.quote(p["q"]) + f"&limit={limit}")
        t0 = time.time()
        hits, err = [], None
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                data = json.loads(r.read().decode())
            hits = data.get("results") or data.get("places") or data
            if isinstance(hits, dict):
                hits = hits.get("results", [])
        except Exception as e:  # noqa: BLE001 — audit tool, record and move on
            err = str(e)
        dt = (time.time() - t0) * 1000
        verdict, _ = classify(p.get("want", []), hits)
        rows = []
        for h in hits[:5]:
            if isinstance(h, dict):
                rows.append({"name": h.get("name") or h.get("display"),
                             "kind": h.get("kind") or h.get("category"),
                             "anchor": h.get("anchor"),
                             "compound": h.get("compound"),
                             "fuzzy": h.get("fuzzy"),
                             "subtitle": h.get("subtitle"),
                             "source": h.get("source")})
        rec = {"q": p["q"], "cat": p["cat"], "verdict": verdict,
               "ms": round(dt, 2), "hits": rows}
        if err:
            rec["error"] = err
            rec["verdict"] = "error"
        out.append(rec)
        done = verdict[:4].upper()
        print(f"[{i + 1:3}/{len(queries)}] {done:6} {p['q']!r:44} "
              f"{rec['hits'][0]['name'] if rec['hits'] else '—'}", flush=True)
        if i + 1 < len(queries):
            time.sleep(spacing)
    return out


def summarize(records):
    cats, tot = {}, {"top1": 0, "top3": 0, "wrong": 0, "empty": 0, "error": 0}
    lat = []
    for r in records:
        v = r["verdict"]
        tot[v] = tot.get(v, 0) + 1
        cats.setdefault(r["cat"], {})
        cats[r["cat"]][v] = cats[r["cat"]].get(v, 0) + 1
        lat.append(r["ms"])
    lat.sort()
    n = len(records)
    ok = tot["top1"] + tot["top3"]
    print("\n===== SUMMARY =====")
    print(f"total {n} | top1 {tot['top1']} ({tot['top1'] * 100 // n}%) "
          f"top3 {tot['top3']} ({tot['top3'] * 100 // n}%) "
          f"→ resolved {ok} ({ok * 100 / n:.1f}%) | wrong {tot['wrong']} "
          f"empty {tot['empty']} error {tot['error']}")
    if lat:
        print(f"latency p50 {lat[len(lat) // 2]:.1f}ms "
              f"p95 {lat[int(len(lat) * 0.95)]:.1f}ms max {lat[-1]:.1f}ms")
    print("\nper-category:")
    for c in sorted(cats):
        t = cats[c]
        n2 = sum(t.values())
        res = t.get("top1", 0) + t.get("top3", 0)
        print(f"  {c:18} {res:3}/{n2:<3} resolved "
              f"(top1 {t.get('top1', 0)}, top3 {t.get('top3', 0)}, "
              f"wrong {t.get('wrong', 0)}, empty {t.get('empty', 0)})")
    print("\n===== MISSES =====")
    for r in records:
        if r["verdict"] in ("wrong", "empty", "error"):
            top = (r["hits"][0]["name"] if r["hits"] else
                   r.get("error", "—"))
            print(f"  {r['verdict']:5} [{r['cat']:16}] {r['q']!r:42} → {top}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--battery", default="tools/probe_battery.json")
    ap.add_argument("--local", action="store_true")
    ap.add_argument("--live", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--spacing", type=float, default=0.4)
    ap.add_argument("--limit", type=int, default=5)
    args = ap.parse_args()
    battery = json.load(open(args.battery))
    queries = battery["queries"]
    if args.local:
        rec = run_local(queries, args.limit)
    elif args.live:
        rec = run_live(queries, args.live, args.spacing, args.limit)
    else:
        ap.error("pass --local or --live URL")
    summarize(rec)
    if args.out:
        json.dump({"records": rec}, open(args.out, "w"), indent=1)
        print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
