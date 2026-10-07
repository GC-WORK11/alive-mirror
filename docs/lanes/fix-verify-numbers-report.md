# fix-verify-numbers — un-pin the harness from the 24-WAQI world

Lane: `fix-verify-numbers`. Pass **2026-10-07 ~01:05 UTC** (≈06:35 IST).
Trigger: truth-audit (`59498d2`) verdict — "the demo-morning liar is
`scripts/verify_numbers.sh` itself": its matchers pinned the 24-WAQI world
and would false-flag correct docs at the T-45 integrity pass.

Scope kept tight: `scripts/verify_numbers.sh` only, plus this report and the
handoff tail. No doc text touched — the docs under audit were already right.

## What was stale → what now matches

| matcher / check | before | now |
|---|---|---|
| stations row + surf pattern | `stations live (WAQI)` matched only `24 (live )?(WAQI\|instruments\|stations)` — invisible to every current "54 / 24 WAQI + 30 DPCC / waqi+dpcc" claim | `stations live (instruments)` prints count + `source` + `feeds` + `/aqi.field.station_readings`; pattern covers the 54 world **and** the 24-only phrasing |
| `/health.sources.stations.count` live check | none — count was printed, never checked | flag on: missing `sources.stations`, `count` ∉ {54, 24}, `count=54` with `source` lacking `dpcc`, `/aqi` readings ≠ count. `count=24` = accepted degrade → info note, not a flag (DPCC staleness guard drops all 30 ~90 min after a site stall). `feeds` missing `dpcc` while count=54 → info note (truth-audit §1 transient wart, self-heals) |
| stamped reads treated as claims | `×1.27`, `~70 fires`, `24 stations` inside dated pass entries flagged against live | stamped lines can never contradict live: `*[ … ]*` pass blocks (demo-day's convention) detected by span, `handoff.md`/`HANDOFF.md` are declared snapshots (NUMBERS §4) and skipped wholesale, elsewhere a ±4-line window looks for pass/deploy/verified/date/probe markers |
| gazetteer `123,934` | flagged on *any* mention — including handoff's "the server-side copy is 123,934" (already says which) | flags only when the line doesn't qualify it (`server/copy/bundle/mobile/on-device/fallback`); `124,334` still always wrong |
| `'~35×'` spread | flagged when \|live − 35\| > 2 — would fire on a fine read (33× this run) | flags only when live spread exits the recorded 31–45× band |
| fires count | `~7[0-9]`-era pin, ±10 vs live — fires moved 67→80 inside the audit | any quoted `N fires`/`fires N` checked; flag needs unstamped **and** \|N − live\| > 25 (documented daily swing ~30→90) |
| edges `1,070,459` / `903,058` | only flagged live MISSING | also flags the figure vanishing from every surface |
| holdout MAE | nothing | new artifact row re-derives former-GAP/all-30 (`10.5 / 6.2`) from `docs/lanes/holdout-reverify-report.md`; **bare-6.2 flag**: `6.2` in an MAE/agreement/holdout context with no range framing (`→`, `–`, `single-digit`, `low-teens`, `worst`, citation/stamp in ±2 lines) → flag with "single-digit to low-teens µg" phrasing |

## Green run — `bash scripts/verify_numbers.sh` vs prod `bc8f82c4`

Fetches (all GET + the script's one sanctioned `POST /v2/plan`):

```
  GET /health -> health.json (908B)
  GET /aqi?lat=28.6315&lon=77.2167 -> aqi.json (1894B)
  GET /grid?h=0 -> grid.json (125958B)
  GET /grid?h=0&cells=40 -> grid40.json (362786B)
  GET /fires -> fires.json (21563B)
  GET /v2/city -> city.json (6283B)
  GET /v2/day?lat=28.6315&lon=77.2167 -> day.json (5088B)
  GET /v2/reach (walk@25 / walk@50 / car@25) -> 157K / 472K / 3.6M
  GET /v2/districts -> districts.json (7095B)
  GET /community -> community.json (1324B)
  GET /v2/outlook -> outlook.json (4621B)
  GET /depart CP→GG -> depart.json (3432B)
  GET /v2/plan (POST, the one allowed) -> plan.json (433350B)
py  : /opt/homebrew/bin/python3.12 (3.12.15)
```

Figure table, live reads this pass: `build_sha bc8f82c4` · edges
`1,070,459 / 819,846` meta, `903,058` priced on `/health` · grid 484/1,600 ·
field age 725 s, stale:false · **stations `54 — src:waqi+dpcc
feeds:{waqi:ok,dpcc:ok} aqi:54`** · model samples 102 · fires 80/20 ·
smoke ×1.10 · PM2.5@CP 72.3/65.7 · US AQI 156 · plan 24 options, took 365 ms ·
dose ladder car 8.5 → walk 281.9 · spread **33.2×** (slowest/best 39.8×) ·
annualized 141 mg vs 4.2 mg · day mean 74.6 · depart 23.0→43.0 (1.9×) ·
reach 3,961/175.5 km · 11,779/643.5 km · 916,308/79,947 km partial ·
corridors 12/54 · community 22/14/725.9 · breath 865 µg (2.74 cig) ·
field_validation 3,550/85/95.4 · LOO 46.1/+0.3/n=94 · graph blob
3,428/107,193/230 · gazetteer 124,311/123,934 · history 125 ·
holdout artifact 10.5 / 6.2.

```
====================  FLAGS  ====================
  (none — all quoted numbers match live within their stated precision)
```

exit 0.

## Degrade-mode fixture tests (synthetic `/health`, no prod writes)

- `count:24, source:waqi, feeds:{waqi:ok, dpcc:unavailable}` → no flag;
  info line: "stations in DEGRADE mode (24 WAQI-only — DPCC stale-dropped).
  Docs quoting 54 stay honest…".
- `count:54, feeds:{waqi:ok}` (the mid-refresh wart) → info line only.
- `count:30` → `⚠ stations.count — not an accepted state`.

## Regression

- `bash -n` + `python3.12 -m compile` of the heredoc: clean.
- No test in `server/tests` (or anywhere) references `verify_numbers.sh` —
  it is invoked by hand and by the T-45 checklist; nothing else to run.
- matcher-by-matcher eyeball of the WHERE-QUOTED section: every listed
  surface is a genuine claim site for that figure; stamped blocks list
  under the figure but never flag.

## What this does NOT fix

- Deploy lag (prod `bc8f82c4` vs HEAD) — separate failure mode; the wart
  note already says "say the ECR tag, not the stamp".
- `mid(None)` class guards were already in place; the py≥3.12 requirement
  is documented in NUMBERS.md/demo-day (this box: homebrew 3.12).
- If T-45 runs while DPCC is stale-dropped, expect the DEGRADE info line —
  that is the honest state, not a script fault.
