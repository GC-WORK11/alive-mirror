"""Bake the GTFS transit layer into the deploy image — run at image build.

Cold-start this removes: data/gtfs/ used to ship empty, so a fresh task
downloaded ~120 MB of feeds lazily on the first request and then paid a
~minute-long pure-Python parse (3.3M stop_times on a 1-vCPU task) inside
the 12 s transit arm budget — degraded:["transit"] for the first minutes
of every cold task.

This script does the whole job at build time instead:

  1. transit_real.warm() — downloads metro + bus feeds (multi-source,
     retries the mirrors in order) and compiles transit_real's own
     _index.pkl beside the txts.
  2. transit_v2.default_feeds() — compiles each feed's CSA index
     (_v2_index.pkl), the pickle the plan arm's first request loads.

Both indexes are baked so EVERY transit path (v2 plan scan, the
transit.py station-model fallback, /compare bus hints) starts warm.
Runtime stays honest: feeds older than REFRESH_DAYS still re-fetch in
the background, and if this script can't fetch anything the image build
fails loudly rather than shipping the cold-start silently.

Usage (from server/):
    python tools/bake_gtfs.py            # build / refresh data/gtfs
    GTFS_BAKE_TIMEOUT_S=1200 python tools/bake_gtfs.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import transit_real  # noqa: E402
import transit_v2    # noqa: E402


def main() -> int:
    timeout_s = float(os.environ.get("GTFS_BAKE_TIMEOUT_S", "900"))
    st = transit_real.warm(timeout_s=timeout_s)
    missing = [k for k in ("metro", "bus") if not st.get(k, {}).get("loaded")]
    if missing:
        print(f"bake_gtfs: feeds failed to land: {missing} — "
              f"errors: {st.get('errors')}", file=sys.stderr)
        return 1

    feeds = transit_v2.default_feeds()
    missing_v2 = [k for k in ("metro", "bus") if k not in feeds]
    if missing_v2:
        print(f"bake_gtfs: txts present but v2 index failed: {missing_v2}",
              file=sys.stderr)
        return 1

    for kind in ("metro", "bus"):
        f = feeds[kind]
        print(f"bake_gtfs: {kind} — {len(f.stop_ids)} stops, "
              f"{len(f.c_dep)} connections")
    return 0


if __name__ == "__main__":
    sys.exit(main())
