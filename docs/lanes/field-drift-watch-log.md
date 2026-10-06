# field-drift-watch log — live numbers per tick

Lane: observe-only. Base: http://65.2.28.40. Times UTC unless noted. Started 2026-10-06T03:06:19+00:00.

## Tick 2026-10-06 03:06:19 UTC

| point | pm25 | amb | band | field_age_s | built_at | flags |
|---|---|---|---|---|---|---|
| CP | 88.2 | 79.5 | 69.0–107.4 | 565 | 02:56:54Z | live |
| AnandVihar | 90.5 | 81.5 | 49.9–131.0 | 566 | 02:56:54Z | live |
| Gurugram | 106.1 | 95.6 | 37.4–174.8 | 566 | 02:56:54Z | live |
| Noida | 108.7 | 97.9 | 42.9–174.6 | 567 | 02:56:54Z | live |
| Rohini | 118.0 | 106.3 | 59.2–176.8 | 567 | 02:56:54Z | live |
| Dwarka | 98.9 | 89.1 | 41.4–156.4 | 568 | 02:56:54Z | live |

- /v2/why: drivers=['stagnation:primary', 'trend:secondary']; trend n=26 span=4.9h Δ=23.3µg dir=rising (73.6→96.9)
  - line: “the air is barely moving — the day's pollution is sitting over the city + levels still climbing”
  - fires eval: n=89 belt=22 modifier=1.11 carrying=False feed=firms-public-csv/live age=4240s
  - ventilation: vc=533.0 m²/s blh=308.1m wind=1.73m/s factor=5.63 age=631s
- /v2/city: breath mid=1297.0µg (pm25_mid=90.3) pm25 mean=90.3 max=119.4 field_age=568s fresh=live corridors=10
- /v2/skill: pairs=62 h1_mae=12.8 (n=9) h3_mae=32.0 (n=8) gen_ist=2026-10-06T08:35:50.764979+05:30
- /fires: count=89 belt=22 acq_dates=['2026-10-04', '2026-10-05'] 
- /admin/api/sources: {"/sources/model/up": null, "/sources/model/status": null, "/sources/model/age_s": null, "/sources/model/samples": 71, "/sources/model/field_age_s": 570, "/sources/met/up": null, "/sources/met/status": null, "/sources/met/age_s": null, "/sources/stations/up": null, "/sources/stations/detail": "WAQI \u2192 data.gov.in CPCB \u2192 OpenAQ v3 \u2014 secrets alive108/{waqi,cpcb,openaq} (WAQI_API_KEY,OPENAQ_API_KEY set)", "/sources/stations/status": null, "/sources/stations/n": null, "/sources/stations/fetched_at": null, "/sources/stations/age_s": null, "/sources/stations/readings": 24, "/sources/stations/n_raw": null, "/sources/stations/n_used": null, "/sources/stations/field_age_s": 570, "/sources/stations/stale": null, "/sources/fires/up": null, "/sources/fires/detail": "NASA FIRMS \u2014 pub
- S3 field builds: latest=field/2026/10/06/0255.json.gz @ 2026-10-06T02:56:03+00:00 UTC gap=10.4min

**FLAGS:**
- ⚠ /v2/why history shrinking: n_snapshots=26 (<~30 builds/6h)

## Tick 2026-10-06 03:27:44 UTC

| point | pm25 | amb | band | field_age_s | built_at | flags |
|---|---|---|---|---|---|---|
| CP | 88.9 | 80.1 | 69.6–108.3 | 135 | 03:25:29Z | live |
| AnandVihar | 88.8 | 80.0 | 48.4–129.1 | 136 | 03:25:29Z | live |
| Gurugram | 103.7 | 93.4 | 34.3–173.1 | 136 | 03:25:29Z | live |
| Noida | 109.1 | 98.3 | 42.1–176.2 | 137 | 03:25:29Z | live |
| Rohini | 123.8 | 111.6 | 62.6–185.1 | 137 | 03:25:29Z | live |
| Dwarka | 96.6 | 87.0 | 38.8–154.4 | 138 | 03:25:29Z | live |

- /v2/why: drivers=['stagnation:primary', 'trend:secondary']; trend n=32 span=5.9h Δ=23.3µg dir=rising (72.9→96.2)
  - line: “the air is barely moving — the day's pollution is sitting over the city + levels still climbing”
  - fires eval: n=89 belt=22 modifier=1.11 carrying=False feed=firms-public-csv/live age=135s
  - ventilation: vc=533.0 m²/s blh=308.1m wind=1.73m/s factor=5.63 age=143s
- /v2/city: breath mid=1274.0µg (pm25_mid=88.7) pm25 mean=88.7 max=116.6 field_age=139s fresh=live corridors=10
- /v2/skill: pairs=61 (+-1) h1_mae=12.8 (n=9) h3_mae=31.8 (n=8) gen_ist=2026-10-06T08:55:51.351966+05:30
- /fires: count=89 belt=22 acq_dates=['2026-10-04', '2026-10-05'] 
- /admin/api/sources: {"model": {"samples": 71, "field_age_s": 141}, "met": {}, "stations": {"readings": 24, "field_age_s": 141}, "fires": {"status": "live", "fires": 89, "belt_fires": 22, "age_s": 137, "stale": false}, "location": {"enabled": false}, "routing": {}}
- S3 field builds: latest=field/2026/10/06/0325.json.gz @ 2026-10-06T03:25:30+00:00 UTC gap=2.4min
- flags: none

## Tick 2026-10-06 03:46:53 UTC

| point | pm25 | amb | band | field_age_s | built_at | flags |
|---|---|---|---|---|---|---|
| CP | 89.2 | 80.4 | 70.0–108.4 | 359 | 03:40:55Z | live |
| AnandVihar | 95.4 | 85.9 | 54.2–136.5 | 360 | 03:40:55Z | live |
| Gurugram | 94.7 | 85.3 | 33.4–156.1 | 360 | 03:40:55Z | live |
| Noida | 103.4 | 93.2 | 43.1–163.8 | 360 | 03:40:55Z | live |
| Rohini | 99.1 | 89.3 | 48.4–149.8 | 361 | 03:40:55Z | live |
| Dwarka | 84.2 | 75.8 | 33.9–134.5 | 361 | 03:40:55Z | live |

- /v2/why: drivers=['stagnation:primary', 'trend:secondary']; trend n=32 span=5.9h Δ=22.2µg dir=rising (73.8→96.0)
  - line: “the air is barely moving — the day's pollution is sitting over the city + levels still climbing”
  - fires eval: n=89 belt=22 modifier=1.11 carrying=False feed=firms-public-csv/live age=1284s
  - ventilation: vc=533.0 m²/s blh=308.1m wind=1.73m/s factor=5.63 age=1292s
- /v2/city: breath mid=1196.0µg (pm25_mid=83.2) pm25 mean=83.2 max=107.1 field_age=362s fresh=live corridors=10
- /v2/skill: pairs=71 (+10) h1_mae=12.5 (n=10) h3_mae=30.5 (n=9) gen_ist=2026-10-06T09:16:58.080149+05:30
- /fires: count=89 belt=22 acq_dates=['2026-10-04', '2026-10-05'] 
- /admin/api/sources: {"model": {"samples": 69, "field_age_s": 365}, "met": {}, "stations": {"readings": 24, "field_age_s": 365}, "fires": {"status": "live", "fires": 89, "belt_fires": 22, "age_s": 1287, "stale": false}, "location": {"enabled": false}, "routing": {"up": true, "age_s": 280.2, "stale": false, "backend": "osrm-local", "ms": 342}}
- S3 field builds: latest=field/2026/10/06/0340.json.gz @ 2026-10-06T03:40:36+00:00 UTC gap=6.5min
- flags: none

## Tick 2026-10-06 04:06:00 UTC

| point | pm25 | amb | band | field_age_s | built_at | flags |
|---|---|---|---|---|---|---|
| CP | 89.2 | 80.4 | 70.0–108.4 | 603 | 03:55:58Z | live |
| AnandVihar | 97.5 | 87.9 | 55.7–139.3 | 604 | 03:55:58Z | live |
| Gurugram | 90.8 | 81.8 | 30.6–151.0 | 604 | 03:55:58Z | live |
| Noida | 100.0 | 90.0 | 40.7–159.2 | 605 | 03:55:58Z | live |
| Rohini | 90.9 | 81.9 | 42.7–139.1 | 605 | 03:55:58Z | live |
| Dwarka | 79.6 | 71.7 | 30.7–128.6 | 605 | 03:55:58Z | live |

- /v2/why: drivers=['stagnation:primary', 'trend:secondary']; trend n=30 span=5.7h Δ=15.2µg dir=rising (79.1→94.3)
  - line: “the air is barely moving — the day's pollution is sitting over the city + levels still climbing”
  - fires eval: n=89 belt=22 modifier=1.11 carrying=False feed=firms-public-csv/live age=2431s
  - ventilation: vc=922.1 m²/s blh=536.1m wind=1.72m/s factor=3.25 age=608s
- /v2/city: breath mid=1155.0µg (pm25_mid=80.4) pm25 mean=80.4 max=104.0 field_age=606s fresh=live corridors=10
- /v2/skill: pairs=71 (+0) h1_mae=12.5 (n=10) h3_mae=30.5 (n=9) gen_ist=2026-10-06T09:36:05.212878+05:30
- /fires: count=89 belt=22 acq_dates=['2026-10-04', '2026-10-05'] 
- /admin/api/sources: {"model": {"samples": 72, "field_age_s": 609}, "met": {}, "stations": {"readings": 24, "field_age_s": 609}, "fires": {"status": "live", "fires": 89, "belt_fires": 22, "age_s": 2434, "stale": false}, "location": {"enabled": false}, "routing": {"up": true, "age_s": 13.9, "stale": false, "backend": "osrm-local", "ms": 106}}
- S3 field builds: latest=field/2026/10/06/0355.json.gz @ 2026-10-06T03:55:41+00:00 UTC gap=10.5min

**FLAGS:**
- ⚠ /v2/why n_snapshots shrank 32→30

## Tick 2026-10-06 04:25:38 UTC

| point | pm25 | amb | band | field_age_s | built_at | flags |
|---|---|---|---|---|---|---|
| CP | 89.3 | 80.4 | 70.1–108.5 | 818 | 04:12:00Z | live |
| AnandVihar | 99.1 | 89.3 | 56.8–141.4 | 819 | 04:12:00Z | live |
| Gurugram | 84.9 | 76.5 | 26.2–143.7 | 819 | 04:12:00Z | live |
| Noida | 95.5 | 86.0 | 36.5–154.4 | 14 | 04:25:25Z | live |
| Rohini | 80.2 | 72.2 | 34.2–126.1 | 15 | 04:25:25Z | live |
| Dwarka | 75.7 | 68.2 | 25.3–126.0 | 821 | 04:12:00Z | live |

- /v2/why: drivers=['stagnation:primary']; trend n=None span=Noneh Δ=Noneµg dir=None (None→None)
  - line: “the air is barely moving — the day's pollution is sitting over the city”
  - fires eval: n=89 belt=22 modifier=1.11 carrying=False feed=firms-public-csv/live age=3608s
  - ventilation: vc=922.1 m²/s blh=536.1m wind=1.72m/s factor=3.25 age=1786s
- /v2/city: breath mid=1089.0µg (pm25_mid=75.8) pm25 mean=75.8 max=99.9 field_age=18s fresh=live corridors=10
- /v2/skill: pairs=71 (+0) h1_mae=12.5 (n=10) h3_mae=30.5 (n=9) gen_ist=2026-10-06T09:53:51.008780+05:30
- /fires: count=89 belt=22 acq_dates=['2026-10-04', '2026-10-05'] 
- /admin/api/sources: {"model": {"samples": 69, "field_age_s": 22}, "met": {}, "stations": {"readings": 24, "field_age_s": 22}, "fires": {"status": "live", "fires": 89, "belt_fires": 22, "age_s": 19, "stale": false}, "location": {"enabled": false}, "routing": {}}
- S3 field builds: latest=field/2026/10/06/0425.json.gz @ 2026-10-06T04:25:26+00:00 UTC gap=0.4min
- flags: none

## Tick 2026-10-06 04:45:24 UTC

| point | pm25 | amb | band | field_age_s | built_at | flags |
|---|---|---|---|---|---|---|
| CP | 85.7 | 77.2 | 67.4–104.0 | 280 | 04:40:44Z | live |
| AnandVihar | 79.4 | 71.5 | 46.0–112.7 | 281 | 04:40:44Z | live |
| Gurugram | 69.2 | 62.3 | 24.5–113.9 | 281 | 04:40:44Z | live |
| Noida | 73.8 | 66.5 | 30.4–117.3 | 282 | 04:40:44Z | live |
| Rohini | 68.3 | 61.5 | 32.6–104.0 | 282 | 04:40:44Z | live |
| Dwarka | 72.1 | 65.0 | 31.1–113.1 | 283 | 04:40:44Z | live |

- /v2/why: drivers=['stagnation:primary']; trend n=29 span=5.7h Δ=1.7µg dir=flat (not claimed) (85.6→87.4)
  - line: “the air is barely moving — the day's pollution is sitting over the city”
  - fires eval: n=89 belt=22 modifier=1.11 carrying=False feed=firms-public-csv/live age=1199s
  - ventilation: vc=922.1 m²/s blh=536.1m wind=1.72m/s factor=3.25 age=1208s
- /v2/city: breath mid=876.0µg (pm25_mid=61.0) pm25 mean=61.0 max=79.7 field_age=283s fresh=live corridors=10
- /v2/skill: pairs=80 (+9) h1_mae=12.2 (n=11) h3_mae=31.7 (n=9) gen_ist=2026-10-06T10:15:28.518229+05:30
- /fires: count=89 belt=22 acq_dates=['2026-10-04', '2026-10-05'] 
- /admin/api/sources: {"model": {"samples": 70, "field_age_s": 286}, "met": {}, "stations": {"readings": 24, "field_age_s": 286}, "fires": {"status": "live", "fires": 89, "belt_fires": 22, "age_s": 1202, "stale": false}, "location": {"enabled": false}, "routing": {"up": true, "age_s": 108.1, "stale": false, "backend": "osrm-local", "ms": 79}}
- S3 field builds: latest=field/2026/10/06/0440.json.gz @ 2026-10-06T04:40:32+00:00 UTC gap=5.0min
- flags: none

## Tick 2026-10-06 05:04:47 UTC

| point | pm25 | amb | band | field_age_s | built_at | flags |
|---|---|---|---|---|---|---|
| CP | 83.3 | 75.1 | 65.5–101.2 | 534 | 04:55:54Z | live |
| AnandVihar | 71.7 | 64.6 | 41.4–102.0 | 534 | 04:55:54Z | live |
| Gurugram | 64.7 | 58.3 | 23.2–106.2 | 535 | 04:55:54Z | live |
| Noida | 65.5 | 59.0 | 25.9–105.1 | 535 | 04:55:54Z | live |
| Rohini | 64.4 | 58.0 | 30.9–97.8 | 536 | 04:55:54Z | live |
| Dwarka | 75.0 | 67.6 | 36.3–113.7 | 536 | 04:55:54Z | live |

- /v2/why: drivers=['stagnation:primary']; trend n=29 span=5.7h Δ=-6.0µg dir=flat (not claimed) (88.5→82.5)
  - line: “the air is barely moving — the day's pollution is sitting over the city”
  - fires eval: n=89 belt=22 modifier=1.11 carrying=False feed=firms-public-csv/live age=2362s
  - ventilation: vc=1251.8 m²/s blh=845.8m wind=1.48m/s factor=2.4 age=566s
- /v2/city: breath mid=795.0µg (pm25_mid=55.4) pm25 mean=55.4 max=72.2 field_age=537s fresh=live corridors=10
- /v2/skill: pairs=80 (+0) h1_mae=12.2 (n=11) h3_mae=31.7 (n=9) gen_ist=2026-10-06T10:33:50.854945+05:30
- /fires: count=89 belt=22 acq_dates=['2026-10-04', '2026-10-05'] 
- /admin/api/sources: {"model": {"samples": 72, "field_age_s": 539}, "met": {}, "stations": {"readings": 24, "field_age_s": 539}, "fires": {"status": "live", "fires": 89, "belt_fires": 22, "age_s": 2365, "stale": false}, "location": {"enabled": false}, "routing": {"up": true, "age_s": 259.7, "stale": false, "backend": "osrm-local", "ms": 259}}
- S3 field builds: latest=field/2026/10/06/0455.json.gz @ 2026-10-06T04:55:38+00:00 UTC gap=9.3min
- flags: none

## Tick 2026-10-06 05:19:27 UTC

| point | pm25 | amb | band | field_age_s | built_at | flags |
|---|---|---|---|---|---|---|
| CP | 81.7 | 73.6 | 64.0–99.4 | 498 | 05:11:09Z | live |
| AnandVihar | 68.0 | 61.3 | 39.3–96.7 | 498 | 05:11:09Z | live |
| Gurugram | 60.4 | 54.4 | 21.4–99.4 | 499 | 05:11:09Z | live |
| Noida | 61.1 | 55.0 | 23.9–98.3 | 499 | 05:11:09Z | live |
| Rohini | 62.6 | 56.4 | 30.5–94.7 | 500 | 05:11:09Z | live |
| Dwarka | 74.6 | 67.2 | 36.9–112.3 | 500 | 05:11:09Z | live |

- /v2/why: drivers=['stagnation:primary']; trend n=29 span=5.7h Δ=-11.8µg dir=flat (not claimed) (90.3→78.5)
  - line: “the air is barely moving — the day's pollution is sitting over the city”
  - fires eval: n=89 belt=22 modifier=1.11 carrying=False feed=firms-public-csv/live age=3242s
  - ventilation: vc=1251.8 m²/s blh=845.8m wind=1.48m/s factor=2.4 age=1446s
- /v2/city: breath mid=759.0µg (pm25_mid=52.9) pm25 mean=52.9 max=68.8 field_age=503s fresh=live corridors=10
- /v2/skill: pairs=80 (+0) h1_mae=12.2 (n=11) h3_mae=31.7 (n=9) gen_ist=2026-10-06T10:47:50.885790+05:30
- /fires: count=89 belt=22 acq_dates=['2026-10-04', '2026-10-05'] 
- /admin/api/sources: {"model": {"samples": 69, "field_age_s": 505}, "met": {}, "stations": {"readings": 24, "field_age_s": 505}, "fires": {"status": "live", "fires": 89, "belt_fires": 22, "age_s": 3246, "stale": true}, "location": {"enabled": false}, "routing": {"up": true, "age_s": 33.1, "stale": false, "backend": "osrm-local", "ms": 7}}
- S3 field builds: latest=field/2026/10/06/0510.json.gz @ 2026-10-06T05:10:43+00:00 UTC gap=8.9min

**FLAGS:**
- ⚠ fires feed marked stale (age_s=3246)
