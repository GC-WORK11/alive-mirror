# Judge QA v2 — the dosimeter-epoch attack set, every answer proven live

The hostile-engineer set against the CURRENT product (lungs' ledger,
day arc, recorded-vs-forecast archive, k≥3 community, smoke modifier,
sideloaded APK). v1's `judges-faq.md` stays valid for the route-first
questions; this sheet owns the dosimeter-epoch attacks.

Every figure below was read off `http://65.2.28.40` on **2026-10-06
02:55–03:15 UTC** (08:25–08:45 IST), build `9af96710`, breathing-zone
dose basis, `smoke_modifier` **1.11** on this pass (it was 1.09 at the
v1 pass — the drift is the proof it is computed, not hard-coded).
Re-run `scripts/verify_numbers.sh` at T-45; quote "about ~N" on
anything marked drift.

Legend: **Honest answer** = the true answer, including the part that
hurts. **Live proof** = the artifact a judge can re-run right now.
**Stage** = the two sentences to say out loud.

---

## 1. "Your timeline is fakeable — the day arc is a JSON on the phone"

**Honest answer:** Partly true at the file level — `daylog.json` is a
local-first file, and any local-first file can be edited by its owner.
The defence is not that the file is tamper-proof; it is that *the
numbers inside it are externally checkable*. Every arc sample is a real
`GET /aqi` read of the served field at that place and IST hour, and the
server publishes what it served — hourly, append-only, to S3 — so a
fabricated arc would have to match a public record it can't edit.

**Live proof:**

- The archive itself:
  ```bash
  curl -s http://65.2.28.40/v2/archive | python3 -c \
    'import json,sys; d=json.load(sys.stdin); print(d["coverage"], d["archive"], d["storage"])'
  # recorded hours 0–8 today, 0 gaps, 9/9 hours carry the forecast the
  # api was serving at capture time; 13 snapshots since Oct-5 20:00 IST;
  # storage: bucket alive108-air, prefix archive/ — durable, off-box,
  # one file per IST hour named by the hour it RECORDS (not when written)
  ```
- `server/archive.py:24-52` — snapshots record ONLY the served field;
  "a field serving nothing writes NO snapshot: the hour stays a gap";
  each blob carries `basis:"recorded"`. Yesterday's archive had an
  honest gap at hour 4 — the mechanism leaves holes, which is what
  unfakeable means in practice.
- `Mobile/src/store/daylog.ts:1-14` — the file's own docstring:
  "each one a real GET /aqi read at the position the OS reports… What
  it never does: upload." `recordSample` (~line 100) dedupes <8 min /
  ~450 m; `GAP_INTERP_MS` (line ~44) = 45 min — a sample can't stand
  for a longer hole; the gap shows as a gap.
- The apk-populated drive dumped the real file:
  `docs/lanes/apk-populated-report.md` "Honest seed" — 9 real `/aqi`
  reads (4 centroid fallbacks before GNSS, 5 at real route positions
  28.6129,77.2295 → 28.5490,77.2523 with amb rising 54.9→84.3 µg/m³),
  `consent.json` `sharing:"off"`, pcap shows zero trip/report POSTs.
  Nothing was hand-edited; the doc says so and shows the raw file
  contents.
- `docs/plan/app-demo-seed.md:78` — the demo-state doc explicitly
  forbids the cheat: "Do NOT hand-seed `daylog.json` — dedupe and the
  21-day keep window make fabricated rows fragile."

**Stage:** "The file is local-first, so sure — *I* could edit my own
phone's file. What I can't edit is what the server served: the field is
snapshotted hourly into S3, append-only, gaps and all. Cross-check any
arc sample against that hour's recorded field — a faked number
contradicts a public record. And our own demo doc forbids seeding —
the populated state you saw was earned live on camera."

## 2. "Why is 33× believable? That number looks cooked"

**Honest answer:** The gap is physics, not routing: the walker spends
~10× longer in the field, at ~2.4× the breathing-zone concentration,
breathing ~1.4× harder. 2.36 × 10.0 × 1.4 ≈ 33. It moves with the
field — the range this week is ~31–45× — which is why we quote a band,
not a constant.

**Live proof** (`POST /v2/plan` CP→Gurugram, tonight, took_ms 5386,
24 options):

```
walk:    avg_conc 139.7 µg/m³ breathing-zone · 17071 s (284.5 min)
         · VE 14.0 L/min → dose.mid 556.6 µg (band 238.7–874.5)
car-AC:  avg_conc  59.1 µg/m³ · 1703 s (28.4 min)
         · VE 10.0 L/min → dose.mid 16.8 µg (band 7.2–26.4)

556.6 / 16.8 = 33.1×
decomposition: 139.7/59.1 = 2.36× conc (microenv 1.30/0.55)
             × 284.5/28.4 = 10.0× time
             × 14.0/10.0 = 1.4× ventilation  →  33.0× — closes.
```

The factors are published Delhi measurements, not tuning knobs:
`server/exposure.py:51-95` MICROENV (walk 1.30 vs car-AC 0.55 —
Sci. Total Environ. 2021 six-mode in-vehicle means; walk is *already
discounted* ~7% because the kriged field carries roadside blend), and
`exposure.py:121-145` VENTILATION_LPM (seated 10.0, walking 14.0,
cycling 22.0 — Zuurbier 2009 / EPA EFH). Every option on the wire
carries `dose.{lo,mid,hi,avg_conc_ugm3,confidence}` and
`dose.basis:"est."` — you can recompute each one by hand.

**Stage:** "Same road, same minute — only the mode changes. The walker
breathes the plume 2.4 times harder per minute, for 10 times as long,
at 1.4 times the ventilation rate. That's thirty-three. It's not a
routing miracle — it's multiplication. Here's the curl, run it."

## 3. "The field is interpolated — where's the calibration?"

**Honest answer:** In two places, both public. On the wire: every
`/aqi` response carries its leave-one-out calibration block — the error
between stations, measured by holding each instrument out and reading
the field at its position. On disk: a 3,550-pair held-out validation
against the OpenAQ archive, including the per-station table that shows
where we're *bad*.

**Live proof:**

```bash
curl -s "http://65.2.28.40/aqi?lat=28.6315&lon=77.2167" | python3 -c \
  'import json,sys; print(json.load(sys.stdin)["calibration"])'
# {"method":"leave-one-out over live OpenAQ instrument readings",
#  "n_stations":94, "mae_ug":46.1, "rmse_ug":71.9,
#  "median_abs_pct":56.0, "mean_bias_ug":0.3,
#  "note":"error between stations — at a station the field reads the
#          instrument itself"}
```

- `server/data/field_validation.md` — 3,550 station-hours across 85
  stations vs the OpenAQ S3 archive: MAE 22.0, RMSE 29.3, bias +15.5
  (+51.6%); measured ±2σ coverage **95.2% vs 95.4% nominal** (the σ the
  API serves is inflated by `SIGMA_CAL`, a factor *measured on this
  window* — `airfield.py`). The file publishes the per-station bias
  table — worst rows are openly listed (IGNOU +598%, Cantonment +385%)
  — and says the quiet part out loud: "IDW-only fallback… MAE 21.8 —
  kriging does not beat IDW on this window."
- `server/data/field_calibration.json` — the same LOO block the wire
  serves.

**Stage:** "Two answers. Live: the calibration rides on every response
— LOO over 94 instruments, mean bias +0.3 µg. Offline: 3,550 held-out
station-hours, ±2σ coverage measured 95.2 against a nominal 95.4 — and
the file shows you the stations where we're worst, not just the mean.
Calibration that's afraid to show its residuals isn't calibration."

## 4. "k≥3 with 14 contributors means your corridors are empty"

**Honest answer:** Yes — that is the gate working at real scale, and we
show the suppression counter instead of padding the map. Tonight:
39 donated trips in 7 days, 14 contributors, and **12 of 54** tracked
corridor cells publish — 42 are suppressed for lacking ≥3 distinct
devices in 72 h. An app with 14 contributors *should* have a mostly
empty map; a full one would mean we seeded it.

**Live proof:**

```bash
curl -s http://65.2.28.40/v2/city/moves
#   min_k:3 · n_trips:39 (7d) · corridors: {"active":12,"tracked":54}
#   mode_share_suppressed_trips: 0
curl -s http://65.2.28.40/community
#   obs_total:22 · contributors:14 · latest_obs_age_min:342
#   top_corridors devices: [6,4,4,3,4] — every published row ≥3
#   basis: "corridor cells published only with >=3 distinct devices in
#          72 h; no per-trip records exist at rest"
```

- `server/community.py:89-90` — `_K_MIN_DEVICES = 3`,
  `_CELL_WINDOW_S = 72*3600`; `corridors()` publishes only above both
  thresholds. `community.py:116+` `_fold()` — the only write path —
  writes straight into cell/hour/day counters; no per-trip row exists
  at rest (`test_no_per_trip_rows_can_exist_at_rest` in the suite).
- The privacy side of the same question: `/v2/ledger` answers
  `422 device token required` with no `X-Device-Token` — per-device
  history is readable only by the holder of the raw token, which is
  hashed before it touches any store (`v2/ledger.py:19-28`).

**Stage:** "Correct — 42 of 54 corridors are suppressed tonight, and
the counter that says so is public. Seeded data wouldn't have a
suppression mechanism at all. This is what honest k-anonymity looks
like at 14 users: mostly empty."

## 5. "The history sparkline is seeded"

**Honest answer:** Two different sparklines, neither seeded. The
morning card's 12-hour line is the *forecast* surface — 12 parallel
`GET /grid?h=0..11` reads, pulled live when the card opens; a failed
hour renders as a literal hole in the stroke. The "vs typical" curve
behind it is the decade climatology — 125 stations, 9.04M OpenAQ
measurements, pulled from a public S3 archive (the source string is on
`/health.history`). The phone-side day arc and week dots are built
only from real foreground samples and real completed trips (see Q1).

**Live proof:**

```bash
curl -s "http://65.2.28.40/grid?cells=8&param=pm2_5&h=0" | head -c 400
#   GeoJSON cells with real pm25+conf per cell — the sparkline's strokes
curl -s "http://65.2.28.40/today?lat=28.6315&lon=77.2167"
#   {"month":10, "hours_ist":[99.8,108.5,…,102.1],
#    "source":"openaq-s3-climatology"} — 24 decade-medians
curl -s http://65.2.28.40/health | python3 -c 'import json,sys;print(json.load(sys.stdin)["history"])'
#   source: openaq-data-archive s3://openaq-data-archive/records/csv.gz
#   (public, measurements only) · 125 stations · pm25/pm10/no2
```

- `Mobile/src/api/dayfield.ts:1-11` — "There is no single per-point day
  endpoint, so we fetch the h-series in parallel… Honesty contract: a
  failed hour is a hole (null), not a guess; a point outside the krige
  window gets `outside` — never a neighbouring cell's number relabelled
  as theirs."
- `useShellFlow.ts:~361` — "only a COMPLETED trip is logged (claims
  audit — logging on option view fabricated trips + inflated every
  avoided-µg total)" — the ledger can't be fed by browsing options.
- The demo-seed doc (Q1) is the procedure for earning a real populated
  state in ~45–75 min of real use; the apk-populated report shows the
  resulting raw file.

**Stage:** "The sparkline is twelve live forecast reads — re-run them
now and watch it move at the next 15-minute reprice. The typical line
is a public OpenAQ archive product. And the populated phone state was
filmed being earned — the lane report publishes the raw daylog."

## 6. "Why should I trust modifier 1.09?" — reads 1.11 tonight

**Honest answer:** Don't trust it — recompute it. It is a bounded,
documented heuristic, computed from NASA FIRMS detections in the NW
burn belt, downscaled when the wind isn't advecting the plume toward
Delhi, applied to the *model prior only* — live stations then correct
it wherever they measure. Tonight's wire lets you re-derive the
published value exactly.

**Live proof** (the math closes to the decimal):

```bash
curl -s "http://65.2.28.40/aqi?lat=28.6315&lon=77.2167" | python3 -c \
  'import json,sys; print(json.load(sys.stdin)["fire"])'
# {"status":"live","source":"firms-public-csv","fires":89,
#  "belt_fires":22,"belt_frp_mw":76.8,"wind_deg":102,
#  "modifier":1.11,"age_s":3759}
```

```
fire_index   = belt_fires / BASELINE_FIRES_48H = 22/160      = 0.1375
raw modifier = 1 + 0.1375 × (MAX_MODIFIER−1)   = 1 + 0.1375×2.75 = 1.378
wind 102° — NOT in the NW quadrant (270–360°) → ×0.3 downscale:
modifier     = 1 + 0.378×0.3 = 1.113 → rounds to 1.11 — the wire value.
```

- `server/fires.py:38-39` — `BASELINE_FIRES_48H = 160` (documented
  ~80/day seasonal baseline × 48 h CSV window), `MAX_MODIFIER = 3.75`
  (episode-day share ratio ~50–75% vs ~15–20% typical — cited to npj
  Clim. Atmos. Sci. 2025 / ES&T 2020 in the module docstring).
- `server/fires.py:187-201` — the modifier itself; the ×0.3 non-NW
  downscale is a "documented assumption, not magic" in the code comment.
- `server/airindex.py:838-854` — applied to model points BEFORE
  kriging: stations correct it where they exist.
- `server/airindex.py:10-17` — the module header says it plainly:
  the modifier hits the prior; stations then re-fit residuals.
- `/v2/why` tonight is honest about it: `fires…carrying:false` — 22
  belt fires are seen but NOT claimed as a driver because wind (102°)
  is outside the NW gate.

**Stage:** "It's not a trust-me constant — it's a formula you can redo
on stage: 22 belt fires out of a documented 160-fire seasonal window
gives 1.38 raw, today's wind is out of the southeast so it downscales
to 1.11, and it only touches the model prior — the 24 live instruments
then overrule it where they measure. Yesterday it read 1.09. A
hard-coded number doesn't drift."

## 7. "Show me the model beats persistence"

**Honest answer: it doesn't — not on the wire, and not tonight.** The
scorecard publishes model-vs-recorded skill (`/v2/skill`); the promised
"beat the persistence baseline" criterion in `docs/05-validation-impact.md`
(§temporal skill) is **not yet a served number**. We computed the
baseline from the archive just now: over the 8 recorded IST hours this
morning, simple hour-ago persistence on the same emit lattice gives
per-cell MAE ≈ 5.4 µg/m³ at h+1 — the served forecast's h+1 MAE is
12.8. Persistence wins every horizon tonight:

| horizon | served model MAE | persistence MAE | n pairs |
|---|---|---|---|
| h+1 | 12.8 | 5.4 | 8 |
| h+2 | 21.9 | 10.1 | 7 |
| h+3 | 32.0 | 14.9 | 6 |
| h+4 | 40.4 | 19.2 | 5 |
| h+5 | 48.6 | 21.7 | 4 |

(Computed from `GET /v2/archive` — recorded cells of hour t vs hour
t−h, matched-cell MAE; the command is in the lane report. The window is
8 hours of a smooth overnight ramp — persistence's best regime.)

What the model actually buys today: calibrated bands (h+1 band-hit
73.3% cell / 77.8% hour on the wire), a 5-day horizon persistence can't
make at all (`/v2/outlook`), spatial structure persistence can't carry
(the field isn't spatially uniform), and driver attribution
(`/v2/why`). **Demo-morning risk:** if a judge asks "does it beat
persistence on RMSE" the honest sentence is "not yet on tonight's
window — the scoreboard is model-vs-recorded; the persistence bar is
promised in the validation doc and isn't wired in." That answer is
defensible; claiming the win is not.

**Stage:** "Honest answer: the scoreboard grades us against what was
recorded — that's public and unforgiving, and tonight it says our h+1
misses by ~13 µg where last-hour-as-forecast would miss by ~5 in a
stable ramp. Persistence is nearly unbeatable at short horizons in
stable weather; our case is bands, horizon, and regimes that change —
and we're not claiming a win we haven't shown. The baseline bake-off is
the gap we'd close next, and the archive already stores everything
needed to compute it."

## 8. "What breaks when WAQI dies?"

**Honest answer:** Layered degradation, no fabrication — and a real
caveat: **WAQI is the only live stations feed**. Every keyless
alternative was probed from inside the prod VPC and found dead or fake
(`docs/plan/handoff.md` line ~54: OpenAQ key 401, data.gov.in refused
even on India egress, CPCB dashboard timeout, SAFAR TLS-hangs, the
`demo` token silently serves *Shanghai* — rejected). So when WAQI
goes, stations go; what remains is the model prior and the honesty
markers.

**What happens, in order** (all in code):

1. `server/ingest_waqi.py:336,371` — a dead map/feed path returns
   `status:"unavailable: <reason>"` with empty `stations`/`obs`.
   Partial failure is partial: per-feed errors are collected, the
   stations that answered still land.
2. `server/airindex.py:10-14` — stations are "optional — the field
   builds without it and the provenance block says so explicitly,
   never silently." Zero survivors → no residuals → the field IS the
   fire-adjusted model prior; per-cell `src:"model"`, distance-grown σ
   → **bands widen, `confidence` drops** (`exposure.py:367-374` tiers).
3. `server/airfield.py:47,1008-1042` — `serving` flips `live`→
   `snapshot` (last good build serves rather than nothing);
   `stale:true` after `stale_after_s` 2700 s; `/health.sources.
   stations.up:false` names the feed dead.
4. `/v2/archive` keeps recording — including `station_readings:0` —
   so the outage itself is visible in the record.
5. Subtle degradation worth saying aloud: with stations gone, the
   "recorded" side of `/v2/skill` degrades toward model-vs-model —
   the self-grade loses its ground truth. The drift-watch lane's
   anomaly list (`docs/lanes/field-drift-watch.md`) already treats a
   sources-drop as a flaggable event.

**Stage:** "The field keeps serving — on the prior alone, with wider
bands and `confidence:low`, while `/health` names WAQI dead and
`serving:snapshot` covers the gap. What breaks is the truth layer, not
the app — and the wire says so instead of hiding it. What we'd never
do is silently pad the station count."

## 9. "Your cigarette math is sensationalism"

**Honest answer:** The constant is a published perception unit, and the
product labels it an estimate everywhere it appears — but the audit
keeps receipts: `docs/claims-audit.md` tracks every cig-eq surface,
flags its own violations (⚠/✗ rows exist and say so), and the product
deliberately refuses the worse version — no "years of life lost", no
mortality claims, ever.

**Live proof:**

- `server/exposure.py:169-171,194-209` — `CIG_UG = 316` with the basis
  in code: Berkeley Earth / Muller & Muller — 22 µg/m³ ambient over a
  day ≈ 1 cigarette at ~14.4 m³ inhaled; `cigs_band()` returns lo/mid/hi
  and `basis:"est."`, never a bare point.
- On the wire tonight: `GET /v2/city` `breath` block — day of breathing
  mid 1297 µg ≈ **4.11 cig** with lo 0.0 / hi 9.66 and the basis string
  "field-weighted mean over the NCR sample lattice… Berkeley Earth:
  22 µg/m³-day ≈ 1 cigarette" — the citation rides the payload.
- `docs/12-lung-ledger.md:11-18` — the ledger's version: cig-eq =
  `todayUg/316`; the daily budget is `todayUg/216` (WHO 15 µg/m³ ×
  14.4 m³) and is labelled "~216 µg daily budget, never 'safe'".
- `docs/26-honest-impact.md:60` — the sanctioned-claims row: "the 22
  µg/m³-for-a-day ≈ 1 cig equivalence is the published Muller/Muller
  estimate, used by Berkeley Earth; we cite it in-app."
- The kill list is real: `claims-audit.md` ✗ rows (e.g. "dose dodged /
  cigarettes not smoked" as achieved impact) are marked for removal —
  counterfactuals can't be claimed as savings.

**Stage:** "It's the Muller-and-Muller equivalence Berkeley Earth
publishes — a perception unit, marked 'est.' with its own band, next to
a WHO-budget line that's explicitly 'not a medical threshold'. We audit
our own strings for exactly this charge — the audit file lists where we
were out of line and what changed. Sensationalism would be 'days of
life lost'; we refuse to compute that."

## 10. "The APK is sideloaded — how do I know it's the same code?"

**Honest answer:** Provenance, not cryptographic attestation — and we
say so. The demo APK is a release build made *from a commit of this
repo* (`alive108-0a26f5a.apk` is named after `base/v2@0a26f5a`), the
build command is published, the bundle inside the APK was grepped to
prove it targets this API, and the whole thing was driven under a
packet capture — so the app's wire behavior is the same wire you're
curling. A debug-signed APK can't prove code identity by signature;
the proof is reproducibility — rebuild at the SHA and compare.

**Live proof / artifacts:**

- `docs/lanes/apk-drive-v5-report.md:5-10` — build recipe:
  `EXPO_PUBLIC_API_URL=http://65.2.28.40 ./gradlew assembleRelease
  -x lint` on a clean checkout → 137.7 MB, 4 ABIs, debug-signed,
  `usesCleartextTraffic` — and `grep -a` on `index.android.bundle`
  verified the bundled JS contains `65.2.28.40`. The app you curl is
  literally the API the APK talks to.
- `docs/lanes/apk-populated-report.md` — full-session pcap: GETs +
  `POST /v2/plan` only; zero `/v2/trip`, `/observe`, `/report` POSTs;
  consent-off state persisted on disk. The app's runtime behavior is
  inspectable from outside — nothing hidden to differ from the source.
- Reproducibility path: `base/v2@0a26f5a` + the published command
  rebuilds the artifact; the lane report names the superseded build
  (`609a6ef`) and what it predates (`3711ccd` arrival gate, `0fdd597`
  dedupe-removal) — version deltas are documented, not vibed.
- Honest limits: no in-app build-SHA screen exists (the SHA rides the
  filename), Play signing is absent by definition, and "same code" is
  proven by rebuild+inspect, not by a signature chain. If a judge wants
  stronger: the delta question that matters — "does it behave like the
  repo" — is answerable from the pcap + the surface tests (11/11 PASS
  lane report) already published.

**Stage:** "Sideloaded because it's a debug-signed release APK — the
honest answer is provenance plus reproduction: the filename is the git
SHA it was built from, the build command is in the lane report, the
bundle was grepped to prove it points at this API, and its entire
network life is a published packet capture. If you want stronger proof,
rebuild at the SHA — it's one gradle command."

---

## Also-armed (hostile extras on the same surfaces)

- **"Your avoided-µg ledger is self-reported counterfactual."** True —
  and labeled: per-trip "avoided" is worst-offered − chosen, `basis:
  "est."`; the community aggregate says "est. from donated trips" on
  the wire (`/community` `avg_dose_basis`). Claims-audit killed the
  stronger wording ("cigarettes not smoked" as achievement is a ✗ row).
  What *is* measured: dose per completed trip on the served field.
- **"95.2% at ±2σ just means you inflated σ until it fit."** Inflating
  σ to measured coverage IS calibration — the honest part is that
  `field_validation.md` publishes the per-station table where it fails
  (worst station +598% bias), states "kriging does not beat IDW on this
  window", and the ±1σ/±3σ misses (53.2%/99.1% vs 68.3%/99.7%) are in
  the same table, not hidden.
- **"The demo is an emulator — GNSS was faked."** Half true: the
  recording rig drives `adb emu geo fix` — position fixes are scripted
  on the emulator, documented in `app-demo-seed.md` and the drive
  reports. Everything the app *did with* those positions was real:
  real `/aqi` reads at those coordinates, real field, real dose math —
  and the ambient poll fell back to the Delhi centroid honestly when
  last-known was null (the populated report shows those 4 centroid
  reads explicitly). The deception class would be fake *air numbers*;
  there are none.
- **"Admin console is a prop."** `/admin` serves a real engine-room
  surface (200, ~125 KB live HTML); the data APIs under it are
  token-gated by design — nothing judge-facing depends on them.
- **"You show a GRAP stage — that's the government's call, not
  yours."** *(shipped 2026-10-06, `83d47de`)* — agreed, and the wire
  says so on every payload: `note: "computed from today's air, not the
  official CAQM declaration"`. The field is named `equivalent_stage`,
  never "GRAP stage"; computed from our own served PM2.5 through the
  CPCB national-AQI table and CAQM trigger bands. Live now: `/v2/day`
  @CP `{stage: 1, aqi: 285, basis: "cpcb aqi of day_mean_pm25"}`;
  `/v2/city` `{stage: 0, aqi: 196, basis: "cpcb aqi of
  pm25_stats.mean"}` — different stages, different bases, each named
  on the wire. One PM2.5→AQI formula in `districts.py` drives both
  surfaces (a second formula was rejected in code so surfaces can't
  disagree). No live CAQM feed — if stage II is declared tomorrow, our
  surface still says what the air maps to, and says that's all it is.
  Say it: "a lens, not a ruling."

---

## Demo-morning risk register

| risk | severity | answer status |
|---|---|---|
| Judge asks "beat persistence?" | **high** | Honest "not yet" — §7. Persistence wins tonight's window at every horizon; say it before they compute it. Offer: the archive stores everything needed; it is the next scoreboard row. |
| Judge demands proof the on-device file isn't editable | medium | It IS editable — reframe to "inputs are cross-checkable against the public archive" (§1). There is no signature on `daylog.json`. |
| WAQI dies during the demo | medium | Station layer goes; field continues on prior+modifier with honest `stale`/`up:false`/`station_readings:0` markers (§8). "Two dozen instruments" line must be dropped live if it happens — watch `/health.sources.stations` at T-45. |
| APK attestation push | low-med | Provenance + reproducibility is the ceiling (§10); no Play signature exists to show. Don't overclaim. |
| Numbers drift between now and stage | expected | smoke_modifier was 1.09→1.11 overnight; dose ladder 33.1×↔week range 31–45×; options count swings ~19–24. Quote "~"/"about"; `verify_numbers.sh` at T-45. |
| `/v2/skill` grows past tonight's table | benign | pairs accumulate from Oct-5 20:00 IST; h≥8 may un-thin. Re-read before stage. |
