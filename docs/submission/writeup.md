# ALive-108 — Builder Center written submission

*Draft for the AWS × WeMakeDevs Environmental Hacks (Track 01 · Air) submission
form and the Builder Center long-form post. Every number below was read off the
live service or traced to a repo file on 2026-10-05 — re-verified ~22:15 UTC on
build `80a15258`, extended 2026-10-06 on build `ce01ec5c` (the DPCC-ingest
deploy), and **re-pinned 2026-10-07 ~11:00 UTC (~16:30 IST) on build
`698cf808`** — prod's live image (`GET /health` → `build_sha`), verified with
`scripts/verify_numbers.sh` at zero flags. Today's landings named where they
belong: the cinematic route chooser (`e2ff634`), the parali `cause_note` news
line (`795ff3b`), real admin sign-in (`b563da2`), map depth r6 (`b47ffd4`),
the iOS cold-launch crash residual killed (`9fbd851`), and the codebase-truth
censuses (`1627a13`/`b633a2d`). `GET /health` reports
`sources.stations.count=52`, `source:"waqi+dpcc"` — the count drifts 52–54 as
instruments age in and out of feed health. Grep-able sources in brackets.
`docs/plan/NUMBERS.md` is the canonical ledger;
`scripts/verify_numbers.sh` re-derives every figure live. Nothing is invented.*

**Live now:** http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com
(public API + dashboards; `GET /health` is open)

---

## The lede

**Your lungs' ledger for Delhi: what you breathed today, where it cost you, and
when tomorrow's air is worth going out in — no device, nothing personal
leaves the phone.**

Delhi is the most polluted megacity on earth — winter PM2.5 runs 10–20× the WHO
guideline through October–February [`docs/00-executive-thesis.md`]. Every tool
people have today sells *"how bad is it"* — an AQI lookup. The graveyard says
that doesn't retain: Plume Labs' $200 hardware dosimeter was discontinued in
2023; BreezoMeter's consumer app was killed twice [`docs/plan/alive-depth.md`].
What retains is *"what do I do"* — and nobody has ever shipped the personal
measurement that makes it answerable.

## The product

**ALive-108 is a personal PM2.5 dosimeter without hardware.** Personal-exposure
reconstruction — timeline × concentration surface → individual dose — is an
established research method that nobody ships to consumers; Plume needed a
device, we need nothing. The concentration field is already sampled per-cell
per-hour, and the phone already knows where it was. Your day is reconstructed
**on-device** — the only things that ever leave the phone are consented,
privacy-floored aggregates (nothing publishes below **k=3 distinct devices
over 72 h** — `min_k` is literally on the wire). We can't leak what we never
take — and we never take a trip: donations fold into cell/hour/day aggregates
at ingest, so **no per-trip row exists in memory, on disk, or in S3**
[`docs/plan/alive-depth.md`; `PRIVACY.md`; `server/community.py`;
`GET /v2/city/moves` — live].

Exposure-aware routing is one feature inside it — the proof that the field and
the dose math are real enough to decide with.

## The architecture: field → engine → dose → ledger

- **Field.** A concentration surface rebuilt every 15 minutes from **52
  live ground instruments — WAQI + DPCC** (the second adapter shipped
  Oct 6 after our own holdout found the blind spots — see the holdout
  section below; the count churns 52–54 as instruments age in and out of
  feed health) + **~97 CAMS/open-meteo model samples** +
  **NASA FIRMS fire detections** (44 at last read, 12 in the NW belt; the
  claim is wind-gated — ×1.24 while the NW fetch carried, downscaled to
  ×1.06 and named-but-refused on today's SW wind), kriged with a
  real σ band per cell.
  Age on the wire at this read: ~7 min [`GET /health`, `GET /aqi` — live
  2026-10-07 ~11:00 UTC]. And once
  an hour the served field itself is written to durable storage — the archive
  snapshots the real served surface into S3 + a local mirror, hour-bucketed in
  IST: Delhi's air is *history*, not just forecast. `GET /v2/archive` replays
  a day hour-by-hour (`basis:"recorded"`); a missing hour stays an honest gap,
  never backfilled [`server/archive.py`, `server/v2/archive.py` — live].
- **Engine.** Our own C++ engine (`alive_core`, pybind) with a bit-exact Python
  twin — kriging, dose integration, and path search. The A* twin and the new
  bounded-Dijkstra reach are asserted to settle the *identical* edge set on
  both engines, and the dose/emission kernels are parity-tested to 1e-9
  ("bit-identical in practice") [`server/tests/test_reach.py`,
  `test_parity_dose.py`, `test_parity_series.py`]. That engine re-prices
  **1,070,459 road edges (903,058 priced)** so dose is a first-class routing
  criterion [`GET /health → routing` — live].
- **Dose.** Honest physics, not a lookup:
  > dose = concentration (µg/m³) × micro-environment factor × ventilation rate
  > (L/min) × time — integrated every ~250 m along the actual route geometry.
  Micro-environment and ventilation are anchored to measured Delhi commuter
  literature (Goel 2015, Apte 2011, Zuurbier 2009), not defaults
  [`server/exposure.py`, `docs/03-models.md`].
- **Ledger.** Trips receipt in µg and persist to `ledger.json` **on the phone**
  (500-trip cap, delete-all, no account). Donation is opt-in: a donated trip
  is trimmed on-device, then re-trimmed + thinned + rounded **server-side** and
  folded into ~500 m cells at ingest — no per-trip row exists in any store.
  Per-device history is readable only by the holder of the raw device token,
  and `DELETE /v2/ledger` wipes it [`server/v2/trip.py`, `server/v2/ledger.py`,
  `PRIVACY.md`].

## What the dosimeter answers today

Three questions, three shipped surfaces:

- **"What did today cost me?"** — the ledger: every trip's inhaled µg, on the
  phone, with the receipt (µg + CO₂ band + where it accumulated). The city side
  of the same ledger is public — a live counter (`GET /community`): 24
  contributors / 44 trips all-time — 5 today / 31.4 km / 312.9 µg *avoided*
  today, and 1,278.9 µg of smoke counted as *avoided* all-time
  [`GET /community` — live, read Oct 7 ~16:20 IST — it grows daily].
- **"When is tomorrow's air worth going out in?"** — `GET /v2/day`: the
  morning card for a point — today's heavy window and cleanest slot with a
  real band each, plus the decisions they change. Live at Connaught Place
  today: a flat-moderate day — `day_mean ~68`, both windows honestly
  `null`, and the `decisions` row says so out loud ("no meaningful window
  today — moderate air all day (61–75 µg/m³)") instead of inventing one;
  on a swing day the same card splits the stretch from the slot with a
  real band each [`GET /v2/day?lat&lon` — live].
- **"Where can my lungs go inside my budget?"** — `GET /v2/reach`: a bounded
  Dijkstra over the same directed-edge-state search as the router — no
  heuristic, no destination — settling every edge whose inhaled dose stays
  under `budget_ug`. The returned set is the real Dijkstra frontier as
  polylines, never a smoothed circle. Live today: a **25 µg walking budget
  from Connaught Place settles ~3,800 road segments (~168 km of street —
  directed edges, so a two-way street counts in both directions)**;
  ≤50 µg walks ~11,400 segments (~618 km); a sealed car on a **25 µg**
  budget settles ~993k edges, ~92,800 km (`edge_partial:true` — the
  2M-state cap binds; the veil paints a 90,000-edge strided sample of the
  settled frontier, so it shows the frontier, not a blob)
  [`GET /v2/reach` — live;
  `server/v2/reach.py`; painted as the "where can your lungs go?" veil on
  `/city`].

## The feature the judges will poke: dose-priced routing

Same city, same minutes — the mode you pick decides what you inhale. Measured
live on the demo trip (Connaught Place → Gurugram, 23.7 km) today, 17 options
[`POST /v2/plan` — live, read 2026-10-07 ~11:05 UTC on build `698cf808`,
breathing-zone basis (`smoke_modifier: 1.06` on the wire); the count drifts
16–24 as engine/transit rows come and go]:

| mode | inhaled dose (µg PM2.5, mid) | ≈µg/km |
|---|---|---|
| sealed AC car | **7.2** | ~0.3 |
| car, windows open | 13.0 | ~0.5 |
| bike / scooter | 16.5 | ~0.7 |
| bus | 18.8 | ~0.8 |
| auto-rickshaw | 21.2 | ~0.9 |
| metro + walk | 32.5 | ~1.4 |
| bus (GTFS timetable row) | — *(absent at this read — service-hours dependent; ~69–144 when the arm serves)* | — |
| cycle | 105.4 | ~4.4 |
| **walk** | **237.9** | ~10 |

**~35× on a Delhi commute** (33.0× measured today; 31–45× across ODs this
week — it is a living ratio, not a constant) — and
it matches published Delhi measurements: walking inhales ≈28× the metro per
km, an auto-rickshaw ≈5× (Sci. Total Environ. 2021; Discover Atmosphere 2025 —
`server/exposure.py` header, `docs/03-models.md`). The honest surprise the
table shows on daytime reads: **metro+walk doses ~4.5× a sealed car** — the
coach is clean,
the road-level walks at both ends are not. The engine also returns least-dose
corridor alternates that must diverge ≥15% of length to count (measured
19–96% divergent) — "via Outer Circle vs via Vivekanand Marg", not one blessed
path [`docs/plan/demo-script.md` numbers sheet].

## What nobody else does

- **A field that moves.** `/v2/city` serves the next 12 hours hour-by-hour —
  driven by a 5-day CAMS forecast anchored to the live field (τ=9 h;
  today's stamped read runs ~61 → ~78 µg/m³ over the strip — the live shape
  drifts nightly)
  [`GET /v2/city → next_hours`; `GET /depart` — live]. `/depart` answers
  "leave now or later?" in micrograms: same trip, ~20 µg now vs ~46 µg at
  tomorrow's worst hour (**~2.3×** today — it has run ~8× this week), and
  `pct_less_vs_now` hits 0 so the leave-later row honestly hides rather than
  sell a non-saving.
- **Privacy as architecture, not policy.** Donations fold into
  cell/hour/day aggregates at ingest — *no per-trip row exists in memory, on
  disk, or in S3*, so there is nothing per-person to leak, lose, or subpoena.
  The raw-coords `/observe` endpoint is retired (**410 Gone**); uvicorn's
  access log is off and the app's own request log writes path templates only,
  with coordinates and tokens on a denylist; the contributor id is a 64-bit
  CSPRNG that rotates every 30 days. And k≥3 everywhere: 12 of 55 tracked
  corridor cells are publishable today; the other 43 are honestly suppressed,
  the suppression field (`mode_share_suppressed_trips`) ships on the wire
  [`PRIVACY.md`; `server/community.py`, `server/observability.py`;
  `GET /community`, `GET /v2/city/moves` — live].
- **History, not just forecast.** Once per IST hour the API snapshots the
  field it is actually serving — mid, σ band, confidence, source counts —
  into durable storage (`archive/field-YYYYMMDDHH.json.gz` on S3 + a local
  mirror). `GET /v2/archive` replays a day hour-by-hour; gaps are serialized
  as gaps, never interpolated. Recording since Oct 5 — the `/admin` archive
  tile shows it live [`server/archive.py`; `GET /v2/archive` — live].
  **`GET /v2/skill` goes further — the forecast grades itself**: every
  served hour is later compared against the field that actually shipped,
  and the wire publishes the decay ladder honestly (304 graded pairs today:
  90.2% band-hit at h+0 down to ~38% by h+11, `basis:"self-graded"`). The
  model marking its own homework
  is the product's calibration habit made public [`GET /v2/skill` — live].
- **Emissions alongside dose.** Each option carries a CO₂ + tailpipe-PM2.5
  band on real Delhi fleet factors (BS-class, fuel, idle, cold-start) —
  metro+walk: 0.42 kg CO₂, zero tailpipe PM [`/v2/plan` wire].
- **The ledger is yours.** On-device file, no account, opt-in donation,
  delete-all on the phone and `DELETE /v2/ledger` on the server — the
  receipt says "kept on this phone only" and means it.

## Working execution — the numbers we measured, not claimed

| claim | value | source |
|---|---|---|
| Held-out uncertainty-band coverage | **95.2 %** at ±2σ over **3,550 station-hours / 85 stations** (nominal 95.4 %) — σ is measured, not tuned | `server/data/field_validation.md` |
| Independent holdout vs 30 govt DPCC stations | pre-ingest: MAE 27.1 (blind sites 22.8) → post-ingest **MAE 6.2** (blind sites 10.5), all 30 at `nearest_sample_km=0.0` | `docs/lanes/accuracy-holdout-report.md`, `holdout-reverify-report.md` |
| Live instruments feeding the field | **52 stations** — WAQI + DPCC both feeds `ok` (`source:"waqi+dpcc"` on the wire since Oct 6; count drifts 52–54 as instruments age) + ~97 model samples, field age ~7 min, 15-min refresh visible | `GET /aqi`, `GET /health` |
| LOO calibration vs live instruments | MAE 8.8 µg/m³, bias +0.2, n=70 (WAQI+DPCC, krige refit per held-out station) | `GET /aqi → calibration` |
| Archive replay (clean-air window) | MAE 22.0 µg/m³, bias +51.6 % — we publish that we over-read in clean air | `server/data/field_validation.md` |
| Plan latency | ~1.1–1.2 s warm server-side (CP→GG 1.07 s · IG→HCC 1.20 s today); fresh unseen ODs ~2–9 s | `POST /v2/plan → took_ms` |
| Reach latency | ~1–2 s wire on walk budgets ≤50 µg; ~5–10 s for a ~890k-edge car reach (partial — 2M-state cap) | `GET /v2/reach` |
| Mode dose gap, CP→Gurugram | **~35× on a Delhi commute** — 33.0× live today (build `698cf808`, bz basis); 31–45× across ODs this week | live probe + `docs/plan/demo-script.md` |
| Search | 97,447 corpus entries (16,949 real address rows); 172/174 top-1 in a live battery (98.9 %), p50 ~470 ms over the NLB; bundled on-device gazetteer 124,311 rows | `server/data/corpus/STATS.md`, `docs/plan/demo-script.md` |
| Engine speed | C++ search index p50 0.189 ms — ~88× the Python twin, asserted bit-identical | `docs/plan/bench-results.md` |
| Self-hosted basemap | 22.7 MB pmtiles built from Geofabrik OSM, z0–14, live at `/tiles/health` | `GET /tiles/health` |
| Landmark-truth sweep | 23 fabricated landmark geocodes purged; top-3 of every flagship query must land within 1.5 km of truth — pinned by `test_search_quality.py` | commit `2c4cab4` |

## The holdout we ran on ourselves — and what we did about it

On the evening of Oct 6 we audited the served field against **30 government
DPCC stations** — a different instrument network than anything the field
ingests — classifying each site by whether the field provably cannot see it
(`nearest_sample_km ≥ 1.0` = blind). Three probe rounds, 81 observations,
nothing tuned, nothing filtered [`docs/lanes/accuracy-holdout-report.md`]:

| class | stations | obs | MAE µg/m³ | RMSE | bias |
|---|---|---|---|---|---|
| GAP — provably blind (1.5–5.8 km) | 7 | 16 | **22.8** | 26.5 | +3.2 (+6%) |
| LIVE-ADJ — instrument in the blend | 6 | 16 | **16.4** | 19.3 | −9.2 |
| ANCHOR — model point on-site | 17 | 49 | **31.9** | 39.8 | −24.6 |
| **All 30 sites** | 30 | 81 | **27.1** | 34.2 | −16.0 |

The blind sites were the *best-behaved* class (~23 MAE, ~zero bias) — but the
misses were real at anchors: Jahangirpuri read 143 while we served 73 (−68),
Sonia Vihar −63, Rohini −53. Local hotspots flare up to 2× past a blend built
from instruments elsewhere; that's exactly why the API serves a band plus the
distance to the nearest real reading, not a confident point.

Then we closed them: `server/ingest_dpcc.py` ingests those same DPCC 5-min
pages behind `ALIVE_DPCC_INGEST` — the site's nav bar hides a 30-station
superset whose 6 unlisted stations were precisely our blind spots (IGNOU, JNU,
CWG Akshardham, NSUT West, Talkatora, SBV Delhi Cantt). Unit tokens are
asserted per row (µg/m³ refused if the site ever switches to indices); stale
and physically impossible rows (PM2.5 > PM10) are dropped. **Live since Oct 6
(build `ce01ec5c`): all 7 former blind spots now carry an instrument at ~0 km**
[`docs/lanes/ingest-dpcc-report.md`].

And the prediction is now a measurement — we re-ran the identical holdout on
prod ~24 h later (Oct 7, two rounds, 60 obs, same method): **former-GAP MAE
22.8 → 10.5 µg/m³** (bias +0.8), **all-30 agreement 27.1 → 6.2**, worst single
miss 19.1, every station at `nearest_sample_km = 0.0`. Kept honest: the two
largest residuals are instruments reading far off their own region (JNU 83.6
vs neighbors ~55–65; IGNOU carries the same suspect pm25/pm10≈0.15 signature
flagged pre-ingest) — instrument-vs-blend disagreement, not blindness, left in
the table unexcluded. The honesty frontier moved out of the city: inside the
instrumented ring every cell is ≤~4 km; the NCR rims run 5.5–15.7 km and the
API says so on the wire via `nearest_sample_km`
[`docs/lanes/holdout-reverify-report.md`].

And a second live watch ran the same evening — 14 probes across ~8 h of the
parali ramp, through three mid-watch deploys: the stubble-fire claim followed
the wind *both* directions (claimed ×1.24 at 344°, refused ×1.07–1.08 at
15°→139° easterly, math re-derived per probe), the trend recorder caught the
regime flip live (−7.5 → +35.7 µg over ~6 h), and one dose-ratio flag
decomposed to a verified spatial gradient, not a scaling bug
[`docs/lanes/field-watch-2-report.md`].

## Where AWS fits (deployed, not claimed)

- **ECS Fargate** (ap-south-1, FARGATE_SPOT, 1 vCPU / 3 GB) runs the FastAPI
  service + C++ pybind engine + osrm-local router sidecar — one service, one
  task; the deploy reports `build_sha 698cf808` on
  the open wire [`GET /health` — live; the ECR image tag is the commit
  sha].
- **Network Load Balancer + Elastic IP** gives the stable public URL above
  (`alive108-….elb.ap-south-1.amazonaws.com`, resolving to 65.2.28.40) — it
  survives every redeploy; each deploy re-registers the live task's IP.
- **CodeBuild → ECR → task definition**: every deploy builds the image in
  AWS (`buildspec.yml` → docker build → push → `update-service`).
- **S3** keeps the last-good field snapshot (the field survives task
  restarts), the community aggregate state, the hourly field archive
  (`archive/field-*.json.gz`), and the pmtiles artifact that
  hot-swaps into running tasks.
- **DynamoDB** (`alive108-agg`) holds only aggregate trip counters — no user
  rows exist anywhere.
- **Secrets Manager** holds the admin token + upstream keys — nothing in the
  repo.
- **EventBridge Scheduler** (`alive108` group) drives a daily rollup and a
  daily validation run (both ENABLED live, run as one-off Fargate tasks —
  their IST names lie: the crons read UTC, `alive108-rollup-daily-0030IST`
  fires 00:30 UTC and `alive108-validate-weekly` actually fires daily
  20:30 UTC; the committed `infra/schedules/*.json` are provisioning
  templates with placeholder ARNs — the live schedules, their exit-0
  runs, and this drift are documented in `docs/plan/ops-handover.md`).
  The 15-minute field-rebuild cadence runs in-app (the
  `alive108-ingest-15min` schedule stays disabled, `docs/plan/ops-handover.md`).
- **CloudWatch + Budgets** — three armed alarms (field age, ingest-emitter
  dead, target down) fanning to a confirmed SNS email, the ops dashboard,
  and a $50/month budget alarm — verified live during the ops handover
  [`docs/plan/ops-handover.md`].
- **OpenAQ's public S3 archive** is the decade climatology source
  (125 stations × a decade of hourly readings, medians by month×hour,
  baked into the image).
- Cost: **$0.00 net billed** over the last 7 days inside the promo credits
  (~$50/month run-rate absorbed — ledger in `docs/plan/ops-handover.md`);
  Fargate Spot keeps it there.

## Security & reliability — measured this week

This week was spent hardening and proving, not just shipping:

- **Real admin sign-in** (`b563da2`): the operator token stopped living in
  `sessionStorage`. `POST /v2/admin/login` trades it once for an
  HMAC-signed, stateless `HttpOnly` + `SameSite=Strict` cookie (8 h);
  the sessionStorage token and the `prompt()` are deleted. Guests land on
  a gate card (no gated fetch fires); a copied cookie rides the same
  plaintext transport as the Bearer it replaces until TLS lands — open
  and named [`server/main.py` (`/v2/admin/login`), `docs/lanes/admin-auth-report.md`].
- **Pentest pass closed the mechanics** — a per-socket-peer rate limiter
  and geo/implied-C bounds went in with it; the threat model is published
  in the same lane report (XSS token-theft path dead by construction;
  cookie theft-on-wire stays open until a 443 listener exists, and the
  report says so).
- **The iOS sim cold-launch SIGSEGV residual is dead** (`9fbd851`): the
  remaining render-thread kill was a JS-thread commit race — the Promise
  hop in `9fbd851` takes it to **0/30** drive-bys (was 12/30 ≈ 40%).
  Release target stays Android — the rig note is
  `docs/lanes/ios-residual-report.md`.
- **A real P0 was caught and sealed**: a broken landing-page template
  shipped briefly today; the fix added a CI gate (`node --check` on every
  inline script inside served HTML) so the class cannot re-ship
  [`docs/lanes/script-guard-report.md`, `scripts/check_inline_scripts.py`].
- **Codebase-truth census** (`1627a13`/`b633a2d`): every endpoint verified
  live or honestly absent — zero stub endpoints; the three dead switches
  found are wired or documented.
- **Deploys are boring on purpose**: `scripts/deploy.sh` re-verified twice
  today (CodeBuild → ECR → task-def → NLB register → healthy; rollback is
  one flag); three CloudWatch alarms + confirmed SNS path, $0.00 net
  billed in the last 7 days [`docs/plan/ops-handover.md`].

## Design & usability

A judge can use it without us: `/` is the dosimeter landing ("the field knows
what Delhi breathed — the app knows what you breathed") over a live field
canvas with a 12-hour scrubber and a→b dose routing (landing v6 adds the
dose-equation strip, the field's own sparkline, and a one-tap demo chip);
`/city` is Delhi's
public ledger — district choropleth, the day-in-dose ticker, corridors,
the lung-reach veil, and the new **parali-watch tile** (`cause_note`:
belt detections · carry wind · ventilation · the recorded trend —
"measured, not reported"); `/community` is the donation ledger; `/admin` is
the
engine room — now behind a real sign-in (operator token → HMAC-signed
HttpOnly cookie; guests land on a gate card) — pipeline provenance,
per-feed trust table, field map with real
FIRMS detections, engine internals. The consumer app (Android release,
one Expo codebase) is FROM→TO→ranked modes plus the on-device dose ledger —
and since today the compare moment is the **cinematic route chooser**
(`e2ff634`): candidates draw as equals, the camera fits them all, then the
winner settles bold with a verdict pill pinning *why* ("cleanest and
fastest" / "cleanest · N% less than fastest" — the server's own
`reason_line`, never a canned claim).
Public JSON endpoints are self-describing — every estimate carries its band,
its basis ("est."), and the field's own age.

## What we do not claim (this is a feature, not a disclaimer)

- Phones measure nothing — traversals adjust dose *estimates*, never the
  field. Per-vehicle emissions are fleet-class bands; per-vehicle truth is
  unknowable.
- The forecast is CAMS + stagnation physics, not ground truth — and the field
  says so itself: `coverage < 1` at the edge, `confidence:"low"` on thin cells,
  a typed `outside_service_area` for Mumbai instead of a fabricated route,
  `null` where a feed serves nothing (ammonia today — the eleventh species
  is honestly empty).
- Community data is young — 24 contributors, 44 corridor observations
  all-time, ~1,278.9 µg avoided (read Oct 7 ~16:20 IST — live counters
  at `GET /community`; figures are stamped reads, the wire drifts).
  The k≥3 floor means the corridor table is honestly sparse.
- `/v2/day` is the morning card's *data* — the card surface itself rides the
  app's ledger today; the endpoint is public JSON for the same answer.
- One task, one region (NCR-only), HTTP :80 only — no custom domain yet.
  Said plainly, because a security judge deserves it: **the transport is
  plaintext today, and we don't pretend otherwise** — what travels is a
  trimmed aggregate, no credentials, no identity (the new admin session
  cookie rides the same plaintext until TLS lands — its `Secure` flag
  auto-enables the moment a 443 listener exists); closing it is a domain +
  ACM cert + a 443 listener.
- CPCB live feeds are geo-blocked from our network (documented in
  `field_validation.md`) — WAQI + DPCC carry the measured-instrument role
  meanwhile; the CPCB adapter reports itself dormant rather than pretend.
- The met-wind feed intermittently reports `known:false` for a refresh or two
  (upstream Open-Meteo reachability) — it says so on the wire instead of
  serving a stale vector.

## Impact, provably

We can't claim "Delhi got cleaner." We can and do show: an individual's
inhaled dose cut by about thirty-five times on the same trip (~35× on a
Delhi commute; 33.0× measured today) and the cleanest hours of
their day named with a real band; N trips switched to a lower-smoke option,
counted and auditable on the dashboard; and the first street-level, per-hour
picture of what Delhi commuters actually breathe — aggregate,
privacy-floored, and growing with every donated trip.
