# privacy-f1-fix lane report — k≥3 gate on `contributors_detail()` day-rows

Date: 2026-10-07 · Branch: `base/v2` (base `212d795`) · Fixes: **F1** of
`docs/lanes/privacy-spine-report.md` (the one latent gap the spine
verify found). F2 assessed, not changed — see §4.

---

## 1. The gap (from the spine report)

`/admin/api` → `community.contributors_detail()` (community.py:610)
emitted one row per UTC day: `{day, trips, km, dose_ug, avoided_ug,
contributors, last_seen_min_ago, modes}` — with **no k-gate**. On a
sparse UTC day (<3 distinct devices) that is a *labelled* one-person
day-slice: everything one device did that day plus its last donation to
the minute — the exact leak class `recent_obs` suppresses at hour
granularity (community.py:656) and `global_aggregates` counts under
`suppressed` (v2/store.py:336-384). Live data was already ≥3 on every
day, so nothing identifying was being served — structural gap only.

## 2. The fix — same shape as `global_aggregates`/`recent_obs`

`server/community.py` `contributors_detail()`:

- day rows with `len(v["devices"]) < _K_MIN_DEVICES` are skipped and
  counted — one `if`, one counter, exactly the `recent_obs` predicate
  and the `global_aggregates` suppressed-block shape.
- return type is now `{"days": [...], "suppressed": {"day_rows": N},
  "days_tracked": M}` — rows list + suppressed counter + honest tracked
  count, mirroring `{"areas", "od_pairs", "suppressed", "areas_tracked",
  "od_pairs_tracked"}` on the global surface. `days_tracked` counts
  every tracked UTC day (suppressed + served), so a reader can tell
  "quiet day" from "suppressed day".

`server/main.py` `/admin/api`:

- `"contributors"` keeps its existing wire contract — the list of
  publishable day rows (consumers like `server/test_api.py` and ops
  curls are unchanged; `live_users` still derives from those rows).
- two sibling fields added, same namespacing as `/admin/api/global`:
  `"contributors_suppressed": {"day_rows": N}` and
  `"contributors_days_tracked": M`.

`docs/privacy/data-flow.md`: the `contributors_detail()` line now
states the k≥3-per-day gate + suppressed counting.

### Wire shape — before / after

Before (any sub-k day served as a labelled one-person slice):

```json
"contributors": [
  {"day": "2026-10-07", "trips": 5, "km": 31.4, "dose_ug": 10.9,
   "avoided_ug": 312.9, "contributors": 1, "last_seen_min_ago": 383,
   "modes": ["bus", "car"]}
]
```

After (the same day is counted, never emitted):

```json
"contributors": [
  {"day": "2026-10-06", "trips": 9, "km": 41.2, "dose_ug": 27.1,
   "avoided_ug": 96.4, "contributors": 3, "last_seen_min_ago": 1490,
   "modes": ["bus", "car", "metro"]}
],
"contributors_suppressed": {"day_rows": 1},
"contributors_days_tracked": 2
```

(Values illustrative — the shape is the point: `contributors` rows all
carry `contributors >= 3`; sub-k days surface only as a counter.)

## 3. Tests — matching the suite's k-gate pattern

In `server/tests/test_community_v2.py`, next to the existing
`recent_obs`/`corridor` suppression cases:

- `test_contributors_detail_suppresses_sub_k_days` — a 2-device UTC day
  does not appear (counted as `suppressed.day_rows: 1`,
  `days_tracked: 2`); a 3-device day does.
- `test_contributors_detail_k_counts_devices_not_trips` — three
  donations from ONE device is k=1, not k=3: the day stays dark
  (same pin as `test_recent_obs_counts_devices_not_trips`).
- `test_contributors_detail_is_day_rollup_not_devices` + the snapshot
  round-trip — updated for the `{"days", "suppressed",
  "days_tracked"}` return shape; the k=3-day shape assertions are
  unchanged.
- `ALL_OUTPUTS` banned-key/no-coords walks still cover the function —
  the new dict is walked the same way.

Evidence:

```
pytest -q tests/test_community_v2.py            → 35 passed
pytest -q tests/test_admin_agg.py test_admin_usage.py
        test_landing_serve.py test_privacy_fuzz.py
        test_admin_v2.py test_city_moves.py      → 78 passed
pytest -q tests (full suite)                     → 1244 passed, 5 skipped
```

(First full-suite run on this box: `.venv312` created +
`core/build_ext.sh` built `alive_core` — none of the pre-existing
env-fails apply; the skips are the 5 usual platform skips, not
failures.)

## 4. F2 — assessed, deliberately not changed

The spine report itself marks F2 "minor" and "arguably fine":
`last_24h.devices`/`today`/`dose.daily`/`per_hour` are **bare counts**
— `test_usage_k_guard_is_structural` asserts counts-not-persons
deliberately. Unlike F1 they carry no per-day *labelled slice*
(modes/km/dose/last-seen joined on one row). Gating them would change
honest ops counters (`journeys_per_hour`, `today`) into
sometimes-suppressed ones — a different, debatable contract change, not
the same one-line shape. Left as-is; flagged for a policy decision, not
a patch.

## 5. Scope / no-deploy

Files: `server/community.py` (+28/-11), `server/main.py` (+7/-1),
`server/tests/test_community_v2.py` (+35/-3),
`docs/privacy/data-flow.md` (+4/-1), this report. No client surfaces
read `contributors[]` (admin.html fetches only the `/admin/api/*`
sub-resources + `/v2/usage`). **Not deployed** — the deploy lane
batches; on next deploy the fix is live.
