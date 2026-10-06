# ALive-108 — demo-day runbook (Oct 10, offline hall)

Verified against live AWS build `a0e74abe` (ECS ap-south-1, task-def 39,
FARGATE_SPOT); re-verified 2026-10-04 on `6a067ca4` (task-def ~110,
osrm-local sidecar live); re-verified 2026-10-05 on `951eeb3c`
(task-def :141, post dose re-anchor). *[drift notes 2026-10-05: live
later stamped `d08d9f74` task-def `:142`, then `c7df5db5` — and at
~18:00 IST the deployed image URI is `alive108-api:1e93b9f2` on
task-def `:147` while `/health` still stamps `c7df5db5`; the BUILD_SHA
env lag is a known wart — the ECR/task image tag is the truth.
~19:15 IST: a further deploy moved the task to `a382cdeb` task-def `:150`,
and `/health` `build_sha` now MATCHES the image tag — the lag wart is
resolved on this revision. New wart observed on that deploy: a fresh task
serves a thin field (~41 model samples / 16 stations, recovering to 24 by
~60 min), `wind.known:false` ~45 min, and transit plan rows absent until
the runtime GTFS download+parse lands (silent-empty → `degraded:["transit"]`
→ bus-then-metro; never deploy inside the T-60 window).
~19:30 IST a further deploy moved `3657d289` (`:152`) → `c3d9c111`
task-def `:153` — "bake GTFS
into image + boot-warm before healthy" (`tools/bake_gtfs.py`): on that
build metro+walk rows served ~4 min after task start, killing the transit
cold-start wart. Verified on the fresh task: `/health` now carries a
`transit` key (on_disk/compiled/real_feeds), field 24 stations + wind
~4 min in. The wart is FIXED on builds ≥ c3d9c11 — it can still regress
on older images. Also observed during the deploy window: a `/v2/strip`
call on a route_id minted pre-swap 404s (route store is per-task,
in-memory) — re-mint plan→strip pairs after any task replacement.
~16:20 UTC refresh pass: `/health` `build_sha` is `cb862533` (matches the
deployed image tag) while `/admin/api/status` still stamps `ec51c882` —
the BUILD_SHA wart is live again on this revision. The field archive
began recording 2026-10-05 20:00 IST (`/v2/archive` → 2 snapshots so far,
hours 0–19 honestly absent); the /city 'what happened' recorded-vs-
forecast flip is committed (`4ad9e0c`) but NOT deployed — it rides the
next image; verify it exists before narrating it.]*
*[demo-proof pass 2026-10-05 ~19:30 UTC — every stale item above
re-run on live: `/health` now stamps `6e82f290` (matches the deployed
image — the lag wart is resolved on this revision). Deployed with it:
`/v2/why` ("the air is barely moving — the day's pollution is sitting
over the city"), the /city 'why tonight' chip, the landing-page
day-note why line (`6e82f29`), the DelhiToday `why.line` render
(`8d032e3`), the `decisions:[]` plain-words fallback (`88e37d5` —
deployed: `decisions` carried 3 rows tonight), the /city 'what
happened' recorded-vs-model flip (`4ad9e0c` — DEPLOYED, the strip
paints recorded hours now), and the why-line suffix fix (`8d359a6` —
the line ends clean, no "— the build you see" tail). Archive: 6
snapshots since Oct 5 20:00 IST (last 01:00 IST Oct 6). Districts: 29
chips (16 district rows incl. Delhi NCT + 13 sub-areas).]*
*[numbers-refresh pass 2026-10-05 ~22:15–22:20 UTC — the strip-bz deploy
landed: `/health` stamps `80a15258` and `/v2/plan` + `/v2/reroute` now
price on the breathing-zone basis, `smoke_modifier: 1.09` echoed on the
wire (same ×1.09 `/aqi` serves — plan and the public pm25 finally share
one basis). Every number below re-read on that build: dose ladder
car-AC 10.8 / walk 358.3 µg (**33.2×**, slowest/best 38.7×), 23 options,
warm took_ms ~56 ms (first post-deploy hit 4,653 ms — fresh-task
reprice), day windows heavy 22:30 IST → day end ~159 / cleanest
12:30–18:30 ~45 / mean ~105, depart 29.2 → 79.7 (2.7×, best +12 h 14.5),
reach walk@25 3,211 edges / 141.2 km, walk@50 10,510 / 553.9 km,
car@25 890,510 / 75,822 km (`edge_partial`), car@100 1,029,263 /
99,503 km, breath 885 µg (2.8 cig), PM2.5@CP 76.1 breathing / 69.8
ambient / US AQI 158, wind 4.3 km/h @182° S (fires refused — outside
the NW gate), 24 stations / 70 samples / field age ~96 s, corridors
12 publishable of 54 tracked, community 22 trips all-time / 14
contributors / 725.9 µg avoided (24 h: 6 obs / 14.1 km / 477.3 µg),
skill 21 pairs — h+1 graded MAE 16.3/+15.8 (71.4%/80.0% band-hit), h+2
29.9/+29.6, h=0 and h≥3 still `thin`, archive 8 snapshots, why still
stagnation (VC ~100 m²/s vs ~3,000).]*
*[demo-rehearse-v2 pass 2026-10-05 ~23:55 UTC → Oct 6 ~00:15 UTC —
`scripts/verify_numbers.sh` + live probes. A deploy rolled mid-pass:
the live build is now **`37e55668`** — ledger-floor `0fdd597`,
ingest-parallel `5ec1f2f`, why-parallel `3aea78f`, hi-i18n `416a195`
ARE live (the first reads in this note were on `3711ccd0`). Fresh
reads on `37e55668`: dose ladder car-AC 12.9 / walk 429.2 µg (**33.3×**,
slowest/best 40.1×), 24 options (the count swung 19→24 inside minutes
on one reprice — never quote an exact count), metro+walk 79.5 + GTFS
"Bus 859" 144.1 present, warm took_ms ~610 ms (~2.1 s wall ex-India;
post-refresh first hit ~8 s server), day windows heavy ~22:30 → day
end @ ~160 / cleanest 13:30–18:30 @ ~45 / mean ~106 (windows move
with the field — read `decisions`/`hours` on stage), depart now 34.4
→ worst ~100.6 (2.9×), best ~14.9, `?hours=120` serves 109 slots
(forecast-limited), reach walk@25 ~84 km, walk@50 ~396 km, car@25
~54,350 km `edge_partial`, breath 1,165 µg (3.7 cig), PM2.5@CP 83.3
breathing / 75.1 ambient / US AQI 161, wind 3.6 km/h @171° S, fires
89/22 (76.8 MW) ×1.11, 24 stations / 70 samples, corridors 12/54,
community unchanged (22/14/725.9; 24 h 6/14.1/477.3), city moves
39 trips/7 d, skill **34 pairs — h+1..h+4 graded** (h+1 14.2/+11.2,
h+2 26.3/+24.5, h+3 42.0, h+4 49.0; h=0,h≥5 thin), archive **10
snapshots**, why stagnation VC ~122 m²/s — trend EVALUATED, history
LIT (+0.3 µg over 5.8 h, 34 snapshots; `cannot_tell` empty). Strip
re-minted: 77 samples, pm2.5 69.7→90.3 (1.30×) — mint on the tagged
recommended row; the least-smoke `rd` engine row strips 'unnamed
road'. `/v2/day` now requires `lat`/`lon` (bare call 422s). Full table:
docs/lanes/demo-rehearse-v2-report.md.]*
Every number below was read
off the running service — they drift with the field; re-check on the
day. Nothing in the product is seeded or faked.

*Product framing (the pivot — `docs/plan/alive-depth.md`): ALive-108 is a
**personal PM2.5 dosimeter without hardware** — timeline × concentration
field → your dose, reconstructed on-device; only consented k≥3 aggregates
ever leave the phone. Routing is one feature inside it — the proof the
field is real enough to decide with. The ≤3 min video arc lives in
`docs/submission/video-shotlist.md` (your-day card → dose gap → lung
reach → engine room → console).*

Release APK: sideload build, universal arm64+x86_64, debug-signed —
built with `EXPO_PUBLIC_API_URL=http://alive108-…elb.ap-south-1.
amazonaws.com` (NLB serves :80 only; never `:8000` or `https://`).
For the self-hosted Delhi basemap (street names/POIs to z14 from our
own pmtiles), also pass `EXPO_PUBLIC_TILES_URL=http://65.2.28.40/
tiles/tilejson.json` at bundle time; omitted → hosted OpenFreeMap
fallback, still fine but not ours (docs/plan/handoff.md cont.15).

## The pitches (one breath each)

- **Consumer (the dosimeter):** "Your lungs' ledger for Delhi — what you
  breathed today, where it cost you, and when tomorrow's air is worth
  going out in. No device, no uploads — your phone's own timeline times
  our field, reconstructed on the phone itself."
- **Admin:** "Every consented trip becomes part of Delhi's public ledger —
  this screen is the engine room behind it, and the only thing that ever
  leaves a phone is an anonymized aggregate."
- **Track (Air):** "Personal exposure without hardware: a kriged field,
  per-250-metre inhaled dose on real routes, a morning card that names
  your cleanest hours, a lung-budget reach map — and a privacy-clean
  community layer that publishes a street only after three different
  riders cross it."

## The questions they will ask

**"Why not Google Maps + search the AQI?"**
Google gives travel time; an AQI site gives one city number — both answer
"how bad is it," which is why the dosimeter category is a graveyard
(Plume's $200 device died in 2023). We answer "what did it cost ME":
the µg you actually inhale per route option — dose = concentration field
sampled every ~250 m of the polyline × mode ventilation × time, plus a
micro-environment factor (a sealed AC car vs walking the same trip
measures ~33× tonight — CP→Gurugram ~13 vs ~429 µg on the
breathing-zone basis, build `37e55668`; re-check T-45,
`scripts/verify_numbers.sh`). Your trips receipt
into an on-device ledger; `GET /v2/day` names today's heavy stretch and
least-bad hours as decisions; `GET /v2/reach` draws where a 25 µg walk
budget can actually take you — bounded Dijkstra on the same engine. Then
emissions per option on real fleet factors (BS-class, fuel,
vintage, occupancy, idle+cold-start).

**"Is the air data real-time? Where from?"**
Yes — keyless, honest provenance, verbatim labels on screen:
- CAMS satellite model + open-meteo, 10 species (PM2.5, PM10, NO₂, O₃,
  CO, SO₂, NH₃, dust, AOD, US/EU AQI), refreshed every 15 min — a
  countdown (`refresh_in_s`) is on the wire. Params a feed doesn't
  serve stay honestly empty (NH₃ is empty today, not zero-filled)
- NASA FIRMS VIIRS/MODIS fire detections (89 today, 22 in the smoke
  belt — drifts daily) feeding a smoke modifier (×1.11 at CP right
  now — sometimes absent; say what `/aqi.smoke_modifier` shows — and
  the same modifier is echoed on `/v2/plan` +
  `/v2/reroute`, already inside their dose numbers)
- WAQI measured stations LIVE: 24 instruments across NCR feed the
  krige directly (the raw feed is a US-EPA sub-index, not µg/m³ —
  inverted via the EPA breakpoint table, Kalman-smoothed, de-biased
  against the archive). CPCB adapter exists too, dormant without a
  CPCB key — the sources table names what is live, never pads
- kriged concentration field served by our own C++ engine (`alive_core`,
  Eigen) — check `/health` → `engine: "alive_core"` live
- a multi-day CAMS horizon anchored to the live field — `/depart?hours=120`
  answers "should I leave tomorrow at 8 am instead" with real numbers
  (109 hourly slots tonight — the served window is
  forecast-limited, not the full 120 h);
  `/v2/city.next_hours` shows the next 12 h rising/falling

**"How is PM2.5 managed on the backend?"**
15-min ingest worker builds a snapshot → mirrors to S3 (last-good field
survives restarts) → C++ `KrigeField` serves point queries with a real σ
band → dose sampling along route geometry → per-mode physics. Edge of
the field reports `coverage < 1` instead of clamping silently. The other
species ride the same lattice; nothing is zero-filled when a feed
doesn't serve it.

**"Why these roads — is it really not the fastest path?"**
The plan engine is an exposure-weighted A* over 1,070,459 real road
edges (903,058 priced; 2-zone OSM merge, Delhi+Haryana+UP side): each
edge's cost is
the inhaled dose for the queried mode (field concentration × microenv
× road uplift × ventilation × dwell), re-priced off a raster of the
live kriged field. A rehearsed query answers in ~1–2 s server-side
(fresh unseen ODs ~6 s; a cold reprice can wall-clock ~9.5 s) and returns
real street
sequences (`via_names`, snap distances) — and every option row's dose
is integrated on the SAME raster the pathfinder minimized over, so
the number shown is the exact criterion the path won on. Routes within
~50km also return **corridor alternatives**: up to two extra least-dose
re-solves that are penalised for re-using the primary corridor's edges
(they must diverge ≥15% of length to count as a real alternative) — so
the app can show "via Outer Circle–Radial 7" vs "via Sansad Marg–Rafi
Marg" (tonight's real alternates), not just one blessed path.

**"How fast is the live surface?"**
`/grid` answers are pure functions of the data's own epochs (field
fetch time, forecast fetch time, community obs version) — repeated
paints replay in ~12 ms and can never serve stale data because the
cache key IS the data version; gzip takes the ~126 KB layer to ~9–11 KB
on the wire (~0.5–0.9 s end-to-end from India).

**"Street-wise how deep does the data go?"**
The search index is built from the real OSM northern+central zone
merge — 120k server rows, ~97.5k corpus entries including **16,949
address-level rows** (real `addr:*` house numbers plus expanded street
interpolations): metro gates, market lanes, mall stores, police
stations, hospitals, house numbers. `559 udyog vihar` returns a real
house-number address; `rajiv chowk gate 5` returns "Rajiv Chowk Metro
Gate No 5" top-hit (all eight gates resolve individually). The C++
index itself answers in ~1ms p50 — the full endpoint measures
p50 ~470 ms over the NLB (172/174 top-1 in a 174-query live battery);
the app bundles a
124,311-entry gazetteer so landmark-level search works fully offline —
no network, no key (23 fabricated landmark geocodes were purged in
`2c4cab4`; the flagship-truth regression pins top-3 within 1.5 km).

**"Privacy?"**
Aggregate-only by construction: no accounts, tokens are hashed
(sha256[:16]), route ends are trimmed on-device before upload, corridors
and mode share are suppressed below k=3 distinct devices. The public
`/v2/city/moves` literally suppresses modes under 3 trips — you can show
`mode_share_suppressed_trips` in the JSON.

**"Does it scale / is it real infrastructure?"**
AWS free-tier shape, least-privilege IAM: ECS Fargate + NLB + DynamoDB
(`alive108-agg`, donations survive redeploys) + S3 field snapshots +
CodeBuild deploys + Secrets Manager. The C++ hot path answers search in
~0.9 ms p50 (120k rows).

**"What happens when a feed or arm dies mid-demo?"**
It says so on the wire — nothing goes silently stale. `/v2/plan` carries
`degraded:[<arm>]` naming any planner arm that timed out or failed while
its siblings still returned real rows (seen live: `["engine","transit"]`
during a cold boot, then absent once warm). `/health` reports
`field_stale:true` + the real age instead of pretending fresh; the
sources table names which feeds are up. The honesty is the point —
we'd rather show a missing arm than a fabricated answer.

## Demo flow (phone)

1. Search: type a Delhi landmark → real suggestions (C++ SearchIndex)
2. Pick → compare sheet: every mode with a dose band + emissions +
   coverage note on edge trips
3. Try a trip to Gurgaon edge → "smoke counted for the NCR span only"
   note (honest coverage); try Mumbai → "outside service area" typed
   notice, no crash
4. Ride it → nav: snapped puck, live dose counter ticking, off-route
   reroute
5. Arrive / End → receipt: dose µg + CO₂ kg + cigarette-equivalent +
   donate toggle → lands in the on-device ledger (the dosimeter's face:
   what today cost, where it accumulated — it never leaves the phone
   unless donated, and donation is aggregate-only)
6. Delhi Today (sidebar): breath hero, the other species row (PM10 ·
   NO₂ · O₃ · CO · SO₂ · US AQI render tonight; NH₃ honestly absent;
   the wire also serves dust+AOD), the 12 h
   forecast strip (CAMS horizon anchored to the live field — hourly
   smoke translates with the real met wind, a semi-Lagrangian
   back-trajectory), "running ±X% vs the decade norm for this hour"
   (9M station-hours), and the "why tonight" line under the hero —
   `why.line` from `/v2/why` (DelhiToday renders it since `8d032e3`,
   live on `6e82f290`, re-verified on `37e55668`): tonight it's stagnation — *"the air is barely
   moving — the day's pollution is sitting over the city"*

## Connectivity plan (venue wifi)

Verified on the release APK emulator gauntlet (airplane cold-start,
edge/gprs throttle, mid-request airplane toggle, dead-server-but-network-up).
The one rule: nothing on screen pretends — every number is either live,
last-good with an honest age mark ("updated N min ago" / "older data —
reconnecting"), or absent.

**Works with zero network (safe on stage no matter what):**

| Surface | Offline behaviour |
|---|---|
| Search | Bundled on-device gazetteer answers instantly (T0). Server tiers degrade silently. |
| Ledger / sidebar | Fully local daylog — trips, week arc, saved places all render. |
| Trip logging | Local-first. A nav leg completes and logs with no uplink. |
| Receipt | Real numbers from the planned route + measured leg. Donations queue: "saved — will send when back online"; the pill counts them ("N saved to send") and they flush on recovery. |
| Nav on a planned route | Directions + route geometry ride from cache; GNSS keeps working with radios off. Counters honestly freeze rather than fabricate. |
| Your day / check-ins | Daylog on-device — breathed-so-far, segments, lens check-ins all work. |

**Needs network (plan around these):**

| Surface | Degrade |
|---|---|
| Plan a NEW O/D | Honest-empty: "couldn't load the ways there — check the connection" + try again (~30 s bound — the krige path legitimately takes >25 s on far routes). |
| Plan a route fetched before | Last-good options; the field chip counts real staleness, never a frozen minute. Start/nav work from it. |
| Delhi today | Last-good payload labelled "older data — reconnecting"; skeletons resolve ≤6 s, never hang. |
| THE DAY AHEAD / DAYS AHEAD | Last-good curve + "last air reading N min ago"; unusable fetch results are refused so they can't overwrite the good cache. |
| Community corridors layer | Fails silent — doesn't draw. |

**Stage plan:** (1) before doors, on any working uplink, touch the demo
route once — search the destination, let compare load, open Delhi today and
the day screen — that seeds every last-good cache; (2) keep a hotspot in
your pocket — if venue wifi dies, join it; the app probes recovery and every
"try again" is one tap; (3) if even the hotspot fails, the demo still
stands — search, a pre-planned route, a full nav leg, the receipt, the
ledger and the day log all work air-gapped; (4) avoid planning a brand-new
route live on stage while the network is down — it will honestly say it
can't (correct, but anticlimactic). Prefer the pre-seeded route.

**Server-side posture (re-verified 2026-10-05 ~19:30 UTC):** every
surface the app and the public pages need is token-less — `/`, `/city`,
`/admin` HTML and all public feeds (`/health`, `/aqi`, `/grid`,
`/fires`, `/v2/city`, `/v2/day`, `/v2/why`, `/v2/skill`, `/v2/archive`,
`/v2/districts`, `/community`, `/v2/reach`, `/v2/outlook`, `/depart`,
`/v2/plan` POST, `/v2/reroute` POST) answer without credentials. Only
`/admin/api/*` is gated — every one returns 401 without
`Authorization: Bearer $ALIVE_ADMIN_TOKEN` (probed tonight). So the
demo's connectivity risk is the venue network itself, never auth.

## Demo flow (admin)

Open `/admin` (token in Secrets Manager `alive108/admin-token`):
- **"where the smoke sits"**: 29 chips — 16 district rows (15 NCR +
  Delhi NCT) + 13 Delhi sub-areas (real OSM admin_level=5 boundaries)
  — each district's own live mean-of-cells pm2.5 read (`/v2/districts`),
  never one number stretched across the map
- headline cards: field age (live badge), samples, donated trips,
  publishable corridors (k≥3), trips switched lighter, daily median,
  cumulative dose, CO₂ emitted by donated rides, model error vs
  held-out stations (MAE)
- **the live field map** (the judge moment): the real /grid cells
  painted on canvas — dose ramp, cells far from a measured sample fade
  honestly, NASA fire detections overlaid as amber dots, the city
  centroid crosshair, the real met wind as a drift arrow. **Species
  pills** (pm2.5 · pm10 · no₂ · o₃ · co · so₂ · us aqi) re-paint the
  map from `/grid?param=` — click no₂ and watch a physically different
  pattern: same lattice, different species, never re-labeled pm2.5.
  All 7 pills re-verified live tonight (100/100 cells each). The
  forecast scrub (`h>0`) is pm2.5-only by design — don't narrate
  species during a scrub; NH₃ is honestly empty today, not zeroed
- **the pipeline panel** (the "how does it work" answer): six stages
  with today's real numbers — measure (N model points, field age) →
  interpolate (kriging engine, alive_core when it serves) → sample
  (~250 m stride) → breathe (the real microenv + ventilation tables:
  car ac ×0.55, auto ×1.15, VE 7.5–22 L/min) → emit (BS bucket ×
  speed × idle × cold-start) → aggregate (k≥3, cells, trips). Served
  by `/admin/api/model` so the constants can never drift from the code
- field panel: serving mode, kriging, σ band, the species line
  (PM10 · NO₂ · O₃ · CO · SO₂ · US AQI — all real), forecast horizon
  health (hours ahead · grid points · fetch age · anchored-to-live flag)
- sources table: model live / met live / fires live / stations live
  (WAQI, N instruments) / **routing** — osrm-local sidecar in the
  same Fargate task (self-hosted MLD over 4.4M NCR edges, ~15ms),
  public demo flagged fallback — observed from real route calls,
  never probed; the honesty is the point
- donations: totals incl. "emissions (mid): kg CO₂ · g PM2.5" — plus
  the **CO₂ phase split** bar (moving / idling / cold-start %) summed
  only over trips whose receipts carried the real breakdown; old
  builds count in the headline total, never in the split
- corridors carry a per-street emission index: `co2_g_per_100m`
  (trip CO₂ spread evenly over the cells the route crosses,
  k≥3-gated, null — never 0 — when no receipts reported emissions) —
  and the table now renders it next to avg dose, so every street row
  reads "breathed X µg · rides put out Y g per 100 m"
- **day-by-day trips strip**: every recorded day as a bar (trips),
  hover carries that day's km/dose/CO₂ — aggregate day counters only
- **the model grades itself** (`/v2/skill`, live since `a5ab92d8`):
  served-forecast vs recorded-hour pairs — n, MAE, bias, band-hit per
  horizon; buckets under 5 pairs render `thin` instead of a number.
  Read it as "the scorecard refuses to bluff" — 34 pairs tonight and
  FOUR horizons now **graded**, not thin: h+1 MAE 14.2 µg/m³,
  bias +11.2 (we over-call), 72.7% cell / 85.7% hour band-hit; h+2
  26.3 / +24.5; h+3 42.0 / +41.9; h+4
  49.0 / +48.9 — the honest widening of error with horizon
  is itself the story. h=0 and h≥5 stay `thin`
  (n<5) — the card only scores what it has receipts for
- **the why beat** (`/v2/why`, shipped `0908d9ad`; line renders on the
  /city 'why tonight' chip, the landing day-note and DelhiToday on
  `6e82f290`) — *the engine grades its own causality.* Tonight's real
  read (build `37e55668`): `drivers[0]` is **stagnation** — "boundary
  layer 111.5 m + wind 1.09 m/s → ventilation ~122 m²/s vs ~3,000
  typical" — while 89 fires
  (22 in the belt, 76.8 MW FRP) are checked-and-refused: `carrying:false`
  because the wind is 171° S, outside the NW-smoke gate; tonight the
  **trend arm evaluated AND history is lit** (+0.3 µg/m³ over 5.8 h,
  34 snapshots — the parallel-fetch fix `3aea78f` is on the live build) and
  `cannot_tell` is empty — every ingredient got checked. Curl on stage:
  `curl $NLB/v2/why` — the judge sees one sentence plus the honest
  `cannot_tell` block. Narration: *"it tells you why — and what it
  can't tell."*
- **the field archive**: `/v2/archive` replays the recorded field hour
  by hour — snapshots land hourly to S3 (**10 tonight**: Oct-5 hours
  20–23 + Oct-6 hours 0–5 IST, since recording began 2026-10-05 20:00
  IST; `/admin/api/status` shows
  `archive.snapshots_total` + `since_ist`); hours with no snapshot are
  honest gaps, never back-filled. The /city 'what happened' flip paints
  recorded hours over the forecast — **deployed** (`4ad9e0c` is live on
  `0908d9ad`+; the strip's recorded/model/δ pills render tonight)
- **live feed**: the newest donations ticking in (ago · mode · dose ·
  km · co₂) — donate a trip on stage and watch it land in the next
  30 s refresh. Aggregate-level events only: the feed can say a trip
  happened, never where or whose. Retried posts dedupe — a phantom
  trip can never enter the totals
- **click any field cell → its locality** (debounced /v2/reverse:
  "near {name} · µg/m³ · measured/interpolated/thin" honesty per
  cell, sectors a01–an40 + degree ticks for indexing); "how this
  layer is made" per species shows the real derivation chain with
  live counts; corridors carry an `air pm2.5` column — the live
  concentration over each corridor's cells, a merge that exists
  nowhere else
- **global dashboard tiles**: users-by-area (k≥3 device counts per
  district), journeys per OD (tracked-vs-published, suppressed until
  k≥3), dose + CO₂ avoided sums over reporting trips, and "their
  reviews" (stars + notes — note bodies publish only at ≥3 reviews;
  no device id or token stored)

## Demo surface: the landing page

`/` itself is a demo surface — open with it: the hero canvas IS the
live field — real `/grid` cells drawn on true NCR geography (thin-
coverage cells honestly dimmer), a wind arrow from `/health`'s live
met vector, and a "watch the day" scrubber that walks real `/grid?h=N`
forecast surfaces. Click any cell for its inspector readout (live
`/aqi` numbers + district + sector — the same APIs admin uses); pick
**a→b** and the line prices a REAL `/v2/plan` call and draws the
least-dose route over the raster — every number on the page is a
served number, never a canned animation.

## Honest limitations (say them first — it lands harder)

- CPCB is dormant without a free CPCB token (WAQI covers measured
  stations meanwhile — 24 instruments live) — the sources table names
  which feeds are up, never pretends
- A corridor appears only after 3 different devices cross it — early on,
  that table is honestly empty
- Service area is Delhi/NCR + a ~2° margin (Jaipur/Agra/Panipat plan
  fine, flagged `conf: medium`); farther trips get a typed notice,
  never a fabricated route
- iOS is a dev-only test bed — the release target is Android

## Ops: keep the task alive + make it warm

### Pre-heat a fresh task (run after every deploy / task replacement)

`python3 tools/warm_task.py` — walks /health, /aqi, /grid, then real
NCR plan ODs until a row with `steps_source: "endpoints"` appears
(priced engine serving), then /reports + /v2/city + the dosimeter
surfaces (/grid?h=12, /v2/day, /v2/reach walk, /v2/outlook, /community)
+ /tiles/health. Exit 0 = warm.
Measured on a live task (2026-10-04): first plan 9.0 s while the
engine repriced, engine rows ~7 s later; a fully cold task needs
~60–100 s to price (graph load ~36 s + first field fetch + raster
sweep) — run this the moment a new task registers healthy, never
cold-call the first demo plan.

### FARGATE_SPOT → on-demand for demo morning (do NOT pre-run; owner executes)

The service runs `capacityProviderStrategy: FARGATE_SPOT weight=1 base=1`
(re-verified `describe-services` 2026-10-05 ~14:00 UTC — ~$0 but Spot can
reclaim any time, including mid-demo). To pin the task on on-demand
Fargate for the day — **T-60: run this verbatim**:

*(the flip replaces the task — SAFE for the why-trend/history surfaces
since `268ed54`: the series reads the S3 `field/` builds, which persist
across rollouts, so the sparkline + trend keep their full recorded
history. The only residual: the ingest worker's first cold build on a
new task takes ~25 min, so the recorded trail gets one ~25-min gap;
serving stays fresh the whole time.)*

```bash
export AWS_DEFAULT_REGION=ap-south-1

# PRE-check (expect FARGATE_SPOT before the flip):
aws ecs describe-services --cluster alive108 --services alive108 \
  --query 'services[0].{cap:capacityProviderStrategy,running:runningCount,taskDef:taskDefinition}'

# THE FLIP — replaces the task with an on-demand one, same image:
aws ecs update-service --cluster alive108 --service alive108 \
  --capacity-provider-strategy "capacityProvider=FARGATE,weight=1,base=1" \
  --force-new-deployment
aws ecs wait services-stable --cluster alive108 --services alive108

# POST-verify — BOTH of these must show FARGATE (not FARGATE_SPOT):
#  a) service strategy:
aws ecs describe-services --cluster alive108 --services alive108 \
  --query 'services[0].{cap:capacityProviderStrategy,deploy:deployments[].rolloutState,running:runningCount}'
#  b) the task itself — capacityProviderName on the new task ARN:
aws ecs describe-tasks --cluster alive108 \
  --tasks "$(aws ecs list-tasks --cluster alive108 --service-name alive108 \
             --query 'taskArns[0]' --output text)" \
  --query 'tasks[].{cap:capacityProviderName,last:lastStatus}'

# THEN warm the replacement task (boots cold — ~2 min to priced engine):
python3 tools/warm_task.py
```

Verify: `describe-services` shows capacityProvider FARGATE and the
`deployments[PRIMARY].rolloutState == COMPLETED`; `describe-tasks` shows
`capacityProviderName: "FARGATE"`; `/health` build_sha unchanged (same
image, new task). Note this REPLACEs the task — the new one boots cold,
so warm it before judging. In-memory route_ids do not survive the swap:
any `/v2/plan → /v2/strip` pair must be re-minted on the new task
(observed live: strip 404s on a pre-deploy route_id).

### Task-size bump for the demo window (optional, pairs with the above)

The service runs 1 vCPU / 3 GB (task-def `:153`) — one uvicorn worker. A burst of
concurrent heavy calls (plans + city + admin on several devices at
once) queues: seen live 2026-10-04, CPU pinned ~100% for 30 min while
an emulator sweep + probes ran together — /v2/reroute hit 24 s waiting
on the event loop (it recovers; single-user demos never see this). To
run the demo on 2 vCPU / 4 GB — headroom for the whole room:

```bash
export AWS_DEFAULT_REGION=ap-south-1
# current task def, same image/env/secrets, bigger cpu/memory:
aws ecs describe-task-definition --task-definition alive108 \
  --query 'taskDefinition.{family:family,role:taskRoleArn,exec:executionRoleArn,
    net:networkMode,req:requiresCompatibilities,vol:volumes,ph:placementConstraints,
    cont:containerDefinitions}' > /tmp/td.json
python3 - <<'PY'
import json,subprocess
td=json.load(open('/tmp/td.json'))
# NOTE: only task-level cpu/memory are bumped. Do NOT set container-level
# memory to the task size — the osrm sidecar carries a hard memory:1024,
# so cont[0].memory=4096 would make the container sum 5120 > task 4096
# and register-task-definition rejects it. Leaving containers as-is gives
# the API ~3 GB effective headroom inside a 4 GB task.
reg=json.loads(subprocess.check_output([
 'aws','ecs','register-task-definition','--region','ap-south-1',
 '--family',td['family'],'--task-role-arn',td['role'],
 '--execution-role-arn',td['exec'],'--network-mode',td['net'],
 '--requires-compatibilities']+td['req']+
 ['--cpu','2048','--memory','4096',
  '--container-definitions',json.dumps(td['cont'])]))
print(reg['taskDefinition']['taskDefinitionArn'])
PY
aws ecs update-service --cluster alive108 --service alive108 \
  --task-definition alive108 --capacity-provider-strategy \
  "capacityProvider=FARGATE,weight=1,base=1" --force-new-deployment
aws ecs wait services-stable --cluster alive108 --services alive108
python3 tools/warm_task.py
```

Cost: 2 vCPU / 4 GB on-demand ≈ ₹8/hr in ap-south-1 — still
single-digit rupees for the demo window. Revert to the prior task-def
revision + FARGATE_SPOT after the event.

Rollback (back to ~$0 Spot) — same command with `FARGATE_SPOT`:

```bash
aws ecs update-service --cluster alive108 --service alive108 \
  --capacity-provider-strategy "capacityProvider=FARGATE_SPOT,weight=1,base=1" \
  --force-new-deployment
```

Cost note: one FARGATE task (1 vCPU / 3 GB) ≈ ₹4–5/hr in ap-south-1 —
single-digit rupees for the whole demo window. Worth it for zero
reclaim risk. Revert to SPOT after the event.

### Public repo (disqualifying if missed — do FIRST on Oct 8)

Rule: *"a repository whose history does not match the event dates
disqualifies the whole team."* Our private history predates Oct 8 —
squash it to ONE baseline commit on a NEW public repo, then every
commit after lands inside the window:

```bash
./scripts/public-repo.sh https://github.com/<owner>/<new-repo>.git
# then work normally; every post-baseline push keeps history in-window
```

Do this before any other demo-day step — the private `main` keeps
shipping either way, the public repo only needs the baseline + the
commits the judges will actually read.

### Demo-morning checklist (T-60 → T-0)

- [ ] FIRST: run `scripts/public-repo.sh` → new public repo (above) —
  the private history disqualifies the entry if skipped
- [ ] T-60: switch SPOT→on-demand (above) or accept reclaim risk and
  note a Spot interruption kills the task with ~2 min warning — the
  replacement boots cold (~2 min to priced engine even with warm-up)
- [ ] T-45: `curl $NLB/health` — `build_sha` is the build you mean to
  demo; `field_stale: false`; `engine: "alive_core"`
- [ ] T-40: `python3 tools/warm_task.py` exits 0 (engine rows flowing;
  its last line should read `/tiles/health ok — 22.7 MB` — that means
  the self-hosted Delhi vector basemap is live; a 503 means the S3
  artifact is absent and the app falls back to hosted OpenFreeMap
  tiles, which still renders but isn't ours)
- [ ] T-30: phone on the venue's network (NLB is HTTP :80 only — hotel
  Wi-Fi "captive portal" pages break it; a phone hotspot is the safest
  path, verified: the APK hits the NLB direct)
- [ ] T-25: open admin page (`/reports` + aggregates) once — confirm
  light theme + CPCB colors render and the 30 s refresh ticks
- [ ] T-15: run ONE full demo pass offline → consent → vehicle → plan →
  ride → donate → watch the aggregate land in the next /reports tick
- [ ] T-10: kill background apps on the phone; disable auto-lock
- [ ] T-5: `curl $NLB/health` once more — if the task restarted, re-run
  warm_task.py before stepping on stage
- [ ] Backups queued: recorded ride video, iOS-sim capture, localhost
  backend path (see below) — pick whichever survives the hall's network

### Numbers morning-of (the integrity pass — T-45)

`scripts/verify_numbers.sh` re-derives every figure below from the live
service and prints it next to what our docs/script/shotlist quote. One
command; read the FLAGS block; canonical ledger: `docs/plan/NUMBERS.md`.
Caveats found today (2026-10-05): the script needs **python ≥3.12**
(stock macOS `python3` 3.9 dies on an f-string — run it with
`server/.venv312/bin/python3` or Homebrew 3.12 on PATH); and it crashes
`mid(None)` if a probed mode is absent — tonight metro+walk rows were
honestly gone (transit service hours over) so the dose table truncated
after `auto`. Read the partial table + check missing modes separately.

- [ ] `bash scripts/verify_numbers.sh` — read the FLAGS block end to
  end. Any flag = a stale doc line or a field read that moved; fix the
  prose or say the live value, never the other way around.
- [ ] **The spread** — the line is "~35× on a Delhi commute" (range
  31–45× this week). Say the range, not a bare "35×": if a judge hits
  `/v2/plan` during a quiet field hour it may read 28× and we'd be
  caught in a fake-constant.
- [ ] **The ladder** — car-AC vs walk mids move with the field (tonight
  ~13 / ~429 µg on the breathing-zone basis — a ~33× spread,
  `smoke_modifier: 1.11` echoed on the plan wire). Read the verifier's
  dose table; narrate "about thirteen vs over four hundred"
  unless the morning reads differently.
- [ ] **Day windows** — tonight `/v2/day` carried both windows + 3
  populated `decisions` rows (heavy ~22:30 IST → day end @ ~160,
  cleanest 13:30–18:30 @ ~45, day mean ~106): the `decisions:[]` wart is
  fixed on the deployed build (`88e37d5` is in `0908d9ad`+). **The
  endpoint now requires `?lat=`/`?lon`** on `37e55668` (bare call 422s);
  the windows themselves move with the field — an earlier read tonight
  showed a morning peak (07:30–09:30 @ ~171). If `decisions` is empty
  on stage, read `hours[]` + `day_mean_pm25` out loud: "lightest ~45
  mid-afternoon, heaviest ~160 late evening, day mean ~106."
- [ ] **Fires/modifier** — `fires` swings daily (33 → 70 → 79 → 89 this
  week; 89/22 tonight); `smoke_modifier` can be absent (`null`) at
  CP — if so, say "fires feed the field" without a multiplier.
- [ ] **The archive** — `/v2/archive` has been recording hourly since
  Oct 5 20:00 IST (**10 snapshots** tonight: Oct-5 hours 20–23 + Oct-6
  hours 0–5; dozens by demo morning). `?day=` takes `YYYY-MM-DD` only —
  bare `/v2/archive` serves today. The 'what happened' flip IS shipped
  — /city paints recorded hours over forecast and pending hours stay
  unpainted — the honest-gap story is the beat.
- [ ] **Options count** — drifts 16–24 as GTFS transit rows come and
  go (19→24 tonight inside minutes on a field reprice — `metro+walk`
  79.5 and GTFS "Bus 859" 144.1 are present on `37e55668`; transit rows
  are honestly absent outside service hours, not `degraded`). If
  `metro+walk`/`bus` rows are absent at T-45, the road-mode rows alone
  still carry the spread line.
- [ ] **build_sha** — `/health` tonight stamps `37e55668` — the
  lane-briefs deploy (ledger-floor/why-parallel/ingest-parallel live),
  matching the image (the lag wart is resolved on this revision).
  `/admin/api/status` can't be probed without the token — check it at
  T-45; if they disagree on stage, say the ECR image tag or "the build
  from this afternoon", never the stamp.
- [ ] **the self-grade card** — `/v2/skill` is live; on stage read the
  live n + the honest-thin line (any horizon under 5 pairs says
  `thin`). Tonight: 34 pairs — h+1 MAE 14.2, bias +11.2, 72.7% cell /
  85.7% hour band-hit; h+2 26.3/+24.5; **h+3 42.0 and
  h+4 49.0 are graded too** (error widening with horizon is the story);
  h=0 and h≥5 still `thin`.
- [ ] **the why line** — `curl $NLB/v2/why` once before doors; tonight
  it reads *"the air is barely moving — the day's pollution is sitting
  over the city"* (stagnation: VC ~122 m²/s vs ~3,000; fires refused —
  S wind 171°; **trend evaluated, history lit** +0.3 µg over 5.8 h,
  34 snapshots — `cannot_tell` empty).
  On `6e82f290`+ the line ends
  clean; if an older build shows a "— the build you see" tail, read
  the line without it.
- [ ] **Stations/samples** — 24 WAQI instruments, ~70 model samples
  tonight; both thin out after a cold task (~16 / ~41) and recover over
  ~60 min. If you redeployed inside the window, say "recovering to".
- [ ] Reach km figures (`distance_km`) drift hour to hour — if quoted,
  stamp them: "a 25 µg walk budget reached ~84 km of street tonight"
  (car@25 is cap-pinned — `edge_partial:true` at ~54,350 km: say "the
  whole priced graph", not a number).

## iOS sim specifics (only if showing iOS on stage)

- The iOS build runs on this box's simulator (ci15 or any booted device) —
  release target stays Android; iOS is demo-only
- **Set the sim location BEFORE launching** (`simctl location <udid> set
  28.6139,77.2090`): the app reads a one-shot fix at launch; setting it
  mid-run leaves origin/distances on the stale fix until restart
- Upstream MapLibre/RN-iOS-simulator render-thread SIGSEGV — measured
  on this box (virtualized GPU): ~1 in 6 map-churn commits drops,
  identical on ci15 (iOS 27.0) and demo265 (iOS 26.5). Cold launches
  are always clean (8/8). Fixes shipped: deferred search focus
  (643d696), close on keyboardDidHide (6286c11→80cd965), always-mounted
  route sources / endpoint markers / location puck
  (759994f→15f5adf), deferred nav teardown (c18ac92), the
  React-Native Modal replaced by an overlay sheet outright (8db9635),
  and nav camera+puck commit batching with deferred sheet-close work
  (14c4b95). Post-14c4b95 the nav path is verified survivable (4
  stepped location updates + arrival→receipt clean — previously every
  location drive crashed); the residual concentrates at sheet
  mount/unmount commits (search-sheet open, receipt teardown)
- If it drops to SpringBoard: relaunch — every state (consent, vehicle,
  recents, trip ledger, donated aggregates) persists; back on the map
  in ~9 seconds
- For a prepped show: finish onboarding + vehicle pick once before
  stage. To skip the vehicle sheets entirely, seed
  `Documents/vehicle.json` in the sim container with
  `{"cls":"car","fuel":"petrol","year":"y2021_plus"}` — removes two
  churn transitions from the demo path
- Honest stage plan on this box: prefer the recorded iOS take on the
  phone, or run iOS from a bare-metal Mac (the upstream bug is rare
  there); on this sim, expect ~1 relaunch per long demo. Android —
  the release target — has never crashed in E2E
- The sim app points at localhost:8000 — keep the local uvicorn up
  (`PYTHONPATH=core/build312 AGG_TABLE="" .venv312/bin/uvicorn main:app
  --host 127.0.0.1 --port 8000` from server/ — the extension builds into
  `core/build312`, not `core/build`) or set
  EXPO_PUBLIC_API_URL to the NLB
