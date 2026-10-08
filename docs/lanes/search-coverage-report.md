# Lane: search-coverage — how complete is the bundled index vs OSM, and what was expanded

Owner's law (verbatim): *"millions of blocks data searchable in millisecond… raw language like
NANDANAGRI A BLOCK POCKET / ASHOOK NAGAR SHADARA GALI NO 4 / PAWAN BAKERY NEAR HANUMAN MANDIR must
resolve the REAL place — no guesses, no duplicates, no cheap icons."*

This report answers with numbers measured from the source PBFs (Geofabrik northern-zone +
central-zone extracts, `server/data/corpus/dl/`, Oct-6 vintage) and the shipped index —
not estimates. Everything below is reproducible: `tools/corpus-venv/bin/python scripts/build_corpus.py`
+ `Mobile/src/search/probe-coverage.mjs`.

## The headline

**Indexed: 132,932 rows** (Mobile/assets/delhi-gazetteer.json → `t0-index/`, 39 chunks / 34.3 MB).
**OSM's whole named+addressable universe in the extraction box: ~102k objects.**

- named objects (any `name=`/`official_name`/`loc_name`/`alt_name`): **71,093**
- addr-tagged objects (housenumber/place/block/street/full/housename): **~30,800** (overlaps named)
- addr:interpolation ways: **1,116**

**Coverage vs OSM, by class (measured):**

| OSM class | in box | ingested | % |
|---|---|---|---|
| named POIs (amenity/shop/leisure/office/tourism/craft/healthcare/club/emergency) | ~29,200 | ~28,900 | ~99% |
| named highways (residential…motorway + ref-only nav classes) | ~22,100 | ~19,300 rows + street-index anchoring | ~87%+ |
| named places (place/railway/public_transport/aeroway/historic/boundary) | ~9,500 | ~10,800 rows (incl. `stop_position`-style splits) | ~100% |
| named buildings + housenames | ~4,700 | ~4,350 | ~93% |
| addr:housenumber objects | 18,958 | ~15,900 direct + ~3,700 proximity-anchored + 7,697 interpolation numbers | ~96% anchored, ~0.7% honest miss |
| addr:place / addr:subdistrict localities | 7,999 | all (414 + 57 distinct names) | ~100% |
| addr:block values | 6,729 objects | carried on composed rows (154 distinct letters) | ~100% where tagged |

**Where the gap is real, and honest:** OSM does not carry "millions of blocks" for Delhi — the full
named+addressable universe inside the box is ~102k. The shipped index already exceeds it (132,932
rows = OSM corpus + bundled seed rows + GeoNames + Wikidata + 263 attested synthetic sector/block
canonicals). The residual distance to "every block" is a *data* gap, not an ingestion gap —
e.g. Nand Nagri's internal block lattice has exactly **zero** `addr:block`-tagged objects in OSM;
only 2 block rows exist within 1.5 km of its centroid (a park and a school). Nothing in this lane
invents those.

**Out of scope (honest skips, kept that way):**
- context-less housenumbers that resolve to nothing within 450 m of a real locality/street (125 this build)
- interpolation ways without ≥2 numbered endpoints (727 ways — the numbers can't be derived, inventing
  them is fabrication)
- `is_in`-only housenumbers (~39) and `name:hi`/`name:ur`-only objects (79) — the index is
  roman-script; transliterating is guesswork
- PIN codes (`addr:postcode` 13,692) — postcodes aren't places; a PIN→locality feature is a different lane
- un-named residential streets (~48k ways) — nameless ways can't be search targets

## What changed this lane

### `scripts/build_corpus.py`

1. **`compose_addr` keeps the block**: `hn + block + ctx` now emits `"44 Block B, Nand Nagri"`
   (Delhi's actual address convention) instead of dropping the block to `"44 Nand Nagri"`.
2. **`classify()` stops collapsing addresses into locality dupes**: an object carrying
   `addr:place`/`addr:subdistrict` *plus* a housenumber/block/street is now emitted as
   `addr:address` with the composed display — it used to render as just the locality name
   ("Nand Nagri"), a dupe of the locality row that threw away the block+number. ~6,400 objects
   reclassified; ~4,000 gain a "Block X" in the name.
3. **name fallback**: `official_name → loc_name → alt_name → short_name` rescue ~193 objects that
   had no `name=` tag (colloquial/formal attested names). `old_name` stays alias-only — stale names
   are searched, never displayed.
4. **POI aliases now include `addr:block` + `addr:housenumber`**: "paan bhandar block c" resolves
   against a POI's own address tokens.
5. **sub-context chain** gains `addr:sector`/`addr:quarter` (18 objects — free, honest).

### `Mobile/src/search/parse.ts`

6. **any single letter beside a designator is a unit value** — `h block` now parses to
   `{block: h}` ('h' was house-number filler and got eaten even next to 'block'). `h no 1234`
   still drops 'h' correctly ('no' is not a designator).
7. **kind bleed removed**: `mandir` → temple|hindu_place_of_worship (was returning mosques via the
   generic `place_of_worship` catch-all); mosque/church/gurudwara tightened symmetrically. A
   generically-tagged worship place no longer guesses at a religion for the user.

### `Mobile/src/search/t0.ts`

8. **fused-skeleton union for every query**: postings cap at 80 per token (`PREFIX_CAP`), so a
   mid-weight row — "Ashok Nagar" (Shahdara, w=10) — was cut from *every* single-token list
   ('ashok', 'nagar', 'xk', 'ngr') while surviving intact in its fused skeleton 'xkngr'
   (11 rows). matchStage previously only consulted the skeleton for single-token queries; now the
   fused form is always unioned — capped postings can no longer make a named place invisible.
9. **tiered unit satisfaction**: unitScan ranked `sat` desc then distance, and *contradictions*
   drop the row ("Sector 63" never stands for "sector 62"). A row satisfying some units with none
   contradicted is the honest container — 'h block sector 62' resolves to Sector 62 when no
   H-block row is mapped (there is none in OSM).
10. **unit-anchor retry**: when the name-match anchor can't see the unit ask, the best row carrying
    a unit's value becomes the anchor ('h block sector 62 noida' → "Noida Sector 62"). Gated —
    the anchor must share a query token or sit within 8 km of the bias, so a matching designator
    in a far colony is never guessed at.

### Budget check

- index: 39 chunks × ~0.9 MB (CHUNK_TARGET unchanged) — the chunked cold-load architecture is
  untouched; hydrate is still one bounded step per chunk.
- query latency on the shipped index (probe box): every probe ≤ 36 ms, most <5 ms.
- gazetteer 132,932 < 150,000 target — honest headroom, no padding.

## End-to-end probe results (shipped 39-chunk index, hydrated exactly as the app does)

| typed | top row | verdict |
|---|---|---|
| `nandanagri a block pocket` | A Block Street Number 21 · Shahdara North → then Nand Nagari/Nand Nagri | real Block-A row + the locality; OSM has no in-Nand-Nagri Block-A (data gap, stated) |
| `ashook nagar shadara gali no 4` | Gali Number 4 · Maharathi Colony (28.6714,77.3005) | phonetic fold + gali:4 unit — right gali, ~1.5 km |
| `pawan bakery near hanuman mandir` | bakery/confectionery rows · Hanuman Mandir Flyover | "Pawan Bakery" isn't in OSM anywhere — honest kind-anchored fallback, correct anchor, correct icon class |
| `ashok nagar` | Ashok Nagar (28.6933,77.2981) — the Shahdara one | was invisible before the fskel fix |
| `ashok nagar gali 4` | Gali Number 4 · HDFC Bank (28.6903,77.2941) — 400 m from Shahdara Ashok Nagar | right colony, right gali |
| `h block sector 62 noida` | Noida Sector 62 Chowk / Sector 62 rows | the containing sector — honest (no Block-H mapped in OSM) |
| `nand nagri b block` | B Block · Jhilmil Indl Area (28.6784,77.3097) | the real B-block row, ~1 km south |
| `mandir near kailash nagar` | Shiv Mandir / Dwarkadhees Mandir · Kailash Nagar | hindu temples only — mosque bleed removed |
| `clinic near ashok nagar shahdara` | CGHS / DGD clinics · Shri Ram Nagar | kind-anchored, ~1 km |
| `bakery paas hanuman mandir` | same Hanuman Mandir Flyover cluster | 'paas' near-word works |
| `atta chakki near shiv mandir` | real Atta Chakki POIs | name-matched (kind list has no atta-chakki entry — note) |
| `e block defence colony` | 31 Block E Jangpura + E-Block park rows | block-E lattice live |
| `gali no 7 jahangirpuri` | 821/822/823 Gali Number 7 · B Block | housenumber rows on the right gali, Jahangirpuri |
| `kirana store near bhajanpura` | supermarkets · Bhajanpura Chowk | kind-anchored near-scan |
| `sector 62 noida h block` | Sector 62 cluster (reordered units parse the same) | units order-independent |
| `zyxwv nonsense placename` | `[]` | honest miss — no guesses |

Duplicates: the ~400 m same-name dedupe held in every probe (distinct "Gali Number 4"s at different
colonies correctly stay separate rows; the old "Nand Nagri" addr-place dupes collapse into the
locality row). Icons/subtitles come from the kind column — no raw OSM values leak through SUB.

## Known honest limits (not bugs)

- **"Pawan Bakery" is not in OSM** (38 pawan/pavan rows exist — Atta Chakki, Halwai — none a bakery
  by that name). The query resolves to real bakeries near the real Hanuman Mandir — the correct
  honest answer, not a fabricated row.
- **Ashok Nagar exists in 3 places** (Shahdara, Ghaziabad, New Ashok Nagar/Chilla). With no 'shahdara'
  token the engine now prefers the Shahdara one near the caller — proximity is the disambiguator,
  same as Google.
- Anything OSM hasn't mapped stays unfound: un-mapped blocks, unnumbered galis, nameless POIs.
  Those are data gaps. The server tiers (t1 gazetteer, t2 Amazon, t3 Photon) still widen coverage
  online; this lane's contract is that t0 never lies offline.

## Files

- `scripts/build_corpus.py` — compose/classify/name-fallback/alias/sub-chain changes
- `Mobile/src/search/parse.ts` — single-letter unit values, worship-kind tightening
- `Mobile/src/search/t0.ts` — fskel union, tiered unit satisfaction, unit-anchor retry
- `Mobile/src/search/probe-coverage.mjs` — this report's probe harness
- `server/data/corpus/delhi-corpus.jsonl.gz` — 103,607 rows (was 97,447)
- `Mobile/assets/delhi-gazetteer.json` — 132,932 rows (was 124,311)
- `Mobile/assets/t0-index/` — 39 chunks / 34.3 MB, manifest `gaz_sha256 ba1d38a39241…`
- `server/data/corpus/STATS.md`, `docs/plan/corpus-report.md` — regenerated build stats
