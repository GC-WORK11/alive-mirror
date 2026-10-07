# ALive-108 — demo-day runbook (Oct 10, offline hall)

**Last verified: 2026-10-06 ~11:07–11:40 UTC (16:37–17:10 IST)** —
the demo-reverify-v2 truth pass on live build **`4eb9e1e8`** (ECS task-def
`:181`, image `alive108-api:4eb9e1e8` == `/health` `build_sha` ==
`/admin/api/status` `build_sha`, probed with the token — the lag wart
is resolved on this revision). Every quoted figure re-derived from the
wire this pass; probe rules kept (GETs + /v2/plan + /v2/reroute only).
The drift notes underneath are history — the numbers in the body and
the T-45 checklist are this afternoon's reads.

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
*[demo-day-final pass 2026-10-06 ~05:10–05:30 UTC — build `f4139b24`
(the persistence-blend deploy `f4139b2` + lane briefs): dose ladder
CP→Gurugram car-AC 10.8 / walk 359.1 (**33.3×**, 24 opts incl.
metro+walk 42.9 + GTFS "Bus 729" 89.5); the demo OD India Gate→Huda
City Centre reads car-AC ~12 / walk ~430–450 (**~36×**, 23 opts) — the
option count still swings **19–24** across ODs minutes apart (19, 23,
24 measured). Warm `took_ms` ~47 on the rehearsed OD (the old "~70 ms"
do-not-say is nearly true again; fresh ODs still ~6–8 s server).
Depart now 28.7 → worst 102.7 (+83 h) / best 16.0 (+51 h), 104 slots.
Day windows moved with the morning field: heavy ~19:30 → day end @ ~76 /
cleanest 14:30–18:30 @ ~53 / mean ~63. `/v2/skill` **80 pairs —
h+1..h+9 graded** (h+1 12.2/+9.4 … h+9 63.6/+62.8; h=0, h≥10 thin).
Why: stagnation still — VC ~1,252 m²/s (BLH 846 m + wind 1.5 — the
morning layer, not the night's ~122); fires refused (S wind 138°);
history lit −6.0 µg over 5.7 h / 29 snapshots. Archive **15
snapshots**. Breath ~795 µg ≈ 2.5 cig. Reach walk@25 ~109 km / w@50
~477 / car@25 ~83,642 `edge_partial`. Community all-time unchanged
(22/14/725.9); 24 h: 5 obs / 10.4 km / 432.4 µg avoided. pm25↔no₂
r=+0.55 today. Strip re-minted `f4139b24`: 82 samples, pm2.5 64.5→82.2
(1.27×), Delhi-Gurugram Expressway 29.6% dose-share. Full table:
docs/lanes/demo-day-final-report.md.]*
*[demo-reverify-v2 pass 2026-10-06 ~11:07–11:40 UTC — build
**`4eb9e1e8`** (task-def `:181`, image tag == `/health` ==
`/admin/api/status`, the last one probed **with** the token this time —
`alive108/admin-token` from Secrets Manager). **The fire story flipped
tonight**: `/v2/why`'s `drivers[0]` is now **stubble_smoke** —
*line: "stubble smoke drifting in on the north-west wind"* — 60 fires
on the wire, 14 in the NW belt, 34.0 MW FRP, wind 4.8–5.0 km/h @315–322°
inside the NW gate → `carrying:true`, smoke modifier **×1.24** at CP and
echoed on `/v2/plan` + `/v2/reroute` (modifier math verified:
1 + 14/160 × 2.75 = 1.24 — `server/fires.py`). Every doc line below
that said "fires refused/honestly not claimed" is updated. **Admin flow
changed**: `/admin` is a **public board** now — no prompt on load;
click the masthead "operator sign in" chip → paste token → internals
unlock; `/admin/api/*` all 401 without Bearer, all 200 with it.
Numbers this pass: dose ladder CP→Gurugram car-AC 8.8 / walk 293.2
(**33.3×**, slowest/best 37.4×), 20–21 options (metro+walk 37.5 live —
the demo OD IG→HCC reads car-AC 9.9 / walk 355.0, **35.9×**, 21 opts,
warm `took_ms` 55.8; fresh hits 6.6–7.4 s). `/v2/day`: **both windows
null today** — flat moderate 71–82, day mean 75.6, 1 `decisions` row;
GRAP stage 0 everywhere (aqi indicative 0 @84.9 / day aqi 152 / city
aqi 65). `/v2/skill` **131 pairs — h+0..h+11 ALL graded** (h+0 MAE 2.2
→ h+11 54.5; no `thin` horizons left). Archive **21 snapshots**,
today 17/17 hours, 0 gaps. Depart now 20.9 → worst 113.2 @+63 h
(5.4×) / best 15.5 @+47 h, 109 slots. Reach w@25 136.1 km / w@50
550.6 km / car@25 93,720.8 km `edge_partial`. Breath 576 µg ≈ 1.82 cig.
PM2.5@CP 84.9–88.2 breathing / ~69–71 ambient / US AQI 158–159.
Community all-time unchanged (22/14/725.9); 24 h: 3 obs / 4.6 km /
392.4 µg. Corridors 12/54 publishable; moves 39 trips/7 d (car 82.1%).
Stations 24 → 13 mid-pass (WAQI staleness), samples 61–72. Species:
9 params serve 484/484 (ammonia honestly empty); pm25↔no₂ r=+0.47.
Strip re-minted `4eb9e1e8` (recommended car row, IG→HCC): 82 samples,
pm2.5 52.2→85.9 (1.65×). Full table:
docs/lanes/demo-reverify-v2-report.md.]*
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

## Runbook setup — export once at the top of your shell

Every `curl $NLB/…` and `aws …` command below assumes this block ran
first — paste it verbatim before anything else (the runbook audit
found `$NLB` was never `export`ed anywhere, so the steps failed as
pasted):

```bash
export AWS_DEFAULT_REGION=ap-south-1

# The public base URL — the NLB serves HTTP :80 ONLY (never :8000,
# never https://). Resolve the DNS name from AWS (deploy.sh's
# NLB_NAME=alive108):
export NLB="http://$(aws elbv2 describe-load-balancers --names alive108 \
  --query 'LoadBalancers[0].DNSName' --output text)"
# No-CLI fallback — the current DNS name (resolves to EIP 65.2.28.40):
# export NLB=http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com

curl -s -o /dev/null -w "NLB -> %{http_code}\n" "$NLB/health"   # expect 200
```

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
measures ~33× this afternoon — CP→Gurugram ~9 vs ~293 µg on the
breathing-zone basis, build `4eb9e1e8`; re-check T-45,
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
- NASA FIRMS VIIRS/MODIS fire detections (67 tonight, 15 in the smoke
  belt — drifts daily; 60/14 at the prior read) feeding a smoke
  modifier (×1.08 at CP tonight — SE wind, only marginally inside
  the gate; it reads ×1.24 when NW wind carries belt smoke;
  sometimes absent entirely — say what `/aqi.smoke_modifier` shows,
  and the same modifier is echoed on `/v2/plan` +
  `/v2/reroute`, already inside their dose numbers)
- Measured stations LIVE: **54 instruments across NCR feed the krige
  directly — 24 WAQI + 30 DPCC** (`/health.sources.stations`,
  `source:"waqi+dpcc"` — count drifts as stations go stale mid-day and
  recover; the WAQI raw feed is a US-EPA sub-index, not µg/m³ —
  inverted via the EPA breakpoint table, Kalman-smoothed, de-biased
  against the archive). The OpenAQ v3 path is dormant without a key —
  the sources table names what is live, never pads
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
cache key IS the data version; gzip takes the ~126 KB layer to ~8.5–11 KB
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
   (decade climatology, 125 stations × ~10 years), and the "why tonight" line under the hero —
   `why.line` from `/v2/why` (DelhiToday renders it since `8d032e3`,
   live on `6e82f290`, re-verified on `4eb9e1e8`): this afternoon it's
   stubble smoke — *"stubble smoke drifting in on the north-west wind"*
   (the fire claim flipped: NW wind 315° inside the gate, 14 belt fires /
   34.0 MW → `carrying:true`, modifier ×1.24 — it flips back to refused
   on a southerly wind)

## The judge's first 90 seconds (demo APK = the newest HEAD build)

Install **the newest `alive108-<sha>.apk`**, built at HEAD — the named
binaries `alive108-0b11123.apk` / `alive108-c3bb731.apk` are STALE
(~30 Mobile commits behind, incl. two fixes on this exact flow:
`344b4a9` — the "Where to?" pill occluded under the open home sheet,
the flow's FIRST tap — and `c84b5c2` — phantom re-plan after
receipt-Done, the flow's LAST beat). Build + verify per the build
lane's report: recipe and expected sha256 in
`docs/lanes/apk-v10-report.md` (or the newest `apk-*-report.md` in
`docs/lanes/` if a later build lands); check `shasum -a 256
alive108-*.apk` against that report's value before sideloading. What a
judge sees, in order, with the clock running:

- [ ] **0–5 s — cold-open**: from force-stopped, the app is on the map in
  under a second (measured `+452ms` to first frame on a slow emulator,
  faster on a real phone). No spinner theatre.
- [ ] **~5–15 s — consent**: onboarding lands on the share choice — flip
  it yourself on camera; it's the product's one real decision and it
  persists (`consent.json`/`settings.json` survive restarts). Either
  answer is honest: *"nothing leaves this phone unless I donate — and
  even then only as a k≥3 aggregate."*
- [ ] **~15–30 s — the sparse hero**: before the phone has sampled
  enough, the hero shows the designed-empty state — the band-dot arc of
  today's served pm2.5 curve, "today's air ~N" at the device's cell, and
  the "0 of 3 samples" progress meter. Point at it: *"it won't invent a
  personal number — the meter shows how far it is from earning one."*
- [ ] **~3 s — the first real number**: the ambient read lands ~3 s
  after launch (~3.5 s measured on swiftshader, quicker on the phone's
  GPU) — a live `/aqi` read, not a splash screen.
- [ ] **~30–90 s — three taps to the dose gap**: (1) tap the **"where
  to?"** bar on home, (2) set the pair — tap the "from" row and type
  **India Gate**, then the destination and type **Huda City Centre**
  (the bundled 124k gazetteer answers each even air-gapped), (3) the
  compare sheet opens with every mode's dose — read the gap row: each
  option prints "+N vs lightest · N×". On this OD the sheet reads
  roughly **Car (AC) ≈10 µg vs On foot ≈355 µg — about a 36×
  spread** (live-verified 2026-10-06 on `4eb9e1e8`; re-read at T-45).
- Backup beats if the sheet stalls: the plan call legitimately takes
  ~6–8 s on a fresh OD — keep narrating ("1.07 million edges re-priced
  off this morning's field"); the rehearsed OD answers in ~50 ms warm.

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

Open `/admin` — **it's a public board now** (re-verified on `4eb9e1e8`):
no token prompt on load — a phone judge lands straight on real public
feeds (field map, district chips, KPI tiles with honest "gated" marks).
For the internals (pipeline detail, sources trust table, donations,
corridors, timing, model card), click the masthead **"operator sign
in"** chip → paste the token (Secrets Manager `alive108/admin-token`)
→ the chip flips to "sign out". `/admin/api/*` returns 401 without
Bearer — all 8 endpoints probed 200 with it this pass:
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
  (waqi+dpcc — 54 instruments tonight) / **routing** — osrm-local sidecar in the
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
  Read it as "the scorecard refuses to bluff" — **210 pairs tonight
  and EVERY horizon graded** (h+0..h+11, none `thin`; 131 at the
  afternoon read — it grows with the archive): h+0 MAE 4.2 µg/m³,
  h+1 8.5, h+2 14.4, h+3 22.8 … h+11 54.9 — the honest widening of
  error with horizon is itself the story. The card only scores what
  it has receipts for
- **the why beat** (`/v2/why`, shipped `0908d9ad`; line renders on the
  /city 'why tonight' chip, the landing day-note and DelhiToday on
  `6e82f290`) — *the engine grades its own causality.* This afternoon's real
  read (build `4eb9e1e8`): `drivers[0]` is **stubble_smoke** —
  *"stubble smoke drifting in on the north-west wind"* — 60 fires on the
  wire, 14 in the NW burn belt (34.0 MW FRP), `carrying:true` because
  the wind is 315° NW, inside the smoke gate → smoke uplift **×1.24**
  (the math is on the wire: `1 + 14/160 × 2.75 = 1.24`,
  `server/fires.py`); the **trend arm evaluated AND history is lit**
  (+5.4 µg/m³ over 5.9 h, 28 snapshots) and
  `cannot_tell` is empty — every ingredient got checked. Curl on stage:
  `curl $NLB/v2/why` — the judge sees one sentence plus the honest
  `cannot_tell` block. Narration: *"it tells you why — and what it
  can't tell."*
- **the field archive**: `/v2/archive` replays the recorded field hour
  by hour — snapshots land hourly to S3 (**21 this afternoon**: Oct-5 20:00
  → Oct-6 16:00 IST, since recording began 2026-10-05 20:00
  IST — today is 17/17 hours, zero gaps; `/admin/api/status` shows
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

- OpenAQ is dormant without a free key (WAQI + DPCC cover measured
  stations meanwhile — 54 instruments live) — the sources table names
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
(re-verified `describe-services` 2026-10-06 ~05:10 UTC via boto3 —
running 1/1, task `capacityProviderName FARGATE_SPOT` — ~$0 but Spot can
reclaim any time, including mid-demo). To pin the task on on-demand
Fargate for the day — **T-60: run this verbatim** (the block opens
with a credentials preflight — abort if it fails; a dead credential
means the flip silently never runs and the task stays on reclaimable
FARGATE_SPOT):

*(the flip replaces the task — SAFE for the why-trend/history surfaces
since `268ed54`+`3aea78f`: the series reads the S3 `field/` builds
(bounded parallel fetch), which persist across rollouts — verified live:
history kept 34 builds/5.8h through the `37e55668` rollout. Cold first
builds land in <1min on a fresh task; the only residual is a rare
pathological upstream stall (~2-3min bounded now, `5ec1f2f`).)*

```bash
export AWS_DEFAULT_REGION=ap-south-1

# CREDS PREFLIGHT — must answer BEFORE the flip:
aws sts get-caller-identity --query 'Account' --output text  # expect the deploy account id
echo "region=$AWS_DEFAULT_REGION"                           # must read ap-south-1
# ABORT here if sts fails or the region is wrong — on a dead
# credential the flip silently never happens and the demo stays on
# reclaimable FARGATE_SPOT. Fix creds (aws configure / fresh keys)
# and re-run; do not "try the flip anyway".

# PRE-check (expect FARGATE_SPOT before the flip):
aws ecs describe-services --cluster alive108 --services alive108 \
  --query 'services[0].{cap:capacityProviderStrategy,running:runningCount,taskDef:taskDefinition}'

# THE FLIP — replaces the task with an on-demand one, same image:
aws ecs update-service --cluster alive108 --service alive108 \
  --capacity-provider-strategy "capacityProvider=FARGATE,weight=1,base=1" \
  --force-new-deployment
aws ecs wait services-stable --cluster alive108 --services alive108
# (waiter budget is ~10 min — a slow rollout exits it with an error;
#  re-run the same wait once before assuming failure. A FAILED rollout
#  still leaves the old SPOT task serving — degraded safety, not an
#  outage; decide then: re-run, accept SPOT, or abort per NO-GO.)

# POST-verify — the service strategy AND every listed task must show
# FARGATE (iterate ALL task ARNs: mid-rollout two tasks exist and
# taskArns[0] can be the draining SPOT one — a lingering FARGATE_SPOT
# row before services-stable is the old task leaving, not a bad flip):
#  a) service strategy:
aws ecs describe-services --cluster alive108 --services alive108 \
  --query 'services[0].{cap:capacityProviderStrategy,deploy:deployments[].rolloutState,running:runningCount}'
#  b) every listed task's capacityProviderName + status:
aws ecs describe-tasks --cluster alive108 \
  --tasks $(aws ecs list-tasks --cluster alive108 --service-name alive108 \
            --query 'taskArns[]' --output text) \
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

### Task-size bump for the demo window (optional — INSTEAD of the flip, never both)

**Mutually exclusive with the T-60 flip block:** its `update-service`
already carries the FARGATE strategy, so running it after the flip is
a SECOND full rollout (~10–16 min total) inside the window. Choose
one: the plain flip (same 1 vCPU / 3 GB image, pinned on-demand —
enough for a single demo phone) OR this bump INSTEAD of the flip
(2 vCPU / 4 GB headroom when several judge devices will hit the
service at once).

The service runs 1 vCPU / 3 GB (task-def `:181`) — one uvicorn worker. A burst of
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
commit after lands inside the window.

Prereqs the script dies without: **create the EMPTY GitHub repo
first** (no README, no license — anything in it adds a second root
commit) and **have push auth ready** (SSH key or PAT in the credential
helper) — it `git ls-remote`s the URL before anything else. It never
touches your worktree: it writes one commit holding the tip-most tree
of {base/v2, main} via `git commit-tree` and pushes it as `main`.

```bash
./scripts/public-repo.sh https://github.com/<owner>/<new-repo>.git
# then work normally; every post-baseline push keeps history in-window
```

Do this before any other demo-day step — the private `main` keeps
shipping either way, the public repo only needs the baseline + the
commits the judges will actually read.

### Demo-morning checklist (T-60 → T-0)

*Companion checklists — don't run them twice, read them once:
`docs/submission/submission-checklist.md` §3 is the richer morning
sequence (token probe, both-networks health check, airplane-mode video
play, the NO-GO list); `docs/plan/go-nogo.md` is the gate table this
section was distilled from.*

- [ ] FIRST: run `scripts/public-repo.sh` → new public repo (above) —
  the private history disqualifies the entry if skipped. Prereqs:
  the EMPTY repo already created (no README/license) + push auth in
  the credential helper.
- [ ] T-60: credentials preflight, then switch SPOT→on-demand (above)
  — `aws sts get-caller-identity` + region `ap-south-1` must answer
  before the flip or the flip silently never happens. Or accept
  reclaim risk and note a Spot interruption kills the task with ~2 min
  warning — the replacement boots cold (~2 min to priced engine even
  with warm-up)
- [ ] T-45: `curl $NLB/health` — `build_sha` is the build you mean to
  demo; `field_stale: false`; `engine: "alive_core"`
- [ ] T-40: `python3 tools/warm_task.py` exits 0 (engine rows flowing;
  its last line should read `/tiles/health ok — 22.7 MB` — that means
  the self-hosted Delhi vector basemap is live; a 503 means the S3
  artifact is absent and the app falls back to hosted OpenFreeMap
  tiles, which still renders but isn't ours)
- [ ] T-30: phone on the venue's network (NLB is HTTP :80 only — hotel
  Wi-Fi "captive portal" pages break it; a phone hotspot is the safest
  path, verified: the APK hits the NLB direct). Battery >80% + power
  bank + cable on the table; hotspot already armed as the fallback
  uplink.
- [ ] T-30: admin token physically at hand (phone note or paper, not a
  laptop you'll have to unlock on stage) — Secrets Manager
  `alive108/admin-token`, the `ALIVE_ADMIN_TOKEN` env the task def
  injects (`aws secretsmanager get-secret-value --secret-id
  alive108/admin-token --query SecretString --output text`). Needed
  for the `/admin` "operator sign in" chip if a judge asks for the
  internals; the public board renders without it.
- [ ] T-25: open `$NLB/admin` in the demo browser — the public board
  renders tokenless; confirm light theme + CPCB band colors render and
  the live feed ticks (~30 s refresh; the "operator sign in" chip +
  token unlock the internals). The totals a donation increments, by
  curl: `curl -s $NLB/community` → `obs_total` / `obs_today` /
  `contributors` / `latest_obs_age_min`. (`/reports` is the k≥3
  corridor GeoJSON — honestly empty until 3 devices cross a street;
  never the surface a donation lands on.)
- [ ] T-15: run ONE full pass on the pre-seeded flow → consent →
  vehicle → plan → ride → receipt → **donate**. Donated offline, it
  honestly queues on the device — receipt reads "saved — will send
  when back online", the status pill counts the outbox ("N saved to
  send") — and auto-flushes on the first successful request after
  reconnect. Then verify it LANDED: `curl -s $NLB/community` →
  `obs_total`/`obs_today` +1 and `latest_obs_age_min` ~0, or the
  signed-in admin live feed shows it within ~30 s. One device can
  NEVER make a corridor — `/reports` is k≥3-gated; don't look there.
- [ ] T-10: kill background apps on the phone; disable auto-lock
- [ ] T-5: `curl $NLB/health` once more — if the task restarted, re-run
  warm_task.py before stepping on stage
- [ ] Before leaving: boot the localhost backup ONCE so it's proven —
  `docker compose up --build` from the repo root → `curl
  http://localhost:8080/health` returns 200 (compose builds
  `server/Dockerfile`; a fresh box needs Docker + a ~5–10 min image
  build; the `.venv312` uvicorn line in §iOS is the no-Docker path).
  Fallback only — the prod NLB is the primary.
- [ ] Backups on the playing device: `docs/video/cut1.mp4` +
  `docs/video/cut2.mp4` copied onto the demo phone and played once in
  airplane mode — the "if live breaks" fallback. iOS-sim capture +
  the localhost path (above) as the deeper fallback — pick whichever
  survives the hall's network.

Budget check (audit-verified): scripted blocks cost ~31–35 min inside
the 60 → ~25 min slack. The new preflight/token/battery lines add
<2 min total; the localhost boot happens before leaving, not inside
the window. The task-size bump is OUTSIDE this budget — INSTEAD of
the flip, never on top of it.

### Numbers morning-of (the integrity pass — T-45)

`scripts/verify_numbers.sh` re-derives every figure below from the live
service and prints it next to what our docs/script/shotlist quote. One
command; read the FLAGS block; canonical ledger: `docs/plan/NUMBERS.md`.
Caveats found today (2026-10-05): the script needs **python ≥3.12**
(stock macOS `python3` 3.9 dies on an f-string — it self-resolves a
`.venv312`→3.14→3.13→3.12→python3 fallback chain since `1ce7678`/`4a9f4f7`,
so just run it). The old `mid(None)` crash on an absent mode is FIXED
(`mid()` guards non-dicts, `1ce7678`) — a missing mode now renders as a
missing row, not a truncated table; metro+walk rows are honestly gone
outside transit service hours — read the partial table + check missing
modes separately.

- [ ] `bash scripts/verify_numbers.sh` — read the FLAGS block end to
  end. Any flag = a stale doc line or a field read that moved; fix the
  prose or say the live value, never the other way around.
- [ ] **The spread** — the line is "~35× on a Delhi commute" (range
  31–45× this week; 33.3× on the script OD and 35.9× on the demo OD
  this afternoon). Say the range, not a bare
  "35×": if a judge hits
  `/v2/plan` during a quiet field hour it may read 28× and we'd be
  caught in a fake-constant.
- [ ] **The ladder** — car-AC vs walk mids move with the field (this
  afternoon ~8.8 / ~293 µg on CP→Gurugram — a ~33× spread; the India
  Gate→Huda City Centre demo OD reads ~9.9 / ~355, ~36× —
  `smoke_modifier: 1.24` echoed on the plan wire). Read the verifier's
  dose table; narrate "about nine vs three hundred"
  unless the morning reads differently.
- [ ] **Day windows** — this afternoon `/v2/day` carried **neither
  window** — flat moderate air all day (71–82 µg/m³): `heavy_window`
  and `cleanest_window` are honestly `null`, `decisions` carried 1
  plain-words row ("no meaningful window today"), day mean ~76. The
  `decisions:[]` wart is fixed on the deployed build (`88e37d5` is in
  `0908d9ad`+). **The
  endpoint requires `?lat=`/`?lon`** (bare call 422s);
  the windows themselves move with the field — earlier reads today
  showed both populated (heavy ~19:30 → day end @ ~76 / cleanest
  14:30–18:30 @ ~53). If `decisions` is empty
  on stage, read `hours[]` + `day_mean_pm25` out loud — today that's
  "moderate all day, ~71 rising to ~86 into the evening, day mean ~76."
- [ ] **Fires/modifier** — `fires` swings daily (33 → 70 → 79 → 89 → 60
  this week; **60 total / 14 in-belt / 34.0 MW tonight**); tonight the
  NW wind carries them — `smoke_modifier: 1.24` at CP, echoed on
  `/v2/plan` + `/v2/reroute`. It can still be absent (`null`) on a
  southerly day — if so, say "fires feed the field" without a
  multiplier.
- [ ] **The archive** — `/v2/archive` has been recording hourly since
  Oct 5 20:00 IST (**21 snapshots** this afternoon: Oct-5 20:00 → Oct-6
  16:00 IST; today 17/17 hours recorded, zero gaps; dozens by demo
  morning). `?day=` takes `YYYY-MM-DD` only —
  bare `/v2/archive` serves today. The 'what happened' flip IS shipped
  — /city paints recorded hours over forecast and pending hours stay
  unpainted — the honest-gap story is the beat.
- [ ] **Options count** — drifts 16–24 as GTFS transit rows come and
  go (measured 20 on CP→Gurugram and 21 on IG→HCC this
  afternoon — `metro+walk` 37.5/43.9 present on
  `4eb9e1e8`, `transit.real_feeds bus+metro true` on `/health`; transit rows
  are honestly absent outside service hours, not `degraded`). If
  `metro+walk`/`bus` rows are absent at T-45, the road-mode rows alone
  still carry the spread line.
- [ ] **build_sha** — `/health` this afternoon stamps `4eb9e1e8`,
  matching image `alive108-api:4eb9e1e8` on task-def `:181`
  (the lag wart is resolved on this revision).
  `/admin/api/status` **was probed with the token this pass** — it
  stamps the same `4eb9e1e8`; re-check at
  T-45; if they disagree on stage, say the ECR image tag or "the build
  from this afternoon", never the stamp.
- [ ] **the self-grade card** — `/v2/skill` is live; on stage read the
  live n + the honest-thin line (any horizon under 5 pairs says
  `thin`). This afternoon: **131 pairs — h+0..h+11 ALL graded** (h+0
  MAE 2.2/+1.0, 93.4% cell / 100% hour band-hit; h+1 9.4/+6.6; h+2
  18.5/+14.2; h+3 27.1 → h+11 54.5; error widening with horizon is the
  story); no `thin` horizons left tonight.
- [ ] **the why line** — `curl $NLB/v2/why` once before doors; this
  afternoon
  it reads *"stubble smoke drifting in on the north-west wind"*
  (**fires claimed tonight**: 60 on the wire, 14 in the NW belt /
  34.0 MW FRP, wind 4.8 km/h @315° inside the gate → `carrying:true`,
  uplift ×1.24 — verify it stayed NW on the day; a southerly wind
  flips it back to refused; **trend evaluated, history lit**
  +5.4 µg over 5.9 h, 28 snapshots — `cannot_tell` empty).
  On `6e82f290`+ the line ends
  clean; if an older build shows a "— the build you see" tail, read
  the line without it.
- [ ] **Stations/samples** — 54 instruments tonight (24 WAQI + 30 DPCC;
  earlier passes saw 13–24 on the WAQI-only feed — stations go stale
  mid-day, honest drift, recovers); ~61–72 model samples. Both thin
  out after a cold task and recover over ~60 min. If you redeployed
  inside the window, say "recovering to".
- [ ] **Breath/community** — the breath hero reads ~576 µg ≈ 1.8
  cigarettes this afternoon (it scales with the day's field mean; evening
  reads run higher — ~2.5–3.7 cig this week); community all-time 22
  trips / 14 contributors /
  725.9 µg avoided, 24 h: 3 obs / 4.6 km / 392.4 µg.
- [ ] Reach km figures (`distance_km`) drift hour to hour — if quoted,
  stamp them: "a 25 µg walk budget reached ~136 km of street this
  afternoon"
  (car@25 is cap-pinned — `edge_partial:true` at ~93,721 km: say "the
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
