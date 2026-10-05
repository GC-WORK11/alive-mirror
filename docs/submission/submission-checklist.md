# Submission checklist — the Oct-8 sequence, in order

*Cross-checked against `docs/plan/go-nogo.md`, `docs/19-submission-checklist.md`,
`docs/20-hackathon-playbook.md` and live state on 2026-10-05. Order matters —
items are sequenced so nothing disqualifying or irreversible happens early.*

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
      predates the pivot). AWS-console beat inside —
      `docs/plan/aws-console-shotlist.md` is the owner's self-filmed 25 s
      window. Grab the separate ~10 s ECS-console screen-record too
      (needed footage per rules).
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
- [ ] Separately: publish the long-form on **AWS Builder Center**
      (same content, it's a second judged prize — AirPods ×5).

## 3 · Demo/judging morning — live stack (from go-nogo, gotchas baked in)

- [ ] T-60: **Spot → on-demand flip** (owner's runbook step — do NOT
      pre-run): `aws ecs update-service … FARGATE,weight=1,base=1
      --force-new-deployment` (full cmd + rollback in
      `docs/demo-day.md` §FARGATE_SPOT). ~₹8/hr; flip back after judging.
      The flip REPLACES the task → re-warm after.
- [ ] T-45: `curl $NLB/health` → `stale:false`, `engine:alive_core`,
      edges 1,070,459, `build_sha` = the build you rehearsed on
      (**drifted again: task-def now `alive108:147`, image
      `alive108-api:1e93b9f2` — but `/health` still stamps `c7df5db5`;
      the BUILD_SHA env lag is a known wart — the ECR/task image tag is
      the truth** — re-verify both on the morning).
- [ ] T-45: `wind.known` can flip `false` for a refresh or two
      (upstream Open-Meteo reachability — transient, self-heals; if it's
      still false at T-30, re-probe once, don't panic).
- [ ] T-45: WAQI `ok` + ≥20 stations; `field.age_s` < 900.
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
- [ ] T-30: warm the two new beats `warm_task.py` doesn't cover —
      `curl "$NLB/v2/day?lat=28.6315&lon=77.2167"` (expect heavy/cleanest
      windows + decisions[]) and
      `curl "$NLB/v2/reach?lat=28.6315&lon=77.2167&mode=walk&budget_ug=25"`
      (expect settled edges + `took_ms` < 2000; a cold field returns the
      honest `engine_unavailable` — warm_task first).
- [ ] T-20: APK on the demo phone — **caveat:** the sideloaded build is
      `6ca0ef7`. It post-dates the crash fix but predates `2c4cab4` (23
      fabricated landmark geocodes purged — the purge touched the
      bundled `delhi-gazetteer.json`, so the on-device gazetteer still
      carries the phantoms). **If the demo shows on-device flagship
      search, rebuild on HEAD; if it's map/plan/ledger only, `6ca0ef7`
      is honest.** Check bundle strings: NLB host present, no `10.0.2.2`.
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
