# Accuracy-holdout report — prod /aqi vs DPCC live instruments

Lane: independent-holdout accuracy evidence for "how accurate is the data at the
particular home the user resides at." GET-only probes against prod; nothing tuned,
nothing filtered out of embarrassment.

- **When:** 2026-10-06 evening, three probe rounds ≈ 15:26 / 16:08 / 16:50 UTC
  (≈ 21:00–22:20 IST). DPCC station pages stamped 20:45 / 21:00–21:05 / 21:30 IST.
- **Field under test:** prod `alive108-…elb.ap-south-1.amazonaws.com`,
  `serving=live`, `sources.stations=waqi` (24 feeds) + `open-meteo/cams` model
  (69 samples), `build_sha=f2ee6bff` during round 3. Wind known (8.8 km/h from 90°).
- **Truth source:** DPCC 5-minute station pages (`dpccairdata.com`) — a different
  instrument network than anything the field ingests. The live set is **30
  stations**, not ~24: the index tree lists 24, and 6 more (IGNOU, JNU, CWG
  Akshardham, NSUT West Campus, Talkatora Garden, SBV Delhi Cantt) appear only in
  per-station-page nav bars. `Supersite (Rouse Avenue)` exists but is stale
  (last data March 2025).

## How "holdout" was decided per station

For each station site, `nearest_sample_km` (API-reported distance to the nearest
field sample) plus distance to the nearest **model** point (airfield.py STATIONS
+ fill grid — model sample coords are enumerable):

| class | rule | meaning |
|---|---|---|
| `GAP` | `nearest_sample_km ≥ 1.0` | no field sample of any kind at the site → **definitive holdout** |
| `LIVE-ADJ` | `km ≤ 0.4` AND `model_km ≥ 0.5` | a non-model sample sits at the site → instrument is in the blend |
| `ANCHOR` | `km ≈ 0` AND `model_km ≈ 0` | model point on-site; ingestion indeterminate from geometry alone |

`pm25_ambient` (field value before smoke overlay) is compared against the
station's raw PM2.5 µg/m³.

## Results

| class | stations | obs | MAE µg/m³ | RMSE | bias (served−truth) |
|---|---|---|---|---|---|
| GAP (provably blind, 1.5–5.8 km) | 7 | 16 | **22.8** | 26.5 | **+3.2 (+6%)** |
| LIVE-ADJ (instrument in blend) | 6 | 16 | **16.4** | 19.3 | −9.2 (−15%) |
| ANCHOR (model point, ambiguous) | 17 | 49 | **31.9** | 39.8 | **−24.6 (−29%)** |
| **ALL 30 sites** | 30 | 81 | **27.1** | 34.2 | −16.0 (−22%) |

Two suspect DPCC rows were flagged and excluded above: `Rohini r1` (PM2.5=3 while
PM10=339 — sensor glitch) and `Alipur r3` (blank in r2, flickers to 3 in r3 —
instrument dying). Including them changes the all-site MAE by <0.3.

### Per-station (3 rounds: DPCC truth / field served; bold = gap class)

| station | class | km | r1 true→served | r2 true→served | r3 true→served | mean err |
|---|---|---|---|---|---|---|
| Alipur | live-adj | 0.1 | 25→28.8 | — | 3*→40 | +3.8 |
| Anand Vihar | anchor | 0.0 | 80→46.2 | 47→72.4 | 47→75.9 | +6.8 |
| Ashok Vihar | anchor | 0.0 | 39→36.7 | 69→42.9 | 69→49.6 | −15.9 |
| **CWG Akshardham** | **gap** | 1.8 | — | 85→52.8 | 79→57.5 | −26.9 |
| Karni Singh Range | live-adj | 0.3 | 96→47.0 | 66→84.6 | 66→85.9 | −3.5 |
| Dwarka Sec-8 | anchor | 0.0 | 56→57.9 | 84→61.7 | 84→63.3 | −13.7 |
| **IGNOU** | **gap** | 4.1 | — | 27→64.7 | 28→67.7 | +39.1 |
| **JNU** | **gap** | 2.7 | — | 58→54.3 | 69→57.2 | −7.6 |
| Jahangirpuri | anchor | 0.0 | 91→36.8 | 143→63.4 | 143→72.6 | −68.1 |
| JLN Stadium | live-adj | 0.3 | 74→48.4 | 80→63.2 | 80→64.0 | −19.5 |
| Dhyan Chand Stadium | live-adj | 0.1 | 53→45.4 | 64→55.7 | 64→56.9 | −7.7 |
| Mandir Marg | anchor | 0.0 | 138→50.6 | 75→74.9 | 75→77.1 | −28.5 |
| **Mundka** | **gap** | 3.4 | 57→40.8 | 84→60.3 | 84→63.5 | −20.1 |
| **NSUT West (Jaffarpur)** | **gap** | 3.6 | — | 51→52.2 | 59→58.9 | +0.6 |
| Najafgarh | live-adj | 0.3 | 53→38.4 | 61→48.7 | 61→53.7 | −11.4 |
| Narela | anchor | 0.0 | 90→40.3 | 114→61.1 | 114→65.7 | −50.3 |
| Nehru Nagar | anchor | 0.0 | 74→50.1 | 51→64.7 | 51→68.3 | +2.4 |
| Okhla Ph-2 | anchor | 0.0 | 91→56.9 | 78→77.3 | 78→83.6 | −9.7 |
| Patparganj | anchor | 0.0 | 62→37.0 | 35→56.6 | 35→61.1 | +7.6 |
| Pooth Khurd, Bawana | anchor | 0.0 | 77→45.0 | 99→64.3 | 99→71.7 | −31.3 |
| Punjabi Bagh | anchor | 0.0 | 79→36.5 | 79→57.9 | 136→62.0 | −45.9 |
| Pusa | anchor | 0.0 | 36→36.0 | 75→47.1 | 75→49.9 | −17.7 |
| R.K. Puram | anchor | 0.0 | 57→57.7 | 105→64.3 | 105→68.5 | −25.5 |
| Rohini | anchor | 0.0 | 3*→41 | 132→73.8 | 132→83.6 | −53.3 |
| **SBV Delhi Cantt** | **gap** | 5.8 | — | 16→56.6 | 17→59.1 | +41.3 |
| **Talkatora Garden** | **gap** | 1.5 | — | 50→72.5 | 51→74.6 | +23.2 |
| Sonia Vihar | anchor | 0.0 | 138→37.7 | 138→76.2 | 114→86.5 | −63.2 |
| Sri Aurobindo Marg | live-adj | 0.3 | 31→45.9 | 69→47.8 | 69→49.7 | −8.5 |
| Vivek Vihar | anchor | 0.0 | 114→58.2 | 69→85.5 | 69→89.2 | −6.4 |
| Wazirpur | anchor | 0.0 | 50→34.0 | 50→44.1 | 74→49.5 | −15.5 |

\* suspect instrument reading.

## Reading it honestly

- **The true holdout (GAP) was the best-behaved class tonight.** At 7 sites the
  field provably cannot see the instrument (1.5–5.8 km away), MAE was ~23 with
  +6% bias — the model+debias field landed in the right place because tonight's
  gap stations read moderate (16–85) and the field sits ~50–75. That flatness
  cuts both ways: IGNOU/Delhi Cantt read ~17–28 true while we served ~60 (+40).
- **The misses are real and they're at anchors.** Jahangirpuri (−68), Sonia Vihar
  (−63), Rohini (−53), Narela (−50), Punjabi Bagh (−46): local pollution spikes
  up to 2× what the field serves, invisible to a blend built from instruments
  elsewhere. This is the honest answer to "accuracy at your home": within ±15–20
  where an instrument exists, but **local hotspots can be missed by 50–70 µg/m³**.
- **Live-adjacent sites (~16 MAE) partly reflect pipe differences.** At those
  sites the field echoes WAQI's feed, and WAQI publishes EPA-NowCast IAQI (a
  trailing 24h-weighted average) — not the raw 5-min µg DPCC shows. At Karni
  Singh tonight: DPCC raw 66, WAQI-pipe ≈97 µg-equiv, we served ~85 — between
  the two instruments' own readings.
- Anchor ambiguity: `km≈0` only proves a model point exists. Value-test
  (served within ~15µg of WAQI's own live µg-equivalent) suggests Anand Vihar is
  ingested; Mandir Marg r1 (served 51 vs 138/124) and Sonia Vihar show anchors
  that are **blind**.

## Demo-speak (3 sentences)

1. "At seven government instruments our blend never touches — up to 6 km from
   the nearest thing it does read — tonight's mean absolute error was
   ~23 µg/m³ with essentially zero bias; at sites where a live instrument sits
   in the blend, error drops to ~16."
2. "Where we're blind and a local hotspot flares — Jahangirpuri read 143 while
   we served 73 — we miss, and that's exactly why the product shows a band and
   a distance-to-nearest-real-reading, not a single confident number."
3. "'Accuracy at your home' isn't a claim for us — the API returns how far the
   closest real measurement is, and tonight's independent check says: tight
   within ~2 km of an instrument, honest-but-coarse in the gaps."

## Broken / unreachable fetch paths (audit trail)

- OpenAQ v3 API — both the org secret (`alive108/openaq`) and a personal key → **401** (keys revoked/dead).
- CPCB portal (`airquality.cpcb.gov.in`) — TCP timeout, geo-blocked from this box.
- DPCC legacy pages (`airpoView15MinData.php`, `civilLines…`, `mmView15MinData`, etc.) — **404**.
- DPCC `index.php` — 406 ModSecurity under plain curl; the bare `display/` index works with a browser UA. (Sibling lane `scripts/testday/field_sampler.py` also fetches it.)
- stateair.net — dead site.
- PurpleAir `data.json` — 404 (API now key-gated).
- sensor.community Delhi bbox — reachable but **zero sensors** in Delhi.
- IQAir `website-api.airvisual.com` — search endpoint works; no public station-value endpoint found (all probes 404); iqair.com pages → 429.
- SAFAR (`tropmet.res.in`) — serves a CMS page that redirects to `ews1.tropmet.res.in` (private IP, unreachable).
- `aqi.in` — 403 Cloudflare challenge.
- US Embassy/AirNow international page — restructured, old URLs 404.

So the independent truth tonight is DPCC only (govt reference-grade, raw µg,
~5-min cadence, 30 stations) plus a same-pipe cross-check via WAQI's own public
city pages (aqicn.org embeds each station's live IAQI).

## Method files

- `/tmp/dpcc_r{1,2,3}.json`, `/tmp/dpcc_extra_r{2,3}.json` — raw DPCC rounds.
- `/tmp/probe_r{1,2,3}.json` — prod `/aqi` probes per station site.
- `/tmp/waqi_pages.json` — WAQI's own live IAQI per resolved Delhi slug.
- `/tmp/holdout_obs.json` — the 83-observation merged table (incl. suspect flags).
- Sampler for future rounds: `scripts/testday/field_sampler.py` (12 cells).
- Coord sources: `server/data/delhi_climatology.json.gz` registry IDs noted per
  station (e.g. Mundka=DPCC-10486, NSUT West=DPCC-6224595 Jaffarpur).
