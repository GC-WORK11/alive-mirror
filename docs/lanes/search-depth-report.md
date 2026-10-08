# search-depth lane — report

Owner's demand, verbatim: *"I want exact shop… show me the multiple shops. Then I will type full address, then you show me the shop that comes in that address."* — two modes: name→shops direct, address→browse shops. All real rows, nothing invented.

## 1. Max free gazetteer

New source: **Overture Maps `places` theme**, release `2026-09-23.1` — free parquet shards on S3 (`overturemaps-us-west-2`), pulled with duckdb `httpfs`+`spatial` straight off the bucket (no full-theme download, no creds).

- `scripts/fetch_overture.py` — lists the release's shards via S3 ListObjectsV2 (paginated), filters to the NCR extract bbox, keeps only named rows with a `basic_category`, drops `permanently_closed`, `confidence < 0.40`, and non-walk-up classes (real estate, wholesale, manufacturer, b2b*, taxi, storage, shipping, leagues, political, housing/property, event services, design/technical/media).
- Row confidence carried through: per-row `k = 0.60 + 0.35·conf` (emit prefers row `k` over the per-source constant). `source: "overture"`/`sources` kept on every row.
- Committed as `server/data/corpus/aux/overture-places.jsonl.gz` (244,425 rows; 77 MB raw → 16 MB gz). `merge_aux` reads `.jsonl.gz`; `fetch_overture` writes gz when `--out` ends `.gz`.
- `scripts/build_corpus.py --remerge-aux` — new mode: rebuilds from the committed corpus + aux only (no PBF re-parse). Drops the regenerable layers (overture-only rows, synthetic rows, stale `overture` in `sources`, `k`/`conf`) then re-merges.

**Real counts** (verified on the built files, not estimates):

| layer | rows |
|---|---|
| server corpus (`delhi-corpus.jsonl.gz`) | **344,923** |
| — overture | 244,762 |
| — osm | 90,729 |
| — wikidata | 7,262 |
| — geonames | 6,247 |
| — synthetic | 1,064 |
| bundled mobile gazetteer (`assets/delhi-gazetteer.json`) | **210,000** |
| t0 prebuilt index | 62 chunks, 55.4 MB |

## 2. Live fallback tier (t3, second callback)

`client.ts` restructured: **t1/t2 deliver immediately on the first `onResults`** — the keystroke path never awaits network. The web tier is a *second* callback `{t1,t2,t3,tookMs}` that only fires when local is weak: `t0Count + t1 + t2 < 3` (`SearchScreen` passes `localCount` = the t0 row count).

- **Photon first** (`photon.komoot.io`, no key), **Nominatim fallback** (`jsonv2` + NCR viewbox + `lat/lon` bias + `accept-language=en,hi`, honest UA, 1.5 s timeout). Shared 1 req/s throttle = Nominatim's strictest limit governs both.
- Web rows carry `tier:"t3"` and subtitle suffix **"from the web · live"** so the reader knows it's not the local index.
- Offline/timeout → `catch → []`, `t3` never blocks.

## 3. Address→shops browse mode

`t0.ts` adds `isBrowseAnchor(kind)` (areas + streets + address/unit kinds) and `nearbyPOIs(anchor, 800 m, cap 15)` — a GEO ring-scan ranked by the index's own fused `wt` minus distance pull, deduping same-name rows only inside ~200 m (real same-name neighbours survive). Roads/areas/infrastructure (`BROWSE_BAD`) never appear as "places here".

`SearchScreen` fires the section when the strongest merged answer is a browse anchor and nothing's picked yet: `shops & places here (n)` — **n is the real row count**, rows already answering above aren't repeated. i18n parity: `यहाँ की दुकानें और जगहें ({n})`.

## 4. Speed

Median eval query 0.2–1.6 ms; kind/compound scans up to ~85 ms on worst-case multi-token queries (one-shot cost, not per-keystroke — results still merge without jank since rows are memoized element trees). Web tier streams in on a second callback, never on the keystroke path.

## 5. Band ramp contrast — checked, no bug

Adjacent-band ΔE76 and luminance, Delhi's live range (bands 1–5 carry >95% of real days):

| pair | ΔE76 | ΔL* |
|---|---|---|
| band1→2 gold→orange | 19.0 | 5.3 |
| band2→3 orange→ember | 19.7 | 11.9 |
| band3→4 ember→brick | 14.7 | 10.5 |
| band4→5 brick→maroon | 24.1 | 13.3 |

Every adjacent pair ≥ ΔE 14.7 with **monotone luminance** (69→63→52→41→28); band0 stays the lone cool anchor. A winter day where Delhi genuinely sits in one band paints one hue — that's the honest field; within-band detail is carried by per-cell µg labels + band-inked edge seams + conf-alpha. Not touched (taste law: bands = air only).

## 30-query eval (shipped chunked index, LOC = Shahdara)

HIT/ANS **25** · SUB 3 · MISS 2 — misses are honest corpus gaps: no "Pawan Bakery" exists in *any* source near Shahdara (40 "Pawan" rows, none a bakery); "Pappu Bakery" exists but sits ~1.8 km from the Shahdara anchor, beyond the 1.5 km compound radius. Scorer-side note: "chandi chowk" ranks Overture's misspelling "Chandini Chowk" over the real wd:Q3236763 row in the mobile scorer (server engine still returns it) — flagged for a future popularity-prior pass.

| query | top hits | verdict | ms |
|---|---|---|---|
| karol bagh | Karol Bagh Terminal · bus_station | HIT | 1.6 |
| shahdara | Shahdara Flyover · primary | HIT | 0.4 |
| seelampur | Seelampur metro station · metro | HIT | 0.3 |
| laxmi nagar | Laxmi Nagar · macrohood | HIT | 0.2 |
| greater kailash | Greater Kailash · macrohood | HIT | 0.2 |
| rohini sector 7 | DAVPS SEC-7 Rohini | HIT | 7.5 |
| dwarka sector 6 | Dwarka-Palam Road · primary | HIT | 2.4 |
| chandni chowk | Chandni Chowk metro | HIT | 0.3 |
| noida sector 18 | Noida Sector 18 metro | HIT | 11.6 |
| pitampura | Pitampura · residential | HIT | 0.6 |
| india gate | India Gate Monument | HIT | 0.8 |
| connaught place | Connaught Place · macrohood | HIT | 0.3 |
| cp | Connaught Place · macrohood | HIT | 0.3 |
| haldiram | Haldiram's · restaurant | HIT | 0.6 |
| nirula | Nirulas Durgapuri | HIT | 0.2 |
| barista | Barista Coffee Cafe | HIT | 0.2 |
| dominos vikaspuri | Domino's Pizza Vikaspuri | HIT | 47.4 |
| jain sweets | Jain Sweets | HIT | 0.3 |
| agarwal sweets | Agarwal sweets sangam | HIT | 0.5 |
| pawan bakery shahdara | Alwin Bakery (nearest real) | MISS | 84.2 |
| pappu bakery shahdara | Bakingo Shahpur | MISS | 26.4 |
| gali no 5 bhalswa | Gali Number 5 · living_street | ANS +15 here | 7.9 |
| ashok nagar shahdara gali no 4 | Gali Number 4 · residential | ANS +15 here | 43.8 |
| nand nagri block a | Block A · residential | ANS +15 here | 2.1 |
| vikas marg laxmi nagar | Vikas Marg · primary | ANS +15 here | 84.0 |
| main market rani bagh | Rani Bagh · residential | ANS +15 here | 0.2 |
| khanpur devli road | Devli road, khanpur | ANS +15 here | 0.2 |
| bakery near hanuman mandir | Japani Samosa · bakery | SUB | 2.7 |
| atm near karol bagh | Axis Bank ATM | SUB | 3.4 |
| chemist near seelampur | ESIC / Anjum medical store | SUB | 2.4 |

Every address-mode anchor yielded 15 real browsable POIs inside 800 m (cap). Harness: `node src/search/eval-search.mjs`.

## Gates

- `npx tsc --noEmit` clean · `npx expo lint` clean
- node runners: search 12/12 · store 98/98 · nav 100/100 · api 37/37 · offline 16/16
- python syntax-checked (`build_corpus.py`, `fetch_overture.py`); aux gz verified 244,425 rows
- server pytest needs `.venv312`+alive_core ext — absent on this box; corpus scripts exercised via real rebuild + eval.

## Files

- `scripts/fetch_overture.py` (new), `scripts/build_corpus.py` (`--remerge-aux`, gz aux, per-row `k`)
- `server/data/corpus/aux/overture-places.jsonl.gz` (new), corpus + STATS + sample + docs/plan/corpus-report.md regenerated
- `Mobile/assets/delhi-gazetteer.json` + `Mobile/assets/t0-index/*` (210 k rows / 62 chunks)
- `Mobile/src/search/client.ts` (immediate t1/t2 + weak-gated Photon→Nominatim t3)
- `Mobile/src/search/t0.ts` (`isBrowseAnchor`, `nearbyPOIs`)
- `Mobile/src/screens/SearchScreen.tsx` (`localCount` + shops-here section), `src/i18n/strings.ts` (en+hi)
- `Mobile/src/search/eval-search.mjs` (new dev harness)
