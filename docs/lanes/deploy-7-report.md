# Lane report — deploy #7: bus line-name fix to prod

**Date:** 2026-10-07 ~20:45–21:05 UTC. **Lane:** deploy + verify (deploys
permitted; everything else GET-only).

## What shipped

| | |
|---|---|
| **Deployed image** | `alive108-api:6bc2b808` (base/v2 HEAD `6bc2b80`) |
| **Previous prod / rollback target** | `1ada0052` — confirmed via `/health` `build_sha` pre-deploy |
| **Pipeline** | CodeBuild `alive108-build:c794b2bb-dddb-41f3-b354-1330cd7512f5` (S3 src.zip of `git archive HEAD:server`; fresh `~/.aws-venv` aws-cli/1.46.1; no docker on box → `BUILD_MODE=auto` took the codebuild path) |
| **Task definition** | `alive108:210` — api `6bc2b808` + osrm sidecar `:latest` (mem 3072) |
| **Task / target** | task `5ba3d805ceba44ed85bb5e8e190951ab`, ENI `eni-06a867bb7160e15fd` → `172.31.20.109`; TG re-registered, old `172.31.26.149` deregistered, target healthy → STABLE |
| **server/ diff vs `1ada0052`** | 2 files, +14/−2: `transit_v2.py` `line_name()`, `v2/plan.py` `_transit_option` |
| **web/ diff** | none — the rest of `1ada0052..6bc2b80` is Mobile + docs/screenshots |

**`transit_v2.py`** (`6bc2b80` audit-fix-2, DEPLOY-PENDING → now live):
`line_name()` strips DTC `UP`/`DOWN` suffixes as before, then maps
all-caps feed-internal ids matching `^[A-Z0-9_-]{9,}$`
(`CGOCOMPLEX-2`, `LNWST-1`, …) to plain `"Bus"` — ids a rider can't
board by are no longer shown as names. Real route numbers like
`347ACL` and board names like `HOHO` survive (the local feed holds
690 such suppressed ids out of 2964 bus routes).

**`v2/plan.py`** `_transit_option`: the option label dedupes the line
list and drops `?`/`Bus` members before joining, so a suppressed leg
reads `Bus 0AIRPORTEXP-4(NS) → 764EXT`, never `Bus CGOCOMPLEX-2`; a
journey whose every leg was suppressed collapses to plain `Bus`
instead of `Bus Bus`.

## Tests before ship — green

Fresh box bootstrap (no `.venv312`): homebrew py3.12 venv +
`requirements.txt` + pytest + pybind11, `brew install eigen` 5.0.1,
`core/build_ext.sh` → `core/build312/alive_core.cpython-312-darwin.so`,
then `PYTHONPATH=core/build312:. pytest -q`:

```
tests/test_transit*.py + test_emissions.py + test_v2_plan.py
  = 134 passed, 1 skipped, 13.4s
tests/ (full suite)
  = 1244 passed, 5 skipped, 8.7 min
```

## Verify on prod (GET only, plan via POST) — all live on `6bc2b808`

| Check | Result | Evidence |
|---|---|---|
| `/health` `build_sha` | `6bc2b808` == deployed tag ✓ | `ok:true`, `engine:alive_core`, `field_age_s:134`, 54 stations |
| Transit `/v2/plan` labels — real line names, no feed ids | ✓ | KashmereGate→Badarpur: **`Bus 405`** (gtfs, eta 10794); CP→Lajpat: **`Bus 0AIRPORTEXP-4(NS)`** — suppressed leg deduped out; CP→Dwarka: **`Bus 0AIRPORTEXP-4(NS) → 764EXT`** (gtfs). Zero `CGOCOMPLEX`/raw-id strings anywhere in options |
| `/aqi?lat&lon` | fresh ✓ | pm2.5 69.6 (ambient 64.5, band 49.4–89.8), US AQI 156, fires live 90/16-belt age 320s, wind age 323s, `beyond_field_edge:false`, smoke_modifier 1.08 |
| `/v2/search?q=ashok nagar shahdara` | anchor retry intact ✓ | 5 rows all "Ashok Nagar" (locality/administrative/…), `cov=0.667`, `match:token-prefix`, `source:alive_core` — identical shape to deploy-6 |

Local oracle (same feed data, pre-deploy): `plan_transit` replays
confirm suppressed legs surface as `Bus` and named legs survive —
`CP→Rohini` `['Bus','0OMS(-)(NS)']`, `SaraiKale→Gurugram`
`['0TMS(+)(NS)','Bus','Bus']`, `CP→Dwarka`
`['0AIRPORTEXP-4(NS)','Bus','764EXT']`.

Note: `0AIRPORTEXP-4(NS)`-style names still show — they contain
parens so they don't match the `^[A-Z0-9_-]{9,}$` suppression. That
is the committed behavior; a broader ugliness pass is audit-fix
scope, not deploy scope.

## Timings

| Step | Duration |
|---|---|
| CodeBuild (src.zip → ECR `:6bc2b808` + `:latest`) | ~2–3 min (SUCCEEDED) |
| ECS rollout `alive108:210` → services-stable + PRIMARY COMPLETED | ~3 min |
| TG health gate | healthy within first polls |
| Wall clock (script start → STABLE) | ~6 min |

## Drift during deploy

`c06f478` (offline-verify: plan flow `getCurrentPositionAsync`
fallback — Mobile-only) landed on base/v2 mid-roll. No `server/`
commits landed; the shipped delta is exactly
`git diff 1ada0052..6bc2b80 -- server/` = the two files above.

## Rollback note

```bash
./scripts/deploy.sh rollback 1ada0052   # prod sha before this lane — tag immutable in ECR
```
