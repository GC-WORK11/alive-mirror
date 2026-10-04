# Duration model — decision memo (2026-10-04)

## The question

Engine durations come from per-edge freeflow speeds (`e_sp` = OSM
`maxspeed` where tagged, else per-class Delhi-conservative defaults —
motorway 80 → primary 60 → residential 30–35 → service 15–25 — with
mode caps: auto 40, bike 50, cycle 16, walk 5 km/h). Router rows carry
OSRM freeflow. The audit asked: does the ~27-vs-55 km/h gap need a
calibration, or a label?

## Measured, live (build 1436c2d4, 6 ODs, car mode)

| OD | router km/h | engine primary km/h |
|---|---|---|
| CP→Noida18 | 54.8 | 55.8 |
| MgRoad→Saket | 40.5 | 44.3 |
| CP→Dwarka21 | 56.6 | 50.8 |
| CP→IndiaGate | 49.2 | 36.3 |
| Rohini→CP | 50.6 | 38.8 |
| CP→Shahdara | 52.2 | 38.2 |

Engine primaries run **36–56 km/h implied (median ~41)**, router rows
**40–57 (median ~51)**. The "~27" figure in the earlier brief did not
reproduce — it was an average dragged down by cycle/walk modes (which
sit at their 16/5 km/h caps by design). Non-car modes ride their caps:
bike ~46 vs cap 50, auto ~39 vs cap 40, cycle ~15 vs 16, walk 5.0.

Both sides overstate *real* Delhi speed: TomTom 2025 puts the Delhi
average at ~24.5 km/h (60.2% congestion level). Neither side has a
traffic feed — durations are freeflow everywhere.

## Decision: (b) label, keep freeflow

Why not (a) — calibrate:

1. **It changes no path choice.** The priced objective is linear in
   per-edge time (`conc × me × ve × len/spd`); scaling all speeds by
   one factor scales every path's dose identically — the A* argmin is
   invariant. A city-average scalar would move only the absolute µg
   number shown, not the route the user gets.
2. **One scalar is fake precision.** TomTom's 24.5 km/h is a
   city-and-day-part average; we have no per-corridor or per-hour
   measured-speed dataset in the repo, and no probe feed is wired.
   Multiplying every edge by ~0.5 would look calibrated and be
   invented — the exact "tune to look good" failure the rules ban.
3. **Per-edge calibration is the honest version and needs data we
   don't have.** A real congestion model (probe speeds, GTFS-RT,
   historical profiles) is a data-purchase/ingest lane, not a code
   fix; flagged for post-demo.

What ships instead:

* `duration_basis: "freeflow"` on every engine row (wire + contract.ts)
  — the label says what the model is, on the row the client renders.
* Engine rows keep `duration_model: "estimated"` (graph speeds, not a
  router's road-traffic estimate).
* Consequence declared: at real Delhi speeds the absolute dose is
  higher than shown — the band understates trip time and therefore
  inhaled mass by roughly the congestion factor (~1.5–2× at peak).
  **Ordering is unaffected** — every row shares the same freeflow
  model, so least-dose ranks stay honest.
* Corpus regression pins implied corridor speed inside per-mode
  freeflow bounds (test_legality_corpus.py::test_corpus_implied_speed_sane)
  so a build that ships uncapped maxspeed or a broken duration
  accumulator fails CI.

## Open gap (lead lane, flagged)

Router-side durations scale OSRM freeflow by fixed per-mode factors
(bike ×0.9 → implied 56–75 km/h — a Delhi 2W does not outrun cars by
1.1×). The engine's side is honest about its freeflow basis; the same
label discipline on router rows is in plan.py's mode table.
