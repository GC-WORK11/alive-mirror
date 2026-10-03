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

# score weights — mirror the C++ defaults (alive::Weights)
W_PREFIX = 1.0
W_COVERAGE = 1.0
W_POPULARITY = 0.5
W_DISTANCE = 0.15

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


def entries_from_gazetteer(path: Optional[str] = None) -> list[dict]:
    """Map Mobile/assets/delhi-gazetteer.json rows to index entries."""
    if path is None:
        path = GAZETTEER_PATH
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return [
        {
            "id": i,
            "display": e["n"],
            "aliases": [],
            "category": e.get("c", ""),
            "lat": float(e["lat"]),
            "lon": float(e["lon"]),
            "popularity": float(e.get("k", 0.0)),
        }
        for i, e in enumerate(raw)
    ]


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
                 w3: float = W_POPULARITY, w4: float = W_DISTANCE):
        self.entries = entries
        self.aliases = aliases or {}
        self.w1, self.w2, self.w3, self.w4 = w1, w2, w3, w4

        postmap: dict[str, list[int]] = {}
        for e, en in enumerate(entries):
            base: list[str] = []
            seen: set[str] = set()
            for t in normalize(en["display"]):
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
        has_bias = lat is not None and lon is not None
        results: list[tuple[float, int, int]] = []  # (score, id, eidx)
        for e, row in atom_best.items():
            sum_q = 0.0
            matched = 0
            for g in groups:
                gq = 0.0
                for alt in g:
                    if not alt:
                        continue
                    aq = min(row.get(a, 0.0) for a in alt)
                    if aq > gq:
                        gq = aq
                sum_q += gq
                if gq > 0:
                    matched += 1
            en = self.entries[e]
            pq = sum_q / G
            cov = matched / G
            dist = (haversine_km(lat, lon, en["lat"], en["lon"])
                    if has_bias else 0.0)
            score = (self.w1 * pq + self.w2 * cov + self.w3 * en["popularity"]
                     - self.w4 * math.log1p(dist))
            results.append((score, en["id"], e))

        results.sort(key=lambda r: (-r[0], r[1], r[2]))
        out = []
        for score, _eid, e in results[:limit]:
            en = self.entries[e]
            out.append({
                "id": en["id"],
                "display": en["display"],
                "category": en["category"],
                "lat": en["lat"],
                "lon": en["lon"],
                "score": score,
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
            entries, aliases, W_PREFIX, W_COVERAGE, W_POPULARITY, W_DISTANCE)
    return PySearchIndex(
        entries, aliases, W_PREFIX, W_COVERAGE, W_POPULARITY, W_DISTANCE)
