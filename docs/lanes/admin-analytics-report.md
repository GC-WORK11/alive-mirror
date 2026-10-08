# Lane report — admin → analytics rebuild

**Lane:** admin-analytics · **File owned:** `server/admin.html` (rebuilt) + `server/admin_agg.py` (one additive block)
**Date:** 2026-10-08 · **Branch:** `base/v2` direct push (no PR, per convention)
**Verify:** `cd server && ALIVE_ADMIN_TOKEN=<any> uvicorn main:app --port 8108` → `http://127.0.0.1:8108/<mount>` — gate → token → board. Shots in `admin-analytics-shots/`.

Owner's brief, verbatim core: *"i dont need admin backend — i want a dashboard of analytics: users and more… simple, orgasmic, playful — no technical pile."* The ~3,100-line card-heavy engine-room console is now a cognition-register analytics page (the register the landing wears since `96789a3`): warm paper `#f7f6f5`, left-rail text nav, margin indices `01–04`, serif prose, hairline-ruled data lines, zero cards/capsules/tables.

## What the page is now

`01 live air · 02 coverage · 03 usage · 04 health` — the exact four sections the brief ordered. Every line is `label — value` on a 1px rule with a serif note under it saying *what the number means and where it came from*. Absent data is an em-dash + an honest note, never a guessed figure.

Playful touches, all real-data-backed: the pm2.5 numeral inks itself in the live band's colour (`--hink` pulls the muted band 55% toward ink, transitions over .8s), a small band-coloured square sits in the label, the felt cigarette line ("a day outside in this air ≈ 0.7–7.1 cigarettes — berkeley earth's 316 µg rule"), a sparkline that draws itself on scroll (`stroke-dashoffset` animation, off under reduced-motion), the ghost `alive` wordmark in the footer.

**What died:** every technical board — pipeline/instrument deep tables, ops feeds, diagnostics grids, the donor-ledger board, corridor management, reweight/cache ops buttons, the two map panels, the alarm-history table, the archive browser, all status chips/cards/dials. Per the brief, ops controls stay only where they're the admin's actual function — which here is exactly one thing: the gate (sign in / sign out). Auth is untouched.

## Stat-truth — every displayed number → served field

Local boot, `ALIVE_ADMIN_TOKEN=devtok123`, serving the repo's own snapshot+live blend. Every row was spot-checked against the JSON it reads.

| Displayed | Source field | Local value seen |
|---|---|---|
| `85.7` µg/m³ + "moderate" band | `GET /v2/city → pm25_stats.mean` | 85.7 → band idx 2 |
| "the data is 5m old" + stale alarm suffix | `api/status → field.age_s`, `field.stale`, `stale_after_s` (real, not hardcoded) | 294s, false |
| stations reporting `0` + feed note | `field.station_readings`, `stations_status`/`stations_src` verbatim | 0 — all feeds keyless locally, shown as such |
| serving "the live field" / snapshot fallback | `field.serving` (+ `snapshot_age_s`, `engine`) | live, engine python |
| wind `6 km/h from se` | `field.wind.speed_kmh/from_deg` → compass | real |
| `−16.1%` vs typical + median note | `pm25_stats` → `typical.vs_now_pct`, `.median` | 102.1 typical |
| forecast sparkline (12 real points) | `next_hours[].pm25` | 86.8–112.1 µg/m³, live-anchored |
| stations into blend / per-feed rows | `field.stations_status` verbatim (`ok`/`skipped`/`unavailable` → colour) | cpcb "unavailable: no key" → brick |
| model grid `48 samples` · kriging `on` · σ `per-query` · `48 cells` | `field.samples/kriging/sigma_coverage/coverage` | real |
| the archive `1 snapshot · missing 23 hours` | `status.archive{snapshots_total,since_ist,today{hours_recorded,hours_elapsed,gaps}}` | real, gap-count computed from gaps[] |
| forecast `120 hours ahead` | `status.forecast.hours` + `age_s` | real |
| route engine `9,03,058 of 10,70,459 edges priced` | `status.routing{edges_priced,edges,reweight_age_s}` | real |
| "counted since boot 11:24 pm ist · every counter resets on deploy" | `api.uptime_s` → boot time | labelled honest, in-process |
| requests served `28` · `4 in flight` | **new** `api/timing.requests{total,by_status}` + `gauges.alive_requests_in_flight` | real registry counters |
| route leaderboard `01 /city 4 · p90 ≤ 10ms` … | `api/timing.routes[]{path,n,p90_le_ms}` — mount prefix stripped for display | real histograms |
| journeys sparkline | `api.journeys_per_hour` (24 real buckets) | flat zero line, "0 journeys in the window" — honest, not faked-up |
| devices seen `0 all-time · 0 in 24h · 0 in 7d` | `api/usage.devices` + `devices_basis` note | "devices that shared; true installs are unknowable by design" |
| active right now / today / every donation / per-trip dose | `api.live_users`, `usage.trips{today,total,km,dose_ug,co2_kg_mid}`, `usage.dose{mean,median}` | real, zeros where empty |
| streets that qualify `0 of 0` | `usage.corridors{publishable,tracked,k_min,window_h}` | k≥3 rule stated |
| `N reviews · M hazard flags` + suppressed-day note | `usage.feedback{reviews,hazard_reports}`, `api.contributors_suppressed.day_rows` | real |
| alarm line "all quiet" / "N things hurting" | computed ONLY from existing health state: `field.stale`, `sources[].stale`, `disk.low`, `ledger.error`, `serving==='none'`, `load_warnings` count | real conditions, names itself |
| feed ledger (model/met/stations/fires/location/routing) | `api/sources.sources[]` — verbatim `status`+`age_s`; verdict word derived from `up`/`stale`/`status` | stations → "down" brick (keyless), others "listening" |
| errors since boot `4xx 3 · 5xx 0` + per-route rows | **new** `api/timing.errors[]` from `alive_http_errors_total` + `alive_http_requests_total` | real — includes `/in/{secret}` and `unmatched` (wrong-guess rows; the token itself never appears in a route label) |
| disk `29.6% free` · ledger `memory` · build `70b733b` | `status.disk{free_pct,path,low}`, `ledger{backend,devices_tracked}`, `build_sha`/`version`/`uptime_s` | real |

**Server additions (the only two the brief sanctions, both in `server/admin_agg.py`):**
`/api/timing` now emits `requests{total,by_status{2xx,4xx,…}}` and `errors[{route,class,n}]` — both rolled from the registry's own `alive_http_requests_total` / `alive_http_errors_total` counters under the same lock snapshot the histograms/gauges already use. **19 lines.** No new middleware, no new counters, no route-table edits — the request logger already wrote these series; the endpoint just exposes them. Per-endpoint request counts needed no new code (the `routes[]` histograms were already there). "Devices seen today" needed no new code either — `api/usage.devices` is the server's real rolling-window counter; the page labels it "devices seen" + the `devices_basis` honesty note instead of inventing an install count.

## Gates — all verified locally

| Gate | Evidence |
|---|---|
| `#gateform`/`#gatetok` byte-identical | same DOM block + same POST contract; gate CSS byte-identical (its token names keep their own values under `:root`) — `gate-1440.png` |
| mount + 404 behaviour | `GET <mount>` 200 · anon `api/status` 401 · `<mount>/in/nope` 404 **byte-identical to an unknown path** (both the generic 404 body) — curl-verified |
| sign-in → board → sign-out → re-gate | cookie login 200 → full board → `sign out` → gate card returns (`gate-relock.png`) |
| @1440 | left rail + margin indices + ruled lines (`hero-1440.png`, `sec0x-*-1440.png`) |
| @390 | rail collapses to a top row, index labels stack, value column right-floors, sparkline scales (`top-390.png`, `sec01-390.png`) |
| inline-script gate | `scripts/check_inline_scripts.py` → OK (admin's inline `<script>` parses under `node --check`) |
| tests | `pytest tests/test_admin_agg.py test_admin_auth.py test_observability.py test_inline_scripts.py` → **57 passed** |

## Honesty notes baked into the page itself

- "counted since boot HH:MM ist — every counter resets on deploy" (the brief's SAY SO)
- "devices that shared; true installs are unknowable server-side by design" (never "users")
- "a street cell publishes only when ≥3 distinct phones crossed it in 72h — the rest are counted, never shown"
- "aggregate-only by construction — nothing here can collapse to one person; N day-slices withheld under the 3-phone rule"
- forecast flat/zero and journeys flat/zero render as real flat lines with the count in the caption — absence is shown, not hidden
- every fetch is `allSettled` — one dead endpoint blanks its own section to honest empties, never the board; the stamp line says when the last good paint happened
