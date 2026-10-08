# Docker notes — Alive API image

## Build / run

```bash
# canonical build — context MUST be server/ (deploy.sh + CodeBuild both
# package server/ only; buildspec.yml sits at that zip root)
docker build -t alive108-api:dev ./server
docker build --build-arg BUILD_SHA=$(git rev-parse --short HEAD) \
    -t alive108-api:dev ./server

docker run --rm -p 8080:8080 alive108-api:dev
curl -s localhost:8080/health

# local dev (from repo root) — same image
docker compose up --build          # API on :8080
docker compose --profile worker run --rm worker   # one field snapshot
```

## What's pinned and why

| Pin | Value | Why |
|---|---|---|
| base (both stages) | `python:3.12-slim-bookworm` | was unpinned `python:3.12-slim` — Debian major could drift under it. `-bookworm` fixes glibc/OS while tags still float on patch releases; a digest pin would stall security updates. Builder and runtime share the base so `alive_core*.so` links the exact CPython/glibc it runs on. |
| pybind11 | `v2.13.6` | GIT_TAG in `server/core/CMakeLists.txt` (FetchContent) — needs `git` + network in the builder stage only. |
| deps | `requirements.txt` via `pip --no-cache-dir` | requirements.txt is the authoritative list — `pyproject.toml` is a manifest that lacks `numpy`/`h3` (verify: it is used for `version` by health.py). uv is local-dev tooling; `uv.lock` is gitignored so there is no lockfile to sync in-image. |
| compiler flags | `-O3 -fno-fast-math` | set in CMakeLists (parity oracle asserts 1e-9) — not repeated here. |
| user | `alive` uid/gid 10001, `nologin` | non-root; code stays root-owned (immutable at runtime), only writable dirs (`data/`, `data/field/*`, `data/gtfs`) are `alive`-owned — `chown` without `-R` avoids a duplicate ~10 MB layer. |

## Image anatomy (measured, this box, Docker 29.1.3 legacy builder)

```
python:3.12-slim-bookworm base            ~120 MB
pip install -r requirements.txt            158 MB  (boto3/botocore ~90,
                                                    numpy ~50, h3, fastapi…)
COPY . (app + data)                        ~10 MB  (corpus 3.2, openaq 4.9,
                                                    climatology 0.6, code)
alive_core.cpython-312-*.so (COPY --from)  0.3 MB
─────────────────────────────────────────────────
alive108-api:dev                           413 MB
```

Builder stage (~560 MB toolchain: build-essential, cmake, git) is discarded —
only the `.so` crosses into the runtime stage. Verified: `import alive_core`
resolves in-container and `SearchIndex.query()` returns scored hits; `/v2/search`
still reports `t1_engine:"gazetteer"` because `v2/search.py` wants a module-level
`search()` which neither module exports — engine wiring is app logic, untouched.

## .dockerignore choices (server/.dockerignore — the effective one)

- **`data/field/`** — regenerable worker output. Bundling stale snapshots would
  make `/health.field_age_s` report image age instead of honest `null`
  ("no snapshot yet"). Dir re-created in-image.
- **`data/gtfs/`, `data/community.json`** — runtime caches (already gitignored).
- **`tests/`, `test_api.py`, `core/bench/`** — pytest runs outside the image
  (`cd server && uv run --with 'pytest,h3,boto3' pytest tests -q`); saves only
  ~60 KB but keeps prod surface clean.
- **`core/build/`** — host cmake output; image compiles its own (host .so could
  be wrong arch/toolchain).
- **`.venv*/`, `__pycache__/`, `.env*`, `.git`** — hygiene/secrets.
- Kept: `data/corpus/delhi-corpus-sample.jsonl`, `openaq_recent.csv`,
  `delhi_climatology.json.gz`, `field_calibration.json`, `aliases.json` —
  loaded at runtime. `admin.html`/`city.html` are served by the app.

A repo-root `.dockerignore` also exists for ad-hoc root-context builds
(guards `.wt/`, `node_modules`, `Mobile` native builds); no pipeline path
builds from root today.

## Compose (docker-compose.yml, repo root)

- `server` — `:8080` published for Expo/emulators: Android `10.0.2.2:8080`,
  iOS sim `localhost:8080`, device `<LAN-IP>:8080`.
- `worker` (profile) — one-shot `ingest_worker.py` into the shared volume so
  `/health.field_age_s` goes real.
- `alive-data` named volume on `/app/data` — persists community.json, GTFS
  cache, field snapshots across restarts.
- Env passthrough (shell or repo-root `.env`, gitignored): `OPENAQ_API_KEY`,
  `FIRMS_MAP_KEY`, `ALIVE_LOCATION_KEY/REGION`, `ALIVE_AIR_BUCKET`,
  `AGG_TABLE`, `COMMUNITY_BUCKET`, `AWS_*`, `ALIVE_GAZETTEER`, `BUILD_SHA`,
  `PORT`, `SOURCE_*_UP`. Empty = feature honestly disabled.

## Healthcheck

`HEALTHCHECK` runs `python -c urllib.request…` against `GET /health` on
`$PORT` (no curl in slim); 30 s interval, 15 s start-period. Same path the
NLB target group probes. Docker reported the container `healthy` in ~30 s.

## Known gaps / follow-ups

- **Builder**: this box runs Docker's deprecated legacy builder (no buildx);
  builds fine but prints a deprecation banner. BuildKit would add real layer
  caching across machines + `--mount` caches for apt/pip.
- **deploy.sh env drift** (not mine to fix): task def injects `AIR_BUCKET`
  but the code reads `ALIVE_AIR_BUCKET` (ingest_worker.py:62, rollup.py:68) —
  in-ECS the worker silently falls back to local disk snapshots.
- `docker push` not exercised here (needs ECR creds); `deploy.sh` handles it.
- No multi-arch: Fargate is x86_64; add `--platform linux/arm64` if graviton.
