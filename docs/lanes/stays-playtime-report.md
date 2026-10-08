# stays+playtime lane report — hackathon features 2 & 3

Date: 2026-10-08 · Branch: `base/v2` · Scope: `server/v2/explore.py` (new),
`GET /v2/stays` + `GET /v2/playtime`, mobile `ExploreSheet` + search intent path.

Features per owner brief: (2) *hotels and accommodation — best place to reside in
Delhi right now, least average pollution*; (3) *kids want to play football — best
TIME in their area, when it is cleanest*.

---

## STEP 1 — engine primitives (what actually exists, and what it costs)

Verified against live code on `base/v2`, server running `main:app` on :8108.

### Exists: hourly PM2.5 forecast at ARBITRARY lat/lon — `forecast.FORECAST.pm25(lat, lon, h)`

`server/forecast.py`. Open-Meteo CAMS gridded forecast — 120 hourly slots
(`h=0..119`), each model value corrected by the ventilation/stagnation model and
advected on live 10 m wind. On refresh it anchors to the live field: a
parcel-bias delta that decays ~9 h plus a persistence blend
`anchor_w(h)` = 1.0 through h+2, linear → 0 by h+40. So the first hours track the
measured field, the tail is pure model. `hour_index(h)` / `time_at(idx)` map
slots→times; `status()` reports fetch age/health.

Cost: after `refresh()` the whole horizon lives in memory — each `pm25()` call is
a dict lookup + correction, no network. Cheap enough to score 40 lodging rows ×
24 h per `/v2/stays` request in milliseconds. **This is the primitive the
"watch the day" scrubber's h+N layers and this lane both sit on.**

### Exists: live field value at a point — `airfield.FIELD.value(lat, lon)`

`server/airfield.py`. Kriged blend of ingested station samples + model fill over
the Delhi coverage bbox. Companions used here: `FIELD.sigma()` (per-query
uncertainty), `FIELD.nearest_station_km()`, `FIELD.beyond_field_edge()`,
`in_service_area()` / `OUT_OF_AREA`, `FIELD.status()` → serving / age_s / stale /
stations. All in-memory after refresh.

### Exists: IST day machinery — `server/v2/day.py` internals (reused, not copied)

`_IST`/`_TZ_NAME`, `_resolve_slot(h) → (idx, t_iso, dt_utc)`,
`_point_anchor(F, lat, lon, ist_now) → (sigma0, adj)`,
`_hour_entry(...) → {h, start, ist_label, pm25_mid, pm25_lo, pm25_hi, us_aqi,
band, confidence}`, `summarize_day(hours) → {day_mean, day_min,
cleanest_window, heavy_window, decisions}`, `_refresh_both()` (FIELD+FORECAST),
`_DAY_CACHE`. `/v2/day` itself truncates at IST midnight, so `/v2/playtime` rolls
its own 24-hour horizon (`_H_WINDOW=24`) and reuses `summarize_day` as a rolling
fold — windows that cross midnight get `start_day_offset`/`end_day_offset` so the
UI can say "tomorrow" without inventing dates.

### Exists: place-name → coords — `v2/search.py` `_t1` on `_T1_EXEC`

Same single-hit resolver the search sheet uses; called off the event loop via
`loop.run_in_executor`. `near=` accepts `"lat,lon"`, an explicit `lat`/`lon`
param pair, or a place phrase — one resolution path shared with search, no
invented geocoder.

### Exists: lodging corpus — `v2/gazetteer.py` `GAZ._load()`

344,923 gazetteer/corpus rows `{name, norm, kind, lat, lon, pop}` already deduped
by (norm, ~110 m cell). Lodging filter = Overture kind prefixes
(`overture:hotel|resort|lodging|private_lodging`) plus substring marks on kind
(`hotel, hostel, lodg, resort, guest_house, guesthouse, motel, dharamshala,
accommodation, tourism:apartment`) → **15,976 lodging rows** (`lodging_rows` is
returned in the response). Nearest pool by `_haversine_m`, no spatial index
needed for a 40-row pool.

### What does NOT exist (said plainly)

- **No pre-baked per-point hourly tiles API** — the map layers are rendered
  rasters; the queryable primitive is `FORECAST.pm25(lat,lon,h)`, which is what
  both endpoints use directly. No gap.
- **No hotel-quality data.** The gazetteer gives name/kind/coords only — stays
  rows say nothing about beds, price, ratings. The card claims "cleanest air",
  never "best hotel".
- **No live station network locally right now.** Field `status()` reports
  `station_readings: 0` — waqi/openaq/cpcb keys absent on this box; field is
  served by `open-meteo/cams` (48 model samples, age ~12 s at test time). The
  honesty flags below are wired to the real signals so prod (with keys) reports
  live-station truth and this box reports model-only truth.

## STEP 2 — endpoints (both served by `server/v2/explore.py`)

Shared cache `_EXPLORE_CACHE = TTLCache(60 s, 128)` keyed on
(rounded anchor, k, IST hour, `data_epoch()`) — same freshness discipline as
`/v2/day`. Both endpoints run `_refresh_both()` first; every number is derived
from `FIELD`/`FORECAST` at request time. `422` when no anchor resolves, `404`
when a named place doesn't resolve, `503`-style honest error when the forecast
has no slots at all.

### `GET /v2/playtime?near=<lat,lon or place>`

Next-24 h curve at the anchor: `hours[]` = `_hour_entry` per slot
(+`date_ist`, `+` `day_offset` since the window rolls past midnight);
`now_pm25`, `mean_pm25`, `best_window` / `worst_window` (contiguous runs from
`summarize_day`, patched with day offsets + relabelled basis "next-24 h mean"),
`cleaner_by_ug` (now − best mid), `confidence` = worst confidence across the
window, `flat` when the day fold finds no meaningful dip, `verdict` =
one line e.g. *"least-bad window 12:30–14:30 tomorrow, ~71 µg/m³ avg — 15 µg/m³
lighter than now"*, `sparse` / `beyond_edge` / `nearest_station_km`, plus
`field` + `forecast` status blocks.

Live probe (Karol Bagh, 2026-10-08 ~23:00 IST): now 85.6 → best 70.8
(12:30–14:30 tomorrow), next-24 h mean 100.5, `sparse: true` — no instrument
within 12 km because the field is model-only on this box. Correct honest flag.

### `GET /v2/stays?near=<lat,lon or place>&k=8`

Pool = 40 nearest lodging rows to the resolved anchor; each row scored by
**mean of `FORECAST.pm25(row.lat, row.lon, h)` over the next 24 h**
(`window_mean_ug`, `scored_on:"forecast"`), falling back to `pm25_now` alone
when the forecast is unavailable (`scored_h: 0` + `window_mean_ug: null`, never
borrowed numbers), rows with neither sort last (`unrated`). Rank by
(unrated, window_mean, pm_now, dist). `cleaner_by_ug` = anchor pm_now − row
pm_now ("cleaner by Xµg vs your area"). Per-row `sparse` +
`nearest_station_km`; top-level `anchor_pm25_now`, `anchor_band`,
`lodging_rows`, `scored_h`.

Live probe (Connaught Place, k=8): 15,976 lodging rows scanned, all 8 results
within ~0.4 km with window means 101.7–101.9 µg/m³ — real modelled gradient is
that smooth at neighbourhood scale; deltas +0.2…+0.4 say honestly "same air
nearby".

## STEP 3 — mobile (one explore sheet, two modes, zero new design language)

Query path: `src/search/explore.ts` `exploreIntent(parsed)` — stay tokens
(hotel/stay/accommodation…) vs play tokens (play/football/park/outside…);
anchor = `near`-phrase else remaining non-stop tokens, else null → "near you".
`SearchScreen` renders an "air answers" intent row above results (hotel/explore
icon, e.g. "where should we stay · near karol bagh") → `SearchSelection`
`{type:"explore"}` → `App.tsx` resolves the anchor (named place or real GPS via
`posNowDetailed`/`searchUserLoc` — never a fabricated center) → new `explore`
phase → `ExploreSheet` (half-detent `Sheet`, mode-switch pill, V2T register —
warm neutral base, forest accent only where it means cleaner).

- **stays mode**: honest chips first (thin-read when `sparse`, now-only when
  `scored_h===0`), then rows — band dot, name, kind · dist, `~N µg` window mean,
  delta text `+0.4 µg lighter than you` / `−… heavier` / `same air`; tap →
  `onPin` drops a real tap-read pin on the air map at the hotel's coords.
- **playtime mode**: verdict line, 24-bar flex curve — bar height = pm25_mid
  within the served span, fill = `bandColorIdx`, best-window bars at full
  opacity with accent underline + "lightest" marker, "now" marker at h=0,
  axis = first label | best chip (e.g. `12:30–14:30 tomorrow`) | last label;
  avg line + worst line + decision rows from the fold. `failed` state per mode,
  empty stays → honest "no stays" line, out-of-area → honest chip.

i18n: 27 new keys in `strings.ts`, en+hi parity (compiler-enforced); server
kind labels go through `localizeKind`, never literals.

## Gates

- server `pytest tests/` full suite: **1206 passed, 62 skipped, 2 xfailed**;
  3 pre-existing environment failures untouched by this lane —
  `test_path_legality.py` ×2 need the `alive_core` C ext (not built on this
  box) and `test_query_tolerance.py::test_search_latency_compound_path` fails
  the 50 ms p95 on this unloaded pure-Python path; both files carry no diff vs
  HEAD. New `test_v2_explore.py` (10 tests: dip-window found, flat-horizon
  honesty, near= by name and by coords, 404 unresolvable, OUT_OF_AREA, stays
  ranked / lodging-kinds only / k cap / delta arithmetic, no-forecast
  now-only fallback) + `test_contract_sync.py` fetchers/NESTED all green.
- mobile `npx tsc --noEmit` clean; `npx expo lint` clean (0 errors);
  node runners — search 12, api 37, nav 100, offline 16, store 99 = 264 pass, 0 fail.
- SIM PROOF: iOS dev client (iPhone 17, iOS 27.0) built against this box's
  live server (`EXPO_PUBLIC_API_URL=http://localhost:8108`), driven end-to-end:
  search intent row → stays sheet (thin-read chip, per-row window means +
  "same air" deltas) → row tap drops a real tap-read pin with a live field
  read at the hotel's coords → in-sheet mode switch → playtime verdict +
  24-bar banded curve → switch back. Screenshots + `explore-drive-small.mp4`
  (~3.6 min, intent → both surfaces) under `docs/lanes/stays-playtime-shots/`.

## Known limits (honest)

- Window scoring is forecast-grade: `scored_h` tells you how many of the 24 h
  were modelled; when the forecast is absent the card says so and scores on
  now-only.
- `sparse` fires whenever `nearest_station_km` is unavailable or > 12 km — on a
  model-only field (no station keys) everything reports sparse. That's the
  honest answer, not a bug.
- Results cluster within a neighbourhood — that's the real gradient, not a dedup
  bug; the delta chips make "no gain nearby" readable.
