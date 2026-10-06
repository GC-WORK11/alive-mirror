# Lead review — codebase-audit flags

Reviewed every item the hygiene lane flagged for judgment (`codebase-audit-report.md`
"Not applied" + review-needed section). Verdicts:

| flagged | verdict |
|---|---|
| `app/main.py` + `app/core/` slice | **phantom** — no such paths exist in the repo (checked filesystem + history-free present tree). Nothing to remove. |
| `scripts/rebuild` + `seeds.py` reference missing inputs | **phantom** — neither file exists under `scripts/` or `server/`. |
| AQI pipeline "triple-implemented" | **misread layers** — `airindex.py` (station index values) → `airfield.py` (spatial blend) → consumers (`why`, `city`, `rollup`, `forecast`, `admin_agg`, ~15 importers). Different stages, not duplicates. No merge needed. |
| SQLite/DDB dual backends runtime-selected | **by design** — `agg_ddb.py` is the prod aggregate path; local dev needs a no-AWS fallback. Runtime selection is the feature. |
| Mobile vs server gazetteer drift (same size, different md5) | **benign superset** — diffed: every server name exists in the mobile bundle; mobile adds 359 extra street-level entries for offline T0 search. Search can only resolve *more*, never less. No resync needed today; if we ever cut the bundle from the server copy, do it deliberately (server copy is `v2/gazetteer.py`'s source, `build_mobile_gaz.py` is the intended generator — worth a stamp comment later). |

## What this means for lane reports

Two of five flagged items were invented paths — lane reports are evidence-pointers,
not ground truth; every "needs-review" flag gets checked before being believed.

## Hygiene lane's applied work (verified)

`b7ce48f` unused imports (incl. a real F821 `day_of_week` fix in test_transit),
`64c122b` −66 lines zero-ref dead code, `a7517f6` single-sourced upstream URLs in
`server/upstreams.py`. Suite green 1146/10sk on the merged tree. All mechanical,
zero feature removal — matches the mandate.
