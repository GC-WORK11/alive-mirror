# ALive-108 — demo-day runbook (Oct 10, offline hall)

Verified against live AWS build `a0e74abe` (ECS ap-south-1, task-def 39,
FARGATE_SPOT); newer commits on `base/v2` ride the next image. Every
number below was read off the running service — they drift with the
field; re-check on the day. Nothing in the product is seeded or faked.

Release APK: sideload build, universal arm64+x86_64, debug-signed —
built with `EXPO_PUBLIC_API_URL=http://alive108-…elb.ap-south-1.
amazonaws.com` (NLB serves :80 only; never `:8000` or `https://`).

## The pitches (one breath each)

- **Consumer:** "Delhi gives you three ways to get there. We tell you what
  each one puts in your lungs — before you leave, while you ride, after
  you arrive."
- **Admin:** "Every shared trip becomes a live sensor over Delhi — this
  screen is the aggregate."
- **Track (Air):** "Exposure and emissions, both measured end-to-end:
  per-250-metre inhaled dose for the rider, per-mode fleet emissions for
  the city, and a privacy-clean community air map that only shows a
  street after three different riders cross it."

## The questions they will ask

**"Why not Google Maps + search the AQI?"**
Google gives travel time; an AQI site gives one city number. We compute
the µg you actually inhale per route option — dose = concentration field
sampled every ~250 m of the polyline × mode ventilation × time, plus a
micro-environment factor (Car AC vs bike is a 30× difference on the same
road). Then emissions per option on real fleet factors (BS-class, fuel,
vintage, occupancy, idle+cold-start).

**"Is the air data real-time? Where from?"**
Yes — keyless, honest provenance, verbatim labels on screen:
- CAMS satellite model + open-meteo, 10 species (PM2.5, PM10, NO₂, O₃,
  CO, SO₂, NH₃, dust, AOD, US/EU AQI), refreshed every 15 min — a
  countdown (`refresh_in_s`) is on the wire
- NASA FIRMS VIIRS/MODIS fire detections (~57 over the belt right now)
  feeding a smoke modifier
- CPCB/WAQI measured stations: adapters exist, dormant without a free
  token — the UI says "stations: no live data" instead of pretending
- kriged concentration field served by our own C++ engine (`alive_core`,
  Eigen) — check `/health` → `engine: "alive_core"` live
- a 120-hour CAMS horizon anchored to the live field — `/depart?hours=120`
  answers "should I leave tomorrow at 8 am instead" with real numbers;
  `/v2/city.next_hours` shows the next 12 h rising/falling

**"How is PM2.5 managed on the backend?"**
15-min ingest worker builds a snapshot → mirrors to S3 (last-good field
survives restarts) → C++ `KrigeField` serves point queries with a real σ
band → dose sampling along route geometry → per-mode physics. Edge of
the field reports `coverage < 1` instead of clamping silently. The 10
other species ride the same lattice; nothing is zero-filled when a feed
doesn't serve it.

**"Why these roads — is it really not the fastest path?"**
The plan engine is an exposure-weighted A* over 1,070,452 real road
edges (2-zone OSM merge, Delhi+Haryana+UP side): each edge's cost is
the inhaled dose for the queried mode (field concentration × microenv
× road uplift × ventilation × dwell), re-priced off a raster of the
live kriged field. Queries answer in ~70ms and return real street
sequences (`via_names`, snap distances) — and every option row's dose
is integrated on the SAME raster the pathfinder minimized over, so
the number shown is the exact criterion the path won on.

**"How fast is the live surface?"**
`/grid` answers are pure functions of the data's own epochs (field
fetch time, forecast fetch time, community obs version) — repeated
paints replay in ~12 ms and can never serve stale data because the
cache key IS the data version; gzip takes the 235 KB layer to ~11 KB
on the wire (~0.5 s end-to-end from India).

**"Street-wise how deep does the data go?"**
The search index is built from the real OSM northern-zone extract —
~94k rows: metro gates, market lanes, mall stores, police stations,
hospitals. `rajiv chowk gate 5` returns "Rajiv Chowk Metro Gate No 5"
top-hit (all eight gates resolve individually); `nai sarak` finds the
book market. The app bundles a 96.8k-entry gazetteer so landmark-level
search works fully offline — no network, no key.

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
~1.8 ms.

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
   donate toggle
6. Delhi Today (sidebar): breath hero, the other 8 species, the 12 h
   forecast strip (CAMS horizon anchored to the live field — hourly
   smoke translates with the real met wind, a semi-Lagrangian
   back-trajectory), "running ±X% vs the decade norm for this hour"
   (9M station-hours)

## Demo flow (admin)

Open `/admin` (token in Secrets Manager `alive108/admin-token`):
- **"where the smoke sits"**: all 13 NCR districts as chips in the
  official CPCB AQI palette — each district's own live pm2.5 read
  (`/v2/districts`), never one number stretched across the map
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
  pattern: same lattice, different species, never re-labeled pm2.5
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
- sources table: model live / met live / fires live / stations no live
  data / **routing** (self-hosted daemon first, public OSRM fallback —
  observed from real route calls, never probed) — the honesty is the
  point
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
- **live feed**: the newest donations ticking in (ago · mode · dose ·
  km · co₂) — donate a trip on stage and watch it land in the next
  30 s refresh. Aggregate-level events only: the feed can say a trip
  happened, never where or whose. Retried posts dedupe — a phantom
  trip can never enter the totals

## Honest limitations (say them first — it lands harder)

- Measured stations are dark without a free WAQI/CPCB token — the field
  is satellite-model only and says so
- A corridor appears only after 3 different devices cross it — early on,
  that table is honestly empty
- Service area is Delhi/NCR + a ~2° margin (Jaipur/Agra/Panipat plan
  fine, flagged `conf: medium`); farther trips get a typed notice,
  never a fabricated route
- iOS is a dev-only test bed — the release target is Android

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
  (`PYTHONPATH=core/build AGG_TABLE="" .venv312/bin/uvicorn main:app
  --host 127.0.0.1 --port 8000` from server/) or set
  EXPO_PUBLIC_API_URL to the NLB
