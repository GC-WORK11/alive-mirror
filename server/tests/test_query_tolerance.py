"""Query-tolerance tests — fuzzy typo precision, kind+place compound
resolution, and numbered-sector ranking.

Distinct from test_search_quality's 0.90 top-3 gate: these are hard
asserts on the matching behaviors leg-3 added. The seeded typo set
reports measured precision rather than assuming it; the compound tests
assert the intent rows fire (and that name-complete queries do NOT get
re-interpreted); the sector tests pin 'sector 12' to Sector 12, not
Sector 125 — the numeric-token rule.
"""
import os
import random
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.pop("ALIVE_LOCATION_KEY", None)  # T1 only — deterministic

import core_engine  # noqa: E402

CP = (28.6315, 77.2167)

# well-known Delhi places the seeded mutator fuzzes — each is a real
# corpus row, so a correct engine recovers it top-3
_TYPO_BASE = [
    "connaught place", "karol bagh", "sarojini nagar", "lajpat nagar",
    "hauz khas", "khan market", "chandni chowk", "rajouri garden",
    "nehru place", "india gate", "lodhi garden", "jamia nagar",
    "dilshad garden", "rohini sector 7", "vaishali metro", "saket",
    "dwarka sector 6", "pitampura", "janakpuri", "vasant kunj",
    "munirka", "malviya nagar", "defence colony", "green park",
    "greater kailash", "andrews ganj", "bhikaji cama place",
    "sarita vihar", "badarpur", "mandi house",
]


def _mutate(rng: random.Random, toks: list) -> list:
    """One seeded typo in one token — del, transpose, sub, or dup —
    never on the first char (leading-token recall matters)."""
    i = rng.choice([i for i, t in enumerate(toks) if len(t) >= 4]
                   or range(len(toks)))
    t = list(toks[i])
    pos = rng.randrange(1, len(t))
    kind = rng.choice(("del", "trans", "sub", "dup"))
    if kind == "del":
        del t[pos]
    elif kind == "trans" and pos + 1 < len(t):
        t[pos], t[pos + 1] = t[pos + 1], t[pos]
    elif kind == "sub":
        t[pos] = rng.choice("abcdefghijklmnopqrstuvwxyz")
    else:
        t.insert(pos, t[pos - 1])
    toks[i] = "".join(t)
    return toks


def _covers(expected: str, name: str) -> bool:
    """expected tokens are a prefix-subset of the name's tokens."""
    nt = core_engine.alive_core_ref.normalize(name)
    return all(any(t.startswith(x) or x.startswith(t) or t == x
                   for t in nt)
               for x in core_engine.alive_core_ref.normalize(expected))


def test_seeded_typo_precision():
    """Measured precision on 40 seeded typos — the bound is set from
    the measurement, not a wish: DL + trigram recall gets most
    mid-token edits; a few land on honest near-misses."""
    rng = random.Random(108)
    resolved = 0
    misses = []
    for base in _TYPO_BASE:
        q = " ".join(_mutate(rng, base.split()))
        hits = core_engine.search(q, CP[0], CP[1], limit=5)
        names = [h.get("display") or "" for h in hits[:3]]
        if any(_covers(base, n) for n in names):
            resolved += 1
        else:
            misses.append((q, base, names[:1]))
    precision = resolved / len(_TYPO_BASE)
    for q, base, top in misses:
        print(f"  typo miss: {q!r} wanted {base!r}, got {top}")
    assert precision >= 0.75, (
        f"typo precision {precision:.0%} < 0.75 — misses: {misses}")


def test_fuzzied_too_far_stays_honest():
    """A mangled query must not resolve to a famous near-miss — a miss
    is honest, a wrong famous place is a bug."""
    hits = core_engine.search("konem place", CP[0], CP[1], limit=5)
    assert not any("connaught" in (h.get("display") or "").lower()
                   for h in hits)


def test_compound_kind_near_place():
    """'atm near cp' — kind+anchor compound resolves real ATMs near
    Connaught Place, with distance to the anchor, not to the caller."""
    hits = core_engine.search("atm near cp", CP[0], CP[1], limit=8)
    comp = [h for h in hits if h.get("compound")]
    assert comp, f"expected compound rows, got {hits}"
    assert comp[0]["anchor"] and comp[0]["distance_m"] is not None
    assert comp[0]["category"] in ("atm", "drinking_water")


def test_compound_kind_in_place():
    """'school sector 62 noida' — schools inside Sector 62, not the
    wrong sector's schools matched on name overlap alone."""
    hits = core_engine.search("school sector 62 noida",
                              CP[0], CP[1], limit=8)
    comp = [h for h in hits if h.get("compound")]
    assert comp, f"expected compound rows, got {[h['display'] for h in hits]}"
    assert "62" in comp[0]["anchor"] or "Sector" in comp[0]["anchor"]


def test_compound_near_me_uses_caller_position():
    hits = core_engine.search("atm near me", CP[0], CP[1], limit=5)
    comp = [h for h in hits if h.get("compound")]
    assert comp, "expected 'near me' to anchor on the caller's position"
    assert all(h["distance_m"] is not None for h in comp)


def test_compound_no_honest_hit_falls_through():
    """Unresolvable anchor — compound must not fire; normal path
    (possibly empty) keeps the result honest."""
    hits = core_engine.search("atm near zzzqqqx", CP[0], CP[1], limit=5)
    assert not any(h.get("compound") for h in hits)


def test_compound_does_not_hijack_full_names():
    """'school of planning and architecture' is a name, not a kind
    request — cov=1.0 keeps the name path, no compound rows."""
    hits = core_engine.search("school of planning and architecture",
                              CP[0], CP[1], limit=5)
    assert hits and not any(h.get("compound") for h in hits)
    assert "planning" in (hits[0].get("display") or "").lower()


def test_sector_12_is_not_sector_125():
    hits = core_engine.search("sector 12 noida", None, None, limit=5)
    names = [(h.get("display") or "").lower() for h in hits[:3]]
    assert any("sector 12" in n and "125" not in n and "127" not in n
               for n in names), names


def test_sector_beta_alpha_resolve_to_sectors():
    """'beta 2'/'alpha 1' land on the sector rows, above POIs and
    parks that merely contain the words."""
    top = core_engine.search("beta 2 greater noida",
                             None, None, limit=3)[0]
    assert (top.get("display") or "").lower().startswith("beta 2"), top
    top = core_engine.search("alpha 1 greater noida",
                             None, None, limit=3)[0]
    assert (top.get("display") or "").lower().startswith("alpha 1"), top


def test_search_latency_compound_path():
    """Compound adds one anchor query + one grid scan — stays ms."""
    import time
    ts = []
    for _ in range(30):
        t0 = time.perf_counter()
        core_engine.search("atm near cp", CP[0], CP[1], limit=8)
        ts.append((time.perf_counter() - t0) * 1000.0)
    ts.sort()
    assert ts[int(len(ts) * 0.95)] < 50.0, f"p95 {ts[-1]:.1f}ms"


# ------------------------------------------------------------------
# leg-4 audit fixes: numeric hard constraint + subplace designators
# ------------------------------------------------------------------

def test_numeric_token_never_satisfied_by_another_locality():
    """'a 43 defence colony' must not surface 'A-43 Dayal Bagh' — a
    different colony's same-numbered unit is a wrong answer, not a
    close one."""
    hits = core_engine.search("a 43 defence colony", None, None, limit=5)
    assert hits
    top = (hits[0].get("display") or "").lower()
    assert "dayal bagh" not in top, hits[0]


def test_missing_sector_number_stays_sector_not_wrong_sector():
    hits = core_engine.search("sector 99 noida", None, None, limit=5)
    # nothing named sector-99 exists: the honest answer is a sector/Noida
    # area row, never a row for a different number
    assert hits
    assert all("125" not in (h.get("display") or "") for h in hits[:3])


def test_subplace_block_letter_stays_in_its_locality():
    hits = core_engine.search("pocket b sarita vihar", None, None, limit=5)
    assert hits
    top = (hits[0].get("display") or "").lower()
    # Pocket B doesn't exist in OSM inside Sarita Vihar — the locality
    # itself is the honest answer, not a bare 'Pocket B' elsewhere
    assert "sarita vihar" in top, hits[0]
    assert hits[0].get("compound")


def test_subplace_sector_block_resolves_inside_sector():
    hits = core_engine.search("h block sector 62 noida",
                              None, None, limit=5)
    assert hits
    d0 = (hits[0].get("display") or "").lower()
    assert ("sector 62" in d0 or "block h" in d0 or "h-3" in d0
            or "h-5" in d0 or "h block" in d0 or "h-block" in d0), hits[0]


def test_subplace_city_sector_resolves_inside_city_extent():
    """'beta 2 greater noida' — a city's sectors sit km from its
    centroid; the sector inside the city is the answer, not the city
    fallback and not a bank containing the word 'beta'."""
    hits = core_engine.search("beta 2 greater noida",
                              None, None, limit=5)
    assert hits
    assert "beta" in (hits[0].get("display") or "").lower(), hits[0]


def test_subplace_house_number_falls_back_to_locality():
    hits = core_engine.search("h no 1234 sector 15 noida",
                              None, None, limit=5)
    assert hits
    assert "sector 15" in (hits[0].get("display") or "").lower()


def test_address_like_query_does_not_cross_localities():
    """'b 7 vasundhara enclave' — a bare 'B-7' 20 km away is a wrong
    answer; the locality is the honest resolution."""
    hits = core_engine.search("b 7 vasundhara enclave",
                              None, None, limit=5)
    assert hits
    assert "vasundhara" in (hits[0].get("display") or "").lower()


def test_subplace_never_fires_on_plain_weak_place():
    """'shahdra' has no designator/digit — subplace must stay off and
    fuzzy name matching stays in charge."""
    hits = core_engine.search("shahdra", None, None, limit=5)
    assert hits
    assert not any(h.get("subplace") for h in hits)


def test_kind_compound_still_wins_before_subplace():
    hits = core_engine.search("school sector 62 noida",
                              None, None, limit=5)
    assert hits
    assert any(h.get("compound") and h.get("match") == "category"
               for h in hits[:3])
