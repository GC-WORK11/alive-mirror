# Delhi-NCR corpus -- STATS

- built: 2026-10-04 04:40:31 UTC
- source: `cached:northern-zone-latest.osm.pbf; cached:central-zone-latest.osm.pbf`
- script: `scripts/build_corpus.py` (pyosmium)
- extraction bbox: lon 76.68-78.02, lat 28.08-29.07
- strict NCR bbox (flag-only): lon 76.75-77.95, lat 28.15-28.98
- nodes scanned: 91,931,396  |  ways scanned: 8,888,227
- **entries emitted: 97,447**

## Entries per source (rows may carry >1 source after dedupe)

| source | entries |
|---|---|
| osm | 84,538 |
| wikidata | 7,254 |
| geonames | 6,246 |
| synthetic | 384 |

## Entries per top-level category

| category | count |
|---|---|
| highway | 19,322 |
| addr | 16,949 |
| amenity | 13,680 |
| shop | 9,044 |
| locality | 4,723 |
| building | 4,350 |
| place | 4,055 |
| landuse | 3,292 |
| hotel | 2,633 |
| railway | 2,284 |
| public_transport | 2,164 |
| leisure | 2,089 |
| office | 1,823 |
| boundary | 1,815 |
| station | 1,456 |
| tourism | 1,358 |
| misc | 843 |
| canal | 533 |
| barrier | 486 |
| healthcare | 466 |
| craft | 370 |
| metro | 266 |
| district | 250 |
| power | 244 |
| synthetic | 235 |
| historic | 233 |
| waterway | 225 |
| natural | 219 |
| school | 209 |
| man_made | 179 |
| village | 174 |
| junction | 158 |
| college | 148 |
| monument | 114 |
| stream | 112 |
| indoor | 108 |
| university | 99 |
| water | 80 |
| geonames | 71 |
| hospital | 62 |
| park | 58 |
| entrance | 49 |
| temple | 39 |
| mosque | 37 |
| club | 35 |
| forest | 31 |
| museum | 30 |
| street | 29 |
| mall | 28 |
| town | 26 |
| aeroway | 22 |
| city | 22 |
| institute | 20 |
| tehsil | 11 |
| church | 10 |
| airport | 9 |
| bridge | 8 |
| cemetery | 8 |
| market | 8 |
| stadium | 8 |
| cinema | 7 |
| lake | 7 |
| bus_station | 4 |
| emergency | 4 |
| library | 4 |
| prison | 3 |
| military | 2 |
| restaurant | 2 |
| shrine | 2 |
| zoo | 2 |
| embassy | 1 |

## Flags

- entries outside strict NCR bbox (Noida / Ghaziabad / fringe NCR — kept in corpus): **4,211**
- deduped (same normalized name + ~75 m cell, richest kept): 15,254
- untagged/empty display dropped: 0

## Artifacts

| file | size |
|---|---|
| `delhi-corpus.jsonl.gz` | 2.4 MB |
| `delhi-corpus-sample.jsonl` (first 20,000) | 4.62 MB |
- osm entries (base layer): 84,367
- housenumbers (OSM addr:*): 3,824 context-less queued -> 302 street-anchored + 1,317 segment-anchored + 2,113 locality-anchored, 92 unresolved (honest misses)
- addr:interpolation: 1,110 ways -> 7,016 housenumbers emitted (654 named via segment vote, 745 ways skipped)
- geonames: 6,245 in box -> +6,195 new (50 deduped in)
- aux/*.jsonl: 7,565 rows -> +6,650 new (915 deduped in); wikidata.jsonl:7,565r/+6,650
- synthetic: 384 attested -> +235 rows (149 folded)


## 47-query acceptance score (tests/search_queries.txt)

Simple Python index: normalized token + prefix match over display+aliases, top-3 must contain expected place.

**Score with alias table: 47/47**  |  without aliases: 42/47

| query | expected | hit | needs alias | top-3 |
|---|---|---|---|---|
| select citywalk | Select Citywalk Mall, Saket | HIT |  | Select Citywalk (mall); Select Citywalk (shop); Select Citywalk Lawn (landuse) |
| lajpat nagar 4 | Lajpat Nagar IV | HIT |  | Chocolate Desire (shop); Nagpal chole bature (amenity); Shagun Departmental Store (shop) |
| haldiram chandni | Haldiram's, Chandni Chowk | HIT |  | Haldiram (amenity); Haldiram (amenity); Haldiram (public_transport) |
| dlf cyber hub | DLF CyberHub, Gurugram | HIT |  | DLF Cyber Hub (tourism); DLF Cyber Hub (landuse); DLF Cyber City (public_transport) |
| chandni chok | Chandni Chowk | HIT |  | Chandni Chauk (locality); Chandni Chowk (tourism); Chandni Chowk (highway) |
| cp | Connaught Place | HIT | yes | Connaught Place (district); Connaught Place (locality); Connaught Place (place) |
| gk 2 | Greater Kailash II | HIT | yes | Greater Kailash 2 (addr); Greater Kailash Metro Gate No. 2 (railway); 2 Greater Kailash (addr) |
| sarojni nagar | Sarojini Nagar Market | HIT | yes | Sarojini Nagar (railway); Sarojini Nagar (place); Sarojini Nagar (locality) |
| aiims metro | AIIMS Metro Station | HIT |  | AIIMS metro station (metro); AIIMS Metro Gate No. 1 (railway); AIIMS Metro Gate No. 2 (railway) |
| kashmere gate | Kashmere Gate / ISBT | HIT |  | Kashmere Gate (place); Kashmere Gate (public_transport); Kashmere Gate (railway) |
| india gate | India Gate | HIT |  | India Gate (monument); India Gate Fountain (amenity); India Gate Park (leisure) |
| noida sec 18 | Noida Sector 18 | HIT |  | Noida Sector 18 (railway); Noida Sector 18 metro station (metro); Noida Sector-18 Metro Gate Number 1 (railway) |
| hauz khas | Hauz Khas Village | HIT |  | Hauz Khas (public_transport); Hauz Khas (public_transport); Hauz Khas (public_transport) |
| karol bag | Karol Bagh | HIT |  | Karol Bagh (public_transport); Karol Bagh (locality); Karol Bagh (locality) |
| dtu | Delhi Technological University (DTU), Bawana Road | HIT |  | Delhi Technological University (amenity); Delhi Technological University (amenity); Delhi Technological University (university) |
| rajiv chowk gate 5 | Rajiv Chowk Metro Gate 5 | HIT |  | Rajiv Chowk Metro Gate No 5 (railway); Rajiv Chowk Metro Gate No 1 (railway); Rajiv Chowk Metro Gate No 2 (railway) |
| saket pvr | PVR / Select Citywalk area, Saket | HIT |  | PVR Saket (amenity); Delhi Government Dispensary, PVR Complex Saket (amenity); PVR Cinemas (amenity) |
| connaught plce | Connaught Place | HIT | yes | Connaught Place (district); Connaught Place (locality); Connaught Place (place) |
| nehru place | Nehru Place | HIT |  | Nehru Place (public_transport); Nehru Place (public_transport); Nehru Place (addr) |
| vaishali metro | Vaishali Metro Station | HIT |  | Vaishali metro station (metro); Vaishali Metro Station Parking (amenity); Vaishali Metro Station Multi Level Car Parkin (amenity) |
| 559 udyog vihar | 559 Udyog Vihar Phase V Road | HIT |  | 559 Udyog Vihar Phase V Road (addr); 559 Baba Amarnath Marg (addr); 559 Fourth Avenue Road (addr) |
| 110 sadbhavana road | 110 Sadbhavana Road | HIT |  | 110 Sadbhavana Road (addr); 1 Sadbhavana Road (addr); 10 Sadbhavana Road (addr) |
| 105 ip extension | 105 IP Extension | HIT |  | 105 IP Extension (addr); 105 IP Extension (addr); 1 IP Extension (addr) |
| 458 harshvardhan marg | 458 Harshvardhan Marg | HIT |  | 458 Harshvardhan Marg (addr); 458 Fourth Avenue Road (addr); 458 K Block Jahangirpuri road (addr) |
| 19 church road | 19 Church Road | HIT |  | 19 Church Road (addr); 1 Church Road (addr); 10 Church Road (addr) |
| sector 62 noida | Sector 62, Noida | HIT |  | Sector 62, Noida (place); Sector 62 (place); Adviks Study Abroad (amenity) |
| rohini sector 7 | Rohini Sector 7 | HIT |  | Rohini Sector 7 (synthetic); Rohini Sector 7 and 8 (public_transport); Aryanveda Cosmeceuticals, Rohini (shop) |
| nithari village | Nithari Village | HIT |  | Nithari Village (city); Nithari Village (village); Nithari (locality) |
| chhapraula | Chhapraula | HIT |  | Chhapraula (locality); Chhapraula (locality); Chhapraula (place) |
| sorkha village | Sorkha | HIT |  | HDFC Bank Sector 116 (synthetic); HDFC Bank Sector 116 Sorkha branch (place); ATS Village (place) |
| pari chowk | Pari Chowk, Greater Noida | HIT |  | Pari Chowk (railway); Pari Chowk (highway); Pari Chowk (highway) |
| akshardham temple | Akshardham Temple | HIT |  | Akshardham Temple Boundary (barrier); Akshardham (temple); Swaminarayan's Akshardham Temple (amenity) |
| sarai kale khan | Sarai Kale Khan | HIT |  | Sarai Kale Khan (place); Sarai Kale Khan (public_transport); Sarai Kale Khan (railway) |
| crossings republik | Crossings Republik | HIT |  | Crossings Republik (place); Crossings Republik (place); Crossings Republik Road (highway) |
| indirapuram | Indirapuram | HIT |  | Indirapuram (misc); Indirapuram (locality); Indirapuram (locality) |
| beta 2 greater noida | Beta 2, Greater Noida | HIT |  | Beta 2 (landuse); Beta 1 (landuse); HDFC Bank Beta Plaza Greater Noida branch (place) |
| purana qila | Purana Qila | HIT |  | Purana Qila (monument); Purana Qila (monument); Purana Qila (tourism) |
| sarita vihar | Sarita Vihar | HIT |  | Sarita Vihar (addr); Sarita Vihar (addr); Sarita Vihar (railway) |
| chirag delhi | Chirag Delhi | HIT |  | Chirag Delhi (railway); Chirag Delhi (railway); Chirag Delhi (railway) |
| dilshad garden | Dilshad Garden | HIT |  | Dilshad Garden (park); Dilshad Garden (locality); Dilshad Garden (railway) |
| mandawali | Mandawali | HIT |  | Mandawali (addr); Mandawali (addr); Mandawali (addr) |
| new friends colony | New Friends Colony | HIT |  | New Friends Colony (place); New Friends Colony (locality); New Friends Colony (locality) |
| seelam pur | Seelampur | HIT |  | Seelam Pur (district); Seelampur (locality); Seelampur (railway) |
| hkv | Hauz Khas Village | HIT | yes | Hauz Khas Village (landuse); Hauz Khas village (mall); Hauz Khas Village Road (highway) |
| ndls | New Delhi Railway Station | HIT |  | New Delhi Railway Station (public_transport); New Delhi Railway Station (boundary); New Delhi railway station (station) |
| bhikaji | Bhikaji Cama Place | HIT |  | Bhikaji Cama Place (public_transport); Bhikaji Cama Place (railway); Bhikaji Cama Place (boundary) |
| srcc | Shri Ram College of Commerce | HIT |  | Shri Ram College of Commerce (amenity); Shri Ram College of Commerce (college); Lady Shri Ram College (amenity) |

- queries that NEED aliases.json to hit: cp, gk 2, sarojni nagar, connaught plce, hkv
- misses (corpus/index gaps): none


## Mobile gazetteer emit

- output: `server/data/corpus/delhi-gazetteer-150k.json` (11.3 MB)
- bundled gazetteer kept: 123,957
- new corpus rows added: 377 (skipped 97,070 name+75 m dupes)
- **total: 124,334** (target 150,000)
## 67-query acceptance score (tests/search_queries.txt)

Simple Python index: normalized token + prefix match over display+aliases, top-3 must contain expected place.

**Score with alias table: 67/67**  |  without aliases: 64/67

| query | expected | hit | needs alias | top-3 |
|---|---|---|---|---|
| select citywalk | Select Citywalk Mall, Saket | HIT |  | Select Citywalk (mall); Select Citywalk (shop); Select Citywalk Lawn (landuse) |
| lajpat nagar 4 | Lajpat Nagar IV | HIT |  | Chocolate Desire (shop); Nagpal chole bature (amenity); Shagun Departmental Store (shop) |
| haldiram chandni | Haldiram's, Chandni Chowk | HIT |  | Haldiram (amenity); Haldiram (amenity); Haldiram (public_transport) |
| dlf cyber hub | DLF CyberHub, Gurugram | HIT |  | DLF Cyber Hub (tourism); DLF Cyber Hub (landuse); DLF Cyber City (public_transport) |
| chandni chok | Chandni Chowk | HIT |  | Chandni Chauk (locality); Chandni Chowk (tourism); Chandni Chowk (highway) |
| cp | Connaught Place | HIT | yes | Connaught Place (district); Connaught Place (locality); Connaught Place (place) |
| gk 2 | Greater Kailash II | HIT | yes | Greater Kailash 2 (addr); Greater Kailash Metro Gate No. 2 (railway); 2 Greater Kailash (addr) |
| sarojni nagar | Sarojini Nagar Market | HIT |  | Sarojini Nagar (railway); Sarojini Nagar (place); Sarojini Nagar (locality) |
| aiims metro | AIIMS Metro Station | HIT |  | AIIMS metro station (metro); AIIMS Metro Gate No. 1 (railway); AIIMS Metro Gate No. 2 (railway) |
| kashmere gate | Kashmere Gate / ISBT | HIT |  | Kashmere Gate (place); Kashmere Gate (public_transport); Kashmere Gate (railway) |
| india gate | India Gate | HIT |  | India Gate (monument); India Gate Fountain (amenity); India Gate Park (leisure) |
| noida sec 18 | Noida Sector 18 | HIT |  | Noida Sector 18 (railway); Noida Sector 18 metro station (metro); Noida Sector-18 Metro Gate Number 1 (railway) |
| hauz khas | Hauz Khas Village | HIT |  | Hauz Khas (public_transport); Hauz Khas (public_transport); Hauz Khas (public_transport) |
| karol bag | Karol Bagh | HIT |  | Karol Bagh (public_transport); Karol Bagh (locality); Karol Bagh (locality) |
| dtu | Delhi Technological University (DTU), Bawana Road | HIT |  | Delhi Technological University (amenity); Delhi Technological University (amenity); Delhi Technological University (university) |
| rajiv chowk gate 5 | Rajiv Chowk Metro Gate 5 | HIT |  | Rajiv Chowk Metro Gate No 5 (railway); Rajiv Chowk Metro Gate No 1 (railway); Rajiv Chowk Metro Gate No 2 (railway) |
| saket pvr | PVR / Select Citywalk area, Saket | HIT |  | PVR Saket (amenity); Delhi Government Dispensary, PVR Complex Saket (amenity); PVR Cinemas (amenity) |
| connaught plce | Connaught Place | HIT |  | Connaught Place (district); Connaught Place (locality); Connaught Place (place) |
| nehru place | Nehru Place | HIT |  | Nehru Place (public_transport); Nehru Place (public_transport); Nehru Place (addr) |
| vaishali metro | Vaishali Metro Station | HIT |  | Vaishali metro station (metro); Vaishali Metro Station Parking (amenity); Vaishali Metro Station Multi Level Car Parkin (amenity) |
| 559 udyog vihar | 559 Udyog Vihar Phase V Road | HIT |  | 559 Udyog Vihar Phase V Road (addr); 559 Baba Amarnath Marg (addr); 559 Fourth Avenue Road (addr) |
| 110 sadbhavana road | 110 Sadbhavana Road | HIT |  | 110 Sadbhavana Road (addr); 1 Sadbhavana Road (addr); 10 Sadbhavana Road (addr) |
| 105 ip extension | 105 IP Extension | HIT |  | 105 IP Extension (addr); 105 IP Extension (addr); 1 IP Extension (addr) |
| 458 harshvardhan marg | 458 Harshvardhan Marg | HIT |  | 458 Harshvardhan Marg (addr); 458 Fourth Avenue Road (addr); 458 K Block Jahangirpuri road (addr) |
| 19 church road | 19 Church Road | HIT |  | 19 Church Road (addr); 1 Church Road (addr); 10 Church Road (addr) |
| sector 62 noida | Sector 62, Noida | HIT |  | Sector 62, Noida (place); Sector 62 (place); Adviks Study Abroad (amenity) |
| rohini sector 7 | Rohini Sector 7 | HIT |  | Rohini Sector 7 (synthetic); Rohini Sector 7 and 8 (public_transport); Aryanveda Cosmeceuticals, Rohini (shop) |
| nithari village | Nithari Village | HIT |  | Nithari Village (city); Nithari Village (village); Nithari (locality) |
| chhapraula | Chhapraula | HIT |  | Chhapraula (locality); Chhapraula (locality); Chhapraula (place) |
| sorkha village | Sorkha | HIT |  | HDFC Bank Sector 116 (synthetic); HDFC Bank Sector 116 Sorkha branch (place); ATS Village (place) |
| pari chowk | Pari Chowk, Greater Noida | HIT |  | Pari Chowk (railway); Pari Chowk (railway); Pari Chowk (highway) |
| akshardham temple | Akshardham Temple | HIT |  | Akshardham Temple Boundary (barrier); Akshardham (temple); Swaminarayan's Akshardham Temple (amenity) |
| sarai kale khan | Sarai Kale Khan | HIT |  | Sarai Kale Khan (place); Sarai Kale Khan (public_transport); Sarai Kale Khan (railway) |
| crossings republik | Crossings Republik | HIT |  | Crossings Republik (place); Crossings Republik (place); Crossings Republik Road (highway) |
| indirapuram | Indirapuram | HIT |  | Indirapuram (power); Indirapuram (misc); Indirapuram (locality) |
| beta 2 greater noida | Beta 2, Greater Noida | HIT |  | Beta 2 (landuse); Beta 1 (landuse); HDFC Bank Beta Plaza Greater Noida branch (place) |
| purana qila | Purana Qila | HIT |  | Purana Qila (monument); Purana Qila (monument); Purana Qila (tourism) |
| sarita vihar | Sarita Vihar | HIT |  | Sarita Vihar (addr); Sarita Vihar (addr); Sarita Vihar (railway) |
| chirag delhi | Chirag Delhi | HIT |  | Chirag Delhi (railway); Chirag Delhi (railway); Chirag Delhi (railway) |
| dilshad garden | Dilshad Garden | HIT |  | Dilshad Garden (park); Dilshad Garden (locality); Dilshad Garden (railway) |
| mandawali | Mandawali | HIT |  | Mandawali (addr); Mandawali (addr); Mandawali (addr) |
| new friends colony | New Friends Colony | HIT |  | New Friends Colony (place); New Friends Colony (locality); New Friends Colony (locality) |
| seelam pur | Seelampur | HIT |  | Seelam Pur (district); Seelampur (locality); Seelampur (railway) |
| hkv | Hauz Khas Village | HIT | yes | Hauz Khas Village (landuse); Hauz Khas village (mall); Hauz Khas Village Road (highway) |
| ndls | New Delhi Railway Station | HIT |  | New Delhi Railway Station (public_transport); New Delhi Railway Station (boundary); New Delhi railway station (station) |
| bhikaji | Bhikaji Cama Place | HIT |  | Bhikaji Cama Place (public_transport); Bhikaji Cama Place (railway); Bhikaji Cama Place (boundary) |
| srcc | Shri Ram College of Commerce | HIT |  | Shri Ram College of Commerce (amenity); Shri Ram College of Commerce (college); Gurdwara (amenity) |
| konnaught place | Connaught Place | HIT |  | Connaught Place (district); Connaught Place (locality); Connaught Place (place) |
| chandi chowk | Chandni Chowk | HIT |  | Chandila Chowk (misc); Chandila Chowk (misc); Chandni Chauk (locality) |
| lodhi gardan | Lodhi Garden | HIT |  | Lodhi Garden (public_transport); Lodhi Colony (boundary); Lodhi Colony (railway) |
| hauz khas vilage | Hauz Khas | HIT |  | Hauz Khas Village (landuse); Hauz Khas village (mall); Hauz Khas Village Road (highway) |
| jamia nagr | Jamia Nagar | HIT |  | Jamia Nagar (place); Jamia Millia Islamia (amenity); Dawat Urdu Sehroza (amenity) |
| nebru place | Nehru Place | HIT |  | Nehru Place (public_transport); Nehru Place (public_transport); Nehru Place (addr) |
| atm near cp | ATM | HIT |  | Yes Bank & ATM (amenity); Urban Banquet Hall (amenity); De Bakery Junction The Cake Shop (building) |
| hospital near saket | hospital / Saket | HIT |  | DR MUKESH GARG (amenity); Max Superspeciality Hospital (amenity); Saroj Hospital (amenity) |
| school sector 62 noida | school / Sector 62 | HIT |  | Noida Sector 62 (public_transport); Noida Sector 62 (public_transport); Noida Sector 62 (public_transport) |
| petrol pump near karol bagh | petrol / fuel | HIT |  | Indian Oil Fuel Filling Station Service Road (Gupta Service Station-Moti Bagh) (station); Bharat Petroleum Fuel Filling Station Baghpat (Gupta Service Station) (station); Bharat Petroleum Fuel Filling Station Baghpat (Meetli Fuel Point) (station) |
| bank near lajpat nagar | bank | HIT |  | Punjab National Bank (amenity); HDFC Bank New Delhi Lajpat Nagar branch (place); Apni Vidhansabha (office) |
| gym in dwarka | gym / fitness | HIT |  | The indian gym (misc); Gym Khana Swimming Pool(AIIMS) (leisure); Gym Khana Maidan (landuse) |
| post office in rohini | post office | HIT |  | Post Office Sector 16 (synthetic); Post Office Sec-16 Rohini (amenity); Pushpa Bhawan Post Office (amenity) |
| bus stop near iit delhi | platform / bus stop | HIT |  | IIT Gate Bus Stop Public Transport (public_transport); Rajdhani Chatkare Foods, IIT Delhi (amenity); Assistech Lab (misc) |
| sector 47 noida | Sector 47 | HIT |  | Jagran Public School (building); ArtShala Center For Design (misc); C-35 Sector 47 (addr) |
| sector 12 noida | Sector 12 | HIT |  | Sector 12 (landuse); E-10 Sector-12 (addr); Greater Noida Sector 12 (synthetic) |
| sector 21 faridabad | Sector 21 | HIT |  | A-21 Dayal Bagh Colony, Sector 39 (addr); HDFC Bank Faridabad Sec 21 Haryana branch (place); Sector 21A (landuse) |
| sector 56 gurgaon | Sector 56 | HIT |  | Alpine Convent School (building); HEWO-2 Apartments (landuse); HUDA Community Centre (building) |
| alpha 1 greater noida | Alpha 1 | HIT |  | Alpha 1 (landuse); S L Tower (building); Shree Krishan Estates Greater Noida & Yamuna Expressway (office) |
| dlf phase 2 | DLF Phase 2 | HIT |  | DLF Phase 2 (synthetic); DLF Phase 2 (railway); DLF Phase 1 (place) |

- queries that NEED aliases.json to hit: cp, gk 2, hkv
- misses (corpus/index gaps): none
