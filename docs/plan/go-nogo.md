# ALive-108 — demo-morning GO/NO-GO checklist

Run order matters: the public repo goes out **before** any of the live
checks (a squashed baseline commit is only legal if authored inside the
Oct 8–11 window), and the on-demand flip precedes warming so the warm
task lands on the stable capacity provider.

`NLB = http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com`
All commands verified against live on 2026-10-05 (build `951eeb3c`).

| # | T-minus | check | command / action | pass threshold |
|---|---------|-------|------------------|----------------|
| 1 | first | **public repo exists + baseline pushed** | Create an EMPTY public repo on GitHub (no README), then `./scripts/public-repo.sh https://github.com/<owner>/<new-repo>.git`. Script logic verified (do NOT run early): `git checkout --orphan public-baseline $(git log -1 --format=%H origin/main)` → `git add -A` → one commit "baseline: ALive-108…" → `push public-repo public-baseline:main` → `git checkout main` + branch/remote cleanup. Orphan squashes history to a single commit whose author/committer date is run-day — inside the Oct 8 window. | `git status --porcelain` empty on `main` BEFORE running (orphan checkout + `git add -A` sweeps whatever is in the tree); `git branch --list public-baseline` empty (delete if a stale one exists); after: `gh repo view <new> --json pushedAt` shows one commit, main = baseline, dated Oct-8. Keep hacking on the PUBLIC repo after — later commits are legal by date. |
| 2 | T-60 | **Spot → on-demand flip** (owner's runbook step — do NOT pre-run) | `aws ecs update-service --cluster alive108 --service alive108 --capacity-provider-strategy "capacityProvider=FARGATE,weight=1,base=1" --force-new-deployment` (full cmd + rollback: docs/demo-day.md §"FARGATE_SPOT → on-demand") | `aws ecs describe-services --cluster alive108 --service alive108 --query 'services[0].{cap:capacityProviderStrategy,running:runningCount}'` → provider `FARGATE`, running 1/1, rollout COMPLETED. ~₹8/hr on-demand — flip back after judging (rollback cmd in same section). |
| 3 | T-45 | **NLB + service health** | `curl -s $NLB/health` | HTTP 200 · `stale:false` · `engine:alive_core` · `routing.edges`=1,070,459 (903,058 priced) · `wind.known:true` · `build_sha` = the build you rehearsed on (re-verify: `aws ecs describe-services` task-def rev matches docs/plan/demo-script.md header). |
| 4 | T-45 | **WAQI freshness + field age** | `curl -s $NLB/health` → `sources.stations`; `curl -s "$NLB/aqi?lat=28.6315&lon=77.2167"` → `field` block | WAQI feed status `ok` and station count ≥20 (24 today); `field.age_s` < 900 s and `refresh_in_s` > 0 counting down — a field older than 15 min means the ingest loop died; check ECS logs before continuing. |
| 5 | T-40 | **warm the task** | `python3 tools/warm_task.py` (base URL is baked in; optional `--timeout 300 --ods 12`) | exit 0 → prints `WARM: priced engine serving after Ns` — engine-priced plan rows appeared inside the timeout (it walks /health, /aqi, /grid, 12 real ODs, /reports, /v2/city, /tiles/health and retries plans until `steps_source:"endpoints"` rows show). exit 1 = engine never priced → NO-GO until logs explain it. |
| 6 | T-30 | **demo OD warm + armed** | `curl -s -X POST $NLB/v2/plan -H 'content-type: application/json' -d '{"from":{"lat":28.6315,"lon":77.2167},"to":{"lat":28.495,"lon":77.089}}'` | `options` ≥15 rows incl. a `mode:"metro+walk"` row with `steps_source:"gtfs"`; warm `took_ms` < 2000 (0.55–0.63 s today). Cold far-ODs can hit the 20 s planner budget → `options:[] + error:"planner timed out"` — the rehearsed OD must be warm BEFORE stage. |
| 7 | T-30 | **AWS console session armed** | Console tab pinned: `https://ap-south-1.console.aws.amazon.com/ecs/v2/clusters/alive108/services/alive108/health` — signed in BEFORE leaving for the venue. CLI understudy (no login needed on stage): `aws ecs describe-services --cluster alive108 --service alive108 --query 'services[0].{status:status,running:runningCount,taskDef:taskDefinition,capacity:capacityProviderStrategy}'` | Console renders ACTIVE · 1/1 · Fargate (post-flip: `FARGATE`). CLI returns the same — prints `alive108:NNN · FARGATE` (was `:141` at this writing). The video MUST show the console — no console, no score. |
| 8 | T-30 | **admin token reachable** | `aws secretsmanager describe-secret --secret-id alive108/admin-token` (SM, ap-south-1) → then `curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer <token>" $NLB/admin/api` | secret exists; `/admin/api` returns **200** with Bearer (401/403 = wrong/missing token — the public `/admin` page still renders but its data tiles stay empty). |
| 9 | T-20 | **APK on the demo phone** | Latest documented release APK = lane-4890a49f build on `e849bf6f` (130 MB, NLB + donate-fields proven in bundle). Verify on-device: app opens → plan CP→Gurugram returns rows → no spinner-only screens. | **Caveat:** `e849bf6f` predates four Mobile commits incl. `266d0d9` (Modal→overlay, kills a render-thread SIGSEGV class) and `d3f48d7` (client-side dose constants re-anchored). If the demo shows Settings/Ledger/nav sheets or quotes app-side dose, rebuild the APK on demo HEAD; if it only shows server-driven plan/city numbers, e849bf6 is honest but carries the crash risk. Check `strings` in `assets/index.android.bundle` for the NLB hostname + no `10.0.2.2`. |
| 10 | T-20 | **backup video on the presentation device** | `alive108-twitter-final.mp4` (2:08 arc) + `alive108-twitter-64s.mp4` — recorded takes live with the recording box/attachments; play once with Wi-Fi OFF. Plus ≤10 s screen-record of the ECS console (required footage). | Files exist locally on the device that plays them AND play under airplane mode. If Wi-Fi dies on stage this video is the demo. |
| 11 | T-15 | **connectivity** | `curl -s -o /dev/null -w '%{http_code}' $NLB/health` on hall Wi-Fi AND on phone hotspot | 200 on both. NLB is HTTP :80 only — captive-portal Wi-Fi breaks it silently; hotspot is the fallback. No custom domain registered: the URL IS the NLB hostname — confirm `getent hosts alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com` → `65.2.28.40` before stage. |
| 12 | stage | **verbatim lines drift-safe** | Re-read `curl $NLB/health` + `/aqi` CP once at T-45 and T-10 | Every quote in docs/plan/demo-script.md is phrased in ranges ("about", "over") — if a number moved outside its range, adjust the line, don't quote the stale figure. Field refreshes every 15 min. |

## NO-GO conditions (fix or cut, don't fake)

- `/health` `stale:true` or `field.age_s` stuck > 900 s after two refresh cycles.
- `warm_task.py` exit 1 — engine never priced within 5 min.
- Demo-OD plan returns `options:[]` twice in a row (budget timeout retry once, then cut to the backup video).
- Public repo not pushed — the Oct-8-history rule is a disqualifier, not a downgrade.
- Phone APK crashes on open twice — demo the web surfaces (`/`, `/admin`, `/v2/city`) instead; they're the same numbers.

## Known-honest warts (already verified — narrate, don't hide)

- A cold far-OD plan can return `options:[] + error:"planner timed out"` — the 20 s arm budget is real; the retry answers.
- The ammonia species param is served but empty today — the species line says ten, not eleven.
- `/depart` says "leave now" on a calm morning (best hour only ~16% under now) — the evening peak (~8×) is the headline.
