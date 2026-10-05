You are the self-grading lane for ALive-108 — the never-done demo artifact: **the product publishes its own accuracy.** The archive has recorded real hourly snapshots + the forecast we served since Oct 5 (`server/archive.py`, basis:recorded, model values stored alongside where they exist). By demo morning ~60+ hourly pairs exist. Build the endpoint + surface that grades the model live — judges can watch the product score itself.

Repo: <owner>/Delhi-Air-108, branch base/v2 (pull latest — lanes push often). Server: FastAPI `server/` (Python 3.12, tests in `server/tests`, venv `.venv312`, `PYTHONPATH=core/build312:.`). Live: http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com.

HARD RULES
- Push code only — never deploy. GETs only on live.
- Suite must stay green: `cd server && PYTHONPATH=core/build312:. .venv312/bin/python -m pytest -q tests` before push. New behavior needs tests.
- Nothing fake: only real recorded-vs-served pairs from the archive. Few pairs → say so honestly (n= is part of the truth), never extrapolate or smooth. If horizon-h pairs don't exist yet, that bucket is honest-empty with its n.
- No new dependencies. No pandas/numpy unless already imported.

MANDATE
1. Read `server/archive.py` + the snapshot schema on S3 (`alive108-air` bucket — you have read access via the task role pattern used by other lanes; check how archive.py reads/writes and reuse it). Understand exactly which pairs exist: recorded value + the forecast value we SERVED for that place/hour (horizon = how far ahead the forecast was when served).
2. `GET /v2/skill` — the scorecard endpoint:
   - per-horizon MAE / bias (model − recorded) in µg/m³, with n per bucket
   - hit-rate: % of hours where the served band (CPCB category) matched the recorded band
   - coverage window (first/last pair timestamp, IST) so "since Oct 5" is provable
   - honest-empty when n is thin: `{"status":"thin","n":k}` rather than fake precision — publish numbers ONLY where n is meaningful (define your floor, justify it)
3. Admin surface (`server/admin.html`): a "the model grades itself" card — horizon × error table, one plain line under it ("each cell: how far off our served forecast was vs what Delhi actually recorded — lower is better, n = how many hours compared"). Match the gtiles/plain-sub-line register already there.
4. Landing or /city: ONE honest line if it earns its place ("our forecast has been within ±N µg/m³ of recorded reality, n hours running") — only if n supports it by demo morning; wire it so it hides itself honestly when thin.
5. Timezone discipline: pairs are IST-hour keyed — get the bucketing right (recorded hour vs the forecast's target hour, not the serve hour).

Report: endpoint contract, sample live output (even thin-n), admin/landing diffs, test names added.
