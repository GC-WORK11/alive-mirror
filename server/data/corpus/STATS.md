# Delhi-NCR corpus -- STATS

- built: 2026-10-03 04:03:37 UTC
- source: `cached:northern-zone-latest.osm.pbf`
- script: `scripts/build_corpus.py` (pyosmium)
- extraction bbox: lon 76.6-77.7, lat 28.0-29.0
- strict NCR bbox (flag-only): lon 76.75-77.95, lat 28.15-28.98
- nodes scanned: 33,447,761  |  ways scanned: 3,089,230
- **entries emitted: 72,456**

## Entries per source (rows may carry >1 source after dedupe)

| source | entries |
|---|---|
| osm | 60,431 |
| wikidata | 7,645 |
| geonames | 4,982 |
| synthetic | 310 |

## Entries per top-level category

| category | count |
|---|---|
| highway | 15,278 |
| amenity | 11,710 |
| shop | 7,829 |
| addr | 4,944 |
| locality | 3,688 |
| place | 3,543 |
| building | 3,192 |
| hotel | 2,700 |
| landuse | 2,545 |
| public_transport | 2,070 |
| boundary | 1,665 |
| leisure | 1,643 |
| office | 1,601 |
| station | 1,592 |
| railway | 1,541 |
| tourism | 1,266 |
| misc | 673 |
| barrier | 459 |
| canal | 357 |
| craft | 335 |
| healthcare | 296 |
| metro | 268 |
| district | 257 |
| historic | 229 |
| school | 216 |
| synthetic | 205 |
| village | 202 |
| waterway | 200 |
| power | 180 |
| natural | 174 |
| man_made | 153 |
| college | 149 |
| junction | 132 |
| monument | 117 |
| indoor | 108 |
| university | 104 |
| stream | 93 |
| water | 88 |
| geonames | 71 |
| hospital | 63 |
| park | 57 |
| entrance | 45 |
| temple | 41 |
| mosque | 37 |
| forest | 35 |
| club | 32 |
| museum | 32 |
| mall | 28 |
| street | 28 |
| town | 26 |
| city | 23 |
| institute | 20 |
| aeroway | 16 |
| tehsil | 11 |
| church | 10 |
| airport | 9 |
| bridge | 8 |
| cemetery | 8 |
| lake | 8 |
| market | 8 |
| stadium | 8 |
| cinema | 7 |
| bus_station | 4 |
| library | 4 |
| prison | 3 |
| emergency | 2 |
| military | 2 |
| restaurant | 2 |
| shrine | 2 |
| zoo | 2 |
| block | 1 |
| embassy | 1 |

## Flags

- entries outside strict NCR bbox (Noida / Ghaziabad / fringe NCR — kept in corpus): **3,394**
- deduped (same normalized name + ~75 m cell, richest kept): 11,784
- untagged/empty display dropped: 0

## Artifacts

| file | size |
|---|---|
| `delhi-corpus.jsonl.gz` | 1.9 MB |
| `delhi-corpus-sample.jsonl` (first 20,000) | 4.40 MB |
- osm entries (base layer): 60,309
- geonames: 4,981 in box -> +4,939 new (42 deduped in)
- aux/*.jsonl: 7,565 rows -> +7,003 new (562 deduped in); wikidata.jsonl:7,565r/+7,003
- synthetic: 310 attested -> +205 rows (105 folded)


## 20-query acceptance score (tests/search_queries.txt)

Simple Python index: normalized token + prefix match over display+aliases, top-3 must contain expected place.

**Score with alias table: 20/20**  |  without aliases: 17/20

| query | expected | hit | needs alias | top-3 |
|---|---|---|---|---|
| select citywalk | Select Citywalk Mall, Saket | HIT |  | Select Citywalk (shop); Select Citywalk (mall); Select Citywalk Lawn (landuse) |
| lajpat nagar 4 | Lajpat Nagar IV | HIT |  | Chocolate Desire (shop); Nagpal chole bature (amenity); Shagun Departmental Store (shop) |
| haldiram chandni | Haldiram's, Chandni Chowk | HIT |  | Haldiram (public_transport); Haldiram (amenity); Haldiram (amenity) |
| dlf cyber hub | DLF CyberHub, Gurugram | HIT |  | DLF Cyber Hub (tourism); DLF Cyber Hub (landuse); DLF Cyber City (place) |
| chandni chok | Chandni Chowk | HIT |  | Chandni Chauk (locality); Chandni Chowk (shop); Chandni Chowk (market) |
| cp | Connaught Place | HIT |  | Connaught Place (place); Connaught Place (district); Connaught Place (locality) |
| gk 2 | Greater Kailash II | HIT | yes | Greater Kailash 2 (addr); Greater Kailash Metro Gate No. 2 (railway); DT Cinema (amenity) |
| sarojni nagar | Sarojini Nagar Market | HIT | yes | Sarojini Nagar (place); Sarojini Nagar (railway); Sarojini Nagar (locality) |
| aiims metro | AIIMS Metro Station | HIT |  | AIIMS metro station (metro); AIIMS Metro Gate No. 1 (railway); AIIMS Metro Gate No. 2 (railway) |
| kashmere gate | Kashmere Gate / ISBT | HIT |  | Kashmere Gate (railway); Kashmere Gate (place); Kashmere Gate (public_transport) |
| india gate | India Gate | HIT |  | India Gate (monument); India Gate Fountain (amenity); India Gate Park (leisure) |
| noida sec 18 | Noida Sector 18 | HIT |  | Noida Sector 18 (railway); Noida Sector 18 metro station (metro); HDFC Bank Sector 18 (synthetic) |
| hauz khas | Hauz Khas Village | HIT |  | Hauz Khas (addr); Hauz Khas (public_transport); Hauz Khas (locality) |
| karol bag | Karol Bagh | HIT |  | Karol Bagh (addr); Karol Bagh (public_transport); Karol Bagh (market) |
| dtu | Delhi Technological University (DTU), Bawana Road | HIT |  | Delhi Technological University (university); Delhi Technological University (amenity); Delhi Technological University (amenity) |
| rajiv chowk gate 5 | Rajiv Chowk Metro Gate 5 | HIT |  | Rajiv Chowk Metro Gate No 5 (railway); Rajiv Chowk Metro Gate No 1 (railway); Rajiv Chowk Metro Gate No 2 (railway) |
| saket pvr | PVR / Select Citywalk area, Saket | HIT |  | PVR Saket (amenity); Delhi Government Dispensary, PVR Complex Saket (amenity); PVR Cinemas (amenity) |
| connaught plce | Connaught Place | HIT | yes | Connaught Place (place); Connaught Place (district); Connaught Place (locality) |
| nehru place | Nehru Place | HIT |  | Nehru Place (railway); Nehru Place (addr); Nehru Place (addr) |
| vaishali metro | Vaishali Metro Station | HIT |  | Vaishali metro station (metro); Vaishali (railway); Vaishali Apartments (building) |

- queries that NEED aliases.json to hit: gk 2, sarojni nagar, connaught plce
- misses (corpus/index gaps): none


## Mobile gazetteer emit

- output: `server/data/corpus/delhi-gazetteer-150k.json` (8.9 MB)
- bundled gazetteer kept: 26,545
- new corpus rows added: 70,275 (skipped 2,181 name+75 m dupes)
- **total: 96,820** (target 150,000)
