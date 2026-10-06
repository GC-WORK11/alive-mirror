# Lane: judge-qa-v2 — brutal questions on the dosimeter product

## Why
judge-qa (v1) ran before the dosimeter epoch — the product then was
route-first. Judges now see: a lungs' ledger, THE MOVE, dose bands,
recorded-vs-forecast, /v2/why causal lines, k≥3 community, engine-room
admin. New surfaces = new attack questions, and v1's answer doc is
stale. Produce a fresh Q&A sheet where every answer cites live proof
a judge can re-run.

## Scope
1. **Attack-list the CURRENT product** — the questions a hostile
   engineer judge asks a dosimeter claim: "where does the dose come
   from — your timeline is fakeable", "why is 33× believable", "the
   field is interpolated — where's the calibration", "k≥3 with 14
   contributors means your corridors are empty", "your history
   sparkline is seeded", "why should I trust modifier 1.09", "show me
   the model is better than persistence", "what breaks when WAQI
   dies", "your cigarette math is sensationalism", "the APK is
   sideloaded — how do I know it's the same code".
2. For each: the honest answer + the LIVE artifact that proves it
   (endpoint, doc, data file, commit). Where the honest answer is
   "it isn't/isn't yet" — write that, and say what the demo says
   instead. No spin.
3. Verify each cited number live (GETs + /v2/plan + /v2/reroute).
4. Output docs/plan/judge-qa-v2.md: question × honest answer ×
   live proof × what-to-say-on-stage. Flag any question we genuinely
   can't answer — those are the demo-morning risks.

## Hard rules
- Live API GETs + /v2/plan + /v2/reroute only. Never POST.
- Docs only — no code changes. Commit to base/v2 (pull --rebase).
- Report → docs/lanes/judge-qa-v2-report.md.
