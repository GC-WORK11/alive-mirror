# Old-org import — complete handoff record (Oct 7, ~14:45 IST)

The second Devin account (org `org-5f3b8c91f908494a9c5d3ddcef1c40c2`, lead session
`devin-93b8804d89e046f58cd1f1c853ab99cf`) is retired for this project. Everything it ran
is imported here. **Raw transcripts: `/Users/devin/oldorg/import/`** (260 session JSONLs +
`sessions_index.json` + lead's 332-message history `lead-93b8804d89e046f58cd1f1c853ab99cf.jsonl`).
This doc is the condensed map; the repo's own `docs/lanes/*-report.md` files are the
verified evidence (every lane below pushed one — verify before believing, per evidence law).

## What the import confirmed

- **Every one of its ~50 ALive lanes completed before sleeping.** Nothing was abandoned
  mid-flight. The board it leaves behind is fully delivered work.
- **All durable state is in this repo already** — lane reports, handoff.md cont.* log,
  the code itself. The import adds the *why* and the watch-list, not new code.
- **Ops moved here**: AWS creds verified working on this org (iam user `alive108`,
  AdministratorAccess, ap-south-1). `scripts/deploy.sh` is in-repo and self-contained.
  Cloudflare token banked (zero zones — no domain yet).

## Their key deliveries (all on base/v2, verified in repo)

| Lane | Result | Evidence |
|---|---|---|
| wipe-verify | Delete-my-data proven on real device FS; 1 hole fixed | `docs/lanes/wipe-verify-report.md` |
| repo-hygiene | 1,219 commits scanned — secrets audit CLEAN, nothing to rotate | `docs/lanes/repo-hygiene-report.md` |
| notify-v2 | cause-aware alerts: trend/grap/outlook drivers, dedupe ladders | commits `5421269` |
| events-notify | pollution events → local alerts, fired on iOS sim vs live AWS | `4d20990`+`f72cef3` |
| pocket-engine | "is a watch always on?" — NO, and it should stay that way (battery/policy truth table) | `docs/lanes/pocket-engine-report.md` |
| route-segments | segments contract verified sound + `/v2/reroute` gap fixed | `58632f3` |
| ios-cold-drive | SIGSEGV measured 40%→12.5% on pre-rootfix build | `docs/lanes/search-fix-verify-report.md` |
| holdout-reverify | independent-station MAE: former-GAP 22.8→10.5, all-30 27.1→6.2 | `39a161c` |
| field-watch | DPCC ingest live (`ALIVE_DPCC_INGEST=1`), 30 govt instruments blended, field corrected honestly | `ce01ec5c` deploy |
| forecast-skill | fitted persistence blend: pooled MAE 39.21→11.21 on 7,381 archive pairs | `f4139b2` |
| accuracy-holdout | flag-gated DPCC adapter shipped (default off) | `47e9601` |
| codebase-hygiene | dead-code audit + 7-beat APK retape 0 crashes | `docs/lanes/video-v8-report.md` |
| demo-video | cut7.mp4 2:38 all-web beats re-taped on prod aee635eb | attachment `59dd9de3` |
| android-drive | release-journey drive, every feature | lane report |
| admin-as-operator | found HIGH: `/v2/trip` missing validation caps → fixed | REPORT.md in lane |

## Ops knowledge absorbed (was their institutional memory)

- **Deploy**: `scripts/deploy.sh` — image→ECR→ECS Fargate→NLB re-register→health verify.
  `deploy.sh rollback <sha>` redeploys an existing tag. Tags = 8-char sha + `:latest`.
  Known outage pattern baked in: redeploys orphan the old task IP — script re-registers.
- **Alarms (all honest now)**: `alive108-field-age` (ns `ALive-108` — was `ALive108`,
  saw nothing for a day), `alive108-field-emitter-dead` (45min silence→breach),
  `alive108-target-down` (NLB HealthyHostCount<1, missing=breaching).
  SNS `alive108-ops` → owner's gmail — subscription CONFIRMED Oct 7.
- **Spend**: ~$0.15-0.25/week actual (Fargate Spot + Dynamo on-demand + S3 + CW).
  $50/month billing alarm armed.
- **T-60 rule**: Spot→on-demand flip ONLY inside the demo-day runbook window
  (docs/demo-day.md), then back after.
- **deploy.sh owner**: was them; now this board. P0 hotfix flow proven today —
  `f9ea5ae` landing-fix went push→prod in ~10 min.

## Open items carried over (watch-list)

1. **iOS residual cold-first-tap** — ~14% on the pre-rootfix measurement;
   ios-residual lane re-measuring post-`3c24a5e` now.
2. **TLS/domain** — HTTP only; needs a domain (~₹400-800) + ACM cert. Owner deferring.
3. **GitHub Release for the APK** — attachment URLs 401 to outsiders;
   needs owner upload or PAT. Freeze-cut binary pending (~20:00 IST freeze).
4. **Admin auth** — owner asked for a real login gate; admin-auth lane building it now.
5. **sdt-website** on the old org — owner's other project, untouched, stays there.
6. **Old-org lead session** still alive there — told to stand down ALive duties.

## Owner's original prompts (4 days, distilled)

96 user messages over the lead's life. The through-lines, verbatim-flavored:
- "loop for 12 hours at least, go through my entire tail to head" (Oct 4)
- "nothing is fake, not even a Figma diagram or a cutout" (Oct 5)
- "I hated the entire landing page… ASCII component… cheap slop neonish vibe" (Oct 5)
- "admin dashboard is not functional — it's a global dashboard I'll show at the hackathon" (Oct 4)
- "launch 2 more subagents… pocket rig has its own, so 2+1=3, two spots left" (Oct 4)
- UI cheapness complaints drove THREE overhaul rounds: vibecoded → skeleton → design-v4/v5.
- Consolidation order (Oct 7): "completely shift from there to here… all your seven agents running."

Full verbatim log: `/Users/devin/oldorg/import/lead-*.jsonl`.
