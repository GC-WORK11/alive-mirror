# Submission checklist — the Oct-8 sequence, in order

*Cross-checked against `docs/plan/go-nogo.md`, `docs/19-submission-checklist.md`,
`docs/20-hackathon-playbook.md` and live state on 2026-10-05. Order matters —
items are sequenced so nothing disqualifying or irreversible happens early.*

## Status — as of Oct 6 late (prod verified `ce01ec5c`)

**Done since this checklist was written:**
- DPCC ingest live on prod — `/health` reads `sources.stations.count=54`,
  `source:"waqi+dpcc"`, both feeds `ok` (24 WAQI + 30 DPCC).
- Independent-holdout evidence committed — the differentiator:
  `docs/lanes/accuracy-holdout-report.md` + `ingest-dpcc-report.md` +
  `field-watch-2-report.md`; now front and center in `writeup.md` and
  `repo-readme.md`.
- Builder Center long-form draft committed at
  `docs/builder-center/article-draft.md` (title options + 120-word abstract
  inside).
- App demo beats re-taped on the final APK — 7/7 PASS, 0 crashes
  (`docs/lanes/video-v8-report.md`); final APK is `alive108-c3bb731.apk`
  (built at `3d3df49` — *includes* the landmark-purge `2c4cab4`, verified
  ancestor).

**Still owner-action (nothing here can be done for you):**
- WeMakeDevs registration + Builder Center profile + **SheerID** verification
- Claim the **$200 AWS credits** code · set the **$5 Budgets alarm**
- Film the ~10 s **AWS console** beat (`docs/plan/aws-console-shotlist.md`) +
  upload the video to YouTube
- The **Oct-8 public-repo squash** (§1) — then APK install on the demo phone
- The demo-morning sequence (§3): Spot→on-demand flip, warm task, health reads

## 0 · Before Oct 8 (done any time)

- [ ] Register: wemakedevs.org/aws/env → join "Environmental Hacks" →
      **Track 01 (Air)**. Requires BOTH a WeMakeDevs account and an AWS
      Builder Center profile.
- [ ] **SheerID student verification** on the Builder Center profile —
      "checked before the hackathon you enter"; pending ≠ blocked from
      submitting but gates fast-track + rewards. Don't leave it to the day.
- [ ] Claim the **$200 AWS credits** code → Billing → Credits.
- [ ] **$5 Budgets alarm** → Billing → Budgets → your email (stack is
      ~$46/mo worst case; alarm fires before any surprise).
- [ ] Record the ≤3:00 video per `docs/submission/video-shotlist.md`
      (dosimeter arc — your-day card → dose gap → lung reach → engine
      room → console; `docs/plan/demo-script.md` is the older route-first
      stage script, still valid as a stage runbook but its numbers sheet
      predates the pivot). **App beats done** — 7/7 PASS on
      `alive108-c3bb731.apk` (video-v8). Remaining: the **AWS-console
      beat** — `docs/plan/aws-console-shotlist.md` is the owner's
      self-filmed 25 s window; grab the separate ~10 s ECS-console
      screen-record too (needed footage per rules).
- [ ] Upload video to YouTube **unlisted or public — verify it opens
      signed-out** (incognito). This is the only demo judges see.

## 1 · Oct 8, FIRST thing — the public repo (disqualifier if missed)

*Rule: "a repository whose history does not match the event dates
disqualifies the whole team." Private history predates Oct 8 → squash to
one baseline commit, run-date stamped, on a NEW public repo.*

- [ ] Land this submission package on `origin/main` first (one merge of
      `base/v2` → main): `docs/submission/*`, and make
      `docs/submission/repo-readme.md` the repo's `README.md` — so the
      baseline the judges clone already sells itself. (Fallback: commit the
      README to the public repo right after baseline — still in-window, but
      baseline-first is cleaner.)
- [ ] Create an **EMPTY public GitHub repo** (no README, no license —
      anything in it adds a second root commit).
- [ ] From a clean clone on `main` (`git status --porcelain` empty —
      the orphan checkout + `git add -A` sweeps whatever is in the tree;
      also check `git branch --list public-baseline` is empty):
      `./scripts/public-repo.sh https://github.com/<owner>/<new-repo>.git`
      → orphan `public-baseline` → one commit "baseline: ALive-108…" →
      `push … public-baseline:main`. Script pushes `origin/main` HEAD —
      verified the tree includes base/v2 (main is 1 merge ahead).
- [ ] Verify: `gh repo view <new> --json pushedAt` — one commit, dated
      Oct 8; repo is PUBLIC; README renders the live URL.
- [ ] Keep hacking normally on the public repo after — every later commit
      is in-window by date.

## 2 · Oct 8 — the submission itself (3 things, one form)

- [ ] **Repo URL** → the new public repo.
- [ ] **YouTube link** → the ≤3:00 upload (confirm signed-out again —
      this is what they open).
- [ ] **Short writeup** → paste from `docs/submission/writeup.md`
      (problem → build → where AWS fits) + the AI-tools line from
      `docs/submission/ai-disclosure.md` (Devin disclosure is a stated
      requirement).
- [ ] Separately: publish the long-form on **AWS Builder Center** —
      draft ready at `docs/builder-center/article-draft.md` (pick a title,
      paste the body; it's a second judged prize — AirPods ×5).
      Publish path (verified): needs a free **AWS Builder ID** (not the
      AWS account) + Builder Center profile → top-nav **"+" → Create
      article** → paste markdown (tables render natively) → Preview →
      Publish → automated moderation scan → live. Gotchas: no API (hand
      paste), every link is checked at publish, cover image 1200×675.

## 3 · Demo/judging morning — live stack (from go-nogo, gotchas baked in)

- [ ] T-60: **Spot → on-demand flip** (owner's runbook step — do NOT
      pre-run): `aws ecs update-service … FARGATE,weight=1,base=1
      --force-new-deployment` (full cmd + rollback in
      `docs/demo-day.md` §FARGATE_SPOT). ~₹8/hr; flip back after judging.
      The flip REPLACES the task → re-warm after.
- [ ] T-45: `curl $NLB/health` → `stale:false`, `engine:alive_core`,
      edges 1,070,459, `build_sha` = the build you rehearsed on
      (**current truth: `ce01ec5c` — the DPCC-ingest deploy; the
      `build_sha`-vs-image-tag wart from NUMBERS.md §2 can still lag a
      deploy — the ECR image tag is the truth**, re-verify both on the
      morning).
- [ ] T-45: `wind.known` can flip `false` for a refresh or two
      (upstream Open-Meteo reachability — transient, self-heals; if it's
      still false at T-30, re-probe once, don't panic).
- [ ] T-45: stations `ok` — expect **54** (`waqi` + `dpcc` both `ok`,
      `source:"waqi+dpcc"`); `field.age_s` < 900.
- [ ] T-40: `python3 tools/warm_task.py` → exit 0 ("WARM: priced engine
      serving after Ns"); last line `/tiles/health ok — 22.7 MB`.
- [ ] T-30: demo-OD plan armed (go-nogo #6) — `options ≥15` incl.
      `metro+walk`/`steps_source:"gtfs"`, warm `took_ms` < 2000. Cold
      far-ODs honestly time out at 20 s — rehearse on the SAME OD.
- [ ] T-30: **AWS console pre-signed + pinned** (sign in BEFORE the
      venue; never log in live). CLI understudy armed — prints
      `alive108:NNN · FARGATE`. The video must show the console.
- [ ] T-30: admin token check (go-nogo #8) — `/admin/api` 200 with
      Bearer; public `/admin` renders regardless.
- [ ] T-30: `warm_task.py` now covers the dosimeter beats it used to
      miss (`/v2/day`, `/v2/reach walk`, `/v2/outlook`, `/grid?h=12`,
      `/community`) — still spot-check
      `curl "$NLB/v2/day?lat=28.6315&lon=77.2167"` (heavy/cleanest
      windows + decisions[]) and
      `curl "$NLB/v2/reach?lat=28.6315&lon=77.2167&mode=walk&budget_ug=25"`
      (settled edges + `took_ms` < 2000; a cold field returns the honest
      `engine_unavailable` — warm_task first). Or run the whole sweep
      read-only: `./scripts/smoke_live.sh`.
- [ ] T-30: **archive tile on `/admin`** — the field has recorded Delhi
      hourly since Oct 5 (`archive.status()` → `snapshots_total`,
      `since_ist`; `GET /v2/archive` replays the day hour-by-hour). A
      `gap` hour is honest, not a bug — it's what the recorder wrote
      while a task was down. Whole-ledger sweep: `./scripts/verify_numbers.sh`.
- [ ] T-20: APK on the demo phone — **final build is
      `alive108-c3bb731.apk`** (built at `3d3df49`, launcher label
      `ALive·108`; *includes* the landmark-purge `2c4cab4` — verified
      ancestor, so the old `6ca0ef7` gazetteer caveat is resolved).
      Check bundle strings: NLB host present, no `10.0.2.2`.
- [ ] T-20: backup videos on the playing device + play once with
      **Wi-Fi OFF** (airplane-mode proof).
- [ ] T-15: `curl $NLB/health` → 200 on hall Wi-Fi AND phone hotspot.
      **NLB is HTTP :80 only** — captive-portal Wi-Fi kills it silently;
      hotspot is the fallback. DNS resolves to 65.2.28.40.
- [ ] Stage: re-read `/health` + `/aqi` at T-10 — every verbatim number
      phrased in ranges ("about", "over"); adjust, never quote stale.

## NO-GO conditions (cut, don't fake)

`/health` stale >900 s after two refreshes · warm_task exit 1 · demo-OD
`options:[]` twice (retry once → backup video) · public repo not pushed
(whole-team DQ) · APK crashes twice on open (demo the web surfaces —
same numbers).

## Files in this package

| file | job |
|---|---|
| `writeup.md` | Builder Center written submission + form paste |
| `ai-disclosure.md` | required AI-tools listing |
| `repo-readme.md` | becomes `README.md` in the public repo |
| `video-shotlist.md` | ≤3:00 audit + trim order + drift flags |
| `submission-checklist.md` | this file |
| `../builder-center/article-draft.md` | Builder Center long-form post (AirPods ×5) — title options + 120-word abstract inside |
