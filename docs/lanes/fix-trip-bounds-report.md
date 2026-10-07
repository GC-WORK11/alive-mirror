# fix-trip-bounds — admission control for /v2/trip donations

Lane: `fix-trip-bounds`. Pass **2026-10-07 ~01:30 UTC** (≈07:00 IST).
Trigger: judge-attack-audit (`0f5f879`) PRIVACY row "k≥3 vs sybil / field
poisoning" + server-audit (`fd951e8`) med BUG "`/v2/trip` donations are not
geographically bounded to NCR".

Scope kept tight: `server/v2/trip.py` admission checks, regression tests,
this report. The privacy pipeline (trim-300 m / thin-100 m / round-4dp /
h3-res-8) and the k≥3 stores are untouched — these bounds run **before**
any of it.

## The attack surface (as audited)

`POST /v2/trip` is unauthenticated by design (rotating anonymous tokens).
Two bounds were missing:

1. **No geo bound** — `v2/trip.py` minted H3 corridor cells for any
   in-range lat/lon on Earth (`_parse` only checked finite/±90/±180). A
   script could write "how Delhi moves" corridors in Mumbai, Chennai, or
   the Bay of Bengal; `origin_area`/`dest_area` already resolved to None
   outside NCR but the cells and totals landed anyway.
2. **No implied-concentration bound** — `dose_ug` was capped only at
   50,000 µg (`_BOUNDS`), never checked against the traversal it claims
   to describe. The corridor layer inverts dose to ambient
   `C = dose/(VE·dur·microenv)` and only accepts ≤900 µg/m³ as a
   measurement (`community._fold`), but the raw dose still inflated
   `dose_sum`/`avg_dose_ug`/day/lifetime totals whatever it implied.

## Bounds added (`server/v2/trip.py`, in `post_trip` after the existing
speed check, before dedupe/record)

| bound | rule | basis |
|---|---|---|
| **Geo** — every `kept` point must be inside `in_service_area` | reject `422` + the canonical `OUT_OF_AREA` string (`"outside service area — dose field covers Delhi/NCR only"`) | Same call `/aqi`, `/v2/plan`, `/v2/reach`, `/v2/day` already use — `airfield.BBOX` ± `SERVICE_MARGIN_DEG` (2.0° ≈ 220 km margin: Jaipur/Chandigarh/Agra stay donatable). The check runs on the whole `kept` set — endpoints **and** mid-path — because every kept point mints a corridor cell; an endpoints-only check would leave the injection open. `kept == []` (summary-only donation) mints no cells → nothing to bound → unchanged. |
| **Implied-C** — `dose_ug` must invert to ≤ `MAX_IMPLIED_PM25 = 900` | `C = dose_ug / (VE_lpm/1000 · dur_min · microenv)` with the claimed mode's `exposure` factors (unknown mode → the `_fold` defaults 10.0/1.0); reject `422 "implausible dose_ug for duration_s"` | Reuses the corridor layer's own measurement ceiling — a donation past it could never be a field sample anyway, so refusing the whole donation at the door is the honest move (the codebase's reject-with-structured-error style, not silent field surgery). |
| implied-C dodge | `duration_s` absent → the check uses the 6 h duration cap, the most donor-favorable duration possible | If dose is absurd even at the longest legal ride time, it is impossible whatever the truth. Kills the "omit duration, claim 50 mg" bypass while honest duration-free donations keep the smallest verifiable bound. |

Not added (deliberately out of "smallest"): trajectory-length vs
`distance_km` cross-checks (GPS noise eats honest trips), rate limiting
(separate finding — `middleware.py` XFF keying), authentication (the
design is anonymous-by-contract; k≥3 + hash stands).

## Verified on the wire (TestClient, this HEAD)

```
foreign trajectory (Mumbai line)         → 422 outside service area — dose field covers Delhi/NCR only
endpoints in NCR, mid-path exits margin  → 422 outside service area — dose field covers Delhi/NCR only
walk 1 h claiming dose_ug 50,000         → 422 implausible dose_ug for duration_s   (implied C ≈ 45,800)
ordinary NCR traversal                   → 200 stored, cells_traversed 6
```

## Test output

`cd server && PYTHONPATH=core/build312:. .venv312/bin/python -m pytest -q tests`

- Baseline at `4a9f4f7` (pre-change, same env): **1169 passed, 5 skipped**.
- New tests in `tests/test_v2_hardening.py` (suite style: /v2/city totals +
  `TRIPS.snapshot_cells()` asserted unchanged after rejected payloads):
  - `test_trip_outside_service_area_rejected_and_never_counted` — four
    foreign/edge/mid-path-excursion trajectories → 422, zero accrual
  - `test_trip_valid_ncr_traversal_still_flows` — honest in-area trip → 200
  - `test_trip_implausible_implied_concentration_rejected` — implied-C
    ~46k/111k/no-duration-25k → 422, zero accrual
  - `test_trip_bad_air_day_dose_still_lands` — implied ~795 → 200
- Two fixtures retargeted, not behavior changes: `test_v2.py`
  `test_trip_privacy_pipeline` sent `dose_ug 60.5` on an 8-min AC-car ride
  (implied ≈1375 µg/m³) and `test_contract_sync.py`'s `V2TripResponse`
  fetcher sent `dose_ug 40.0` on the same ride (implied ≈909 — 1% over the
  ceiling) — both correctly refused; doses now `30.0` (implied ≈682), the
  wire-shape assertions are identical.
- Full suite on HEAD: **1173 passed, 5 skipped** (the 4 new tests included;
  run ~8 min on this box).

## Residual surface (honest ledger)

- Unauthenticated-by-design stands: a script can still mint rotating
  tokens and donate *plausible* NCR trips. k≥3 + hashed-token distinct
  counting + 72 h windows cap what fake-but-plausible trips can publish;
  device attestation / rate limiting is a product decision, not a bound.
- `dose_ug` with no `duration_s` is now bounded by the 6 h-cap implied-C
  check, not unverifiable — but milder inflation inside the ceiling still
  lands (e.g. dose claiming 5,897 µg walk-equivalent). Bounded, not zero.
- `/v2/ledger` self-history rows record the same bounded summary — no new
  exposure either way.

Commits: `e540952` geo bound · `1a1f636` implied-C bound · `01059fe` tests.
