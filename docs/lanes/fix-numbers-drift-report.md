# fix-numbers-drift — close the prod-numbers-card's three flags

Lane: `fix-numbers-drift`. Pass **2026-10-07 ~04:05–04:30 UTC**
(≈09:35–10:00 IST). Trigger: `prod-numbers-card` (17bf81f) — prod
`aee635eb` serves the rebuilt LOO artifact and 53 instruments while docs
and `verify_numbers.sh` still pinned the old world; the {54,24} whitelist
would false-flag at T-45.

Scope kept tight: `scripts/verify_numbers.sh` + doc text only. No product
code touched. Lane reports, handoff entries, and claims-audit rows are
dated records — left as stamps per the fix-verify convention
(`docs/lanes/fix-verify-numbers-report.md`).

## Drift → fix

### Flag 1 · script station whitelist {54,24} → range [52..54] + ±2 cross-check

`verify_numbers.sh` check #10 and the matching notes/emit text:

| matcher | before | now |
|---|---|---|
| accepted full-feed count | exactly `54` | `52–54` — per-instrument aging under `MAX_AGE_S` drifts the count down a few between feeds (max2 watched 54→53→52; prod tonight = 53) |
| `count=54` + source lacking `dpcc` flag | only fired at exactly 54 | fires for any count in the full range that claims WAQI-only — `{N} instruments can't come from WAQI alone` |
| transient `feeds` wart note | `count=54` only | any count in the full range |
| `count=24` degrade | unchanged — info note, not a flag | unchanged |
| impossible-count flag | `∉ {54,24}` | `∉ [52..54] ∪ {24}` — e.g. 30 still flags |
| `/aqi station_readings` ≠ `/health count` | `!=` | flags only when `abs(diff) > 2` — each endpoint ages instruments out at different times (53 vs 53 tonight anyway) |
| `'24 stations' world` doc flag | fired when `st_count == 54` | fires when live is anywhere in the full 52–54 range |

Note text at the bottom of the run updated to describe the range + the
±2 endpoint skew.

### Flag 2 · LOO sweep — 46.1/n=94 "OpenAQ" → the real artifact

Prod `/aqi.calibration` (verified live this pass):
`{"method":"leave-one-out over live WAQI+DPCC instrument readings
(krige refit per held-out station)", "n_stations":70, "mae_ug":8.8,
"rmse_ug":12.7, "median_abs_pct":8.8, "mean_bias_ug":0.2}` — byte-identical
to `server/data/field_calibration.json`. Every claim-doc quote re-pinned
to those numbers (never invented — all from the artifact file):

- `docs/plan/NUMBERS.md` §1 artifact row (the ledger itself)
- `README.md` field-LOO row
- `docs/submission/writeup.md` numbers table
- `docs/submission/repo-readme.md` validation list
- `docs/submission/video-shotlist.md` engine-tile shot note
- `docs/plan/demo-script.md` Honesty section
- `docs/plan/judges-faq.md` proof line
- `docs/plan/10-claims-ledger.md` say-table
- `docs/25-peak-physics.md` shipped table
- `docs/24-design-language-spec.md` provenance-as-design spec
- `docs/10-shipped.md` (both the §measured table and the "error is
  published" paragraph — reframed to "at an instrument the field reads
  the instrument itself", the artifact's own note)
- `docs/17-submission-writeup.md` validation section
- `docs/20-hackathon-playbook.md` trust-mechanism line
- `docs/28-pitch.md` trust-card line
- `docs/plan/judge-qa-v2.md` — the wire-accurate curl sample replaced
  with the new block; its parenthetical caveat rewritten (the OpenAQ-era
  flag is overtaken: the wire now serves the rebuilt artifact)
- `docs/api/REFERENCE.md` + `docs/api/samples/get_aqi.json` — captured
  `calibration` blocks re-pinned; a dated note added to the REFERENCE
  header declaring the refresh (the captures are 2026-10-03 bodies —
  the note says which parts now show newer fields)

Records left alone (dated snapshots, never claims): `docs/claims-audit.md`
rows (audit-dated ledger of what README said on Oct-3), `docs/plan/
bench-krige.md` "spring midday (94 stations)" heading (a stamped bench
window), `docs/plan/handoff.md` cont. entries, all `docs/lanes/*`.

### Flag 3 · "46% below average" — drift, not a constant

`vs_now_pct = (pm25_bz − typical_median)/typical_median` — arithmetic vs
climatology, not a fixed number. Sweep found one claim-doc quote of a
fixed figure: `docs/plan/judges-faq.md` re-derive table said `−44.8% vs
decade norm`. Re-framed to the honest range: "running about a third to a
half below the typical October hour", with the −44.8% kept as its
2026-10-05 stamped read and a "re-read live" pointer. The only other
"46%" hit anywhere is `docs/lanes/android-drive-report.md` — a dated
lane report (record, untouched). `demo-day.md` already phrases it as
"±X% vs the decade norm".

## Green run — `bash scripts/verify_numbers.sh` vs prod `aee635eb`

Run at ~04:26 UTC. Fetches (all GET + the one sanctioned `POST /v2/plan`):

```
  GET /health -> health.json (921B)
  GET /aqi?lat=28.6315&lon=77.2167 -> aqi.json (5642B)
  GET /grid?h=0 -> grid.json (125957B)
  GET /grid?h=0&cells=40 -> grid40.json (362785B)
  GET /fires -> fires.json (21563B)
  GET /v2/city -> city.json (10303B)
  GET /v2/day?lat=28.6315&lon=77.2167 -> day.json (8448B)
  GET /v2/reach (walk@25 / walk@50 / car@25) -> 142K / 452K / 3.7M
  GET /v2/districts -> districts.json (7092B)
  GET /community -> community.json (1452B)
  GET /v2/outlook -> outlook.json (8285B)
  GET /depart CP→GG -> depart.json (7103B)
  GET /v2/plan (POST, the one allowed) -> plan.json (436092B)
py  : /opt/homebrew/bin/python3.12 (3.12.15)
```

Key rows this pass: stations `53 — src:waqi+dpcc
feeds:{waqi:ok,dpcc:ok} aqi:53` (**accepted under the new 52–54 range —
would have flagged under the old whitelist**) · LOO `8.8 / 0.2 / 70`
artifact row matching wire + file · edges `1,070,459 / 903,058` · grid
484/1,600 · field age 71 s stale:false · fires 80/20 ×1.10 · plan 24
options · spread 33.3× (slowest/best 39.8×) · community 40 obs / 22
contributors / 1,028.5 µg all-time.

```
====================  FLAGS  ====================
  (none — all quoted numbers match live within their stated precision)
```

exit 0. The stations note now reads: "accepts: 53 now — 52–54 = 24 WAQI +
up-to-30 DPCC …; /aqi station_readings may sit ±2 off /health — each
endpoint ages instruments at different times."

## Regression / checks

- `bash -n` clean; heredoc parses under python3.12 (the file documents
  the ≥3.12 requirement; stock macOS 3.9 can't parse its f-strings —
  unchanged behavior).
- Sweep verified post-edit: `rg "46\.1|n=94|n_stations.*94|94 live"` over
  claim docs returns only claims-audit record rows, the bench-krige stamp,
  and judge-qa-v2's deliberate "earlier 46.1/n=94 was the pre-DPCC audit"
  historical note.
- `docs/api/REFERENCE.md` header drift-note updated so the doc doesn't
  silently mix 10-03 captures with the re-pinned calibration.

## What this does NOT fix

- Other drift rows in the card §9 (community 40/22, corridors 12/55,
  fires 80/20, skill 242 pairs, breath 836 µg) — stamped drift-class
  figures, not contradictions; the drift tables already carry ranges.
- Deploy lag itself (`aee635eb` vs HEAD) — same separate failure mode as
  before; the wart note stands.
- If the count drifts below 52 while both feeds stay ok, or a feed drops
  partially, the whitelist will flag — that IS a real surprise worth
  flagging; re-pin or widen only after understanding which.
