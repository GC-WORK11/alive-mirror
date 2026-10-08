# Delhi-NCR corpus -- STATS

- built: 2026-10-08 14:18:45 UTC
- source: `remerge(committed+aux)`
- script: `scripts/build_corpus.py` (pyosmium)
- extraction bbox: lon 76.68-78.02, lat 28.08-29.07
- strict NCR bbox (flag-only): lon 76.75-77.95, lat 28.15-28.98
- mode: **remerge-aux** — OSM PBF pass skipped; base = previous committed corpus rows
- **entries emitted: 344,923**

## Entries per source (rows may carry >1 source after dedupe)

| source | entries |
|---|---|
| overture | 244,762 |
| osm | 90,729 |
| wikidata | 7,262 |
| geonames | 6,247 |
| synthetic | 1,064 |

## Entries per top-level category

| category | count |
|---|---|
| overture | 240,927 |
| addr | 22,847 |
| highway | 19,344 |
| amenity | 13,792 |
| shop | 9,027 |
| locality | 4,723 |
| building | 4,351 |
| place | 4,060 |
| landuse | 3,297 |
| hotel | 2,627 |
| railway | 2,289 |
| public_transport | 2,157 |
| leisure | 2,111 |
| boundary | 1,821 |
| office | 1,821 |
| station | 1,456 |
| tourism | 1,360 |
| misc | 844 |
| synthetic | 738 |
| canal | 533 |
| barrier | 488 |
| healthcare | 466 |
| craft | 370 |
| metro | 266 |
| district | 250 |
| power | 244 |
| historic | 233 |
| waterway | 225 |
| natural | 221 |
| school | 207 |
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
| hospital | 61 |
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

- entries outside strict NCR bbox (Noida / Ghaziabad / fringe NCR — kept in corpus): **12,547**
- deduped (same normalized name + ~75 m cell, richest kept): 10,758
- untagged/empty display dropped: 0

## Artifacts

| file | size |
|---|---|
| `delhi-corpus.jsonl.gz` | 16.8 MB |
| `delhi-corpus-sample.jsonl` (first 20,000) | 4.81 MB |
- remerge: base 103,344 committed rows; dropped 0 overture-only + 263 synthetic rows before re-merge
- aux/*.jsonl: 251,990 rows -> +240,841 new (11,149 deduped in); overture-places.jsonl:244,425r/+240,841, wikidata.jsonl:7,565r/+0
- synthetic: 1,042 attested -> +738 rows (304 folded)


## 88-query acceptance score (tests/search_queries.txt)

Simple Python index: normalized token + prefix match over display+aliases, top-3 must contain expected place.

**Score with alias table: 87/88**  |  without aliases: 84/88

| query | expected | hit | needs alias | top-3 |
|---|---|---|---|---|
| select citywalk | Select Citywalk Mall, Saket | HIT |  | Select Citywalk (mall); Select Citywalk (shop); Select Citywalk Lawn (landuse) |
| lajpat nagar 4 | Lajpat Nagar IV | HIT |  | Lajpat Nagar 4 National Park (overture); Chocolate Desire (shop); Nagpal chole bature (amenity) |
| haldiram chandni | Haldiram's, Chandni Chowk | HIT |  | Haldiram's - Omaxe Mall, Chandani Chowk (overture); Haldiram (amenity); Haldiram (amenity) |
| dlf cyber hub | DLF CyberHub, Gurugram | HIT |  | DLF Cyber Hub (landuse); DLF Cyber Hub (tourism); Cyber Hub, DLF Cyber City (overture) |
| chandni chok | Chandni Chowk | HIT |  | Chandni Chauk (locality); Chandni Chowk (overture); Chandni Chowk (tourism) |
| cp | Connaught Place | HIT | yes | Connaught Place (overture); Connaught Place (locality); Connaught Place (district) |
| gk 2 | Greater Kailash II | HIT |  | Greater Kailash 2 (overture); Gk2 Enclave (overture); Greater Kailash-2 Dominos (overture) |
| sarojni nagar | Sarojini Nagar Market | HIT | yes | Sarojini Nagar (place); Sarojini Nagar (boundary); Sarojini Nagar (railway) |
| aiims metro | AIIMS Metro Station | HIT |  | AIIMS Metro Station (overture); AIIMS metro station (metro); AIIMS Metro Gate No. 1 (railway) |
| kashmere gate | Kashmere Gate / ISBT | HIT |  | Kashmere Gate (overture); Kashmere Gate (railway); Kashmere Gate (railway) |
| india gate | India Gate | HIT |  | India Gate (overture); India Gate (overture); India Gate (monument) |
| noida sec 18 | Noida Sector 18 | HIT |  | Noida Sec 18 (overture); Noida Sec-18 (overture); Noida Sector 18 (railway) |
| hauz khas | Hauz Khas Village | HIT |  | Hauz Khas (overture); Hauz Khas (public_transport); Hauz Khas (locality) |
| karol bag | Karol Bagh | HIT |  | KAROL BAGH (overture); Karol Bagh (public_transport); Karol Bagh (public_transport) |
| dtu | Delhi Technological University (DTU), Bawana Road | HIT |  | Delhi Technological University (university); Delhi Technological University (amenity); Delhi Technological University (amenity) |
| rajiv chowk gate 5 | Rajiv Chowk Metro Gate 5 | HIT |  | Rajiv Chowk Metro Gate No 5 (railway); Rajiv Chowk Metro Gate No 1 (railway); Rajiv Chowk Metro Gate No 2 (railway) |
| saket pvr | PVR / Select Citywalk area, Saket | HIT |  | Chaayos - PVR Saket (overture); FabHotel PVR Saket (overture); Dominos, PVR Saket Complex (overture) |
| connaught plce | Connaught Place | HIT |  | Connaught Place (overture); Connaught Place (locality); Connaught Place (district) |
| nehru place | Nehru Place | HIT |  | Nehru Place (public_transport); Nehru Place (public_transport); Nehru Place (public_transport) |
| vaishali metro | Vaishali Metro Station | HIT |  | Vaishali metro station (metro); Vaishali metro station (overture); Vaishali Metro Station Ghaziabad (overture) |
| 559 udyog vihar | 559 Udyog Vihar Phase V Road | HIT |  | 559 Udyog Vihar Phase V Road (addr); 559 Block E, Mayur Vihar Phase 2 (addr); 559 Baba Amarnath Marg (addr) |
| 110 sadbhavana road | 110 Sadbhavana Road | HIT |  | 110 Sadbhavana Road (addr); 110 Mall Road (addr); 1 Sadbhavana Road (addr) |
| 105 ip extension | 105 IP Extension | HIT |  | 105 IP Extension (addr); 105 IP Extension (addr); 1 IP Extension (addr) |
| 458 harshvardhan marg | 458 Harshvardhan Marg | HIT |  | 458 Harshvardhan Marg (addr); 458 Fourth Avenue Road (addr); 458 K Block Jahangirpuri road (addr) |
| 19 church road | 19 Church Road | HIT |  | 19 Church Road (addr); 19 Akashneem Marg (addr); 19 Gurdwara Road (addr) |
| sector 62 noida | Sector 62, Noida | HIT |  | Sector 62 Noida (overture); Sector 62, Noida (place); Sector 62 (place) |
| rohini sector 7 | Rohini Sector 7 | HIT |  | Rohini Sector 7 (synthetic); Rohini sector 7 (overture); Rohini Sector 7 and 8 (public_transport) |
| nithari village | Nithari Village | HIT |  | Nithari Village (village); Nithari Village (city); Setu School, Shiv Mandir Gali Village Nithari Noida (overture) |
| chhapraula | Chhapraula | HIT |  | Chhapraula (place); Chhapraula (locality); Chhapraula (locality) |
| sorkha village | Sorkha | HIT |  | Sorkha (overture); HDFC Bank Sector 116 (synthetic); HDFC Bank Sector 116 Sorkha branch (place) |
| pari chowk | Pari Chowk, Greater Noida | HIT |  | PARI CHOWK (overture); Pari Chowk (public_transport); Pari Chowk (public_transport) |
| akshardham temple | Akshardham Temple | HIT |  | Akshardham Temple (overture); Akshardham Temple (overture); Akshardham Temple Boundary (barrier) |
| sarai kale khan | Sarai Kale Khan | HIT |  | Sarai Kale Khan (place); Sarai Kale Khan (railway); Sarai Kale Khan (public_transport) |
| crossings republik | Crossings Republik | HIT |  | Crossings Republik (place); Crossings Republik (overture); Crossings Republik (place) |
| indirapuram | Indirapuram | HIT |  | Indirapuram (overture); Indirapuram (overture); Indirapuram (locality) |
| beta 2 greater noida | Beta 2, Greater Noida | HIT |  | Beta 2 (landuse); Sector Beta 2, Greater Noida, Up (overture); Harshi PG & Hostel for Girls in Greater Noida, Beta-2nd (overture) |
| purana qila | Purana Qila | HIT |  | Purana Qila (monument); Purana Qila (monument); Purana Qila (tourism) |
| sarita vihar | Sarita Vihar | HIT |  | Sarita Vihar (railway); Sarita Vihar (place); Sarita Vihar (overture) |
| chirag delhi | Chirag Delhi | HIT |  | Chirag Delhi (public_transport); Chirag Delhi (railway); Chirag Delhi (railway) |
| dilshad garden | Dilshad Garden | HIT |  | Dilshad Garden (railway); Dilshad Garden (overture); Dilshad Garden (overture) |
| mandawali | Mandawali | HIT |  | Mandawali (addr); Mandawli (overture); Mandawali Fazalpur (place) |
| new friends colony | New Friends Colony | HIT |  | New Friends Colony (public_transport); New Friends Colony (public_transport); New Friends Colony (boundary) |
| seelam pur | Seelampur | HIT |  | Seelam Pur (district); Seelampur (railway); Seelampur (public_transport) |
| hkv | Hauz Khas Village | HIT |  | Hauz Khas Village (overture); Hauz Khas Village (overture); Hauz Khas Village (landuse) |
| ndls | New Delhi Railway Station | HIT |  | @ New Delhi Railway Station... (overture); New Delhi Railway Station (public_transport); New Delhi Railway Station (boundary) |
| bhikaji | Bhikaji Cama Place | HIT |  | Bhikaji Cama Place (public_transport); Bhikaji Cama Place (railway); Bhikaji Cama Place (locality) |
| srcc | Shri Ram College of Commerce | HIT |  | SRCC (overture); SRCC (overture); Shri Ram College of Commerce (overture) |
| konnaught place | Connaught Place | HIT |  | Connaught Place (overture); Connaught Place (district); Connaught Place (locality) |
| chandi chowk | Chandni Chowk | MISS |  | Chandila Chowk (misc); Chandila Chowk (misc); Chandini Chowk (overture) |
| lodhi gardan | Lodhi Garden | HIT |  | Lodhi Garden (public_transport); Lodhi Garden (overture); Lodhi Garden Gate (overture) |
| hauz khas vilage | Hauz Khas | HIT |  | Hauz Khas Village (overture); Hauz Khas Village (overture); Hauz Khas Village (landuse) |
| jamia nagr | Jamia Nagar | HIT |  | Jamia Nagar (overture); Jamia Nagar (place); Jamia Millia Islamia (amenity) |
| nebru place | Nehru Place | HIT |  | Nehru Place (public_transport); Nehru Place (public_transport); Nehru Place (public_transport) |
| atm near cp | ATM | HIT | yes | Treebo Check In By Oran - Near Connaught Place (overture); Delhi - Connaught Place (Outer Circle) Branch ATM (overture); Delhi - Gurugram Sec 5 Nr Rlwy Stn Offsite ATM (overture) |
| hospital near saket | hospital / Saket | HIT |  | DR MUKESH GARG (amenity); Max Superspeciality Hospital (amenity); Saroj Hospital (amenity) |
| school sector 62 noida | school / Sector 62 | HIT |  | ASPAM Scottish School | Schools in Noida sector 62 | CBSE School In Noida | Best schools near me | Private Schools In Noida (overture); Gurugram Public School ,sector-62 (overture); Gurugram Public School Sec 62 (overture) |
| petrol pump near karol bagh | petrol / fuel | HIT |  | Indian Oil Fuel Filling Station Service Road (Gupta Service Station-Moti Bagh) (station); Domino's Pizza | Karol Bagh, Near Faiz Chowk, New Delhi (overture); Townhouse Le Heritage Near Karol Bagh Metro (overture) |
| bank near lajpat nagar | bank | HIT |  | New Delhi - Lajpat Nagar (overture); New Delhi - Lajpat Nagar (overture); New Delhi - Lajpat Nagar Iv (overture) |
| gym in dwarka | gym / fitness | HIT |  | Fitness First Platinum Dwarka | Best gym in Dwarka Sector 12, Delhi (overture); Aap ka Bazar (shop); Cult Dwarka Sector 12 - Gyms in Dwarka, New Delhi (overture) |
| post office in rohini | post office | HIT |  | Post Office Sector 16 (synthetic); Post Office Sec-16 Rohini (amenity); Pushpa Bhawan Post Office (amenity) |
| bus stop near iit delhi | platform / bus stop | HIT |  | IIT Gate Bus Stop Public Transport (public_transport); PG Rooms for students near IIT Delhi and JNU campus (overture); Civil Engineering Forum, IIT Delhi (overture) |
| sector 47 noida | Sector 47 | HIT |  | Jagran Public School (building); ArtShala Center For Design (misc); C-35 Sector 47 (addr) |
| sector 12 noida | Sector 12 | HIT |  | Sector 12 (landuse); ICICI Bank Noida Sector 12 (overture); Delhi Metropolitan Education (office) |
| sector 21 faridabad | Sector 21 | HIT |  | Diet Clinic Faridabad Sec 21 (overture); Faridabad - Sector 21 (synthetic); A-21 Dayal Bagh Colony, Sector 39 (addr) |
| sector 56 gurgaon | Sector 56 | HIT |  | Alpine Convent School (building); Gurgaon Sec 56 (overture); Gurgaon Sector 56 (synthetic) |
| alpha 1 greater noida | Alpha 1 | HIT |  | Alpha 1 (landuse); S L Tower (building); Jiva Ayurveda Clinic, Alpha 1, Greater Noida (overture) |
| dlf phase 2 | DLF Phase 2 | HIT |  | DLF Phase 2 (railway); DLF Phase 2 Gurgaon (overture); Dlf Phase-2, Gurgaon (overture) |
| pocket b sarita vihar | Sarita Vihar | HIT |  | Pocket C Sarita Vihar Park (leisure); Pocket N Market-Sarita Vihar (overture); Diabetes & Hormone Clinic (amenity) |
| h block sector 62 noida | Sector 62 / H Block | HIT |  | JSS Boys Hostel (building); JSS Girls Hostel (tourism); Multipurpose Hall (building) |
| a 43 defence colony | Defence Colony | HIT |  | 43 Block C, Defence Colony (addr); 43 Block D, Defence Colony (addr); 430 Block D, Defence Colony (addr) |
| e block model town | Model Town | HIT |  | Police Colony Model Town Block-3 (overture); Dashi (amenity); Model Town Phase 2 (synthetic) |
| c 56 lajpat nagar | Lajpat Nagar | HIT |  | Lajpat Rai Market, Chandni Chowk, Delhi (addr); C 118, Lajpat Nagar 2 (overture); Chocolate Desire (shop) |
| b 7 vasundhara enclave | Vasundhara Enclave | HIT |  | Yes Bank (amenity); Abhinav Apartment (landuse); Anupam Apartments (landuse) |
| h no 1234 sector 15 noida | Sector 15 | HIT |  | Shilsha Technologies (office); Tisha Services Pvt. Ltd. (building); Tata Value Homes Sector 150 Noida (overture) |
| gamma 2 greater noida | Gamma 2 | HIT |  | Gamma 2, Greater Noida (overture); Gamma 2 (landuse); Sector gamma 2 Greater noida (overture) |
| badarpur bus depot | Badarpur | HIT |  | Badarpur Said Bus Stop (overture); Shadipur DTC Bus Depot (overture); Organic Harvest, wazir pur (shop) |
| e 47 greater kailash | Greater Kailash / D Block | HIT |  | Nature's Tattva (shop); E-110 Greater Kailash 2 (addr); E-142 (building) |
| murthal dhaba | Murthal | HIT |  | Gulshan Dhaba Murthal (overture); Mannat Dhaba Dharuhera (overture); Mannat Dhaba Rohtak (overture) |
| azadpur mandi | Azadpur | HIT |  | Azadpur Mandi Delhi (overture); Azadpur Mandi Office (office); Azadpur Fruit and Vegetable Market (boundary) |
| sis ganj gurudwara | Sis Ganj | HIT |  | Gurdwara Sis Ganj Sahib (amenity); Gurdwara Sis Ganj Sahib (place); Gurdwara Sis Ganj Sahib (overture) |
| t3 airport | Terminal | HIT |  | T3 Newdelhi International Airport (overture); Terminal 3 - Indira Gandhi International Airport (overture); New Delhi Airport. Terminal 3 (overture) |
| gaffar market | Gaffar | HIT |  | Gaffar Market (landuse); Gaffar Market (amenity); Gaffar Market (overture) |
| khari baoli | Khari Baoli | HIT |  | Khari Baoli (misc); Khari Baoli (market); Khari Baoli (overture) |
| iimc | IIMC | HIT |  | Indian Institute of Mass Communication (overture); IIMC Delhi (overture); IIMC Machines (overture) |
| house 559 udyog vihar | Udyog Vihar | HIT |  | 559 Udyog Vihar Phase V Road (addr); The Walsons House (building); 559 Block E, Mayur Vihar Phase 2 (addr) |
| b-12 lajpat nagar | Lajpat Nagar / B-12 | HIT |  | Salt Spa (leisure); B-63 Lajpat Nagar 1 (addr); B-12 Sanwal Nagar (addr) |
| aiims | AIIMS | HIT |  | AIIMS (public_transport); AIIMS (public_transport); AIIMS (overture) |
| lodhi garden | Lodi Gardens | HIT |  | Lodhi Garden (public_transport); Lodhi Garden (overture); Lodhi Garden Gate (overture) |

- queries that NEED aliases.json to hit: cp, sarojni nagar, atm near cp
- misses (corpus/index gaps): chandi chowk


## Mobile gazetteer emit

- output: `server/data/corpus/delhi-gazetteer-150k.json` (19.9 MB)
- bundled gazetteer kept: 132,932
- new corpus rows added: 77,068 (skipped 124,166 name+75 m dupes)
- **total: 210,000** (target 210,000)
