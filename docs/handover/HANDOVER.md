# ALive — MASTER HANDOVER (2026-10-09 ~17:00 IST)
*Written by the local Devin CLI session. You are the new parent orchestrator.*

## The mission
ALive = Delhi PM2.5 exposure app. Hackathon: AWS × WeMakeDevs EnvironmentalHacks —
release is TODAY. Owner's X post got a "lets go" reply from WeMakeDevs. Judges,
public scrutiny, and the owner's career ride on this shipping polished and honest.

## Repo access — READ THIS FIRST
- Canonical: `origin` https://github.com/<owner>/Delhi-Air-108.git —
  **the owner's GitHub account is SUSPENDED locally but cloud pushes WORK**
  (bridge lane pushed 1772669 fine). Always `git fetch origin` first.
- Mirror (fallback, always writable): https://github.com/GC-WORK11/alive-mirror.git
  branch `base-v2` — kept in sync by the local CLI session.
- Local working copy lives at ~/repos/Delhi-Air-108 on cloud machines.

## Current state — what is true right now
- **Prod http://65.2.28.40** serves the NEW teaser landing (build 67a85e1d).
  Verified: zero console errors, no banned links, no overflow 320→1440,
  loader self-removes normal+reduced-motion, tests 5/5.
- **origin/base/v2 = 1772669** (+04ae11d inbound via bridge): teaser landing +
  mobile D2 (skip→sharing OFF) + consent footnote + share-caption-state +
  sheets safe-area + strings + android-god round-2 fixes.
- **Ship APK**: `alive-final-universal.apk` built by apk-final lane (attachments
  in that session) — universal arm64+x86_64, on-device verified: skip→home,
  sharing OFF, caption "off — nothing leaves this phone", live 43µg/m³ hero.
- Local verified binary: alive-consciousness/local-logs/apk/alive-04ae11d-universal.apk
  (built 16:16 IST from tree incl. footnote+P1 caption; predates only 04ae11d P2 copy).

## THE LAW (owner's rules — violations caused days of rage)
1. NO hardcoded/fake numbers — every figure traces to a live API field or honest
   computation; disclose data age. When data's missing: say so, never invent.
2. Brand is "Alive" — capital A, never ALIVE in visible UI.
3. Landing page = pure teaser. ZERO links to github/admin/download/city/community.
   Admin analytics = separate owner-only obscured mount, NOT public.
4. No cards/boxes/capsule pills on web surfaces (cognition.com register).
   Hairlines + type, not containers. Band colors = air quality only.
5. Both iOS AND Android screens shown raw/tilted — no thick device mockup frames.
6. Plain purpose-driven copy. Banned: "dosimeter", "body count", delay-your-life
   framing, cringe captions, dashboard aesthetics on marketing pages.
7. Every surface has a visible exit; nothing under the status bar.
8. i18n en+hi both. Maps plain by default; colored field only on air intent.
9. Verify on real frames, never claim without evidence.
10. In-app brand string: user accepts tracked "A l i v e" wordmark on onboarding;
    body/section headers use "Alive".

## Open defects / work queue
- [P1-fixed] share caption + skip→off + footnote — merged, verified on-device.
- [P2-fixed] move card "cleanest stretch" vs playtime "least-bad window" — 04ae11d.
- [OPEN] landing-verify P1: hero "95.2% / 3,550 hidden readings" claim vs what
  /v2/skill actually serves — reconcile copy to wire truth or fix the endpoint.
- [OPEN] landing beats v20 in progress locally: each use-case beat gets a REAL
  recorded app video (not stale-copy drafts); spacing/composition tighten;
  mobile shots larger; districts return as a HORIZONTAL ruled strip fed by
  /v2/districts. Draft mp4s in server/static/demo-*.mp4 contain STALE copy —
  must be re-recorded on the final APK before shipping.
- [OPEN] demo-record flag: hero "pm2.5 · satisfactory" chip = thin rectangular
  tag — borderline box; restyle to dot+text if owner still unhappy.
- [OPEN] To-field keeps stale text on rebind (minor UX wart).
- [OPEN] nav-mount ~40-70s under swiftshader (rig artifact; physical device TBD).
- [OPEN] live-GPS nav unverifiable on emulator — needs physical device.
- [REMEMBER] release builds need EXPO_PUBLIC_API_URL=http://65.2.28.40 exported
  before bundling or the APK shows "can't reach the server" forever.

## Cloud lanes this day (all under org, tag alive108/final-day)
- bridge a247bcb1ec6c4e89b372cc19fe5b25ef — deployed teaser, merges mirror→origin
- android-god 71bb3e10d2294320ac50de0720f06b8c — shipped e4eff61, round-2 no-rage
- android-KVM 6093e3a70ce04fe1b37030ff9a15c80e — round-2 zero-crash, found P1
- e2e-prod 996183b2b92f4fd88cc24e62519e9d1f — 84/84 GETs verified honest
- judges-copy bf89bd93d14d4f2cb401ba522e3ad4b3 — writeup+X drafts, no "dosimeter"
- field-watch 97305a289bf64deb822e8ab8af11584b — prod guardian (running)
- demo-record 42909b1eed184ab586d77f865d621344 — landing film, frame-verified
- landing-verify 99c3df03689e45f8b343bc1aeae830b5 — GO + P1 flag
- apk-final aefb8f9a5da84bf38d1a444447f39e82 — universal+arm64 delivered
- apk-verify 71f95f2599434fc0aaeffe2c0ad3bc72 — KVM drive PASS, emulator warm

## Deploy
./scripts/deploy.sh — ECR→ECS Fargate→NLB. AWS creds in cloud env.
Does NOT need GitHub. Prod = http://65.2.28.40.

## HANDBACK PROTOCOL (for the local CLI session to resume)
When the owner returns, the local session will:
1. git fetch mirror (GC-WORK11/alive-mirror base-v2) — any of your commits there
   land locally; also fetch origin tip.
2. Read docs/handover/HANDBACK.md IF YOU WROTE IT — write it before you suspend:
   what you changed, commit shas, prod build_sha, open items, anything half-done.
3. Query org sessions for your final status + attachments.
Leave the repo committed + pushed (origin preferred, mirror as backup). Never
leave the tree dirty without a note in HANDBACK.md.

## Local-only knowledge base
/home/govinda/alive-consciousness — git repo with 00-STATE, 01-PRODUCT,
02-WHY-HE-IS-ANGRY, 03-05 sagas, 06-THE-LAW, local-logs/{android,demos,city,apk},
all 256 session dumps. Cloud can't read this path — this doc carries what matters.
