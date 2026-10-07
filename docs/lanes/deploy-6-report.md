# Lane report — deploy #6: search anchor-retry + emissions wording to prod

**Date:** 2026-10-07 ~18:55–19:10 UTC. **Lane:** deploy + verify (deploys
permitted; everything else GET-only).

## What shipped

| | |
|---|---|
| **Deployed image** | `alive108-api:1ada0052` (base/v2 HEAD `1ada005`) |
| **Previous prod / rollback target** | `7c68c8bc` — confirmed via `/health` `build_sha` pre-deploy |
| **Pipeline** | CodeBuild `alive108-build:085400a0-4fd4-4c0f-bdf0-33387cfb580c` (S3 src.zip of `git archive HEAD:server`, aws-cli/1.46.1 fresh `~/.aws-venv`; no docker on box → `BUILD_MODE=auto` took the codebuild path) |
| **Task definition** | `alive108:209` — api `1ada0052` + osrm sidecar `:latest` (mem 3072) |
| **Task / target** | task `64f72ef9885f4b3099d6456bc62e32fa`, ENI `eni-07b7eddaf1ac73b13` → `172.31.26.149`; TG re-registered, old `172.31.26.129` deregistered, target healthy → STABLE |
| **server/ diff vs `7c68c8bc`** | 4 files, +38/−15: `core_engine.py` (search anchor retry), `emissions.py` + `tests/test_emissions.py` (label wording), `v2/strip.py` (basis fallback text) |

**core_engine.py anchor retry** (the `ashok nagar shahdara` fix,
`c583cab`): `_subplace` now tries variants — full phrase → minus
digits → trailing-context shrink — so a glued-on context token can't
starve the anchor. `_compound` takes the anchor phrase right of the
LAST near-class marker (left-side name qualifiers like 'pawan bakery'
no longer glue to the anchor) and shrinks from the right until a
candidate clears `cov ≥ 0.75`.

**emissions.py + strip.py** (`4fa85ea`): label wording "estimated for
vehicles like yours" → "estimated for a \<fuel\> \<class\>"; strip's
`basis` fallback matches. Pure string changes; `test_label_shape`
updated to pin the new prefix.

## Tests before ship — green

`.venv312` + `core/build312/alive_core.cpython-312-darwin.so` built
fresh on this box (brew eigen 5.0.1, `core/build_ext.sh`), then
`PYTHONPATH=core/build312:. pytest -q`:

```
tests/test_emissions.py        — label chain incl. updated test_label_shape
tests/test_query_tolerance.py  — compound/subplace/anchor suite (incl. p95<50ms on C++ path)
tests/test_core_engine.py      — engine adapter contract
tests/test_inline_scripts.py   — landing script gate
= 60 passed, 2.7s
```

Honest caveat: on the pure-Python engine path (no `.so`),
`test_search_latency_compound_path` fails its 50ms gate at ~122ms —
environmental, not a regression: it fails identically at `7c68c8bc`
(~116ms, measured in a `7c68c8bc` worktree). Prod runs `alive_core`.

## Verify on prod (GET only) — all live-verified on `1ada0052`

| Check | Result | Evidence |
|---|---|---|
| `/health` `build_sha` | `1ada0052` == deployed tag ✓ | `ok:true`, `engine:alive_core`, `field_age_s:157`, station sources up |
| `/v2/search?q=ashok nagar shahdara` | **5 rows — retry works live** ✓ | all "Ashok Nagar" (locality/administrative/neighborhood/platform), `cov=0.667` (2/3 tokens — 'shahdara' context dropped, `token-prefix` match), `t1_engine:alive_core`, `took_ms t1:5.4`, HTTP 200 in 0.47s |
| `/aqi` (real route; `/v2/aqi` is 404 by design) | fresh ✓ | pm2.5 67.6 (ambient 62.6, band 47.6–87.5), US AQI 155, fires live 90/16-belt age 189s, smoke_modifier 1.08, field edge ok |
| Compound regression `'atm near cp'` | unchanged ✓ | anchored on Connaught Place: SBI ATM 41.8m, Pi-Lo water ATM 77.2m, `compound:true`, `anchor:"Connaught Place"` |

Note for the report chain: the prompt named `/v2/aqi`; the served
route is `/aqi` (main.py:1048). Verified `/aqi` — that's what the app
calls.

## Timings

| Step | Duration |
|---|---|
| CodeBuild (src.zip → ECR `:1ada0052` + `:latest`) | ~121 s (SUCCEEDED) |
| ECS rollout `alive108:209` created → COMPLETED | ~174 s |
| TG health gate | first poll healthy |
| Wall clock (script start → STABLE) | ~5.5 min |

## Drift during deploy

None — `git log 7c68c8bc..HEAD -- server/` captured at deploy start is
the full shipped delta; no `server/` commits landed mid-roll.

## Rollback note

```bash
./scripts/deploy.sh rollback 7c68c8bc   # prod sha before this lane — tag immutable in ECR
```
