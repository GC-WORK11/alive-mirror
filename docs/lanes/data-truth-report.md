# DATA-TRUTH lane — report

Audited 2026-10-08 ~17:30–18:00 UTC against `base/v2` `c2f63c9`
(= prod's live `build_sha c2f63c9c`; the branch later moved to
`70b733b` — sibling lanes, none of the files cited below changed).
All prod reads were GET-only. Re-verify:
`python3 scripts/research/freshness_probe.py`.

## Header truth (per the brief's instruction)

**We do NOT read `api.data.gov.in` (CPCB open-data) or `api.openaq.org`
directly today.** We DO serve the same instruments — 52 live CPCB/DPCC
CAAQMS readings reach prod through WAQI's republication + DPCC's own
5-minute pages (`/health` → `sources.stations`: `up`, count 52, src
`waqi+dpcc`, feeds `{waqi: ok, dpcc: ok}`). Both direct legs are coded
and stay in the chain; they report dark honestly — CPCB is TCP-refused
from every egress we own including AWS ap-south-1 (measured Fargate
probe, `docs/plan/cpcb-source.md`), and the stored OpenAQ key is
revoked. OpenAQ *is* in the product — as the historical climatology
archive (`history.py`, 125 stations, generated 2026-10-01, stamped on
`/health` → `history`).

## STEP 1 — pipeline map (file:line)

**Sources feeding prod NOW** (`airindex.py:7-54`, `fetch_inputs:741`,
parallel `FETCH_WORKERS=4`):

| Source | Legs / endpoint | Code | Prod status tonight |
|---|---|---|---|
| Instruments | WAQI `api.waqi.info` (`/map/bounds/` + `/feed/@uid/`, EPA sub-index → µg/m³ inversion `ingest_waqi.py:67-191`) → CPCB `api.data.gov.in` res. `3b01bcb8…` (keyed, `ingest_cpcb.py:52-63`) → OpenAQ v3 (`/locations`+`/latest`, `airindex.py:574-666`); chain order + rationale `airindex.py:669-738` | winner stamps `source`; losers ride as `*_status` | `waqi+dpcc` won; CPCB refused; OpenAQ `skipped: no key` |
| DPCC additive | `dpccairdata.com` index + `AallStationView5MinData.php`, opt-in flag `ALIVE_DPCC_INGEST`, never preempts, fills 7 verified blind spots | `ingest_dpcc.py:79-120`, `airfield.py:464-499` | on in prod, `dpcc: ok` |
| Model prior | Open-Meteo CAMS pm2_5 grid over NCR bbox `(76.75,28.15,77.95,28.98)` | `airindex.py:98,455-480` | up, ~100 samples |
| Fires | NASA FIRMS public 24h CSV → smoke modifier on prior only | `fires.py`, `airindex.py:527-571` | up, 120 fires / 16 in-belt / ×1.08 |
| Met | Open-Meteo wind+BLH → ventilation VC | `airindex.py:483-524`, `airfield.py:620-663` | 5.1–5.3 km/h @117–118°, `known:true` |
| Climatology | OpenAQ public S3 archive → (month,hour-IST) p25/med/p75, 125 stations | `history.py` | live |

**Poll cadence:** field refresh TTL **900 s** (`airfield.py:36`);
snapshot worker every **900 s** (`ingest_worker.py:63 INDEX_PERIOD_S`),
snapshots → `s3://$ALIVE_AIR_BUCKET/field/YYYY/MM/DD/HHmm.json.gz`,
keep 96 (24 h), CloudWatch ns `ALive-108` emits
`StationsUsed/FieldAgeSeconds/MeanSigma` (`ingest_worker.py:276-304`).

**Live-station count vs interpolated share NOW:** 52 instrument
readings + ~100 model samples → kriged cells carry
`src ∈ {station, model, inferred}` + `sigma` + `n_stations_within_10km`
+ `nearest_station_km` (`airindex.py:875-991`). Sparse districts flag
themselves (`/v2/districts` → Jhajjar `confidence:"sparse"`,
`cells_covered:1`, `centroid_read:true`).

**Staleness:** `STALE_S=3h` drop + flatline ≥3 identical + >5σ spike
(`airindex.py:106-110`, `qc_stations:233-308`); DPCC self-drops >90 min
(`ingest_dpcc.py:93`); served field marks `field_stale` past 45 min
(`airfield.py:51`). Kalman Q=12/R=60 smooths each station
(`airfield.py:198-213`). De-bias needs ≥8 instruments + ≥10 model pts
(`airfield.py:290-402`). σ calibrated — 95.2% coverage @±2σ over 3,550
held-out station-hours (`SIGMA_CAL=3.2`, `airfield.py:57-76`,
`server/data/field_validation.md`).

**Confidence signals on the wire:** `field_age_s`,
`field_refresh_in_s`, `field_stale`, `sources.*.{up,feeds,age_s}`,
`field.stations[]` (names+positions), per-cell `conf`,
`confidence:"field|sparse"`, `partial_field_coverage`,
`centroid_read`, `beyond_field_edge`, `outside_service_area`,
`/aqi` `pm25_lo/hi`, `us_aqi_model` kept visible, forecast
`confidence hi|med|lo` + anchor weight (`forecast.py:545+`),
GRAP labeled indicative (`airfield.py:1187-1199`).

## STEP 2 — judges' sources, factually

- **CPCB `api.data.gov.in`**: resource `3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69`
  ("Real time Air Quality Index", catalog `a3e7afc6…`, updated
  25/09/2026); free `api-key` via MyGov SSO "Generate API Key";
  `format=json`, `filters[state]`, `filters[pollutant_id]`,
  `limit≤1000`+`offset` paging; `last_update` IST; **no coordinates**
  (registry join required); ~hourly. **TCP-refused from our egress —
  verified twice** (dev box + Fargate ap-south-1). CCR dashboard API is
  private/encrypted — not wired, documented and rejected.
- **OpenAQ v3**: `X-API-Key` header; free **60 req/min + 2,000 req/hr**;
  `/v3/locations?bbox=…&parameters_id=2` + `/v3/locations/{id}/latest`;
  per-record datetimes. OpenAQ **re-ingested India's CPCB reference
  network in 2025** (their year-in-data) — Delhi regulatory coverage is
  real again. Our adapter needs only a valid key.
- **Verdict: defensible.** Answer to "are you using CPCB/OpenAQ?" —
  yes, the same instruments, through republishers, because the
  official APIs refuse our egress / our key; and the wire says all of
  this out loud. Free real upgrade found → `source-upgrade-rfc.md`
  (RFC-1 OpenAQ key flip = zero code; RFC-2 CPCB via free India-egress
  relay with failure modes).

## STEP 3 — shipped docs

- `docs/judges/data-truth.md` — transparency page (sources, freshness
  math, sparsity in words, interpolation limits, have-vs-owe disclosure)
- `docs/judges/demo-script.md` — 3-min, 6 beats, every number a live GET
- `docs/judges/checklist-vs-brief.md` — every brief + X-claim line →
  shipped/partial/absent + evidence
- `docs/judges/source-upgrade-rfc.md` — RFC-1/RFC-2 build-ready
- `docs/judges/x-post-thread.md` — 3 posts, each mapped to a beat
- `scripts/research/freshness_probe.py` — GET-only probe printing every
  cited number (ran clean: `instruments 52`, `pm25 80.2`, compare
  14.0→501.3, Jhajjar sparse)

## Honest gaps surfaced (not hidden)

1. Per-station reading ages are not on the wire (RFC-1 fixes it — each
   OpenAQ latest record carries `datetime`).
2. Live refresh path has no explicit staleness gate on the WAQI leg
   (the snapshot path's 3h QC + DPCC's own 90min drop cover it; a
   live-path age check is a real follow-up).
3. The X-announced "hotel/stay least-pollution" picker is **partial**:
   the field answers it (`/escape`, `/v2/districts`); no dedicated stay
   surface exists at audit HEAD — flagged as such in the checklist, not
   claimed.
4. `api.data.gov.in` refusal may be AWS-IP reputation, not policy —
   RFC-2 option 1 tests that for $0.

No code touched outside `docs/` + `scripts/research/`. No PR, direct
push to `base/v2`.
