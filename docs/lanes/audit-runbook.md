# Lane report — audit-runbook (hostile rehearsal of `docs/demo-day.md`)

**Lane:** audit-only. No product-code edits; this file is the only write.
**HEAD at audit:** `16d7202` (base/v2, pulled 2026-10-07 ~02:30 UTC).
**Live prod probed (GETs only):** `/health` `aee635eb`, `engine:"alive_core"`,
`field_stale:false`, stations 52 (`waqi`+`dpcc` both ok), transit
`real_feeds bus+metro true`, routing loaded 1,070,459 edges / 903,058 priced,
`/tiles/health` ok 22.7 MB, `/v2/why` 200, `/reports` 200 (empty
FeatureCollection — see T-25/T-15 findings), `/community` 200.

Verdict up front: the AWS mechanics are sound — the T-60 flip command is
syntactically and semantically correct against `deploy.sh`'s real
identifiers. The demo-killing risks are all in the *surrounding* steps:
the named demo APK is stale by ~30 Mobile commits (two docs name two
different binaries), `$NLB` is never defined, two checklist items point
at the wrong endpoint (`/reports`), and the offline-pass step contains a
contradiction. Details below.

## Step table

| runbook step | artifact exists? | would it work? | est. cost | risk |
|---|---|---|---|---|
| `./scripts/public-repo.sh <url>` | ✅ `scripts/public-repo.sh` (commit-tree, never touches worktree, blob+secrets guards) | ⚠️ yes — but only if the GitHub repo **already exists, empty** and push auth is set; script does `git ls-remote` and dies if unreachable. Demo-day's own block lists neither prereq (they live only in `docs/submission/submission-checklist.md` §1). | ~1–2 min | **P0 if missed entirely** (whole-team DQ per the cited rule); P1 prereq gap in this doc |
| T-60 pre-check `describe-services` | ✅ | ✅ correct (`--services` plural, cluster/service `alive108` match `deploy.sh` `ECS_CLUSTER`/`ECS_SERVICE` defaults) | seconds | — |
| T-60 **flip** `update-service --capacity-provider-strategy "capacityProvider=FARGATE,weight=1,base=1" --force-new-deployment` | ✅ | ✅ verified: FARGATE/FARGATE_SPOT are the AWS built-ins; `base=1 ≤ desired 1`; service already carries a capacity-provider strategy (handoff cont.: FARGATE_SPOT confirmed live), so no launchType conflict; strategy replaces wholesale as intended. Same task-def → same image, warm task replaces it. | rollout ~4–8 min (task boot ~1–2 + NLB TG health ~2–3 + stable gate) | — command itself is correct |
| `aws ecs wait services-stable` | ✅ | ✅ real waiter; note max budget ~10 min (40×15 s) — a slow rollout exits the waiter with an error, re-run it | up to 10 min | P2 |
| post-verify `describe-services` + `describe-tasks` | ✅ | ⚠️ `list-tasks … --query 'taskArns[0]'` checks only ONE ARN — mid-rollout (desired 1 → 2 tasks) it can pick the **old SPOT task** and read back `FARGATE_SPOT`, a false alarm at the worst moment. Post-`services-stable` it's fine. Iterate all ARNs to be safe. | seconds | P2 |
| `python3 tools/warm_task.py` (post-flip + T-40) | ✅ `tools/warm_task.py` (prompt's `scripts/` guess was a probe — runbook cites the right path) | ✅ GETs + the sanctioned `POST /v2/plan`; walks /health, /aqi, /grid, 12 real NCR ODs until `steps_source:"endpoints"` rows appear, /reports, /v2/city, /grid?h=12, /v2/day, /v2/reach ×3 mode×budget combos, /v2/outlook, /v2/why, /v2/skill, /v2/archive, /community, /tiles/health. Exit 0 ⇔ priced engine serving — the gate that matters. Transit rows counted + loud NOTE if zero. | ~60–100 s cold task; ~1–2 min | P2 — does NOT hit `/search` (index is boot-warmed in `_lifespan._warm_static`, fine) and does NOT hit the demo OD IG→HCC (see Missing #7) |
| T-45 `curl $NLB/health` | ✅ `/health` live-verified (build_sha, field_stale, engine all present) | ❌ **as pasted it fails** — `$NLB` is never `export`ed in demo-day.md, submission-checklist.md, or go-nogo.md. Operator must know to `export NLB=http://alive108-…elb…` | seconds | P1 |
| T-45 `bash scripts/verify_numbers.sh` | ✅ executable, `BASE` defaults to the real NLB | ✅ GETs + one allowed POST; python≥3.12 self-resolves (`.venv312`→3.14→3.13→3.12→python3 fallback chain, `4a9f4f7`); exit is always 0 by design — "read the FLAGS block" is the contract. **Stale caveat in runbook**: the `mid(None)` crash is fixed (`mid()` guards non-dict + `if ms else None`). `--max-time 90` on a cold task can still print MISSING for reach — keep the flip-block warm before T-45 (already the written order). | ~2–5 min | P2 (stale caveat) |
| T-30 phone on venue network / hotspot | ✅ | ✅ matches verified APK behavior (NLB :80 only, captive portals break it) | 1 min | — |
| T-25 "open admin page (`/reports` + aggregates) — confirm light theme + CPCB colors" | ⚠️ `/reports` exists but is **not the admin page** | ❌ wrong surface: `GET /reports` = `community.reports_geojson()` — raw GeoJSON, currently `{"type":"FeatureCollection","features":[]}` live (honest-empty; no live corridors). No theme/colors exist there to check. The checkable surfaces are `/admin` (public board → operator sign-in) and `/community` HTML. | seconds | P1 |
| T-15 offline pass → "donate → watch the aggregate land in the next `/reports` tick" | — | ❌ **doubly broken as written**: (a) an *offline* pass queues the donation ("saved — will send when back online") — nothing can land until reconnect; (b) `/reports` only renders **k≥3 corridors** — one device donating can never make a corridor appear. The real observable is the `/admin` **live feed** (post sign-in; community.py `live_reports()`) or `/community` totals incrementing (`obs_total` 40 live now). | 5–8 min | P1 |
| T-10 kill apps + auto-lock off | ✅ | ✅ | 1–2 min | — but no battery step (Missing #5) |
| T-5 re-curl `/health` | ✅ | ✅ (same `$NLB` wart) | seconds | — |
| Task-size bump block (optional) | ✅ | ⚠️ works, but: (1) its `update-service` **already carries the FARGATE strategy** — running it after the flip block means **two full rollouts** (~10–16 min) inside the window; run bump *instead of* flip or fold both into one call. (2) the heredoc drops `volumes`/`placementConstraints`/`runtimePlatform` — benign today (current def sets none) but silently drops them if a future def adds them. (3) registers a permanent new task-def rev — rollback line is present and correct. | rollout ~4–8 min + warm ~1–2 | P1 sequencing |
| Rollback to `FARGATE_SPOT` | ✅ | ✅ correct, symmetric | ~4–8 min | — |
| Backups: recorded ride video / iOS-sim capture / localhost path | ⚠️ `docs/video/cut1.mp4`+`cut2.mp4` exist in-repo (3.3/4.3 MB); localhost path needs `docker-compose.yml` (exists) or the `.venv312` uvicorn line in §iOS | ⚠️ the checklist never says *which file* is the backup or to put it on the phone — that coverage lives only in submission-checklist T-20 (on-device + airplane-mode play) | — | P1 (asset localization), P1 for laptop-localhost prep (Missing #8) |
| Demo APK: `alive108-0b11123.apk` ("the HEAD binary") | ⚠️ not in repo (attachment-hosted); report `docs/lanes/apk-final-report.md` exists | ❌ **contradicts** submission-checklist T-20 which names `alive108-c3bb731.apk` "the final build" — and **both are stale**: c3bb731 built at `3d3df49` ~Oct 6 08:18 UTC; `0b11123` tree ~Oct 5–6. ~30 Mobile commits landed after, incl. **demo-path fixes**: `344b4a9` ("Where to?" pill occluded under open home sheet — the flow's FIRST tap) and `c84b5c2` (phantom re-plan after receipt-Done — the flow's LAST beat), plus design-v4 `8c7ad97`, i18n leaks `832e7fa`, outbox `c674705`, alerts `4d20990`. A judge on either named binary sees pre-v4 UI and can hit the eaten-tap bug on camera. | — | **P0 — decide: rebuild APK at HEAD and re-verify, or consciously bless the stale binary and script around its two known on-stage bugs** |

## Failure-mode coverage

Covered well: feed outage → honest degrade (verified live: `sources.*` names
feeds, `field_stale` boolean, `/v2/plan` `degraded[]` arm names); route-id
invalidation across task swap (documented + observed); Spot reclaim (2-min
warning + cold-boot cost stated); deploy inside the window ("never" —
drift note); transit cold-start (bake_gtfs, verified live); BUILD_SHA lag
wart (documented, "say the ECR tag"); empty `decisions`/windows (plain-words
fallback verified in doc); corridor sparsity (honest-empty documented).

Partially covered / gaps:

- **Failed flip leaves the old SPOT task serving** (minHealthyPercent keeps
  it until the new task is healthy) — worth saying explicitly: a failed
  rollout is degraded-safety, not outage. Not stated. P2.
- **No target-group health verify in the flip block** — `services-stable`
  covers the ECS rollout, not NLB target health; the T-45 `curl $NLB/health`
  catches it transitively (~15 min later). Add `describe-target-health` if
  you want the earlier signal. P2.
- **ECR pull stall on the new task** — same protection as above (old task
  keeps serving); waiter timeout is the symptom. P2.
- **`wind.known:false` transient** — covered in submission-checklist T-45,
  absent here. P2 cross-link.
- **WAQI/DPCC mid-demo outage** — honest-degrade verified live today
  (station count drifts 13–54; sources table + `field_stale` say so; UI
  last-good + staleness chip per the connectivity table). Covered.
- **Venue outside NCR** — the demo flow is search-driven (origin typed
  manually), so planning works; but the ambient hero/`/aqi` read the
  phone's own cell — if the venue's GPS is outside the service area the
  hero honestly reports out-of-area. If the venue isn't in NCR, set a
  Delhi mock location on the demo phone beforehand. Conditional P1 — owner
  knows the venue.
- **Laptop localhost backup** — `docker-compose.yml` + the `.venv312`
  uvicorn command exist, but no step says "boot the local server once
  before leaving" — an untested backup is no backup (fresh box needs venv
  + eigen + `core/build_ext.sh` first). P1 if the localhost path is a real
  backup rather than a nicety.
- **Admin token on stage** — `/admin` is a public board but the internals
  need `Authorization: Bearer` (verified: `/admin/api/*` 401 without);
  token lives in Secrets Manager `alive108/admin-token` — no step says to
  have it physically at hand (phone note/paper). Submission-checklist T-30
  covers a token *probe*, not possession. P1.
- **Hall-wifi + app POSTs** — plan/donate POSTs over captive or
  TLS-MITM'd venue wifi fail the same as GETs; the connectivity table
  covers the app's side; hotspot fallback already the stated plan.
- **iOS SIGSEGV** — section is accurate and current (Lane-B iOS report at
  HEAD: 4× on first sheet mount, cold launches clean); Android is the
  release target and has never crashed in E2E — the "prefer Android /
  recorded take" guidance stands.

## Timeline arithmetic (T-60 → T-0 = 60 min)

| block | worst-case cost |
|---|---|
| public-repo (should be Oct 8, not demo morning — correctly placed FIRST) | ~2 min |
| T-60 flip → stable → post-verify → warm | ~8–10 min |
| T-45 health + verify_numbers | ~5 min |
| T-40 warm re-run | ~2 min |
| T-30/T-25 network + admin open | ~3 min |
| T-15 pass | ~8 min |
| T-10/T-5 | ~3 min |
| **total scripted** | **~31–35 min → ~25 min slack** |

Enough slack for the flip path — *unless* the optional bump is also run as
written (adds a second rollout+warm: still inside, ~10 min more, but
wasteful) or the rollout fails (waiter error → decide: re-run, accept SPOT,
or abort — no scripted decision point; the NO-GO list lives only in
submission-checklist §NO-GO). Unestimated cost flagged: NLB target-health
(not waited on; T-45 curl is the backstop).

## Missing steps (consolidated)

1. **`export NLB=http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com`**
   before the checklist — every `curl $NLB/…` in three docs fails as
   pasted. P1.
2. **`aws sts get-caller-identity` + aws-cli presence check before T-60** —
   the flip block assumes creds silently; a dead cred means the flip
   doesn't happen and SPOT risk stands. Add as a T-90/T-60 line. P1.
3. **Public-repo prereqs in this doc** — create the EMPTY GitHub repo
   (no README/license) + push auth before running the script. Only
   submission-checklist §1 has them. Also: submission-checklist's
   description of the script's *mechanics* (orphan checkout + `git add -A`,
   "pushes origin/main HEAD") is stale — the current script is
   `commit-tree` of the tip-most of {base/v2, main}, never touches the
   worktree. P1/P2.
4. **Reconcile the three checklists** — demo-day.md, submission-checklist
   §3, and go-nogo.md overlap but diverge: different APK names
   (0b11123 vs c3bb731 vs HEAD-stale), T-25 `/reports` vs admin-token
   check, both-networks health probe, `wind.known` note, NO-GO list.
   None cross-links the others. P1.
5. **Phone battery** — charge to full + power bank + cable on the table.
   Absent everywhere. P1 (classic stage-killer).
6. **Admin token physically at hand** — see failure modes. P1.
7. **Warm/arm the actual demo OD (India Gate → Huda City Centre)** —
   `warm_task.py`'s 12 ODs don't include it; the staged OD answers ~50 ms
   only if the pre-doors phone pass actually completes the compare load
   (stage plan covers it — make the dependency explicit, or add the OD to
   `WARM_ODS`). Submission-checklist T-30 arms it separately. P2.
8. **Boot the localhost backup once before leaving** (compose up or the
   `.venv312` uvicorn line — needs eigen + `core/build_ext.sh` on a fresh
   box). P1 if it's a real backup.
9. **Post-flip verify should iterate ALL task ARNs**, not `taskArns[0]` —
   mid-rollout the old SPOT task is still listed. P2.
10. **Backup-video localization** — name the files
    (`docs/video/cut1.mp4`, `cut2.mp4`), copy to the demo phone, airplane-
    mode play-test (submission-checklist T-20 has the gesture). P1.
11. **Decide-on-cut criteria in this doc** — NO-GO list exists only in
    submission-checklist §NO-GO. P2.
12. **Doc self-drift**: verify_numbers `mid(None)` caveat is fixed
    (`4a9f4f7`); community totals in the body are stale (live: 40 obs /
    22 contributors / 1,028.5 µg vs quoted 22/14/725.9 — drift is
    expected, T-45 pass handles it); `/health` `build_sha` is now
    `aee635eb` (doc's `4eb9e1e8`). P2.

## Repro / evidence

- Live GETs (2026-10-07 ~02:33 UTC): `/health` (aee635eb, 52 stations,
  engine alive_core, transit real_feeds, wind known), `/tiles/health`
  (22.7 MB, 1,644 entries, z0–14), `/v2/why` (200, `point_in_area:true`,
  line = stagnation — fire story already flipped back, as documented),
  `/reports` (200, `features:[]`), `/community` (obs_total 40,
  contributors 22, avoided_ug_all 1028.5, top_corridors present),
  `/v2/city` (200).
- Static audit: `tools/warm_task.py` (full read), `scripts/deploy.sh`
  (cluster/service/family = `alive108`, port 8080, TG `alive108-tg`,
  health-check `/health` 30 s, grace 150 s), `scripts/verify_numbers.sh`
  (py3.12 fallback chain, GETs + one POST, exit-0 reporting contract),
  `scripts/public-repo.sh` (commit-tree, guards), `server/Dockerfile`
  (PORT=8080, `RUN python tools/bake_gtfs.py` — file exists at
  `server/tools/bake_gtfs.py`), `server/main.py` `/_lifespan` (boot warms:
  fires, field, forecast, transit, community, static/gazetteer, engine,
  grid), `community.py` (`reports_geojson` = k≥3 corridors only;
  `live_reports` feeds the admin live feed).
- Git facts: `c3bb731` APK built at `3d3df49` (Oct 6 ~08:18 UTC);
  `344b4a9`/`c84b5c2`/`bc8f82c` all Oct 6 ~17:30–18:35 UTC; HEAD `16d7202`
  Oct 6 19:25 UTC. ~30 `Mobile/` commits post-date the newest named APK.
- Cross-docs: `docs/submission/submission-checklist.md` (its §3 is the
  richer demo-morning sequence — covers token probe, both-networks check,
  airplane-mode video play, NO-GOs — but names the other APK and still
  uses undefined `$NLB`), `docs/plan/go-nogo.md`, `docs/plan/NUMBERS.md`.

## Recommendation (one line)

Flip mechanics are safe to run verbatim at T-60; **before Oct 8, fix the
P0 APK question (rebuild at HEAD or bless-with-caveats), add
`export NLB` + the AWS creds preflight, and correct the T-15/T-25
`/reports` misdirect to the admin live feed / `/community` totals.**
