# scorer-prior + search-regression lane — report

Two linked fixes from audit-3: (A) the 210k-row Overture merge left rows
carrying `overture:*` category names that neither the server kind map
nor the mobile `KIND_RE` understood → five `test_query_tolerance`
failures; (B) the mobile scorer ranked Overture's misspelled "Chandini
Chowk" rows above the real "Chandni Chowk" on the fuzzy path → needed
an authority prior. Branch `base/v2`, direct push, no PR.

## A) F5 regression — overture categories now cook

- `alive_core_ref.py` — `entries_from_gazetteer` strips the
  `overture:` prefix at ingest (`category.removeprefix("overture:")`),
  matching exactly what the shipped mobile gazetteer already stores.
  One strip point fixes row emission, kind matching and the rev/geo
  paths uniformly — no parallel resolver map.
- `core_engine.py` — `_KIND_PHRASES` extended with the post-strip
  Overture names (~40 phrases: `atm`, `bank_or_credit_union`,
  `place_of_learning`+the education set, `lodging`/`bed_and_breakfast`,
  `casual_eatery`/food-service set, the health set, transit
  `public_transit_facility_or_service`/`rail_facility_or_service`, …).
- `Mobile/src/search/parse.ts` — `KIND_RE` extended with the same
  post-strip names so the offline kind-fallback regexes hit them.

### Compound strictness + locality radius

- `_AREA_KINDS` (frozenset) + `_COMPOUND_AREA_MAX_M = 2600` in
  `core_engine.py`. The 2600 m loosened radius applies ONLY when the
  resolved anchor is a container place (locality/sector/macrohood…) —
  'pawan bakery shahdara' sweeps Shahdara's edges; a street anchor
  stays at `_COMPOUND_MAX_M`.
- `_subplace(..., strict=)` + `_unit_leading`: strict mode keeps only
  rows whose normalized display *leads* with the unit ask
  ('beta 2…'), and falls back to a bare area row rather than a foreign
  colony's unit. `_compound` runs strict whenever the name side was
  strong (`strict = not weak`), and refuses a named-POI anchor —
  'school of planning and architecture' resolves to the MBS school
  (a building), so no compound hijack; 'school sector 62 noida'
  anchors on the Sector 62 place row, so the compound runs.
- Verified tension case: 'atm near cp' keeps real ATMs at Connaught
  Place (`match:category`), 'atm near zzzqqqx' stays an honest empty.

## B) scorer authority prior — `t0.ts`

- `AUTH_W = 7` — the weight band canonical gazetteer rows live in
  (localities/stations/landmarks run w7-11; Overture POIs w4-6).
- New **leading-prefix tier** in `matchStage`: when the entry's whole
  name is a leading prefix of the query (`beta 2 greater noida` → the
  `Beta 2` row), it scores `70 + 15·(rowToks/queryToks)` — under
  exact-prefix, above substring. Gated to `LEAD_AREA` kinds
  (area-kind rows plus `residential`/`gated_community`/…) or `w ≥
  AUTH_W`, so a light stub can't claim the slot and suppress the
  fuzzy pass a fuller match needs.
- **Authority rescue**: after scoring, any weak row (`w < AUTH_W`)
  looks up its fused-skeleton postings; a heavy sibling with the same
  `fskel` that still satisfies every query fold within DL≤2 is the
  real answer — promoted to the weak row's own slot +0.5 (never
  higher), or pushed if unscored. Misspellings stay listed, demoted.
- **Homonym guard**: skeleton equality alone admitted `Khanna Market`
  (a different real place — `fold(khanna)=fold(khan)=kn`). The sibling
  must now also have the same token count with every token within DL 1
  of the weak row's tokens (`chandini→chandni` = 1 ✓,
  `khanna→khan` = 2 ✗).
- `push()` dedupe: same-name rows within ~400 m now keep the heavier
  row at its own slot (was first-seen-wins) — dedupe prefers
  authoritative.
- No Entry serialization change — `i` rides on the scored tuple only;
  shipped index chunks unchanged.

## Eval — `src/search/eval-search.mjs` (45 real Delhi queries)

Same 30 from search-depth + 15 added: sarojini nagar market, gurudwara
bangla sahib, select citywalk, atm near cp, school sector 62 noida,
beta 2, alpha 1 greater noida, chandi chowk, chandini chowk, hauz
khas, khan market, lajpat nagar, majnu ka tila, sarai kale khan,
lotus temple. Bias = Shahdara (28.68, 77.29).

| | before (HEAD `e43f2a3`) | after |
|---|---|---|
| HIT/ANS | 37 | **38** |
| SUB | 5 | 5 |
| MISS | 3 | **2** |

Original-30 subset: 25 HIT/ANS both runs — floor held.

Deltas:

| query | before | after |
|---|---|---|
| `chandi chowk` | MISS (only Overture's misspelled rows) | **HIT — `Chandni Chowk · station` #1**, misspellings demoted below |
| `chandini chowk` | `Chandini Chowk` shop #1 | canonical `Chandni Chowk` rows #1–2, shop #3 |
| `alpha 1 greater noida` | `Domino's | Alpha Commercial Belt` #1 | **`Alpha 1 · residential` #1**, station #2 |
| `beta 2` / `beta 2 greater noida` | lodging-first ordering on server; ok on mobile | `Beta 2 · residential` #1 both |
| `atm near cp` | SUB — real ATMs at CP | SUB — same rows, still honest |
| `school sector 62 noida` | SUB — Sector 62 area rows | SUB — same |
| `dominos vikaspuri` | `Domino's Pizza | Vikaspuri` #1 | #1 again — preserved (see below) |
| `khan market` | `Khan Market` rows lead | `Khan Market` leads; `Khanna Market` (different real place) no longer hijacks via skeleton equality |
| `pawan bakery shahdara` | MISS | MISS — row doesn't exist in the gazetteer (server corpus only, `casual_eatery`, 2 km out); honest |
| `pappu bakery shahdara` | MISS | MISS — the `Pappu · clothes` stub stays suppressed so the fuzzy pass still reaches real fuller rows |

Caught-and-fixed during the lane (regressions the first draft caused):

- `dominos vikaspuri` — the Vikaspuri branch only ever scored via the
  *fuzzy* pass (`domino s pizza vikaspuri delhi` doesn't prefix-cover
  `dominos`); leadpref stubs made `scored` non-empty, fuzzy never ran,
  the branch vanished. Fix: leadpref gated to `LEAD_AREA`/`w≥7`.
- `khan market` — `Khanna Market` led via fskel-equal rescue; fixed
  with the DL≤1 token gate.

## Gates — all green

- `server`: `pytest tests` — **1268 passed**, 5 skipped, 2 xfailed (incl.
  `test_query_tolerance` 26/26 — the 5 failures are gone)
- `Mobile`: `tsc --noEmit` clean · `expo lint` clean
- `node:test` runners: store 99 · nav 100 · api 37 · offline 16 ·
  search 12 — all pass
- `eval-search.mjs` — table above, 45 cases

## Files

- `server/alive_core_ref.py` — overture prefix strip at ingest
- `server/core_engine.py` — `_KIND_PHRASES` coverage, `_AREA_KINDS`,
  strict `_subplace`/`_compound`, locality radius
- `Mobile/src/search/parse.ts` — `KIND_RE` coverage
- `Mobile/src/search/t0.ts` — `AUTH_W`, `LEAD_AREA` lead-prefix tier,
  authority rescue + homonym guard, heavier-row dedupe
- `Mobile/src/search/eval-search.mjs` — +15 Delhi cases

## Not done / watch

- 'pawan bakery shahdara' stays an honest miss on mobile — the row
  exists only in the server corpus. A gazetteer refresh that carries
  it would fix it; no fake row was added.
- `khan market` top row shows `residential` (w5) — the w10/w11
  `Khan Market` attraction/metro rows exist but the `khan`/`market`
  posting caps keep the search space thin; the metro station row does
  surface at #2. Cosmetic, not a miss.
- Server `match:area` rows for `school sector 62 noida` are
  Sector-62-anchored area rows, not schools — honest substitutes; the
  compound kind path reports `match:category` when a real school row
  is inside the anchor's radius.
