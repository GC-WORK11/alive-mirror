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
       - POIs        (amenity / shop / tourism / leisure / office / craft /
                      healthcare / emergency / club / indoor tags)
       - places      (place / railway / public_transport / aeroway / historic /
                      boundary + landuse / natural / waterway / man_made /
                      power / junction / barrier / entrance / military)
       - buildings   (building=* + name, incl. building:part)
       - streets     (highway=* + name, centroid of the way; bus stops)
       - addr blocks (addr:place / addr:subdistrict / addr:housenumber /
                      addr:block where enough context makes it displayable)
       - misc        (name=* on anything else -- "misc:named")
     Every entry -> {id, display, aliases[], category, lat, lon, popularity,
     source, sources[], synthetic} (schema per docs/plan/08-cpp-engine.md
     "Search index design" + provenance fields).
  3. Merge auxiliary sources (all real named entities, no fabrication):
       - GeoNames IN dump (download.geonames.org/export/dump/IN.zip,
         sliced to the extraction box; alternatenames -> aliases;
         population -> popularity)
       - Wikidata JSONL written by scripts/fetch_wikidata.py
         (server/data/corpus/aux/*.jsonl -- provenance per row)
     Dedupe key is normalized display + ~75 m cell; on collision the
     richer row wins and `sources`/`aliases` are unioned.
  4. Generate `synthetic:true` rows ONLY for sector/block designators that
     are attested in the merged data ("Sector 14, NOIDA" -> canonical
     "Noida Sector 14"; "Block C, X" -> "C Block, X"), located at the mean
     of the attesting features' coordinates.  No designator is invented.
  5. Emit  server/data/corpus/delhi-corpus.jsonl.gz  (one JSON per line, gzip)
           server/data/corpus/delhi-corpus-sample.jsonl  (committed, <=5 MB)
           server/data/corpus/STATS.md
           docs/plan/corpus-report.md   (counts by source, dedupe, scores)
  6. --emit-mobile also writes a Mobile-ready gazetteer (same schema as
     Mobile/assets/delhi-gazetteer.json: {n, c, lat, lon, w, k}) deduped
     against the bundled 26.5k gazetteer by normalized-name + 75 m radius,
     capped at --mobile-target entries (default 150k).
  7. --score loads the corpus + aliases.json and scores
     tests/search_queries.txt with a simple normalized prefix+token index;
     --stats summarizes the existing corpus file.

Usage:
    tools/corpus-venv/bin/python scripts/build_corpus.py --emit-mobile  # full run
    tools/corpus-venv/bin/python scripts/build_corpus.py --score    # rescore only
    tools/corpus-venv/bin/python scripts/build_corpus.py --stats    # count sources
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
OUT_REPORT = os.path.join(REPO, "docs", "plan", "corpus-report.md")

# Auxiliary merge inputs.  aux/*.jsonl rows share the entry schema plus
# provenance (written by scripts/fetch_wikidata.py and friends).
AUX_DIR = os.path.join(CORPUS_DIR, "aux")

# GeoNames all-India dump; sliced to EXTRACT_BBOX at merge time.
GEONAMES_URL = "https://download.geonames.org/export/dump/IN.zip"
GEONAMES_TXT = os.path.join(DL_DIR, "geonames", "IN.txt")

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
            "healthcare", "emergency", "club")

# Named feature classes needed for nav-grade recall (metro stations,
# localities, monuments). Only extracted when they carry a name.
PLACE_KEYS = ("place", "railway", "public_transport", "aeroway", "historic",
              "boundary")

# Extra named-feature keys folded into the corpus (Delhi OSM uses these for
# colonies, parks-as-landuse, drains, gates, substations, junctions...).
# Category is "<key>:<value>"; they still require name=*.
FEATURE_KEYS = ("landuse", "natural", "waterway", "man_made", "power",
                "junction", "barrier", "entrance", "military", "indoor",
                "aerialway", "building:part")

# feature-code -> corpus category for the GeoNames dump.
GEONAMES_CAT = {
    "PPL": "locality", "PPLX": "locality", "PPLA": "locality",
    "PPLA2": "locality", "PPLA3": "locality", "PPLA4": "locality",
    "PPLC": "locality", "PPLF": "locality", "PPLG": "locality",
    "PPLL": "locality", "PPLQ": "locality", "PPLR": "locality",
    "PPLS": "locality", "PPLW": "locality", "STLMT": "locality",
    "ADM2": "district", "ADM3": "district", "ADM4": "district",
    "ADMD": "district", "ADMF": "office", "PRSH": "district",
    "LCTY": "locality", "RESF": "forest", "PRK": "park", "AREA": "district",
    "HTL": "hotel", "RSTN": "station", "RSTNQ": "station", "RSTP": "station",
    "RSTPQ": "station", "BUSTN": "bus_station", "BUSTP": "bus_station",
    "AIRP": "airport", "AIRF": "airport", "AIRH": "airport",
    "MALL": "mall", "MKT": "market", "TMPL": "temple", "SHRE": "shrine",
    "MSQE": "mosque", "CH": "church", "HOSP": "hospital", "HSPC": "hospital",
    "UNIV": "university", "SCH": "school", "SCHC": "college",
    "MNMT": "monument", "RUIN": "monument", "TMB": "monument",
    "MUS": "museum", "GDN": "park", "ZOO": "zoo", "STDM": "stadium",
    "CNL": "canal", "CNLQ": "canal", "STM": "stream", "STMD": "stream",
    "STMC": "stream", "STMI": "stream", "STMQ": "stream", "LK": "lake",
    "RSV": "lake", "BLDG": "building", "ITTR": "building",
    "RR": "street", "RD": "street", "MT": "hill", "HLL": "hill",
    "POST": "office", "PO": "office", "INSM": "military",
    "EST": "district", "ESTX": "district", "RNCH": "farm",
}

# Confidence (k) per source for the mobile gazetteer.
SOURCE_K = {"osm": 0.90, "wikidata": 0.92, "geonames": 0.88,
            "synthetic": 0.80, "bundled": 0.97}

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
    # aux-source + widened-OSM categories
    "city": 9, "town": 7, "village": 6, "locality": 7, "district": 6,
    "neighbourhood": 7, "suburb": 7, "monument": 8, "museum": 7,
    "park": 6, "garden": 6, "temple": 6, "mosque": 5, "church": 5,
    "gurudwara": 5, "shrine": 5, "school": 6, "college": 7,
    "institute": 6, "library": 5, "stadium": 7, "zoo": 7,
    "office": 5, "embassy": 6, "police": 5, "fire": 5, "prison": 2,
    "cemetery": 3, "water": 3, "canal": 2, "stream": 2, "lake": 4,
    "forest": 4, "hill": 4, "bridge": 4, "farm": 3, "military": 2,
    "block": 4, "tehsil": 4, "complex": 4, "named": 3, "misc": 2,
    "gate": 5, "entrance": 3, "junction": 4, "substation": 2,
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
            raw = json.load(f)
    except FileNotFoundError:
        return {}
    # Wrapped form: {"comment": ..., "aliases": {token: [phrases]}} — the first
    # phrase is the canonical form; the rest are expansion-only alternatives.
    if isinstance(raw, dict) and isinstance(raw.get("aliases"), dict):
        raw = raw["aliases"]
    out = {}
    for k, v in raw.items():
        if k.startswith("_"):
            continue
        if isinstance(v, list):
            if v:
                out[k] = v[0]
        else:
            out[k] = v
    return out


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


def make_entry(osm_id, display, aliases, category, lat, lon,
               source="osm", synthetic=False, popularity=0):
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
        "popularity": popularity,
        "source": source,
        "sources": [source],
        "synthetic": synthetic,
    }


def merge_into(old: dict, new: dict) -> dict:
    """Union-merge a dedupe collision: keep the richer display row, union
    aliases + sources, take max popularity."""
    for a in new["aliases"]:
        if a.lower() not in {x.lower() for x in old["aliases"]} \
                and a.lower() != old["display"].lower():
            old["aliases"].append(a)
    if new["display"].lower() not in {old["display"].lower()} | \
            {x.lower() for x in old["aliases"]}:
        old["aliases"].append(new["display"])
    for s in new.get("sources", [new.get("source", "osm")]):
        if s not in old["sources"]:
            old["sources"].append(s)
    old["popularity"] = max(old.get("popularity", 0), new.get("popularity", 0))
    old["synthetic"] = old.get("synthetic", False) and new.get("synthetic", False)
    return old


def top_stat_key(cat: str) -> str:
    top = cat.split(":")[0]
    return ("poi" if top in POI_KEYS else
            "place" if top in PLACE_KEYS or top in FEATURE_KEYS else
            "building" if top == "building" else
            "addr" if top == "addr" else
            "street" if top == "highway" else "misc")


def dedupe_key(entry) -> tuple:
    """Normalized display + ~75 m cell (0.0007 deg ~ 77 m lat)."""
    return (
        normalize(entry["display"]),
        int(entry["lat"] / 0.0007),
        int(entry["lon"] / 0.0007),
    )


def put_entry(entries: dict, stats: dict, entry) -> bool:
    """Dedupe-insert into entries map. Returns True if a new key was added."""
    if entry is None:
        stats["empty_name_dropped"] = stats.get("empty_name_dropped", 0) + 1
        return False
    if not in_box(entry["lat"], entry["lon"]):
        return False
    key = dedupe_key(entry)
    old = entries.get(key)
    if old is None:
        entries[key] = entry
        return True
    stats["deduped"] = stats.get("deduped", 0) + 1
    if len(entry["aliases"]) > len(old["aliases"]):
        merge_into(entry, old)
        entries[key] = entry
    else:
        merge_into(old, entry)
    return False


def compose_addr(t) -> str | None:
    """Display string for an addr object, or None if it can't be named.

    Real addressing convention: housenumber + street/place/block context.
    A bare housenumber ("12") is not findable -- skipped.
    """
    hn = (t.get("addr:housenumber") or "").strip()
    if hn in ("-", "—", "?"):
        hn = ""
    street = t.get("addr:street", "").strip()
    place = t.get("addr:place", "").strip()
    block = t.get("addr:block", "").strip()
    sub = t.get("addr:subdistrict", "").strip()
    ctx = street or place or sub
    if hn and ctx:
        return f"{hn} {ctx}"
    if hn and block:
        return f"{hn} Block {block}"
    if block and ctx:
        return f"Block {block}, {ctx}"
    return None


def build_corpus(pbf_path: str):
    """Parse the PBF, return (entries, stats_dict)."""
    import osmium  # pyosmium, in tools/corpus-venv

    entries: dict[tuple, dict] = {}  # dedupe key -> entry
    way_centroids: dict[int, tuple] = {}  # way id -> (lat, lon), in-box only
    stats = {
        "nodes_scanned": 0, "ways_scanned": 0,
        "poi": 0, "building": 0, "street": 0, "addr": 0, "place": 0,
        "misc": 0,
        "outside_ncr_bbox": 0, "deduped": 0, "empty_name_dropped": 0,
    }

    def put(entry):
        put_entry(entries, stats, entry)

    def classify(t):
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
            if t.get("highway") == "bus_stop":
                return "highway:bus_stop", name
            for k in FEATURE_KEYS:
                if k in t:
                    return f"{k}:{t[k]}", name
            # name on anything else is still a named entity
            return "misc:named", name
        if t.get("addr:housename") and re.search(r"[a-zA-Z]",
                                                 t["addr:housename"]):
            return "building:housename", t["addr:housename"]
        if "addr:place" in t:
            return "addr:place", t["addr:place"]
        if "addr:subdistrict" in t:
            return "addr:subdistrict", t["addr:subdistrict"]
        if t.get("addr:full"):
            return "addr:address", t["addr:full"]
        if t.get("addr:housenumber") or t.get("addr:block"):
            disp = compose_addr(t)
            if disp:
                return "addr:address", disp
        # ref-only named-class roads: "NH 9"/"SH 15" are real searched names
        # (restricted to road classes people navigate by; crossing refs like
        # "NHPC_CHOWK_PEDESTRIAN_S3" are survey codes, not place names)
        if t.get("highway") in ("motorway", "trunk", "primary", "secondary",
                                "tertiary") and t.get("ref"):
            return f"highway:{t['highway']}", t["ref"].replace(";", " / ")
        return None

    class Handler(osmium.SimpleHandler):
        def node(self, n):
            stats["nodes_scanned"] += 1
            t = n.tags
            c = classify(t)
            if c is None:
                return
            cat, disp = c
            aliases = [t[k] for k in ALIAS_TAGS if k in t]
            if cat == "addr:address" and not t.get("name"):
                for k in ("addr:street", "addr:place", "addr:block",
                          "addr:subdistrict"):
                    if t.get(k):
                        aliases.append(t[k])
            try:
                lat, lon = n.location.lat, n.location.lon
            except Exception:
                return
            e = make_entry(f"n{n.id}", disp, aliases, cat, lat, lon)
            if e:
                stats[top_stat_key(cat)] += 1
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
                c = classify(t)
                if c is None:
                    return
                cat, disp = c
            aliases = [t[k] for k in ALIAS_TAGS if k in t]
            e = make_entry(f"w{w.id}", disp, aliases, cat, lat, lon)
            if e:
                stats[top_stat_key(cat)] += 1
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
            c = classify(t)
            if c is None or c[0].startswith("addr:") or c[0] == "misc:named":
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
                stats[top_stat_key(cat)] += 1
                put(e)

    h = Handler()
    # locations=True materializes node coords onto way node-refs (flex_mem index)
    h.apply_file(pbf_path, locations=True, idx="flex_mem")
    # pass 2 for relations -- member refs need no node location index
    rh = RelationHandler()
    rh.apply_file(pbf_path)
    return entries, stats


# ---------------------------------------------------------------------------
# Step 2b -- GeoNames all-India dump, sliced to the extraction box
# ---------------------------------------------------------------------------

def download_geonames() -> str | None:
    """Ensure dl/geonames/IN.txt exists; download IN.zip if not."""
    if os.path.exists(GEONAMES_TXT):
        return GEONAMES_TXT
    os.makedirs(os.path.dirname(GEONAMES_TXT), exist_ok=True)
    zip_path = os.path.join(DL_DIR, "IN.zip")
    try:
        req = urllib.request.Request(GEONAMES_URL,
                                     headers={"User-Agent": "alive-corpus/1.0"})
        with urllib.request.urlopen(req, timeout=120) as r, \
                open(zip_path, "wb") as out:
            out.write(r.read())
        import zipfile
        with zipfile.ZipFile(zip_path) as z:
            z.extract("IN.txt", os.path.dirname(GEONAMES_TXT))
        return GEONAMES_TXT
    except Exception as e:  # noqa: BLE001
        print(f"geonames download failed: {e}", file=sys.stderr)
        return None


def merge_geonames(entries: dict, stats: dict) -> dict:
    """Slice dl/geonames/IN.txt to EXTRACT_BBOX and merge into entries.

    GeoNames columns: geonameid, name, asciiname, alternatenames, lat, lon,
    fclass, fcode, country, cc2, admin1..4, population, elevation, dem, tz,
    modified.  Alternatenames become aliases (they carry Hindi + spelling
    variants); population -> popularity.
    """
    gstats = {"in_box": 0, "added": 0, "deduped_into": 0}
    path = download_geonames()
    if not path:
        gstats["unavailable"] = True
        return gstats
    with open(path, encoding="utf-8") as f:
        for line in f:
            c = line.rstrip("\n").split("\t")
            if len(c) < 19:
                continue
            try:
                lat, lon = float(c[4]), float(c[5])
            except ValueError:
                continue
            if not in_box(lat, lon):
                continue
            gstats["in_box"] += 1
            name = c[2] or c[1]  # asciiname preferred (folded, stable)
            if not name.strip():
                continue
            alts = [a for a in c[3].split(",") if a.strip()]
            try:
                pop = int(c[14])
            except ValueError:
                pop = 0
            # popularity is a 0..1 scorer weight — write the log-scaled
            # value (Delhi-scale ceiling) so raw population can't become
            # a million-point term downstream (alive_core_ref._norm_popularity
            # re-guards at index load for older corpora)
            pop_w = min(1.0, math.log1p(pop) / math.log1p(20_000_000.0))
            cat = GEONAMES_CAT.get(c[7], f"geonames:{c[7] or c[6]}")
            e = make_entry(f"gn:{c[0]}", name, alts, cat, lat, lon,
                           source="geonames", popularity=pop_w)
            if e is None:
                continue
            e["geonames"] = c[0]
            if put_entry(entries, stats, e):
                gstats["added"] += 1
            else:
                gstats["deduped_into"] += 1
    return gstats


# ---------------------------------------------------------------------------
# Step 2c -- aux/*.jsonl merge (Wikidata etc.)
# ---------------------------------------------------------------------------

def merge_aux(entries: dict, stats: dict, aux_dir: str = AUX_DIR) -> dict:
    """Merge every aux/*.jsonl file (same entry schema + provenance)."""
    astats = {"files": [], "rows": 0, "added": 0, "deduped_into": 0}
    if not os.path.isdir(aux_dir):
        return astats
    for fn in sorted(os.listdir(aux_dir)):
        if not fn.endswith(".jsonl"):
            continue
        path = os.path.join(aux_dir, fn)
        rows = added = deduped = 0
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if not (e.get("display") and isinstance(e.get("lat"), (int, float))):
                    continue
                e.setdefault("aliases", [])
                e.setdefault("popularity", 0)
                e.setdefault("source", fn.rsplit(".", 1)[0])
                e.setdefault("sources", [e["source"]])
                e.setdefault("synthetic", False)
                rows += 1
                if put_entry(entries, stats, e):
                    added += 1
                else:
                    deduped += 1
        astats["files"].append(f"{fn}:{rows:,}r/+{added:,}")
        astats["rows"] += rows
        astats["added"] += added
        astats["deduped_into"] += deduped
    return astats


# ---------------------------------------------------------------------------
# Step 2d -- attested sector/block canonicalization (synthetic:true)
# ---------------------------------------------------------------------------

# "Dwarka Sector 12" / "Rohini Sector 7" / "Noida Sec-18" / "Sector 14, NOIDA".
# The designator word and its number are separate: digits may fuse
# ("Sector63") but a letter designator must be separated -- otherwise
# "Barola PHC" (Primary Health Centre) would fake-match "Phase C".
_KIND = r"(?:sector|sec|sect|pocket|pkt|block|blk|phase|ph)"
_SECT_PREFIX = re.compile(
    r"^(.+?)[\s,]+" + _KIND + r"[\s\-–]*([0-9]{1,3}[a-zA-Z]?)\b"
    r"|^(.+?)[\s,]+" + _KIND + r"[\s\-–]+([a-zA-Z])\b", re.IGNORECASE)
_SECT_SUFFIX = re.compile(
    r"^" + _KIND + r"[\s\-–]*([0-9]{1,3}[a-zA-Z]?)\s*[,;]\s*(.+?)\s*$"
    r"|^" + _KIND + r"[\s\-–]+([a-zA-Z])\s*[,;]\s*(.+?)\s*$", re.IGNORECASE)
# "Block C, Lajpat Nagar" / "C Block, Kalkaji" / "J-Block, Saket"
_BLOCK_PREFIX = re.compile(
    r"^(?:block|blk|pocket|pkt)[\s\-]*([a-zA-Z0-9]{1,3})\s*[,;]\s*(.+?)\s*$",
    re.IGNORECASE)
_BLOCK_SUFFIX = re.compile(
    r"^([a-zA-Z0-9]{1,3})[\s\-]*(?:block|pocket|pkt)\s*[,;]\s*(.+?)\s*$",
    re.IGNORECASE)

_LOCALITY_TOPS = {"place", "boundary", "addr", "landuse", "amenity",
                  "office", "leisure", "tourism"}

# a "locality" that is itself a designator phrase (e.g. "A Block",
# "A-Block Park") is not a sector parent -- it is a block already.
_DESIGNATOR_WORDS = {"sector", "sec", "sect", "pocket", "pkt",
                     "block", "blk", "phase", "ph"}


def _locality_names(entries) -> set:
    """Normalized names worth being a sector/block parent: real places only."""
    names = set()
    for e in entries.values():
        if e["category"].split(":")[0] in _LOCALITY_TOPS:
            for s in [e["display"], *e.get("aliases", [])]:
                n = normalize(s)
                if 3 <= len(n) <= 40 and not any(
                        ch.isdigit() for ch in n):
                    names.add(n)
    return names


def _loc_ok(norm_loc: str, locnames: set) -> bool:
    return (norm_loc in locnames
            and not (_DESIGNATOR_WORDS & set(norm_loc.split())))


def synth_sector_entries(entries: dict) -> list:
    """Canonical 'Locality Sector N' / 'X Block, Locality' rows for
    designators attested in real source data.  Each row carries
    synthetic:true, source:'synthetic', sources including the attesting
    sources, and lat/lon = mean of attesting features (never invented)."""
    locnames = _locality_names(entries)
    attested: dict[str, dict] = {}  # canonical_norm -> {display, coords, ...}

    _KIND_WORD = {"sec": "Sector", "sect": "Sector", "sector": "Sector",
                  "pkt": "Pocket", "pocket": "Pocket",
                  "blk": "Block", "block": "Block",
                  "ph": "Phase", "phase": "Phase"}

    def note(canon, kind, alias_forms, lat, lon, src):
        key = normalize(canon)
        a = attested.setdefault(key, {
            "display": canon, "kind": kind, "aliases": set(),
            "coords": [], "srcs": set()})
        a["coords"].append((lat, lon))
        a["srcs"].add(src)
        for af in alias_forms:
            if af and af.lower() != canon.lower():
                a["aliases"].add(af)

    def kind_of(s, fallback="block"):
        m = re.search(_KIND, s, re.IGNORECASE)
        return _KIND_WORD.get(m.group(0).lower(), fallback.title()) \
            if m else fallback.title()

    for e in entries.values():
        if e.get("synthetic"):
            continue
        src = e.get("source", "osm")
        forms = [e["display"], *e.get("aliases", [])]
        for s in forms:
            s = s.strip()
            m = _SECT_PREFIX.match(s)
            if m:
                loc = " ".join((m.group(1) or m.group(3)).split())
                num = m.group(2) or m.group(4)
                if num and _loc_ok(normalize(loc), locnames):
                    kind = kind_of(s)
                    canon = f"{loc} {kind} {num.upper()}"
                    note(canon, kind, [s, f"{kind} {num}, {loc}"],
                         e["lat"], e["lon"], src)
                    continue
            m = _SECT_SUFFIX.match(s)
            if m:
                num = m.group(1) or m.group(3)
                loc = " ".join((m.group(2) or m.group(4) or "").split())
                if loc and _loc_ok(normalize(loc), locnames):
                    kind = kind_of(s)
                    canon = f"{loc} {kind} {num.upper()}"
                    note(canon, kind, [s], e["lat"], e["lon"], src)
                    continue
            m = _BLOCK_PREFIX.match(s) or _BLOCK_SUFFIX.match(s)
            if m and _loc_ok(normalize(m.group(2)), locnames):
                blk, loc = m.group(1).upper(), " ".join(m.group(2).split())
                canon = f"{blk} Block, {loc}"
                note(canon, "Block",
                     [s, f"{loc} {blk} Block", f"{loc} Block {blk}"],
                     e["lat"], e["lon"], src)

    out = []
    for key, a in attested.items():
        lat = sum(c[0] for c in a["coords"]) / len(a["coords"])
        lon = sum(c[1] for c in a["coords"]) / len(a["coords"])
        out.append({
            "id": f"syn:{key.replace(' ', '_')}",
            "display": a["display"],
            "aliases": sorted(a["aliases"]),
            "category": f"synthetic:{a['kind'].lower()}",
            "lat": round(lat, 6), "lon": round(lon, 6),
            "popularity": 0,
            "source": "synthetic",
            "sources": ["synthetic", *sorted(a["srcs"])],
            "synthetic": True,
        })
    return out


def merge_synthetic(entries: dict, stats: dict) -> dict:
    """Generate + merge attested canonical sector/block rows.

    Neighbour-aware dedupe: if the canonical normalized name already exists
    within ~500 m, fold aliases into the existing row instead of adding a
    near-duplicate."""
    sstats = {"attested": 0, "added": 0, "merged_nearby": 0}
    synthetics = synth_sector_entries(entries)
    sstats["attested"] = len(synthetics)

    # name -> cells index for the ~500 m neighbour check
    name_cells: dict[str, list] = {}
    for e in entries.values():
        n = normalize(e["display"])
        cell = (int(e["lat"] / 0.0007), int(e["lon"] / 0.0007))
        name_cells.setdefault(n, []).append((cell, e))

    for e in synthetics:
        n = normalize(e["display"])
        cell = (int(e["lat"] / 0.0007), int(e["lon"] / 0.0007))
        near = None
        for oc, oe in name_cells.get(n, []):
            if abs(oc[0] - cell[0]) <= 6 and abs(oc[1] - cell[1]) <= 6:
                near = oe
                break
        if near is not None:
            merge_into(near, e)
            sstats["merged_nearby"] += 1
            continue
        if put_entry(entries, stats, e):
            sstats["added"] += 1
            name_cells.setdefault(n, []).append((cell, e))
        else:
            sstats["merged_nearby"] += 1
    return sstats


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
    per_src = {}
    for e in entries:
        top = e["category"].split(":")[0]
        per_cat[top] = per_cat.get(top, 0) + 1
        for s in e.get("sources", [e.get("source", "osm")]):
            per_src[s] = per_src.get(s, 0) + 1
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
    a("## Entries per source (rows may carry >1 source after dedupe)\n")
    a("| source | entries |\n|---|---|")
    for k in sorted(per_src, key=lambda k: -per_src[k]):
        a(f"| {k} | {per_src[k]:,} |")
    a("")
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
        # a sub-category only earns `c` when it is a clean snake token —
        # raw tag values ("Ayurvedic Hospital", "part:yes", "3-4_floors")
        # fall back to the top-level bucket so the app never renders
        # unfiltered OSM values as subtitles
        clean_sub = bool(re.fullmatch(r"[a-z][a-z0-9_]*", sub)) \
            and sub not in {"yes", "no", "fixme", "unknown"}
        c = sub if clean_sub else top
        w = MOBILE_W.get(c, MOBILE_W.get(top, 5))
        new_rows.append({
            "n": e["display"],
            "c": c,
            "lat": e["lat"],
            "lon": e["lon"],
            "w": w,
            # source-aware confidence; bundled gazetteer stays ~0.97+
            "k": SOURCE_K.get(e.get("source", "osm"), 0.85),
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
# corpus report (docs/plan/corpus-report.md)
# ---------------------------------------------------------------------------

def write_report(stats, gstats, astats, sstats, source_desc,
                 entries, hits_with, hits_without, mobile=None,
                 prev_total=None, n_osm=None):
    """docs/plan/corpus-report.md -- the honest source/dedup/score summary."""
    per_src = {}
    n_synth = 0
    for e in entries:
        if e.get("synthetic"):
            n_synth += 1
        for s in e.get("sources", [e.get("source", "osm")]):
            per_src[s] = per_src.get(s, 0) + 1

    L = []
    a = L.append
    a("# Delhi-NCR corpus report\n")
    a(f"Built: {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}  |  "
      f"OSM source: `{source_desc}`  |  script: `scripts/build_corpus.py`\n")
    a("## Sources\n")
    a("| source | rows in | merged into existing | new entries | provenance |")
    a("|---|---|---|---|---|")
    a(f"| OSM (Geofabrik northern-zone PBF) | {n_osm if n_osm is not None else 0:,} "
      f"in extraction box (post-dedupe) | — | base layer | "
      f"`source:osm`, id n/w/r<osmid> |")
    if gstats and not gstats.get("unavailable"):
        a(f"| GeoNames IN.zip | {gstats['in_box']:,} in box | "
          f"{gstats['deduped_into']:,} | {gstats['added']:,} | "
          f"`source:geonames`, id gn:<geonameid> |")
    else:
        a("| GeoNames IN.zip | — | — | 0 | download unavailable |")
    if astats and astats["files"]:
        a(f"| aux/*.jsonl ({', '.join(astats['files'])}) | {astats['rows']:,} | "
          f"{astats['deduped_into']:,} | {astats['added']:,} | per-row `source`/`wikidata` |")
    if sstats:
        a(f"| synthetic (attested sector/block canonicalization) | "
          f"{sstats['attested']:,} attested | {sstats['merged_nearby']:,} folded | "
          f"{sstats['added']:,} | `synthetic:true`, coords = mean of attesting features |")
    a("")
    a(f"**Total entries: {len(entries):,}**"
      + (f"  (previous build: {prev_total:,})" if prev_total else "") + "\n")
    if mobile:
        a(f"T0/T1 ceiling check: corpus {len(entries):,} + bundled "
          f"{mobile['existing']:,} -> gazetteer {mobile['total']:,} "
          f"vs ~150k ambition. The gap to 150k is real, not padded -- "
          f"OSM Delhi named features + GeoNames + Wikidata + attested "
          f"sector/block canonicals exhaust the legitimate sources; "
          f"the rest must come from Amazon T2 cache-back or licensed data.\n")
    a("| per-source membership | entries |")
    a("|---|---|")
    for k in sorted(per_src, key=lambda k: -per_src[k]):
        a(f"| {k} | {per_src[k]:,} |")
    a(f"| rows flagged synthetic:true | {n_synth:,} |")
    a("")
    a("## Dedupe\n")
    a(f"- same normalized name + ~75 m cell, richest row kept, aliases+sources "
      f"unioned: {stats['deduped']:,} merges")
    a("")
    a("## 20-query score (tests/search_queries.txt)\n")
    a(f"- **with aliases.json: {hits_with}/20** — without: {hits_without}/20")
    a("")
    if mobile:
        a("## Mobile gazetteer\n")
        a(f"- bundled kept {mobile['existing']:,} + new {mobile['added']:,} "
          f"= **{mobile['total']:,}** ({mobile['size_mb']:.1f} MB, "
          f"dedupe-skipped {mobile['skipped_dupes']:,})")
        a("")
    a("## Reproduce\n")
    a("```sh")
    a("tools/corpus-venv/bin/python scripts/fetch_wikidata.py")
    a("tools/corpus-venv/bin/python scripts/build_corpus.py --emit-mobile")
    a("tools/corpus-venv/bin/python scripts/build_mobile_gaz.py   # alt emit")
    a("```")
    a("")
    a("Note: only real named entities are emitted -- Wikidata/GeoNames/OSM rows "
      "or attested sector/block designators (synthetic:true, coords averaged "
      "from attesting features). No fabricated names. Where the sources run "
      "dry the report above is the real ceiling, not a target hit by padding.")
    a("")
    os.makedirs(os.path.dirname(OUT_REPORT), exist_ok=True)
    with open(OUT_REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(L))


def corpus_stats():
    """--stats: summarize the existing corpus file."""
    from collections import Counter
    cats = Counter()
    srcs = Counter()
    n = synth = 0
    with gzip.open(OUT_JSONL, "rt", encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            cats[e["category"].split(":")[0]] += 1
            for s in e.get("sources", ["osm"]):
                srcs[s] += 1
            synth += bool(e.get("synthetic"))
            n += 1
    print(f"{n:,} entries in {os.path.relpath(OUT_JSONL, REPO)} "
          f"({synth:,} synthetic)")
    print("by source:", dict(srcs.most_common()))
    print("top categories:", dict(cats.most_common(20)))
    return 0


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", help="path to a local .osm.pbf (skip download)")
    ap.add_argument("--score", action="store_true",
                    help="only re-run the 20-query scoring on the existing corpus")
    ap.add_argument("--stats", action="store_true",
                    help="summarize the existing corpus file and exit")
    ap.add_argument("--emit-mobile", action="store_true",
                    help="also write the Mobile-ready ~150k gazetteer JSON")
    ap.add_argument("--mobile-target", type=int, default=150000)
    ap.add_argument("--osm-only", action="store_true",
                    help="skip GeoNames/aux/synthetic merge (baseline OSM run)")
    args = ap.parse_args()

    aliases = load_aliases()

    if args.stats:
        return corpus_stats()

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
    entries_map, stats = build_corpus(pbf)
    n_osm = len(entries_map)
    print(f"  OSM pass: {n_osm:,} entries", flush=True)

    gstats = astats = sstats = None
    if not args.osm_only:
        print("  merging GeoNames IN.txt slice ...", flush=True)
        gstats = merge_geonames(entries_map, stats)
        print(f"    {gstats}", flush=True)
        print("  merging aux/*.jsonl (Wikidata etc.) ...", flush=True)
        astats = merge_aux(entries_map, stats)
        print(f"    {astats}", flush=True)
        print("  generating attested sector/block canonical rows ...",
              flush=True)
        sstats = merge_synthetic(entries_map, stats)
        print(f"    {sstats}", flush=True)

    entries = list(entries_map.values())
    extra = {"osm entries (base layer)": f"{n_osm:,}"}
    if gstats and not gstats.get("unavailable"):
        extra["geonames"] = (f"{gstats['in_box']:,} in box -> "
                             f"+{gstats['added']:,} new "
                             f"({gstats['deduped_into']:,} deduped in)")
    if astats and astats.get("files"):
        extra["aux/*.jsonl"] = (f"{astats['rows']:,} rows -> "
                                f"+{astats['added']:,} new "
                                f"({astats['deduped_into']:,} deduped in); "
                                f"{', '.join(astats['files'])}")
    if sstats:
        extra["synthetic"] = (f"{sstats['attested']:,} attested -> "
                              f"+{sstats['added']:,} rows "
                              f"({sstats['merged_nearby']:,} folded)")
    lines = write_outputs(entries, stats, src, extra)

    # --- score ---
    rows_with = run_score(entries, aliases, True)
    rows_without = run_score(entries, aliases, False)
    hits_with = append_score_stats(lines, rows_with, rows_without)
    hits_without = sum(r["hit"] for r in rows_without)

    # --- mobile emit ---
    mobile = None
    if args.emit_mobile:
        mobile = emit_mobile(entries, args.mobile_target)
        lines.append("\n## Mobile gazetteer emit\n")
        lines.append(f"- output: `{os.path.relpath(mobile['path'], REPO)}` "
                     f"({mobile['size_mb']:.1f} MB)")
        lines.append(f"- bundled gazetteer kept: {mobile['existing']:,}")
        lines.append(f"- new corpus rows added: {mobile['added']:,} "
                     f"(skipped {mobile['skipped_dupes']:,} name+75 m dupes)")
        lines.append(f"- **total: {mobile['total']:,}** "
                     f"(target {args.mobile_target:,})")

    write_report(stats, gstats, astats, sstats, src, entries,
                 hits_with, hits_without, mobile, prev_total=53298,
                 n_osm=n_osm)

    with open(OUT_STATS, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
