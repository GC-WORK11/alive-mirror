# Lane: judge-qa — the brutal questions, answered with live evidence

## Why now
The demo isn't just the walkthrough — it's the Q&A. judges-faq.md exists
but was written pre-dosimeter-epoch. Every answer a judge can test must
be verifiable with a live curl or a pointed file. An answer that can't
be proven on stage is a liability, not an answer.

## Scope
- Read `docs/plan/judges-faq.md` + `docs/demo-day.md` + the product
  thesis in `docs/plan/alive-depth.md` first.
- Build the brutal set — the questions a hostile judge ACTUALLY asks:
  1. "How is this different from the AQI apps on my phone?" → the
     dosimeter answer (personal µg dose, nobody else computes it
     without hardware) + the live curl that proves it.
  2. "Prove the field isn't fake" → /v2/skill self-grade (h+1 MAE live),
     24 WAQI stations in /health.sources, recorded-vs-model archive.
  3. "Prove privacy isn't a slide" → the privacy epoch evidence:
     community.py aggregate-at-ingest (no per-trip row exists), the
     apk-v3 tcpdump (268 reqs, only plan/reroute POSTs), k≥3 gates,
     first/last-300m client-side trim.
  4. "How is the dose actually computed?" → Mobile/src/store/daylog.ts
     trapezoid integration + ME_VE table + server/exposure.py parity
     tests + the 13-test runnable harness.
  5. "What happens offline / on venue wifi?" → the offline-resilience
     findings + honest queue behavior.
  6. "What's AWS doing here?" → ECS/CodeBuild/NLB/S3/ECR — the deploy
     pipeline itself (this is the AWS hackathon).
  7. "Numbers that look too good" → the 33× dose gap mechanism (mode
     dominates over micro-routing: ME·VE vs street choice) — have the
     live pair ready.
  8. "What breaks at scale?" → honest limits: reach is bounded-Dijkstra
     O(edges), field rebuild cadence 15min, OTP/Amazon-geo for transit.
  9. "Is this just a wrapper around government data?" → no — kriged
     field + priced graph + dose reconstruction + recorded archive are
     the product; stations are one input.
  10. Whatever you'd ask if you wanted this to fail — add them.
- For EVERY answer: the one-line stage answer + the proof artifact
  (live curl command + expected output, or file:line). Verify each curl
  against live `http://65.2.28.40` NOW — never leave a stale figure.
- Rewrite `docs/plan/judges-faq.md` with the verified set (keep any
  still-true content; kill anything you can't prove today).
- Report → docs/lanes/judge-qa-report.md: the question list, which were
  already covered, which were gaps, which answers changed.

## Hard rules
- Every claim cites a live curl (with its output pasted) or a
  file:line reference. Zero unverified claims.
- GETs + /v2/plan + /v2/reroute only on live.
- Commit to base/v2 (pull --rebase first). Never deploy.
