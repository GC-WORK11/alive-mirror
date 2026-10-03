#!/usr/bin/env python3
"""
build_corpus.py -- ALive-108 Delhi-NCR search corpus builder.

Pipeline:
  1. Download a Geofabrik OSM extract that covers Delhi into
     server/data/corpus/dl/ (gitignored).  Geofabrik has no
     `delhi-latest.osm.pbf`; Delhi lives in the India *northern-zone*
     extract.  We try delhi-latest first (in case it appears), then
     northern-zone-latest, then the all-India extract.
  2. Parse with pyosmium.  Extract, inside the NCR extraction box:
       - POIs        (amenity / shop / tourism / leisure / office / craft tags)
       - buildings   (building=* + name)
       - streets     (highway=* + name, centroid of the way)
       - addr blocks (addr:place / addr:subdistrict / addr:housenumber where a
                      name or street makes it displayable)
     Every entry -> {id, display, aliases[], category, lat, lon, popularity:0}
     (schema per docs/plan/08-cpp-engine.md "Search index design").
  3. Emit  server/data/corpus/delhi-corpus.jsonl.gz  (one JSON per line, gzip)
           server/data/corpus/delhi-corpus-sample.jsonl  (committed, <=5 MB)
           server/data/corpus/STATS.md
  4. --emit-mobile also writes a Mobile-ready gazetteer (same schema as
     Mobile/assets/delhi-gazetteer.json: {n, c, lat, lon, w, k}) deduped
     against the bundled 26.5k gazetteer by normalized-name + 75 m radius,
     capped at --mobile-target entries (default 150k).
  5. --score (default on after a build) loads the corpus + aliases.json and
     scores tests/search_queries.txt with a simple normalized
     prefix+token index; results appended into STATS.md.

Usage:
    tools/corpus-venv/bin/python scripts/build_corpus.py            # full run
    tools/corpus-venv/bin/python scripts/build_corpus.py --score    # rescore only
    tools/corpus-venv/bin/python scripts/build_corpus.py --emit-mobile
"""

from __future__ import annotations

import argparse
import bisect
import gzip
import io
import json
import math
import os
import re
import sys
import time
import unicodedata
import urllib.request

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO, "server", "data")
CORPUS_DIR = os.path.join(DATA_DIR, "corpus")
DL_DIR = os.path.join(CORPUS_DIR, "dl")
ALIASES_PATH = os.path.join(DATA_DIR, "aliases.json")
QUERIES_PATH = os.path.join(REPO, "tests", "search_queries.txt")
GAZETTEER_PATH = os.path.join(REPO, "Mobile", "assets", "delhi-gazetteer.json")

OUT_JSONL = os.path.join(CORPUS_DIR, "delhi-corpus.jsonl.gz")
OUT_SAMPLE = os.path.join(CORPUS_DIR, "delhi-corpus-sample.jsonl")
OUT_STATS = os.path.join(CORPUS_DIR, "STATS.md")
OUT_MOBILE = os.path.join(CORPUS_DIR, "delhi-gazetteer-150k.json")

# Geofabrik candidates, best first.  Geofabrik redirects missing files to the
# site index (a ~10 kB HTML page), so a "200" is not proof of a PBF -- we
# verify the final URL still ends in .osm.pbf.
PBF_CANDIDATES = [
    "https://download.geofabrik.de/asia/india/delhi-latest.osm.pbf",
    "https://download.geofabrik.de/asia/india/northern-zone-latest.osm.pbf",
    "https://download.geofabrik.de/asia/india-latest.osm.pbf",
]

# Extraction box: Delhi-NCR with buffer -- must cover Gurugram, Noida,
# Greater Noida, Ghaziabad, Faridabad (test set hits all of these).
EXTRACT_BBOX = (76.60, 77.70, 28.00, 29.00)  # minlon, maxlon, minlat, maxlat

# Strict NCR reference box from the task / doc 04 -- used ONLY for flagging.
NCR_BBOX = (76.75, 77.95, 28.15, 28.98)

POI_KEYS = ("amenity", "shop", "tourism", "leisure", "office", "craft",
            "healthcare", "emergency")

# Named feature classes needed for nav-grade recall (metro stations,
# localities, monuments). Only extracted when they carry a name.
PLACE_KEYS = ("place", "railway", "public_transport", "aeroway", "historic",
              "boundary")

# Extra tags that turn into aliases.
ALIAS_TAGS = (
    "name:en", "alt_name", "loc_name", "official_name", "old_name",
    "short_name", "name:hi", "brand", "ref",
    # context tags: a POI's street/locality becomes searchable context
    "addr:street", "addr:place", "addr:subdistrict", "addr:city", "is_in",
)

SAMPLE_LINES = 20000  # first N entries copied to the committed sample file

# Weight table for the mobile gazetteer `w` field (matches bundled scale ~1-12)
MOBILE_W = {
    "airport": 12, "station": 11, "metro": 11, "attraction": 10,
    "hospital": 9, "mall": 9, "university": 9, "bus_station": 9,
    "market": 8, "cinema": 8, "hotel": 7, "restaurant": 6, "cafe": 6,
    "street": 4, "building": 3, "address": 2, "poi": 5,
}


# ---------------------------------------------------------------------------
# Normalization (mirrors the T1 index spec in docs/plan/08)
# ---------------------------------------------------------------------------

def ascii_fold(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    )


_PUNCT = re.compile(r"[^a-z0-9 ]+")
_SPACE = re.compile(r"\s+")


def load_aliases(path: str = ALIASES_PATH) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return {k: v for k, v in json.load(f).items()
                    if not k.startswith("_")}
    except FileNotFoundError:
        return {}


def normalize(s: str, aliases: dict | None = None) -> str:
    """lowercase -> ascii-fold -> strip punct -> token alias map."""
    s = _SPACE.sub(" ", _PUNCT.sub(" ", ascii_fold(s.lower()))).strip()
    if not aliases:
        return s
    out = []
    for tok in s.split():
        out.append(aliases.get(tok, tok))
    return _SPACE.sub(" ", " ".join(out)).strip()


def norm_tokens(s: str, aliases: dict | None = None) -> list:
    return normalize(s, aliases).split()


# ---------------------------------------------------------------------------
# Step 1 -- download
# ---------------------------------------------------------------------------

def download_pbf(dl_dir: str = DL_DIR) -> tuple[str | None, str]:
    """Return (local_path, source_url) or (None, error_text)."""
    os.makedirs(dl_dir, exist_ok=True)

    # Reuse an already-downloaded extract.
    for name in sorted(os.listdir(dl_dir)):
        if name.endswith(".osm.pbf") and os.path.getsize(
            os.path.join(dl_dir, name)
        ) > 1_000_000:
            return os.path.join(dl_dir, name), f"cached:{name}"

    last_err = ""
    for url in PBF_CANDIDATES:
        name = url.rsplit("/", 1)[-1]
        dest = os.path.join(dl_dir, name)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "alive-corpus/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                final = r.geturl()
                if not final.endswith(".osm.pbf"):
                    last_err = f"{url} -> redirected to {final} (no such extract)"
                    continue
                with open(dest, "wb") as out:
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        out.write(chunk)
            if os.path.getsize(dest) < 1_000_000:
                last_err = f"{url} -> suspiciously small ({os.path.getsize(dest)} B)"
                os.unlink(dest)
                continue
            return dest, url
        except Exception as e:  # noqa: BLE001 -- report, try next mirror
            last_err = f"{url} -> {e}"
            if os.path.exists(dest):
                os.unlink(dest)
    return None, last_err


# ---------------------------------------------------------------------------
# Step 2 -- OSM extraction
# ---------------------------------------------------------------------------

def in_box(lat: float, lon: float, box=EXTRACT_BBOX) -> bool:
    return box[2] <= lat <= box[3] and box[0] <= lon <= box[1]


def make_entry(osm_id, display, aliases, category, lat, lon):
    disp = " ".join(str(display).split()).strip()
    if not disp:
        return None
    seen, al = {disp.lower()}, []
    for a in aliases:
        a = " ".join(str(a).split()).strip()
        if a and a.lower() not in seen:
            seen.add(a.lower())
            al.append(a)
    return {
        "id": str(osm_id),
        "display": disp,
        "aliases": al,
        "category": category,
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        "popularity": 0,
    }


def build_corpus(pbf_path: str):
    """Parse the PBF, return (entries, stats_dict)."""
    import osmium  # pyosmium, in tools/corpus-venv

    entries: dict[tuple, dict] = {}  # dedupe key -> entry
    way_centroids: dict[int, tuple] = {}  # way id -> (lat, lon), in-box only
    stats = {
        "nodes_scanned": 0, "ways_scanned": 0,
        "poi": 0, "building": 0, "street": 0, "addr": 0, "place": 0,
        "outside_ncr_bbox": 0, "deduped": 0, "empty_name_dropped": 0,
    }

    def put(entry):
        if entry is None:
            stats["empty_name_dropped"] += 1
            return
        if not in_box(entry["lat"], entry["lon"]):
            return  # outside extraction box entirely
        # dedupe by normalized name + ~75 m cell (0.0007 deg ~ 77 m lat)
        key = (
            normalize(entry["display"]),
            int(entry["lat"] / 0.0007),
            int(entry["lon"] / 0.0007),
        )
        old = entries.get(key)
        if old is None or len(entry["aliases"]) > len(old["aliases"]):
            if old is not None:
                stats["deduped"] += 1
            entries[key] = entry
        else:
            stats["deduped"] += 1

    def classify(t, has_name):
        """Return (category, display_source) for a tag set, or None."""
        name = t.get("name")
        for k in POI_KEYS:
            if k in t and name:
                return f"{k}:{t[k]}", name
        if name:
            for k in PLACE_KEYS:
                if k in t:
                    return f"{k}:{t[k]}", name
            if "building" in t:
                return f"building:{t['building']}", name
        if "addr:place" in t:
            return "addr:place", t["addr:place"]
        if "addr:subdistrict" in t:
            return "addr:subdistrict", t["addr:subdistrict"]
        if "addr:housenumber" in t and (t.get("addr:street") or name):
            return "addr:address", name or (
                f"{t['addr:housenumber']} {t.get('addr:street', '')}".strip())
        return None

    class Handler(osmium.SimpleHandler):
        def node(self, n):
            stats["nodes_scanned"] += 1
            t = n.tags
            c = classify(t, t.get("name"))
            if c is None:
                return
            cat, disp = c
            aliases = [t[k] for k in ALIAS_TAGS if k in t]
            if cat == "addr:address" and not t.get("name"):
                aliases.append(t.get("addr:street", ""))
            try:
                lat, lon = n.location.lat, n.location.lon
            except Exception:
                return
            e = make_entry(f"n{n.id}", disp, aliases, cat, lat, lon)
            if e:
                top = cat.split(":")[0]
                stats["poi" if top in POI_KEYS else
                      "place" if top in PLACE_KEYS else
                      "building" if top == "building" else "addr"] += 1
                put(e)

        def way(self, w):
            stats["ways_scanned"] += 1
            t = w.tags
            name = t.get("name")
            # centroid = mean of node locations (cheap; fine for search anchors)
            slat = slon = 0.0
            cnt = 0
            for ref in w.nodes:
                try:
                    loc = ref.location
                    if loc.valid():
                        slat += loc.lat
                        slon += loc.lon
                        cnt += 1
                except Exception:
                    pass
            if not cnt:
                return
            lat, lon = slat / cnt, slon / cnt
            if in_box(lat, lon):
                way_centroids[w.id] = (lat, lon)  # for relation assembly
            if "highway" in t and name:
                cat, disp = f"highway:{t['highway']}", name
            else:
                c = classify(t, name)
                if c is None:
                    return
                cat, disp = c
            aliases = [t[k] for k in ALIAS_TAGS if k in t]
            e = make_entry(f"w{w.id}", disp, aliases, cat, lat, lon)
            if e:
                top = cat.split(":")[0]
                stats["street" if top == "highway" else
                      "poi" if top in POI_KEYS else
                      "place" if top in PLACE_KEYS else
                      "building" if top == "building" else "addr"] += 1
                put(e)

    class RelationHandler(osmium.SimpleHandler):
        """Second pass: named relations (malls, campuses, locality boundaries)

        assembled from member-way centroids collected in pass 1.  Node-only
        member relations are skipped (stations already arrive as nodes).
        """
        def relation(self, r):
            t = r.tags
            if not t.get("name"):
                return
            c = classify(t, t["name"])
            if c is None or c[0].startswith("addr:"):
                return
            cat, disp = c
            slat = slon = 0.0
            cnt = 0
            for m in r.members:
                if m.type == "w" and m.role in ("", "outer"):
                    cxy = way_centroids.get(m.ref)
                    if cxy:
                        slat += cxy[0]
                        slon += cxy[1]
                        cnt += 1
            if not cnt:
                return
            aliases = [t[k] for k in ALIAS_TAGS if k in t]
            e = make_entry(f"r{r.id}", disp, aliases, cat,
                           slat / cnt, slon / cnt)
            if e:
                top = cat.split(":")[0]
                stats["poi" if top in POI_KEYS else
                      "street" if top == "highway" else
                      "place" if top in PLACE_KEYS else
                      "building" if top == "building" else "addr"] += 1
                put(e)

    h = Handler()
    # locations=True materializes node coords onto way node-refs (flex_mem index)
    h.apply_file(pbf_path, locations=True, idx="flex_mem")
    # pass 2 for relations -- member refs need no node location index
    rh = RelationHandler()
    rh.apply_file(pbf_path)
    return list(entries.values()), stats


# ---------------------------------------------------------------------------
# Step 3 -- outputs
# ---------------------------------------------------------------------------

def write_outputs(entries, stats, source_desc: str, extra_stats: dict):
    os.makedirs(CORPUS_DIR, exist_ok=True)
    entries.sort(key=lambda e: (e["category"], e["display"]))

    with gzip.open(OUT_JSONL, "wt", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    with open(OUT_SAMPLE, "w", encoding="utf-8") as f:
        for e in entries[:SAMPLE_LINES]:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    per_cat = {}
    for e in entries:
        top = e["category"].split(":")[0]
        per_cat[top] = per_cat.get(top, 0) + 1
        if not in_box(e["lat"], e["lon"], NCR_BBOX):
            stats["outside_ncr_bbox"] += 1

    gz_size = os.path.getsize(OUT_JSONL)
    sample_size = os.path.getsize(OUT_SAMPLE)
    lines = []
    a = lines.append
    a(f"# Delhi-NCR corpus -- STATS\n")
    a(f"- built: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    a(f"- source: `{source_desc}`")
    a(f"- script: `scripts/build_corpus.py` (pyosmium)")
    a(f"- extraction bbox: lon {EXTRACT_BBOX[0]}-{EXTRACT_BBOX[1]}, lat {EXTRACT_BBOX[2]}-{EXTRACT_BBOX[3]}")
    a(f"- strict NCR bbox (flag-only): lon {NCR_BBOX[0]}-{NCR_BBOX[1]}, lat {NCR_BBOX[2]}-{NCR_BBOX[3]}")
    a(f"- nodes scanned: {stats['nodes_scanned']:,}  |  ways scanned: {stats['ways_scanned']:,}")
    a(f"- **entries emitted: {len(entries):,}**\n")
    a("## Entries per top-level category\n")
    a("| category | count |\n|---|---|")
    for k in sorted(per_cat, key=lambda k: -per_cat[k]):
        a(f"| {k} | {per_cat[k]:,} |")
    a("")
    a("## Flags\n")
    a(f"- entries outside strict NCR bbox (Noida / Ghaziabad / fringe NCR — kept in corpus): "
      f"**{stats['outside_ncr_bbox']:,}**")
    a(f"- deduped (same normalized name + ~75 m cell, richest kept): {stats['deduped']:,}")
    a(f"- untagged/empty display dropped: {stats['empty_name_dropped']:,}")
    a("")
    a("## Artifacts\n")
    a("| file | size |\n|---|---|")
    a(f"| `delhi-corpus.jsonl.gz` | {gz_size/1e6:.1f} MB |")
    a(f"| `delhi-corpus-sample.jsonl` (first {SAMPLE_LINES:,}) | {sample_size/1e6:.2f} MB |")
    for k, v in extra_stats.items():
        a(f"- {k}: {v}")
    a("")
    return lines


# ---------------------------------------------------------------------------
# Step 4 -- mobile gazetteer emit
# ---------------------------------------------------------------------------

def emit_mobile(entries, target: int, gaz_path: str = GAZETTEER_PATH,
                out_path: str = OUT_MOBILE):
    """Write a Mobile-ready gazetteer [{n,c,lat,lon,w,k}] deduped vs bundled."""
    aliases = load_aliases()

    def grid_key(name, lat, lon):
        # normalized name + ~75 m cell
        return (normalize(name, aliases), int(lat / 0.0007), int(lon / 0.0007))

    taken = set()
    merged = []
    if os.path.exists(gaz_path):
        with open(gaz_path, encoding="utf-8") as f:
            gaz = json.load(f)
        for g in gaz:
            taken.add(grid_key(g["n"], g["lat"], g["lon"]))
        merged = [dict(g) for g in gaz]
    else:
        gaz = []

    added = skipped = 0
    new_rows = []
    for e in entries:
        key = grid_key(e["display"], e["lat"], e["lon"])
        if key in taken:
            skipped += 1
            continue
        top, _, sub = e["category"].partition(":")
        c = sub if sub else top
        w = MOBILE_W.get(c, MOBILE_W.get(top, 5))
        new_rows.append({
            "n": e["display"],
            "c": c,
            "lat": e["lat"],
            "lon": e["lon"],
            "w": w,
            "k": 0.9,  # OSM-sourced confidence below bundled gazetteer (~0.97+)
        })
        taken.add(key)
        added += 1

    # keep richest: sort new rows by weight desc, cap total at target
    new_rows.sort(key=lambda r: (-r["w"], r["n"]))
    room = max(0, target - len(merged))
    out = merged + new_rows[:room]
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    return {
        "existing": len(gaz), "added": min(added, room),
        "skipped_dupes": skipped, "total": len(out),
        "size_mb": os.path.getsize(out_path) / 1e6, "path": out_path,
    }


# ---------------------------------------------------------------------------
# Step 5 -- 20-query acceptance scoring
# ---------------------------------------------------------------------------

class SimpleIndex:
    """normalized prefix+token index over display+aliases."""

    def __init__(self, entries, aliases):
        self.entries = entries
        self.aliases = aliases
        self.postings: dict[str, set[int]] = {}
        self.tokens: list[str] = []
        for i, e in enumerate(entries):
            toks = set()
            for s in [e["display"], *e.get("aliases", [])]:
                toks.update(norm_tokens(s, aliases))
            for t in toks:
                self.postings.setdefault(t, set()).add(i)
        self.tokens = sorted(self.postings)

    def candidates(self, qtok):
        """indices whose tokens == qtok or startswith qtok (prefix)."""
        out = set()
        if qtok in self.postings:
            out |= self.postings[qtok]
        lo = bisect.bisect_left(self.tokens, qtok)
        hi = bisect.bisect_left(self.tokens, qtok + "\xff")
        for t in self.tokens[lo:hi]:
            out |= self.postings[t]
        return out

    def search(self, query, k=3):
        qts = norm_tokens(query, self.aliases)
        if not qts:
            return []
        n_entries = len(self.entries)
        denom = max(len(qts) - 1, 1)
        scores: dict[int, float] = {}
        for j, qt in enumerate(qts):
            cands = self.candidates(qt)
            exact = self.postings.get(qt, set())
            # idf: rare query tokens weigh more than common ones like "metro"
            w = 1.0 + math.log(1.0 + n_entries / max(len(cands), 1))
            # leading tokens carry the entity's distinctive name -> weigh more
            w *= 1.6 - 0.6 * (j / denom)
            for i in cands:
                scores[i] = scores.get(i, 0.0) + (w if i in exact else 0.7 * w)
        # precision bonus: prefer short clean names over long addr strings
        for i in list(scores):
            dtok = norm_tokens(self.entries[i]["display"], self.aliases)
            scores[i] += 0.5 * min(1.0, len(qts) / max(len(dtok), 1))
            # positional alignment: query token i vs display token i
            for j, qt in enumerate(qts):
                if j < len(dtok) and dtok[j].startswith(qt):
                    scores[i] += 0.25
        ranked = sorted(
            scores.items(),
            key=lambda kv: (-kv[1], self.entries[kv[0]]["display"]),
        )
        return [(self.entries[i], s) for i, s in ranked[:k]]


# expected -> list of acceptable normalized token-sets (any one fully ⊆
# candidate's normalized token set counts as a hit)
EXPECTED_SETS = {
    "select citywalk": [{"select", "citywalk"}, {"citywalk"}],
    "lajpat nagar 4": [{"lajpat", "nagar", "iv"}, {"lajpat", "nagar", "4"},
                        {"lajpat", "nagar", "4th"}],
    "haldiram chandni": [{"haldirams"}, {"haldiram"}],
    "dlf cyber hub": [{"dlf", "cyber", "hub"}, {"cyber", "hub"}, {"cyberhub"}],
    "chandni chok": [{"chandni", "chowk"}],
    "cp": [{"connaught", "place"}],
    "gk 2": [{"greater", "kailash", "ii"}, {"greater", "kailash", "2"},
             {"gk", "2"}, {"gk", "ii"}],
    "sarojni nagar": [{"sarojini", "nagar"}],
    "aiims metro": [{"aiims"}],
    "kashmere gate": [{"kashmere", "gate"}, {"kashmiri", "gate"}, {"isbt"}],
    "india gate": [{"india", "gate"}],
    "noida sec 18": [{"noida", "sector", "18"}, {"sector", "18"},
                     {"noida", "18"}],
    "hauz khas": [{"hauz", "khas"}],
    "karol bag": [{"karol", "bagh"}],
    "dtu": [{"delhi", "technological", "university"}, {"dtu"}],
    "rajiv chowk gate 5": [{"rajiv", "chowk", "5"}, {"rajiv", "chowk"}],
    "saket pvr": [{"pvr"}, {"select", "citywalk"}, {"saket"}],
    "connaught plce": [{"connaught", "place"}],
    "nehru place": [{"nehru", "place"}],
    "vaishali metro": [{"vaishali"}],
}


def load_queries(path=QUERIES_PATH):
    qs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            q, exp = line.split("\t", 1)
            qs.append((q.strip(), exp.strip()))
    return qs


def entry_tokens(e, aliases):
    toks = set()
    for s in [e["display"], *e.get("aliases", [])]:
        toks.update(norm_tokens(s, aliases))
    return toks


def run_score(entries, aliases, use_aliases=True):
    al = aliases if use_aliases else {}
    idx = SimpleIndex(entries, al)
    rows = []
    for q, expected in load_queries():
        res = idx.search(q, k=3)
        # normalize each expected token through the same alias map
        sets = [{tok for t in req for tok in norm_tokens(t, al)}
                for req in EXPECTED_SETS.get(q, [])]
        hit = False
        for e, _s in res:
            toks = entry_tokens(e, al)
            if any(req <= toks for req in sets):
                hit = True
                break
        rows.append({
            "query": q, "expected": expected, "hit": hit,
            "top3": [(e["display"], e["category"]) for e, _ in res],
        })
    return rows


def append_score_stats(lines, rows_with, rows_without):
    a = lines.append
    a("\n## 20-query acceptance score (tests/search_queries.txt)\n")
    a("Simple Python index: normalized token + prefix match over display+aliases, "
      "top-3 must contain expected place.\n")
    hits_with = sum(r["hit"] for r in rows_with)
    hits_without = sum(r["hit"] for r in rows_without)
    a(f"**Score with alias table: {hits_with}/20**  |  without aliases: {hits_without}/20\n")
    a("| query | expected | hit | needs alias | top-3 |")
    a("|---|---|---|---|---|")
    for rw, rn in zip(rows_with, rows_without):
        need = "yes" if rw["hit"] and not rn["hit"] else ""
        top3 = "; ".join(f"{d} ({c.split(':')[0]})" for d, c in rw["top3"])
        a(f"| {rw['query']} | {rw['expected']} | {'HIT' if rw['hit'] else 'MISS'} | "
          f"{need} | {top3} |")
    need_list = [r["query"] for r, rn in zip(rows_with, rows_without)
                 if r["hit"] and not rn["hit"]]
    miss_list = [r["query"] for r in rows_with if not r["hit"]]
    a("")
    a(f"- queries that NEED aliases.json to hit: {', '.join(need_list) or 'none'}")
    a(f"- misses (corpus/index gaps): {', '.join(miss_list) or 'none'}")
    a("")
    return hits_with


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", help="path to a local .osm.pbf (skip download)")
    ap.add_argument("--score", action="store_true",
                    help="only re-run the 20-query scoring on the existing corpus")
    ap.add_argument("--emit-mobile", action="store_true",
                    help="also write the Mobile-ready ~150k gazetteer JSON")
    ap.add_argument("--mobile-target", type=int, default=150000)
    args = ap.parse_args()

    aliases = load_aliases()

    if args.score:
        entries = []
        with gzip.open(OUT_JSONL, "rt", encoding="utf-8") as f:
            for line in f:
                entries.append(json.loads(line))
        lines = []
        rows_with = run_score(entries, aliases, True)
        rows_without = run_score(entries, aliases, False)
        append_score_stats(lines, rows_with, rows_without)
        with open(OUT_STATS, "a", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print("\n".join(lines))
        return 0

    # --- download ---
    if args.input:
        pbf, src = args.input, f"local:{args.input}"
    else:
        pbf, src = download_pbf()
    if pbf is None:
        os.makedirs(CORPUS_DIR, exist_ok=True)
        with open(OUT_STATS, "w", encoding="utf-8") as f:
            f.write("# Delhi-NCR corpus -- STATS\n\n## DOWNLOAD-FAILED\n\n"
                    f"Tried: {', '.join(PBF_CANDIDATES)}\n\nLast error: {src}\n")
        print("DOWNLOAD-FAILED:", src, file=sys.stderr)
        return 2

    print(f"parsing {pbf} ({os.path.getsize(pbf)/1e6:.0f} MB) ...", flush=True)
    entries, stats = build_corpus(pbf)
    extra = {}
    lines = write_outputs(entries, stats, src, extra)

    # --- score ---
    rows_with = run_score(entries, aliases, True)
    rows_without = run_score(entries, aliases, False)
    append_score_stats(lines, rows_with, rows_without)

    # --- mobile emit ---
    if args.emit_mobile:
        m = emit_mobile(entries, args.mobile_target)
        lines.append("\n## Mobile gazetteer emit\n")
        lines.append(f"- output: `{os.path.relpath(m['path'], REPO)}` "
                     f"({m['size_mb']:.1f} MB)")
        lines.append(f"- bundled gazetteer kept: {m['existing']:,}")
        lines.append(f"- new OSM rows added: {m['added']:,} "
                     f"(skipped {m['skipped_dupes']:,} name+75 m dupes)")
        lines.append(f"- **total: {m['total']:,}** (target {args.mobile_target:,})")

    with open(OUT_STATS, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
