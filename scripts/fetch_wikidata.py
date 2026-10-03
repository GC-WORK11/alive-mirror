#!/usr/bin/env python3
"""
fetch_wikidata.py -- ALive-108 Delhi-NCR corpus, Wikidata source.

Pulls every Wikidata item that has coordinates (P625) inside the NCR
extraction box via the Wikidata Query Service `wikibase:box` geo index:

    SELECT ?item ?coord ?sitelinks ?en ?hi ?alt ?inst ?instLabel WHERE {
      SERVICE wikibase:box {
        ?item wdt:P625 ?coord .
        bd:serviceParam wikibase:cornerSouthWest "Point(76.6 28.0)"^^geo:wktLiteral .
        bd:serviceParam wikibase:cornerNorthEast "Point(77.7 29.0)"^^geo:wktLiteral .
      }
      OPTIONAL { ?item rdfs:label    ?en.  FILTER(LANG(?en)  = "en") }
      OPTIONAL { ?item rdfs:label    ?hi.  FILTER(LANG(?hi)  = "hi") }
      OPTIONAL { ?item skos:altLabel ?alt. FILTER(LANG(?alt) IN ("en","hi")) }
      OPTIONAL { ?item wdt:P31       ?inst. }
      OPTIONAL { ?item wikibase:sitelinks ?sitelinks. }
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
    }

Rows are grouped per item (the OPTIONALs cross-multiply), then emitted as
server/data/corpus/aux/wikidata.jsonl in the same schema build_corpus.py
produces ({id, display, aliases[], category, lat, lon, popularity}) plus
provenance fields:
    source   : "wikidata"
    wikidata : "Q12345"
    sitelinks: <int>           (real popularity signal -> popularity)
synthetic is absent/False -- every row is a real Wikidata entity.

instance-of (P31) is mapped to corpus categories (station / hospital /
school / university / mall / market / temple / mosque / monument / locality
...) by INST_MAP + keyword fallback; unmatched -> "place".

Usage:
    tools/corpus-venv/bin/python scripts/fetch_wikidata.py            # fetch+write
    tools/corpus-venv/bin/python scripts/fetch_wikidata.py --stats    # report only
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS_DIR = os.path.join(REPO, "server", "data", "corpus")
OUT_PATH = os.path.join(CORPUS_DIR, "aux", "wikidata.jsonl")

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "alive-corpus/1.0 (ALive-108 Delhi-NCR gazetteer build; scripts/fetch_wikidata.py)"

# Must match EXTRACT_BBOX in scripts/build_corpus.py (minlon, maxlon, minlat, maxlat).
EXTRACT_BBOX = (76.60, 77.70, 28.00, 29.00)

QUERY_TEMPLATE = """
SELECT ?item ?coord ?sitelinks ?en ?hi ?alt ?inst ?instLabel WHERE {
  SERVICE wikibase:box {
    ?item wdt:P625 ?coord .
    bd:serviceParam wikibase:cornerSouthWest "Point({minlon} {minlat})"^^geo:wktLiteral .
    bd:serviceParam wikibase:cornerNorthEast "Point({maxlon} {maxlat})"^^geo:wktLiteral .
  }
  OPTIONAL { ?item rdfs:label    ?en.  FILTER(LANG(?en)  = "en") }
  OPTIONAL { ?item rdfs:label    ?hi.  FILTER(LANG(?hi)  = "hi") }
  OPTIONAL { ?item skos:altLabel ?alt. FILTER(LANG(?alt) IN ("en","hi")) }
  OPTIONAL { ?item wdt:P31       ?inst. }
  OPTIONAL { ?item wikibase:sitelinks ?sitelinks. }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
ORDER BY ?item
"""

# P31 -> corpus category.  QIDs for the classes that dominate Delhi NCR
# Wikidata coverage; keyword fallback below catches the long tail.
INST_MAP = {
    "Q928830": "metro",            # metro station
    "Q55488": "station",           # railway station
    "Q1248784": "airport",
    "Q16917": "hospital",
    "Q3914": "school",
    "Q3918": "university",
    "Q875538": "university",       # public university
    "Q11315": "mall",              # shopping mall
    "Q44539": "temple",
    "Q32815": "mosque",
    "Q16970": "church",
    "Q486972": "locality",         # human settlement
    "Q532": "village",
    "Q15284": "village",
    "Q3957": "town",
    "Q515": "city",
    "Q22698": "park",
    "Q33506": "museum",
    "Q41176": "building",
    "Q79007": "street",
    "Q570116": "attraction",       # tourist attraction
}

# keyword (lowercased, on instLabel) -> category, first hit wins
INST_KEYWORDS = [
    ("metro station", "metro"), ("railway station", "station"),
    ("station", "station"), ("airport", "airport"), ("hospital", "hospital"),
    ("university", "university"), ("college", "college"),
    ("school", "school"), ("mall", "mall"), ("shopping", "mall"),
    ("market", "market"), ("mandi", "market"), ("bazaar", "market"),
    ("temple", "temple"), ("mosque", "mosque"), ("church", "church"),
    ("gurudwara", "gurudwara"), ("monument", "monument"),
    ("fort", "monument"), ("tomb", "monument"), ("museum", "museum"),
    ("park", "park"), ("garden", "park"), ("stadium", "stadium"),
    ("village", "village"), ("locality", "locality"),
    ("neighbourhood", "locality"), ("neighborhood", "locality"),
    ("human settlement", "locality"), ("town", "town"), ("city", "city"),
    ("district", "district"), ("block", "block"), ("tehsil", "tehsil"),
    ("constituency", "district"), ("census town", "town"),
    ("hotel", "hotel"), ("restaurant", "restaurant"),
    ("cinema", "cinema"), ("theatre", "cinema"), ("theater", "cinema"),
    ("office", "office"), ("court", "office"), ("embassy", "embassy"),
    ("lake", "water"), ("pond", "water"), ("river", "water"),
    ("stream", "water"), ("canal", "water"), ("drain", "water"),
    ("bridge", "bridge"), ("road", "street"), ("street", "street"),
    ("bus station", "bus_station"), ("bus terminus", "bus_station"),
    ("depot", "bus_station"), ("institute", "institute"),
    ("research", "institute"), ("library", "library"),
    ("police station", "police"), ("fire station", "fire"),
    ("prison", "prison"), ("cemetery", "cemetery"),
    ("cremator", "cemetery"), ("shrine", "temple"), ("dargah", "shrine"),
    ("memorial", "monument"), ("gate", "monument"),
    ("archaeological", "monument"), ("heritage", "monument"),
    ("building", "building"), ("complex", "complex"),
    ("industrial", "district"), ("estate", "district"),
    ("region", "district"), ("academic", "college"),
]

_COORD_RE = re.compile(r"Point\(([-0-9.]+) ([-0-9.]+)\)")


def ascii_fold(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    )


def in_box(lat: float, lon: float, box=EXTRACT_BBOX) -> bool:
    return box[2] <= lat <= box[3] and box[0] <= lon <= box[1]


def sparql(query: str, retries: int = 3) -> dict:
    """GET the SPARQL endpoint; return parsed JSON. Retries on 429/5xx."""
    url = (SPARQL_ENDPOINT + "?format=json&query=" +
           urllib.parse.quote(query))
    last = ""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/sparql-results+json",
            })
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.reason}"
            if e.code in (429, 500, 502, 503):
                wait = 5 * (attempt + 1)
                print(f"  {last} -- retry in {wait}s", file=sys.stderr)
                time.sleep(wait)
                continue
            raise
        except Exception as e:  # noqa: BLE001
            last = str(e)
            wait = 5 * (attempt + 1)
            print(f"  {last} -- retry in {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"SPARQL failed after {retries} tries: {last}")


def categorize(inst_qids: set, inst_labels: set) -> str:
    for q in inst_qids:
        if q in INST_MAP:
            return INST_MAP[q]
    for lab in inst_labels:
        l = lab.lower()
        for kw, cat in INST_KEYWORDS:
            if kw in l:
                return cat
    return "place"


def fetch() -> list[dict]:
    minlon, maxlon, minlat, maxlat = EXTRACT_BBOX
    q = (QUERY_TEMPLATE
         .replace("{minlon}", str(minlon)).replace("{maxlon}", str(maxlon))
         .replace("{minlat}", str(minlat)).replace("{maxlat}", str(maxlat)))
    print("querying Wikidata box "
          f"lon {minlon}-{maxlon}, lat {minlat}-{maxlat} ...", flush=True)
    data = sparql(q)
    rows = data["results"]["bindings"]
    print(f"  {len(rows):,} bindings", flush=True)

    items: dict[str, dict] = {}
    for b in rows:
        qid = b["item"]["value"].rsplit("/", 1)[-1]
        it = items.setdefault(qid, {
            "labels_en": set(), "labels_hi": set(), "alts": set(),
            "insts": set(), "inst_labels": set(),
            "coord": None, "sitelinks": 0,
        })
        if "en" in b:
            it["labels_en"].add(b["en"]["value"])
        if "hi" in b:
            it["labels_hi"].add(b["hi"]["value"])
        if "alt" in b:
            it["alts"].add(b["alt"]["value"])
        if "inst" in b:
            it["insts"].add(b["inst"]["value"].rsplit("/", 1)[-1])
        if "instLabel" in b:
            il = b["instLabel"]["value"]
            if not il.startswith("Q"):  # unlabelled classes echo the QID
                it["inst_labels"].add(il)
        if "coord" in b:
            m = _COORD_RE.search(b["coord"]["value"])
            if m:
                it["coord"] = (float(m.group(2)), float(m.group(1)))
        if "sitelinks" in b:
            it["sitelinks"] = max(it["sitelinks"],
                                  int(b["sitelinks"]["value"]))

    entries = []
    skipped = {"no_coord": 0, "outside": 0, "no_label": 0}
    for qid, it in items.items():
        if not it["coord"]:
            skipped["no_coord"] += 1
            continue
        lat, lon = it["coord"]
        if not in_box(lat, lon):
            skipped["outside"] += 1
            continue
        if not it["labels_en"]:
            skipped["no_label"] += 1
            continue
        disp = sorted(it["labels_en"], key=len)[0]  # shortest en label
        aliases = sorted(
            {*it["labels_en"], *it["labels_hi"], *it["alts"]} - {disp})
        entries.append({
            "id": f"wd:{qid}",
            "display": " ".join(disp.split()),
            "aliases": aliases,
            "category": categorize(it["insts"], it["inst_labels"]),
            "lat": round(lat, 6), "lon": round(lon, 6),
            "popularity": it["sitelinks"],
            "source": "wikidata",
            "sources": ["wikidata"],
            "wikidata": qid,
            "synthetic": False,
        })
    print(f"  items: {len(items):,}  ->  entries in box: {len(entries):,}  "
          f"skipped {skipped}", flush=True)
    return entries


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=OUT_PATH)
    ap.add_argument("--stats", action="store_true",
                    help="don't fetch; just summarize the existing file")
    args = ap.parse_args()

    if args.stats:
        if not os.path.exists(args.out):
            print("no file at", args.out)
            return 1
        from collections import Counter
        cats = Counter()
        n = 0
        with open(args.out, encoding="utf-8") as f:
            for line in f:
                e = json.loads(line)
                cats[e["category"]] += 1
                n += 1
        print(f"{n:,} wikidata rows in {args.out}")
        for c, k in cats.most_common(30):
            print(f"  {c:14s} {k:,}")
        return 0

    entries = fetch()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    tmp = args.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    os.replace(tmp, args.out)
    print(f"wrote {len(entries):,} rows -> {os.path.relpath(args.out, REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
