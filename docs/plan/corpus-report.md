# Delhi-NCR corpus report

Built: 2026-10-04 03:50 UTC  |  OSM source: `cached:northern-zone-latest.osm.pbf; cached:central-zone-latest.osm.pbf`  |  script: `scripts/build_corpus.py`

## Sources

| source | rows in | merged into existing | new entries | provenance |
|---|---|---|---|---|
| OSM (cached:northern-zone-latest.osm.pbf; cached:central-zone-latest.osm.pbf) | 84,370 in extraction box (post-dedupe) | — | base layer | `source:osm`, id n/w/r<osmid> |
| GeoNames IN.zip | 6,245 in box | 50 | 6,195 | `source:geonames`, id gn:<geonameid> |
| aux/*.jsonl (wikidata.jsonl:7,565r/+6,650) | 7,565 | 915 | 6,650 | per-row `source`/`wikidata` |
| synthetic (attested sector/block canonicalization) | 384 attested | 149 folded | 235 | `synthetic:true`, coords = mean of attesting features |

**Total entries: 97,450**  (previous build: 72,456)

T0/T1 ceiling check: corpus 97,450 + bundled 96,820 -> gazetteer 123,957 vs ~150k ambition. The gap to 150k is real, not padded -- OSM Delhi named features + GeoNames + Wikidata + attested sector/block canonicals exhaust the legitimate sources; the rest must come from Amazon T2 cache-back or licensed data.

| per-source membership | entries |
|---|---|
| osm | 84,541 |
| wikidata | 7,254 |
| geonames | 6,246 |
| synthetic | 384 |
| rows flagged synthetic:true | 235 |

## Dedupe

- same normalized name + ~75 m cell, richest row kept, aliases+sources unioned: 15,251 merges

## Address depth (addr:* — 16,952 rows)

| kind | rows | provenance |
|---|---|---|
| addr:address | 8,635 | `addr:housenumber + street/place/block/subdistrict` tags; 3,732 of them are context-less housenumbers anchored by proximity (1,616 to a named street ≤90 m, 2,116 to a locality ≤450 m); 92 context-less numbers stayed honest misses |
| addr:interpolation | 7,098 | generated housenumber rows along 1,110 `addr:interpolation` ways — numbers sit at the linear-fraction position the OSM model defines; 745 ways skipped (no numeric endpoints / no street resolvable) |
| addr:place / addr:subdistrict | 1,219 | named address-localities carried as-is |

## 36-query score (tests/search_queries.txt)

- **with aliases.json: 36/36** — without: 32/36

## Mobile gazetteer

- bundled kept 96,820 + new 27,137 = **123,957** (11.3 MB, dedupe-skipped 70,313)

## Reproduce

```sh
tools/corpus-venv/bin/python scripts/fetch_wikidata.py
tools/corpus-venv/bin/python scripts/build_corpus.py --emit-mobile
tools/corpus-venv/bin/python scripts/build_mobile_gaz.py   # alt emit
```

Note: only real named entities are emitted -- Wikidata/GeoNames/OSM rows or attested sector/block designators (synthetic:true, coords averaged from attesting features). No fabricated names. Where the sources run dry the report above is the real ceiling, not a target hit by padding.
