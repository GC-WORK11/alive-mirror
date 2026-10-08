#!/usr/bin/env python3
"""fetch_overture.py — pull Overture Maps `places` rows for the Delhi-NCR box
into the corpus aux pipeline.

The Overture places theme is a free parquet dataset on public S3 (no auth):
    s3://overturemaps-us-west-2/release/<REL>/theme=places/type=place/*.parquet

It carries ~394k named rows inside the corpus extraction bbox — business
POIs OSM lacks (banks, electronics shops, clinics, hotels).  Rows are
filtered before emit:

    * display name present (names.primary)
    * basic_category present — uncategorized rows would emit an empty
      subtitle and carry no kind signal
    * operating_status != 'permanently_closed'
    * confidence >= MIN_CONF (Overture's own dedupe/attestation score;
      the bottom tail is single-source noise)
    * category not in DROP_CATS — non-navigable B2B/spam classes
      (manufacturers, wholesalers, real-estate brokers, ...)

Emitted schema is exactly what build_corpus.merge_aux() consumes:
    {id, display, aliases, category, lat, lon, popularity,
     source, sources, synthetic, k, conf}

    category  "overture:<basic_category>" — merge_aux dedupes on
              normalized-name + ~75 m cell, so an OSM shop and its
              Overture twin collapse into one row with both sources.
    popularity  Overture confidence (0..1, passes _norm_popularity).
    k           per-row ship-confidence 0.60 + 0.35*conf — emit_mobile
                prefers row-level k over the SOURCE_K table default.
    conf        raw confidence kept for audits.

Usage:
    python3 scripts/fetch_overture.py                 # writes aux/overture-places.jsonl
    python3 scripts/fetch_overture.py --release 2026-09-23.1
    python3 scripts/fetch_overture.py --min-conf 0.45 --out /tmp/x.jsonl

Requires `duckdb` (pip install duckdb) — it reads the remote parquet in
place, no download of the full theme (~60 GB) needed.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO, "scripts"))
from build_corpus import EXTRACT_BBOX  # noqa: E402

AUX_DIR = os.path.join(REPO, "server", "data", "corpus", "aux")
OUT_PATH = os.path.join(AUX_DIR, "overture-places.jsonl.gz")

RELEASE = "2026-09-23.1"
BUCKET = "overturemaps-us-west-2"
MIN_CONF = 0.40

# Overture classes a Delhi user cannot walk up to / would never type:
# upstream suppliers, intermediaries and listing noise.  Kept classes
# include offices (people navigate to them), home_service (hardware is
# mistagged there), and event services (tent houses / decorators are real
# Delhi storefront searches).
DROP_CATS = {
    "real_estate_service", "manufacturer", "supplier_or_distributor",
    "building_or_construction_service", "design_service",
    "technical_service", "media_service", "wholesaler",
    "storage_facility", "shipping_or_delivery_service",
    "taxi_or_ride_share_service", "sport_league", "sport_team",
    "political_organization", "housing_or_property_service",
    "event_or_party_service",
}


def _release_files(release: str) -> list[str]:
    """List the parquet shard keys of one release's places theme."""
    import urllib.request
    import xml.etree.ElementTree as ET

    prefix = f"release/{release}/theme=places/type=place/"
    url = (f"https://{BUCKET}.s3.amazonaws.com/?list-type=2"
           f"&prefix={urllib.request.quote(prefix)}")
    keys = []
    token = None
    while True:
        u = url + (f"&continuation-token={urllib.request.quote(token)}"
                   if token else "")
        with urllib.request.urlopen(u, timeout=30) as r:
            root = ET.fromstring(r.read())
        ns = {"s": "http://s3.amazonaws.com/doc/2006-03-01/"}
        for k in root.findall("s:Contents/s:Key", ns):
            keys.append("https://" + BUCKET + ".s3.amazonaws.com/" + k.text)
        trunc = root.find("s:IsTruncated", ns)
        if trunc is None or trunc.text != "true":
            break
        nxt = root.find("s:NextContinuationToken", ns)
        if nxt is None:
            break
        token = nxt.text
    return keys


def fetch(release: str, min_conf: float, out_path: str) -> dict:
    try:
        import duckdb
    except ImportError:
        sys.exit("fetch_overture needs `pip install duckdb` "
                 "(reads remote parquet over https; no AWS creds needed)")

    files = _release_files(release)
    if not files:
        sys.exit(f"no parquet shards listed for release {release}")

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute("INSTALL spatial; LOAD spatial;")
    lit = "[" + ",".join(f"'{f}'" for f in files) + "]"
    xmin, xmax, ymin, ymax = EXTRACT_BBOX
    dlit = "(" + ",".join(f"'{d}'" for d in sorted(DROP_CATS)) + ")"
    sql = f"""
    SELECT id, names.primary AS name,
           basic_category AS cat,
           coalesce(map_values(names.common), []) AS common,
           brand.names.primary AS brand_name,
           confidence, ST_X(geometry) AS lon, ST_Y(geometry) AS lat
    FROM read_parquet({lit}, union_by_name=true)
    WHERE bbox.xmin <= {xmax} AND bbox.xmax >= {xmin}
      AND bbox.ymin <= {ymax} AND bbox.ymax >= {ymin}
      AND names.primary IS NOT NULL
      AND basic_category IS NOT NULL
      AND (operating_status IS NULL OR operating_status <> 'permanently_closed')
      AND basic_category NOT IN {dlit}
      AND basic_category NOT LIKE 'b2b%'
      AND confidence >= {min_conf}
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    n = 0
    cats: dict[str, int] = {}
    opener = gzip.open if out_path.endswith(".gz") else open
    with opener(out_path, "wt", encoding="utf-8") as f:
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description]
        while True:
            batch = cur.fetchmany(5000)
            if not batch:
                break
            for row in batch:
                rec = dict(zip(cols, row))
                aliases = []
                seen = {rec["name"].strip().lower()}
                for a in (rec.get("common") or []):
                    a = " ".join(str(a).split()).strip()
                    if a and a.lower() not in seen:
                        seen.add(a.lower())
                        aliases.append(a)
                b = rec.get("brand_name")
                if b and b.strip().lower() not in seen:
                    seen.add(b.strip().lower())
                    aliases.append(b.strip())
                conf = float(rec["confidence"])
                e = {
                    "id": "ovt:" + str(rec["id"]),
                    "display": " ".join(str(rec["name"]).split()),
                    "aliases": aliases,
                    "category": "overture:" + rec["cat"],
                    "lat": round(float(rec["lat"]), 6),
                    "lon": round(float(rec["lon"]), 6),
                    "popularity": conf,
                    "source": "overture",
                    "sources": ["overture"],
                    "synthetic": False,
                    "k": round(0.60 + 0.35 * conf, 3),
                    "conf": conf,
                }
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
                cats[rec["cat"]] = cats.get(rec["cat"], 0) + 1
                n += 1
    return {"rows": n, "out": out_path,
            "size_mb": os.path.getsize(out_path) / 1e6,
            "cats": cats, "release": release, "min_conf": min_conf}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--release", default=RELEASE)
    ap.add_argument("--min-conf", type=float, default=MIN_CONF)
    ap.add_argument("--out", default=OUT_PATH)
    args = ap.parse_args()
    st = fetch(args.release, args.min_conf, args.out)
    print(f"overture {st['release']}: {st['rows']:,} rows -> {st['out']} "
          f"({st['size_mb']:.1f} MB)")
    for c, n in sorted(st["cats"].items(), key=lambda kv: -kv[1])[:15]:
        print(f"  {n:>7,}  {c}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
