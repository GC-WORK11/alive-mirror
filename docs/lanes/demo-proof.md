You are the demo-proof lane for ALive-108 — the runbook rehearsal on TODAY's live build. Every beat the owner will show on demo morning must be re-verified against what's live RIGHT NOW (numbers moved, /v2/why just shipped). Deliver: every demo command re-run + demo-day.md updated to current truth + the why line added to the demo arc where it earns a slot.

Repo: <owner>/Delhi-Air-108, branch base/v2 (pull latest — lanes push often; rebase before push). Docs: docs/demo-day.md, docs/plan/aws-console-shotlist.md, docs/demo/ (video assets + assemble.sh). Live: http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com

HARD RULES
- Push docs only — never deploy, never touch code. GETs + /v2/plan + /v2/reroute only. NEVER POST /v2/feedback, /observe, /v2/trip.
- Every command you write into demo-day.md must be one you RAN today against live — record the actual output, not a paraphrase.
- Honest numbers: if a beat's live numbers moved (median, edges priced, stations, MAE), the runbook says what it says TODAY.

MANDATE
1. Read docs/demo-day.md fully — every curl, every beat, every timing claim. Run each against live. Flag anything stale: wrong numbers, endpoints that moved, beats that no longer show what's claimed.
2. /v2/why is live (stagnation claimed honestly, fires gated by bearing, cannot_tell when unknowable). Decide where it earns a demo beat — candidate: right after /city "why tonight" or inside the admin walk ("the engine grades its own causality"). Write the beat: the curl + what the judge sees + the one-line narration. Sample the live response so the script carries a REAL example line.
3. /v2/skill model-grades-itself: probe live, refresh the numbers in the runbook (MAE/bias/band-hit today, per-horizon n).
4. Verify the kill-list: each "works with zero connectivity" vs "needs net" claim in demo-day.md — the offline lane's connectivity plan — confirm each listed surface still matches what the server actually needs (public vs gated endpoints — /admin works token-less for public feeds? verify).
5. Re-time the video beats in docs/demo/assemble.sh against the cut3 assets — flag any beat that references a surface that changed.
6. Report: runbook diff summary, every stale item fixed, the why-beat placement + script, anything demo-risky discovered today.
