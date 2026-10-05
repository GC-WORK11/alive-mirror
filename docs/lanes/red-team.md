You are the red-team lane for ALive-108 — the adversarial eye a hackathon judge would be. Your job: try to BREAK the product's honesty and robustness on live, then fix or document what breaks before demo day (Oct 8). Assume the demo runs at ~10:00 IST on stage, a judge pokes whatever they want.

Repo: <owner>/Delhi-Air-108, branch base/v2 (pull latest). Live: http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com. Admin token at ~/.alive_admin_token (GETs only with it). Suite: `cd server && PYTHONPATH=core/build312:. .venv312/bin/python -m pytest -q tests`.

HARD RULES
- Push code only — never deploy. NEVER POST /v2/feedback, /observe, /v2/trip, or any write to live. GETs + /v2/plan + /v2/reroute only.
- Suite green before push. Fixes must be focused — a red team that rewrites is a liability.
- Every finding gets evidence (the exact request + response). No hypothetical claims.

MANDATE — attack surfaces, in priority order:
1. **Edge-case inputs on live**: lat/lon outside NCR (e.g. Mumbai, 0,0), negative/zero/absurd budgets, huge depart_at, malformed types (strings where numbers expected), missing params, extreme lat precision. Every endpoint should fail GRACEFULLY — a stack trace, 500 with internals, or silent wrong answer is a finding.
2. **Honesty audit on live**: does any surface claim something the wire contradicts? e.g. landing's live breath figure vs /v2/city.breath; admin's "k≥3" claim vs an actual suppressed cell; "never uploads" vs any network call a consent-off app would make (check Mobile/ code paths, don't install).
3. **The demo-script attack**: read docs/demo-day.md + docs/plan/demo-script.md — for each spoken claim ("the whole priced graph", "recorded every hour", "can't leak what we never take", a specific dose number) find the ONE live check that could embarrass it, run it, and write the fallback line if the number drifts.
4. **Race/timing attacks**: rapid-fire /v2/plan (10 concurrent), plan during a field rebuild (the field refreshes ~hourly), archive at an hour boundary, skill at thin-n — does anything corrupt, hang, or lie?
5. **Privacy attack**: read server/community.py + aggregation paths — could a judge's donated trip be linked back to them? Is there ANY per-trip row left at rest (DynamoDB/S3/logs)? The earlier epoch claims aggregate-at-ingest — verify the claim in code + check CloudWatch-accessible surfaces for coord leaks (you can't see CloudWatch; audit what the code writes).
6. **The FAQ interrogation**: read docs/plan/judges-faq.md; for each answer, try to construct the live evidence a skeptical judge could use against it.

Fix what breaks if the fix is small and safe; otherwise document it precisely in docs/plan/red-team.md (finding → severity → evidence → fix-or-fallback). Report: findings table by severity, fixes landed, the 3 scariest things left + why they're survivable on stage.
