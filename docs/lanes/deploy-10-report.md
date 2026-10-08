# deploy-10 — server ship report

Shipped `base/v2` server tree to prod. Prod `585a7171` / task def `:214` →
`90766e25` / `:215`. Headline ship: **landing-v8** (`7eab286`, the full
landing overhaul) plus the **precision-audit** server fixes (`81ba1a2`).

## Deployed

- **commit** `90766e2` (HEAD of base/v2 at deploy time)
- **image** `185708268748.dkr.ecr.ap-south-1.amazonaws.com/alive108-api:90766e25`
  digest `sha256:813ab640f19417656dfb4375abc3c8e92cd01cd17e8e4c07b2473dfefc11f2d7`
- **task def** `arn:aws:ecs:ap-south-1:185708268748:task-definition/alive108:215`
- **service** alive108/alive108 ACTIVE 1/1, task `cbcf2232` ENI
  `172.31.22.219` registered+healthy in TG `alive108-tg`; prior target
  `172.31.31.105` deregistered. Rollout `COMPLETED`.
- **CodeBuild** `alive108-build:aa50d5c5-fca3-4a26-9359-f4e4990db32f`

## Server delta shipped (vs prod 585a7171)

Two commits touched `server/` (the rest of the 11-commit wave is
Mobile/docs only — `git diff --stat 585a7171..HEAD -- server/`):

| file | change |
|---|---|
| `server/landing.html` | +373/−119 — landing-v8: kriged field breathes edge-to-edge under the hero (`#fieldair` canvas on `/grid`), numeral anchored at hero foot (`#heroLive` provenance strip), `.top` made `position:sticky` (v7's `#toplive` was dead chrome), dose equation staggers via IO, `.choose` becomes a 235vh scroll-cranked `.film-gate` on real app frames, daybars + district chips accrue live |
| `server/airfield.py` | new `nearest_station_km()` — km to nearest NAMED live instrument (live feed first, snapshot cell's own build-time value when dark); `nearest_sample_km` anisotropic degree→km fix (`_KY`/`_KX`, E-W was overstated ~13% at 28.6°N) |
| `server/main.py` | `/aqi` emits `nearest_station_km` (new wire field) + `nearest_sample_km`, both `None`-guarded — `round(inf)` would emit JSON `Infinity` and parse-fail a cold-start poll whole |
| `server/exposure.py`, `server/alive_core_ref.py`, `server/core/src/field.cpp` | `segment_samples` carry fix ×3 impls — `frac`/`dist_m`/`seconds` now use accumulated `carry`, not the crossing leg `seg` (under-attributed dose on vertex-sparse geometry) |

## Pre-deploy gate

- Extracted the served inline `<script>` (lines 1040–2617, 1578 lines)
  and `node --check`'d it: **clean** — the f9ea5ae dead-page class
  (unescaped `'` in a JS string killed the whole script → dead boot
  overlay) is not present.
- Lane-side gates already green on this exact tree: precision-audit ran
  full pytest **1262p/5s**; landing-v8 ran inline-script check + local
  FCP/LCP ~64 ms + desktop/mobile proxy drives vs live prod data.
  (`server/.venv312` + `core/build312` don't exist on this box — no
  local suite re-run; the two lane reports cover the tree.)

## Live verification (all on http://65.2.28.40, build 90766e25)

| check | result |
|---|---|
| `GET /health` | `ok`, `build_sha=90766e25`, `engine=alive_core` (C++ rebuilt — carry fix in), field_age 135 s, `field_stale=false`, wind live |
| `GET /` | 200, TTFB 0.47 s, 131.0 kB; v8 DOM markers served: `id="heroZone"`, `id="fieldair"`, `id="heroLive"`, `class="film-gate"`, 2× `position:sticky` |
| **Boot (f9ea5ae class)** | **PASS — page boots**: browser drive shows numeral **49.1 µg/m³** painted (PM2.5 · SATISFACTORY), live provenance strips (`53 STATIONS LIVE · MAP 4 MIN FRESH · WIND 7 KM/H` — the age ticker incremented during the drive), footer `BUILD 90766e25` painted by JS from `/health` |
| Sticky chrome | PASS — scrolled page shows `PM2.5 49.1 µg/m³ · MAP 4 MIN FRESH` inside the sticky top bar (v7's dead toplive now follows) |
| Daybars + district chips | PASS — hourly daybar accrued (`NOW −57% VS THE TYPICAL HOUR`); 4 district chips live: SW Delhi 142 / Rohtak 129 / Gurugram 116 / Jhajjar 168 |
| FCP | sane — TTFB 0.47 s, no blocking external resources (data-URI favicon, system fonts, 2 `decoding=async` PNGs); inline script only |
| `GET /city` | 200, 0.93 s, 89.1 kB |
| `GET /community` | 200 ×2 — JSON on `Accept: */*` (app contract), HTML on `text/html` |
| `GET /admin` | 200, 1.16 s, 167 kB |
| `GET /aqi?lat=28.6139&lon=77.2090` | pm25 64.5, us_aqi 152, `nearest_sample_km` 1.7, **`nearest_station_km` 1.7 — new field live on the wire** |
| `POST /v2/plan` CP→IGI | 24 options, no error |
| `GET /v2/search?q=connaught` | 5 results, `_t1_pos` count 0 (deploy-9 fix holding) |
| CloudWatch alarms | `alive108-field-age`, `alive108-field-emitter-dead`, `alive108-target-down` all `OK` |
| ECS/TG | rollout `COMPLETED` on `:215`; new ENI `172.31.22.219` healthy, stale `172.31.31.105` pruned |

## Rollback

`./scripts/deploy.sh rollback 585a7171` re-points the service at the
prior image (still in ECR). Task def `:214` remains registered; older
`:213` (`ea5dfb96`) and `:210` also remain registered.

## Box notes for future deploy lanes

- No aws CLI / docker — `~/awsenv` recreated this session:
  `/opt/homebrew/bin/python3.12 -m venv ~/awsenv &&
  ~/awsenv/bin/pip install awscli` (aws-cli 1.46.1).
- Secrets (AWS_*/CF_*) inject into **one-shot exec calls only** —
  persistent `shell_id` shells start without them. Long deploys: launch
  one-shot, let it background, poll `get_output` (env is captured at
  process start, so polling keeps working).
- `aws cloudwatch` etc. need `--region ap-south-1` explicitly
  (`AWS_REGION` is not among the injected secrets; deploy.sh sets its
  own `AWS_DEFAULT_REGION`).
- `server/.venv312` + `core/build312` absent on this box — local pytest
  needs a fresh venv + pybind build; lane-report gates covered this tree.
