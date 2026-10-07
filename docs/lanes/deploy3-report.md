# Lane report — deploy #3: landing-perf to prod

**Date:** 2026-10-07 ~11:40–11:55 UTC. **Lane:** deploy + verify (deploys
permitted; everything else GET-only — the one sanctioned `/v2/plan` POST
inside `tools/warm_task.py`).

## What shipped

One CodeBuild roll. `git log 698cf808..HEAD -- server/` audit before deploy:
**only `47d7bff` touches the image** — landing-perf (landing.html WebP hero +
preload + `api()` in-flight dedup + idle-deferred below-fold feeds +
`/v2/city` 60 s payload cache + cache-control headers + overlay count-in;
`server/main.py`, `server/v2/city.py`, `server/v2/store.py`,
`server/landing.html`, 3 new statics, `test_landing_serve.py`). Other commits
on `base/v2` since prod (`3439184`, `72a3d9a`, `06085a9`, `43913dc`) are
docs/Mobile — `43913dc` is iOS-only, still rides the same image sha.

| | |
|---|---|
| **Deployed image** | `alive108-api:43913dc0` (base/v2 HEAD at deploy time; ECR tag = `BUILD_SHA` env) |
| **Previous prod / rollback target** | `698cf808` |
| **Task def** | `alive108:205` (cpu 1024 / mem 3072, osrm sidecar) |
| **Task** | `ae4318700b9d475bba3ae0976e883f5e` |
| **Task ENI → IP** | `eni-02f710ea8eeec395d` → `172.31.28.112` |
| **TG** | `alive108-tg` — new IP registered; old `172.31.20.254` deregistered; STABLE |
| **Pipeline** | `BUILD_MODE=auto` → CodeBuild `alive108-build:56924ea7-d8b7-4748-9983-858a4cd87170` (S3 src.zip of `git archive HEAD:server`, aws-cli/1.46.1 fresh `~/.aws-venv`, no docker on box) — ~9 min end-to-end |
| **Mid-deploy drift** | `a1be7e7` + `2e07f60` landed during rollout — **docs-only, zero `server/` delta**, no redeploy needed |

## Perf claims — measured on prod `43913dc0`

| Claim | Before (`698cf808`) | After (prod-measured) | Verdict |
|---|---|---|---|
| Hero shot bytes | `app-hero.png` 530,914 B | `app-hero-708.webp` 42,890 B served `image/webp`; `472.webp` 26,436 B; `708.png` 255,181 B fallback exists | **−91.9 %** ✓ ("−92%" claim holds) |
| Landing doc + hero wire (uncompressed) | ~645 KB (114,108 html + 530,914 png) | **158.7 KB** (115,803 html + 42,890 webp) | **−75 %** ✓ (report's "~128 KB" was html-estimate-based; real doc grew +1.7 KB, still −75 %) |
| Landing doc wire (gzip) | — | **38,465 B** (`Accept-Encoding: gzip` honored) | total first-view gzip wire ≈ 81 KB |
| `/v2/city` cold vs warm | 3,807 ms cold (lane's local measure) | cold **3.10 s** (`cached_s: 0.0` — my request rebuilt) → warm **0.47 s** from this box (~450 ms is my RTT to ap-south-1; server-side warm is ms-level) | cache works on prod ✓ |
| Cache disclosure | — | `cached_s` rises 10.6→11.2→20.3→20.8 across hits; `0.0` on the rebuilding response; byte-identical 10,714 B payload while warm | ✓ |
| `cache-control` | none | `/` → `public, max-age=300`; `/ncr.geojson`, `/delhi_subdistricts.geojson`, hero variants → `public, max-age=3600` | ✓ |
| Boot overlay / live number | (f9ea5ae trap = parse-fail dead boot) | served inline script **parses clean** — `scripts/check_inline_scripts.py` on the downloaded page: `node --check` OK (1 advisory: `<script` inside an HTML comment, prose) | ✓ screenshot: overlay mid-fade + `35.1 µg/m³` painted — `deploy3-shots/boot-overlay-fade.png`, `landing-live-number.png` |
| Below-fold defer | 11 requests at parse | `loadDistricts/tlInit/dayStrip/skillLine/whyTonight` on `requestIdleCallback`; render shows deferred feeds painted live (district chips 95/91/79/78, day strip "−39 % vs typical") | ✓ `hero-shot-webp.png` |
| Footer build pin | `698cf808` | **`43913dc0`** rendered in page footer | ✓ `footer-build-sha.png` |

## Standard sweep (all live-verified on `43913dc0`)

| Check | Result | Evidence |
|---|---|---|
| `/health` `build_sha` | `43913dc0` == deployed tag ✓ | `ok:true`, routing loaded (1,070,459 edges / 903,058 priced), `field_stale:false`, engine `alive_core`, stations 52 (waqi+dpcc), fires 44 |
| `/admin` | gate card, not board ✓ | 200; login card + `v2/admin/login` in served HTML |
| `/city` `why.cause_note` tile | populated ✓ | `"12 fires in the Punjab–Haryana belt — the wind isn't carrying it this way right now"`; `cause_note_fields` complete (belt_fires 12, carrying false, wind 267°/12.8 km/h); `.whyline`/`#grapline` markup in served HTML (nested under `why` — top level null by design) |
| `/community` | live both contracts ✓ | `Accept: */*` → 200 `application/json` 1,484 B (`obs_total:44`, `km_today:31.4`) — app contract intact; `Accept: text/html` → 200 HTML 21,108 B |
| `/v2/usage` guest | **401** ✓ | unauthenticated rejected |
| Served-vs-HEAD | `/`, `/city`, `/admin` **byte-identical** to `HEAD` | sha256 match `git show HEAD:server/*.html` |
| `tools/warm_task.py` | **WARM** ✓ | "priced engine serving after 4 s · transit rows on 1 plan OD(s)"; `/v2/plan` 2.2 s 24 rows w/ 15 engine + 2 transit; every probe ok incl. `/tiles/health` 22.7 MB z[0,14] |

## Rollback note

```bash
./scripts/deploy.sh rollback 698cf808   # previous prod — tag immutable in ECR
```

`698cf808` is what `/health` reported pre-deploy (deploy #2's build); rollback
redeploys the identical image through the same task-def + NLB pipeline minus
the build.

## Drift / caveats

- **`/v2/city` warm latency** measured from this box is dominated by ~450 ms
  RTT — the server-side claim (1–3 ms) isn't observable from here; what IS
  verified is the mechanism: hits return byte-identical payloads with rising
  `cached_s`, misses cost ~2.6 s of server CPU and disclose `cached_s: 0.0`.
- **The 60 s cache races the field**: `cached_s` observed resetting ~20–60 s —
  the cache key includes field state + `TRIPS._rev`, so any field rebuild or
  donation busts it early. Working as designed; don't expect the TTL to be
  the binding constraint.
- **`ncr_districts.geojson` (no `.` alias) is 404 on prod** — pre-existing,
  not from this change; landing fetches `/ncr.geojson` +
  `/delhi_subdistricts.geojson` which serve 200 + 3600 s cache.
- New `cached_s` field is contracted (`Bridge/contract.ts`,
  `Mobile/src/api/city.ts`) — app ignores it harmlessly.
