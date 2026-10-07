# prod-numbers-card — every stage number re-verified on the DEPLOYED build

Lane: `prod-numbers-card`. Probe window **2026-10-07 03:04–03:45 UTC**
(≈08:35–09:15 IST). Ground truth: live `GET`s + the one sanctioned
`POST /v2/plan` (test plan allows it — `verify_numbers.sh`/`warm_task.py`
precedent) against prod `alive108-…elb.ap-south-1`,
build **`aee635eb`** (`/health.build_sha`; == HEAD−17 at probe time,
docs plus small server/observability deltas — tripwires, `token_via`,
XFF rate-limit, DelhiToday title-case, `/city` UTC day-key).
HEAD `base/v2` = `3d30c99` at probe (`368c155` at push — mobile delta,
no wire change).

Method note: no doc was trusted — every wire number below was re-derived
from a live response or re-computed from the same upstream feed
(FIRMS CSVs) this pass.

## The headline

- **The LOO deploy-lag resolved.** Prod serves the rebuilt artifact
  (`mae_ug:8.8, n_stations:70`, krige refit per held-out WAQI+DPCC
  instrument) — byte-identical to `server/data/field_calibration.json`.
  **Every doc still quoting 46.1/n=94 now contradicts the live wire**
  (list in §9 — includes `NUMBERS.md` itself, README, writeup, shotlist,
  demo-script, judges-faq, API reference).
- **Fires verified against FIRMS itself**: 80 ring / 20 belt / 42.1 MW on
  the wire; independently re-counted from the same 4 public 24h CSVs —
  **exact match** (S-NPP 15/3/5.6 MW · N20 20/4/4.2 · N21 39/13/32.2 ·
  MODIS 6/0/0).
- **Stations drifted to 53** (one DPCC instrument aged out — honest,
  documented behavior). All surfaces agree (health 53 = /aqi 53).
  **But `verify_numbers.sh` will FALSE-FLAG this at T-45** — its
  accepted-states whitelist is still `{54, 24}`; single-instrument
  drift to 53/52 was already observed in the max2 run (54→53→52).
- **Community moved**: donations landed since NUMBERS §2 — `obs_total
  40` (was 22), `contributors 22` (was 14), `avoided 1,028.5 µg`
  (was 725.9), `obs_today:1` (8.0 km, 62.5 µg avoided). Rehearsed
  "22 obs/14 contributors" lines are stale in the good direction.

## 1 · Stations — AGREE

| surface | prod value @03:1xZ | match? |
|---|---|---|
| `/health.sources.stations.count` | **53** | ✓ |
| `/health…stations.feeds` | `{waqi:"ok", dpcc:"ok"}` | ✓ (no transient-dpcc-drop window observed this pass) |
| `/health…stations.source` | `"waqi+dpcc"` | ✓ |
| `/aqi.field.station_readings` | **53** | ✓ — equals count |
| `/aqi.field.stations_status` | `{waqi:"ok", dpcc:"ok"}` | ✓ |

53 = honest churn, not a drop: instruments age out individually under
`MAX_AGE_S` (max2 watched 54→53→52 across 3h). **Doc quotes of "54" are
now off-by-one** — say "about 53 government instruments" or "54
instruments when both feeds are full". Landing `stnHero` live-renders
the real count, so the page never lies; rehearsed VO pins of "54" or
"52" (video re-tape) are point-in-time reads.

## 2 · Edges — MATCH, verbatim-safe

`/health.routing`: `edges:1,070,459`, `edges_priced:903,058`,
`engine:"alive_core"` — matches docs claim **903,058 / 1,070,459**
exactly, structural (moves only on graph rebuild). Landing live-renders
`1.07`/`0.90` million from this wire.

## 3 · Field — MATCH

| claim | prod | verdict |
|---|---|---|
| age cycles ~900 s | `field_age_s` observed 336 → 467 → 800 → 836 s across the pass; `refresh_ttl_s:900`; `field_stale:false` | ✓ rebuild lands inside TTL |
| `/v2/why` drivers live | `drivers[0]=stagnation` — BLH 366.8 m × wind 1.88 m/s → VC 690 m²/s vs ~3,000 ref; trend +0.9 µg over 5.7 h / 27 snapshots; `cannot_tell:[]` | ✓ live, real evidence attached |
| fires count | `fires:80`, `belt_fires:20`, `belt_frp_mw:42.1`, feed `firms-public-csv` live, `age_s≈3,100–3,575` of `stale_after_s:22,500` | ✓ **re-derived from FIRMS CSVs this pass — exact match** |
| carrying flag | `carrying:false` — wind 110–112° (E–SE) outside the NW gate (270–360°); `modifier ×1.10` = `(1 + 20/160×2.75) × 0.3` | ✓ arithmetic + gate logic consistent with code (`fires.py:212-217`) |

## 4 · LOO calibration — PROD NOW SERVES THE NEW ARTIFACT

`/aqi.calibration` on `aee635eb`:

```json
{"method":"leave-one-out over live WAQI+DPCC instrument readings (krige refit per held-out station)",
 "n_stations":70,"mae_ug":8.8,"rmse_ug":12.7,"median_abs_pct":8.8,"mean_bias_ug":0.2}
```

== `server/data/field_calibration.json` at HEAD (commit `6ad7de6`).
**The deploy-lag story in `judge-answers-v3` §6 is overtaken by events**
— the card says "46.1 still on the wire"; tonight the wire says 8.8.
Rehearse the NEW line, not the lag apology.

**Demo line:** "between stations the rebuilt LOO is about 9 µg — a real
krige refit per held-out WAQI+DPCC instrument, n=70; at an instrument it
reads the instrument itself." The three error figures a judge can
conflate, kept straight: **8.8** LOO between stations · **~8.4** the
3-hour live blend-vs-DPCC MAE (max2) · **22.0** archive-window MAE
(field_validation.md, the clean-air holdout — different measure).

**Docs still quoting 46.1/n=94 — now contradicted by the live wire:**
`docs/plan/NUMBERS.md` §1 artifact row (the ledger itself),
`README.md` L80, `docs/submission/writeup.md` L192,
`docs/submission/repo-readme.md` L214, `docs/submission/video-shotlist.md`
L133, `docs/plan/demo-script.md` L106, `docs/plan/judges-faq.md` L274,
`docs/plan/10-claims-ledger.md` L17, `docs/25-peak-physics.md` L15,
`docs/24-design-language-spec.md` L319, `docs/api/REFERENCE.md` L790–792,
`docs/api/samples/get_aqi.json`, `docs/10-shipped.md` L17.
(`docs/plan/judge-qa-v2.md` quotes the old wire sample but flags it as
the OpenAQ-era artifact — half-honest, still worth a refresh.)

## 5 · Dose/typical — the math HOLDS; "46%" is drift, not a constant

`vs_now_pct = (pm25_bz − typical_median) / typical_median`, recomputed
from the returned typical median at 3 points — **exact agreement**:

| point | pm25 (bz) | typical median (Oct, h+8 IST) | wire `vs_now_pct` | recomputed |
|---|---|---|---|---|
| CP (28.6315,77.2167) | 74.3 | 113.3 | **−34.4%** | −34.4% |
| Gurugram (28.4595,77.0266) | 72.7 | 97.1 | **−25.1%** | −25.2% |
| JLN Stadium (28.5677,77.2434) | 52.2 | 135.9 | **−61.6%** | −61.6% |
| `/v2/city` (city surface) | mean 58.2 | 113.3 | **−48.6%** | −48.6% |

The "46% below the 10-year average" in `android-drive-report.md` was one
read's drift. Tonight the same surface would say **~49% below** (city
read) or **~34% below** (CP point). Live-mapped → never lies.
**Demo line: "about a third to a half below the typical October
hour"** — or show the app, which states the exact live figure.

`/v2/day` @CP: day_mean **74.4**, heavy **20:30→end ~93.9**, cleanest
**14:30–17:30 ~61.3**, `decisions` 3 plain-words rows (the `decisions:[]`
wart stays fixed).

## 6 · Week/forecast — MATCH, demo-window note

`/v2/outlook` @CP (`horizon_days:5`, `horizon_hours:106` served — the
served count drifts with time-of-day; code probes the full 121 h reach.
**Say "five days", not "120 hours"**):

| IST day | pm25 mid | band |
|---|---|---|
| Oct-7 today (partial) | 74.4 | Moderate |
| Oct-8 | 121.6 | Poor |
| Oct-9 | 164.9 | Very Poor |
| Oct-10 | 132.8 | Very Poor |
| Oct-11 (partial) | 136.5 | Very Poor |

Demo days Oct 8–11 are all Poor→Very Poor on tonight's read — the
"dirty air" pitch is easy to show; a "cleanest window" beat may be thin.
`/depart` (CP→GG, auto): now **22.9 µg** → best **20.1 @+8 h (−12%)**,
worst **44.9 @+23 h**. Landing's day-strip (`/today` climatology,
Oct h+8 ~111 at CP) and district chips are live-mapped; "Delhi today"
in the app reads the same `vs_now_pct` arithmetic verified in §5.

## 7 · Engine budget — MATCH

20 consecutive `POST /v2/plan` on the demo OD (CP→Gurugram), warm task:

| measure | value | doc claim | verdict |
|---|---|---|---|
| server `took_ms` | **p50 325 · p95 4,405 · min 306 · max 4,405** (n=20; the 4.4s outlier = first-hit-after-reprice) | "~56–660 ms warm; 2–8 s unseen OD; 20 s budget" | ✓ inside every bound |
| client wall (this box → NLB) | p50 1,989 · p95 5,859 ms | "under two seconds on the rehearsed trip" | ✓ server-side yes; wall adds ~1.5 s US→Mumbai transit |
| options | **24** (incl. `metro+walk` + GTFS Bus 460 — inside service hours at 08:30 IST) | "16–24, swings" | ✓ top of range |
| `smoke_modifier` echoed | **×1.10** | bz basis on wire | ✓ |
| `degraded` / `error` | none | honest-degrade machinery | ✓ all 20 calls 200 |

**Dose ladder this read** (demo OD, bz basis): car-AC **8.6–8.9** ·
car-open 15.5 · bike 19.6 · bus 22.4 · auto 25.3 · metro+walk 39.2 ·
GTFS bus 68.1 · cycle 125.7 · **walk 283.7** → spread **33.0×**
best-vs-best, **39.6×** slowest-vs-best — inside the documented
31–45× band. **Demo line: "about thirty-three times on this trip
tonight; the range all week is thirty-one to forty-five."**

## 8 · Headline framing — all live-mapped, no static hero numbers

`landing.html` (served build): every public numeral is a live wire read.

| element | source | renders now |
|---|---|---|
| `hnumV` hero numeral | `/v2/city.pm25_stats.mean` | **58.2 µg/m³** |
| `hnumT` felt line | `breath.cigarettes.mid` | "a day ≈ **2.6** cigarettes" (mid 836 µg; hi ≈6.2 cig in the sub-line) |
| `stnHero` | `/health.sources.stations.count` | **53** (static fallback text "54" is replaced at runtime) |
| `edgecount`/`pricedcount(2)` | `/health.routing` | 1.07 / 0.90 million |
| `dayNote` | `typical.vs_now_pct` | "now — live field **−49%** vs the typical hour" |
| boot strip numeral | `/v2/city.pm25_stats.mean` | 58.2, banded Moderate; honest "no live air reading" fallback exists |
| `skillLine` | `/v2/skill` | "missed … by **28.8 µg/m³** on average · 242 pairs" (h+0 3.9/89.2% → h+11 45.1/28.3%; coverage 33 h graded) |
| `whyLine` | `/v2/why` @CP | "the air is barely moving — …" live |
| districts | `/v2/districts` | 29 chips, all with live AQI tonight |
| grid | `/grid` | 484 cells ✓ |
| routeline/ladder/departline | user-driven `POST /v2/plan` + `/depart` | interactive-only, live |

Static text on the page is structural or artifact-true: "95.2% of 3,550
held-out station-hours inside ±2σ" (correct, cites the file), "AQI
sub-indices inverted to µg/m³" (true), "22 µg/m³-day ≈ 1 cig" (the
Berkeley Earth constant), "no profiles · k≥3" (true).
`/city` + `/community` pages: `hMean`/`hBand`/community totals all
live-fetched (`/v2/city`, `/community`, `/health`, `/reports`) — no
static numbers.

## 9 · Drift ledger (what moved since NUMBERS §2 was stamped ~23:30 UTC)

| figure | NUMBERS pin | prod now | flag |
|---|---|---|---|
| stations | 54 = 24 WAQI + 30 DPCC | **53** (same composition, one instrument aged out) | doc-by-one; say "~53/54" |
| model samples | 100 | **100** | ✓ |
| community | 22 obs / 14 contributors / 725.9 µg | **40 obs / 22 / 1,028.5 µg**, `obs_today:1` | stale — better direction; wire now `*_today` fields (e572f58 deployed), not `*_24h` |
| corridors | 12 active / 54 tracked / 39 trips | **12 / 55 / 40 trips** | drift |
| fires | 67/15 ×1.08 | **80/20 ×1.10** (verified vs FIRMS) | drift; carrying still false (wind E–SE) |
| `/v2/skill` | 210 pairs | **242**, h+0 3.9 → h+11 45.1, all `ok` | drift — say "242 pairs, all horizons graded" |
| breath mid | 576 µg ≈ 1.8 cig | **836 µg ≈ 2.65 cig** | drift within 550–1,099 |
| `/depart` | 23.6 → 45.5 worst / 21.3 best | 22.9 → 44.9 worst / 20.1 best (−12%) | drift |
| day windows | 19:30→end ~104 / 12:30–16:30 ~58 | **20:30→end ~93.9 / 14:30–17:30 ~61.3** | drift |
| outlook | Oct-7 ~75 / Oct-8 ~123 / Oct-9 ~159 | 74.4 / 121.6 / **164.9** / 132.8 / 136.5 | ✓ same story |
| horizon_hours | "120 h / 101 served" | **106 served** | say "5 days" |
| LOO | 46.1 / n=94 | **8.8 / n=70 — NEW artifact on the wire** | **see §4 — biggest flag** |
| build_sha | `ce01ec5c` | **`aee635eb`** | HEAD−17, mostly docs + observability (tripwires/token_via/XFF) |

## 10 · What a doc says that prod contradicts RIGHT NOW

1. **LOO 46.1/n=94** — ~14 surfaces (§4). Wire serves 8.8/n=70. The
   canonical `NUMBERS.md` §1 artifact row is itself stale.
2. **"22 observations / 14 contributors"** — `NUMBERS.md`, `demo-script`,
   `judge-answers-v3` §1 rehearsed line. Wire says 40/22. The
   citizen-layer attack answer is now *stronger* than rehearsed.
3. **Station count 54** — many docs. Wire says 53. Honest churn; the
   phrasing fix is "~53 instruments (54 when both feeds are full)".
4. **`obs_24h`-era field names** — wire is `obs_today`/`km_today`/
   `dose_ug_today`/`avoided_ug_today` since `e572f58` deployed. Any
   judge-facing line quoting `obs_24h` is a field-name lie-by-omission.
5. **`verify_numbers.sh` stations check** — the {54,24} whitelist will
   false-flag the live 53 at T-45. Accept a range (≥24 with dpcc feeds
   ok) or re-pin on the morning.
6. **"46% below the 10-year average"** — a stamped report figure, fine
   as a report; do not rehearse it as the number — tonight it's −34%
   at CP / −49% city-wide. The surface states the live figure.

No fabrication, no stale-flag lie, no broken wire observed this pass.
Every contradiction above is docs-behind-prod or point-in-time drift —
nothing prod says is untrue of itself.
