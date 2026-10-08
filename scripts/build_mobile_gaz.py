#!/usr/bin/env python3
"""
build_mobile_gaz.py -- ALive-108 T0 mobile gazetteer emitter.

Reads the merged corpus (server/data/corpus/delhi-corpus.jsonl.gz,
built by scripts/build_corpus.py), dedupes it against the bundled
Mobile/assets/delhi-gazetteer.json by normalized-name + ~75 m cell, and
writes server/data/corpus/delhi-gazetteer-150k.json in the bundled schema:
    {n, c, lat, lon, w, k}
  n   display name        c  category (sub-type after ':')
  w   ranking weight 1-12 (MOBILE_W in build_corpus.py)
  k   source confidence   (SOURCE_K; bundled rows keep their own k)

Usage:
    tools/corpus-venv/bin/python scripts/build_mobile_gaz.py
    tools/corpus-venv/bin/python scripts/build_mobile_gaz.py --target 150000 \
        --out server/data/corpus/delhi-gazetteer-150k.json
    tools/corpus-venv/bin/python scripts/build_mobile_gaz.py --install

--install is the data-stamp step: it writes the emitted gazetteer over
Mobile/assets/delhi-gazetteer.json AND regenerates the prebuilt t0 search
index (Mobile/assets/t0-index/ via Mobile/scripts/build-t0-index.mjs)
in the same run, so the shipped index can never rot behind the corpus.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_corpus as bc  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", default=bc.OUT_JSONL)
    ap.add_argument("--out", default=bc.OUT_MOBILE)
    ap.add_argument("--gazetteer", default=bc.GAZETTEER_PATH,
                    help="bundled gazetteer to merge/dedupe against")
    ap.add_argument("--target", type=int, default=150000)
    ap.add_argument("--install", action="store_true",
                    help="also write the emit over the bundled asset and "
                         "rebuild the prebuilt t0 index (one stamp step)")
    args = ap.parse_args()

    if not os.path.exists(args.corpus):
        print(f"corpus missing: {args.corpus} -- run build_corpus.py first",
              file=sys.stderr)
        return 2

    entries = []
    with gzip.open(args.corpus, "rt", encoding="utf-8") as f:
        for line in f:
            entries.append(json.loads(line))
    print(f"{len(entries):,} corpus rows loaded")

    m = bc.emit_mobile(entries, args.target,
                       gaz_path=args.gazetteer, out_path=args.out)
    print(f"out: {os.path.relpath(m['path'], bc.REPO)} ({m['size_mb']:.1f} MB)")
    print(f"bundled kept: {m['existing']:,} | new corpus rows added: "
          f"{m['added']:,} | name+75 m dupes skipped: {m['skipped_dupes']:,}")
    print(f"total: {m['total']:,} (target {args.target:,})")

    if args.install:
        import shutil
        import subprocess
        shutil.copyfile(args.out, bc.GAZETTEER_PATH)
        print(f"installed -> {os.path.relpath(bc.GAZETTEER_PATH, bc.REPO)}")
        # the index derives from the corpus: rebuild it in THIS step so a
        # stale t0 index can never ship against fresher data
        r = subprocess.run(
            ["node", "scripts/build-t0-index.mjs", "--force"],
            cwd=os.path.join(bc.REPO, "Mobile"), check=False)
        if r.returncode != 0:
            print("t0 index prebuild failed -- run `cd Mobile && "
                  "npm run build:t0` manually", file=sys.stderr)
            return r.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
