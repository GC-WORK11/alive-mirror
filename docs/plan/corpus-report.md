# Delhi-NCR corpus report

Built: 2026-10-08 04:31 UTC  |  OSM source: `local:northern-zone-latest.osm.pbf+central-zone-latest.osm.pbf`  |  script: `scripts/build_corpus.py`

## Sources

| source | rows in | merged into existing | new entries | provenance |
|---|---|---|---|---|
| OSM (local:northern-zone-latest.osm.pbf+central-zone-latest.osm.pbf) | 90,498 in extraction box (post-dedupe) | — | base layer | `source:osm`, id n/w/r<osmid> |
| GeoNames IN.zip | 6,245 in box | 49 | 6,196 | `source:geonames`, id gn:<geonameid> |
| aux/*.jsonl (wikidata.jsonl:7,565r/+6,650) | 7,565 | 915 | 6,650 | per-row `source`/`wikidata` |
| synthetic (attested sector/block canonicalization) | 412 attested | 149 folded | 263 | `synthetic:true`, coords = mean of attesting features |

**Total entries: 103,607**  (previous build: 97,447)

T0/T1 ceiling check: corpus 103,607 + bundled 124,311 -> gazetteer 132,932 vs ~150k ambition. The gap to 150k is real, not padded -- OSM Delhi named features + GeoNames + Wikidata + attested sector/block canonicals exhaust the legitimate sources; the rest must come from Amazon T2 cache-back or licensed data.

| per-source membership | entries |
|---|---|
| osm | 90,697 |
| wikidata | 7,254 |
| geonames | 6,246 |
| synthetic | 412 |
| rows flagged synthetic:true | 263 |

## Dedupe

- same normalized name + ~75 m cell, richest row kept, aliases+sources unioned: 10,066 merges

## 88-query score (tests/search_queries.txt)

- **with aliases.json: 88/88** — without: 84/88

## Mobile gazetteer

- bundled kept 124,311 + new 8,621 = **132,932** (12.1 MB, dedupe-skipped 94,986)

## Reproduce

```sh
tools/corpus-venv/bin/python scripts/fetch_wikidata.py
tools/corpus-venv/bin/python scripts/build_corpus.py --emit-mobile
tools/corpus-venv/bin/python scripts/build_mobile_gaz.py   # alt emit
```

Note: only real named entities are emitted -- Wikidata/GeoNames/OSM rows or attested sector/block designators (synthetic:true, coords averaged from attesting features). No fabricated names. Where the sources run dry the report above is the real ceiling, not a target hit by padding.
