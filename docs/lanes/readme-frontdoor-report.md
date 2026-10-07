# readme-frontdoor lane report — the judge's first surface

Date: 2026-10-07 · Branch: `base/v2` @ `2cc3628` + this commit · Lane brief:
cold-read the README as a judge, refresh it honest, sweep the repo front
door. Boundaries kept: README.md + this report only — no product code.

---

## 1. What a judge saw first (the old README)

The old README was already honest — dosimeter lead, measured-numbers table,
a "what it does not claim" section — but read as an engineering doc, not a
front door:

- **No live demo in the first screenful.** The NLB URL sat in a plain-text
  sentence under the fold; nothing said "click here and it's running." For
  an Oct-8–11 judge pass that's the single most important line in the file.
- **No try-it block.** The repo serves a public GET surface a judge can
  curl in 30 seconds; the README never showed it.
- **APK absent entirely.** No mention of how a judge gets the app.
- **"54 instruments"** in the diagram footnote vs **53 live** — one-day
  drift, exactly the mismatch the numbers-audit lanes keep catching.
- 180 lines, heavy on process (phase table + per-endpoint detail) before
  the reader knows whether the thing is alive.

## 2. What changed (README.md)

Front-loaded the proof, kept the honesty engine:

- **New "See it live" block at the top** — clickable ELB link (landing `/`
  + `/city` `/community` `/admin`), honest "plain HTTP" tag, and the
  Android APK stated as what it is: a sideloaded debug-signed demo build
  shipped with the submission (recipe `docs/demo-day.md`); iOS stated as
  simulator-only.
- **New "Try it — public, GET-only"** curl block: `/health`, `/aqi`,
  `/v2/city`, `/v2/city/moves` (`min_k:3` on the wire), `/v2/archive`.
  Every endpoint in it re-hit live before shipping.
- **"Privacy, in three lines"** — no accounts; trim-300m/thin/round/hash-
  before-store so no per-trip record exists server-side; nothing publishes
  below k=3/72h with the suppression counter public.
- **The ~35× demo-OD spread** moved up into "What it is" with the honest
  drift band (31–45×) and the published-measurement anchor.
- **Architecture diagram kept (ASCII), trimmed**: `54 instruments` →
  **53, with the drift band (51–54, 24 in a DPCC stall) stated**; the
  endpoint wall collapsed to one line; EventBridge noted as *honestly
  disabled* scaffolding; added the self-hosted 22.7 MB pmtiles basemap +
  125-station climatology (both verified live — `/tiles/health` 200).
- **"Why AWS (Track 01)"** — the real-vs-decorative split in one
  paragraph: CodeBuild→ECR→Fargate+NLB+EIP, DynamoDB agg store, S3 archive,
  Secrets Manager; EventBridge stubs disabled by design; ~$46/mo.
- **"What it does not claim" gained two rows judges will actually hit:**
  plaintext HTTP edge + one-task honest capacity (~8–15 concurrent), and
  the young community layer (~40 donations — sparse by the k≥3 gate, and
  we say so).
- **Run-it-yourself**: kept, plus the demo-build note (EXPO_PUBLIC_API_URL
  baked, cleartext by necessity, debug-signed) and the C++ build step
  (`brew install eigen` + `core/build_ext.sh`) so a cloner's pytest run
  doesn't silently skip the parity suite.
- Status table kept (honest checkboxes), wording refreshed — iOS SIGSEGV
  now says "root-caused + patched sim-side" with the report link instead
  of the stale "upstream render race" line.

## 3. Verification — every live claim re-hit, 2026-10-07 ~06:56 UTC

| Claim in README | Live value now | Where |
|---|---|---|
| stations live | **53** (`waqi+dpcc`, both feeds `ok`) | `/health.sources.stations` |
| edges | 1,070,459 total / 903,058 priced | `/health.routing` |
| engine | `alive_core` | `/health.engine` |
| transit | metro + bus `real_feeds` true | `/health.transit` |
| LOO calibration | mae 8.8 / rmse 12.7 / n 70 / bias +0.2 | `/aqi.calibration` (on the wire, not just the file) |
| privacy floor | `min_k: 3` | `/v2/city/moves` |
| demo OD spread | 34.5× at last probe; README says ~35× + 31–45× band | `POST /v2/plan` (lane card) |
| climatology | 125 archive stations | `/health.history.stations_climatology` |
| tiles | 22.7 MB pmtiles, z0–14 | `/tiles/health` |
| build | `70914c00` | `/health.build_sha` |

File-traced claims re-checked: 124,311-row bundled gazetteer (counted in
`Mobile/assets/delhi-gazetteer.json`), 97,447 corpus entries + 16,949 addr
rows + 67/67 acceptance (`server/data/corpus/STATS.md`), bench table
(0.189 ms / 174,618 lups / 11.2 µs — `docs/plan/bench-results.md`),
field-validation 3,550/85/95.2% (`server/data/field_validation.md`).

## 4. Front-door hygiene sweep

- **LICENSE** — present, MIT, `govinda (ALive-108 contributors)`.
- **PRIVACY.md / SECURITY.md / HANDOFF.md / docs/README.md** — all exist
  and are linked from the README.
- **Every `](path)` link and every inline-code path in the README resolves**
  (script-checked; all 20 referenced files exist).
- **No badges, no stale-branch refs** — nothing abandoned-looking.
- **CONTRIBUTING**: deliberately not added. `docs/README.md` is the "how to
  read this repo" map and the README now links it; a CONTRIBUTING file
  would be process-cosplay for a hackathon repo. Flagged as the call made.

## 5. Still missing — owner follow-ups, stated plainly

- **No public APK artifact exists.** The canonical APKs live at
  `app.devin.ai/attachments/…` URLs, which return **401 to anyone outside
  the org** — a judge cannot download the app from a link in this repo.
  Fix at squash time: attach `alive108-<head-sha>.apk` as a **GitHub
  Release asset** on the public repo (137 MB < 2 GB limit), then the
  README can link `releases/latest` directly. Until then the README says
  "shipped with the submission + build from source" — true, but weaker
  than a link.
- **No embedded screenshots.** In-repo captures (`docs/lanes/*-shots/`,
  `docs/assets/cloud-build/`) predate landing-v5 and the current app
  chrome — embedding them would show judges a page that no longer exists.
  Fresh captures at freeze-time would be strictly better than none; the
  honest call today is none.
- **TLS** — unchanged: plaintext :80, owner decision, stated in the README.
- **`docs/submission/repo-readme.md` is a different, glossier README**
  (screenshots, longer pitch) still sitting in the tree — if the public
  repo uses it as the front page instead, port these edits there; if it's
  vestigial, it duplicates the front door.
