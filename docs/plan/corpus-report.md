# Delhi-NCR corpus report

Built: 2026-10-04 04:40 UTC  |  OSM source: `cached:northern-zone-latest.osm.pbf; cached:central-zone-latest.osm.pbf`  |  script: `scripts/build_corpus.py`

## Sources

| source | rows in | merged into existing | new entries | provenance |
|---|---|---|---|---|
| OSM (cached:northern-zone-latest.osm.pbf; cached:central-zone-latest.osm.pbf) | 84,367 in extraction box (post-dedupe) | — | base layer | `source:osm`, id n/w/r<osmid> |
| GeoNames IN.zip | 6,245 in box | 50 | 6,195 | `source:geonames`, id gn:<geonameid> |
| aux/*.jsonl (wikidata.jsonl:7,565r/+6,650) | 7,565 | 915 | 6,650 | per-row `source`/`wikidata` |
| synthetic (attested sector/block canonicalization) | 384 attested | 149 folded | 235 | `synthetic:true`, coords = mean of attesting features |

**Total entries: 97,447**  (previous build: 97,447)

T0/T1 ceiling check: corpus 97,447 + bundled 123,957 -> gazetteer 124,334 vs ~150k ambition. The gap to 150k is real, not padded -- OSM Delhi named features + GeoNames + Wikidata + attested sector/block canonicals exhaust the legitimate sources; the rest must come from Amazon T2 cache-back or licensed data.

| per-source membership | entries |
|---|---|
| osm | 84,538 |
| wikidata | 7,254 |
| geonames | 6,246 |
| synthetic | 384 |
| rows flagged synthetic:true | 235 |

## Dedupe

- same normalized name + ~75 m cell, richest row kept, aliases+sources unioned: 15,254 merges

## 47-query score (tests/search_queries.txt)

- **with aliases.json: 47/47** — without: 42/47

## Mobile gazetteer

- bundled kept 123,957 + new 377 = **124,334** (11.3 MB, dedupe-skipped 97,070)

## Reproduce

```sh
tools/corpus-venv/bin/python scripts/fetch_wikidata.py
tools/corpus-venv/bin/python scripts/build_corpus.py --emit-mobile
tools/corpus-venv/bin/python scripts/build_mobile_gaz.py   # alt emit
```

Note: only real named entities are emitted -- Wikidata/GeoNames/OSM rows or attested sector/block designators (synthetic:true, coords averaged from attesting features). No fabricated names. Where the sources run dry the report above is the real ceiling, not a target hit by padding.
