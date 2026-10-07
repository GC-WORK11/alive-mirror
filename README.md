# ALive-108

**A personal PM2.5 dosimeter for Delhi — no hardware.** Your lungs' ledger: the app reconstructs what you breathed from a live modelled concentration field, so every trip prices in two numbers maps don't show — the smoke you will inhale, and the smoke your ride puts into the air — before you leave, live while you travel, and as a receipt when you arrive. The phone measures nothing itself, and only consented, anonymized **k≥3 aggregates** ever leave it.

Built for the AWS × WeMakeDevs Environmental Hacks hackathon, Track 01 (Air), Oct 8–11 2026. Delhi-only by design. MIT — see [`LICENSE`](LICENSE).

## See it live

- **Web demo (no install, plain HTTP):** [alive108-….elb.ap-south-1.amazonaws.com](http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com) — the landing demo at `/`, then `/city`, `/community`, `/admin` (the engine room sits behind a real sign-in since Oct 7: operator token → `POST /v2/admin/login` → HMAC-signed HttpOnly session cookie; guests land on a gate card). `GET /health` is public and reports the running `build_sha`, field age, and per-source status.
- **Android:** the demo build is a sideloaded APK (universal, debug-signed, cleartext HTTP → prod) shipped with the submission; the build recipe is `docs/demo-day.md` → "Release APK", and `Mobile/` below builds it from source. **iOS:** simulator-only (no Apple developer account; see Status).

## Try it — public, GET-only

```bash
NLB=http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com

curl -s $NLB/health                              # engine, edges priced, field age, per-source status
curl -s "$NLB/aqi?lat=28.6315&lon=77.2167"       # PM2.5 + σ band + calibration + fire modifier
curl -s $NLB/v2/city                             # Delhi's air now + per-hour outlook
curl -s $NLB/v2/city/moves                       # the privacy floor on the wire: min_k 3
curl -s "$NLB/v2/archive"                        # the served field's own recorded history
```

## What it is

You type FROM → TO. Candidates draw as equals, then the winner settles with a verdict pill naming *why* (e.g. "cleanest · N% less than fastest" — the server's own reason line). The server returns real options — road modes via a router, metro/bus via GTFS — each with an ETA, an estimated inhaled-PM2.5 **dose band**, and an estimated **emission band** for the vehicle class you declared. During the trip the app ticks both counters at 1 Hz off a route strip the server hands it (no per-second network); on arrival the receipt lands in an on-device ledger. Both numbers are always bands with a stated basis, never point truth.

On the demo OD (India Gate → Huda City Centre, 24.7 km) the same minutes read **car-AC ~7.4 µg vs on-foot ~255 µg — a ~34.5× spread** the map you use today never shows. It drifts with the field (31–45× across ODs this week) and matches published Delhi measurements (walking ≈28× metro per km inhaled). The field also names *why* in plain words: `GET /v2/why` serves a `cause_note` composed only from measured fields (belt fires · carry wind · ventilation · the recorded trend — "measured, not reported"), rendered on `/city`'s parali-watch tile and the app's air card.

## Privacy, in three lines

1. **No accounts** — the app is fully usable with sharing off.
2. A donated trip is trimmed 300 m at both ends, thinned to ~100 m, rounded to ~11 m, folded into H3 cells, and the device token is SHA-256'd **before anything can touch a store or a log** — no per-trip record exists server-side.
3. Nothing publishes below **k=3 distinct devices in 72 h** — the suppression counter itself is public at `/v2/city/moves` (`min_k: 3`).

[`PRIVACY.md`](PRIVACY.md) has the full transform chain + how to verify it; [`SECURITY.md`](SECURITY.md) covers the threat model (and `docs/lanes/pentest-report.md` is the self-run pentest).

## How it works

```
┌─ Android / iOS app (Expo, MapLibre) ─────────────────────────────┐
│ T0 search — bundled Delhi gazetteer (124,311 rows), on-device    │
│ light bilingual map — hi/en basemap, housenumbers/POIs           │
│ live trip — dose + emission counters tick locally at 1 Hz off    │
│             the route strip; no per-second network               │
└──────────────┬───────────────────────────────────────────────────┘
               │ HTTP (NLB :80 — no TLS terminator today)
┌──────────────▼────────────── AWS ap-south-1 ─────────────────────┐
│ NLB → FastAPI on ECS Fargate                                     │
│                                                                  │
│  /v2/search  alive_core C++ index over the OSM-NCR corpus        │
│              fuzzy typos · kind+place compounds (·hospital near  │
│              saket·) · Hinglish · sector-depth · aliases         │
│              T2: Amazon Location Suggest   [needs API key]        │
│  /v2/reverse gazetteer-first ≤150 m → honest 404 dropped_pin     │
│  /v2/plan    options: ETA + dose band + emission band + reason   │
│              + least-inhalation engine rows (below)              │
│  /v2/strip   field sampled along a route → the live counters     │
│  /v2/trip    anonymous trip summary in (no user table)           │
│  /v2/ledger  per-device dose/emission history (token-keyed)      │
│  /depart · /decide · /v2/day · /v2/reach · /v2/outlook · /v2/why │
│  /v2/city · /v2/districts · /v2/city/moves · /v2/skill · /fires  │
│  /v2/archive · /aqi · /grid · /reports · /admin                  │
│                                                                  │
│  alive_core: C++20 pybind11 module — search index, field         │
│  sampling, dose + emission integrators, and PathEngine:          │
│  an edge-state A* over a 1.07M-edge Delhi-NCR road graph,        │
│  edge cost = length × local PM2.5 (the live field raster,        │
│  repriced every ≤10 min — 903k edges), enforcing 230 OSM         │
│  turn-ban tuples + 3,428 per-way access overrides, returning     │
│  corridor-diverse alternatives with engine_dose_ug on the wire.  │
│  A pure-Python twin (alive_core_ref.py) is the fallback: if      │
│  the C++ import fails the API still serves, just slower; both    │
│  engines are asserted bit-identical in tests.                    │
└──┬──────────────────────────────────┬────────────────────────────┘
   │ every 15 min (in-app ingest loop) │ aggregates only
   ▼                                  ▼
┌───────────────────────────┐  ┌────────────────────────────┐
│ air index (airindex.py)   │  │ DynamoDB alive108-agg      │
│ CAMS grid + NASA FIRMS    │  │ trips / km / µg / g per    │
│ fires + stations* + wind/ │  │ mode-day; corridor cells   │
│ BLH → QC → Kalman →       │  │ TTL 30 d. No user rows.    │
│ kriging ±σ → snapshot→S3  │  └────────────────────────────┘
└───────────────────────────┘
  *stations live: 52 instruments via the WAQI + DPCC feeds right now
   (drifts 52–54 with feed health; count on `/health.sources.stations`
   — OpenAQ stays a dormant keyed path).
```

Also live: a self-hosted Delhi basemap (22.7 MB pmtiles from Geofabrik OSM, z0–14, `GET /tiles/health`), and a decade climatology from OpenAQ's public S3 archive (125 stations) that backs the "vs typical October" line.

## Measured numbers

Everything below traces to a file in this repo or a live endpoint. Where a row says "bench", the protocol and both builds are in `docs/plan/bench-results.md`.

| What | Number | Source |
|---|---|---|
| Search index (T1), C++ vs Python | p50 0.189 ms vs 16.623 ms → **~88× p50** (~100× p95), build 45 ms vs 142 ms | `docs/plan/bench-results.md` |
| Field lookups + dose integration | ~6.8× lookups (174,618 vs 25,849/s); **~13× dose p50** (46.0 µs vs 607.3 µs) | `docs/plan/bench-results.md` |
| Emission integrator | ~3.3× p50 (11.2 µs vs 37.3 µs) | `docs/plan/bench-results.md` |
| Search corpus | 124,311 bundled gazetteer rows (`Mobile/assets/delhi-gazetteer.json`); 97,447 OSM-NCR corpus entries (incl. 16,949 real address rows) | `server/data/corpus/STATS.md` |
| Search acceptance | 67/67 fixed queries in top-3 (name, typo, compound, sector, alias) | `server/data/corpus/STATS.md`, `tests/search_queries.txt` |
| Search latency | C++ index p50 0.189 ms / p95 0.723 ms on the benched 26,545-row corpus; re-measured p50 0.320 ms / p95 1.228 ms on the 120,351-entry index (same harness) | `docs/plan/bench-results.md` |
| Field leave-one-out vs live instruments | MAE 8.8 µg/m³, bias +0.2, n=70 WAQI+DPCC instruments (krige refit per held-out station) — served on the wire | `GET /aqi → calibration` |
| Field vs station archive (3,550 pairs, 85 stations) | MAE 22.0 µg/m³, bias +15.5 µg (+51.6%) — **over-reads in clean post-monsoon air**; ±2σ coverage 95.2% measured vs 95.4% nominal | `server/data/field_validation.md` |
| Path engine | 1,070,459 edges / 819,846 nodes; 903,058 edges priced per reweight; 230 turn bans + 3,428 access overrides | `GET /health → routing` |
| Live instruments | 52 stations via WAQI + DPCC (verified Oct-7 ~11:00 UTC on `698cf808`; accepted drift band 52–54, 24 in a DPCC stall) | `GET /health → sources.stations` |
| Mode exposure ratios | walking ≈28×, rickshaw ≈5× the metro per km inhaled PM2.5 — published Delhi measurements | `docs/plan/10-claims-ledger.md`, `server/exposure.py` header |
| Cigarette equivalence | 316 µg PM2.5 ≈ 1 cigarette (Berkeley Earth) — OFF by default; opt-in toggle, always "≈" | `docs/plan/10-claims-ledger.md` |

C++ result parity is asserted bit-exact against the Python reference in `server/tests/`.

## What it does not claim

This section is a feature, not a disclaimer.

- **Phones measure nothing.** The app traverses a model field; it never says "your phone measured the air." User traversals adjust *dose estimates*, never the underlying field.
- **Emissions are class-level estimates.** "Vehicles like yours (2016 petrol car, BS-IV): ~1.1–1.6 kg CO₂" — a band from published factors, never "your car emitted 42.0 g."
- **Plaintext HTTP edge, one task.** NLB is TCP:80 only — no TLS terminator today (a domain + ACM cert away; flagged owner decision, in `docs/lanes/pentest-report.md`). One Fargate task, one region: honest capacity is ~8–15 concurrent active users — a demo room, not the internet.
- **Stations: WAQI + DPCC are live; OpenAQ/CPCB-keyed still pending.** 52 instruments carry the field today (drifting 52–54 with feed health); OpenAQ needs `OPENAQ_API_KEY`, and no CPCB public JSON endpoint is reachable from the deployment network (`server/data/field_validation.md`).
- **Amazon Location is optional.** With `ALIVE_LOCATION_KEY` you get T2 suggestions, traffic-aware routes, and Amazon reverse-geocode. Without it the app still works: bundled gazetteer + C++ search, public OSRM demo routing, gazetteer-first reverse.
- **The field is honest about its own error.** It over-reads in clean air (+51.6% bias on the validated window); the calibration and σ bands are served next to the data, not hidden.
- **The community layer is young.** 44 real dev donations from 24 contributors so far — the k≥3 suppression that keeps them honest also keeps the public corridor table sparse. We say so.
- **No outcome claims.** We can count "N trips switched to a lower-smoke option" — a countable behaviour — but not "Delhi got cleaner because of ALive."

## Why AWS (Track 01)

What's real, not decorative: the deploy pipeline is CodeBuild → ECR → Fargate behind an NLB on an Elastic IP in `ap-south-1` — compute in the same region as the air it measures. DynamoDB holds the aggregate-only donation store (`alive108-agg`, TTL 30 d), S3 holds field snapshots + the hourly served-field archive + community snapshots, Secrets Manager holds every key (none in the repo — the secrets-history audit is `docs/lanes/repo-hygiene-report.md`). The EventBridge schedule stubs in `infra/schedules/` are honestly **disabled** scaffolding — the in-app loop owns the 15-min rebuild. Runs at ~$46/mo on Fargate Spot.

## Run it yourself

Server (Python ≥3.11):

```bash
cd server
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt pytest
.venv/bin/python -m uvicorn main:app --port 8080
```

Tests — the offline unit suite needs no credentials; C++-parity tests skip cleanly if the extension isn't built (`brew install eigen` + `bash core/build_ext.sh` builds it; `core/build312/` is gitignored):

```bash
cd server
.venv/bin/python -m pytest tests/                      # offline
.venv/bin/python test_api.py --base http://localhost:8080   # hits real upstreams
```

Mobile (Expo SDK 57, npm — `package-lock.json` is the lockfile):

```bash
cd Mobile
npm install
npx expo start        # dev server; npx expo lint · npx tsc --noEmit to check
```

The demo APK is a release build with the prod endpoint baked at bundle time (`EXPO_PUBLIC_API_URL=http://alive108-…elb.ap-south-1.amazonaws.com`, optionally `EXPO_PUBLIC_TILES_URL=http://65.2.28.40/tiles/tilejson.json` for the self-hosted basemap), then `cd android && ./gradlew assembleRelease` — debug-signed sideload, cleartext HTTP by necessity (prod is :80). That's the shipped demo configuration, not a release channel.

Search corpus (downloads Geofabrik OSM, builds the corpus, emits the mobile gazetteer, scores the 67-query acceptance list into `STATS.md`):

```bash
./tools/setup-corpus.sh
```

AWS infra + deploy (one-time / drift repair; `--dry-run` prints every command):

```bash
./infra/provision.sh --dry-run
AWS_ACCESS_KEY_ID=… AWS_SECRET_ACCESS_KEY=… ./scripts/deploy.sh
```

## Status

| Phase | State | Notes |
|---|---|---|
| 0 · Foundations + AWS | ✔ built | NLB + ECS Fargate Spot + ECR + DynamoDB + Secrets Manager live; ~$46/mo; EventBridge scaffolding disabled by design |
| 1 · Instant search | ✔ built | C++ index over 120k rows, fuzzy/compounds/Hinglish/sectors/aliases, 67/67 acceptance, p50 <1 ms engine |
| 2 · Map + shell | ✔ built | bilingual (hi/en) basemap, housenumber/POI tiers, sidebar + design tokens |
| 3 · Plan: breath + smoke-out | ✔ built | `/v2/plan` options + least-inhalation engine rows + corridor alternatives + legality; `engine_dose_ug` on the wire |
| 4 · Live trip | ✔ built | `/v2/strip` + `/v2/trip`, turn nav chrome, voice cues (Android-verified; iOS sim cold-launch SIGSEGV residual killed — 12/30→0/30 drive-bys via the Promise JS-thread hop, `docs/lanes/ios-residual-report.md`), reroute served, cinematic route chooser with verdict pill (`e2ff634`) |
| 5 · Air index + city + admin | ✔ built | krige field + σ bands, ingest workers, rollup, NCR choropleth, species layers, corridors CO₂/100 m, PUC calibration, `cause_note` parali-watch line; 52 stations live via WAQI + DPCC; `/admin` behind real sign-in (`b563da2`) |
| 6 · Polish + proof + submission | ◐ in progress | benchmarks above; videos shipped; store signing on owner |

**Only the owner can unblock:** a wider station key (OpenAQ would add instruments; data.gov.in is TCP-refused even from ap-south-1), the Amazon Location spend cap/key, a release-signing keystore (the shipped APK is debug-signed and sideloads fine), a domain+ACM cert for TLS, real-phone Delhi test drives, and an Apple developer account (iOS stays simulator-only).

**Hackathon note.** Event rules require repo history inside the Oct 8–11 window: `scripts/public-repo.sh` squashes this tree to one baseline commit on the public repo; later commits land inside the window. The full audit trail — every verification, bench, and lane report — ships inside `docs/` either way.

## Docs

The plan folder is the source of truth; `docs/plan/10-claims-ledger.md` governs every number this repo shows. Full map: [`docs/README.md`](docs/README.md) — `docs/plan/` (engineering plan, benches, runbook, living `handoff.md`), `docs/lanes/` (~200 dated audit reports and briefs — evidence, not prose), `docs/submission/` (hackathon writeup + checklist), `docs/privacy/` (claim → enforcement → test table).

## Layout

`server/` — FastAPI dose engine + `server/core/` C++ (`alive_core`: search index, field/dose/emission integrators, PathEngine) + `server/v2/` API · `Mobile/` — Expo app · `Bridge/` — shared wire contract · `scripts/` `infra/` `tools/` — deploy, provisioning, corpus · `tests/search_queries.txt` — the fixed acceptance list · `docs/plan/` — the plan.
