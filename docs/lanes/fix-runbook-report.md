# Lane report — fix-runbook (repairs `docs/demo-day.md` per audit-runbook)

**Lane:** docs-fix. Only files under `docs/` changed: `docs/demo-day.md`
+ `docs/submission/submission-checklist.md` (shared bugs).
**HEAD at fix:** `086a502` (base/v2, pulled 2026-10-07 ~02:50 UTC).
**Audit repaired:** `docs/lanes/audit-runbook.md` (086a502).

## Bug → fix table (every fix verified against code/scripts)

| # | bug (audit ref) | fix | where |
|---|---|---|---|
| 1 | **P0 APK**: demo-day named `alive108-0b11123.apk`, checklist named `alive108-c3bb731.apk` — both predate ~30 Mobile commits incl. demo-flow fixes `344b4a9` (first-tap occlusion) + `c84b5c2` (phantom re-plan) | Rewrote both steps parameterized: "install the newest `alive108-<sha>.apk` built at HEAD"; build recipe + sha256 verified against `docs/lanes/apk-v10-report.md` (or newest `apk-*-report.md`); stale names explicitly marked do-not-install. Checklist Status + §0 video-beat lines kept as history but carry the staleness caveat + re-tape note. | demo-day.md L356–367; submission-checklist.md L19–26, L52–53, L165–172 |
| 2 | `$NLB` never `export`ed → every `curl $NLB/…` failed as pasted | New "## Runbook setup" block at doc top (before the first `$NLB` use in the admin-flow section): resolves DNS via `aws elbv2 describe-load-balancers --names alive108` (deploy.sh's `NLB_NAME`), prints the HTTP-:80-only note, pins the known DNS `alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com` as the no-CLI fallback, then a `curl $NLB/health` smoke check. Same export block added atop submission-checklist §3. | demo-day.md L176–195; submission-checklist.md L110–117 |
| 3 | No AWS-creds preflight — dead creds mean the T-60 flip silently never runs | `aws sts get-caller-identity` + `region=ap-south-1` check added at the top of the flip code block itself (so it's un-skippable as pasted) with an explicit ABORT comment; the T-60 checklist line and §3 T-60 both reference it. | demo-day.md L610–616, L756–759; submission-checklist.md L119–129 |
| 4 | T-25 pointed at `/reports` — the k≥3-corridors GeoJSON (`community.reports_geojson()`), live-verified empty `features:[]`; no theme/colors exist there | Rewritten to the real surfaces: open `$NLB/admin` (public board renders tokenless — `server/main.py` L1620 → `server/admin.html` light paper/ink theme; "operator sign in" chip unlocks internals) + `curl -s $NLB/community` for the totals a donation increments (`obs_total`/`obs_today`/`contributors`/`latest_obs_age_min` — `community.py` `totals()`). The `/reports` misdirect is called out so nobody looks there. | demo-day.md L781–788 |
| 5 | T-15 self-contradiction — an offline pass can never make a k≥3 corridor from one donation | Rewritten: run the pass on the pre-seeded flow; an offline donation honestly queues on the device (receipt "saved — will send when back online" `strings.ts:458`, outbox pill "N saved to send" `strings.ts:399`; `Mobile/src/offline/queue.ts` `enqueueTripDonation` → `/v2/trip`), auto-flushes on reconnect (`wireAutoFlush` on next successful request), then verify landing via `/community` totals +1 or the signed-in admin live feed (`/admin/api.reports` ← `community.live_reports()`). | demo-day.md L789–797 |
| 6 | Double-rollout footgun — bump block's `update-service` already carries the FARGATE strategy; flip + bump = two deployments | Bump section retitled "INSTEAD of the flip, never both" + mutual-exclusion paragraph: plain flip for single-device, bump instead when judge devices hit concurrently; the choice rationale is stated inline. Budget note under the checklist reiterates the bump is outside the 31–35 min window math. | demo-day.md L657–665, L813–817 |
| 7a | No phone-battery step | T-30 network line now carries battery >80% + power bank + cable + hotspot pre-armed as fallback uplink. | demo-day.md L769–773 |
| 7b | Admin token never staged | New T-30 line: token physically at hand — Secrets Manager `alive108/admin-token` = the `ALIVE_ADMIN_TOKEN` env the task def injects (`server/main.py:1561` reads `os.environ.get("ALIVE_ADMIN_TOKEN")`); fetch command included; needed for the `/admin` sign-in chip. | demo-day.md L774–780 |
| 7c | Localhost backup never booted → untested backup | New "before leaving" line: `docker compose up --build` → `curl http://localhost:8080/health` 200 (repo-root `docker-compose.yml` publishes :8080; `server/Dockerfile` build); `.venv312` uvicorn line in §iOS noted as the no-Docker path. Marked fallback-only. | demo-day.md L801–806 |
| 7d | "If live breaks" assets not localized | Backups line now names `docs/video/cut1.mp4` + `docs/video/cut2.mp4` (verified present, 3.3/4.3 MB), copy-to-phone + airplane-mode play-test. | demo-day.md L807–811 |
| 7e | `warm_task.py` path | **No bug** — every reference already says `tools/warm_task.py` (grep-verified: zero `scripts/warm_task` anywhere); the `scripts/` guess was the audit's probe. No change needed. | — |
| 8 | Timeline table | demo-day.md had no timeline table; added a "Budget check" paragraph keeping the audit-verified ~31–35 min / ~25 min slack arithmetic, noting the new in-window steps add <2 min and the bump is outside the budget. | demo-day.md L813–817 |

## Adjacent audit findings also fixed (inside the same blocks)

| bug | fix | where |
|---|---|---|
| Post-flip verify read only `taskArns[0]` — mid-rollout it can return the draining SPOT task (false alarm at the worst moment) | `describe-tasks` now iterates ALL task ARNs (`taskArns[]` unquoted multi-arg) with the "a lingering FARGATE_SPOT row before services-stable is the old task leaving" explanation | demo-day.md L636–644 |
| `services-stable` waiter budget (~10 min) unexplained; failed-rollout-is-not-outage unstated | Comment added inline: re-run the wait once on error; FAILED rollout leaves old SPOT serving = degraded safety, not outage; decide re-run/accept/abort per NO-GO. Same "degraded safety" line added to submission-checklist T-60. | demo-day.md L628–631; submission-checklist.md L127–129 |
| Public-repo prereqs absent from demo-day (script `git ls-remote`s and dies); checklist §1 described stale mechanics (orphan checkout + `git add -A`, "pushes origin/main HEAD") | demo-day §Public-repo gained the prereq paragraph (EMPTY repo first — no README/license — + push auth; `commit-tree` of the tip-most of {base/v2, main}, never touches the worktree). Checklist §1 rewritten to the real mechanics. | demo-day.md L726–733; submission-checklist.md L74–83 |
| Three checklists diverge with no cross-links | Companion-checklist note added atop the demo-morning checklist naming submission-checklist §3 (richer sequence: token probe, both-networks, NO-GO) and `docs/plan/go-nogo.md` (gate table). | demo-day.md L746–750 |
| Doc self-drift: `verify_numbers.sh` `mid(None)` caveat is stale (fixed `1ce7678`: `mid()` guards non-dicts) | Caveat rewritten — missing modes now render as missing rows; the python≥3.12 self-resolve chain (`4a9f4f7`) replaces "run it with .venv312". | demo-day.md L822–829 |

## Deliberately NOT changed

- **Quoted field numbers** (stations, community totals, build_sha
  `4eb9e1e8`, fire counts): all timestamped reads inside a doc that says
  "they drift with the field; re-check on the day" — the T-45
  `verify_numbers.sh` FLAGS pass is the reconciliation mechanism
  (audit Missing #12, P2). Re-stamping them would just re-stale.
- **`docs/plan/go-nogo.md`** — its `$NLB` uses are defined inline by its
  own `NLB = http://…` line (L8); outside this lane's named files.
  Flagging for the owner: it still names a much older APK
  (`e849bf6f`) with its own caveat.
- **`docs/19-submission-checklist.md`** — no APK/`$NLB` references;
  untouched.

## Verification

Every new command was checked against the thing it calls:
- `describe-load-balancers --names alive108` — matches deploy.sh
  `NLB_NAME` default (L40); DNS fallback matches `warm_task.py` BASE
  (L33) + the apk-v10 baked endpoint.
- `aws sts get-caller-identity` / `ap-south-1` — the same first call
  deploy.sh makes (L61).
- `/community` totals fields — `server/community.py` `totals()`:
  `obs_total`, `obs_today`, `contributors`, `latest_obs_age_min` (L935+).
- Admin live feed — `/admin/api` → `community.live_reports()` (main.py
  L1577+); `/admin/api/*` Bearer-gated by `ALIVE_ADMIN_TOKEN` (main.py
  L1561); `/admin` HTML public (L1620).
- Outbox copy — `Mobile/src/i18n/strings.ts` `receipt_queued` /
  `offlinePending`; flush path `offline/queue.ts` `enqueueTripDonation` →
  `POST /v2/trip`, `wireAutoFlush` on net-up.
- Localhost backup — repo-root `docker-compose.yml` maps host :8080 →
  container :8080 (`server/Dockerfile` build).
- `public-repo.sh` — `git commit-tree` at L155; ls-remote preflight at
  L121; never touches worktree (header comment + implementation).
- `describe-tasks --tasks arn1 arn2` — CLI accepts space-separated ARNs;
  unquoted `$(list-tasks … 'taskArns[]')` is the correct expansion.

## Residual risk

The doc now *describes* the newest-HEAD APK but that binary is owned by
the build lane in flight — if it lands as a differently-named report,
the `apk-v10-report.md` pointer in both docs should be re-pointed (the
"or the newest `apk-*-report.md`" clause already covers the reader).
