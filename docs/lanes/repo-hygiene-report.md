# repo-hygiene lane report — public surface launch-clean

Date: 2026-10-07 · Branch: `base/v2` @ `e7db808` → this commit · Lane brief:
secrets-history audit + judge-facing docs. Boundaries respected: docs/config/
README/LICENSE only — no server logic, no Mobile/src, no history rewrite.

---

## 1. Secrets history audit (P0) — CLEAN

Scope: all 1,219 commits reachable from `--all` (main + base/v2 + every lane
branch), the full `git log -p` diff stream (470,811 added/removed lines), plus
the set of filenames ever tracked.

### Commands run + results

| # | Command (abridged) | Result |
|---|---|---|
| 1 | `git log --all --full-history --oneline -- server/.env '**/.env' '.env'` | **0 commits** — no `.env` ever tracked |
| 2 | `git ls-files \| grep -i '\.env'` | Only `Mobile/ios/.xcode.env` (Xcode `NODE_BINARY` export — not a secret) and `server/.env.example` (placeholders only) |
| 3 | `git log --all -p \| grep -E 'AKIA[0-9A-Z]{16}\|AIza…{35}\|ghp_…\|github_pat_…\|xox[baprs]-…\|BEGIN … PRIVATE KEY\|sk-…{20,}'` | **0 hits** — no AWS/Google/GitHub/Slack/OpenAI/PEM material in any public diff |
| 4 | `git log --all -p \| grep -E '(AWS_SECRET_ACCESS_KEY\|OPENAQ_API_KEY\|WAQI_API_KEY\|CPCB_API_KEY\|FIRMS_MAP_KEY\|ALIVE_ADMIN_TOKEN\|ALIVE_OTD_API_KEY\|DEVIN_*KEY)[:=] …'` | **0** — no named secret ever had a value committed |
| 5 | Generic `(SECRET\|TOKEN\|PASSWORD\|API_?KEY)…[:=] "<literal≥12>"` over full history, minus getenv/placeholder lines | 1 hit: `TOKEN_FREE='/admin/api/corridors'` — a JS constant holding a URL path, not a credential |
| 6 | `git log --all -p \| grep -E 'https?://user:pass@'` (creds-in-URL) | **0** |
| 7 | PEM/`PRIVATE KEY-----` scan over full history | **0** |
| 8 | `Bearer <token>` / Slack webhook / JWT-shape scan | 1 hit: `Bearer supersecret-token-abc123` in `server/tests/test_observability.py:181` — **deliberate fake**: the privacy test asserts it must NOT appear in request logs. No rotation needed. |
| 9 | Long-hex/Devin-key (`apk_…`, `devin-…`, 40-hex) scan | Only Xcode constraint ids, lockfile `revision` SHAs, and 2 Devin **session IDs** quoted in lane docs (`devin-e866a72b…`, `devin-f0abfff3…`) — session ids are references, not credentials |
| 10 | Ever-tracked suspicious filenames (`git log --all --name-only` filtered) | `Mobile/android/app/debug.keystore` — the stock React Native debug certificate (creation date 2013, well-known RN template fingerprint `FA:C6:17:45…`). It signs debug builds only; sideloads work, Play doesn't accept it. Standard RN practice — **not a secret**. `tools/flip_waqi_token.sh` — takes the token as a CLI arg; embeds nothing. |
| 11 | DB connection strings `postgres/mysql/mongo/redis://user:pass@` | **0** |
| 12 | `api_key`/32-hex token literals in docs | **0** |
| 13 | `.gitignore` coverage | `.env` + `.env.*` ignored with `!.env.example` carve-out; nested Mobile gitignores cover the app dirs. Verified `tools/corpus-venv/` (a local venv whose `requests/auth.py` tripped the raw grep) is **ignored**, not tracked. |

### Findings for the owner

- **Nothing requires rotation.** No real credential reached a tracked file in
  any commit.
- **Watch item (not a leak):** `Mobile/android/app/debug.keystore` is the
  stock debug cert — fine for hackathon sideloads. If a *release* keystore is
  ever created, keep it out of git (`.gitignore` already covers
  `Mobile/android/app/release/`).
- Public-by-design infra strings in tree (NLB hostname, EIP `65.2.28.40`,
  Secrets Manager *names* like `alive108/waqi`) — identifiers, not secrets;
  the values live in Secrets Manager.

## 2. README.md — judge landing cold

- Lead reframed as the **personal PM2.5 dosimeter** (phone reconstructs what
  you breathed; only consented k≥3 aggregates leave — links `PRIVACY.md` +
  `SECURITY.md`).
- MIT license named + linked.
- **Fixed one untraceable number:** the "Search latency" row claimed
  "p50 0.86 ms / p95 2.51 ms on 120k rows" citing `bench-results.md` — that
  doc only benches the 26,545-row corpus (0.189 ms). No source contained the
  120k figure. Re-measured on this checkout with the shipped harness
  (`bench_search.py`, C++ `alive_core` over the current 124,311-row gazetteer
  → 120,351 index entries): **p50 0.320 ms / p95 1.228 ms / p99 2.128 ms**.
  The row now cites the file numbers + the fresh measurement, labelled.
- Docs section now points at the new `docs/README.md` map.
- Every other quoted number re-verified against its cited file:
  bench table (88×/13×/3.3×/6.8×), corpus stats (97,447 + 16,949 + 67/67),
  LOO calibration (8.8/+0.2/n=70), held-out validation (3,550/85/22.0/+51.6%),
  route-graph meta (1,070,459 / 819,846 / 230 bans — read from
  `route_graph.meta.json`), 316 µg cigarette constant, 28×/5× exposure ratios.
- **Drift note, not an error:** `/health` today reports `stations.count=53`
  (`waqi+dpcc`) vs the documented 54 — instrument count drifts with feed
  health; README already routes readers to `/health.sources.stations` for the
  live count. `edges_priced` live = 903,058, matching docs.
- Live URL verified: `GET http://65.2.28.40/health` → `ok:true`,
  `field_age_s≈292`, `build_sha:44e5e97f` (fresh field, routing loaded).

## 3. LICENSE

MIT added at repo root (`LICENSE`), copyright line `govinda
(ALive-108 contributors)` — owner's open-source call, conventional choice.

## 4. `server/.env.example`

Existed and covered the user keys; completed it against an actual
`os.environ`/`os.getenv` sweep of tracked `server/*.py`:

- **added (optional upgrades):** `ALIVE_LOCATION_KEY` +
  `ALIVE_LOCATION_REGION` (Amazon Location T2 — README already referenced the
  var, the example didn't list it), `ALIVE_DPCC_INGEST` flag.
- **added (ops):** `OSRM_URL` + per-profile `OSRM_URL_{DRIVING,CYCLING,WALKING}`
  + `OSRM_LOCAL_TIMEOUT` (default `127.0.0.1:5001`; deploy.sh overrides to the
  `:5000` sidecar), rate-limit/body/HSTS knobs (`ALIVE_RATE_RPS/BURST`,
  `ALIVE_MAX_BODY_BYTES`, `ALIVE_SEC_HSTS`).
- **added (deploy-only):** `COMMUNITY_BUCKET`, build stamps
  (`BUILD_SHA`/`GIT_SHA`/`ALIVE_VERSION`/`APP_VERSION`).
- **added (internals, commented):** data-path/snapshot/archive vars, job vars
  (`ALIVE_JOB`, `ALIVE_ROLLUP_*`, `ALIVE_GC_APPLY`, `GTFS_BAKE_TIMEOUT_S`) —
  listed so nothing the server reads is undocumented.

## 5. docs index

New `docs/README.md` — the honest map: `plan/` as source of truth
(ledger/bench/runbook/handoff linked), api/privacy/submission/video/builder-
center tables, `lanes/` described as the dated audit trail (~160 files,
brief vs `*-report.md` convention explained), the `00`–`33` numbered docs
labelled historical research where they disagree with the running service.
Only files that exist are linked.

## 6. Dead links + stale claims sweep

Scanner: all `**/*.md` `](path)` targets resolved relative to their file,
fenced code blocks excluded (two earlier hits — an Overpass bbox and
`E[emission](winner)` — were notation, not links).

Fixed:
- `docs/submission/repo-readme.md` — 5 broken image links. 3 pointed at
  `docs/assets/readme/*.png` (dir never populated); wired to real captured
  shots from Oct-6 lanes (`web-nits-shots/after/landing-1280-hero.png`,
  `web-overhaul-v2-shots/after-city.png`, `after-admin.png`) and refreshed the
  stale "PENDING CAPTURE" comments. 2 pointed at real files under
  `docs/assets/cloud-build/` with repo-root-relative paths (invalid from
  `docs/submission/`) → `../assets/…`.
- `docs/21-search-map-ux.md` — `](Mobile/App.tsx)` → `](../Mobile/App.tsx)`.
- `Bridge/README.md` — understated endpoint list for `contract.ts`; updated
  to the real `/v2/*` surface actually defined there.

Verified-not-broken: every README-claimed route exists in `server/main.py` +
`server/v2/` (`/v2/search`, `/v2/reverse`, `/v2/plan`, `/v2/strip`,
`/v2/trip`, `/v2/ledger`, `/v2/city`, `/v2/districts`, `/depart`, `/decide`,
`/admin`, `/health`, …). `PRIVACY.md`'s `OSRM_URL=127.0.0.1:5000` matches the
deployed sidecar port (deploy.sh:191); the local default `:5001` is the
dev path — both true.

## Gates

- No `server/` code touched → the pytest gate does not apply. Only the bench
  harness was *run* (read-only, produces numbers) to fix the stale row.

## Not done / owner follow-ups

- Release keystore hygiene when one is cut (see §1).
- `stations.count` drifts day to day (54 documented, 53 live today); if the
  README's "54" matters on demo morning, re-stamp from `/health` then.
