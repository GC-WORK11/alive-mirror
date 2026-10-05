# ALive-108 — demo-day runbook (Oct 10, offline hall)

Verified against live AWS build `a0e74abe` (ECS ap-south-1, task-def 39,
FARGATE_SPOT); re-verified 2026-10-04 on `6a067ca4` (task-def ~110,
osrm-local sidecar live); re-verified 2026-10-05 on `951eeb3c`
(task-def :141, post dose re-anchor). *[drift note added 2026-10-05
~16:30 IST: live now reports build `d08d9f74`, task-def `:142` — a newer
deploy landed after the :141 verification pass; numbers below were true
when read, re-check on the day per §Ops.]* Newer commits on `base/v2` ride
the next image. Every
number below was read off the running service — they drift with the
field; re-check on the day. Nothing in the product is seeded or faked.

Release APK: sideload build, universal arm64+x86_64, debug-signed —
built with `EXPO_PUBLIC_API_URL=http://alive108-…elb.ap-south-1.
amazonaws.com` (NLB serves :80 only; never `:8000` or `https://`).
For the self-hosted Delhi basemap (street names/POIs to z14 from our
own pmtiles), also pass `EXPO_PUBLIC_TILES_URL=http://65.2.28.40/
tiles/tilejson.json` at bundle time; omitted → hosted OpenFreeMap
fallback, still fine but not ours (docs/plan/handoff.md cont.15).

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
micro-environment factor (a sealed AC car vs walking the same trip
measures ~33× today — CP→Gurugram 5.7 vs 189.8 µg). Then emissions per option on real fleet factors (BS-class, fuel,
vintage, occupancy, idle+cold-start).

**"Is the air data real-time? Where from?"**
Yes — keyless, honest provenance, verbatim labels on screen:
- CAMS satellite model + open-meteo, 10 species (PM2.5, PM10, NO₂, O₃,
  CO, SO₂, NH₃, dust, AOD, US/EU AQI), refreshed every 15 min — a
  countdown (`refresh_in_s`) is on the wire. Params a feed doesn't
  serve stay honestly empty (NH₃ is empty today, not zero-filled)
- NASA FIRMS VIIRS/MODIS fire detections (~70 over the belt right now —
  drifts daily) feeding a smoke modifier (×1.27 at CP today)
- WAQI measured stations LIVE: 24 instruments across NCR feed the
  krige directly (the raw feed is a US-EPA sub-index, not µg/m³ —
  inverted via the EPA breakpoint table, Kalman-smoothed, de-biased
  against the archive). CPCB adapter exists too, dormant without a
  CPCB key — the sources table names what is live, never pads
- kriged concentration field served by our own C++ engine (`alive_core`,
  Eigen) — check `/health` → `engine: "alive_core"` live
- a 120-hour CAMS horizon anchored to the live field — `/depart?hours=120`
  answers "should I leave tomorrow at 8 am instead" with real numbers;
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
live kriged field. A rehearsed query answers in ~0.6 s server-side
(fresh unseen ODs 2–7 s) and returns real street
sequences (`via_names`, snap distances) — and every option row's dose
is integrated on the SAME raster the pathfinder minimized over, so
the number shown is the exact criterion the path won on. Routes within
~50km also return **corridor alternatives**: up to two extra least-dose
re-solves that are penalised for re-using the primary corridor's edges
(they must diverge ≥15% of length to count as a real alternative) — so
the app can show "via Outer Circle" vs "via Vivekanand Marg", not just
one blessed path.

**"How fast is the live surface?"**
`/grid` answers are pure functions of the data's own epochs (field
fetch time, forecast fetch time, community obs version) — repeated
paints replay in ~12 ms and can never serve stale data because the
cache key IS the data version; gzip takes the 235 KB layer to ~11 KB
on the wire (~0.5 s end-to-end from India).

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
124k-entry gazetteer so landmark-level search works fully offline —
no network, no key.

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
   donate toggle
6. Delhi Today (sidebar): breath hero, the other 8 species, the 12 h
   forecast strip (CAMS horizon anchored to the live field — hourly
   smoke translates with the real met wind, a semi-Lagrangian
   back-trajectory), "running ±X% vs the decade norm for this hour"
   (9M station-hours)

## Demo flow (admin)

Open `/admin` (token in Secrets Manager `alive108/admin-token`):
- **"where the smoke sits"**: 28 chips — 15 NCR districts + 13 Delhi
  sub-areas (real OSM admin_level=5 boundaries) — each district's own
  live mean-of-cells pm2.5 read (`/v2/districts`), never one number
  stretched across the map
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
(priced engine serving), then /reports + /v2/city. Exit 0 = warm.
Measured on a live task (2026-10-04): first plan 9.0 s while the
engine repriced, engine rows ~7 s later; a fully cold task needs
~60–100 s to price (graph load ~36 s + first field fetch + raster
sweep) — run this the moment a new task registers healthy, never
cold-call the first demo plan.

### FARGATE_SPOT → on-demand for demo morning (do NOT pre-run; owner executes)

The service runs `capacityProviderStrategy: FARGATE_SPOT weight=1 base=1`
(verified `describe-services` 2026-10-04 — ~$0 but Spot can reclaim any
time, including mid-demo). To pin the task on on-demand Fargate for the
day:

```bash
export AWS_DEFAULT_REGION=ap-south-1
aws ecs update-service --cluster alive108 --service alive108 \
  --capacity-provider-strategy "capacityProvider=FARGATE,weight=1,base=1" \
  --force-new-deployment
aws ecs wait services-stable --cluster alive108 --services alive108
python3 tools/warm_task.py   # re-heat the replacement task
```

Verify: `describe-services` shows capacityProvider FARGATE and the
`deployments[PRIMARY].rolloutState == COMPLETED`; `/health` build_sha
unchanged (same image, new task). Note this REPLACEs the task — the
new one boots cold, so warm it before judging.

### Task-size bump for the demo window (optional, pairs with the above)

The service runs 1 vCPU / 2 GB — one uvicorn worker. A burst of
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
c=td['cont'][0]; c['cpu']=2048; c['memory']=4096
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

Cost note: one FARGATE task (1 vCPU / 2 GB) ≈ ₹3–4/hr in ap-south-1 —
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
