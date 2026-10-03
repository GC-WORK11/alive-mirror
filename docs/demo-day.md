# ALive-108 — demo-day runbook (Oct 10, offline hall)

Verified against live AWS build `4a75e554` (ECS ap-south-1, task-def 23).
Every number below was read off the running service — they drift with the
field; re-check on the day. Nothing in the product is seeded or faked.

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

**"How is PM2.5 managed on the backend?"**
15-min ingest worker builds a snapshot → mirrors to S3 (last-good field
survives restarts) → C++ `KrigeField` serves point queries with a real σ
band → dose sampling along route geometry → per-mode physics. Edge of
the field reports `coverage < 1` instead of clamping silently.

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
6. Delhi Today (sidebar): breath hero, the other 8 species, "running
   ±X% vs the decade norm for this hour" (9M station-hours)

## Demo flow (admin)

Open `/admin` (token in Secrets Manager `alive108/admin-token`):
- headline cards: field age (live badge), samples, donated trips,
  publishable corridors (k≥3), trips switched lighter, daily median,
  cumulative dose, model error vs held-out stations (MAE)
- field panel: serving mode, kriging, σ band, the species line
  (PM10 · NO₂ · O₃ · CO · SO₂ · US AQI — all real)
- sources table: model live / met live / fires live / stations no live
  data — the honesty is the point
- donations: totals incl. "emissions (mid): kg CO₂ · g PM2.5" —
  the emission half of the pitch

## Honest limitations (say them first — it lands harder)

- Measured stations are dark without a free WAQI/CPCB token — the field
  is satellite-model only and says so
- A corridor appears only after 3 different devices cross it — early on,
  that table is honestly empty
- Service area is Delhi/NCR + a ~2° margin (Jaipur/Agra/Panipat plan
  fine, flagged `conf: medium`); farther trips get a typed notice,
  never a fabricated route
- iOS is a dev-only test bed — the release target is Android
