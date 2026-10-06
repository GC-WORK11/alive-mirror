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
