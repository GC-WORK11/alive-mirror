# What feeds the map — and how honest it is

Written 2026-10-08 ~17:45 UTC against `base/v2` `c2f63c9` and live prod
`http://65.2.28.40` (GET-only; `build_sha c2f63c9c`). Every number below
was read off the wire or out of the source file cited. Re-verify any of
it in one command: `python3 scripts/research/freshness_probe.py`.

## The short answer

Delhi's government monitors — CPCB and DPCC instruments — feed the map
right now: **52 live instrument readings** at the time of writing,
reaching us through two free, public pipes (WAQI's republication of the
CAAQMS network + DPCC's own 5-minute pages), blended into the ECMWF CAMS
model field. `/health` says which pipes are up and which are dark, in
plain words, on every read.

We do **not** read `api.data.gov.in` or `api.openaq.org` directly
tonight. The official open-data API is TCP-refused from every egress we
own (including AWS ap-south-1 — measured from a Fargate probe inside the
prod VPC, `docs/plan/cpcb-source.md`), and the OpenAQ key on file is
revoked. Both code paths exist, stay in the chain, and report their real
status — they are dark, not hidden. When the chain degrades, the wire
says so (`sources.stations.feeds`), never "ok".

## What feeds the map, line by line

| What | Where it comes from | Cadence | Status on prod now | Code |
|---|---|---|---|---|
| 52 live instruments (CPCB/DPCC CAAQMS) | WAQI `api.waqi.info` republish (primary) + DPCC `dpccairdata.com` 5-min pages (additive, fills verified blind spots) | ~15 min field refresh | `waqi: ok`, `dpcc: ok` — `/health` → `sources.stations` | `airfield.py:404-610`, `ingest_waqi.py`, `ingest_dpcc.py` |
| Model field | Open-Meteo CAMS, ~96 sample points over NCR | hourly upstream, 15-min local cache | up, 96 samples | `airfield.py:215-289`, `airindex.py:455-480` |
| CPCB open-data API (`api.data.gov.in`) | wired, keyed, **dark**: TCP-refused from our egress | — | disclosed in code + probe log | `ingest_cpcb.py`, `docs/plan/cpcb-source.md` |
| OpenAQ v3 | wired, keyed slot, **dark**: stored key revoked | — | `skipped: no key` in chain status | `airindex.py:574-666`, `airfield.py:530-610` |
| Fire belt | NASA FIRMS public 24h CSVs | per field refresh | 120 fires, 16 in-belt, modifier ×1.08 | `fires.py`, `airindex.py:527-571` |
| Wind / ventilation | Open-Meteo 10 m wind + boundary-layer height | per refresh, 90 s retry while unknown | 5.1 km/h from 117°, `known:true` | `airfield.py:620-663` |
| Typical-day climatology | OpenAQ public S3 archive, 125 NCR stations | static artifact, rebuilt | generated 2026-10-01 | `history.py`, `openaq_archive.py` |
| Forecast horizon | CAMS 5-day hourly × live-anchor blend | 30-min cache | live, anchor decays ~9h | `forecast.py` |

## How fresh is it

- The served field is rebuilt or re-fetched at most every **15 minutes**
  (`airfield.py:36 CACHE_TTL=900`; the 15-min worker writes snapshots at
  `ingest_worker.py:63 INDEX_PERIOD_S=900`). At read time the live field
  was **~8 minutes old** (`/health` → `field_age_s: 462`).
- Every served number carries its own age: `/health` → `field_age_s`,
  `field_refresh_in_s`, `field_stale`, per-feed ages (`fires.age_s`,
  `wind.age_s`). Surfaces print "air reading: N min old" from these.
- A station reading older than **3 hours is dropped** in the index build
  (`airindex.py:106 STALE_S`) — the QC report names what was dropped and
  why (`malformed / stale / flatline / spike`, `airindex.py:233-308`).
- The DPCC leg drops rows older than **90 minutes** itself
  (`ingest_dpcc.py:93 MAX_AGE_S`).
- Honest gap: **per-station reading age is not yet on the wire.** The
  field-level ages are; a station-level median age is the first thing
  the source-upgrade RFC proposes to expose.

## How sparse is it

NCR is ~1,484 km². Tonight the blend is:

- **52 real instruments** — roughly one monitor per ~28 km², named on
  the wire (`/aqi` → `field.stations[]`; the map draws these exact
  dots, never a baked-in list).
- **~96 model samples** + kriging with a measured uncertainty band
  between them (`airfield.py:290-402`: instruments de-bias the model
  where they measure; nothing is smoothed into fiction).
- Sparsity is **labeled, not hidden**: every cell carries a confidence
  flag (`/grid` → `conf: hi|med`), every district that leans on partial
  coverage says so (`/v2/districts` → `partial_field_coverage`,
  `centroid_read`, `confidence:"sparse"` — e.g. Jhajjar tonight: 1
  covered cell, flagged sparse), and points outside coverage refuse
  politely (`beyond_field_edge`, `outside_service_area`).
- The uncertainty band itself was **measured, not tuned**: σ covers
  ~95% of held-out station-hours at ±2σ over 3,550 replayed hours
  across 85 stations (`server/data/field_validation.md`,
  `airfield.py:67-80 SIGMA_CAL`).

## What the numbers mean

- `pm25` at a point = de-biased instrument + model blend; `lo`/`hi` =
  the measured ±1.96σ band. Tonight at Connaught Place: **79.6 µg/m³
  [49.1–110.0]**, US AQI 160 on the same basis public dashboards use.
- `us_aqi` is recomputed from the served species, never the model's own
  index (which read 221 vs instruments' 160 tonight — the raw model
  value stays visible as `us_aqi_model`).
- Station readings pass a Kalman smooth (`airfield.py:198-213`) — the
  field tracks the sustained level, not a truck idling past.

## What we disclose vs. what we still owe

Have, on the public wire today: per-source up/down with verbatim
reasons, per-field age + next refresh + stale flag, live instrument
count + names + positions, per-cell confidence, per-district sparse
flags, GRAP labeled "indicative — the legal stage is CAQM's call"
(`airfield.py:1187-1199`), forecast confidence per day
(`confidence:"hi|med|lo"` with the anchor weight printed).

Still owe: per-station reading ages on the wire (RFC §2), a
freshness-by-feed median the demo can quote, and the direct
CPCB/OpenAQ legs lit — both blocked on things money doesn't buy here
(a valid key + an India-reachable egress; `source-upgrade-rfc.md`).
