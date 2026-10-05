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
| corridor shown only with ≥3 distinct devices, 72 h | `_publishable_cells`: `len(v["tokens"]) >= 3 and now - v["last_ts"] <= self._cell_window_s` (`store.py:99-107`), `_cell_window_s = 72*3600` (`store.py:68`); the community layer enforces the same gate — `dev_all`/`dev_ts` device sets in `corridors()` and `corridor_field_samples()` (`community.py`) | grep `store.py` and `community.py` for `_K_MIN_DEVICES`; `tests/test_community_v2.py` (`test_corridor_below_k_never_publishes`, `test_field_samples_stale_traversals_dont_publish`) |
| no per-trip records at rest | `community.observe()` folds into `_CELLS`/`_HOURS`/`_DAYS`/`_LIFE` aggregates — no obs/row list exists (`community.py` `_fold`, `_snapshot`) | `test_no_per_trip_rows_can_exist_at_rest`, `test_snapshot_round_trip_preserves_aggregates` (`test_community_v2.py`) |
| opt-out = nothing uploaded | `if (shareEnabled && trajRef.current.length > 1) s.donated = await donate(s)` — the only donation callsite (`Mobile/src/nav/engine.ts`); toggle at `Sidebar.tsx`; default in `settings.ts` | grep Mobile for `donate(` / `postTrip` → the only callsite is gated |
| device token rotates | `ID_TTL_MS = 30d`, CSPRNG via `expo-crypto` (`Mobile/src/community.ts`) | read `contributor.txt` — `{id, ts}` JSON; delete ts → new id |
| ledger token stays out of URLs | `X-Device-Token` header on `GET`/`DELETE /v2/ledger` (`server/v2/ledger.py`, `Mobile/App.tsx`) | `tests/test_privacy_transport.py` |
| no coords in server logs | uvicorn `--no-access-log` (`server/Dockerfile`); `observability.py` denylist (`lat`, `lon`, `token`, `query_string`) | run a local uvicorn, `GET /aqi?lat=…`, inspect stdout → no request line |
| hazard pins are street-level | `round(lat,3)`/`round(lon,3)` ≈ 110 m in `community.report()` | `test_report_snaps_to_street_granularity` |
| review notes can't carry coords | `_redact_note` coord-pattern → ~1 km at ingest (`community.py`) | `test_review_note_coords_redacted_at_ingest` |
| delete-my-data is real | `clearAllData()` deletes `settings.json, ledger.json, contributor.txt, intro_seen.txt` (`Mobile/src/components/shell/settings.ts:45-52`), and `DELETE /v2/ledger` wipes server-side rows keyed to the token | grep `clearAllData`; `test_ledger_delete_via_header` |
| raw trajectory never logged | no logging statement exists in `trip.py` / `store.py` — `grep -n "log\|print" server/v2/trip.py server/v2/store.py` → nothing | code review |
| payload abuse cap | `MAX_POINTS = 5000`, `trip.py:31,65` | post >5000 points, `points_used` stays bounded |

## Residual limits (verified, not fixed — see PRIVACY.md "Known gaps")

| limit | why it stands |
|---|---|
| sybil: 3 fresh tokens can mint a corridor; joining a 2-device cell forces publication | unauthenticated donations — needs a bigger design lane (rate-of-identity proofing, DP) |
| device token is a bearer key: holder reads `/v2/ledger` | deliberate (no accounts); header transport + 30 d rotation bound the exposure |
| NLB/TLS terminator sees request lines in transit | infrastructural — app-level logging now carries no coords, but the wire still does |

## Fast greps

```bash
# does anything write raw coords to disk? (→ community.py _save writes _snapshot(), aggregates only)
grep -n "write_text\|put_object" server/community.py
# where can a token/id appear? (→ hashed at ingest; raw never persists)
grep -n "contributor\|token" server/v2/trip.py server/v2/store.py server/community.py
# who calls the donation endpoints? (→ /v2/trip from nav/engine.ts; /observe is 410)
grep -rn "postTrip\|/v2/trip" Mobile/src
# k-threshold sites
grep -n ">= 3\|tokens" server/v2/store.py server/community.py
```
