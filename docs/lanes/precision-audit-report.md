# Precision-audit report — every rendered number's precision chain

Lane: `precision-audit`. Owner's law, verbatim: *"not a single fucking number
should be hardcoded, assumed, or random — exact to the very meter, detailed,
brutally honest."* Daycount proved no rendered number is **fake**; this lane
asks whether each is as **exact** as its data allows and whether its display
implies false precision or hides real precision. Base: `base/v2` @ `e3a1183`
(own changes land on top).

Gates run after the fixes: `server` pytest **1262 passed / 5 skipped**
(PYTHONPATH=core/build312 — alive_core rebuilt with Eigen, krige+dose parity
included); Mobile `tsc --noEmit` clean; `expo lint` clean; node runners
store 16 / nav 76 / api 17 / offline 16 / search 8 — **133/0 fail**.

## What got fixed

**1. `segment_samples` distance mis-attribution (the real numeric bug).**
The dose engine emits one sample per ~250 m of route and apportions each
sample `duration_s * frac` + `dist_m` — but both were computed from `seg`
(the leg that crossed the step) instead of `carry` (all meters accumulated
since the last emission). Net effect: dose-time and distance were credited
to wherever geometry happened to be vertex-dense. On a worked 9.76 km
mixed-density route (200 short legs + one ~2 km leg) `dist_km` reported
3.09 km and the long-leg sample carried 64.6 % of dose-time instead of its
true 21.6 %. `avg_conc_ugm3`, `implied_speed_kmh` (the `>150 km/h`
plausibility gate), and `/v2/strip`'s per-sample `dist_m` + road-attribution
all inherit the bug. Fixed in all three implementations so the 1e-9 parity
contract keeps holding: `server/exposure.py`, `server/alive_core_ref.py`,
`server/core/src/field.cpp`. Verified after fix: all three emit identical
rows; Σdist_m = route length (9 763 m), Σseconds = duration exactly.

**2. `nearest_sample_km` flat-earth longitude error.** The live-serving
branch used `* 111.0` on BOTH axes; `_snap_nearest`, krige.py and
airindex.py all use `_KX = 99.4` km/°lon at 28.6 N — the caption distance
overstated E-W separation ~13 %. Now `hypot(dlat*110.6, dlon*99.4)`,
matching the snapshot path. Verified: a 0.2°-due-west sample reads 19.88 km
(old code would have said 22.2 km).

**3. "Nearest live monitor" now means a monitor.** The caption
(`homeAirMeta`, `settingsNearestInstrument`) claimed a *live monitor* but
rendered `nearest_sample_km` — the nearest **field sample**, which includes
unnamed CAMS model fill points and, on snapshot serving, the nearest kriged
cell centre. New `FIELD.nearest_station_km` returns km to the nearest
**named** live instrument (`_stations_live` — the same (lat,lon,name) rows
`status()` serves as `stations`); on snapshot serving with no live feed it
falls back to the cell's own build-time `nearest_station_km`; **inf when no
instrument is live → wire null → no monitor claimed**. Served on `/aqi` as
`nearest_station_km` (Bridge contract updated); the client prefers it and
falls back to `nearest_sample_km` only when the key is absent entirely
(pre-update servers).

**4. `Infinity` in JSON.** `round(inf, 1)` = `inf` → `json.dumps` emits the
spec-invalid literal `Infinity`, which kills a RN `JSON.parse` of the whole
poll. Both distance keys now serialize as `null` when non-finite.

**5. Location captions name the locality (owner's repeated ask).** The hero
caption now reads **"read near Karol Bagh · nearest live monitor ~1.8 km
away"** when the gazetteer can honestly name the locality: new
`t0.localityAt()` wraps `areaNear()` (the same weight-minus-distance rule
search subtitles use, ≤1.4 km reach) — real names like "Karol Bagh",
"Shekhpur" (verified against the shipped index in `locality.test.ts`), and
`null` — never a guess — when no locality is in reach or the index isn't
built. Four caption states, all honest: locality+monitor, locality alone
("no live monitors feeding the field right now"), no-locality+monitor
(legacy text), neither (model-only disclosure). Hindi keys land with parity
(`homeAirMetaPlace`/`homeAirPlaceModel`/`homeAirModel`).

**6. Display-precision unifications.**
- `settingsNearestInstrument` was `nearestKm < 1 ? toFixed(1) : Math.round`
  — a 4.2 km instrument printed "~4 km". Now always `toFixed(1)` (0.1 km =
  the wire's own precision).
- `DayStrip` "lightest hour" line used `Math.round(dose_mid)` while every
  other dose surface uses `doseUgRound` (<10 µg keeps a decimal). Now
  `doseUgRound` on both render paths (a 4.4 µg hour no longer prints "4").
- `daylog.recordSample`'s dedupe comment claimed "~450 m"; the gate is
  `dlat + dlon < 0.008°` ≈ **0.9 km** N-S / ~0.6 km diagonal. Comment fixed
  (it under-documented a real precision rule 2×).

## Audited and verified honest (no change needed)

**µg/m³ chain.** `FIELD.value` → `pm25 = round(v*mod, 1)`, `pm25_ambient =
round(v, 1)` — the wire keeps 0.1 µg while the kriged field carries
σ ≈ ±40 %; the hero then shows `Math.round` whole µg — the right display
precision for the field's real uncertainty (a second decimal would be the
false-precision crime). `us_aqi` = rounded int over per-species EPA
sub-indices at *ambient* values — correct convention. CPCB bands: client
`PM25_BREAKS [30,60,90,120,250]` and server `_CPCB_PM25` breakpoint table
match Table 3.1 exactly (server interpolates linearly inside bands —
correct; boundary `v > break` lands 30.0 in Good per the 0–30 band
convention). **No dose float drift**: `daylog.reconstructDay` rebuilds the
day from scratch each render (Σ trapezoid + trip doses, one final round) —
no running accumulator to drift.

**Percentages.** `depart`'s `pct_less_vs_now` = `round(100*(1-best/now))`
vs. the *now* slot only (deploy-8 fix holds — client reads it verbatim via
`departSavedPct`, never recomputes; the legacy misnamed `ug_saved_vs_now`
alias carries the same value). `dose_vs_best_pct` = `(e−best)/best` —
denominator named correctly (served, not rendered client-side).
CompareSheet felt line: `d.mid/minDose` vs the lightest option, named
correctly; below 2× it degrades to an absolute `+N µg` gap — honest.
`refBudget` = `ug/budgetUg` vs the WHO-scaled profile budget. `vs_now_pct`
= `(v−median)/median` vs the climatology median, rendered as `N % below/
above typical` — right base. `coverage` shows only when <99.9 % — no false
"100 %".

**Time.** `arrivalLabel`/`clock` = `Date.now() + durationMin*60_000` in the
app's single 12h convention (`clockLabel`/`wireClockLabel` for server
"HH:MM IST" strings — the timezone conversion is real, not offset-fudged).
`fieldAgeLine` floors `age_s/60` (conservative — understates rather than
overstates age); the freshness chip re-ticks on each 60 s poll.
`hourLabel`/`+Nh` are integer horizons — honest.

**Distances elsewhere.** Trip/route km = `round(osrm_distance/1000, 1)` —
routed metres, 0.1 km display, honest. NavChrome's `distToStr` (10 m steps
under 950 m, else 0.1 km) matches what a driver can read. SearchScreen
`fmtDist` rounds to 50 m / 0.1 km / 1 km by scale — honest ladder.
`landing.html` "cell fade = distance to the nearest station" reads the
cell's real `nearest_station_km`; `city.html` fieldmeta calls
`nearest_sample_km` the "nearest map square" — literally what it is.

**False-precision sweep.** `cigLine` renders the cigarette fraction to
2 dp under 1 cigarette (0.04 cigs stays meaningful) and the band collapse
(`bandTxt`) suppresses a "0–0" band. `fmtKg` 2 dp under 0.1 kg. No
3-decimal µg anywhere.

## Catalogued — structural / not fixed here

- **Snapshot `nearest_station_km` fallback is cell-centric**: when the live
  feed is dark, it reports the cell's build-time distance-to-station from
  the *cell centre*, up to ~1.7 km slop vs the user's point. The number is
  real; its precision claim is bounded by cell size. (Display already says
  "~".)
- **`airSrc` stays "live" when all stations are dark** — the field is then
  model-only (debias can't run). The new model-only caption discloses this;
  renaming the src tier itself is a contract change for another lane.
- **`fieldAgeLine` floors while `howWe_fieldAge` rounds** — ±30 s display
  wobble on "N min old", both defensible; left as-is (unify later if the
  owner cares).
- **Static age between polls**: `howWe_fieldAge`/hero age reflect the value
  at poll time and tick only on poll/re-render (≤60 s staleness of the
  staleness number itself).
- **`vs_now_pct` == 0 renders "0 % above typical"** (sign test `< 0`) —
  "at typical" would be honest; cosmetic edge.
- **`coveredMin` adds min(60, trips×15)** heuristic coverage credit for
  trip-only time — labelled estimate, not measurement.
- **`vehicle durations`** are `MODE_SPEED_KMH`/`VEHICLE_TIME_FACTOR`
  estimates and are served as `duration_model="estimated"` — honest
  disclosure already; real traffic is out of scope by design.

## Wire/API notes for other lanes

`/aqi` now carries `nearest_station_km` (null when no live instrument).
`nearest_sample_km` is unchanged in meaning (evidence density incl. model
points — confidence tiers still use it). Web surfaces reading
`nearest_sample_km` keep working; any new "monitor" copy should read
`nearest_station_km` only.

Verify-on-sim: hero caption → locality name + station km; dose counters →
unchanged totals (the segment fix redistributes *within* a trip, total dose
holds where the field is flat).

## Sim verification (iPhone 17 sim, EDD9B083, 8:28 pm IST, prod-backed)

Device GPS pinned at 28.6517, 77.1907 (Karol Bagh metro). Home screen
shows — screenshot `precision-audit-sim-home.png`:

- **"read near Karol Bagh · nearest live monitor ~2.1 km away"** —
  `localityAt` resolved the locality name from the bundled gazetteer
  (no network, exact for the pinned coords). km came from prod
  `nearest_sample_km=2.1` via the field fallback — `nearest_station_km`
  serves `null` until this branch deploys.
- **"same air = AQI 138 on other apps"** — prod `us_aqi=138` for the same
  coords; EPA breakpoint math confirmed (35.5–55.4 band → 101–150).
- **"3.4× the WHO daily limit"** — 51.3 / 15 = 3.42.
- **"air reading · 2 min old"**, fires line "27 fires … up from 16 over
  ~5.7h … clearing at ~27%" — all live-server-derived, `~` markers present
  on every estimate.

Hero read 51 µg/m³ while prod `/aqi` returned 57.6 for the same coords a
minute later — live field drift between polls, not a display error.

### Build notes (macOS VM)

- `xcodebuild` initially failed in the EXConstants script phase:
  `expo-build-properties` was in package.json but missing from
  node_modules (a stale install predating a lane's package.json change).
  `npm install` fixed it; **BUILD SUCCEEDED**.
- pod install needs `LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8` or it dies on
  `Unicode Normalization not appropriate for ASCII-8BIT`.
- App launches via `simctl openurl alive108://expo-development-client/?url=…`
  (an OS "Open in" prompt) or plain `simctl launch com.anonymous.app`
  with metro on :8081.
