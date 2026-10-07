# Lane report — admin "usage" tab (`/v2/usage`)

Owner ask (verbatim): "admin must show usage — how many users, usage happening,
feedback, average breathing — aggregate only, never personalized/named".

Lane: `admin-usage`. Branch `base/v2`. Scope touched: `server/admin_agg.py`,
`server/main.py`, `server/v2/store.py`, `server/agg_ddb.py`,
`server/admin.html`, `server/tests/test_admin_usage.py`,
`server/tests/test_admin_agg.py`, `server/tests/test_admin_v2.py`,
this file.

## What was added

- `GET /v2/usage` — admin-token gated (`_admin_guard`, same Bearer/
  loopback-only scheme as `/admin/api/*`; mounted next to it in
  `main.py`). Also listed in the `/admin/api` index. Aggregate scalars
  only — the k-anonymity contract here is *structural*: nothing
  dimensional below a city total is served, so there is no sub-k row to
  leak.
- `Usage` section in `server/admin.html` ("07 · who's using it"; the
  archive renumbered to 08). Same card/kv grammar as the neighbouring
  sections; `paintUsage()` renders honest-empty and honest-locked
  states; guests' fetch is short-circuited in `tick()` via
  `isGatedPath` (same mechanism as `/admin/api/*`) — a guest never fires
  the request, so no 401 token-prompt nag.
- Store reads added (read-only — no write path touched):
  - `TripAggregates.hours_window(window_s)` / `trips_per_hour(hours)`
    on both the memory store and `DDBTripAggregates`.
  - `DeviceLedger.device_windows()` / `dose_values()` on both the memory
    ledger and `DDBDeviceLedger` (scan-based, like the existing
    `devices()`; `None` on failure so a partial scan is never painted as
    a total).

## Field → source → why honest

| field | source | honesty |
|---|---|---|
| `devices.total / seen_24h / seen_7d` | `LEDGER.device_windows()` — distinct hashed tokens by each token's newest ledger row | counts "devices that shared"; the server learns a token only when a donation carries it. Scalar counts, never identities. DDB backend scans `ledger_meta` `last_ts`; memory scans newest row per token. |
| `installs` | `None` + `installs_note` | true installs are unknowable server-side by design — no install registers with the API; the token count is disclosed as the floor under it, not dressed up as installs. |
| `trips.total/km/dose_ug/switched/days_tracked` | `TRIPS.city_aggregates()["days"]` counters | same day counters `/admin/api/donations` and public `/v2/city` already serve. |
| `trips.today` | today-key row of the same `days` counters | UTC-day counter, labelled as such in the tab. |
| `trips.last_24h` | `TRIPS.hours_window(86400)` — retained UTC-hour aggregates (72 h) | rolling window sums; `devices` is the union of the buckets' distinct-token sets (exact, not summed). `null` + `last_24h_note` if the backend can't answer. |
| `trips.per_hour` | `TRIPS.trips_per_hour(24)` | count series, oldest→newest — mirrors `community.journeys_per_hour` but reads the ledger's own hour aggregates. |
| `trips.latest_donation_age_min` | max `last_ts` across day counters | same freshness basis `community.totals()` uses. |
| `dose.mean_ug_per_trip` | `dose_ug`/`trips` over day counters | every donated trip, the headline "average breathing". |
| `dose.median_ug_per_trip` (+`median_n`,`median_basis`) | `LEDGER.dose_values()` — retained per-trip rows | true median; basis disclosed (≤300 rows/device, ~90 d TTL on DDB; un-tokened donations not ledgered). `null` when the ledger can't answer. |
| `dose.mean_ug_per_km` | `dose_ug`/`km` | same counters. |
| `dose.daily` | per-day `{day, trips, mean_ug}` over `days` | same day rows admins already get on `/admin/api/donations`; `mean_ug` null on zero-trip days. |
| `corridors.tracked / publishable` | `city_aggregates()` `cells_tracked` / `corridors_publishable` | the k≥3 set, computed inside the store — same figures `/v2/city` publishes. |
| `feedback.reviews` | `community.reviews_summary()` verbatim | hist + mean always; note bodies keep their own ≥3-reviews gate inside the summary. |
| `feedback.hazard_reports` | `community.live_reports()` counted by kind | counts only — pins (`lat`/`lon`) never enter the payload. |

## Feedback — premise check

The lane brief said "v2/feedback returns 410 intentionally". Verified
against code + live prod: **`/v2/feedback` is live** (POST →
`community.add_review`, 10/hr per-IP cap; prod returns 422 on an empty
body, not 410). The 410 endpoint is `/observe`. So a real feedback store
exists — `community._reviews` — and the endpoint serves its real
aggregate shape rather than a fabricated or empty-fabricated block.

## Guest view

No token → `tick()` rejects `/v2/usage` before it fires (`isGatedPath`),
the section renders "locked — sign in as operator" cards and empty
panels. No internals, no 401 prompt loop. Verified in the tests below.

## Tests

`server/tests/test_admin_usage.py` (8 tests): shape on empty + populated
stores, 24 h/7 d window bucketing, recursive no-identity key scan,
degraded-ledger honesty (null + note, trips block still answers),
structural k-guard (a solo device's donations still report scalar totals
while its corridor stays suppressed), the real `_admin_guard` 401/200
round-trip, and admin page wiring markers.

Ran: `PYTHONPATH=. .venv312/bin/python -m pytest -q tests` — see commit
message for the count. (This VM had no server venv; created `.venv312`
on python3.12, `pip install -r requirements.txt`. The `core/build*`
C++ ext isn't built here, so the suite ran the pure-python path.)

## Not touched (per lane rules)

Donation pipeline internals, token issuance, auth scheme — the existing
`_admin_guard` is reused as-is. Prod was only read (GET).
