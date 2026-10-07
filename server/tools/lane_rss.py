"""Lane probe — staged RSS of the real server components.

Loads the prod-shaped resident state piece by piece in ONE process and
prints psutil RSS after each stage: imports -> graph engine -> gazetteer
-> history -> community -> GTFS feeds -> field snapshot/live refresh.

Run:  PYTHONPATH=core/build312:. .venv312/bin/python tools/lane_rss.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "core", "build312"))

import psutil

P = psutil.Process(os.getpid())


def rss(label: str) -> float:
    mb = P.memory_info().rss / 1e6
    print(f"RSS {mb:9.1f} MB   {label}", flush=True)
    return mb


def main():
    t0 = time.time()
    rss("interpreter + psutil")

    import main  # noqa: F401 — the whole request-path import graph
    rss("import main (app + field + forecast + fires modules)")

    import history
    history._load()
    rss("history._load() (climatology db)")

    from v2.gazetteer import GAZ
    n = len(GAZ._load())
    rss(f"gazetteer._load() ({n} rows + postings + trigram)")

    import community
    community._load()
    rss("community._load() (cells/hours/days + name buckets)")

    import routegraph
    t = time.time()
    eng = routegraph.path_engine()
    dt = time.time() - t
    rss(f"routegraph.path_engine() [{type(eng).__name__}] ({dt:.0f}s load)")

    # engine warm structures: lazy per-mode reach floods + traversal
    # structures the first A* builds per mode (the ~9 s boot burn)
    try:
        for mode in ("car", "bike", "auto", "cycle", "walk"):
            eng.query(28.6315, 77.2167, 28.6519, 77.1907, mode)
        rss("engine warmed: 5-mode first A* + reach floods")
    except Exception as e:
        rss(f"engine warm query failed: {e!r}")

    # GTFS feeds — baked into the prod image; local download ~120 MB.
    # Skipped when feeds aren't on disk (download takes minutes).
    try:
        import transit_real
        if transit_real.feeds_on_disk():
            from transit_v2 import default_feeds
            t = time.time()
            feeds = default_feeds()
            dt = time.time() - t
            rss(f"transit_v2.default_feeds() {sorted(feeds)} ({dt:.0f}s)")
        else:
            rss("GTFS feeds absent locally — prod image bakes them "
                "(~120 MB feeds -> compiled indexes, measure there)")
    except Exception as e:
        rss(f"GTFS load failed: {e!r}")

    # snapshot field (local mirror; prod ships none — replaced by live)
    from airfield import FIELD
    FIELD.load_snapshot()
    rss("FIELD.load_snapshot() (air-index warm serve)")

    import asyncio
    import httpx

    async def _live():
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(8.0, connect=4.0))
        try:
            await FIELD.refresh(client, force=True)
        finally:
            await client.aclose()
    asyncio.run(_live())
    rss(f"FIELD.refresh(force) — live samples "
        f"({len(FIELD._samples)} rows, stations {FIELD._station_count})")

    # engine reweight against the field — the priced-raster path
    from v2 import plan as vp
    t = time.time()
    vp._engine_reweight(eng)
    ep = getattr(eng, "edges_priced", 0)
    ep = ep() if callable(ep) else ep
    rss(f"engine reweight ({time.time() - t:.0f}s, {ep} edges priced)")

    rss(f"DONE total {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
