"""Search-quality acceptance harness — the fixed 20-query Delhi list.

docs/plan/09 Phase 1 acceptance: every query in
tests/search_queries.txt goes through GET /v2/search (TestClient, T1
only — the Amazon client is unset so results are deterministic) with a
Connaught-Place bias point, and the top-3 must contain the expected
place. Target: >= 18/20.

Expected-answer convention (parsed from the tab-separated file):
    query <TAB> expected place
The expected label is descriptive, so a result counts as correct when
  A) every token of the expected head (text before the first comma;
     '/' separates alternatives — any alternative fully covered counts)
     is covered by result-name tokens, or
  B) the result name is a strict part of the expected label (all its
     tokens covered by the expected tokens and the expected head's
     first token appears in the result).
"Cover" = prefix in either direction, DL distance <= 1 for tokens >= 4
chars, or a name token pair whose concatenation equals the expected
token ('cyber hub' covers 'cyberhub'). Digit/roman tokens form
equivalence classes ({4, iv, four}) and must match within their class —
'Lajpat Nagar 4' covers 'Lajpat Nagar IV' but not 'Lajpat Nagar II'.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.pop("ALIVE_LOCATION_KEY", None)  # T1 only — deterministic

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from v2 import deps  # noqa: E402
from v2.gazetteer import normalize  # noqa: E402

client = TestClient(main.app)

QUERIES_PATH = os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))),
    "tests", "search_queries.txt")
CP = (28.6315, 77.2167)  # Connaught Place bias

_NUM_CLASSES = [
    {"1", "i", "one"}, {"2", "ii", "two"}, {"3", "iii", "three"},
    {"4", "iv", "four"}, {"5", "v", "five"}, {"6", "vi", "six"},
    {"7", "vii", "seven"}, {"8", "viii", "eight"}, {"9", "ix", "nine"},
    {"10", "x", "ten"},
]
_NUM_OF = {t: i for i, cls in enumerate(_NUM_CLASSES) for t in cls}


def _lev1(a: str, b: str) -> bool:
    if abs(len(a) - len(b)) > 1 or not a or not b:
        return False
    if len(a) == len(b):
        return sum(1 for x, y in zip(a, b) if x != y) <= 1
    if len(a) > len(b):
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


def _tok_covers(exp_tok: str, name_tokens: list) -> bool:
    """One expected token covered by the result name tokens."""
    if exp_tok in _NUM_OF:
        return any(name_tok in _NUM_OF
                   and _NUM_OF[name_tok] == _NUM_OF[exp_tok]
                   for name_tok in name_tokens)
    for t in name_tokens:
        if t == exp_tok or t.startswith(exp_tok) or exp_tok.startswith(t):
            return True
        if len(exp_tok) >= 4 and _lev1(exp_tok, t):
            return True
    # 'cyberhub' covered by adjacent 'cyber' + 'hub'
    return any(t1 + t2 == exp_tok
               for t1, t2 in zip(name_tokens, name_tokens[1:]))


def _expected_hit(expected: str, name: str, subtitle: str = "") -> bool:
    head, _, _qual = expected.partition(",")
    name_tokens = normalize(name).split()
    exp_tokens = normalize(expected).split()
    if not name_tokens or not exp_tokens:
        return False
    # rule B: the result NAME is a strict part of the expected label
    # (subtitle/kind is metadata — it never makes a name 'contained')
    if (all(_tok_covers(t, exp_tokens) for t in name_tokens)
            and _tok_covers(normalize(head).split()[0], name_tokens)):
        return True
    # rule A may also credit kind/subtitle tokens toward coverage
    cover_tokens = name_tokens + [
        t for t in normalize(subtitle).split()
        if t not in name_tokens]
    # rule A: every token of one '/'-separated head alternative covered
    for alt in head.split("/"):
        alt_toks = normalize(alt).split()
        if alt_toks and all(_tok_covers(t, cover_tokens)
                            for t in alt_toks):
            return True
    return False


def _load_queries() -> list:
    out = []
    with open(QUERIES_PATH, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            q, exp = line.split("\t", 1)
            out.append((q.strip(), exp.strip()))
    return out


QUERIES = _load_queries()


@pytest.fixture(autouse=True)
def t1_only():
    deps.set_location(None)
    yield
    deps.set_location(None)


# --- the 20-query acceptance score ---------------------------------------------
def test_queries_file_is_parseable():
    assert len(QUERIES) == 20, f"expected 20 queries, got {len(QUERIES)}"


def test_acceptance_score_at_least_18_of_20():
    misses = []
    score = 0
    for q, expected in QUERIES:
        r = client.get("/v2/search",
                       params={"q": q, "lat": CP[0], "lon": CP[1]})
        assert r.status_code == 200, f"{q!r}: HTTP {r.status_code}"
        top3 = r.json()["results"][:3]
        hits = [res for res in top3
                if _expected_hit(expected, res.get("name") or "",
                                 res.get("subtitle") or "")]
        if hits:
            score += 1
        else:
            misses.append((q, expected,
                           [res.get("name") for res in top3]))
    detail = "\n".join(f"  {q!r} expected {e!r} got {names}"
                       for q, e, names in misses)
    print(f"\nACCEPTANCE SCORE: {score}/20")
    if misses:
        print(f"missing ({len(misses)}):\n{detail}")
    assert score >= 18, f"score {score}/20 < 18\n{detail}"


@pytest.mark.parametrize("q,expected", QUERIES,
                         ids=[q for q, _ in QUERIES])
def test_query_top3(q, expected):
    """Per-query visibility — the aggregate test above owns the >=18
    gate; this one marks exactly which queries miss, without failing
    the suite when the total still holds (xfail-under-threshold)."""
    r = client.get("/v2/search",
                   params={"q": q, "lat": CP[0], "lon": CP[1]})
    assert r.status_code == 200
    top3 = r.json()["results"][:3]
    hit = any(_expected_hit(expected, res.get("name") or "",
                            res.get("subtitle") or "")
              for res in top3)
    if not hit:
        pytest.xfail(
            f"top-3 miss for {q!r}: expected {expected!r}, got "
            f"{[res.get('name') for res in top3]}")


# --- response shape & timing -----------------------------------------------------
def test_response_shape_and_took_ms_truthful():
    r = client.get("/v2/search",
                   params={"q": "connaught", "lat": CP[0], "lon": CP[1]})
    assert r.status_code == 200
    body = r.json()
    for key in ("results", "t1", "t2", "t2_status", "took_ms",
                "tiers", "t1_engine"):
        assert key in body, f"missing response key {key!r}"
    assert body["tiers"] == ["t1"]
    assert body["t1_engine"] in ("alive_core", "alive_core_ref",
                                 "gazetteer")
    # t2 rows stay a list; the Amazon-tier status lives in t2_status
    assert isinstance(body["t2"], list)
    assert "disabled" in body["t2_status"]
    took = body["took_ms"]
    assert isinstance(took["t1"], (int, float)) and took["t1"] >= 0
    assert took["t2"] is None
    assert took["total"] >= took["t1"] - 0.05
    for res in body["results"]:
        assert {"name", "lat", "lon", "match", "match_rank",
                "sources", "distance_m"} <= set(res)
        assert res["match"] in ("exact-prefix", "token-prefix",
                                "fuzzy", "other")


# --- landmark ranking regression (geonames-popularity poisoning fix) ----------
# GeoNames rows carry raw population as `popularity`; before load-time
# normalization that term ran into the millions ('Hauz Khas' district at
# ~500k vs a real landmark at ~6) and buried every landmark query under
# district/locality rows. Each of these must be top-1, not merely top-3.
@pytest.mark.parametrize("q,name_sub", [
    ("india gate", "india gate"),
    ("dilli haat", "dilli haat"),
    ("khan market", "khan market"),
    ("qutub minar", "minar"),
    ("lodhi garden", "lodh"),
    ("nehru place", "nehru place"),
    ("lotus temple", "lotus"),
    ("akshardham", "akshard"),
])
def test_landmark_beats_geonames_popularity(q, name_sub):
    r = client.get("/v2/search",
                   params={"q": q, "lat": CP[0], "lon": CP[1]})
    assert r.status_code == 200
    top = r.json()["results"][:1]
    assert top, f"no results for {q!r}"
    assert name_sub in (top[0].get("name") or "").lower(), (
        f"{q!r} top-1 {top[0].get('name')!r} lacks {name_sub!r}")


@pytest.mark.parametrize("q,name_sub", [
    ("hkv", "hauz khas"),
    ("deerpark", "deer"),
])
def test_slang_aliases_hit(q, name_sub):
    r = client.get("/v2/search",
                   params={"q": q, "lat": CP[0], "lon": CP[1]})
    assert r.status_code == 200
    top3 = [res.get("name") or "" for res in r.json()["results"][:3]]
    assert any(name_sub in n.lower() for n in top3), (
        f"{q!r} top-3 {top3} lacks {name_sub!r}")


def test_popularity_normalization_bounds():
    """_norm_popularity: <=1 passes through; >1 log-maps into (0,1] with
    ordering preserved (Delhi-NCT ~16.7M ~ ceiling)."""
    from alive_core_ref import _norm_popularity
    assert _norm_popularity(0.0) == 0.0
    assert _norm_popularity(0.9) == 0.9
    assert _norm_popularity(1.0) == 1.0
    big = _norm_popularity(16_700_000)
    assert 0.95 <= big <= 1.0
    assert _norm_popularity(500) < _norm_popularity(50_000) < big
    assert _norm_popularity(4.0) < 0.2


# --- edge cases -------------------------------------------------------------------
def test_edge_single_char():
    r = client.get("/v2/search",
                   params={"q": "c", "lat": CP[0], "lon": CP[1]})
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["results"], list)


def test_edge_max_length_200():
    r = client.get("/v2/search",
                   params={"q": "x" * 200, "lat": CP[0], "lon": CP[1]})
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["results"], list)  # no crash is the contract
    assert body["took_ms"]["t1"] >= 0


def test_edge_over_max_length_rejected():
    r = client.get("/v2/search", params={"q": "x" * 201})
    assert r.status_code == 422


def test_edge_unicode():
    r = client.get("/v2/search",
                   params={"q": "क़रोल बाग़ मेट्रो",
                           "lat": CP[0], "lon": CP[1]})
    assert r.status_code == 200
    assert isinstance(r.json()["results"], list)


def test_edge_empty_q_rejected():
    r = client.get("/v2/search", params={"q": ""})
    assert r.status_code == 422


def test_edge_missing_q_rejected():
    r = client.get("/v2/search")
    assert r.status_code == 422
