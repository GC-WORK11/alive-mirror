"""Tier-1 search index over the bundled Delhi gazetteer + OSM corpus.

This is the pure-Python fallback for T1 (docs/plan/04 §2): the C++
`alive_core` index and `alive_core_ref` are used instead when importable
(search.py picks the best at import). Two data sources are merged:

- Mobile/assets/delhi-gazetteer.json — the app's bundled 26.5k places
  ({n, c, lat, lon, w, k}: name, category, position, weight, popularity)
- server/data/corpus/*.jsonl — the OSM Delhi-NCR extract
  ({id, display, aliases, category, lat, lon, popularity}); entry
  aliases become extra match tokens, never the display name.

Scoring mirrors alive_core_ref's contract: per query token a group of
alternatives (the token itself + alias phrases from
server/data/aliases.json, wrapped {"aliases": {...}} format); a token is
covered when some alternative's atoms all match entry tokens
(prefix -> len/len quality, fuzzy -> DL within bound sharing a padded
trigram). Score = pq + coverage + popularity + name-precision
+ kind boost - log1p(distance_km); the lead query token must be covered
and >= half the tokens must cover. Kind boosts are intent-gated
(station/mall/university words in the query boost the matching kinds;
otherwise locality kinds get a small default boost).
"""
import bisect
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
CORPUS_PATHS = [
    os.environ.get("ALIVE_CORPUS", ""),
    os.path.join(_SERVER_DIR, "data", "corpus", "delhi-corpus.jsonl"),
    os.path.join(_SERVER_DIR, "data", "corpus",
                 "delhi-corpus-sample.jsonl"),
]
ALIAS_PATHS = [
    os.environ.get("ALIVE_ALIASES", ""),
    os.path.join(_SERVER_DIR, "data", "aliases.json"),
]

# score weights — same shape as alive_core_ref
W_PQ = 1.0        # mean per-group best pair quality
W_COV = 1.0       # matched query tokens / query tokens
W_POP = 0.5       # curated gazetteer popularity (corpus rows are 0)
W_PREC = 0.5      # fraction of display tokens the query explains
W_DIST = 0.15     # -log1p(distance_km)
MIN_COV = 0.5     # at least half the query tokens must cover
KIND_BOOST = 0.30

# intent -> kind substrings; fires only when an intent word is among the
# expanded query atoms (so "vaishali metro" boosts stations but
# "sarojni nagar" does not).
_INTENT_KINDS = {
    ("metro", "station", "stn", "railway", "rly", "isbt", "airport",
     "bus"): ("station", "metro", "train", "railway", "airport", "bus"),
    ("mall", "market", "mkt", "bazar", "bazaar", "cinema", "pvr",
     "shopping", "mart", "store"): ("mall", "market", "cinema",
                                    "shopping", "bazaar", "store",
                                    "mart"),
    ("university", "univ", "college", "institute", "school",
     "iit", "dtu", "jnu", "nsut", "dce"): ("university", "college",
                                          "institute", "school"),
    ("hospital", "medical", "clinic", "hosp"): ("hospital", "clinic",
                                               "medical"),
}
# default boost (no intent word): named places over POI noise
_LOCALITY_KINDS = ("locality", "neighborhood", "macrohood", "place",
                   "suburb", "district", "addr:place")
_LOCALITY_BOOST = 0.25

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

# roman <-> arabic equivalences — query-side alternatives and one-level
# index expansion only; normalize() itself never rewrites numerals.
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


_ALIAS_TABLE: Optional[dict] = None


def alias_table() -> dict:
    """{token: [[tok, ...], ...]} — builtins + roman + aliases.json.

    The file uses the wrapped {"comment": ..., "aliases": {...}} shape;
    phrases may be multi-token (each phrase is one alternative). File
    entries extend builtins, never remove.
    """
    global _ALIAS_TABLE
    if _ALIAS_TABLE is not None:
        return _ALIAS_TABLE
    table: dict = {}

    def _raw_norm(s: str) -> list:
        """Case/punct fold WITHOUT alias application — alias keys must
        not migrate under their own expansions ('cp' stays 'cp')."""
        s = _WS.sub(" ", _NON_ALNUM.sub(" ", (s or "").lower())).strip()
        return s.split()

    def add(key: str, phrase: str) -> None:
        ktoks = _raw_norm(key)
        if len(ktoks) != 1:
            return
        ptoks = _raw_norm(phrase)
        if not ptoks:
            return
        alts = table.setdefault(ktoks[0], [])
        if ptoks not in alts:
            alts.append(ptoks)

    for k, v in TOKEN_ALIASES.items():
        add(k, v)
    for k, v in PHRASE_ALIASES.items():
        if len(k.split()) == 1:
            add(k, v)
    for k, phrases in _ROMAN.items():
        for p in phrases:
            add(k, p)
    for path in ALIAS_PATHS:
        if not path or not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(raw, dict):
            raw = raw.get("aliases", raw)
        if not isinstance(raw, dict):
            continue
        for key, phrases in raw.items():
            if isinstance(phrases, str):
                phrases = [phrases]
            for p in phrases or []:
                if isinstance(p, str):
                    add(key, p)
        break  # first readable file wins
    _ALIAS_TABLE = table
    return table


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


def _lev_bound(a: str, b: str, bound: int) -> int:
    """Plain Levenshtein with a length cutoff — <=bound or bound+1."""
    la, lb = len(a), len(b)
    if abs(la - lb) > bound:
        return bound + 1
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        row_min = i
        for j in range(1, lb + 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1,
                         prev[j - 1] + (a[i - 1] != b[j - 1]))
            if cur[j] < row_min:
                row_min = cur[j]
        if row_min > bound:
            return bound + 1
        prev = cur
    return prev[lb]


def _trigrams(tok: str) -> set:
    p = "  " + tok + "  "
    return {p[i:i + 3] for i in range(len(p) - 2)}


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371000.0 * math.asin(math.sqrt(h))


def _query_groups(qn: str, aliases: dict) -> list:
    """Per query token: [(atom,...), ...] — literal token + alias phrases."""
    groups = []
    for t in qn.split():
        alts = [(t,)]
        for phrase in aliases.get(t, ()):
            tup = tuple(phrase)
            if tup and tup not in alts:
                alts.append(tup)
        groups.append(alts)
    return groups


def _pair_quality(atom: str, tok: str) -> float:
    """atom vs entry token: prefix -> len/len; fuzzy (len>=4, DL<=bound)
    -> 1 - d/max(len). Mirrors alive_core_ref's pair rules."""
    if not atom or not tok:
        return 0.0
    if tok.startswith(atom):
        return len(atom) / len(tok)
    la = len(atom)
    if la >= 4:
        bound = 1 if la < 8 else 2
        d = _lev_bound(atom, tok, bound)
        if d <= bound:
            return 1.0 - d / max(la, len(tok))
    return 0.0


def _eval_groups(groups: list, match_tokens: list, display_tokens: list):
    """Score one entry against the query groups.

    Returns (pq, coverage, precision, fuzzy_flag): pq is the mean over
    groups of the best alternative quality (an alternative scores the
    min quality of its atoms); coverage is matched groups / groups;
    precision is the share of display tokens any atom matches.
    """
    G = len(groups)
    if not G:
        return 0.0, 0.0, 0.0, False
    toks = match_tokens or display_tokens
    sum_q = 0.0
    matched = 0
    fuzzy_used = False
    all_atoms = []
    for alts in groups:
        gq = 0.0
        for alt in alts:
            if not alt:
                continue
            # an alternative scores the min over its atoms of each
            # atom's best pair quality against the entry tokens
            aq = min(max((_pair_quality(a, t) for t in toks), default=0.0)
                     for a in alt)
            if aq > gq:
                gq = aq
        if gq > 0:
            matched += 1
            for alt in alts:
                for a in alt:
                    if a not in all_atoms:
                        all_atoms.append(a)
            if not any(t.startswith(a)
                       for alt in alts for a in alt for t in toks):
                fuzzy_used = True
        sum_q += gq
    prec = 0.0
    if display_tokens:
        hit = sum(1 for t in display_tokens
                  if any(_pair_quality(a, t) > 0 for a in all_atoms))
        prec = hit / len(display_tokens)
    return sum_q / G, matched / G, prec, fuzzy_used


def classify(query_norm: str, name_norm: str) -> int:
    """0 exact-prefix | 1 token-prefix | 2 fuzzy | 3 no match.

    Same contract as before but alias-aware: each query token also tries
    its alias phrases (aliases.json), so 'gk 2' token-prefixes
    'greater kailash ii'. Partial coverage is still class 3 here —
    scored partials surface through Gazetteer.search instead.
    """
    if not query_norm or not name_norm:
        return 3
    if name_norm.startswith(query_norm):
        return 0
    groups = _query_groups(query_norm, alias_table())
    ntoks = name_norm.split()
    pq, cov, _prec, fuzzy = _eval_groups(groups, ntoks, ntoks)
    if cov < 1.0:
        return 3
    return 2 if fuzzy else 1


class Gazetteer:
    """In-memory index over the gazetteer + corpus — load once, reuse."""

    def __init__(self, paths=None, corpus_paths=None):
        self._paths = paths if paths is not None else GAZETTEER_PATHS
        self._corpus_paths = (corpus_paths if corpus_paths is not None
                              else CORPUS_PATHS)
        self._rows: Optional[list] = None
        self._vocab: Optional[list] = None
        self._postings: Optional[dict] = None
        self._tri: Optional[dict] = None

    # --- loading -------------------------------------------------------------
    def _add_row(self, rows: list, idx, name: str, kind: str,
                 lat, lon, pop: float, aliases: list) -> None:
        norm = normalize(name)
        if not norm or lat is None or lon is None:
            return
        match = norm.split()
        seen = set(match)
        for al in aliases or []:
            for t in normalize(al).split():
                if t not in seen:
                    seen.add(t)
                    match.append(t)
        # one-level alias expansion (bag semantics, index side)
        table = alias_table()
        for t in list(match):
            for alt in table.get(t, ()):
                for a in alt:
                    if a not in seen:
                        seen.add(a)
                        match.append(a)
        rows.append({
            "idx": idx,
            "name": name,
            "norm": norm,
            "display_tokens": norm.split(),
            "match_tokens": match,
            "kind": kind or "place",
            "lat": float(lat), "lon": float(lon),
            "pop": float(pop or 0.0),
        })

    def _load(self) -> list:
        if self._rows is not None:
            return self._rows
        rows: list = []

        for p in self._paths:
            if not p or not os.path.exists(p):
                continue
            try:
                with open(p, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except (OSError, ValueError):
                continue
            for i, e in enumerate(data):
                self._add_row(rows, i, e.get("n") or "",
                              e.get("c") or "place",
                              e.get("lat"), e.get("lon"),
                              e.get("k") or 0.0, [])
            break  # first readable gazetteer file wins

        for p in self._corpus_paths:
            if not p or not os.path.exists(p):
                continue
            try:
                fh = open(p, "r", encoding="utf-8")
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
                    self._add_row(rows, e.get("id"),
                                  e.get("display") or "",
                                  e.get("category") or "place",
                                  e.get("lat"), e.get("lon"),
                                  e.get("popularity") or 0.0,
                                  e.get("aliases") or [])
            break  # first readable corpus file wins

        # dedupe: same normalized name inside a ~110 m cell keeps the
        # most popular row (corpus ships near-duplicate place rows)
        best: dict = {}
        for r in rows:
            key = (r["norm"], round(r["lat"], 3), round(r["lon"], 3))
            prev = best.get(key)
            if prev is None or r["pop"] > prev["pop"]:
                best[key] = r
        rows = list(best.values())

        self._rows = rows
        postmap: dict = {}
        for i, r in enumerate(rows):
            for t in set(r["match_tokens"]):
                postmap.setdefault(t, []).append(i)
        self._vocab = sorted(postmap)
        self._postings = postmap
        self._tri = {}
        for vid, tok in enumerate(self._vocab):
            for key in _trigrams(tok):
                self._tri.setdefault(key, []).append(vid)
        return self._rows

    def count(self) -> int:
        return len(self._load())

    def by_index(self, idx) -> Optional[dict]:
        for r in self._load():
            if r["idx"] == idx:
                return r
        return None

    # --- query ---------------------------------------------------------------
    def _candidates(self, groups: list) -> dict:
        """{row_i: {atom: quality}} — prefix scan + trigram-gated fuzzy."""
        atom_best: dict = {}
        vocab = self._vocab
        seen_atoms: set = set()
        atoms = [a for g in groups for alt in g for a in alt]
        for a in atoms:
            if a in seen_atoms:
                continue
            seen_atoms.add(a)
            scored: dict = {}
            lo = bisect.bisect_left(vocab, a)
            vid = lo
            while vid < len(vocab) and vocab[vid].startswith(a):
                scored[vid] = len(a) / len(vocab[vid])
                vid += 1
            la = len(a)
            if la >= 4:
                bound = 1 if la < 8 else 2
                for key in _trigrams(a):
                    for cvid in self._tri.get(key, ()):
                        if cvid in scored:
                            continue
                        t = vocab[cvid]
                        if abs(len(t) - la) > bound:
                            continue
                        d = _lev_bound(a, t, bound)
                        if d <= bound:
                            scored[cvid] = 1.0 - d / max(la, len(t))
            for vid2, qv in scored.items():
                for ri in self._postings[vocab[vid2]]:
                    row = atom_best.get(ri)
                    if row is None:
                        atom_best[ri] = {a: qv}
                    elif qv > row.get(a, 0.0):
                        row[a] = qv
        return atom_best

    def _kind_boost(self, atoms: set, kind: str) -> float:
        k = (kind or "").lower()
        for words, kinds in _INTENT_KINDS.items():
            if atoms & set(words):
                if any(s in k for s in kinds):
                    return KIND_BOOST
        else:
            if any(s in k for s in _LOCALITY_KINDS):
                return _LOCALITY_BOOST
        return 0.0

    def search(self, q: str, lat: Optional[float] = None,
               lon: Optional[float] = None, limit: int = 8) -> list:
        rows = self._load()
        qn = normalize(q)
        if not rows or not qn or limit <= 0:
            return []
        blat = lat if lat is not None else 28.6139
        blon = lon if lon is not None else 77.2090

        groups = _query_groups(qn, alias_table())
        atom_best = self._candidates(groups)
        atoms_set = {a for g in groups for alt in g for a in alt}
        need = max(1, math.ceil(len(groups) * MIN_COV))

        scored = []
        for ri, amap in atom_best.items():
            r = rows[ri]
            # group quality: best fully-matched alternative (min atom
            # quality within the alternative)
            sum_q = 0.0
            matched = 0
            fuzzy = False
            for alts in groups:
                gq = 0.0
                for alt in alts:
                    aq = min(amap.get(a, 0.0) for a in alt)
                    if aq > gq:
                        gq = aq
                if gq > 0:
                    matched += 1
                    if not any(t.startswith(a)
                               for alt in alts for a in alt
                               for t in r["match_tokens"]):
                        fuzzy = True
                sum_q += gq
            if matched < need or matched == 0:
                continue
            # lead query token must be covered — kills the
            # 'X + locality-tail' noise ('haldiram chandni' must be a
            # haldiram hit, not any chandni hit)
            lead_alts = groups[0]
            if max((min(amap.get(a, 0.0) for a in alt)
                    for alt in lead_alts), default=0.0) <= 0:
                continue
            G = len(groups)
            pq, cov = sum_q / G, matched / G
            disp = r["display_tokens"]
            # display precision — prefix either direction (cheap: the
            # term only breaks score ties between same-coverage rows)
            prec = (sum(1 for t in disp
                        if any(t.startswith(a) or a.startswith(t)
                               for a in atoms_set)) / len(disp)
                    if disp else 0.0)
            d = _haversine_m(blat, blon, r["lat"], r["lon"])
            score = (W_PQ * pq + W_COV * cov + W_POP * r["pop"]
                     + W_PREC * prec
                     + self._kind_boost(atoms_set, r["kind"])
                     - W_DIST * math.log1p(d / 1000.0))
            scored.append((score, d, r, cov, fuzzy))
        scored.sort(key=lambda t: (-t[0], t[1], t[2]["name"]))

        out = []
        for score, d, r, cov, fuzzy in scored[:limit]:
            if cov >= 1.0:
                cls = 0 if r["norm"].startswith(qn) else (2 if fuzzy else 1)
            else:
                cls = 3
            out.append({
                "id": (f"gaz:{r['idx']}" if isinstance(r["idx"], int)
                       else f"cor:{r['idx']}"),
                "name": r["name"],
                "subtitle": r["kind"],
                "lat": r["lat"], "lon": r["lon"],
                "kind": r["kind"],
                "match": ("exact-prefix" if cls == 0 else
                          "token-prefix" if cls == 1 else
                          "fuzzy" if cls == 2 else "other"),
                "match_rank": cls,
                "score": round(score, 4),
                "distance_m": round(d),
                "source": ("gazetteer" if isinstance(r["idx"], int)
                           else "corpus"),
                "sources": ["t1"],
            })
        return out


GAZ = Gazetteer()
