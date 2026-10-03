"""ALive-108 — T1 search index, Python reference implementation.

This module is both:
  1. the parity oracle for the C++ `alive_core` module (CI asserts identical
     result order and scores to 1e-9), and
  2. the runtime fallback used when the compiled module cannot be imported —
     `get_search_index()` picks the C++ index when available, this one
     otherwise.

Query semantics (identical to server/core/src/search.cpp):

- normalization: NFKD -> drop non-ASCII, lowercase, keep [a-z0-9]
- index tokens: tokens(display) + tokens(entry aliases) + one-level alias
  expansion (bag semantics)
- query: each query token forms a group of alternatives; alternative 0 is
  the token itself, further alternatives come from the alias table (each a
  token *sequence*). A query token is "covered" by an entry when some
  alternative has ALL of its atoms matched by entry tokens.
- atom vs index-token pair quality:
    * index token startswith atom          -> len(atom)/len(token)
    * len(atom) >= 4 and DL(atom, token) <= (1 if len < 8 else 2)
      and the tokens share a padded trigram -> 1 - d/max(len)
  pair quality is the max of applicable rules.
- entry score:
    prefix_quality*w1 + token_coverage*w2 + popularity*w3
    - log1p(distance_km)*w4
  where prefix_quality = mean over query tokens of the group's best pair
  quality and token_coverage = matched query tokens / query tokens.
- result order: score desc, then entry id asc, then entry index asc.

Alias table: `load_aliases()` merges built-in defaults with
server/data/aliases.json when that file exists (absence is tolerated).
"""

from __future__ import annotations

import bisect
import gzip
import json
import math
import os
import sys
import unicodedata
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
ALIASES_PATH = os.path.join(_HERE, "data", "aliases.json")
GAZETTEER_PATH = os.path.abspath(
    os.path.join(_HERE, "..", "Mobile", "assets", "delhi-gazetteer.json"))

# Same source list v2/gazetteer resolves (kept in sync deliberately):
# env override, the app's bundled gazetteer, the server-local copy.
# The image ships only the corpus under server/data — a hard-coded
# single path is why the deployed index couldn't build at all.
GAZETTEER_PATHS = [
    os.environ.get("ALIVE_GAZETTEER", ""),
    GAZETTEER_PATH,
    os.path.join(_HERE, "data", "delhi-gazetteer.json"),
]
CORPUS_PATHS = [
    os.environ.get("ALIVE_CORPUS", ""),
    os.path.join(_HERE, "data", "corpus", "delhi-corpus.jsonl"),
    os.path.join(_HERE, "data", "corpus", "delhi-corpus.jsonl.gz"),
    os.path.join(_HERE, "data", "corpus", "delhi-corpus-sample.jsonl"),
]

# score weights — mirror the C++ defaults (alive::Weights)
W_PREFIX = 1.0
W_COVERAGE = 1.0
W_POPULARITY = 0.5
W_DISTANCE = 0.15
W_PRECISION = 0.5   # gazetteer W_PREC — display-token precision

# popularity is a 0..1 weight in the scorer, but unbounded scales arrive
# in the data — geonames rows carry raw population (Delhi ~16.7M) and a
# few aux rows ship small >1 values. Any >1 source is an unbounded
# magnitude scale: re-map it through a log curve against a Delhi-scale
# ceiling so ordering (megacity > town > village) survives while the
# term stays a tiebreaker instead of a million-point sledgehammer.
_POP_LOG_CEIL = math.log1p(20_000_000.0)


def _norm_popularity(p: float) -> float:
    if p <= 1.0:
        return p
    return min(1.0, math.log1p(p) / _POP_LOG_CEIL)

# ---------------------------------------------------------------------------
# C++ module lookup — direct import, then the local cmake build dir.
# ---------------------------------------------------------------------------
try:
    import alive_core as _cpp
except ImportError:
    _build = os.path.join(_HERE, "core", "build")
    if os.path.isdir(_build) and _build not in sys.path:
        sys.path.append(_build)
    try:
        import alive_core as _cpp
    except ImportError:
        _cpp = None

HAVE_CPP = _cpp is not None

_D2R = 0.017453292519943295  # pi / 180


# ---------------------------------------------------------------------------
# normalization
# ---------------------------------------------------------------------------
def normalize(s: str) -> list[str]:
    """NFKD -> drop non-ASCII -> lowercase -> [a-z0-9] tokens.

    Non-folding codepoints vanish *without* becoming separators — identical
    to ``s.encode('ascii', 'ignore')`` (and to the C++ normalize()).
    """
    out: list[str] = []
    cur: list[str] = []
    for ch in unicodedata.normalize("NFKD", s):
        o = ord(ch)
        if o < 128:
            if 65 <= o <= 90:
                ch = chr(o + 32)
            if ("a" <= ch <= "z") or ("0" <= ch <= "9"):
                cur.append(ch)
            elif cur:
                out.append("".join(cur))
                cur = []
        # non-ascii codepoints are dropped entirely (ascii-ignore semantics)
    if cur:
        out.append("".join(cur))
    return out


def _trigrams(tok: str) -> set[str]:
    """Padded trigrams: 2-space pad on both ends of the token."""
    p = "  " + tok + "  "
    return {p[i:i + 3] for i in range(len(p) - 2)}


def dl_distance(a: str, b: str, bound: int) -> int:
    """True Damerau-Levenshtein (unrestricted adjacent transpositions).

    `bound` only prunes |len(a)-len(b)| > bound; the full matrix is computed
    otherwise. Mirrors the C++ dl_distance() line for line.
    """
    la, lb = len(a), len(b)
    if abs(la - lb) > bound:
        return bound + 1
    INF = la + lb
    d = [[0] * (lb + 2) for _ in range(la + 2)]
    d[0][0] = INF
    for i in range(la + 1):
        d[i + 1][0] = INF
        d[i + 1][1] = i
    for j in range(lb + 1):
        d[0][j + 1] = INF
        d[1][j + 1] = j
    da: dict[str, int] = {}
    for i in range(1, la + 1):
        db = 0
        for j in range(1, lb + 1):
            i1 = da.get(b[j - 1], 0)
            j1 = db
            cost = 0 if a[i - 1] == b[j - 1] else 1
            if cost == 0:
                db = j
            d[i + 1][j + 1] = min(
                d[i][j] + cost,
                d[i + 1][j] + 1,
                d[i][j + 1] + 1,
                d[i1][j1] + (i - i1 - 1) + 1 + (j - j1 - 1),
            )
        da[a[i - 1]] = i
    return d[la + 1][lb + 1]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0088
    p1 = lat1 * _D2R
    p2 = lat2 * _D2R
    dp = (lat2 - lat1) * _D2R
    dl = (lon2 - lon1) * _D2R
    h = (math.sin(dp / 2) * math.sin(dp / 2)
         + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) * math.sin(dl / 2))
    return 2 * R * math.asin(min(1.0, math.sqrt(h)))


# ---------------------------------------------------------------------------
# alias table
# ---------------------------------------------------------------------------
_ROMAN = {
    "1": ["i", "one"], "i": ["1", "one"],
    "2": ["ii", "two"], "ii": ["2", "two"],
    "3": ["iii", "three"], "iii": ["3", "three"],
    "4": ["iv", "four"], "iv": ["4", "four"],
    "5": ["v", "five"], "v": ["5", "five"],
    "6": ["vi", "six"], "vi": ["6", "six"],
    "7": ["vii", "seven"], "vii": ["7", "seven"],
    "8": ["viii", "eight"], "viii": ["8", "eight"],
    "9": ["ix", "nine"], "ix": ["9", "nine"],
    "10": ["x", "ten"], "x": ["10", "ten"],
}

_BUILTIN_ALIASES: dict[str, list[str]] = {
    "sec": ["sector"], "sector": ["sec"],
    "ph": ["phase"], "phase": ["ph"],
    "st": ["saint", "street"], "rd": ["road"], "ave": ["avenue"],
    "ngr": ["nagar"], "mkt": ["market"], "stn": ["station"],
    "rly": ["railway"], "nr": ["near"], "chok": ["chowk"],
    "cp": ["connaught place"], "gk": ["greater kailash"],
    "ncr": ["national capital region"],
    "isbt": ["inter state bus terminus"],
    "dtu": ["delhi technological university"],
    "iit": ["indian institute of technology"],
    "aiims": ["all india institute of medical sciences"],
    **_ROMAN,
}


def load_aliases(path: Optional[str] = None) -> dict[str, list[list[str]]]:
    """Resolve the alias table -> {token: [[tok, ...], ...]}.

    Built-ins first, then merged with the JSON file when present (file
    phrases extend, never remove). Keys and phrases are normalized through
    the same normalize() used for entries and queries.
    """
    if path is None:
        path = ALIASES_PATH

    table: dict[str, list[list[str]]] = {}

    def add(key: str, phrase: str) -> None:
        ktoks = normalize(key)
        if len(ktoks) != 1:
            return
        ptoks = normalize(phrase)
        if not ptoks:
            return
        alts = table.setdefault(ktoks[0], [])
        if ptoks not in alts:
            alts.append(ptoks)

    for k, phrases in _BUILTIN_ALIASES.items():
        for p in phrases:
            add(k, p)

    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            raw = raw.get("aliases", raw)
        for key, phrases in raw.items():
            if isinstance(phrases, str):
                phrases = [phrases]
            for p in phrases:
                add(key, p)
    return table


def entries_from_gazetteer(path: Optional[str] = None,
                           corpus_paths: Optional[list] = None) -> list[dict]:
    """The T1 entry universe — the same sources the gazetteer engine
    serves: first readable gazetteer JSON + first readable corpus
    JSONL, deduped the same way (normalized name inside a ~110 m cell
    keeps the most popular row).

    `path` pins a single gazetteer file (tests); corpus loads
    independently of it. Missing files are skipped, not fatal — a
    container that only ships data/corpus still gets an index."""
    gaz_paths = [path] if path else GAZETTEER_PATHS
    cor_paths = corpus_paths if corpus_paths is not None else CORPUS_PATHS

    entries: list[dict] = []
    for p in gaz_paths:
        if not p or not os.path.exists(p):
            continue
        try:
            with open(p, encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, ValueError):
            continue
        for i, e in enumerate(raw):
            entries.append({
                "id": i,  # place-holder; reassigned to position below
                "pid": f"gaz:{i}",
                "display": e["n"],
                "aliases": [],
                "category": e.get("c", ""),
                "lat": float(e["lat"]),
                "lon": float(e["lon"]),
                "popularity": _norm_popularity(float(e.get("k", 0.0))),
            })
        break  # first readable gazetteer file wins

    for p in cor_paths:
        if not p or not os.path.exists(p):
            continue
        try:
            fh = (gzip.open(p, "rt", encoding="utf-8")
                  if p.endswith(".gz")
                  else open(p, encoding="utf-8"))
        except OSError:
            continue
        with fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if e.get("lat") is None or e.get("lon") is None \
                        or not e.get("display"):
                    continue
                entries.append({
                    "id": 0,
                    "pid": f"cor:{e.get('id')}",
                    "display": e["display"],
                    "aliases": list(e.get("aliases") or []),
                    "category": e.get("category") or "place",
                    "lat": float(e["lat"]),
                    "lon": float(e["lon"]),
                    "popularity": _norm_popularity(
                        float(e.get("popularity") or 0.0)),
                })
        break  # first readable corpus file wins

    # gazetteer dedupe: same normalized name inside a ~110 m cell keeps
    # the most popular row (corpus ships near-duplicate place rows)
    best: dict = {}
    for en in entries:
        key = (tuple(normalize(en["display"])),
               round(en["lat"], 3), round(en["lon"], 3))
        prev = best.get(key)
        if prev is None or en["popularity"] > prev["popularity"]:
            best[key] = en
    entries = list(best.values())
    # `id` = the entry's position (C++ Entry.id is uint32 — corpus string
    # ids can't cross the binding); `pid` keeps the resolvable wire id
    # (gaz:<idx>/cor:<osm-id>, the same schemes /v2/place speaks).
    for pos, en in enumerate(entries):
        en["id"] = pos
    return entries


# ---------------------------------------------------------------------------
# the reference index
# ---------------------------------------------------------------------------
class PySearchIndex:
    """Linear-ish Python implementation of the T1 query semantics.

    Same result order and scores as alive_core.SearchIndex; used as the
    parity oracle and the runtime fallback.
    """

    def __init__(self, entries: list[dict],
                 aliases: Optional[dict] = None,
                 w1: float = W_PREFIX, w2: float = W_COVERAGE,
                 w3: float = W_POPULARITY, w4: float = W_DISTANCE,
                 w5: float = W_PRECISION):
        self.entries = entries
        self.aliases = aliases or {}
        self.w1, self.w2, self.w3, self.w4, self.w5 = w1, w2, w3, w4, w5

        postmap: dict[str, list[int]] = {}
        # per-entry match tokens (display + alias + alias-expanded atoms)
        # — the same set that builds the postings; needed for fuzzy flag
        self._entry_toks: list[list[str]] = []
        # per-entry display tokens (normalize(display)) — precision term
        self._display_toks: list[list[str]] = []
        for e, en in enumerate(entries):
            base: list[str] = []
            seen: set[str] = set()
            disp = normalize(en["display"])
            self._display_toks.append(disp)
            for t in disp:
                if t not in seen:
                    seen.add(t)
                    base.append(t)
            for al in en.get("aliases") or []:
                for t in normalize(al):
                    if t not in seen:
                        seen.add(t)
                        base.append(t)
            # one-level alias expansion (bag semantics on the index side)
            for t in base:
                for alt in self.aliases.get(t, ()):
                    seen.update(alt)
            for t in seen:
                postmap.setdefault(t, []).append(e)
            self._entry_toks.append(list(seen))

        self.vocab = sorted(postmap)
        self.postings = {t: postmap[t] for t in self.vocab}
        self.tri: dict[str, list[int]] = {}
        for vid, tok in enumerate(self.vocab):
            for key in _trigrams(tok):
                self.tri.setdefault(key, []).append(vid)

    def __len__(self) -> int:
        return len(self.entries)

    def size(self) -> int:
        return len(self.entries)

    def query(self, q: str, lat: Optional[float] = None,
              lon: Optional[float] = None, limit: int = 8) -> list[dict]:
        qtoks = normalize(q)
        G = len(qtoks)
        if G == 0 or not self.entries or limit <= 0:
            return []

        # groups of alternatives; each alternative is a tuple of atom ids
        atomid: dict[str, int] = {}
        atoms: list[str] = []

        def intern(s: str) -> int:
            i = atomid.get(s)
            if i is None:
                i = len(atoms)
                atomid[s] = i
                atoms.append(s)
            return i

        groups: list[list[tuple[int, ...]]] = []
        for t in qtoks:
            alts = [(intern(t),)]
            for alt in self.aliases.get(t, ()):
                alts.append(tuple(intern(a) for a in alt))
            groups.append(alts)

        vocab = self.vocab
        # phase 1 — candidate generation + per-(entry, atom) best quality
        atom_best: dict[int, dict[int, float]] = {}
        for ai, x in enumerate(atoms):
            lx = len(x)
            scored: dict[int, float] = {}

            lo = bisect.bisect_left(vocab, x)
            vid = lo
            while vid < len(vocab) and vocab[vid].startswith(x):
                scored[vid] = lx / len(vocab[vid])
                vid += 1

            if lx >= 4:
                bound = 1 if lx < 8 else 2
                for key in _trigrams(x):
                    for cvid in self.tri.get(key, ()):
                        if cvid in scored:
                            continue  # prefix rule already covers this pair
                        t = vocab[cvid]
                        if abs(len(t) - lx) > bound:
                            continue
                        d = dl_distance(x, t, bound)
                        if d <= bound:
                            scored[cvid] = 1.0 - d / max(lx, len(t))

            for vid, qv in scored.items():
                for e in self.postings[vocab[vid]]:
                    row = atom_best.get(e)
                    if row is None:
                        atom_best[e] = {ai: qv}
                    elif qv > row.get(ai, 0.0):
                        row[ai] = qv

        # phase 2 — group evaluation + scoring
        # Coverage gates (v2/gazetteer.search's tuned rules): at least
        # half the query tokens must cover, and the LEAD query token must
        # cover — kills 'X + locality-tail' noise ('haldiram chandni'
        # must be a haldiram hit, not any chandni hit).
        need = max(1, math.ceil(G * 0.5))
        has_bias = lat is not None and lon is not None
        results: list[tuple[float, int, int]] = []  # (score, id, eidx)
        for e, row in atom_best.items():
            sum_q = 0.0
            matched = 0
            lead_gq = -1.0
            fuzzy = False
            for gi, g in enumerate(groups):
                gq = 0.0
                for alt in g:
                    if not alt:
                        continue
                    aq = min(row.get(a, 0.0) for a in alt)
                    if aq > gq:
                        gq = aq
                if gi == 0:
                    lead_gq = gq
                sum_q += gq
                if gq > 0:
                    matched += 1
                    # a covered group with no entry token starting with a
                    # query atom was reached only by DL distance → fuzzy
                    if not any(t.startswith(atoms[a])
                               for alt in g for a in alt
                               for t in self._entry_toks[e]):
                        fuzzy = True
            if matched < need or lead_gq <= 0.0:
                continue
            en = self.entries[e]
            pq = sum_q / G
            cov = matched / G
            # display precision — share of display tokens explained by a
            # query atom (prefix either direction); gazetteer W_PREC
            disp = self._display_toks[e]
            prec = (sum(1 for t in disp
                        if any(t.startswith(a) or a.startswith(t)
                               for a in atoms)) / len(disp)
                    if disp else 0.0)
            dist = (haversine_km(lat, lon, en["lat"], en["lon"])
                    if has_bias else 0.0)
            score = (self.w1 * pq + self.w2 * cov + self.w3 * en["popularity"]
                     + self.w5 * prec
                     - self.w4 * math.log1p(dist))
            results.append((score, en["id"], e, cov, fuzzy))

        results.sort(key=lambda r: (-r[0], r[1], r[2]))
        out = []
        for score, _eid, e, cov, fuzzy in results[:limit]:
            en = self.entries[e]
            out.append({
                "id": en["id"],
                "display": en["display"],
                "category": en["category"],
                "lat": en["lat"],
                "lon": en["lon"],
                "score": score,
                "cov": cov,
                "fuzzy": fuzzy,
            })
        return out


def get_search_index(entries: list[dict],
                     aliases: Optional[dict] = None,
                     prefer_cpp: bool = True):
    """Build the T1 index — C++ when importable, Python reference otherwise."""
    if aliases is None:
        aliases = load_aliases()
    if prefer_cpp and HAVE_CPP:
        return _cpp.SearchIndex(
            entries, aliases, W_PREFIX, W_COVERAGE, W_POPULARITY, W_DISTANCE,
            W_PRECISION)
    return PySearchIndex(
        entries, aliases, W_PREFIX, W_COVERAGE, W_POPULARITY, W_DISTANCE,
        W_PRECISION)


# ===========================================================================
# Phase 3 — field view + dose/emission integrators (docs/plan/08)
#
# These are the parity oracle AND runtime fallback for the C++ functions in
# server/core/src/field.cpp and src/emission.cpp. The contract below is what
# the plan lane codes against — keep signatures and semantics exactly.
#
# FieldView semantics (identical in alive_core.FieldView):
#   A snapshot's `cells` block (schema alive-airindex/1) maps cell ids to
#   {pm25, lo, hi, sigma, ...}. Cell ids are "g8:<lat>:<lon>" on the
#   latlon-fallback grid, or H3 res-8 ids when h3 built the grid (decoded
#   via the h3 package when installed).
#   value(lat, lon) returns the pm25 of the NEAREST cell center, using
#   airindex's flat-earth metric
#       km = hypot(dlat * 110.6, dlon * 99.4)
#   and only when that center is within coverage_km (default 1.0 — cells
#   are ~0.86 km apart, so in-field points are <0.61 km from a center;
#   a miss means the point is genuinely off-field). sigma()/band() return
#   the same cell's sigma / (lo, pm25, hi). No interpolation: cells are
#   already the kriged product — interpolating would fabricate precision.
#   Nearest-cell ties break on the smaller (lat, lon) — deterministic and
#   bit-identical to the C++ implementation.
# ===========================================================================

FIELD_COVERAGE_KM = 1.0     # max distance to nearest cell center for a hit
_FIELD_BIN_DEG = 0.01       # spatial-bin side in degrees (~1 km at 28.6N)
_KY = 110.6                 # km per degree latitude  (airindex._km)
_KX = 99.4                  # km per degree longitude at 28.6N (airindex._km)


def _cell_center(cid: str) -> tuple:
    """(lat, lon) of a snapshot cell id — airindex.cell_center semantics."""
    if cid.startswith("g8:"):
        _, la, lo = cid.split(":")
        return float(la), float(lo)
    try:
        import h3  # type: ignore
    except ImportError as e:
        raise ValueError(
            f"unsupported cell id {cid!r} (h3 grid but h3 not installed)"
        ) from e
    fn = getattr(h3, "cell_to_latlng", None) or getattr(h3, "h3_to_geo")
    lat, lon = fn(cid)
    return float(lat), float(lon)


def field_rows(src) -> list[tuple]:
    """Snapshot dict / cells dict / row iterable ->
    [(lat, lon, pm25, lo, hi, sigma)] — the canonical FieldView input."""
    cells = src.get("cells", src) if isinstance(src, dict) else src
    rows = []
    if isinstance(cells, dict):
        for cid, c in cells.items():
            lat, lon = _cell_center(cid)
            pm = float(c["pm25"])
            rows.append((lat, lon, pm,
                         float(c.get("lo", pm)),
                         float(c.get("hi", pm)),
                         float(c.get("sigma", 0.0))))
    else:
        for r in cells:
            rows.append((float(r[0]), float(r[1]), float(r[2]),
                         float(r[3]), float(r[4]), float(r[5])))
    return rows


class PyFieldView:
    """Nearest-cell field view — Python reference for alive_core.FieldView.

    Spatial index: uniform bins of _FIELD_BIN_DEG; a query scans expanding
    Chebyshev rings until the ring's minimum possible distance exceeds the
    running best (initialised to coverage_km). Same algorithm in C++.
    """

    def __init__(self, src, coverage_km: float = FIELD_COVERAGE_KM):
        self.coverage_km = float(coverage_km)
        self._cells = field_rows(src)
        self._bins: dict[tuple, list[int]] = {}
        for i, c in enumerate(self._cells):
            key = (math.floor(c[0] / _FIELD_BIN_DEG),
                   math.floor(c[1] / _FIELD_BIN_DEG))
            self._bins.setdefault(key, []).append(i)

    def __len__(self) -> int:
        return len(self._cells)

    def size(self) -> int:
        return len(self._cells)

    def _nearest(self, lat: float, lon: float):
        """-> cell index of nearest center within coverage_km, else None."""
        cells = self._cells
        if not cells:
            return None
        bi = math.floor(lat / _FIELD_BIN_DEG)
        bj = math.floor(lon / _FIELD_BIN_DEG)
        best = self.coverage_km
        best_i = -1
        best_ll = None
        r = 0
        # ring-r bins hold cells no closer than (r-1)*bin degrees on the
        # worst axis; _KX < _KY is the conservative km-per-degree scale.
        while (r - 1) * _FIELD_BIN_DEG * _KX <= best:
            for di in range(-r, r + 1):
                for dj in range(-r, r + 1):
                    if max(abs(di), abs(dj)) != r:
                        continue
                    for ci in self._bins.get((bi + di, bj + dj), ()):
                        c = cells[ci]
                        d = math.hypot((c[0] - lat) * _KY,
                                       (c[1] - lon) * _KX)
                        if d < best or (d == best and (
                                best_i < 0 or (c[0], c[1]) < best_ll)):
                            best, best_i = d, ci
                            best_ll = (c[0], c[1])
            r += 1
        return best_i if best_i >= 0 else None

    def nearest_cell(self, lat: float, lon: float):
        """-> {lat, lon, pm25, lo, hi, sigma, dist_km} or None."""
        i = self._nearest(lat, lon)
        if i is None:
            return None
        c = self._cells[i]
        return {"lat": c[0], "lon": c[1], "pm25": c[2], "lo": c[3],
                "hi": c[4], "sigma": c[5],
                "dist_km": math.hypot((c[0] - lat) * _KY,
                                      (c[1] - lon) * _KX)}

    def value(self, lat: float, lon: float, pollutant: str = "pm2_5"):
        """pm2.5 µg/m³ of the nearest cell, or None off-field. The snapshot
        field is pm2.5-only — any other pollutant returns None."""
        if pollutant not in ("pm2_5", "pm25"):
            return None
        i = self._nearest(lat, lon)
        return self._cells[i][2] if i is not None else None

    def sigma(self, lat: float, lon: float):
        """Kriging sigma (µg/m³) of the nearest cell, or None off-field."""
        i = self._nearest(lat, lon)
        return self._cells[i][5] if i is not None else None

    def band(self, lat: float, lon: float):
        """(lo, pm25, hi) of the nearest cell, or None off-field."""
        i = self._nearest(lat, lon)
        if i is None:
            return None
        c = self._cells[i]
        return (c[3], c[2], c[4])


def get_field_view(src, coverage_km: float = FIELD_COVERAGE_KM,
                   prefer_cpp: bool = True):
    """Build a FieldView — C++ when importable, Python reference otherwise."""
    rows = field_rows(src)
    if prefer_cpp and HAVE_CPP:
        return _cpp.FieldView(rows, coverage_km)
    return PyFieldView(rows, coverage_km)


# ---------------------------------------------------------------------------
# dose:  dose_µg = Σ C(x)·ME(mode)·VE(mode)·Δt   (docs/plan/06 §1)
# ---------------------------------------------------------------------------

def _haversine_m(a, b) -> float:
    """exposure._haversine_m verbatim — a,b are (lon, lat) pairs."""
    R = 6371000.0
    p1, p2 = math.radians(a[1]), math.radians(b[1])
    dp, dl = math.radians(b[1] - a[1]), math.radians(b[0] - a[0])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def segment_samples(coords, duration_s: float, step_m: float = 250.0) -> list:
    """exposure.segment_samples verbatim on a coords list — sample a
    LineString every ~step_m; duration apportioned by segment length
    (uniform-speed assumption), renormalized so Σseconds == duration_s.
    `coords` may be [[lon, lat], ...] or a GeoJSON geometry dict.
    Returns [{lat, lon, seconds, dist_m}]."""
    if isinstance(coords, dict):
        coords = coords.get("coordinates", [])
    if len(coords) < 2:
        return []
    total = sum(_haversine_m(coords[i - 1], coords[i])
                for i in range(1, len(coords)))
    if total <= 0:
        return []
    out = []
    carry = 0.0
    for i in range(1, len(coords)):
        a, b = coords[i - 1], coords[i]
        seg = _haversine_m(a, b)
        carry += seg
        if carry >= step_m or i == len(coords) - 1:
            frac = seg / total
            out.append({"lat": b[1], "lon": b[0],
                        "seconds": duration_s * frac, "dist_m": seg})
            carry = 0.0
    s = sum(x["seconds"] for x in out) or 1.0
    for x in out:
        x["seconds"] *= duration_s / s
    return out


def integrate_dose(coords, field, me: float, ve: float,
                   duration_s: float, step_m: float = 250.0) -> dict:
    """Inhaled PM2.5 dose (µg) over a polyline — THE CONTRACT.

    coords: [[lon, lat], ...] or a GeoJSON geometry dict.
    field:  object with .band(lat, lon) -> (lo, mid, hi)|None —
            PyFieldView or alive_core.FieldView.
    me:     microenvironment ratio (exposure.MICROENV[mode]).
    ve:     minute ventilation in m³/min (exposure.VENTILATION_LPM[mode]/1000).
    duration_s: total traversal time; Δt per sample follows exposure.py's
            uniform-speed apportioning.

    Band rule (doc 06 §1): conservative — lo/hi are the sums of per-cell
    lo/hi through the same integral. Samples off-field are skipped
    (coverage < 1). Returns:
      {"lo","mid","hi": µg floats (None when nothing hit the field),
       "coverage": hit fraction, "n_samples", "n_hit", "dist_km"}
    Values are unrounded — callers round for display.
    """
    samples = segment_samples(coords, duration_s, step_m)
    if not samples:
        return {"lo": None, "mid": None, "hi": None, "coverage": 0.0,
                "n_samples": 0, "n_hit": 0, "dist_km": 0.0}
    lo = mid = hi = 0.0
    got = 0
    dist_km = 0.0
    for s in samples:
        b = field.band(s["lat"], s["lon"])
        dist_km += s["dist_m"] / 1000.0
        if b is None:
            continue
        got += 1
        t_min = s["seconds"] / 60.0
        lo += b[0] * me * ve * t_min
        mid += b[1] * me * ve * t_min
        hi += b[2] * me * ve * t_min
    coverage = got / len(samples)
    if got == 0:
        return {"lo": None, "mid": None, "hi": None, "coverage": coverage,
                "n_samples": len(samples), "n_hit": 0, "dist_km": dist_km}
    return {"lo": lo, "mid": mid, "hi": hi, "coverage": coverage,
            "n_samples": len(samples), "n_hit": got, "dist_km": dist_km}


def mode_factors(mode: str) -> tuple:
    """(me, ve_m3min) for a plan mode — thin read of exposure.py's tables
    so callers don't re-key them (dose contract takes the raw factors)."""
    import exposure  # local tables, stdlib-only
    me = exposure.MICROENV.get(mode, 1.0)
    ve = exposure.VENTILATION_LPM.get(mode, 8.0) / 1000.0
    return me, ve


# ---------------------------------------------------------------------------
# emissions:  Σ ef(v)·dist over moving spans + idle g/s + cold-start
#             (emissions.integrate's span walk — docs/plan/06 §2–3)
# ---------------------------------------------------------------------------
# The vehicle-resolution chain (declared class/fuel/year -> BS bucket -> EF
# band) stays in emissions.py; this integrator takes the RESOLVED bands so
# the C++ kernel carries no vehicle tables.

EM_POLS = ("co2", "pm25", "nox")
EM_REF_SPEED_MPS = 30.0 / 3.6   # ef(v)=1 here (MIDC urban average)
EM_V_OPT_MPS = 50.0 / 3.6       # curve minimum ≈50 km/h (COPERT structure)
EM_V_FLOOR_MPS = 2.5            # slower motion belongs in the idle bucket
EM_COLD_KM = 4.0                # cold-start penalty zone
_EM_SPEED_PARAMS = {"co2": (1.2, 0.8), "pm25": (1.8, 1.2), "nox": (0.9, 1.4)}


def _em_g_curve(pol: str, v_mps: float) -> float:
    L, H = _EM_SPEED_PARAMS[pol]
    v = max(v_mps, EM_V_FLOOR_MPS)
    if v < EM_V_OPT_MPS:
        return 1.0 + L * ((EM_V_OPT_MPS - v) / EM_V_OPT_MPS) ** 2 \
            * (EM_V_OPT_MPS / v)
    return 1.0 + H * ((v - EM_V_OPT_MPS) / EM_V_OPT_MPS) ** 2


_EM_G_REF = {p: _em_g_curve(p, EM_REF_SPEED_MPS) for p in _EM_SPEED_PARAMS}


def emission_speed_factor(pol: str, v_mps: float) -> float:
    """ef(v)/ef(v_ref) — COPERT U-curve, 1.0 at EM_REF_SPEED_MPS."""
    return _em_g_curve(pol, v_mps) / _EM_G_REF[pol]


def _em_cold_avg_mult(c: float, d_start: float, cold_len_km: float) -> float:
    """Mean of 1+(C-1)(1 - x/COLD_KM) over the cold overlap — closed form."""
    x_avg = d_start + cold_len_km / 2.0
    return 1.0 + (c - 1.0) * (1.0 - x_avg / EM_COLD_KM)


def integrate_emissions(spans, ef_band: dict, idle_band: dict,
                        cold_mult: dict, nx_band=(0.0, 0.0, 0.0),
                        cold_km_done: float = 0.0,
                        occupancy: float = 1.0) -> dict:
    """Trip emissions over spans — THE CONTRACT (C++ parity target).

    spans:      [{dist_m, speed_mps, moving, dur_s?}] — moving spans accrue
                g/km at ef(v); non-moving/zero-distance spans accrue g/s
                over dur_s (or dist/speed when v > 0.3).
    ef_band:    {"co2": (lo,mid,hi), "pm25": ..., "nox": ...} g/km, warm.
    idle_band:  same shape, g/s.
    cold_mult:  {"co2": c, ...} — multiplier at km 0, linear decay to 1.0
                at EM_COLD_KM; applied at 0.7 strength to lo, 1.3 to hi.
    nx_band:    (lo,mid,hi) non-exhaust PM10 g/vkm — kept separate.
    cold_km_done: km already driven this cold trip (multi-leg calls).
    occupancy:  divide everything for per-passenger shared modes.

    Returns unrounded grams:
      {"co2_g","pm25_g","nox_g": (lo,mid,hi), "non_exhaust_pm10_g": (lo,mid,hi),
       "distance_km", "moving_mid_g"/"idle_mid_g"/"cold_extra_mid_g": {pol: g}}
    Mirrors emissions.integrate's accumulation order exactly — parity tests
    assert equality to 1e-9 relative.
    """
    acc = {p: [0.0, 0.0, 0.0] for p in EM_POLS}
    acc_nx = [0.0, 0.0, 0.0]
    moving_mid = {p: 0.0 for p in acc}
    idle_mid = {p: 0.0 for p in acc}
    cold_mid = {p: 0.0 for p in acc}
    d = max(0.0, float(cold_km_done or 0.0))
    tot_km = 0.0

    for s in spans or []:
        dist_m = float(s.get("dist_m") or 0.0)
        v = float(s.get("speed_mps") or 0.0)
        moving = bool(s.get("moving", True))

        if moving and dist_m > 0.0:
            km = dist_m / 1000.0
            tot_km += km
            cold_len = min(d + km, EM_COLD_KM) - d if d < EM_COLD_KM else 0.0
            warm_len = km - max(0.0, cold_len)
            for p in acc:
                f = emission_speed_factor(p, v)
                sw = 1.0 + 0.2 * abs(f - 1.0)
                lo, mid, hi = ef_band[p]
                km_lo, km_mid, km_hi = lo * f / sw, mid * f, hi * f * sw
                if cold_len > 0.0:
                    c = cold_mult[p]
                    ml = _em_cold_avg_mult(1.0 + (c - 1.0) * 0.7, d, cold_len)
                    mm = _em_cold_avg_mult(c, d, cold_len)
                    mh = _em_cold_avg_mult(1.0 + (c - 1.0) * 1.3, d, cold_len)
                    acc[p][0] += km_lo * (cold_len * ml + warm_len)
                    acc[p][1] += km_mid * (cold_len * mm + warm_len)
                    acc[p][2] += km_hi * (cold_len * mh + warm_len)
                    cold_mid[p] += km_mid * cold_len * (mm - 1.0)
                else:
                    acc[p][0] += km_lo * km
                    acc[p][1] += km_mid * km
                    acc[p][2] += km_hi * km
                moving_mid[p] += km_mid * km
            for i in range(3):
                acc_nx[i] += nx_band[i] * km
            d += km
        else:
            dur = s.get("dur_s")
            if dur is None:
                dur = dist_m / v if v > 0.3 else 0.0
            dur = max(0.0, float(dur))
            for p in acc:
                for i in range(3):
                    acc[p][i] += idle_band[p][i] * dur
                idle_mid[p] += idle_band[p][1] * dur

    if occupancy > 1.0:
        for p in acc:
            for i in range(3):
                acc[p][i] /= occupancy
            idle_mid[p] /= occupancy
            moving_mid[p] /= occupancy
            cold_mid[p] /= occupancy
        for i in range(3):
            acc_nx[i] /= occupancy

    return {
        "co2_g": tuple(acc["co2"]),
        "pm25_g": tuple(acc["pm25"]),
        "nox_g": tuple(acc["nox"]),
        "non_exhaust_pm10_g": tuple(acc_nx),
        "distance_km": tot_km,
        "moving_mid_g": {p: moving_mid[p] for p in acc},
        "idle_mid_g": {p: idle_mid[p] for p in acc},
        "cold_extra_mid_g": {p: cold_mid[p] for p in acc},
    }


def vehicle_bands(vehicle: dict) -> dict:
    """Resolve a declared vehicle dict to the integrator's input bundle via
    emissions.py's own chain — {ef_band, idle_band, cold_mult, nx_band,
    occupancy, label, ...}. Convenience so callers never re-key tables."""
    import emissions  # local, stdlib-only
    vclass, fuel, year = emissions._resolve(vehicle)
    dom, opts, conf, prior = emissions._bs_options(vclass, fuel, year)
    band = emissions._ev_ef(vclass) if fuel == "electric" else \
        emissions._merge_band(vclass, fuel, dom, opts, prior)
    return {
        "ef_band": band,
        "idle_band": emissions._idle_band(vclass, fuel),
        "cold_mult": emissions._COLD_MULT[fuel],
        "nx_band": emissions._NON_EXHAUST_PM10_GVKM[
            emissions._EF_GROUP[vclass]],
        "occupancy": emissions._occupancy(vclass),
        "bs_class": dom, "bs_options": list(opts), "confidence": conf,
        "fuel": fuel, "class": vclass,
        "label": emissions._label(vclass, fuel, year, dom, opts),
    }
