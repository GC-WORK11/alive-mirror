# Delhi-NCR corpus -- STATS

- built: 2026-10-08 04:31:10 UTC
- source: `local:northern-zone-latest.osm.pbf+central-zone-latest.osm.pbf`
- script: `scripts/build_corpus.py` (pyosmium)
- extraction bbox: lon 76.68-78.02, lat 28.08-29.07
- strict NCR bbox (flag-only): lon 76.75-77.95, lat 28.15-28.98
- nodes scanned: 91,945,922  |  ways scanned: 8,890,300
- **entries emitted: 103,607**

## Entries per source (rows may carry >1 source after dedupe)

| source | entries |
|---|---|
| osm | 90,697 |
| wikidata | 7,254 |
| geonames | 6,246 |
| synthetic | 412 |

## Entries per top-level category

| category | count |
|---|---|
| addr | 22,847 |
| highway | 19,344 |
| amenity | 13,834 |
| shop | 9,047 |
| locality | 4,723 |
| building | 4,355 |
| place | 4,060 |
| landuse | 3,300 |
| hotel | 2,633 |
| railway | 2,289 |
| public_transport | 2,158 |
| leisure | 2,114 |
| office | 1,823 |
| boundary | 1,822 |
| station | 1,456 |
| tourism | 1,361 |
| misc | 844 |
| canal | 533 |
| barrier | 488 |
| healthcare | 466 |
| craft | 370 |
| metro | 266 |
| synthetic | 263 |
| district | 250 |
| power | 244 |
| historic | 233 |
| waterway | 225 |
| natural | 221 |
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
| museum | 29 |
| mall | 28 |
| street | 28 |
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

- entries outside strict NCR bbox (Noida / Ghaziabad / fringe NCR — kept in corpus): **4,229**
- deduped (same normalized name + ~75 m cell, richest kept): 10,066
- untagged/empty display dropped: 0

## Artifacts

| file | size |
|---|---|
| `delhi-corpus.jsonl.gz` | 2.6 MB |
| `delhi-corpus-sample.jsonl` (first 20,000) | 4.81 MB |
- osm entries (base layer): 90,498
- housenumbers (OSM addr:*): 3,859 context-less queued -> 310 street-anchored + 1,323 segment-anchored + 2,101 locality-anchored, 125 unresolved (honest misses)
- addr:interpolation: 1,110 ways -> 7,697 housenumbers emitted (671 named via segment vote, 727 ways skipped)
- geonames: 6,245 in box -> +6,196 new (49 deduped in)
- aux/*.jsonl: 7,565 rows -> +6,650 new (915 deduped in); wikidata.jsonl:7,565r/+6,650
- synthetic: 412 attested -> +263 rows (149 folded)


## 88-query acceptance score (tests/search_queries.txt)

Simple Python index: normalized token + prefix match over display+aliases, top-3 must contain expected place.

**Score with alias table: 88/88**  |  without aliases: 84/88

| query | expected | hit | needs alias | top-3 |
|---|---|---|---|---|
| select citywalk | Select Citywalk Mall, Saket | HIT |  | Select Citywalk (shop); Select Citywalk (mall); Select Citywalk Lawn (landuse) |
| lajpat nagar 4 | Lajpat Nagar IV | HIT |  | Chocolate Desire (shop); Nagpal chole bature (amenity); Shagun Departmental Store (shop) |
| haldiram chandni | Haldiram's, Chandni Chowk | HIT |  | Haldiram (public_transport); Haldiram (amenity); Haldiram (amenity) |
| dlf cyber hub | DLF CyberHub, Gurugram | HIT |  | DLF Cyber Hub (landuse); DLF Cyber Hub (tourism); DLF Cyber City (public_transport) |
| chandni chok | Chandni Chowk | HIT |  | Chandni Chauk (locality); Chandni Chowk (tourism); Chandni Chowk (railway) |
| cp | Connaught Place | HIT | yes | Connaught Place (district); Connaught Place (locality); Connaught Place (place) |
| gk 2 | Greater Kailash II | HIT | yes | Greater Kailash Metro Gate No. 2 (railway); DT Cinema (amenity); Hotel GTC (tourism) |
| sarojni nagar | Sarojini Nagar Market | HIT |  | Sarojini Nagar (railway); Sarojini Nagar (boundary); Sarojini Nagar (railway) |
| aiims metro | AIIMS Metro Station | HIT |  | AIIMS metro station (metro); AIIMS Metro Gate No. 1 (railway); AIIMS Metro Gate No. 2 (railway) |
| kashmere gate | Kashmere Gate / ISBT | HIT |  | Kashmere Gate (public_transport); Kashmere Gate (railway); Kashmere Gate (railway) |
| india gate | India Gate | HIT |  | India Gate (monument); India Gate Fountain (amenity); India Gate Park (leisure) |
| noida sec 18 | Noida Sector 18 | HIT |  | Noida Sector 18 (railway); Noida Sector 18 metro station (metro); Noida Sector-18 Metro Gate Number 1 (railway) |
| hauz khas | Hauz Khas Village | HIT |  | Hauz Khas (district); Hauz Khas (public_transport); Hauz Khas (public_transport) |
| karol bag | Karol Bagh | HIT |  | Karol Bagh (public_transport); Karol Bagh (locality); Karol Bagh (locality) |
| dtu | Delhi Technological University (DTU), Bawana Road | HIT |  | Delhi Technological University (amenity); Delhi Technological University (university); Delhi Technological University (amenity) |
| rajiv chowk gate 5 | Rajiv Chowk Metro Gate 5 | HIT |  | Rajiv Chowk Metro Gate No 5 (railway); Rajiv Chowk Metro Gate No 1 (railway); Rajiv Chowk Metro Gate No 2 (railway) |
| saket pvr | PVR / Select Citywalk area, Saket | HIT |  | PVR Saket (amenity); Delhi Government Dispensary, PVR Complex Saket (amenity); PVR Cinemas (amenity) |
| connaught plce | Connaught Place | HIT |  | Connaught Place (district); Connaught Place (locality); Connaught Place (place) |
| nehru place | Nehru Place | HIT |  | Nehru Place (public_transport); Nehru Place (public_transport); Nehru Place (amenity) |
| vaishali metro | Vaishali Metro Station | HIT |  | Vaishali metro station (metro); Vaishali Metro Station Parking (amenity); Vaishali Metro Station Multi Level Car Parkin (amenity) |
| 559 udyog vihar | 559 Udyog Vihar Phase V Road | HIT |  | 559 Udyog Vihar Phase V Road (addr); 559 Block E, Mayur Vihar Phase 2 (addr); 559 Baba Amarnath Marg (addr) |
| 110 sadbhavana road | 110 Sadbhavana Road | HIT |  | 110 Sadbhavana Road (addr); 110 Mall Road (addr); 1 Sadbhavana Road (addr) |
| 105 ip extension | 105 IP Extension | HIT |  | 105 IP Extension (addr); 105 IP Extension (addr); 1 IP Extension (addr) |
| 458 harshvardhan marg | 458 Harshvardhan Marg | HIT |  | 458 Harshvardhan Marg (addr); 458 Fourth Avenue Road (addr); 458 K Block Jahangirpuri road (addr) |
| 19 church road | 19 Church Road | HIT |  | 19 Church Road (addr); 1 Church Road (addr); 10 Church Road (addr) |
| sector 62 noida | Sector 62, Noida | HIT |  | Sector 62, Noida (place); Sector 62 (place); Adviks Study Abroad (amenity) |
| rohini sector 7 | Rohini Sector 7 | HIT |  | Rohini Sector 7 (synthetic); Rohini Sector 7 and 8 (public_transport); Aryanveda Cosmeceuticals, Rohini (shop) |
| nithari village | Nithari Village | HIT |  | Nithari Village (village); Nithari Village (city); Nithari (place) |
| chhapraula | Chhapraula | HIT |  | Chhapraula (place); Chhapraula (locality); Chhapraula (locality) |
| sorkha village | Sorkha | HIT |  | HDFC Bank Sector 116 (synthetic); HDFC Bank Sector 116 Sorkha branch (place); ATS Village (place) |
| pari chowk | Pari Chowk, Greater Noida | HIT |  | Pari Chowk (public_transport); Pari Chowk (public_transport); Pari Chowk (railway) |
| akshardham temple | Akshardham Temple | HIT |  | Akshardham Temple Boundary (barrier); Akshardham (temple); Swaminarayan's Akshardham Temple (amenity) |
| sarai kale khan | Sarai Kale Khan | HIT |  | Sarai Kale Khan (place); Sarai Kale Khan (public_transport); Sarai Kale Khan (railway) |
| crossings republik | Crossings Republik | HIT |  | Crossings Republik (place); Crossings Republik (place); Crossings Republik Road (highway) |
| indirapuram | Indirapuram | HIT |  | Indirapuram (misc); Indirapuram (locality); Indirapuram (locality) |
| beta 2 greater noida | Beta 2, Greater Noida | HIT |  | Beta 2 (landuse); AVJ Heights (landuse); Beta 1 (landuse) |
| purana qila | Purana Qila | HIT |  | Purana Qila (monument); Purana Qila (monument); Purana Qila (tourism) |
| sarita vihar | Sarita Vihar | HIT |  | Sarita Vihar (railway); Sarita Vihar (place); Sarita Vihar (public_transport) |
| chirag delhi | Chirag Delhi | HIT |  | Chirag Delhi (railway); Chirag Delhi (railway); Chirag Delhi (locality) |
| dilshad garden | Dilshad Garden | HIT |  | Dilshad Garden (park); Dilshad Garden (locality); Dilshad Garden (railway) |
| mandawali | Mandawali | HIT |  | Mandawali (addr); Mandawali Fazalpur (place); Mandawali Chander Vihar (station) |
| new friends colony | New Friends Colony | HIT |  | New Friends Colony (place); New Friends Colony (boundary); New Friends Colony (public_transport) |
| seelam pur | Seelampur | HIT |  | Seelam Pur (district); Seelampur (locality); Seelampur (railway) |
| hkv | Hauz Khas Village | HIT | yes | Hauz Khas Village (landuse); Hauz Khas village (mall); Hauz Khas Village Road (highway) |
| ndls | New Delhi Railway Station | HIT |  | New Delhi Railway Station (boundary); New Delhi Railway Station (public_transport); New Delhi railway station (station) |
| bhikaji | Bhikaji Cama Place | HIT |  | Bhikaji Cama Place (boundary); Bhikaji Cama Place (locality); Bhikaji Cama Place (public_transport) |
| srcc | Shri Ram College of Commerce | HIT |  | Shri Ram College of Commerce (amenity); Shri Ram College of Commerce (college); Gurdwara (amenity) |
| konnaught place | Connaught Place | HIT |  | Connaught Place (district); Connaught Place (locality); Connaught Place (place) |
| chandi chowk | Chandni Chowk | HIT |  | Chandila Chowk (misc); Chandila Chowk (misc); Chandni Chauk (locality) |
| lodhi gardan | Lodhi Garden | HIT |  | Lodhi Garden (public_transport); Tomb of Sikandar Lodhi (historic); Tomb of Muhammad Shah Sayyid (historic) |
| hauz khas vilage | Hauz Khas | HIT |  | Hauz Khas Village (landuse); Hauz Khas village (mall); Hauz Khas Village Road (highway) |
| jamia nagr | Jamia Nagar | HIT |  | Jamia Nagar (place); Jamia Millia Islamia (amenity); Dawat Urdu Sehroza (amenity) |
| nebru place | Nehru Place | HIT |  | Nehru Place (public_transport); Nehru Place (public_transport); Nehru Place (boundary) |
| atm near cp | ATM | HIT |  | Yes Bank & ATM (amenity); Urban Banquet Hall (amenity); De Bakery Junction The Cake Shop (building) |
| hospital near saket | hospital / Saket | HIT |  | DR MUKESH GARG (amenity); Max Superspeciality Hospital (amenity); Saroj Hospital (amenity) |
| school sector 62 noida | school / Sector 62 | HIT |  | Noida Sector 62 (power); Noida Sector 62 (public_transport); Noida Sector 62 (public_transport) |
| petrol pump near karol bagh | petrol / fuel | HIT |  | Indian Oil Fuel Filling Station Service Road (Gupta Service Station-Moti Bagh) (station); Bharat Petroleum Fuel Filling Station Baghpat (Gupta Service Station) (station); Bharat Petroleum Fuel Filling Station Baghpat (Meetli Fuel Point) (station) |
| bank near lajpat nagar | bank | HIT |  | Punjab National Bank (amenity); HDFC Bank New Delhi Lajpat Nagar branch (place); Apni Vidhansabha (office) |
| gym in dwarka | gym / fitness | HIT |  | Aap ka Bazar (shop); The indian gym (misc); Gym Khana Swimming Pool(AIIMS) (leisure) |
| post office in rohini | post office | HIT |  | Post Office Sector 16 (synthetic); Post Office Sec-16 Rohini (amenity); Pushpa Bhawan Post Office (amenity) |
| bus stop near iit delhi | platform / bus stop | HIT |  | IIT Gate Bus Stop Public Transport (public_transport); Rajdhani Chatkare Foods, IIT Delhi (amenity); Assistech Lab (misc) |
| sector 47 noida | Sector 47 | HIT |  | Jagran Public School (building); ArtShala Center For Design (misc); C-35 Sector 47 (addr) |
| sector 12 noida | Sector 12 | HIT |  | Sector 12 (landuse); Delhi Metropolitan Education (office); Megamax Services (building) |
| sector 21 faridabad | Sector 21 | HIT |  | A-21 Dayal Bagh Colony, Sector 39 (addr); HDFC Bank Faridabad Sec 21 Haryana branch (place); Sector 21A (landuse) |
| sector 56 gurgaon | Sector 56 | HIT |  | Alpine Convent School (building); HEWO-2 Apartments (landuse); HUDA Community Centre (building) |
| alpha 1 greater noida | Alpha 1 | HIT |  | Alpha 1 (landuse); S L Tower (building); Shree Krishan Estates Greater Noida & Yamuna Expressway (office) |
| dlf phase 2 | DLF Phase 2 | HIT |  | DLF Phase 2 (synthetic); DLF Phase 2 (railway); DLF Phase 1 (place) |
| pocket b sarita vihar | Sarita Vihar | HIT |  | Pocket C Sarita Vihar Park (leisure); Diabetes & Hormone Clinic (amenity); Sarita Vihar Pocket A (landuse) |
| h block sector 62 noida | Sector 62 / H Block | HIT |  | JSS Boys Hostel (building); JSS Girls Hostel (tourism); Multipurpose Hall (building) |
| a 43 defence colony | Defence Colony | HIT |  | 43 Block C, Defence Colony (addr); 43 Block D, Defence Colony (addr); A-43 Dayal Bagh Colony (addr) |
| e block model town | Model Town | HIT |  | Dashi (amenity); Model Town Phase 2 (synthetic); MAAC Chaudhary Mod Ghaziabad (building) |
| c 56 lajpat nagar | Lajpat Nagar | HIT |  | Lajpat Rai Market, Chandni Chowk, Delhi (addr); Chocolate Desire (shop); Angel's Basket (shop) |
| b 7 vasundhara enclave | Vasundhara Enclave | HIT |  | Yes Bank (amenity); Abhinav Apartment (landuse); Anupam Apartments (landuse) |
| h no 1234 sector 15 noida | Sector 15 | HIT |  | Shilsha Technologies (office); Tisha Services Pvt. Ltd. (building); Noida Sector 123 (power) |
| gamma 2 greater noida | Gamma 2 | HIT |  | Gamma 2 (landuse); Gamma 1 (landuse); Peoples Dental clinic (amenity) |
| badarpur bus depot | Badarpur | HIT | yes | Organic Harvest, wazir pur (shop); Badar Pur (locality); Badar Pur Majra Burari (locality) |
| e 47 greater kailash | Greater Kailash / D Block | HIT |  | Nature's Tattva (shop); E-110 Greater Kailash 2 (addr); E-142 (building) |
| murthal dhaba | Murthal | HIT |  | Collection O 82801 Sudhir Murthal Dhaba (hotel); Murthal (locality); Murthal (place) |
| azadpur mandi | Azadpur | HIT |  | Azadpur Mandi Office (office); Azadpur Fruit and Vegetable Market (boundary); Azadpur (building) |
| sis ganj gurudwara | Sis Ganj | HIT |  | Gurdwara Sis Ganj Sahib (place); Gurdwara Sis Ganj Sahib (amenity); Gurdwara Rakab Ganj (public_transport) |
| t3 airport | Terminal | HIT |  | Delhi Bazaar Craft House (shop); Capital O 68517 Airport T3 (hotel); IGI Airport T3 Road (highway) |
| gaffar market | Gaffar | HIT |  | Gaffar Market (amenity); Gaffar Market (landuse); Rabbani Telecom (shop) |
| khari baoli | Khari Baoli | HIT |  | Khari Baoli (misc); Khari Baoli (market); Khari Baoli Road (highway) |
| iimc | IIMC | HIT |  | IIMC parking (amenity); Indian Institute of Mass Communication(IIMC) (office); Editworks School of Mass Communication, NOIDA (school) |
| house 559 udyog vihar | Udyog Vihar | HIT |  | 559 Udyog Vihar Phase V Road (addr); The Walsons House (building); 559 Block E, Mayur Vihar Phase 2 (addr) |
| b-12 lajpat nagar | Lajpat Nagar / B-12 | HIT |  | Salt Spa (leisure); B-63 Lajpat Nagar 1 (addr); Bina (shop) |
| aiims | AIIMS | HIT |  | AIIMS (public_transport); AIIMS (public_transport); All India Institute of Medical Sciences (public_transport) |
| lodhi garden | Lodi Gardens | HIT |  | Lodhi Garden (public_transport); Tomb of Sikandar Lodhi (historic); Tomb of Muhammad Shah Sayyid (historic) |

- queries that NEED aliases.json to hit: cp, gk 2, hkv, badarpur bus depot
- misses (corpus/index gaps): none


## Mobile gazetteer emit

- output: `server/data/corpus/delhi-gazetteer-150k.json` (12.1 MB)
- bundled gazetteer kept: 124,311
- new corpus rows added: 8,621 (skipped 94,986 name+75 m dupes)
- **total: 132,932** (target 150,000)
