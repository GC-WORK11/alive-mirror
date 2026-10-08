# deploy-25 — v15 landing to prod

- **Shipped:** `3c9392d` → image `alive108-api:3c9392d7`, task def `alive108:232`, STABLE on http://65.2.28.40 (CodeBuild path; macOS lane, no local docker — fresh `~/.aws-venv` awscli provisioned this box)
- **Rollback target:** `c5ba61c0` / `:231` (`./scripts/deploy.sh rollback c5ba61c0`)
- **What's flying:** `3c9392d` v15 landing — tighter vertical components (col padding clamp 34-72px → 24-52px), districts as 3-col ruled table (`.dscroll` → `grid-template-columns:repeat(3,1fr)` 10-row column-flow @≥1024, `.dchip` slim 20px/1fr/auto rows, boundary thumbs hidden), smaller `.phone` (292px), slimmer `.eq/.jrow/.door/.foot` rhythm. Riding: `96df587` routes-delta server half (`server/v2/plan.py` +116 — per-option `delta` field + tests), Mobile e2e-residual `ec2ed08` + APK lanes (not in image), docs.

## Pre-flight — CLEAN (third clean sweep in a row)

- **Statics sweep:** landing.html refs → `/hero-delhi-smog.webp` (route main.py:2055), `/ios-{choose-priced,dose}.{webp,png}` + `/ios-feat-{trips,week}.webp` (loop routes 2005-2014), `/delhi_subdistricts.geojson` (2068), `/ncr.geojson` (1832) — all 6 static files present in server/static/, all handlers registered. `git diff c5ba61c0..3c9392d -- server/landing.html` = **+31 CSS-only lines, zero new asset references** — the trap did not fire this ship.
- **v2 router:** `/v2/{city,districts,skill,why,plan,stays,playtime}` all in `server/v2/*.py` router table, included at main.py:2250.
- **admin.html:** zero diff vs :231 — analytics page untouched.

## Verify gates — all PASS on prod

| gate | result |
|---|---|
| (a) `/` renders v15 | 200 — 120,667 B. Markers: `hero-delhi-smog.webp` ×2, "Delhi's air, counted.", rail `.top{position:fixed;left:0;width:216px}` + `.stack{margin-left:216px}`, `repeat(3,1fr)` grid on `.dscroll`. Rendered-eyeball (shots below): hero + rail + live statusline "pm2.5 89.9 µg/m³ · map 4 min fresh", tighter 006/007 sections, **3-col district table live** (South West Delhi 286 / Nuh 215 / Hapur 178 aqi, numbered, worst-first). Zero junk strings (no lane/commit-paste leak) |
| (b) `/health` | 200 — `build_sha: 3c9392d7`, `engine: alive_core` |
| (c) `/grid?cells=40` | 200 — 363,208 B GeoJSON, 1600 features, 1.48 s |
| (d) `/v2/city` | 200 — live pm25 + why line ("air barely moving — day's pollution sitting over the city", 18 Punjab-Haryana fires cited) |
| (d) `/v2/stays?near=28.6315,77.2167&k=1` | 200 — k=1 → "The Hotel W" 0.2 km, pm25_now 82.6, window_mean_ug 97.7, scored_on forecast — real gradient, non-sparse |
| (d) `/v2/playtime?near=28.6315,77.2167` | 200 — 24h rolling horizon, IST stamps, model disclosure (CAMS × stagnation, parcel-bias anchored) |
| (e) statics | hero-delhi-smog / ios-feat-trips / ios-feat-week / ios-choose-priced.{webp,png} / ios-dose.{webp,png} / ios-choose-bold.webp / ios-choose-verdict.webp — all 200, correct content-types |
| (f) admin mount | `<mount>` 200, 43,278 B — `counter(sec` margin-index present = deploy-23 analytics page NOT regressed; `/admin` honest 404 |
| (g) service | ACTIVE on `:232`; new task ENI `172.31.27.53` registered healthy on TG (old `172.31.30.20` deregistered); 3× /health repeat 200 @ ~0.47 s; `/city` + `/community` 200 |

Shots: `deploy-25-shots/` — top-hero.png (rail + hero + headline), mid-sections-006-007.png (eq arithmetic + live field map), districts-3col.png (the v15 signature table).

New-rev proof: taskdef `:231`→`:232`, image `c5ba61c0`→`3c9392d7`, TG cutover `172.31.30.20`→`172.31.27.53`, `/health` build_sha flip.
