# Ledger-batch lane report — app-stress follow-ups

Source: `docs/lanes/ledger-batch.md` ← `docs/lanes/app-stress-report.md`
(`3711ccd`). Branch `base/v2`. All three items landed in one commit.

## F2 → fixed: ledger dedupe deleted, not sharpened

**Finding (MED):** `Mobile/src/store/ledger.ts` `logTrip` deduped on
`from`+`to`+`vehicle` display names with a 10-min keep-first window.
It ate two real trips on the hostile drive (a 1.8 km/1.1 µg and a
2.5 km/0.7 µg ride merged into earlier entries; 9 trips → 4 rows) and
its key was locale-fragile — `from`/`to` are display strings that
change with the app language ("सेंट्रल दिल्ली" vs "central Delhi"),
so the same physical trip keyed differently after a language flip.

**Decision: delete it.** The dedupe's only observed function was
masking phantom-arrival noise — a phantom 0-km entry absorbed the real
ride that followed it. That bug is fixed in `3711ccd` (odometer
arrival now requires `snap.offsetM <= OFF_ROUTE_M`). The only append
path is `NavSession`'s `onArrive` → `useShellFlow.recordTrip`, and the
engine already guarantees exactly one arrival callback per session
(`arrivedRef`, `engine.ts:300`). No double-write path remains that
dedupe could legitimately suppress — sharpening a wrong key would keep
eating real trips. "Prefer deleting it over sharpening it" — done.

**Evidence:** `node src/store/test-runner.mjs` — 18/18 pass, incl. 4
new `src/store/ledger.test.ts` cases: two same-name trips 4 min apart
→ both land; a real trip after a phantom-grade 0-km row → both land;
same O&D+vehicle persists as separate rows across reload; `deleteTrip`
still removes exactly one row.

## F3 → fixed: offline pill mounts above the nav turn card

**Finding (LOW):** the offline/stale pill rendered *under* the nav
turn-instruction card — only its tail peeked out mid-nav.

**Fix:** `Mobile/App.tsx` — moved the offline pill (and the pick-hint
that slides under it) to mount **after** `NavSession`, before the
sheet layer (`HomeScreen`/sidebar/`DelhiToday`/`LedgerScreen`/
`SettingsScreen`/`VehicleSheet`/`OnboardingScreen`). Z-order on this
stack is sibling mount-order on iOS and elevation-then-mount-order on
Android (the D1 finding): the pill shares the turn card's
`V2Elev.float` rung (elevation 5), so the later mount wins both
platforms — "above map chrome, below sheets" per the D1 ladder
(sheets sit at elevation 24/30 and still beat it). Moving the pill to
the `top+92` slot instead was rejected: during nav that slot belongs
to the engine's own status pills (reroute / outside-field /
strip-unavailable) — offline + failed strip is a guaranteed collision
class.

**Residual (honest):** verified by reasoning on the z-order rules the
D1 commit established + `tsc`/`lint` green; not re-driven on a device.
The overlap is now the pill's bottom edge over the turn card's lower
edge — the reverse of the bug and the mandated direction.

## N2 → fixed: /v2/trip plausibility floor

**Finding (note):** live `/v2/trip` accepted
`{distance_km:0, duration_s:37, trajectory:[]}` → `stored:true` —
phantom trips pollute the collective totals.

**State found:** HEAD already 422'd `distance_km` missing/zero
(`not summary.get("distance_km")` — live deployment predates that
hardening). The remaining hole was everything *near* zero: sub-100 m
"trips" and impossible implied speeds still landed in aggregates.

**Fix:** `server/v2/trip.py` — two floors after the existing gate,
before dedupe/record:
- `MIN_TRIP_KM = 0.1` — a sub-100 m donation is a cancelled nav or
  GNSS noise: real telemetry, never a traversal (its trajectory would
  trim to zero corridor cells anyway). **Decided + documented:** a
  cancelled-nav donation still POSTs from a real device but is not a
  trip — 422 at ingest; the app's own ledger.json keeps its row and
  the outbox drops 4xx permanently (`queue.ts postOne → "reject"`),
  so nothing retry-floods.
- `MAX_SPEED_KMH = 140` — implied average speed past every Delhi
  mode's physical ceiling (airport-express peak ≈120) is a bug or an
  injection. Checked only when `duration_s` is present and positive;
  no lower bound — Delhi jams really do park a trip for hours, and its
  in-traffic dose is honest data. `duration_s` stays optional
  (older clients); missing duration can't be speed-checked and isn't
  refused — the distance floor still applies.

**Evidence:** `PYTHONPATH=core/build312:. .venv312/bin/python -m
pytest` — donation-path suite green: **204 passed** across
`test_v2_hardening`, `test_v2`, `test_v2_ledger_roads`,
`test_community_v2`, `test_privacy_fuzz`, `test_privacy_transport`,
`test_contract_sync`. New cases in `test_v2_hardening.py`:
`test_trip_phantom_donations_rejected_and_never_counted` (the wire
capture `0 km/37 s` + sub-floor `0.04 km`, `900 km/h`, `duration_s:0`
→ all 422, and `/v2/city` day totals unmoved),
`test_trip_plausible_receipt_still_lands` (1.8 km/5 min auto ≈22 km/h
+ 12 km/6 min metro =120 km/h → 200 `stored`),
`test_trip_distance_only_donation_still_lands` (no `duration_s` →
200).

## Gates — all green

| gate | result |
|---|---|
| `cd Mobile && npx tsc --noEmit` | clean (needed `npm ci` first — node_modules predated the branch's font/expo-device deps) |
| `npx expo lint` | exit 0 (the cam.ts nit doesn't surface; bare `npx eslint` shows only pre-existing warnings/errors on untouched lines) |
| `node src/store/test-runner.mjs` | 18/18 |
| `node src/nav/test-runner.mjs` | 68/68 |
| server pytest (donation path) | 204/204 |
| live `http://65.2.28.40` | GET /health + /v2/city only — healthy, donations flowing; never POSTed |

## Files touched

- `Mobile/src/store/ledger.ts` — dedupe removed, rationale in comment
- `Mobile/src/store/ledger.test.ts` — new, 4 cases
- `Mobile/App.tsx` — offline pill + pick-hint moved after NavSession
- `server/v2/trip.py` — `MIN_TRIP_KM`, `MAX_SPEED_KMH` floor + comments
- `server/tests/test_v2_hardening.py` — 3 new cases

Never deployed; no native dirs touched.
