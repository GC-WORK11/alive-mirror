# Lane report — deploy #5: landing-v7 (+ privacy-f1) to prod

**Date:** 2026-10-07 ~13:50–14:40 UTC. **Lane:** deploy + verify (deploys
permitted; everything else GET-only — the one sanctioned `/v2/plan` POST
inside `tools/warm_task.py`).

## What shipped

**Two CodeBuild rolls** — the prompt's warned-for case fired: privacy-f1
(`af653e5`, k≥3 gate on `contributors_detail` day-rows) landed on base/v2
*while roll 1 was in flight*. `git log c86074ff..HEAD --oneline -- server/`
at deploy-start showed only `ffddab9` + `54a296e`; the post-roll re-pull
caught `af653e5` with a `server/main.py` delta → redeployed immediately.

| | |
|---|---|
| **Deployed image (final)** | `alive108-api:7c68c8bc` (base/v2 HEAD incl. privacy-f1 + docs) |
| **Roll 1 (superseded)** | `alive108-api:ffddab93` — landing-v7 only; task def `alive108:207`, task IP `172.31.24.110`, STABLE 14:0x UTC, replaced ~15 min later |
| **Roll 2 (live)** | `alive108-api:7c68c8bc` — task def `alive108:208`, task `f1e3bd84f94747738386b34f5e8324d7`, ENI `eni-0afa8ae0c71d26a68` → `172.31.26.129`; TG re-registered, STABLE |
| **Previous prod / rollback target** | `c86074ff` — confirmed via `/health` `build_sha` pre-deploy |
| **Pipeline** | CodeBuild ×2 (`…:f7ac0cba`, `…:17c3c370`), S3 src.zip of `git archive HEAD:server`, aws-cli/1.46.1 fresh `~/.aws-venv` (no aws CLI/docker on box) — ~7 min per roll |
| **server/ diff shipped** | `ffddab9` landing-v7 (landing.html, 4 choose-strip static routes, hero webp/png swap) + `54a296e` (`/v2-light.json` route + parity test — the offline-pack http style_url fix) + `af653e5` (k≥3 gate on contributor day-rows) |

## Landing-v7 surface — live-verified (real browser, Chrome 154 CDP)

| Check | Result | Evidence |
|---|---|---|
| Hero = dose-ledger home shot | ✓ | `<img alt="the app on android: you've breathed 17 µg today — 8% of the daily budget, good band…">` loading `currentSrc=/app-hero-472.webp` (srcset 472/708 webp + 708 png fallback); DOM probe, not markup-read |
| "The same field, asked to choose" film-strip | ✓ | Section renders 896×432 in viewport; `<h2>` text + verdict pill `∅ the cleanest way there`; figcaption trio `every way, priced / the verdict pins itself / the cleanest goes bold` — three real frames of one India Gate run (candidates → pill pins → winner bold) |
| Strip routes serve | ✓ | `/app-choose-strip-848.webp` 200 30,974 B · `-1360.webp` 200 57,764 B · `-1520.webp` 200 62,048 B · `-848.png` 200 302,412 B · `/v2-light.json` 200 94,254 B `application/json` |
| Page wire ≤ ~206 KB | ✓ | HTML 118,614 B + hero-472.webp 19,216 B ≈ **138 KB first paint**; even adding the 848 strip (30,974 B) the whole landing wire is ~149 KB |
| Live number paints | ✓ | `hnumV` = **47.2** µg/m³ "pm2.5 · satisfactory" painted by `/v2/city` → `countIn` (boot strip self-unmounted post-intro, `bootInDom:false`); page shows `54 stations live · map 6 min fresh · usual 44 µg/m³ · next 11 h forecast 57.7–70.4` |
| Inline scripts parse | ✓ | `scripts/check_inline_scripts.py` (real-HTML-parser extractor → `node --check`) run **against the served bytes** `/tmp/landing2.html`: 1 block, parse clean — the f9ea5ae trap does not exist |
| Build tag | `build 7c68c8bc` | in-page `#buildTag` painted from `/health` (first roll showed `ffddab93`) |

## Standard sweep (live-verified on `7c68c8bc`)

| Check | Result | Evidence |
|---|---|---|
| `/health` `build_sha` | `7c68c8bc` == deployed tag ✓ | `ok:true`, `engine:alive_core`, `field_age_s:138`, stations 54 |
| `/admin` | gate card, not board ✓ | 200 "engine room" sign-in — `type="password"`, `placeholder="operator token"`; zero admin data served unauthenticated; `/admin/api/*` unauth → 401/404 |
| `/v2/city` `why.cause_note` | populated ✓ | `"16 fires in the Punjab–Haryana belt — the wind isn't carrying it this way right now · air barely mixing — ventilation 319 m²/s vs ~3,000 typical"` (nested under `why` — top-level null by design) |
| `/community` | live aggregates ✓ | 200 JSON `obs_total:44 · contributors:24 · avoided_ug_all:1278.9` + top_corridors (k≥3 cells, `avg_dose_basis:"est. from donated trips"`) |
| `/v2/usage` guest | **401** ✓ | unauthenticated rejected |
| Served-vs-HEAD | landing.html **byte-identical** | sha256 `git show HEAD:server/landing.html` == served bytes (admin.html likewise) |

## Privacy-f1 (`af653e5`) — live-verified

`/admin/api` (Bearer via `alive108/admin-token` from Secrets Manager, ops
account) on `7c68c8bc` returns the NEW contract:
`contributors: [4 day-rows]` each `contributors ≥3` (sample: day 2026-10-07,
5 trips, 10.1 km, **3** devices) + `contributors_suppressed:{day_rows:0}` +
`contributors_days_tracked:4`. The suppressed-block shape exists — sub-k
day-rows can no longer be emitted. (0 suppressed because all 4 tracked
UTC days currently have ≥3 devices; suppression behaviour covered by the
lane's tests, 1244 passed.)

## Warm

`tools/warm_task.py` on `7c68c8bc` → **WARM**: "priced engine serving
after 4 s · transit rows on 1 plan OD(s)". `/v2/plan` CP→IndiaGate 1.7 s,
23 rows (15 engine + 1 transit); every probe ok incl. `/v2/skill` 0.6 s,
`/v2/archive` 3.1 s, `/tiles/health` 22.7 MB z[0,14].

## Mid/post-deploy drift

`d9482b8` (watchdog log) + `7c68c8b` (offline-pack report) landed during
rolls — docs-only, zero `server/` delta vs the deployed image
(`git log 7c68c8b..HEAD -- server/` = 0).

## Rollback note

```bash
./scripts/deploy.sh rollback c86074ff   # prod sha before this lane — tag immutable in ECR
```

Verified working earlier this window: roll 1 (`ffddab93`) itself served
as a clean intermediate — rollback swaps the task-def image pin + TG
target, no rebuild.
