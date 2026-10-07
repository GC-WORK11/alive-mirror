# Lane report — demo-morning: the final runbook

**Date:** 2026-10-07 ~13:05 UTC · **Deliverable:** `docs/plan/demo-morning.md`
(the single timed checklist Govinda holds tomorrow morning).
**Prod at write time:** `/health` `build_sha c86074ff`, `field_stale false`,
`field_age_s 651`, engine `alive_core`, stations 51 (waqi+dpcc both `ok`),
wind 5.1 km/h @ 354° N. No code touched; this lane writes two docs only.

## Sources read

`docs/demo-day.md` (1033 lines, re-pinned Oct-7 11:00 UTC on `698cf808`),
`docs/plan/demo-script.md` (8-beat table, same pin), `docs/11-demo-script.md`
(video script), `docs/plan/admin-login.md` (T-30 sign-in playbook, proven
on prod by admin-login-e2e), `docs/plan/go-nogo.md`,
`docs/submission/submission-checklist.md` §3, `docs/plan/handoff.md`
cont.66–70, and today's lane reports: `demo-rehearsal-v2-report.md`,
`watchdog-log.md`, `testday-offline-report.md`, `offline-walk-report.md`
(landed 81c2326 mid-write — verdict folded into the runbook),
`ios-residual-reverify-report.md`, `apk-v10-report.md`,
`apk-final-report.md`, `admin-login-e2e-report.md`.

## Brief claims — verified against the lane reports, not trusted

| brief claim | verified? | evidence |
|---|---|---|
| chooser plays behind vehicle wizard on cold/first-run → pre-warm phone | **YES** | rehearsal-v2 F1: "vehicle wizard only intercepts the **first-ever** plan"; 03-chooser.mp4 shows the equals→bold→pill under the wizard. In runbook as the T-45 phone block. |
| notif permission dialog interrupts welcome film on FIRST boot only → install+grant once before morning | **YES** | rehearsal-v2 F4 + beat 1: film → POST_NOTIFICATIONS dialog → 3-page onboarding → location perm → home; consent/state persisted across force-stop (shot 07). |
| chooser pill holds ~4.2 s | **YES, twice** | rehearsal-v2 timing table: pill A "cleanest and fastest" 30.1→35.3 s, pill B "cleanest · 51% less than fastest" 39.5→43.7 s — two ~4.2 s holds; runbook narrates the second (it carries the quantified claim). |
| metro+walk only guaranteed on the demo OD; don't improvise ODs | **YES** | rehearsal-v2 plan table: metro+walk **48.5 present** on IG→HCC, **ABSENT on CP→Gurugram** (the script OD) the same hour; my live probe 13:00 UTC: present again at 58.8. Runbook carries the "don't improvise" rule + the fallback clause. |
| `/v2/why` drivers flip with wind → T-45 live check, no memorized line | **YES — flipped today** | watchdog 12:31 UTC: `carrying false→true` (belt 16, N wind); my live read 12:56 UTC: `line` = stagnation + "stubble smoke drifting in on the northerly wind", modifier ×1.27 (was refused ×1.06 all morning). Runbook gives both wordings keyed on `cause_note_fields.carrying`. |
| `/depart` pct on demo OD was 17–25 today; row needs >8 | **YES — and it moved again** | rehearsal measured `pct_less_vs_now` 25 (row stable, no flicker); my live probe 13:0x UTC: **car 29 / auto 28 / walk 28** (now 7.0 µg, best 5.0 @ +22 h Oct-8 10:00). Still far over the `>8` gate — but the T-45 curl + the flat-day fallback are in. |
| admin sign-in at T-30, Chrome "Save password?" → Never | **YES** | `docs/plan/admin-login.md` line 21 verbatim; e2e report proves gate-card → cookie → board → 8 h on prod build `43913dc0`. Failure table (429/503/captive portal) folded in. |
| iOS residual exists in DEBUG builds only; release rate being measured | **YES, with a gap** | `ios-residual-reverify-report.md`: REGRESSION — 14/30 kills at HEAD (was 0/30), identical SIGSEGV signature, patch verified active; victim is `consoleTaskRun` (dev-inspector, Debug-only). **`docs/lanes/ios-release-residual-report.md` has NOT landed** — Release crash rate remains unmeasured. Runbook: demo is Android; iOS needs ≥90 s open before first search tap if it must show. |
| `offline-walk-report.md` may have landed | **LANDED mid-write (81c2326)** — and it changes the fallback | `offline-walk-report.md`: the `delhi-ncr-z9-13-r1` offline pack creates its region row but downloads **0 tiles** — `Mbgl-HttpRequest` rejects the `file://` style_url. Everything else degrades honestly (search via bundled gazetteer, plan/DelhiToday fail with real error+retry, home shows last-known, recovery repaints live). **Demo-morning consequence folded in: the basemap will NOT cover the venue on dead Wi-Fi — only viewport panned that day renders; the T-45 pre-warm pan over the demo corridor is what makes the map survive.** testday-offline's 8/8 honesty PASS also folded in (mid-trip nav + receipt work air-gapped on the cached strip). |

## Live probes run this session (all GET + the sanctioned POST)

| probe | result (13:0x UTC, `c86074ff`) |
|---|---|
| `GET /health` | 200 · `c86074ff` · stale false · age 651 s · engine `alive_core` · stations 51 · wind 5.1 km/h @354° known:true |
| `GET /v2/why` | line "…sitting over the city **+ stubble smoke drifting in on the northerly wind**" · cause_note carrying:true · belt 16 fires / 41.4 MW · modifier ×1.27 · drivers[0] stagnation |
| `GET /v2/depart` demo OD | vehicle=car: now 7.0 µg, `pct_less_vs_now` **29**, best 5.0 @+22 h (Oct-8 10:00), worst 14.6 @+18 h; auto: 20.6/28; walk: 240.7/28 |
| `POST /v2/plan` demo OD | **22 options, `took_ms` 8,783** (cold post-refresh reprice — this is why warm_task + the T-45 re-hit are load-bearing), `smoke_modifier` 1.27, no `degraded`; car-AC 8.9 / walk ~307–314 → **~34.5×**; **metro+walk 58.8 present** |

## Corrections vs the brief (folded into the runbook)

- **`scripts/warm_task.py` → `tools/warm_task.py`** — the real path
  (audit-runbook already flagged the `scripts/` guess). BASE is baked to
  the NLB; exit 0 ⇔ priced engine serving.
- The Spot→on-demand flip is **omitted as a step** — demo-day.md was
  amended today: default is stay on FARGATE_SPOT (₹0 budget); flip only
  if a reclaim lands or the owner decides. Runbook carries it as a
  standing rule, not a timed step.
- GO/NO-GO admin check = a curl login probe (proves token+endpoint);
  the browser sign-in itself stays at T-30 per `admin-login.md`.
- The freeze APK `alive108-c3f7e9e.apk` **predates** `795ff3b`
  (news-layer app air-card) — verified `git merge-base --is-ancestor`.
  App surfaces still carry `why.line` (`8d032e3`); the parali curl at
  T-45 decides the wording regardless. If a later HEAD re-cut lands
  tonight, take the newest per `apk-*-report.md`.

## Numbers policy in the runbook

Pinned where verified today (spread ~34–35×, "about twenty" options,
pill ~4.2 s ×2, edge counts, cookie ~8 h, 15-min field heartbeat) —
**placeholder-for-live-check where the data moves** (why/cause_note/
carrying/fires, depart pct, AQI, stations, community counters,
build_sha) with the exact curl to re-derive each at T-45/T-5.
