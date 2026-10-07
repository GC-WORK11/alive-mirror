# Lane report — deploy #4: skill-latency to prod

**Date:** 2026-10-07 ~12:20–12:45 UTC. **Lane:** deploy + verify (deploys
permitted; everything else GET-only — the one sanctioned `/v2/plan` POST
inside `tools/warm_task.py`).

## What shipped

One CodeBuild roll. `git log 43913dc0..HEAD --oneline -- server/` audit
before deploy: **only `44993d6` touches the image** — skill parsed-doc
cache (`_DOCS` sig-checked `(d,hh)` map; the 6 s tail was O(archive) S3
reads per miss — cold fill 6.3 s→~1 s, miss ~0.13 s). `06b774a` is the
lane's own report; everything else since prod is docs/lanes.

| | |
|---|---|
| **Deployed image** | `alive108-api:c86074ff` (base/v2 HEAD at deploy time; ECR tag = `BUILD_SHA` env) |
| **Previous prod / rollback target** | `43913dc0` — confirmed via `/health` `build_sha` pre-deploy |
| **Task def** | `alive108:206` (cpu 1024 / mem 3072, osrm sidecar) |
| **Task** | `a6037c81ebb64e63897888a33dc5c990` |
| **Task ENI → IP** | `eni-0abd639c2db6750e9` → `172.31.20.241` |
| **TG** | `alive108-tg` — new IP registered; old `172.31.28.112` deregistered; STABLE |
| **Pipeline** | `BUILD_MODE=auto` → CodeBuild `alive108-build:89adfd2f-09a6-40ce-953c-d39b2ef7f32d` (S3 src.zip of `git archive HEAD:server`, aws-cli/1.46.1 fresh `~/.aws-venv`, no docker on box) — ~8 min end-to-end |
| **Mid/post-deploy drift** | `71a154a`, `c1f22da` landed during/after rollout — **docs-only, zero `server/` delta** (`git log HEAD..origin -- server/` = 0), no redeploy needed |

## THE WIN — `/v2/skill` miss latency, prod-measured

Baseline caught on old prod `43913dc0` minutes before deploy: **5.25 s**
miss → 0.72 s hit (consistent with the lane's documented 4.8–4.9 s miss
series every ~120 s).

On new prod `c86074ff` (this box's RTT floor to the ELB ≈ 0.5 s — subtract
it for server-side times):

| Measurement | Time | `generated_ist` | What it was |
|---|---|---|---|
| warm pair a | 0.565 s | 18:04:49 | payload-cache hit (~0.06 s server-side) |
| warm pair b (+1 s) | 0.563 s | 18:04:49 | payload-cache hit |
| spaced-1 (+125 s) | **0.714 s** | 18:07:20 | **real recompute** (~0.2 s server-side) |
| spaced-2 (+125 s) | **0.720 s** | 18:09:26 | **real recompute** |
| spaced-3 (+125 s) | **0.708 s** | 18:11:31 | **real recompute** |

`generated_ist` advanced on every spaced hit → each was a genuine doc-
cache-backed recompute, not a payload-cache serve. Miss cost went from
**~5–6 s wall → ~0.7 s wall (~0.2 s server-side)** — the parsed-doc cache
works on prod. First-hit ~1 s / second <0.5 s target holds once the
~0.5 s vantage RTT is subtracted.

Cold-task note (honest): the first four hits in the minutes right after
the task registered ran 1.35–4.9 s despite payload-cache hits (same
`generated_ist`) — new-task contention while GTFS/graph/reweight loaded.
Post-warm all hits ≤0.72 s.

## Standard sweep (all live-verified on `c86074ff`)

| Check | Result | Evidence |
|---|---|---|
| `/health` `build_sha` | `c86074ff` == deployed tag ✓ | `ok:true`, routing loaded (1,070,459 edges / 903,058 priced), `field_stale:false`, engine `alive_core`, stations 54 (waqi+dpcc), fires 44 |
| Landing boots + live number | 200, 1.42 s, 115,803 B ✓ | `#boot` strip + `alive_boot_v1` sessionStorage key + `32 µg` live reading in served HTML |
| `/admin` | gate card, not board ✓ | 200 "engine room" sign-in (login/password/token fields); admin data not served unauthenticated |
| `/city` `why.cause_note` tile | populated ✓ | `"16 fires in the Punjab–Haryana belt — a N wind at 5.9 km/h is carrying it toward Delhi · air barely mixing — ventilation 1,364 m²/s vs ~3,000 typical"` (nested under `why` — top-level null by design) |
| `/community` | live aggregates ✓ | 200 JSON: `obs_total:44`, `obs_today:5`, `km_today:31.4`, `dose_ug_today:10.9`, `avoided_ug_today:312.9` |
| `/v2/usage` guest | **401** ✓ | unauthenticated rejected |
| `/reports` guest | 200 ✓ | public board surface (by design) |
| Served-vs-HEAD | `/`, `/admin`, `/city` **byte-identical** | sha256 match `git show HEAD:server/{landing,admin,city}.html` |
| `tools/warm_task.py` | **WARM** ✓ | "priced engine serving after 5 s · transit rows on 1 plan OD(s)"; `/v2/plan` 2.2 s 23 rows w/ 15 engine + 1 transit; every probe ok incl. `/v2/archive` 3.8 s, `/tiles/health` 22.7 MB z[0,14] |

Independent confirmation: watchdog lane `c1f22da` swept this same deploy
and reported PASS (cause_note flipped to carrying=true — 16 fires, N
wind — matching this report's tile text).

## Rollback note

```bash
./scripts/deploy.sh rollback 43913dc0   # previous prod — tag immutable in ECR
```

Likely the last deploy pre-freeze (`docs/demo-day.md`: T-60 → demo end =
no pushes/deploys).
