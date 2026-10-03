# Delhi-NCR corpus -- STATS

- built: 2026-10-03 02:21:49 UTC
- source: `cached:northern-zone-latest.osm.pbf`
- script: `scripts/build_corpus.py` (pyosmium)
- extraction bbox: lon 76.6-77.7, lat 28.0-29.0
- strict NCR bbox (flag-only): lon 76.75-77.95, lat 28.15-28.98
- nodes scanned: 33,447,761  |  ways scanned: 3,089,230
- **entries emitted: 53,298**

## Entries per top-level category

| category | count |
|---|---|
| highway | 14,194 |
| amenity | 11,720 |
| shop | 7,830 |
| addr | 4,071 |
| building | 2,754 |
| public_transport | 2,080 |
| place | 2,011 |
| boundary | 1,690 |
| leisure | 1,646 |
| office | 1,592 |
| railway | 1,543 |
| tourism | 1,277 |
| craft | 335 |
| healthcare | 297 |
| historic | 240 |
| aeroway | 16 |
| emergency | 2 |

## Flags

- entries outside strict NCR bbox (Noida / Ghaziabad / fringe NCR — kept in corpus): **1,301**
- deduped (same normalized name + ~75 m cell, richest kept): 10,614
- untagged/empty display dropped: 0

## Artifacts

| file | size |
|---|---|
| `delhi-corpus.jsonl.gz` | 1.3 MB |
| `delhi-corpus-sample.jsonl` (first 20,000) | 3.25 MB |


## 20-query acceptance score (tests/search_queries.txt)

Simple Python index: normalized token + prefix match over display+aliases, top-3 must contain expected place.

**Score with alias table: 20/20**  |  without aliases: 17/20

| query | expected | hit | needs alias | top-3 |
|---|---|---|---|---|
| select citywalk | Select Citywalk Mall, Saket | HIT |  | Select Citywalk (shop); Select Hotel (tourism); LeMarche Select (amenity) |
| lajpat nagar 4 | Lajpat Nagar IV | HIT |  | Chocolate Desire (shop); Nagpal chole bature (amenity); Shagun Departmental Store (shop) |
| haldiram chandni | Haldiram's, Chandni Chowk | HIT |  | Haldiram (amenity); Haldiram (amenity); Haldiram (amenity) |
| dlf cyber hub | DLF CyberHub, Gurugram | HIT |  | DLF Cyber Hub (tourism); DLF Cyber City (addr); DLF Cyber City (place) |
| chandni chok | Chandni Chowk | HIT |  | Chandni Chowk (tourism); Chandni Chowk (shop); Chandni Chowk (railway) |
| cp | Connaught Place | HIT |  | Connaught Place (addr); Connaught Place (addr); Connaught Place (addr) |
| gk 2 | Greater Kailash II | HIT | yes | Greater Kailash 2 (addr); Greater Kailash Metro Gate No. 2 (railway); DT Cinema (amenity) |
| sarojni nagar | Sarojini Nagar Market | HIT | yes | Sarojini Nagar (boundary); Sarojini Nagar (railway); Sarojini Nagar (railway) |
| aiims metro | AIIMS Metro Station | HIT |  | AIIMS Metro Gate No. 1 (railway); AIIMS Metro Gate No. 2 (railway); AIIMS Metro Gate No. 3 (railway) |
| kashmere gate | Kashmere Gate / ISBT | HIT |  | Kashmere Gate (railway); Kashmere Gate (public_transport); Kashmere Gate (place) |
| india gate | India Gate | HIT |  | India Gate (tourism); India Gate Fountain (amenity); India Gate Park (leisure) |
| noida sec 18 | Noida Sector 18 | HIT |  | Noida Sector 18 (railway); Noida Sector 15 (railway); Noida Sector 16 (railway) |
| hauz khas | Hauz Khas Village | HIT |  | Hauz Khas (addr); Hauz Khas (public_transport); Hauz Khas (public_transport) |
| karol bag | Karol Bagh | HIT |  | Karol Bagh (place); Karol Bagh (public_transport); Karol Bagh (railway) |
| dtu | Delhi Technological University (DTU), Bawana Road | HIT |  | Delhi Technological University (amenity); Delhi Technological University (amenity); DCE Parking (amenity) |
| rajiv chowk gate 5 | Rajiv Chowk Metro Gate 5 | HIT |  | Rajiv Chowk Metro Gate No 5 (railway); Rajiv Chowk Metro Gate No 1 (railway); Rajiv Chowk Metro Gate No 2 (railway) |
| saket pvr | PVR / Select Citywalk area, Saket | HIT |  | PVR Saket (amenity); Delhi Government Dispensary, PVR Complex Saket (amenity); PVR Cinemas (amenity) |
| connaught plce | Connaught Place | HIT | yes | Connaught Place (addr); Connaught Place (addr); Connaught Place (addr) |
| nehru place | Nehru Place | HIT |  | Nehru Place (boundary); Nehru Place (railway); Nehru Place (public_transport) |
| vaishali metro | Vaishali Metro Station | HIT |  | Vaishali (railway); Vaishali Apartments (building); Vaishali Enclave (public_transport) |

- queries that NEED aliases.json to hit: gk 2, sarojni nagar, connaught plce
- misses (corpus/index gaps): none


## Mobile gazetteer emit

- output: `server/data/corpus/delhi-gazetteer-150k.json` (7.2 MB)
- bundled gazetteer kept: 26,545
- new OSM rows added: 51,418 (skipped 1,880 name+75 m dupes)
- **total: 77,963** (target 150,000)
