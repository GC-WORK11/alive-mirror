# Lane report — deploy-eod: end-of-build-day prod deploy + surface verify

**Date:** 2026-10-07 ~09:35–10:00 UTC. **Lane:** deploy + verify (deploys
permitted in this lane; everything else stayed GET-only).

## What shipped

Two CodeBuild rolls this run — `9fbd8517` (task-def rev 202) went live, then
`1627a13` landed on `base/v2` mid-verify (server-touching: `v2/day.py` TZ fix
+ `admin.html` timing labels) and was deployed too so prod serves real HEAD.

| | |
|---|---|
| **Deployed image** | `alive108-api:1627a13f` (ECR tag = `BUILD_SHA` env) |
| **Previous prod** | `f9ea5ae8` |
| **Task def** | `alive108:203` (rev 202 carried the interim `9fbd8517`) |
| **Task** | `ad6610aaf06842a0918ddf87898b9d2c` |
| **Task ENI → IP** | `eni-044622c8d0753fee4` → `172.31.28.54` |
| **TG** | `alive108-tg` — `172.31.28.54:8080` **healthy**; `172.31.17.160` draining, `172.31.19.221` deregistered |
| **Pipeline** | `BUILD_MODE=auto` → CodeBuild `alive108-build:60d3cb29…` (S3 src.zip path, aws-cli/1.46.1, no docker on box) |

**Commits on prod now that weren't before** (`f9ea5ae8..1627a13f`):
`1627a13` code-truth server pass · `9fbd851` ios-residual (sim-only —
`Mobile/patches` + docs, zero server diff — verified) · `a45a443`/`95e6d7e`/
`b2ef3d2` notify-e2e evidence lanes · `b47ffd4` map depth r6 (`v2-light.json`
+ tileWarm — Mobile bundle, not in image) · `666c4c8` landing v6 · `b563da2`
admin HMAC-cookie sign-in · `f017dad` inline-script gate · ops-handover +
lane docs. Server diff vs old prod: `main.py` +114, `admin.html` rewritten,
`landing.html` v6, `middleware.py` +3, `v2/day.py` TZ pin, +`test_admin_auth`
(179 lines) +`test_inline_scripts`.

## Health-check table (all live-verified on `1627a13f`)

| Check | Result | Evidence |
|---|---|---|
| `alive108-tg` target health | `172.31.28.54` **healthy** | `describe-target-health` |
| `/health` `build_sha` | `1627a13f` == deployed tag ✓ | `ok:true`, edges 1,070,459 / priced 903,058, stations 52 (waqi+dpcc ok), `field_stale:false` |
| Landing `/` | boots ✓ | boot overlay dismissed; live **44.1 µg/m³ SATISFACTORY** painted + equation strip (f9ea5ae regression guard) — `deploy-eod-shots/landing-live.png` |
| `/admin` gate | login card, not board ✓ | "OPERATOR ONLY · operator token · SIGN IN" — `deploy-eod-shots/admin-gate.png` |
| `/city` | live ✓ | 29 districts, AQI 79, GRAP stage I chip, district map — `deploy-eod-shots/city-live.png` |
| `/community` | live ✓ | 24 phones / 44 trips / 10.9 mg / 31.4 km — `deploy-eod-shots/community-live.png` |
| `/v2/usage` guest | **401** ✓ correct — admin-auth landed, cookie required | `curl` |
| `/v2/day` | 200 w/ params | TZ fix verified live: `start:"2026-10-07T09:00"` → `ist_label:"14:30"` (UTC→IST correct on UTC host) |
| `/aqi?lat,lon` | 200 | pm25 64.1 breathing @CP, us_aqi 154 |
| Served-vs-HEAD | `/`, `/admin`, `/city`, `/community` all byte-identical to `1627a13f` ✓ | sha256 diff (`/community` needs `Accept: text/html` — it content-negotiates to the JSON API otherwise) |
| `tools/warm_task.py` | WARM ✓ | priced engine serving after 4 s; `/v2/plan` 1.7 s, transit rows; every endpoint ok incl. `/tiles/health` 22.7 MB |
| `scripts/verify_numbers.sh` | **zero flags** | full log `/tmp/vn-1627a13f.log` (this box); raw JSON `/tmp/verify_numbers.4xqLDC` |

## Rollback note

```bash
./scripts/deploy.sh rollback f9ea5ae8   # previous prod image — tag immutable in ECR
# or any known-good: aws ecr list-images --repository-name alive108-api
```

Sha tags are immutable; `9fbd8517` also exists in ECR now (verified build) but
`f9ea5ae8` remains the last fully-baked prod build pre-today.

## Drift / caveats

- **Lanes still landing** — `route-chooser` and further codebase sweeps were in
  flight per the lead session; anything landing after `1627a13f` is NOT on
  prod. Next deploy lane: pull, deploy, repeat.
- Stations read 52 (accept 52–54 per verify_numbers; 24 = DPCC-stall degrade,
  self-recovers).
- `verify_numbers` notes the `build_sha` wart is unchanged: `/health` shows
  `1627a13f`; on stage quote the ECR tag.
- Landing numbers drift with the field: 47.0 µg/m³ on the interim build,
  44.1 on final — both painted correctly; not a regression.
