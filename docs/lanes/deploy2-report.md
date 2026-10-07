# Lane report — deploy #2: news-layer (`cause_note`) to prod

**Date:** 2026-10-07 ~10:35–10:50 UTC. **Lane:** deploy + verify (deploys
permitted in this lane; everything else stayed GET-only — one sanctioned
`/v2/plan` POST inside `tools/warm_task.py`).

## What shipped

One CodeBuild roll. `git log 1627a13f..HEAD -- server/` audit before deploy:
**only `795ff3b` touches the image** — news-layer `cause_note`
(`server/v2/why.py` `_cause_note` + `server/v2/city.py` passthrough +
`server/city.html` parali-watch tile + `server/tests/test_v2_why.py`).
Everything else on `base/v2` since prod is docs/Mobile (`698cf80`, `1c062c3`,
`b281262`, `c3f7e9e`, `b633a2d`, `d8e38e8`, `82e1c64`, `e2ff634`) — no other
server-side changes from the deploy-eod report's post-deploy window needed
shipping.

| | |
|---|---|
| **Deployed image** | `alive108-api:698cf808` (base/v2 HEAD; ECR tag = `BUILD_SHA` env) |
| **Previous prod** | `1627a13f` (rollback target) |
| **Task def** | `alive108:204` (cpu 1024 / mem 3072, osrm sidecar on) |
| **Task** | `ffd3f643fde143f2a003c94102e730b5` |
| **Task ENI → IP** | `eni-0c0082d5d9a9cdb19` → `172.31.20.254` |
| **TG** | `alive108-tg` — `172.31.20.254:8080` **healthy**; old `172.31.28.54` deregistered |
| **Pipeline** | `BUILD_MODE=auto` → CodeBuild `alive108-build:fb7a7695-5cba-4cfc-9a39-6de68256efc7` SUCCEEDED (S3 src.zip path, aws-cli/1.46.1 fresh venv, no docker on box) |
| **Rollout** | PRIMARY deployment `rolloutState COMPLETED`, ~7 min end-to-end |

## Health-check table (all live-verified on `698cf808`)

| Check | Result | Evidence |
|---|---|---|
| `alive108-tg` target health | `172.31.20.254` **healthy** | `describe-target-health` |
| `/health` `build_sha` | `698cf808` == deployed tag ✓ | `ok:true`, edges 1,070,459 / priced 903,058, `field_stale:false`, stations 52 (`waqi`+`dpcc` both `ok`), fires 44 live age 128s |
| **`/v2/why` `cause_note`** | populated ✓ | `"12 fires in the Punjab–Haryana belt — the wind isn't carrying it this way right now · city mean 60.6 → 46.8 µg/m³ over 5.8 h"`; `cause_note_fields` complete (`basis:measured`, belt_fires 12, carrying false, wind 241°/9.9 km/h, trend 60.6→46.8/5.8h) |
| **`/v2/city` `why.cause_note`** | populated ✓ | same note + fields, nested under `why` (top level is null by design — tile reads `cy.why.cause_note`) |
| **`/city` parali-watch tile** | renders on live data ✓ | tile unhidden, shows the note + `· measured, not reported` — `deploy2-shots/city-parali-tile.png` |
| Air-event `{note}` | wired ✓ | `Mobile/src/store/events.ts` — `noteFor()` appends `causeNote(causeFieldsFromWhy(why))` to fires/band/stag/severe/grap/trend/outlook bodies (server serves the note on `/v2/why`; app re-localizes from `cause_note_fields`) |
| Landing `/` | boots ✓ | 200; live **43.2 µg/m³ SATISFACTORY** painted + equation strip (43.2 × 14.4 m³/day ≈ 620 µg = 2.0 cigs), "52 instruments" — `deploy2-shots/landing-live.png` |
| `/admin` gate | login card, not board ✓ | 200; "OPERATOR ONLY · operator sign in" |
| `/community` | live ✓ | 200 (Accept: text/html) |
| `/aqi` @CP | 200 | pm25 62.2 breathing / 58.7 ambient, us_aqi 153, nearest sample 1.8 km |
| Served-vs-HEAD | `/`, `/admin`, `/city`, `/community` byte-identical to `698cf808` ✓ | sha256 diff vs `git show HEAD:server/*.html` |
| `tools/warm_task.py` | **WARM** ✓ | priced engine serving after 5 s; `/v2/plan` 2.2 s 23 rows w/ transit; every endpoint ok incl. `/tiles/health` 22.7 MB |
| `scripts/verify_numbers.sh` | **zero flags** | "all quoted numbers match live within their stated precision" — full log `/tmp/vn-698cf808.log`, raw JSON `/tmp/verify_numbers.JHaYLt` (this box) |

## Rollback note

```bash
./scripts/deploy.sh rollback 1627a13f   # previous prod image — tag immutable in ECR
# or any known-good: aws ecr list-images --repository-name alive108-api
```

`1627a13f` was the sha `/health` reported before this deploy (deploy-eod's
build); sha tags are immutable so rollback redeploys the identical image
through the same task-def + NLB pipeline minus the build.

## Drift / caveats

- **Lanes still landing** — anything committed to `base/v2` after `698cf808`
  is NOT on prod. Next deploy lane: pull, deploy, repeat.
- `/v2/city` top-level `cause_note` is null by design — the wire nests it
  under `why` (verified: `cy.why.cause_note` populated, that is what the tile
  and mirrors read).
- Landing numbers drift with the field (43.2 vs eod's 44.1) — not a
  regression.
- `verify_numbers` notes the standing `build_sha` wart: `/health` shows
  `698cf808`; on stage quote the ECR tag.
- Demo-day freeze per `docs/demo-day.md`: T-60 → demo end is a no-deploy
  window — this deploy is safely outside it at time of writing (~16:15 IST,
  Oct 7).
