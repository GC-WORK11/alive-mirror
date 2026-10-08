# Lane report — local-store: the app's whole on-device footprint, bounded

**Owner ask (verbatim-ish):** "the app itself takes local storage of the
device — make it efficient so even used for years it won't take much
storage… Profile-based backup tied to THEIR account (like Gmail) — new
phone, they log in, data comes back — but the DB is on THEIR side, client
side. We never host user data. Cache management for personalized user."

**Repo/branch:** `<owner>/Delhi-Air-108` @ `base/v2`
**Method:** real-store simulation — `scripts/storage-growth-sim.mjs` drives
the actual `ledger`/`daylog`/`daysum`/`api/cache` modules against an
in-memory expo-file-system for 30d/1y/2y/3y of a heavy-Delhi profile
(3 trips + 28 ambient samples + 1 check-in + 4 distinct `v2:plan` +
`v2:strip` cache writes/day at the measured ~300 KB plan size).
Payload sizes measured against the live backend earlier this session:
`/v2/plan` 255–420 KB, `/v2/strip` 7.4 KB, `/v2/day` 4.9 KB,
`/v2/outlook` 4.7 KB, `/grid?cells=28` 235 KB.

## Inventory — everything the app persists

All under `Paths.document` (Android `files/`, iOS `Documents/` +
`Library/Application Support/`). **No AsyncStorage, no SQLite of ours**
(the repo comment stands: "the repo carries no AsyncStorage"). Native
SQLite that does exist is MapLibre's `mbgl-offline.db` (Android) /
`.mapbox/cache.db` (iOS) — the offline tile store.

| store | file(s) | bound | verdict |
|---|---|---|---|
| trip ledger | `ledger.json` + `.tmp/.bak` | 500 trips (was: disk-only cap — see fix #1) | now bounded in RAM too |
| daylog | `daylog.json` + `.tmp/.bak` | 21d window, ≤4000 samples, ≤120d check-ins | already honest |
| daily rollups | `daysum.json` + `.tmp/.bak` | 400 days sealed DaySum, 14d arcs | **is** the "daily rollup after N days" — ledger stays meaningful, fine-grain expires |
| API last-good cache | `alive-cache/*` | **was unbounded** → now 64 files / 12 MB / 30d | **fixed (fix #2)** |
| outbox | `outbox.json` | 50 queued donations, drop-oldest + counter | bounded |
| settings/consent/vehicle/welcome | `*.json` | constants (~30–200 B) | bounded |
| search recents | `places.json` | 5 recents + home/work | bounded |
| events dedupe | `events.json` | per-day seen-marks, single-digit KB | bounded |
| contributor id | `contributor.txt` | ~31 B, 30d rotation | bounded |
| perf log | `perf_log.jsonl` | PERF_ON=false in committed builds | dev-only |
| URL caches | `fsCachedData`, `Cache.db*`, `HTTPStorages` | under `Paths.cache` — OS-purgeable | not user data; not backed up |
| offline tiles | `mbgl-offline.db` / `.mapbox/` | 27 MB pack + `AMBIENT_MAX_BYTES=160MB` ambient | bounded by MLRN; **excluded from backup** |
| t0 search index + gazetteer | bundled assets (31 MB + 11 MB) | read-only app bundle | in APK/IPA, never in backup scope |

## Measured growth (sim output, verbatim)

```
lived | ledger.json (rows) | daylog.json (samples) | daysum.json (days) | alive-cache (files) | TOTAL app docs
30d   | 23.7 KB (90)   | 43.6 KB (589) | 14.2 KB (30)  | 9.60 MB (64)  | 9.76 MB
365d  | 131.7 KB (500) | 49.3 KB (589) | 170.9 KB (365)| 10.80 MB (72) | 11.48 MB
730d  | 131.7 KB (500) | 49.3 KB (589) | 187.3 KB (400)| 9.60 MB (64)  | 10.32 MB
1095d | 131.7 KB (500) | 49.3 KB (589) | 215.0 KB (400)| 10.80 MB (72) | 11.57 MB
```

**Plateau ≈ 11.5 MB forever** — dominated by the now-bounded cache. The
user-owned ledger+daylog+daysum+small-files total stays under ~450 KB.
Re-run: `cd Mobile && node scripts/storage-growth-sim.mjs`.

### The curve before this lane (projected, arithmetic from measured sizes)

`alive-cache/` had **no cap and no eviction**: one file per distinct
~100 m-rounded O/D pair × vehicle signature and per route_id. At the
sim's 4 plan + 4 strip writes/day: ≈1.23 MB/day → **~15 MB/mo, ~450 MB/yr**
of last-good JSON. On the real device this was already visible —
wipe-verify's pre-wipe manifest shows `alive-cache/` at 42 files after a
single drive session.

## What this lane changed

### 1. `src/store/ledger.ts` — the mirror is bounded, not just the file

`MAX_TRIPS=500` only ran inside `ensureMem()` (load) and `scheduleWrite()`
(persist). `logTrip` pushed onto `mem` without trimming, so a long-lived
session accumulated every trip in RAM — `loadTrips()`/`stats()`/the week
math all scaled with session-lifetime rows, not 500. Sim showed 3285 in
memory at 3y (file was still 500). Now `logTrip` splices the mirror to the
cap at push time — memory and disk tell the same story.

### 2. `src/api/cache.ts` — eviction sweep

- Bounds: `MAX_ENTRIES=64`, `MAX_BYTES=12MB`, `MAX_AGE_MS=30d`.
- Sweep runs inside `cacheSet`, **every 16th write** — reads (every
  request) never pay for a listing; writes stay O(1) in the hot path.
- Eviction is **metadata-only**: `Directory.list()` + `modificationTime` +
  `size` — no envelope body is ever parsed. Oldest-mtime-first until all
  three bounds hold (stale-age entries die even under the caps).
- `cacheStats()` exported for diagnostics/audit.
- Semantics unchanged: envelope `{k,t,ttl,v}`, last-good `cachePeek`,
  wipe-generation guard intact (`src/api/cache.test.ts` pins all of it:
  5 new tests — entry cap, byte cap, 30d reap, post-wipe no-resurrection,
  fresh/last-good read).
- 12 MB is deliberate: ~28–40 of the measured ~300 KB plan payloads —
  months of distinct commute routes; last-good stays useful without
  eating the phone.

### 3. Backup — platform account, client-side, zero server of ours

**Android** (`allowBackup` was already true but coverage was default):
`plugins/withBackupRules.js` — a config plugin that writes
`android:dataExtractionRules` (API 31+) + `android:fullBackupContent`
(≤30) into the manifest and `res/xml/alive_*.xml`. Rules are
include-everything-except-regenerables, so any *future* store file is
covered by default:

- included: `ledger.json`, `daylog.json`, `daysum.json`, `settings.json`,
  `consent.json`, `vehicle.json`, `welcome_seen_v1.json`, `places.json`,
  `outbox.json`, `events.json`, `contributor.txt` (+ `.bak` forms) —
  ≲450 KB against Auto Backup's 25 MB quota.
- excluded: `mbgl-offline.db*` (+`.mapbox` dir), `delhi.pmtiles`,
  `alive-cache`, `perf_log.jsonl`, `ReactNativeDevSupport` — all
  regenerable.

Applied output is checked in (`android/app/src/main/AndroidManifest.xml`
attrs + the two `res/xml` files) — `npx expo prebuild` regenerates cleanly
but produces unrelated churn (drops the hand-added
`usesCleartextTraffic`, rewrites icons/permissions), so the checked-in
copy carries the surgical equivalent; the plugin remains the
regeneration source of truth. `xmllint` clean.

**iOS**: everything under `Documents/` + `Library/Application Support/`
backs up to the user's iCloud by default — the restore path needs no
config. What must be excluded is MLRN's `…/Application
Support/<bundleId>/.mapbox/` store (~30–190 MB regenerable tiles).
`plugins/withBackupExclusion.js` injects one ObjC file
(`ios/ALive108/AliveBackupExclusion.m`, wired into the app target in the
checked-in `project.pbxproj`) whose `+load` sets
`NSURLIsExcludedFromBackupKey` on `.mapbox` — once at image load and once
~30 s in, because MLRN creates the dir lazily on first map init.
`xcodebuild -list` parses the project; `clang -fsyntax-only` passes on the
.m. (expo-file-system exposes no exclusion API — this is the smallest
correct hook.)

**Honest gaps:** `bmgr backupnow` staging needs a Google account on a real
device — not drivable on the emulator; coverage is verified statically
(manifest attrs + rule XMLs lint-clean, paths match `Paths.document`
layout). Same on iOS — the exclusion attribute applies at runtime;
verified by compile + Apple documented semantics, not a live restore.
t0 chunks/gazetteer live in the app *bundle* — outside backup scope by
construction.

## Low-RAM posture (already true, verified not regressed)

- `LedgerScreen` uses FlatList virtualization; `stats()`/`weekStats()` are
  single-pass over the now-≤500 mirror.
- `daysum.getDay` seals one day at a time; `getDays` batch-reads.
- `daylog.allSamples()` loads ≤49 KB peak (21d window).
- Cache sweep reads metadata only — no body parsing ever.

## Gates

`tsc --noEmit` clean · `expo lint` clean · node runners: store 16/16,
nav 94/94, api 22/22 (5 new cache-eviction tests), offline 16/16.
