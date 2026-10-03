"""Parity tests — C++ alive_core.SearchIndex vs Python reference.

Asserts identical result ORDER and scores (1e-9) over:
  - the 20 fixed Delhi queries in <repo>/tests/search_queries.txt
  - >=200 generated prefix/typo queries built from the real gazetteer
  - a no-geo-bias run of the fixed queries
plus the Python-fallback path when alive_core is absent.
"""

import os
import random
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "core", "build"))

import alive_core_ref as ref  # noqa: E402

SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(SERVER_DIR)
QUERIES_FILE = os.path.join(REPO_ROOT, "tests", "search_queries.txt")
DELHI_BIAS = (28.6139, 77.2090)  # Connaught Place
SCORE_TOL = 1e-9
LIMIT = 10


def _fixed_queries() -> list[str]:
    out = []
    with open(QUERIES_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            out.append(line.split("\t")[0])
    return out


def _typo(tok: str, rng: random.Random) -> str:
    """One random edit on a token (sub / del / swap / ins)."""
    op = rng.randrange(4)
    i = rng.randrange(len(tok))
    if op == 0:  # substitute
        return tok[:i] + rng.choice("abcdefghijklmnopqrstuvwxyz") + tok[i + 1:]
    if op == 1:  # delete
        return tok[:i] + tok[i + 1:]
    if op == 2 and len(tok) > 2:  # swap adjacent
        i = rng.randrange(len(tok) - 1)
        return tok[:i] + tok[i + 1] + tok[i] + tok[i + 2:]
    # insert
    return tok[:i] + rng.choice("abcdefghijklmnopqrstuvwxyz") + tok[i:]


def _generated_queries(entries: list[dict], n: int = 240) -> list[str]:
    """Deterministic prefix/typo/multi-token queries from real names."""
    rng = random.Random(108)
    usable = [e for e in entries if ref.normalize(e["display"])]
    out: list[str] = []
    while len(out) < n:
        e = rng.choice(usable)
        toks = ref.normalize(e["display"])
        kind = rng.randrange(10)
        if kind < 4:  # prefix of one token
            t = rng.choice(toks)
            k = rng.randint(3, len(t)) if len(t) >= 3 else len(t)
            out.append(t[:k])
        elif kind < 7:  # typo inside a >=5-char token
            cand = [t for t in toks if len(t) >= 5]
            if not cand:
                continue
            out.append(_typo(rng.choice(cand), rng))
        elif kind < 9:  # multi-token: full first token + prefix/typo second
            if len(toks) < 2:
                continue
            t2 = rng.choice(toks[1:])
            if len(t2) >= 5 and rng.random() < 0.5:
                t2 = _typo(t2, rng)
            else:
                t2 = t2[: rng.randint(2, len(t2))] if len(t2) >= 2 else t2
            out.append(f"{toks[0]} {t2}")
        else:  # full normalized name
            out.append(" ".join(toks))
    # edge cases that must not diverge
    out += ["", "a", "zz", "the", "!!!", "कashmere", "café", "connaught  plce",
            "CP", "sec 18", "gk 2", "iit", "t3", "q", "99", "st mary"]
    return out


@pytest.fixture(scope="module")
def entries():
    return ref.entries_from_gazetteer()


@pytest.fixture(scope="module")
def aliases():
    return ref.load_aliases()


@pytest.fixture(scope="module")
def py_idx(entries, aliases):
    return ref.PySearchIndex(entries, aliases)


@pytest.fixture(scope="module")
def cpp_idx(entries, aliases):
    cpp = pytest.importorskip(
        "alive_core", reason="C++ module not built (server/core/build)")
    return cpp.SearchIndex(entries, aliases, ref.W_PREFIX, ref.W_COVERAGE,
                           ref.W_POPULARITY, ref.W_DISTANCE)


def _assert_same(cpp_idx, py_idx, q, lat, lon):
    rc = cpp_idx.query(q, lat, lon, LIMIT)
    rp = py_idx.query(q, lat, lon, LIMIT)
    ids_c = [r["id"] for r in rc]
    ids_p = [r["id"] for r in rp]
    assert ids_c == ids_p, f"order mismatch for {q!r}: {ids_c} != {ids_p}"
    for a, b in zip(rc, rp):
        assert a["display"] == b["display"]
        assert abs(a["score"] - b["score"]) < SCORE_TOL, (
            f"score mismatch for {q!r} id={a['id']}: "
            f"{a['score']} vs {b['score']}")


def test_parity_fixed_queries(cpp_idx, py_idx):
    queries = _fixed_queries()
    assert len(queries) == 20
    for q in queries:
        _assert_same(cpp_idx, py_idx, q, *DELHI_BIAS)


def test_parity_fixed_queries_no_bias(cpp_idx, py_idx):
    for q in _fixed_queries():
        _assert_same(cpp_idx, py_idx, q, None, None)


def test_parity_generated_queries(cpp_idx, py_idx, entries):
    queries = _generated_queries(entries)
    assert len(queries) >= 220
    for q in queries:
        _assert_same(cpp_idx, py_idx, q, *DELHI_BIAS)


def test_normalize_parity(cpp_idx, entries):
    cpp = pytest.importorskip("alive_core")
    for e in entries[:2000]:
        assert cpp.normalize(e["display"]) == ref.normalize(e["display"])
    for s in ["café №5", "Sarāi Kāle Khān", "ﬁnal", "a\u0301b", "𝐚𝐛𝐜", "µm"]:
        assert cpp.normalize(s) == ref.normalize(s)


def test_dl_distance_parity(cpp_idx):
    cpp = pytest.importorskip("alive_core")
    for a, b in [("abcd", "abdc"), ("sarojni", "sarojini"), ("place", "plce"),
                 ("kashmere", "kashmir"), ("a", "b"), ("", ""), ("abc", ""),
                 ("university", "univeristy"), ("sector", "sectro"),
                 ("noida", "nodia"), ("delhi", "delhii")]:
        for bound in (1, 2, 8):
            assert cpp.dl_distance(a, b, bound) == ref.dl_distance(a, b, bound)


def test_fallback_when_cpp_absent(monkeypatch, entries, aliases):
    """get_search_index must degrade to PySearchIndex without alive_core."""
    monkeypatch.setattr(ref, "HAVE_CPP", False)
    idx = ref.get_search_index(entries, aliases)
    assert isinstance(idx, ref.PySearchIndex)
    hits = idx.query("connaught place", *DELHI_BIAS, limit=5)
    assert hits and hits[0]["score"] > 0


def test_factory_prefers_cpp(entries, aliases):
    if not ref.HAVE_CPP:
        pytest.skip("alive_core not built")
    import alive_core  # noqa: E402
    idx = ref.get_search_index(entries, aliases)
    assert isinstance(idx, alive_core.SearchIndex)
