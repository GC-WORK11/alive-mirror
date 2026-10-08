# search-tolerance-fix lane — `test_address_like_query_does_not_cross_localities`

Lane goal: the plain-words lane flagged a deterministic red —
`server/tests/test_query_tolerance.py::test_address_like_query_does_not_cross_localities`
fails on `base/v2`. Contract under test (the owner's #1 search ask —
*it should not assume, it should go through to the particular thing*):
an address-like query (`b 7 vasundhara enclave`) must resolve to THAT
locality, not silently land on a same-tokened row elsewhere.

HEAD at verification: `61364f3`. Prod untouched (GET-only rule; no
deploy).

## Verdict

**Option (a) — the new logic genuinely broke the unit contract, fixed
in the engine.** The test stands as written. `B-16 Gali Number 7` is
NOT a legitimate sibling for `b 7`: it is a different unit whose 'b'
and '7' satisfy the old token-containment check coincidentally ('b'
from `B-16`, '7' from `Gali Number 7`). Returning it asserts a
precision the corpus does not have — exactly the "assuming" behavior
the owner banned. The honest answers are the locality itself or a real
`B-7` inside it (none exists in the gazetteer).

## Root cause

Two search-lane waves interacted:

- `4a4854a` (multi-anchor `_subplace` resolve) + `e32624d` (engine-order
  merge, foreign-colony rejection) — the machinery.
- `7926c14` (search-coverage corpus rebuild, gazetteer 124k→133k rows,
  block-preserving addresses) — the data. `B-16 Gali Number 7` is one of
  the new address rows (`gaz:132326` — above the old 124k ceiling); it
  did not exist when `ee79c44` wrote the test.

`_subplace.resolve()` promoted any row inside the anchor's extent
radius whose **token set** covered `want`. For `b 7 vasundhara
enclave`: `want=[b,7]`; `B-16 Gali Number 7` normalizes to
`{b,16,gali,number,7}` — covers both want atoms, sits at 3.54 km
(inside the anchor's 3.59 km `extent*1.5` radius but past the ~1 km
locality itself), so it won promotion and the `subtitle` pinned
`· Vasundhara Enclave` onto a row at the fuzzy edge.

Proof it is the corpus + loose containment, not the merge order: every
engine version `pre_ee79c44`→HEAD returns the same wrong top against
the current gazetteer.

## Fix — unit-atom pairing (`server/core_engine.py`)

Adjacent unit atoms in the query must stay bound in the hit. New
helpers:

- `_unit_atom(t)` — letters, digits, designator words
  (`_SUBPLACE_STRUCT`); ordinary words break the unit run.
- `_unit_pairs(base, want)` — adjacent pairs on the unit side of the
  query, computed on `base` so a consumed anchor token can never fuse
  a fake pair (`b 7` → `{(b,7)}`, `gali no 4` → `{(gali,4)}`,
  `beta 2` → `{(beta,2)}`).
- `_unit_pairs_hold(dseq, etoks, pairs)` — each pair must appear in
  the hit adjacent in either order after the same `_DESIG_FILLER`
  strip, or fused (`b7`, `7b`). `B-16 Gali Number 7` fails `(b,7)`:
  its pairs are `(b,16)` + `(gali,7)` → falls through to the honest
  `_area_row`.

Applied in `resolve()` to both in-extent scans (name-path `hits` and
`nearest()` grid) and to the anchor-is-the-sub-place early return.
When the query carries no unit pair (`559` alone, `pocket b` where a
real `Pocket B` exists, `h block`) nothing tightens.

## Evidence

Probe (`PYTHONPATH=core/build312:.`, `ALIVE_LOCATION_KEY` unset):

| query | before | after |
|---|---|---|
| `b 7 vasundhara enclave` | **B-16 Gali Number 7** (wrong unit, edge of extent) | **Vasundhara Enclave** (honest locality) |
| `b-7 vasundhara enclave` | B-16 Gali Number 7 | Vasundhara Enclave |
| `ashook nagar shadara gali no 4` | Ashok Nagar | Ashok Nagar (unchanged — owner's example already correct) |
| `h block sector 62 noida` | H-Block · Sector 62 | H-Block · Sector 62 (real in-area unit still wins) |
| `beta 2 greater noida` | Beta 2 | Beta 2 (unchanged) |
| `a 43 defence colony` | 43 Block D · Defence Colony | 43 Block D · Defence Colony (`a` is a stop-word; `43` still pins) |
| `b-12 lajpat nagar` | Lajpat Nagar | Lajpat Nagar (foreign-colony rows still rejected) |
| `pocket b sarita vihar` | Sarita Vihar | Sarita Vihar (unchanged) |
| `house 559 udyog vihar` | 559 Udyog Vihar Ph V Rd | unchanged (name path) |

Sibling check per the lane rule: a hit that IS the asked unit keeps
winning — `H-Block` inside Sector 62 still promotes over the bare
sector row; only scattered-atom rows are gated.

## Gates

| gate | result |
|---|---|
| `test_query_tolerance.py` (26) | **26/26 pass** — was 2 fail (`test_address_like_query_does_not_cross_localities` + `test_search_latency_compound_path`) |
| search suite (`test_query_tolerance` + `test_search_quality` + `test_core_engine` + `test_v2` + `test_core_parity`) | 144 + 155 pass |
| full `pytest -q tests` | **1264 pass, 5 skip, 0 fail** |
| `cd Mobile && npx tsc --noEmit` | clean |
| `ruff check core_engine.py` | 0 new findings (5 pre-existing: I001, BLE001, 3×UP045) |

Notes:

- `test_search_latency_compound_path` red on this box before the fix
  was the documented pure-Python-fallback artifact — no `core/build*`
  ext existed here. Built `build312` via `core/build_ext.sh` (Eigen via
  Homebrew for `KrigeField`); the test then passes (suite file 2.05 s).
- `test_parity_krige` (25) initially failed `no attribute KrigeField` —
  the first build ran without Eigen. Rebuilt with `EIGEN_INC`; 51/51
  pass on `test_parity_krige` + `test_query_tolerance`. Both are
  environment artifacts of this fresh VM, not the patch.

## Files

- `server/core_engine.py` — `_unit_atom`, `_unit_pairs`,
  `_unit_pairs_hold`; applied inside `_subplace.resolve()` (+49/−4).
- `docs/lanes/search-tolerance-report.md` — this report.

[Written by Devin](https://app.devin.ai/sessions/c8603f34c35b43f684a6a2b18cf510f7)
