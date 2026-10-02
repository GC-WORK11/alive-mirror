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
| Built on AWS | **Zero AWS in the running system.** Fatal for prizes | S3 climatology (already real, un-wired visually), App Runner deploy, DynamoDB/S3 community ledger — pick 2 and show them |
| Design & Usability | Functional light theme, real data, working drawer | Onboarding: a first-time judge needs 10 seconds to "get it" — the explainer line exists but the first screen is still dense |
| Execution | Works end-to-end on both platforms, proven | Android re-proof pending; make the video itself the proof |

## What wins (ranked by leverage/effort)

1. **Deploy + show AWS.** App Runner (uvicorn) or EC2 free tier; S3 for
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
