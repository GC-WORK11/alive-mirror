# Delhi-NCR corpus report

Built: 2026-10-08 14:19 UTC  |  OSM source: `remerge(committed+aux)`  |  script: `scripts/build_corpus.py`

## Sources

| source | rows in | merged into existing | new entries | provenance |
|---|---|---|---|---|
| OSM (remerge(committed+aux)) | 90,498 in extraction box (post-dedupe) | — | base layer | `source:osm`, id n/w/r<osmid> |
| GeoNames IN.zip | 6,245 in box | 0 | 0 | `source:geonames`, id gn:<geonameid> |
| aux/*.jsonl (overture-places.jsonl:244,425r/+240,841, wikidata.jsonl:7,565r/+0) | 251,990 | 11,149 | 240,841 | per-row `source`/`wikidata` |
| synthetic (attested sector/block canonicalization) | 1,042 attested | 304 folded | 738 | `synthetic:true`, coords = mean of attesting features |

**Total entries: 344,923**  (previous build: 345,186)

T0/T1 ceiling check: corpus 344,923 + bundled 132,932 -> gazetteer 210,000 vs ~150k ambition. The gap to 150k is real, not padded -- OSM Delhi named features + GeoNames + Wikidata + attested sector/block canonicals exhaust the legitimate sources; the rest must come from Amazon T2 cache-back or licensed data.

| per-source membership | entries |
|---|---|
| overture | 244,762 |
| osm | 90,729 |
| wikidata | 7,262 |
| geonames | 6,247 |
| synthetic | 1,064 |
| rows flagged synthetic:true | 738 |

## Dedupe

- same normalized name + ~75 m cell, richest row kept, aliases+sources unioned: 10,758 merges

## 88-query score (tests/search_queries.txt)

- **with aliases.json: 87/88** — without: 84/88

## Mobile gazetteer

- bundled kept 132,932 + new 77,068 = **210,000** (19.9 MB, dedupe-skipped 124,166)

## Reproduce

```sh
tools/corpus-venv/bin/python scripts/fetch_wikidata.py
tools/corpus-venv/bin/python scripts/build_corpus.py --emit-mobile
tools/corpus-venv/bin/python scripts/build_mobile_gaz.py   # alt emit
```

Note: only real named entities are emitted -- Wikidata/GeoNames/OSM rows or attested sector/block designators (synthetic:true, coords averaged from attesting features). No fabricated names. Where the sources run dry the report above is the real ceiling, not a target hit by padding.
