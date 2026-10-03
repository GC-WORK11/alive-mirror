# Delhi-NCR corpus report

Built: 2026-10-03 04:04 UTC  |  OSM source: `cached:northern-zone-latest.osm.pbf`  |  script: `scripts/build_corpus.py`

## Sources

| source | rows in | merged into existing | new entries | provenance |
|---|---|---|---|---|
| OSM (Geofabrik northern-zone PBF) | 60,309 in extraction box (post-dedupe) | — | base layer | `source:osm`, id n/w/r<osmid> |
| GeoNames IN.zip | 4,981 in box | 42 | 4,939 | `source:geonames`, id gn:<geonameid> |
| aux/*.jsonl (wikidata.jsonl:7,565r/+7,003) | 7,565 | 562 | 7,003 | per-row `source`/`wikidata` |
| synthetic (attested sector/block canonicalization) | 310 attested | 105 folded | 205 | `synthetic:true`, coords = mean of attesting features |

**Total entries: 72,456**  (previous build: 53,298)

T0/T1 ceiling check: corpus 72,456 + bundled 26,545 -> gazetteer 96,820 vs ~150k ambition. The gap to 150k is real, not padded -- OSM Delhi named features + GeoNames + Wikidata + attested sector/block canonicals exhaust the legitimate sources; the rest must come from Amazon T2 cache-back or licensed data.

| per-source membership | entries |
|---|---|
| osm | 60,431 |
| wikidata | 7,645 |
| geonames | 4,982 |
| synthetic | 310 |
| rows flagged synthetic:true | 205 |

## Dedupe

- same normalized name + ~75 m cell, richest row kept, aliases+sources unioned: 11,784 merges

## 20-query score (tests/search_queries.txt)

- **with aliases.json: 20/20** — without: 17/20

## Mobile gazetteer

- bundled kept 26,545 + new 70,275 = **96,820** (8.9 MB, dedupe-skipped 2,181)

## Reproduce

```sh
tools/corpus-venv/bin/python scripts/fetch_wikidata.py
tools/corpus-venv/bin/python scripts/build_corpus.py --emit-mobile
tools/corpus-venv/bin/python scripts/build_mobile_gaz.py   # alt emit
```

Note: only real named entities are emitted -- Wikidata/GeoNames/OSM rows or attested sector/block designators (synthetic:true, coords averaged from attesting features). No fabricated names. Where the sources run dry the report above is the real ceiling, not a target hit by padding.
