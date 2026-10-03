# 07 · "Delhi today" (consumer), the admin dashboard, and privacy

## 1. Consumer: "Delhi today" (from the sidebar)
One scrolling page, dark, editorial — the mission made visible.
1. **The live map** — Delhi's air on the H3 grid, breath ramp, gently animated with real wind direction (particles drift with the Open-Meteo wind field). Label: "updated 9 min ago · from 38 stations + model".
2. **Three lines**: "Right now Delhi's air is heavier than yesterday." / "Best hours to travel today: 1–4 pm." (from the forecast + ventilation) / "Heaviest roads right now: Ring Road near Ashram, …" (top corridor cells with ≥3 trips).
3. **What ALive travellers did today** (aggregate, live): trips · km · smoke breathed (cigarettes, total) · smoke put out (kg CO2, band) · "trips that took a lighter way: N".
4. **Why** — 3 sentences of mission + "How these numbers are made" link (sources, validation error shown plainly).
No charts that don't answer a question. Empty → hidden, not zero-filled.

## 2. Admin dashboard (`/admin`, basic-auth, web)
For the team and judges; built on the same aggregates, more detail:
- **Ingest health**: each source, last success, age, rows; field rebuild duration; stations used; mean σ.
- **Air index**: H3 map with time slider (last 7 days from S3 snapshots); city percentile curves.
- **Trips (aggregate)**: per hour/day: trips by mode, km by mode, breath µg sum, emission g sum (band), switched-to-lighter count, median dose per km by mode.
- **Corridors**: cells with ≥3 distinct trips in 72 h, mean exposure per traversal.
- **Validation**: latest leave-one-out report.
- **System**: p50/p95 per endpoint, error rate, AWS cost-to-date (Cost Explorer once data exists).

## 3. Privacy design (what lets us say "no personal data")
| Rule | Implementation |
|---|---|
| No accounts, no names, no phone numbers | none collected |
| Random device token | UUIDv4 generated on device, rotated every 30 days; never linked to anything |
| Trip endpoints hidden | client drops the first and last 300 m of every trajectory before upload |
| Thinning | upload one point per ~100 m, coordinates rounded to 4 decimals (≈11 m) |
| No raw trajectories at rest | server converts to H3 cell traversals immediately; stores only cell counts + exposure sums; raw payload discarded |
| k-threshold | a cell/corridor is displayed only with ≥3 distinct device tokens in the window |
| Opt-out | Settings → "Share anonymous trip data" off = nothing uploaded; local ledger still works |
| Delete | Settings → "Delete my data" wipes local data; server has nothing linkable to delete (stated plainly) |
| Disclosure | one-screen plain explanation at first launch, no dark patterns |

This is what makes the central claim true: the server holds city-wide totals and anonymous road-cell counts, nothing that identifies a person or a home.
