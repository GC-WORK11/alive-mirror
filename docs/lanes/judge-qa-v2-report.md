# Lane report: judge-qa-v2 — dosimeter-epoch attack set, verified live

Pass: 2026-10-06 ~02:55–03:20 UTC (08:25–08:50 IST). Every curl ran
against `http://65.2.28.40` during the pass (build `9af96710` —
`/health.build_sha`). Deliverable: `docs/plan/judge-qa-v2.md` — 10
mandated attacks + 4 hostile extras, each with honest answer, live
proof, stage line. Rules kept: GETs + `POST /v2/plan` + `POST
/v2/reroute` only; docs-only; no deploys, no admin-token probes.

## Verdict per mandated question

| # | attack | verdict | load-bearing proof |
|---|---|---|---|
| 1 | timeline fakeable | answered (with honest caveat) | `/v2/archive` recorded hours 0-8, 0 gaps, `storage.bucket:alive108-air`; `archive.py:24-52` append-only/gaps-are-data; `daylog.ts:1-14`; apk-populated "Honest seed"; demo-seed:78 forbids hand-seeding |
| 2 | 33× believable | answered | live `POST /v2/plan`: walk 556.6/car 16.8 = 33.1×; decomposes 2.36× conc ×10.0× time ×1.4× VE; `exposure.py:51-145` tables |
| 3 | calibration | answered | `/aqi.calibration` LOO 94 stations (MAE 46.1/bias +0.3) on the wire + `field_validation.md` 3,550 pairs, ±2σ 95.2% vs 95.4%, per-station bias table published |
| 4 | k≥3 → empty corridors | answered (the gate IS the answer) | `/v2/city/moves` 12 of 54 active; `/community` devices [6,4,4,3,4] all ≥3; `community.py:89-90` |
| 5 | sparkline seeded | answered | `dayfield.ts:1-11` (12×GET /grid?h=, holes-not-guesses); `/today` `openaq-s3-climatology`; `/health.history` 125 stations; `useShellFlow.ts:~361` completed-trip-only logging |
| 6 | modifier 1.09 why | answered — drifted to **1.11** live | `fires.py:187-201` recomputed exactly: 22 belt/160 ×2.75 →1.378, wind 102° non-NW →×0.3 →**1.11** on wire; prior-only application `airindex.py:838-854`; `/v2/why` `carrying:false` |
| 7 | model beats persistence? | **NOT answerable as a win — flagged** | `/v2/skill` grades model-vs-recorded only; doc 05's "beat persistence" criterion not on the wire. Computed baseline from `/v2/archive` myself: persistence wins every horizon tonight (below) |
| 8 | WAQI dies | answered — plus the harder truth | `ingest_waqi.py:336,371` unavailable→empty; `airindex.py:10-14` prior-only field; `airfield.py:47,1008-1042` snapshot/stale flags; **WAQI is the only live feed** (handoff ~L54: all keyless paths probed dead/fake from prod VPC) |
| 9 | cigarette sensationalism | answered | `exposure.py:169-209` CIG_UG=316 + basis on wire; `/v2/city` breath 1297 µg ≈4.11 cig w/ Berkeley Earth basis string; `26-honest-impact.md:60`; `claims-audit.md` lists its own ✗ rows |
| 10 | sideloaded APK same code? | answered — provenance, not attestation | `apk-drive-v5-report.md`: `alive108-0a26f5a.apk` named by commit, `./gradlew assembleRelease` recipe, bundle greps 65.2.28.40; populated-report pcap = GETs+/v2/plan only; no in-app SHA screen (stated) |

## The finding of this pass: persistence wins tonight

`/v2/skill` publishes model-vs-recorded but no persistence baseline;
`docs/05-validation-impact.md:10` names "Beat persistence baseline on
RMSE" as the acceptance criterion — **it isn't served**. I computed it
from the public archive payload alone:

```python
# GET /v2/archive → hours[recorded].cells = [lon,lat,pm25,...] per IST hour
# persistence(t, h) = recorded[t-h]; compare |persist - rec[t]| vs
# served model MAE from /v2/skill horizons (same emit lattice)
h+1: persist 5.4  vs served 12.8   (8 pairs, 968 cells)
h+2: persist 10.1 vs served 21.9
h+3: persist 14.9 vs served 32.0
h+4: persist 19.2 vs served 40.4
h+5: persist 21.7 vs served 48.6
```

Fair context, said in the doc: 8 recorded hours of a smooth overnight
ramp (field mean 70.8→95.3 over 5.9 h per `/v2/why`) is persistence's
best regime; the stored `model` block per hour is the earliest-lead
surface (lead 3-10 h), which is the stricter reading; and the model
carries band calibration + 5-day horizon + spatial structure that
persistence cannot. None of that changes the verdict — **if a judge
asks for the bake-off, "we beat it" is false today.** Written as the
top demo-morning risk.

## Verified live during the pass (the numbers the doc quotes)

```
/health       ok · build 9af96710 · alive_core · edges 1,070,459 /
              903,058 priced · field_age 64 s · ttl 900 · 24 WAQI /
              71 model samples · fires 89 · history 125 stations
              (openaq-data-archive) · wind 6.1 km/h @114°
/v2/plan      CP→GG: 24 options · took_ms 5386 · smoke 1.11
              car-AC 16.8 (7.2-26.4) conc 59.1 · walk 556.6
              (238.7-874.5) conc 139.7 · eta 1703 s vs 17071 s
              → 33.1× (2.36× ×10.0× ×1.4×)
/v2/reroute   24 options · fresh route_id · took_ms 368
/v2/skill     62 pairs since Oct-5 20:00 IST · h+1 MAE 12.8/+9.7,
              band-hit 73.3%/77.8% · h+7 ok(5) · h≥8 thin ·
              overall MAE 38.7/+36.7
/v2/archive   13 snapshots · today h0-8 recorded · 0 gaps ·
              all 9 carry stored forecast · storage bucket
              alive108-air prefix archive/
/community    22 obs · 6 in 24 h · 14 contributors · corridors
              devices [6,4,4,3,4] · latest_obs_age 342 min
/v2/city/moves min_k 3 · 39 trips/7d · corridors 12/54 ·
              suppressed_trips 0
/v2/city      breath 1297 µg ≈4.11 cig (lo 0/hi 9.66) · typical
              m10 h8 median 113.3, vs_now −20.3% · pm25 mean 90.3
/v2/why       stagnation VC 545 vs ~3000 · trend +24.5 µg over
              5.9 h (31 builds) · fires carrying:false @ wind 102°
/aqi @CP      pm25 88.2 bz/79.5 amb · band 69.0-107.4 · aqi 163 ·
              fires 89/22 belt/76.8 MW · modifier 1.11 ·
              nearest_sample 1.8 km · nh3 null · LOO block live
/v2/day       cleanest 15:30-18:30 @39.7 vs day 114.8 · 2 decision
              rows · anchor τ9 h declared on the wire
/today        24 decade-medians, openaq-s3-climatology
/v2/reach     walk@25 → 2,596 edges/111 km, partial:false;
              car@25 → 666,649 edges, edge_partial:true
/v2/ledger    422 without X-Device-Token (keyed read, hashed)
/v2/districts 29 rows · Delhi NCT 98.4
/depart       auto CP→GG now 45.1 → best +8 h 16.1 (64% less)
/v2/outlook   5 days; tomorrow confidence:lo, anchor_w 0.047
/fires        live GeoJSON, firms-public-csv
/admin        200 · ~125 KB engine-room HTML
/observe      POST → 410 Gone per main.py:1273-1283 (bare POST
              without a body 422s on validation first)
/grid?h=0     cells=8 GeoJSON served (the sparkline's strokes)
```

Local runs: `Mobile node src/store/test-runner.mjs` **18/18** (was 13
at v1 — suite grew); `pytest test_parity_dose + test_community_v2 +
test_v2` **60/60**.

## What changed vs v1 (judge-qa / judges-faq)

- `smoke_modifier` 1.09 → **1.11** on the wire — the v1 clause survives
  verbatim modulo drift (now re-derivable: belt 22/160, non-NW ×0.3).
- `/v2/skill` matured: 21 → 62 pairs; h+1…h+7 all graded `ok` now
  (v1 had h≥3 thin); overall block exists.
- Dose ladder moved with the heavier field: car 10.8→16.8, walk
  357.9→556.6 — the 33× multiple holds (33.1× now).
- `/aqi` gained the `calibration` block on the wire (LOO 94) — v1 cited
  the file version only.
- The v1 "show me a failure" hour-4 archive gap is gone — today's
  archive has 0 gaps; the thin-floor demonstration now lives at h≥8
  (`thin(4),(3),(2),(1)`) instead.
- `/v2/day` now requires lat/lon (422 without) — demo-rehearse-v2
  already flagged the schema drift; confirmed on this pass.
- New since v1: GRAP-`equivalent_stage` surface on `/v2/day` +
  `/v2/city` (`83d47de`, lane `grap-stage`) — labeled "computed from
  today's air, not the official CAQM declaration"; covered as hostile
  Q15. Live: day@CP stage 1 (aqi 285), city stage 0 (aqi 196) —
  different bases, each named on the wire.
- Community: same honest posture — 22 obs/14 contributors (identical
  totals to v1's read; 24 h counts moved: obs_24h 6, avoided_24h 477.3).

## Not done / limits of this pass

- No POST to `/v2/trip`, `/observe`, `/report` (lane rule) — the
  plausibility floor (`trip.py:251-262` 422s) and the 410 are cited
  from code + the v5 lane's permitted probe, not re-fired.
- S3 object listing for the archive not re-verified from this box (no
  `aws` CLI on the macOS VM); the bucket/prefix claim is off the wire's
  own `storage` block + `archive.py`.
- The persistence table is my one-off computation over the archive's
  downsampled lattice (stride 4, 121 cells) — same cells the skill
  join uses at that granularity; matched-cell MAE, not the pipeline's
  own pairing rules.
- Admin `/admin/api/*` surfaces not probed (token-gated by design).

## Files

- `docs/plan/judge-qa-v2.md` — the attack sheet (10 mandated + 4
  extras + risk register).
