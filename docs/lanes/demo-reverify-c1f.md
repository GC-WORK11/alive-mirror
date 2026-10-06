# lane: demo-reverify-c1f — every published figure re-derived on live c1fbfb88

Read docs/demo-day.md + docs/plan/handoff.md first. base/v2 only, no deploy, no edits outside docs/.

Loop: pull --rebase; verify each numbered claim in demo-day.md + repo README + landing copy against LIVE http://65.2.28.40 right now; append a "re-verified @ c1fbfb88" table to docs/lanes/demo-reverify-c1f-report.md.

Checks (GETs + /v2/plan only — never POST /v2/feedback|observe|trip):
- dose gap O→D: India Gate 28.6129,77.2295 → Huda 28.4594,77.0725 — min vs max option doses, ratio
- option count range across 3-4 OD pairs incl. one short-hop
- breath ≈ cigarettes figure — landing live figure vs /v2/day
- day windows: least-bad hour vs published claim
- /v2/why trend: n_snapshots + span on the fresh task (record history is S3-side, should be non-zero)
- forecast claim wording: pooled MAE vs persistence (from /v2/day forecast basis + field-drift-watch method — if MAE can't be recomputed live, cite the fitted-blend commit + mark "unchanged")
- /v2/health edges_priced, field_age_s sane
- GRAP stage line + /admin comprehension captions present
- landing hero hnum = today's real figure (not a placeholder)

Report deltas >10% as FLAGGED with the new number. Never claim verified without the curl output pasted in the report.
