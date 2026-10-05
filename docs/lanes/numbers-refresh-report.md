# numbers-refresh report — strip-bz pass

**Pass:** 2026-10-05 ~22:15–22:30 UTC (≈ 2026-10-06 03:45–04:00 IST)
**Build verified:** `/health` `build_sha: 80a15258` (the strip-bz deploy —
`/v2/plan`, `/v2/reroute`, `/v2/strip` dose on the breathing-zone basis and
echo `smoke_modifier` on the wire). Deploy waited for via 60 s `/health`
poll; landed at ~22:10 UTC on poll 3.
**Method:** `bash scripts/verify_numbers.sh http://65.2.28.40` with
`server/.venv312/bin/python3` (stock python3.9 fails); raw JSON evidence
from that run in `/tmp/verify_numbers.Vv67S3/` on the lane box. All GETs
plus the one allow-listed `POST /v2/plan` and `POST /v2/reroute`. No
feedback/observe/trip POSTs, no deploys.

## The basis question, answered

Mandate asked: does the bz basis move the car-vs-walk ratio? **No — and
provably.** `smoke_modifier` is a city-wide scalar (fires.py:180-200 —
wind-gated NW 270–360°, ×0.3 outside, cap MAX_MODIFIER), applied at the
dose seam `plan.py::_bz_field` (~line 282). A uniform scalar commutes
through Σc·ME·VE·t, so every mode scales identically and the ratio is
basis-invariant. Verified empirically: 358.3/10.8 = **33.18×** tonight
and 328.7/9.9 = **33.18×** on the ambient equivalent (÷1.09). The
published 32.7→33.2 move across passes is field drift + rounding, not
the basis.

Corollary: absolute trip doses went *down* tonight despite the +9 %
basis (walk 363.5→358.3) because the ambient field dropped (~80→69.8
µg/m³ at CP between passes). The "+9 %" is the basis term, not the read.

## Figure table — before → after

All "after" values from the 22:15–22:30 UTC run unless noted.

| Figure | Was published | Now live (evidence) | Touched |
|---|---|---|---|
| `/health` build_sha | `6e82f290` | `80a15258` (`curl /health`) | NUMBERS, demo-day, shotlist, demo-script, writeup |
| plan dose ladder (mid µg) | car 11.1 / open 20.1 / bike 25.4 / bus 29.0 / auto 32.8 / metro+walk 43.6 / bus-GTFS 65.0 / cycle 151.5 / walk 363.5 (older files: 7.8…258.8) | car 10.8 / open 19.6 / bike 24.8 / bus 28.3 / auto 32.0 / metro+walk absent (service hours) / bus-GTFS 69.3 / cycle 158.8 / walk 358.3 (`POST /v2/plan`) | writeup, repo-readme, demo-day, shotlist, demo-script, NUMBERS |
| walk÷car spread | 32.7× | **33.2×** (slowest-vs-best 38.7×) | all of the above + judges-faq |
| options count | 18–22 | **23** | repo-readme, demo-script, demo-day, NUMBERS |
| plan `smoke_modifier` on wire | not echoed | **1.09** (new — the strip-bz change) | demo-day, shotlist, NUMBERS, judges-faq |
| warm `took_ms` | ~760 ms | **~56 ms** (first post-deploy hit 4,653 ms — fresh-task reprice) | demo-script, NUMBERS |
| `/v2/reroute` | ambient basis | bz basis, mod 1.09, 20 opts, 1,743.9 ms (`POST /v2/reroute` — allowed probe) | NUMBERS, report |
| `/v2/day` windows | heavy 06:30–11:30 ~155 / cleanest ~68 / mean ~113 (or "no clean slot" at 19:30) | heavy 22:30 IST→day end **159.2** / cleanest 12:30–18:30 **44.7** / mean **105.3**, 3 decisions | writeup, repo-readme, demo-day, shotlist, NUMBERS |
| `/depart` | now 22.9 → worst 94 (~4.1×) | now **29.2** → worst +16 h **79.7** (**2.7×**); best +12 h **14.5** (−50 %) | writeup, demo-script, NUMBERS |
| `/v2/city` next_hours swing | 68.5→205.1 (~3×) | **38.8→151.1** peak ~03:00 →38.8 ~09:00 (**~3.9×**) | demo-script, writeup |
| breath/day (landing hero) | ~997 µg ≈3.16 cig (earlier ~735/2.33) | **885.0 µg ≈ 2.8 cig** (`GET /v2/city`) | shotlist, demo-script, NUMBERS, writeup |
| `/v2/reach` walk@25 | 2,150 edges / 92.5 km | **3,211 / 141.2 km** | repo-readme, shotlist, demo-day, writeup, NUMBERS |
| walk@50 | 8,608 / 428 km | **10,510 / 553.9 km** | same |
| car@25 (edge_partial) | ~829k / 67,349 km | **890,510 / 75,822 km** (`edge_partial:true`) | same |
| car@100 | ~1.03 M / 99,503 km | 1,029,263 / 99,503.2 km — unchanged claim | shotlist, NUMBERS |
| corridors publishable | 10 of 54 | **12 of 54** (`/v2/city` provenance.trips; `/v2/city/moves` active 12) | writeup, judges-faq, shotlist, demo-script, NUMBERS |
| `/community` | 20 obs / 12 contrib / 333.5 µg avoided | **22 obs / 14 contrib / 725.9 all-time; 24 h: 6 obs / 14.1 km / 107.2 dose / 477.3 avoided** | writeup, demo-script, shotlist, NUMBERS |
| `/v2/city/moves` | 33 trips/7 d, car 78.8% | **36 trips/7 d, car 80.6 %, 0 suppressed** | demo-script |
| `/v2/skill` | 11 pairs, all horizons `thin` | **21 pairs — h+1 graded** MAE 16.3 / bias +15.8 / band-hit 71.4 % cell / 80.0 % hour; h+2 29.9/+29.6/13.9 %/20.0 %; h=0, h≥3 `thin` | shotlist, demo-day, NUMBERS |
| `/v2/archive` | 6 snapshots | **8** since 2026-10-05T20:00 IST | shotlist, demo-day, NUMBERS |
| `/v2/why` numbers | VC 84 m²/s, wind 1.0 m/s, BLH 84 m | **BLH 86.9 m / wind 1.15 m/s → VC ~100 m²/s vs ~3,000; fires refused (carrying:false, wind 182° S outside NW gate; 79 fires/17 belt/72.1 MW)** | demo-day, shotlist |
| field age / samples | ~8 min / ~71 samples | **96 s / 70 samples**, 24 stations (`/health`, `/aqi`) | demo-script, repo-readme, writeup |
| PM2.5 @CP | 74.7 breathing / 68.5 ambient | **76.1 / 69.8**, us_aqi 158 (unchanged band) | demo-script, NUMBERS |
| wind | 7.3 km/h @ 308° / 0.6 @108° | **4.3 km/h @ 182° S** | demo-script beats 1–2 |
| districts | 28 chips | **29** | demo-script |
| fires line | "~70 fires" | **79 (17 belt)** — detector string still trips deliberately | demo-script, NUMBERS |
| ECS task-def pin | `:141` | de-pinned — cite `/health` build_sha + read console live (no `aws` CLI on this box) | demo-script |

## Verifier flags — reconciled

`scripts/verify_numbers.sh` raised two flags; both resolved without edits:

1. **gazetteer '123,934'** — `docs/plan/handoff.md:19` already names both
   counts ("bundle 124,311 rows post-purge; the server-side copy is
   123,934"). False positive — the detector found the deliberate
   disambiguation line. No edit.
2. **smoke ×1.27** — `docs/plan/demo-script.md:114` is the timestamped
   "Pass 3 (16:05–16:50 IST)" verify stamp. Dated log = snapshot, not a
   claim (precedent: NUMBERS.md §4). Left as history; noted here.

The script's hard-coded patterns are **stale-string detectors**
(`if m: flag(...)` — they grep docs for known-dated values like
"124,334", "×1.27", "~70 fires", old reach strings). None assert truth;
no baseline update needed or made.

## Left stale on purpose (dated artifacts)

- `docs/11-demo-script.md`, `docs/28-pitch.md` — Oct-1 dated reads
  (89.7 vs 2.9 µg etc.), marked "measured Oct 1". Snapshots, not claims.
- `docs/plan/handoff.md`, `HANDOFF.md` — timestamped deploy/verify log
  entries (incl. the 19:30 demo-proof line quoting 11.1/363.5).
- `docs/plan/red-team.md` — audit table stamped "verified live
  2026-10-06 ~01:40 IST" (~2 h before this pass). Its "10/54 corridors"
  and "11 pairs, all thin" rows are now superseded by this pass
  (12/54; h+1/h+2 graded) — left stamped per precedent.
- `docs/plan/realtime-status.md` — dated Oct-3 verification ("moves
  honestly empty" era).
- `docs/plan/demo-script.md` Pass-3 block — stamped history.
- `docs/lanes/video-v4.md` — claims read "breath ≈3 cig, spread ~33-35×,
  car ~11 vs walk ~360-400µg" — within tolerance of tonight's
  2.8 cig / 33.2× / 10.8 vs 358.3; not rewritten (±1 µg rule).
- `docs/lanes/video-v4-report.md` does not exist (v3 report + v4 lane
  brief only); "video beats" = `docs/submission/video-shotlist.md` +
  `video-v4.md`, both handled above.

## Watch-items for the next pass

- `metro+walk` drops out of `/v2/plan` outside transit service hours —
  night reads have no metro row. Daytime passes must re-mint the
  "car beats metro" line (the mechanism claim "~4× metro" stays a
  daytime-read-only citation).
- `smoke_modifier` goes absent (`null`) when the wind exits the NW gate
  or fires thin — bz-basis dose figures then equal ambient reads.
- Reach/km, breath, day windows, community counters drift every 15 min
  field refresh; the "re-check T-45" habit stands.
