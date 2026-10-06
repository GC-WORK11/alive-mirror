# Lane report — `ingest_dpcc` prototype (flag-gated DPCC 5-min ingest)

Date: 2026-10-06 · Lane: ingest-dpcc · Commit: this push · Status: **prototype landed, flag OFF by default**

The holdout lane proved our blend is blind at 7 DPCC station locations
(1.5–5.8 km from the nearest field sample, GAP-class MAE 22.8). This lane
puts those instruments *inside* the blend: `server/ingest_dpcc.py` scrapes
the same DPCC 5-min pages used for the holdout truth data, behind
`ALIVE_DPCC_INGEST=1` (default off).

## What was built

**`server/ingest_dpcc.py`** (~530 lines) — mirrors `ingest_waqi.py`'s
adapter shape exactly:

- `fetch() -> {status, stations, obs, skipped, ...}` — same bundle
  contract; obs carry `{station_id, name, lat, lon, parameter, value,
  unit:"µg/m³", src_value, src_unit, ts, ts_utc, coord_src}`.
- `grab_async(client) -> [(lat, lon, name, {field-keyed vals})]` — same
  row shape the airfield chain consumes (`pm2_5`, `pm10`,
  `nitrogen_dioxide`, `ozone`, `sulphur_dioxide`, `carbon_monoxide`).
- 15-min module cache (`CACHE_TTL_S = 900`) shared by both entry points —
  their cadence is 5 min but we only refresh per field rebuild; one field
  refresh = one index GET + one nav-probe GET + ≤30 page GETs, 4-way
  concurrency, ≤1 retry, no retry on 4xx. **Never hammered.**

**`airfield.py` wiring** — additive, not preemptive: inside
`_grab_stations`, after the WAQI rows loop and before the `if out:`
return. DPCC rows **append** to the WAQI backbone (24 stations) rather
than compete in the first-non-empty chain — its whole value is the
stations WAQI doesn't carry. `_stations_src` reports `"waqi+dpcc"` when
both contribute; `_stations_status["dpcc"]` shows ok/unavailable/skipped
in `/health`-style diagnostics. Flag off → zero requests, status
`"skipped: flag off"`.

## Units — verified, not assumed

DPCC publishes **raw µg/m³** (CO in mg/m³), not sub-indices. Verified on
live pages 2026-10-06: Vivek Vihar row literally reads `69.0 µg/m3` for
PM2.5 — the same raw concentration our field consumes post-debias (the
WAQI path does the IAQI→µg inversion; DPCC needs none). The parser
**asserts the unit token per row** (`µg/m3`, `mg/m3` for CO) and counts
`skipped.unit_mismatch` — if the site ever switches to indices, values
are refused, never silently reinterpreted. Distinction documented in the
module docstring.

## Station discovery (the part the index hides)

The index tree lists 24 stations. The station pages' nav bar carries a
**30-station superset** — the 6 stations the tree omits are exactly the
verified blind spots (IGNOU, JNU, CWG Akshardham, NSUT West, Talkatora,
SBV Delhi Cantt) plus Supersite Rouse Avenue (stale since March 2025 —
its rows die at the staleness guard). Discovery: fetch index → probe ONE
station page → union nav links. One harvest pass, no recursion.

## QC guards (real constraints only — nothing tuned)

- staleness: row timestamp (IST on the page) older than 90 min → drop
  (Supersite's March rows → all dropped, verified by fixture).
- range: pm25 0–1500, pm10 0–3000 µg/m³ (same clamps as cpcb/waqi).
- physical: pm25 > pm10 × 1.05 → pm25 row dropped (`bad_value`) — a
  swapped cell can never poison the blend.
- coords: static map of all 30 DPCC labels (verified live) + registry
  fallback (`_norm_station` over `delhi_climatology.json.gz`); unknown
  labels are counted `unresolved_coords`, **never guessed**.

## Tests

`tests/test_ingest_dpcc.py` — 18 tests, all synthetic except three real
page fixtures pinned under `tests/fixtures/` (Vivek Vihar healthy,
Alipur flapping instrument, Supersite stale). Covers: parser reads raw
µg/m³ not index, CO mg→µg ×1000, stale rejection, blank cells, pm25>pm10
guard, bad-ts/unit-mismatch counters, tree + nav link extraction,
static-map coverage for every live label, flag-off = zero requests,
15-min cache behavior, index-down/failure → empty, grab_async row shape.

`pytest tests/` — **641 passed**, 18 of them new. One failure is a
**pre-existing flake unrelated to this work**:
`test_query_tolerance.py::test_search_latency_compound_path` asserts
search p95 < 50 ms and lands ~99–104 ms on this box — **it fails on a
clean `base/v2` checkout** (verified via `git stash`). Search-engine
timing, not the ingest path.

## Live smoke (flag ON, real site, this session)

```
status ok | pages 31 | stations 30 | obs 180
skipped: {no_pm25:1(Supersite), stale:6(Supersite rows), unit_mismatch:0,
          http_error:0, unresolved_coords:0}
```

All 7 holdout GAP sites ingested live: Mundka 84, IGNOU 27.2, JNU 75.7,
Akshardham 69.6, NSUT 70.5, Talkatora 58.8, Delhi Cantt 18.3 µg/m³.
Known quirk: **Alipur reports pm25=3.0, pm10=3.0** — the dying sensor
from the holdout report. Physically consistent (pm25≤pm10) so it passes
through; flagged here so nobody treats it as a parser bug.

## Holdout re-check on paper (flag ON)

With DPCC ingested, every DPCC station coordinate carries an instrument
at ~0 km. Before → after for the 7 GAP sites:

| station | km today | pm25 served-tonight vs truth | km with flag on |
|---|---|---|---|
| Mundka | 3.4 | MAE 20.1 | ~0 |
| IGNOU | 4.1 | MAE 39.1 | ~0 |
| JNU | 2.7 | MAE 7.6 | ~0 |
| CWG Akshardham | 1.8 | MAE 26.9 | ~0 |
| NSUT West | 3.6 | MAE 0.8 | ~0 |
| Talkatora | 1.5 | MAE 23.2 | ~0 |
| SBV Delhi Cantt | 5.8 | MAE 41.3 | ~0 |

GAP class (n=7, 3.3 km mean) → all instrumented. Residual error becomes
instrument-vs-blend disagreement at ~LIVE-ADJ scale (MAE ~16) or better,
not blind-gap error. Bigger win is the ANCHOR misses: tonight's worst
serves were blind anchors under local flares (Jahangirpuri −68, Sonia
Vihar −63, Narela −50) — with the real reading ingested at 3× weight
those specific misses cannot recur the same way.

**Honest limits:** paper math, not deployed proof — `_smooth` shrink and
blend weights can still pull a served point off its own instrument's
reading, and WAQI-vs-DPCC instrument disagreement (Karni Singh: WAQI ≈97
µg-equiv vs DPCC 66 tonight) is unresolved noise whichever pipe wins the
cell. The number to report when this ships: GAP-class MAE recomputed on
prod with the flag on — expected to collapse to ~LIVE-ADJ level.

## Risk notes for whoever flips the flag

- DPCC site is ModSecurity-fronted: needs a browser UA (`_UA` in module),
  index 406s without it. Page churn is the main fragility — mitigated by
  `unavailable:` status + `skipped` counters, never silent.
- 31 page fetches per refresh is heavier than WAQI's one call; the
  15-min cache + PAGE_SEM=4 + no-4xx-retry keep it polite.
- If `pages` count or `unresolved_coords` climbs in `_stations_status`,
  the site renamed stations — update `STATIONS` in ingest_dpcc.py.
