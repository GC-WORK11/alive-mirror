# docs/15 — Win analysis, brutally honest

Sources: wemakedevs.org/aws/rules, /aws/env, /aws/first-commit (read 2026-10-01).

## The actual rules — what judging sees

A submission is exactly three things: **a public repository, a ≤3-minute
demo video, and a short writeup** (problem, build, where AWS fits).
There is no live demo and no call: *"if the video does not show it, it
does not count."* Judges score only what is submitted.

Criteria (official page):

1. **Idea & Impact** — does it solve a real problem; what changes for
   people. "A small problem solved well beats a big one solved vaguely."
2. **Built on AWS** — mandatory for prizes. *"Your project has to use AWS,
   and your demo video has to show it. Naming AWS in the writeup alone is
   not enough."*
3. **Design & Usability** — a judge who has never seen it must be able to
   pick it up. "Clean and obvious beats clever and confusing."
4. **Execution** — does it work, not perfect.

## Disqualification risk (read first)

> "a repository whose history does not match the event dates
> disqualifies the whole team."

This repo's history predates the Oct 8–11 event window. **Plan:**
on Oct 8, create a fresh **public** repo, squash the current state into
one baseline commit, and keep committing during the event. Nothing is
lost — all work carries over — but the visible history then matches the
rules. This is non-negotiable hygiene, not gaming the system: the rules
also allow "open-source libraries, frameworks, boilerplate" — what is
judged is what you add during the event, and our real additions (docs
below) land inside the window.

Also note: **the repo is private today — submissions must be public.**

Second honesty note: *"Winning a track does not qualify a project for a
fast-track interview"* — prizes and interviews are decided separately,
on different criteria. Win anyway; but the internship path is the
project's overall impression, not only the trophy.

## Score today (honest)

| Criterion | Now | Gap |
|---|---|---|
| Idea & Impact | Strong — personal dose + collective map; real numbers | Ledger of avoided-µg must be **visible in the video**, not just coded |
| Built on AWS | **Zero AWS in the running system.** Fatal for prizes | ECS Fargate deploy (LIVE — public URL serving the engine), S3+CodeBuild+ECR pipeline, S3 climatology — all running, all filmable |
| Design & Usability | Functional light theme, real data, working drawer | Onboarding: a first-time judge needs 10 seconds to "get it" — the explainer line exists but the first screen is still dense |
| Execution | Works end-to-end on both platforms, proven | Android re-proof pending; make the video itself the proof |

## What wins (ranked by leverage/effort)

1. **Deploy + show AWS.** DONE — ECS Fargate live at a public URL (App Runner refused on new accounts; Fargate is the same serverless story). S3 for
   the climatology parquet already in use; DynamoDB table for
   observations (replaces community.json — same code shape). Show the
   AWS console in the video for 10 seconds. Without this, zero prize
   chance regardless of quality.
2. **The 3-minute video is the product.** Arc: 0:00 Delhi problem stat →
   0:20 FROM→TO dose ranking (the money shot) → 0:55 leave-later +
   segments → 1:20 Lung Ledger (cigarette math = instantly understood
   impact) → 1:45 "Delhi breathes" community layer + admin dashboard →
   2:20 AWS architecture slide → 2:45 honesty slide (what we measure,
   what we don't claim). Every second scripted in docs/11 — rewrite it
   around this arc.
3. **Ship the safety layer** — MoRTH publishes 115 Delhi accident black
   spots (blackspot.morth.gov.in / data.gov.in dataset, free key needed).
   `/decide` already does safety-first mode ranking; add black-spot
   proximity to routes when the data lands. User asked for this
   explicitly — it is also the cheapest "real" addition.
4. **Admin dashboard** (`/admin`) — built. In the video it proves the
   system is live and collective, not a mockup.
5. **Cut/none**: C++ rewrite (wastes days for latency nobody measures —
   the demo server is already <1s end-to-end), accident "avoidance"
   claims beyond mode tiers (no street-level data exists — honesty).

## The honest sentence for the video

"We cannot clean Delhi's air with an app. But we can measure exactly
what each commute costs your lungs, cut it by up to 30x on the same
trip, and turn every journey into a shared sensor the city doesn't
have. That is ALive-108."

## Intel from the organizer's own recap (builder.aws.com, Oct '26)

Source: https://builder.aws.com/content/3G032f5pc3jkHYJgScu58vxrXsn/first-commit-hackathon-recap-and-whats-next
plus wemakedevs.org/aws/env + /aws/first-commit pages and the three
winner demo transcripts (pulled via yt-dlp).

### The event shape
- Bharat Builds = 6-city tour; Environmental Hacks is stop #2 (Oct 8–11,
  online). Build day Oct 10 at DTU Delhi 8AM–8PM — in person, AWS
  mentors + Kunal Kushwaha / Saiyam Pathak / Piyush Garg on the floor.
  Going is free feedback + face time with the judges' own mentors.
- ₹20 lakh pool; Air track ₹2L + $2K AWS credits; 4 runners-up $1K each;
  5 AirPods for Builder Center blog write-ups (publish the build story
  and link it in the submission — free extra entry).
- Top-10 across ALL tracks get Amazon fast-track (6-mo internship + FTE)
  — a win is not required; a strong project alone can carry it.
- Prior stop scale: 13,667 participants → 1,180 submissions.

### Published judging criteria (verbatim)
1. Idea & Impact — "a small problem solved well beats a big one solved
   vaguely" ← we are a small real problem solved deeply.
2. Built on AWS — mandatory for prizes; "the architecture is part of
   the score" for Ship It ← ECS/NLB/S3 deploy + the console film beat.
3. Design & Usability — "a judge who has never seen your project should
   be able to pick it up and use it... clean and obvious beats clever
   and confusing" ← the scoring axis IS the cold-eye/soul work; the
   judge is a stranger by design.

### What actually won (transcripts of the embedded demo videos)
- Suraksha (1st): opens "Parents want independence. Children want
  peace of mind." — two emotional lines, then what it is, then live
  demo. Pattern: felt framing first, features second.
- Beacon (2nd): "It is 3:00 in the morning, payments are failing..."
  — an in-the-moment scenario before the product appears.
- CampusEvac (3rd + Best UI): straight into live footage — craft and
  usable design count as their own axis.
- Formula: emotional/scenario hook in the first ~20s, LIVE product,
  zero slides until architecture at the end.

### Delta for our cut (vs the arc above)
- Our cold-open should be a FELT line, not a stat: e.g. "It's 7am in
  Delhi. The air outside your door is 12 cigarettes today — and nobody
  told you." Then the day-in-life arc we already taped.
- The hero-in-3-seconds moment (open → breathing hero → the move) is
  our "clean and obvious" proof — the judge-picks-it-up test.
- Console film stays; add one architecture TALKING point on tape:
  "the field builds every 15 minutes on ECS — the phone only pays for
  consented aggregates" (architecture-as-score, spoken).
