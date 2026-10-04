# Engine-quality decomposition — why 112 worse-dose rows (2026-10-04)

Live build `5805620`, NLB :80. Audits: `tools/audit_engine_quality.py`
(112 worse-dose rows / 194 same-mode pairs, 10/40 win vs fast, 17/40 vs
same-mode, 0 absurd detours) then `tools/audit_dose_decomp.py` — the
decomposition harness added this leg.

## The math

Every row's displayed dose is one integrator
(`exposure.dose` on the priced raster, flat uplift since `7e92660`):

    dose.mid = VE · me · C̄ · T
    C̄ = dose.avg_conc_ugm3  (length-weighted mean field value, on the wire)
    T = eta_s               (declared duration, on the wire)

so a same-mode engine/router pair factors cleanly — VE, me cancel:

    dose_ratio = conc_ratio · dist_ratio · (r_speed / e_speed)
               = conc_ratio · time_ratio

`equal_speed_ratio = conc_ratio · dist_ratio` is the dose a user pays
when both vehicles run the **same** speed profile. <1 = the engine
corridor is genuinely lung-cheaper; the wire flag is then purely a
duration-model artifact.

## The split (112 worse-dose rows)

| Class | Rows | Meaning |
|---|---|---|
| `conc > 1.05` — engine picked a measurably smokier corridor | **0** | none exist |
| `conc 1.02–1.05` — mild (within 4–5 km raster sampling noise) | 15 | no priced-objective failure |
| `conc ≤ 1.02 & dist > 1.05` — longer-corridor disagreement | 56 | speed-model disagreement, see below |
| `conc ≤ 1.02 & dist ≤ 1.05` — same corridor, slower assumed speed | 41 | pure duration-model artifact |

- Median conc_ratio across all 194 pairs: **1.000** — the priced raster
  is ~4–5 km cells (`/grid`: 484 cells over the NCR bbox), so intra-city
  corridors are nearly indistinguishable in C̄. At a flat field,
  least-dose degenerates to least-time, and every "corridor failure" is
  actually a disagreement about which corridor is *faster*, not cleaner.
- 29/37 ODs have an engine primary corridor that is per-metre
  cleaner-or-equal; 15/37 ODs have one that is equal-speed-cheaper.
- Median implied speed: engine 35.2 km/h vs router 37.0 km/h. Per mode:
  car 47 vs 51, **bike 42 vs 56 (router p90 65.7, max 74.6)**, auto 37 vs
  43, cycle 16 vs 15, walk 5 vs 5.

## Honest residuals (what is NOT explained away)

1. **Router side overstates durations' speed** (plan.py — lead lane).
   Router rows are OSRM driving freeflow with factors: bike = car×0.9
   (implied 56–75 km/h — a Delhi 2W does not outrun cars 1.1×), auto
   = ×1.25, cycle flat 15, walk flat 5. The comment says it: "OSRM
   duration ≈ free-flow — no traffic feed". Delhi ground truth ~24.5
   km/h average (TomTom 2025, 60.2% congestion) makes *both* sides
   optimistic — but the router's far more so, which systematically
   understates router `dose.mid` and manufactures most of the
   worse-dose flags. A shared, declared duration model (or a freeflow
   label on router ETAs) is the honest fix; it changes user-facing
   ETAs, so it's a lead decision, not this lane's edit.
2. **Longer-corridor picks rest on freeflow speed beliefs.** When C̄ is
   flat the priced objective `Σ conc·me·ve·len/sp` is time-minimization
   under the engine's per-edge plausible speeds (OSM maxspeed or class
   defaults: motorway 80 … residential 30). E.g. CP→MayurVihar car:
   engine takes a 13.3 km expressway arc (believes 53 km/h) over the
   router's 10.6 km direct (OSRM believes 55). Whether the detour pays
   for the user is unknowable without a traffic feed — the relative
   spread between classes is the only thing that matters for path
   choice (uniform scaling changes displayed eta/dose but not the
   argmin). Compressing the spread toward congestion reality would cut
   detours; it also changes ETAs → same lead-decision category.
3. **Fixed-speed detours are snap/access-driven, not objective
   failures.** Walk (5 km/h) and cycle (~16) can't trade concentration
   for speed, so their residuals (e.g. NehruPlace→Kalkaji walk +18%)
   trace to endpoint handling: verified locally (`routegraph.path_engine`
   + flat field reproduces the exact live path) that the engine snaps
   to **graph nodes** under per-mode access bits, while OSRM snaps to
   **edge projections** with its own access model. The engine's longer
   route is the shortest *foot-legal* path in its graph. Improving this
   means mid-edge snap — real engine work, not a bug fix.
4. **Legality asymmetry inside the audit itself.** The router `auto`
   row is car geometry ×1.25 — it may follow roads autos are denied
   (engine auto denies motorway/trunk classes). Comparing the engine's
   legal auto path against a possibly-illegal corridor inflates the
   "corridor" count (worst case CP→MayurVihar auto, eq 1.487).

## What raises the win-rate honestly

- The `vs fast row` metric is structurally hard on a flat field: with
  C̄ equal, ≥10% dose save needs the engine path ~10% *faster* than the
  fastest router row. Real wins come only from spatial variation — the
  raster at ~4–5 km cells can't give intra-city corridors different C̄.
  Finer field resolution or road-class uplift (exists as
  `exposure.ROAD_UPLIFT`; both priced AND display must apply it, unlike
  pre-`7e92660` where only priced did) would create genuine corridor
  differentiation.
- Engine-side: no objective bug found. `engine_dose_ug` and `dose.mid`
  agree (priced integrand = display integrand); 0 absurd detours; the
  A* minimizes exactly the shown quantity.

## How verified

- `tools/audit_engine_quality.py` + `tools/audit_dose_decomp.py` vs NLB
  build `5805620` — 40 ODs, 194 same-mode pairs (numbers above).
- Local repro: C++ `PathEngine` on `server/data/route_graph.bin.gz`
  reweighted with a flat 50 µg/m³ field reproduces the live
  NehruPlace→Kalkaji walk corridor verbatim (2.96 km, same via_names) —
  confirming fixed-speed detours are snap/access, not search errors.
