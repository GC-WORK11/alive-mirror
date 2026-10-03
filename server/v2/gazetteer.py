"""Tier-1 search index over the bundled Delhi gazetteer.

This is the pure-Python fallback for T1 (docs/plan/04 §2): the C++
`alive_core` index and `alive_core_ref` are used instead when importable
(search.py picks the best at import). Data is the app's bundled
26.5k-place gazetteer (Mobile/assets/delhi-gazetteer.json) — entries
{n, c, lat, lon, w, k}: name, category, position, weight, popularity
score. When the file isn't shipped (server-only deploy) T1 simply
returns [] — the API stays honest rather than failing.
"""
import json
import math
import os
import re
from typing import Optional

_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO = os.path.dirname(_SERVER_DIR)
GAZETTEER_PATHS = [
    os.environ.get("ALIVE_GAZETTEER", ""),
    os.path.join(_REPO, "Mobile", "assets", "delhi-gazetteer.json"),
    os.path.join(_SERVER_DIR, "data", "delhi-gazetteer.json"),
]

# Hinglish/abbrev normalization (docs/plan/04 §2). Phrase-level aliases
# are applied before token-level ones.
PHRASE_ALIASES = {
    "cp": "connaught place",
    "gk": "greater kailash",
    "gk 1": "greater kailash 1",
    "gk 2": "greater kailash 2",
    "karol bagh mkt": "karol bagh market",
    "igi": "indira gandhi",
    "ndls": "new delhi railway station",
    "isbt": "inter state bus terminal",
    "chandni chok": "chandni chowk",
}
TOKEN_ALIASES = {
    "chok": "chowk",
    "sec": "sector",
    "stn": "station",
    "rd": "road",
    "mkt": "market",
    "nr": "near",
    "extn": "extension",
    "ext": "extension",
    "enclave": "enclave",
    "ngr": "nagar",
    "colny": "colony",
    "marg": "marg",
    "intl": "international",
}

_NON_ALNUM = re.compile(r"[^a-z0-9 ]+")
_WS = re.compile(r"\s+")


def normalize(s: str) -> str:
    """Lowercase, punctuation-free, alias-expanded — the dedupe key."""
    s = (s or "").lower().replace("&", " and ")
    s = _NON_ALNUM.sub(" ", s)
    s = _WS.sub(" ", s).strip()
    if s in PHRASE_ALIASES:
        s = PHRASE_ALIASES[s]
    toks = [TOKEN_ALIASES.get(t, t) for t in s.split()]
    return " ".join(toks)


def _lev_le1(a: str, b: str) -> bool:
    """Edit distance <= 1, early exit — the cheap typo bucket."""
    la, lb = len(a), len(b)
    if abs(la - lb) > 1 or not a or not b:
        return False
    if la == lb:
        diff = sum(1 for x, y in zip(a, b) if x != y)
        return diff <= 1
    if la > lb:
        a, b = b, a
    i = j = 0
    skipped = False
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            i += 1
            j += 1
        elif skipped:
            return False
        else:
            skipped = True
            j += 1
    return True


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371000.0 * math.asin(math.sqrt(h))


def classify(query_norm: str, name_norm: str) -> int:
    """0 exact-prefix | 1 token-prefix | 2 fuzzy | 3 no match.

    Token-prefix = every query token is a prefix of some name token.
    Fuzzy = every query token is within one edit of some name token
    (query tokens <4 chars are too short to typo-safely expand).
    """
    if not query_norm or not name_norm:
        return 3
    if name_norm.startswith(query_norm):
        return 0
    qtoks = query_norm.split()
    ntoks = name_norm.split()
    if qtoks and all(any(t.startswith(qt) for t in ntoks)
                     for qt in qtoks):
        return 1
    if qtoks and all(any(_lev_le1(qt, t) for t in ntoks)
                     for qt in qtoks if len(qt) >= 4):
        if all(len(qt) >= 4 for qt in qtoks):
            return 2
    return 3


class Gazetteer:
    """In-memory scan over the bundled gazetteer — load once, reuse."""

    def __init__(self, paths=None):
        self._paths = paths or GAZETTEER_PATHS
        self._rows: Optional[list] = None

    def _load(self) -> list:
        if self._rows is not None:
            return self._rows
        self._rows = []
        for p in self._paths:
            if not p or not os.path.exists(p):
                continue
            try:
                with open(p, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except (OSError, ValueError):
                continue
            for i, e in enumerate(data):
                name = e.get("n") or ""
                norm = normalize(name)
                if not norm:
                    continue
                self._rows.append({
                    "idx": i,
                    "name": name,
                    "norm": norm,
                    "tokens": norm.split(),
                    "kind": e.get("c") or "place",
                    "lat": e.get("lat"), "lon": e.get("lon"),
                    "pop": e.get("k") or 0.0,
                })
            break  # first readable file wins
        return self._rows

    def count(self) -> int:
        return len(self._load())

    def by_index(self, idx: int) -> Optional[dict]:
        for r in self._load():
            if r["idx"] == idx:
                return r
        return None

    def search(self, q: str, lat: Optional[float] = None,
               lon: Optional[float] = None, limit: int = 8) -> list:
        rows = self._load()
        qn = normalize(q)
        if not rows or not qn:
            return []
        blat = lat if lat is not None else 28.6139
        blon = lon if lon is not None else 77.2090

        scored = []
        for r in rows:
            cls = classify(qn, r["norm"])
            if cls >= 3:
                continue
            d = _haversine_m(blat, blon, r["lat"], r["lon"]) \
                if r["lat"] is not None else 9e9
            scored.append((cls, d, -float(r["pop"]), r))
        scored.sort(key=lambda t: (t[0], t[1], t[2]))
        out = []
        for cls, d, _pop, r in scored[:limit]:
            out.append({
                "id": f"gaz:{r['idx']}",
                "name": r["name"],
                "subtitle": r["kind"],
                "lat": r["lat"], "lon": r["lon"],
                "kind": r["kind"],
                "match": ("exact-prefix" if cls == 0 else
                          "token-prefix" if cls == 1 else "fuzzy"),
                "match_rank": cls,
                "distance_m": round(d),
                "source": "gazetteer",
                "sources": ["t1"],
            })
        return out


GAZ = Gazetteer()
