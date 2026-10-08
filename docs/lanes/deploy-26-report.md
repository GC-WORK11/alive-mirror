# deploy-26 — ios-shot recaptures + new feat frames to prod

- **Shipped:** `90bc055` → image `alive108-api:90bc055d`, task def `alive108:233`, STABLE on http://65.2.28.40 (CodeBuild path; macOS lane, no local docker — fresh `/tmp/alive-venv312` awscli provisioned this box)
- **Rollback target:** `c5ba61c0` / `:231` (`./scripts/deploy.sh rollback c5ba61c0`) — per lane brief. Nearest prior tag is `3c9392d7`/`:232` (v15 live) — `c5ba61c0` is the brief's named rollback image.
- **What's flying:** `1e41c9d` ios-shot content — recaptured `ios-choose-priced` (68,494→185,272 B webp), `ios-dose` (41,004→52,474), `ios-feat-trips` (21,368→57,316), `ios-feat-week` (32,794→48,736) at better moments + **three NEW frames** `ios-feat-{stays,playtime,airmap}.webp` (195,806 / 197,058 / 193,302 B) + their FileResponse routes (main.py:2013-2015, webp-only loop extended from 2→5 names). `90bc055` air-gate docs (mobile-only, not in image). `landing.html` **unchanged** — prod `/` byte-identical to HEAD (120,667 B).
- **Note:** `curl -sI` on the shot routes returns 405 — FileResponse handlers are registered GET-only, HEAD is not auto-allowed. Byte-size gate (d) run with GET `%{size_download}` instead.

## Pre-flight — CLEAN

- **Statics sweep:** landing.html + admin.html same-origin refs (14) → all assets present in `server/static/`, all handlers registered. Loop-route table (main.py:2005-2015): `ios-{choose-priced,choose-verdict,choose-bold,dose}.{webp,png}` + `ios-feat-{trips,week,stays,playtime,airmap}.webp`.
- **TestClient sweep (fresh /tmp venv, import main OK):** 20 GETs all expected — `/` 200 (120,667 B), `/health` 200, `/city` `/community` 200, all 9 ios shots 200, `/hero-delhi-smog.webp` 200, `/v2/{city,skill,why,stays,playtime}` 200, `/admin` honest 404. **Byte parity: served == disk on all 5 recaptured/new shots.**
- **v2 router:** stays/playtime in `server/v2/explore.py` router, `_v2_router` include at main.py:2250.

## Verify gates — all PASS on prod

| gate | result |
|---|---|
| (a) `/` renders v15 | 200 — 120,667 B byte-identical to HEAD. Markers: `repeat(3,1fr)`, "Delhi's air, counted.", rail `.top`/`margin-left:216px` |
| (b) `/health` | 200 — `build_sha: 90bc055d`, `engine: alive_core`, field fresh (age 118 s) |
| (c) `/v2/city` | 200 |
| (c) `/v2/stays?near=28.6315,77.2167&k=1` | 200 — "The Hotel W" 0.2 km, pm25_now 79.5, window_mean 96.3, scored_on next24h, `sparse:false`, 15,977 lodging rows |
| (c) `/v2/playtime?near=28.6315,77.2167` | 200 — rolling 24 h horizon, IST stamps, CAMS × stagnation model disclosure |
| (d) `ios-feat-trips.webp` | 200 — **57,316 B** (was 21,368 — ~57 KB ✓) |
| (d) `ios-choose-priced.webp` | 200 — **185,272 B** (was 68,494 — ~185 KB ✓) |
| (d) `ios-feat-stays.webp` NEW | 200 — **195,806 B** |
| (d) `ios-feat-playtime.webp` NEW | 200 — **197,058 B** |
| (d) `ios-feat-airmap.webp` NEW | 200 — **193,302 B** |
| (d) recaptured | `ios-dose.webp` 52,474 B · `ios-feat-week.webp` 48,736 B — all `image/webp` |
| (e) admin | `<mount>/` 200 (43,278 B), `/admin` honest 404 |
| (f) service | `alive108:233` PRIMARY 1/1; new ENI `172.31.23.189` healthy on TG; old `172.31.27.53` draining |

New-rev proof: taskdef `:232`→`:233`, image `3c9392d7`→`90bc055d`, TG cutover `172.31.27.53`→`172.31.23.189`, `/health` build_sha flip.
