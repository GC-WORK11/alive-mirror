# Lane report — runbook-sync: demo-morning.md final refresh

**Date:** 2026-10-07 ~14:25 UTC · **Lane:** docs sync (verify-then-edit; prod
GETs only) · **Base:** `base/v2` HEAD `ef5d95f` at pull.

## What changed in `docs/plan/demo-morning.md`

| Stale | Now says | Verified how |
|---|---|---|
| header prod stamp `c86074ff` | `7c68c8bc` (deploy-5 roll 2) + sources list adds deploy5/privacy-f1-fix/offline-pack-fix/community-sanity/ios-release-residual/judge-answers-v6 | `curl $NLB/health` → `build_sha:7c68c8bc`, `field_stale:false`, `age_s:950`, `engine:alive_core` — live at write time |
| GO/NO-GO check 1 had no sha expectation | `build_sha` = deployed tag, "`7c68c8bc` family — re-check with this same curl; a flip = task restart or freeze-break, see T-5" | same live `/health` read |
| GO/NO-GO check 4 pinned freeze APK `c3f7e9e` | "install the latest `alive108-<sha>.apk` from the final freeze-cut — check the recut report for the sha" (newest `docs/lanes/apk-*-report.md`) + `shasum -a 256` verify; `c3f7e9e` demoted to OLD freeze, `c3bb731`/`0b11123` still never | `git show`: `c3f7e9e` (03:16 PDT) predates offline fix `54a296e` (06:31 PDT) → it is r1-era, warms zero tiles. Recut report not yet on disk — lane in flight, so the doc points at the report, not a sha. Install+open-once pre-warm step untouched (gauntlet paragraph intact) |
| T-45 pan note claimed "the offline tile pack downloads zero tiles" unconditionally | honest split: fix is live on prod but pre-recut installs still carry r1 code → panned viewport (ambient cache) is what survives a dead hall; re-cut APK self-warms all 744 NCR tiles | `/v2-light.json` → **200, 94,254 B** live on prod; `offline-pack-fix-report.md` (region_tiles=744 on iOS sim) + residuals §"a new APK cut is required" |
| Wi-Fi+hotspot-both-dead fallback row implied the r2 pack might already be on the phone | row now states plainly: fix live on prod but only reaches phones via the re-cut → **this morning's install renders only where the T-45 pan cached it** (ambient cache is the plan, not a fallback) | same evidence |
| iOS standing rule: "Release rate unmeasured, report not landed" | Release measured **0/60 cold launches clean**; ~47% dev-debug crash = React-dev-inspector-only race → post-demo item; Android stays demo target | `ios-release-residual-report.md` (landed): Release 0/60 vs Debug 14/30, Fisher p≈8.4e-6; device build unmeasured caveat kept |
| — | new pinned ammo: privacy spine PASS + F1 day-row gate closed & live (55 cells → 12 publishable); community ledger proven real (44/24/1,278.9 exact to DDB+S3, zero test devices/seeds); `/v2/skill` ~0.7 s | `privacy-spine-report.md` + `privacy-f1-fix-report.md` + `deploy5-report.md` (new `/admin/api` contract live-verified); `community-sanity-report.md`; live `/community` → `{obs_total:44, contributors:24, avoided_ug_all:1278.9}` matches; `/v2/skill` → 200 in 0.53 s this box |

## Unchanged on purpose

- `python3 tools/warm_task.py` path — file exists at `tools/warm_task.py`, correct.
- Deploy-freeze / probe / route_id-per-task rules, T-0 beat order, fallback
  mechanics — still accurate as written.
- `c3f7e9e` kept once as historical context (the OLD freeze) — never as the
  install target.

## Note for the owner

The runbook's APK line resolves to a sha only when the apk-recut lane lands
its report — the doc already says where to read it. Everything else was
re-verified live on prod `7c68c8bc` while editing.
