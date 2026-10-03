# Verify the privacy claims yourself

Every claim in `PRIVACY.md` maps to a line of code or a test assertion.
Run the suite from `server/`:

```bash
.venv/bin/python -m pytest tests/test_v2.py -v
```

## Claims → enforcement → proof

| claim | where it's enforced | proof / how to check |
|---|---|---|
| endpoints trimmed 300 m | `TRIM_M = 300.0`, `server/v2/trip.py:28`; applied `trip.py:82-85` | `test_trip_privacy_pipeline` asserts `privacy.trimmed_start_m >= 290` and `trimmed_end_m >= 290` (`server/tests/test_v2.py:275-276`); `test_trip_pipeline_unit_endpoints_dropped` asserts first kept point ≥250 m along-path (`test_v2.py:291-296`) |
| thinned to ~100 m | `THIN_M = 100.0`, `trip.py:29`; loop `trip.py:87-91` | `test_trip_privacy_pipeline` bounds `points_used` to 8–22 for a ~2.6 km trace (`test_v2.py:274`) |
| rounded to 4 dp (~11 m) | `ROUND_DP = 4`, `trip.py:30,90` | `test_trip_pipeline_unit_endpoints_dropped` asserts every kept point equals its own `round(…,4)` (`test_v2.py:297-299`) |
| no raw coordinates at rest | cells computed at `trip.py:107`; only `cells` reach `TRIPS.record_trip` (`trip.py:114`) | `test_trip_privacy_pipeline` asserts no cell key contains `"28."` or `"77."` and cell payloads are exactly `{count, dose_sum, devices}` (`test_v2.py:281-283`) |
| device token never persisted | sha256→16 hex before any store call, `trip.py:109-110` | `test_trip_privacy_pipeline` asserts the literal token is absent from the entire store repr: `assert "device-under-test-1" not in repr(store.TRIPS.snapshot_cells())` (`test_v2.py:284`) — grep it |
| only aggregates stored | `TripAggregates._days` / `_cells` shapes, `server/v2/store.py:66-97` | same test; `city_aggregates()` returns day counters + counts only (`store.py:117-129`) |
| corridor shown only with ≥3 distinct devices, 72 h | `_publishable_cells`: `len(v["tokens"]) >= 3 and now - v["last_ts"] <= self._cell_window_s` (`store.py:99-107`), `_cell_window_s = 72*3600` (`store.py:68`) | grep `store.py` for `>= 3`; exercised indirectly — post 3 tokens to `/v2/trip`, then `TRIPS.corridors()` |
| opt-out = nothing uploaded | `if (coords.length > 1 && shareEnabled)` — the only donation callsite (`Mobile/src/components/shell/useShellFlow.ts:168`); toggle at `Sidebar.tsx:279-283`; default + label `settings.ts:21`, `i18n/strings.ts:62,87` | grep Mobile for `observeTrip(` → one callsite, gated |
| delete-my-data is real | `clearAllData()` deletes `settings.json, ledger.json, contributor.txt, intro_seen.txt` (`Mobile/src/components/shell/settings.ts:45-52`), called from `App.tsx:95-98` | grep `clearAllData` |
| raw trajectory never logged | no logging statement exists in `trip.py` / `store.py` — `grep -n "log\|print" server/v2/trip.py server/v2/store.py` → nothing | code review |
| payload abuse cap | `MAX_POINTS = 5000`, `trip.py:31,65` | post >5000 points, `points_used` stays bounded |

## What is NOT enforced (verify these gaps too)

| spec says | reality — how to see it |
|---|---|
| "client drops first/last 300 m before upload" | `useShellFlow.ts:167-174` sends the **full** chosen-option geometry, index-thinned by stride (`coords.filter((_,i)=>i%step===0)`) — endpoints included. `POST /observe` stores points at 5 dp, ≤400, with no trim (`community.py:112-121`). |
| "no raw trajectories at rest" | true only for `/v2/trip`. `/observe` persists `points` to `server/data/community.json` and `$COMMUNITY_BUCKET/community/state.json` (`community.py:83-99`). Check `community.py` for `_save`/`_FILE`. |
| "device token = UUIDv4, rotated every 30 days" | contributor id is `"anon-"`+8 base36 chars, generated once, **no rotation** (`Mobile/src/community.ts:16`). Grep `rotat` in Mobile → nothing. |
| "k≥3 distinct devices before a corridor shows" | `/v2` yes (`store.py:106`); `/observe` corridors have **no** device threshold — `corridors()` ranks any cell with ≥1 sample (`community.py:294-315`), and `corridor_field_samples` needs ≥3 *traversals*, which can be one device (`community.py:255`). |
| "admin is basic-auth" | `@app.get("/admin")` and `/admin/api` have no dependency or auth check (`server/main.py:885-910`); `/admin/api` returns contributor ids (`community.py:149-197`). |
| rotation/expiry of donated data | no TTL on `_obs` (rolling 20 k cap only, `community.py:57`); `_cell_window_s` filters display, not storage. |

## Fast greps

```bash
# does anything write raw coords to disk? (→ community.py _save)
grep -n "write_text\|put_object" server/community.py
# where can a token/id appear? (→ trip.py hashes; community.py stores raw)
grep -n "contributor\|token" server/v2/trip.py server/v2/store.py server/community.py
# who calls the donation endpoints? (→ /observe only)
grep -rn "observeTrip\|/v2/trip" Mobile/src
# k-threshold sites
grep -n ">= 3\|tokens" server/v2/store.py server/community.py
```
