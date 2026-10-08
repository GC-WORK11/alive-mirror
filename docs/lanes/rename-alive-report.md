# Lane report — rename to "Alive" (rebrand, drop the 108)

Owner's call, verbatim: "the name of the app is now only Alive, not 108. Remove
108 from every place. The app name is Alive. No 108."

Scope rule applied: strip/rework `108` on every user-visible surface; keep infra
names, bundle ids, file names, repo/domain strings, and plain numbers.

## What was swept

### Mobile (Expo app)

- `app.json` — `"name"` → `Alive`; `locationWhenInUsePermission` copy → `Alive uses…`.
- `src/i18n/strings.ts` — 5 brand mentions in `en` + `hi` (share body/line,
  settings rate-cta, plan-outside body): `ALive-108`/`ALive·108`/`alive-108` →
  `Alive` in both languages, en+hi parity kept.
- `src/components/shell/Sidebar.tsx` — wordmark `ALIVE<Text>-108</Text>` → `ALIVE`
  (removed the accent-colored `-108` span).
- `android/app/src/main/res/values/strings.xml` — `app_name` → `Alive`.
- `ios/ALive108/Info.plist` — `CFBundleDisplayName` → `Alive`;
  `NSLocationWhenInUseUsageDescription` → `Alive uses your position…`.
- `src/map/v2-dark.json` `name`, `src/map/style.ts` raster-fallback `name` →
  `Alive v2 …`.
- Comment/wordmark sweep across `src/**`, `metro.config.js`, `assets/map/*.svg`,
  `src/{store,nav,api,offline}/test-runner.mjs`, `SettingsScreen.tsx`,
  `SOURCES.md`, `ui.tsx`, `a11y/index.ts` — brand strings → `Alive`.

### server/ (FastAPI + served HTML)

- `landing.html` — `<title>` + `og:title` → `Alive — a personal dosimeter for
  Delhi air`; aria-label, boot strip (`bt-top`), wordmark `ALIVE<i>·</i>108` →
  `ALIVE`, footer `alive — delhi ncr`.
- `city.html` — title/og → `Alive — Delhi NCR air…`; wordmark; body `<b>Alive</b>`.
- `community.html` — title/og → `Alive — everyone's trips, merged`; wordmark;
  footer.
- `admin.html` (engine room) — title/og → `Alive · engine room`; aria-label;
  boot strip; 2× `mark` divs; footer.
- `main.py` — module docstring; `FastAPI(title="Alive API")`; internal UA →
  `alive/0.1 (hackathon)`.
- `tiles.py` — tilejson `name` → `Alive Delhi NCR (OpenMapTiles schema)`.
- `admin_agg.py` — served `"service"` field → `alive admin aggregates`.
- Outbound User-Agent strings → `alive-*` or `alive/N.N` form across
  `airindex.py`, `location_client.py`, `ingest_cpcb/openaq/waqi.py`,
  `routing_local.py`, `transit_rt.py`, `transit_real.py`, `iitm_probe.py`,
  `fires.py`, `v2/geo.py`.
- `test_api.py` — engine-room assertion updated to match the new markup.
- Docstrings/comments → `Alive` in `observability.py`, `exposure.py`,
  `middleware.py`, `alive_core_ref.py`, `v2/*`, `core/include/alive/*.hpp`,
  `core/src/*.cpp` header comments, `core/bindings.cpp` docstring,
  `.env.example`, `Dockerfile`, `buildspec.yml`, `pyproject.toml` description.

### scripts/ + tools/

- `scripts/video/cards/{title,end,cold,close}.html` — rendered video-card
  wordmark `ALIVE<i>·</i>108` → `ALIVE` (these produce user-facing demo frames).
- `scripts/geo/config-openmaptiles.json` — tilejson name → same as tiles.py.
- Comment/echo headers → `Alive` in a11y_audit, android-cloud-proof,
  build_mobile_gaz, build_corpus, public-repo, release_prep, deploy.sh,
  gen_api_docs, verify_numbers, video/lib.sh, video/cdp_rec.py, geo/common.sh,
  load_v2.py, flip_waqi_token, audit_route_quality, firstopen/, tools/*.

### docs + root files

- ~50 files under `docs/` (plan, api, release, submission, video, design,
  builder-center notes) + `README.md`, `PRIVACY.md`, `SECURITY.md`,
  `docs/api/openapi.json` (`"title": "Alive API"`), `docs/api/REFERENCE.md`,
  `LICENSE` — brand forms → `Alive`. Repo-name strings `Delhi-Air-108` left as-is.

## Intentionally left (not user-visible / breaking)

- **AWS/infra names** — `infra/provision.sh` all `Project=ALive-108` tags,
  `DASH_NAME`, dashboard name, SG description in `deploy.sh`, secret names,
  `infra/dashboard.json`, `infra/schedules/*.json` — renaming deployed
  resources would break them.
- **Identifiers** — `pyproject.toml` package `name = "alive108-api"`,
  `docker-compose` image `alive108-api:dev`, `server/alive108_apis.rest`/
  `alive108-apis.rest` file names, `ios/ALive108/` dir + scheme/target,
  `Mobile/android/...` package dirs — ids, not labels.
- **Repo/domain strings** — `github.com/<owner>/Delhi-Air-108` links
  (3 hits on landing: 2× releases, 1× blob), `alive108` in `SECURITY.md`
  contact placeholder, `alive-delhi-air` in the WAQI UA.
- **Numbers** — seeds, coordinates (`77.1080`), SVG path data, `1080` video
  height, `landing.html` line-count render (`opts.length`/`took_ms`), wikidata
  Q-ids, corpus/bench stats.
- **git history** — untouched.

## Verification

- `python3 scripts/check_inline_scripts.py` — OK, 4 blocks parse clean.
- `cd Mobile && npx tsc --noEmit` — clean.
- `node src/{store,nav,api,offline}/test-runner.mjs` — all suites pass
  (offline runner: 16/16).
- `npx expo lint` — clean.
- Local server boot (`uvicorn main:app` on :8108, venv py3.12): `/`, `/city`,
  `/community`, `/a-AFiVSpmZ1Oc4YhaaQyhRie5yqnlKV_qs` all serve `Alive`
  titles, og tags, wordmarks, footers — zero `108` outside the 3 GitHub
  repo links. `/openapi.json` → `"Alive API"`.
- `rg -i '108'` residual audit — remaining hits are repo URLs, AWS resource
  names/tags, seeds/coords/data, and file names only.
