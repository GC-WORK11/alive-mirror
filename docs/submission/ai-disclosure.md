# AI tools disclosure — ALive-108

*Hackathon rules require AI tools to be listed in the writeup. This is the
honest list, drafted from repo evidence — verify against your own memory
before pasting.*

## Tools used

| tool | what it did |
|---|---|
| **Devin (Cognition AI)** — autonomous software-engineering agent | Bulk of the engineering across every lane: the FastAPI backend and `alive_core` C++ engine, the Expo mobile app, the web surfaces (landing, `/admin`, `/v2/city`, `/community`), tests, deploy automation, and the `docs/` research + verification corpus. Ran the live verification passes whose numbers fill the demo script and this submission. Its authorship is visible in git: **1,077 commits** carry the `Co-Authored-By: Devin AI` trailer on the working branch (`git log --format=%b \| grep -c devin-ai-integration`; 1,084 across all branches — measured Oct 7). |

## What the human did

Govinda directed the project end-to-end: scope and product decisions, the
zero-fake-data rule, architecture choices (ECS Fargate over App Runner after
the `SubscriptionRequiredException`, self-hosted pmtiles, k≥3 privacy floor),
review and merge of every change, all AWS credentials/deploys/cost decisions,
and every final call on what ships. Devin wrote code at his direction; the
engineering judgement in what to build and what *not* to claim is his.

## Checked and *not* found

A `git log` scan across all branches finds **no** Copilot, Claude, Cursor,
ChatGPT, or other AI-tool trailers — Devin is the only AI tool evidenced in
the repo history. No AI image/video generation is evidenced for assets
(app icons and recorded screen footage only).

*If you used anything else — e.g. a chat assistant for research, or a
generation tool for icons/end-cards — add one line here before submitting.
The rule is disclosure, not abstinence.*
