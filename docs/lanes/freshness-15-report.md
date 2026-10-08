# freshness-15 — "every number updates within 15 min" audit

Lane: freshness-15 · branch `base/v2` @ `05a3b4b` · audited 2026-10-08 ~06:05 UTC (11:35 IST)
Scope: every number the app, landing (/), /city, /community can render — each one's real
refresh path read end-to-end (client poll → server cache → field/forecast/feed cadence →
upstream). Audit only; no fixes landed.

## Server ground truth (what everything bottoms out on)

| layer | cadence / TTL | staleness bound |
|---|---|---|
| live field (`airfield.FIELD`) | request-driven refresh, `CACHE_TTL=900s`, bounded 10 s (`_field_refresh_bounded`); retry 60 s on failure | a served answer never outlives ~15 min while upstreams answer; `stale` flag trips at 45 min (`STALE_AFTER_S`), CloudWatch `alive108-field-age` |
| field snapshot fallback (`data/field/snapshots`, ingest worker) | worker rebuild every `INDEX_PERIOD_S=900s`; serves when newer than live (`_serving_snapshot`) | snapshot age unbounded only if worker AND live refresh both die → flagged stale at 45 min, alarmed |
| forecast (`FORECAST`) | `CACHE_TTL=1800s` (30 min) | forecast numbers re-anchor to live field per refresh; upstream CAMS is hourly anyway |
| fires (`FIRES`) | `CACHE_S=6h`, `STALE_AFTER_S=6h15m`, per-detection `acq_date/acq_time` on the wire | feed-side ≤ ~6h by contract — intrinsically >15 min; disclosed in payload |
| wind (`FIELD.wind`) | own retry 90 s; expires `2*CACHE_TTL+60` ≈ 31 min | up to ~31 min old in the worst case; `age_s` served |
| stations upstreams | WAQI per-refresh pull; DPCC adapter 15 min cache + drops rows >90 min old; CPCB hourly-ish; OpenAQ last-resort | a DPCC row can legally enter the blend up to ~90 min stale (the >90 min drop is the stale guard); station counts age out per instrument |
| archive (`/v2/archive`) | one recorded field per IST hour (archive.run_forever, sleeps to next hour) | newest recorded hour lands ≤ ~hour + a capture delay |
| `/v2/city` payload cache | 60 s, keyed to (field epoch, stations, TRIPS._rev, forecast epoch); `cached_s` disclosed | ≤ 60 s on top of the inputs' own cadence |
| `/v2/districts` cache | 120 s keyed to field epoch | ≤ 2 min past a field rebuild |
| `/v2/day`, `/v2/outlook` | 60 s cache keyed (cell, hour, field+forecast epochs) | ≤ 60 s over field/forecast cadence |
| `/v2/why` series | 5 min snapshot-series cache; drivers computed per call | ≤ 5 min over the 15-min build series |
| `/v2/skill` | 120 s fingerprint cache (`ALIVE_SKILL_TTL_S`) over the hourly archive | doc can repeat identical `generated_ist` for ≤120 s; pairs themselves land hourly |
| `/v2/reach` veil | 60 s, key includes field epoch | ≤ 60 s |
| `/v2/strip` | sampled at serve; route_id expires 1 h | the strip is a **snapshot** — see F3 |
| `/community` totals | live aggregate scan per request (TRIPS/DDB), corridor cells cache 60 s | real-time + ≤60 s |
| `/grid` cells | epoch-keyed memo (`fetched_at`, obs rev) — the surface only changes when the field does | = field cadence |
| `/today` | decade-climatology curve, static per month×hour | history by design |
| rollups | daily 00:30 IST + weekly Sun Fargate; in-app mirror pulls S3 every 30 min | day-scale by design |

## Landing `/` (server/landing.html)

Client cadence: the whole live set repaints on `setInterval(…, 120000)` — paint, status,
loadDistricts, heroCity, skillLine, whyTonight. The map-age readout re-derives every 30 s on
wall-clock between /health polls (honest ticking, goes stale on dead net). Day strip + boot
numeral are once-per-load. Forecast horizon frames are fetched once per h, **then held for
the whole page session**.

| number | source | mechanism | worst-case staleness | verdict | fix-if-needed |
|---|---|---|---|---|---|
| hero numeral (NCR PM2.5 mean) | `/v2/city` `pm25_stats.mean` | 120 s page poll → 60 s keyed cache → field ≤15 min | ~field cadence + ≤3 min transit ≈ ≤18 min corner | ok (age shown via heroLive/toplive) | — |
| breath equation (µg inhaled, cigarettes) | `/v2/city` `breath` | same payload | same | ok | — |
| "live air +N% vs typical" (dayNote) | `/v2/city` `typical.vs_now_pct` | same payload; typical is static climatology | same | ok | — |
| next-12-hours spark + lo–hi range | `/v2/city` `next_hours` | 60 s cache → FORECAST 30 min TTL | ≤ ~30 min over field | ok — labeled "live forecast" | — |
| map cells (the raster) | `/grid?cells&param` | 120 s poll; server epoch-keyed memo | field cadence ≤15 min | ok | — |
| "map N min fresh" / stale (status line, heroLive, toplive) | `/health` `field_age_s`, `field_stale` | 120 s poll + 30 s client-side re-derive | ≤ ~2 min render lag on true age | ok — honestly ages, flips to "stale" | — |
| stations-live count | `/health` `sources.stations.count` | 120 s poll → field status | ≤ field cadence | ok | — |
| wind km/h | `/health` `wind` | field wind, expires ~31 min | ≤ ~31 min worst-case (disclosed on wire, not on the strip) | degraded-minor — the strip never says wind's age | could append `wind.age_s` or dim when >15 min |
| "usual N µg/m³" in status line | median of **live** /grid cells (`MEDIAN`) | 120 s poll | field cadence | ok freshness — **label nit**: word "usual" reads climatological but it's the live median | rename label if it bothers |
| road segments priced / edges | `/health` `routing` | static per deploy | only changes on redeploy | ok (structural number, not a reading) | — |
| district chips + count | `/v2/districts` | 120 s poll → 120 s field-keyed cache | field cadence + ≤2 min | ok | — |
| confidence split ("N measured · N estimated · N thin") | `/grid` `conf` counts | same paint | same | ok | — |
| day-bars climatology + "now" bar | `/today` | **once per page load** — never re-polled | curve is static history (fine); the "now" marker freezes at open | honest-stale — a page open >1 h shows the wrong "now" bar | F6 — cheap: re-run dayStrip on the 120 s cycle or re-mark client-side |
| skill line (MAE/bias/hit-rate + since) | `/v2/skill` | 120 s poll → 120 s fingerprint cache → hourly archive | numbers land hourly + ≤2 min; by-design archive-lag | honest-stale | — |
| why-tonight line | `/v2/why` | computed per call; fires 6 h feed, series 5 min cache | drivers ≤15 min; fires figures ≤6 h intrinsic | degraded-intrinsic — fire counts/deltas are hours-old data (labeled "measured") | none sane — FIRMS cadence is upstream reality; the payload carries acq stamps |
| timeline h+0…h+11 forecast frames | `/grid?h=N` | fetched once per h, `TL.cache` held **for the session** | session-length — a page open >30 min animates last forecast epoch's cells | **degraded — can sit >15 min stale and reads as "forecast"** | F1 — invalidate TL.cache on `cell_epoch[1]` change or re-pull on the 120 s cycle |
| a→b plan demo + depart curve | `/v2/plan`, `/depart` | on tap only; live field + forecast at call time; `/depart` cache keyed to forecast epoch | fresh at interaction | ok | — |
| locality / reverse names | `/v2/reverse`, gazetteer | on tap; static + live name layer | n/a | ok | — |
| build tag | `/health` `build_sha` | 120 s poll | per deploy | ok | — |

## `/city` (server/city.html)

Client cadence: `refreshMs` = the field's own `refresh_in_s`×1000 when ≥30 s, else 60 s —
the page sleeps until just after the next field build, then repaints everything (map, hero,
ledger, ticker, corridors, archive strip, outlook strip) in one `load()`. Clock 30 s local.
Reach/horizon strips are on-interaction.

| number | source | mechanism | worst-case staleness | verdict | fix-if-needed |
|---|---|---|---|---|---|
| live mean + band + CPCB AQI (hMean/hBand) | `/v2/city` `pm25_stats.mean`, `grap.aqi` | adaptive poll → 60 s cache → field | field cadence + ~60 s | ok | — |
| "across the map lo–hi" range | `/grid` cell spread | same load() | same | ok | — |
| districts live / easiest / heaviest | `/v2/districts` | same load() | field cadence + ≤2 min | ok | — |
| why line, cause note, GRAP line | `/v2/city` `why`, `grap` | computed inside the city payload | field cadence; fires figures ≤6 h | degraded-intrinsic (fires only) | — |
| feed line (source · N points · N live stations · kriging) | `/aqi` `field` | same load() | field cadence | ok | — |
| "map rebuilt N min ago · nearest square X km · ±M µg" | `/aqi` `field.age_s`, `nearest_sample_km`, `calibration.mae_ug` | same load() | honest age at paint | ok | — |
| wind tag | `/aqi` `wind` | wind expires ~31 min | can sit ~31 min stale **with no age printed** | degraded-minor | F7 — print or dim when `wind.age_s`>15 min |
| today ledger: dose µg, trips, km, all-time contrib, corridors ≥3, cells, CO₂, modes | `/v2/city` `trips` aggregates | live aggregate scan + ≤60 s payload cache, **but the page's poll itself can sleep a whole 15-min field cadence** | donation counters can lag ~15–16 min in the corner (poll follows `refresh_in_s`) | degraded-borderline vs the 15-min rule | F8 — `refreshMs = Math.min(rs, 10*60*1000)` caps the wait inside the rule |
| breaths estimate | derived client-side (dose_ug/mean×2000) | same | same | ok | — |
| corridors table (street, trips, µg/trip, vs typical) | `/v2/city` `corridors` (72 h k≥3) | same load() | aggregates move only on donations; publish gate is real | ok | — |
| archive strip (recorded hours mosaic) | `/v2/archive` | re-fetched each load(); capture hourly IST | ≤ ~1 h by design; labeled recorded | honest-stale | — |
| days-ahead strip | `/v2/outlook` | each load() → 60 s cache → forecast 30 min | ≤ ~30 min | ok | — |
| timeline h+N frames | `/grid?h=N` | **once per session** (`TL.pending[h]` first-touch fetch) | session-length | **degraded — same as landing** | F1 |
| reach veil (dose-budget region) | `/v2/reach` | on interaction; 60 s veil cache incl. field epoch | ≤60 s over field | ok | — |
| IST clock + "updated HH:MM" stamp | client render | 30 s tick / per load() | live | ok | — |

## `/community` (server/community.html)

Client cadence: `setInterval(load, 60000)` — /community + /reports + /health each minute.

| number | source | mechanism | worst-case staleness | verdict | fix-if-needed |
|---|---|---|---|---|---|
| phones sharing / trips all-time / trips today / km / µg breathed / µg dodged (today + all-time) / modes today | `/community` totals | live aggregate scan per request; page polls 60 s | ≤ ~60 s | ok | — |
| "last shared trip N min ago" | `/community` `latest_obs_age_min` | computed at serve, re-polled 60 s | honestly ages (91 min observed) | ok | — |
| live rider flags count + rows | `/reports` (6 h TTL pins) | 60 s poll, per-request list | ≤60 s; pins expire at 6 h — disclosed per row (`age_min`) | ok | — |
| corridors board (trips, phones, µg/trip, main mode, CO₂/100 m) | `/community` `top_corridors` | 60 s cells cache, 72 h k≥3 gate | ≤ ~2 min over donation writes | ok | — |
| build tag | `/health` | 60 s poll | per deploy | ok | — |

## App (Mobile/)

Client cadences (App.tsx boot effect): **/aqi ambient poll 60 s** (foreground; also drives
the events engine + daylog sampling), **/reports 60 s**, **/health ping 15 s**, **field grid
pull 10 min** (epoch-deduped, 3×7 s boot retry). `fetchCached` is last-good-on-failure only —
it never short-circuits a live fetch, and stale serves carry `stale` + `ageS` so the UI ages
honestly. Field age re-derives on wall-clock every 30 s (`ageTick`) so a dead network flips
the chip to stale instead of lying.

| number | source | mechanism | worst-case staleness | verdict | fix-if-needed |
|---|---|---|---|---|---|
| home hero ambient ("outside now ~N µg/m³") | `/aqi` `pm25_ambient` | 60 s poll → field ≤15 min | ~16 min corner (field cadence + poll) | ok — forecast fallback is labeled "forecast", never reads as live | — |
| hero field-age line / freshness chips everywhere | `/aqi` `field.age_s`/`stale` + `plan.field` | 60 s data + 30 s wall-clock re-derive | display ages honestly even offline | ok | — |
| painted air-map cells | `/grid?cells=28` | 10 min pull, same-epoch skip → ≤ field cadence | ≤ ~15 min + poll skew ≈ 15–25 min; cells carry the field's own build epoch and the chip reports it | ok | — |
| live station dots | `/aqi` `field.stations` list | 60 s poll | field cadence | ok | — |
| day arc / morning answers (heaviest/cleanest window, "same errand N× lighter") | `/v2/day` (+`/grid?h` fallback) | re-assembles on each landed ambient sample — dedupe lands ≥ every ~8 min even stationary | ≤ ~8–10 min while foreground | ok | — |
| days-ahead card | `/v2/outlook` | same re-assemble cadence | ≤ ~8–10 min | ok | — |
| DelhiToday sheet (breath µg/cig, districts, corridors, trips ledger, moves card) | `/v2/city` + `/v2/city/moves` | fetched once per sheet open; `freshness.age_min` shown | fresh at open; **frozen while the sheet stays open** — the age chip prints the fetch-time value, not elapsed | honest-stale — disclosed but static | F4 — tick age client-side or re-fetch every 60 s while visible |
| dose ledger / trips / week dots / symptom lens | on-device daylog + sealed rollups | accrues per sample & trip; pure local | real-time | ok — genuinely stale-able but recomputes as samples accumulate (owner-sanctioned) | — |
| nav live counters (dose, CO₂, ETA) | `/v2/strip` at nav start (+ on reroute); 1 s local tick | **strip is one snapshot for the whole trip; route_id expires 1 h** | a 30–60 min trip integrates a launch-time field; receipt "updated N min ago" prints the strip's fetch-time `age_min`, under-reporting as the trip lengthens | **degraded — can ride >15 min stale while the counter reads live** | F3 — re-pull strip ~every 10–15 min during nav; stamp receipt age = fetch-age + elapsed |
| plan compare doses / "cleanest · N% less" | `/v2/plan` + `/v2/strip` per option | on demand; plan carries `field` block | fresh at call | ok | — |
| depart curve (dose-by-hour) | `/depart` | on demand; server cache keyed to forecast epoch | fresh at call | ok | — |
| report pins (map) | `/reports` | 60 s poll | ≤60 s | ok | — |
| fires layer dots | `/fires` | **fetched once per app session** (`if (!fires)` guard) | session + feed's ≤6 h → a long session sees launch-time fires | **degraded — worst case far past 15 min** | F2 — refetch on enable-if->15 min-old or a 15 min timer while the layer is on |
| corridors layer dots | `/community` `top_corridors` | **fetched once per session** (`if (!community)` guard) | session-length; corridors are 72 h aggregates so harm is low | degraded-minor | same fix shape as F2 |
| blackspots layer | `/blackspots` | static published data (DTP 2021 + IIT lists) | frozen dataset by nature | honest-static | — |
| air alerts (band/window/fires/stagnation pings) | `/aqi` poll + `/v2/why` (10 min throttle) + `/v2/day` + `/v2/outlook` | piggyback the 60 s poll; why ≤10 min | ≤ ~10 min | ok | — |
| settings "nearest instrument N km" | `/aqi` `nearest_station_km` | 60 s poll | field cadence | ok | — |
| "saved to send" outbox count | local outbox | drains on next success (lazy flush) | real-time-ish (drains on next poll success, not a timer) | ok | — |
| onboarding ambient number | boot `/aqi` read | once | one read, framed as such | ok | — |
| tap readout ("N µg/m³ — band · locality") | painted cell else `/aqi` edge fallback | on tap | field cadence | ok | — |
| daily-brief best window | `/today` climatology | computed at arm time | static climatology | honest-static | — |
| clocks / ETA / duration / "N paused min" | local + engine | 1 s ticks | live | ok | — |

## Prod drift probe (GET-only, 74 s apart, 05:57–05:58 UTC)

- `/aqi?lat=28.63&lon=77.22`: `field.age_s` 319 → 394 (+75 s wall), `built_at` fixed
  `05:52:11`, `refresh_in_s` 581 → 506 counting down to the next build — **the field ages
  honestly and is mid-cadence; pm25/ambient identical within the epoch as designed.**
- `/v2/city`: `generated_at` advanced +74 s; `freshness.field_age_s` 283 → 348 (live);
  `cached_s` 34.8 → 44.2 → **the 60 s keyed cache rebuilt mid-gap exactly once, as designed.**
- `/v2/skill`: `generated_ist` byte-identical across hits → **confirms the 120 s fingerprint
  cache**; `coverage.last_pair_ist` = 11:00 IST = the current archive hour → capture is live.
- `/v2/archive`: 60 snapshots, last = current IST hour. `/v2/outlook`: `field.age_s` 636,
  five days out, live-anchored. `/fires`: 71 detections with per-fire acq stamps
  (24 h rolling feed — intrinsic age). `/community`: `latest_obs_age_min` = 91 min, real.
- `/v2/districts`: `field_age_s` 639, `cached_s` 0 — rebuilt on the fresh epoch.
- `/health`: build `05a3b4bd` = HEAD; engine `alive_core`; 53 stations (waqi+dpcc); field
  not stale; `refresh_in_s` consistent with the 900 s TTL.

## Verdict vs the 15-min rule

**Held.** Every number that claims "live" rides the field's own 15-min cadence or a shorter
client poll on top of it; staleness paths are disclosed (age fields, stale flags, honest
"recorded"/"forecast" labels) rather than silent. The boundary cases that can render
>15-min-old data without saying so:

- **F1 — forecast timeline frames never refresh in-session** (landing `tlFetch` ~L1542 +
  the 120 s set ~L2609; city `TL.pending[h]` ~L828): horizon cells can animate an old
  forecast epoch all session. Fix: compare `cell_epoch[1]` (FORECAST epoch) per poll or
  fold horizon re-pull into the existing refresh cycle.
- **F2 — app fires/corridors layers fetch once per session** (`Mobile/App.tsx` ~L880–882,
  `!fires`/`!community` guards): long sessions show launch-time overlays. Fix: refetch when
  layer data is >15 min old (stamp at fetch, check on enable + a timer while on).
- **F3 — nav dose counters integrate a stale strip on >15-min trips** (`engine.ts`
  `refreshStrip` once at start + reroute only; receipt age = fetch-time `age_min`,
  `ReceiptSheet.tsx` ~L435). Fix: re-fetch the strip on a 10–15 min timer during nav
  (route_id lives 1 h) and render receipt age as fetch-age + elapsed-since-fetch.
- **F4 — DelhiToday freezes at open** (`DelhiToday.tsx` mount effect ~L246; age chip
  ~L437 prints fetch-time `age_min`). Fix: age = serve-age + wall-clock-since-fetch, or
  re-poll 60 s while visible.
- **F8 — /city poll can sleep a full 15-min field cadence** (`city.html` ~L1687
  `refreshMs = refresh_in_s*1000`): donation-derived ledger numbers (dose/km/trips today)
  can lag ~15–16 min even though /community serves them at 60 s. Fix: cap at ≤10 min
  (`Math.min(rs, 600_000)`).
- **F7 — /city wind tag prints no age** (wind expires ~31 min server-side): a ~30-min-old
  wind reads as current. Fix: include `wind.age_s` or mute the tag when >15 min.
- **F6 — landing daybar "now" marker freezes on long-open pages** (`/today` is
  load-once): re-mark client-side or re-run `dayStrip()` on the 120 s cycle.
- **F5 — `/v2/city` freshness label tolerates 2×TTL = 30 min** (`city.py` `STALE_S`): a
  20-min-old field still says "live" (age_min is shown, so it's disclosed — borderline,
  not a lie). Optional tightening to 1×TTL.

Honest-stale by design (intrinsic upstream cadence, disclosed): fire counts/fields (≤6 h
FIRMS), archived hours (hourly), skill pairs (hourly archive), climatology curves (static),
DPCC rows (may be up to ~90 min at the adapter's drop gate), corridors (72 h window).
