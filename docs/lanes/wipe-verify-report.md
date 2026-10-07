# Lane report — wipe-verify: "delete my data" on the real filesystem

**Claim under test:** "nothing leaves your phone unless you donate, and deleting
actually deletes." The pocket-engine lane fixed the daylog `mem`-mirror
resurrection bug (its report, finding #3) but only against a stub FS. This lane
drove the real path on a booted iPhone sim and read the app's own container.

- **Repo/branch:** `<owner>/Delhi-Air-108` @ `base/v2` (`0ac91e3` + the
  fix below)
- **Device:** iOS Simulator iPhone 17, iOS 26.5, UDID
  `EDD9B083-63F1-44E6-9A7B-0A6964CC2561`, dev client `com.anonymous.app`
- **Backend:** `EXPO_PUBLIC_API_URL=http://65.2.28.40` (prod)
- **Container:** `…/Devices/EDD9B083-…/data/Containers/Data/Application/113A05E6-…`
- **Date:** 2026-10-06, ~21:25–21:57 local

Screenshots live in `docs/lanes/wipe-verify-shots/` (device-truth via
`simctl io screenshot`). Full pre-wipe Documents md5 manifest:
`wipe-verify-shots/prewipe-hashes.txt`.

## Populate (real drive, consent ON)

Delhi parked location set pre-launch, then moved (>450 m) so `recordSample`
wrote real per-position samples — 3 samples at 3 coords; one check-in
`{breath:1, eyes:1, energy:-1}`; a real search "India Gate"; one driven nav
trip ended at the receipt ("Trip ended" — logged `Car (AC) · least-smoke rd`,
1.1 µg dose / 1.1 kg emit); week strip + Delhi today opened; vehicle `auto`.
00–02 in the shots dir.

### Pre-wipe Documents/ (53 files, 12 personal + 42 alive-cache)

| file | bytes | contents verified |
|---|---|---|
| `ledger.json` | ~400 | the trip above (from/to coords, dose, label) |
| `daylog.json` | ~600 | 3 samples + check-in `2026-10-06` |
| `daylog.json.bak` | ~500 | prior generation — 2 samples + check-in (**`.bak` does carry personal data**) |
| `daysum.json` / `.bak` | ~10.9 k | sealed days 09-30…10-05 (all thin), `dirty:["2026-10-06"]` |
| `settings.json` | ~160 | defaults + `vehicle:"auto"` |
| `vehicle.json` | 15 | `{"cls":"auto"}` |
| `contributor.txt` | 31 | `{"id":"anon-c08f9dabb041de33"}` |
| `consent.json` | 29 | `{"seen":true,"sharing":"on"}` |
| `places.json` | ~120 | 1 recent (India Gate coords) |
| `events.json` | ~180 | `beltFires:20`, `bandIdx:1`, seen stagnation+window |
| `welcome_seen_v1.json` | 32 | `{"seen":true}` |
| `alive-cache/` | 42 files | last-good strip/outlook/daycurve/route payloads (GPS-bearing) |
| `outbox.json` | — | absent (nothing queued) |

## Wipe path (real UI)

Pass 1: menu → Settings → "Delete my data" → system alert "delete my data? —
your trips, settings and anonymous id are removed from this phone" →
destructive "delete" (shot 03). `App.deleteAll` ran: `DELETE /v2/ledger`
(800 ms cap) → `clearAllData()` → `resetEventsStore()` → React state resets.

## Post-wipe Documents/ (within seconds)

```
alive-cache/  (2 files — re-fetched ambient daycurve+outlook)
daysum.json   10892 B — NEW file
daysum.json.bak 9085 B — NEW file (previous post-wipe generation)
```

`ledger.json`, `daylog.json`, `settings.json`, `contributor.txt`,
`consent.json`, `vehicle.json`, `places.json`, `events.json`,
`welcome_seen_v1.json`: **all deleted.**

The reappearing `daysum.json`/`.bak` are **honest-empty re-seals**, not
resurrection: 6 sealed days all `totalUg:0, samples:0, trips:0, parts:[]` with
fresh `at` timestamps (21:39:57) and `dirty:["2026-10-06"]` — the week strip
re-reading `getDay` after `setDayNonce` legitimately re-seals empty days. The
old trip/sample content is absent. `.bak` holds only the *previous post-wipe
generation* — the safefile contract intact, no wiped bytes inside.

## Resurrection test (the bug pocket-engine fixed)

Without relaunching, waited ~75 s for the next foreground `/aqi` poll:

- `daylog.json` reappeared, 97 B: **exactly one new sample** at ts 21:40:15
  (`28.6158,77.2337`, amb 50.8) with `checkins:{}`. Under the pre-fix `mem`
  mirror this write would have restored all 3 wiped samples + the check-in.
  **It did not.** wipeGen guard verified on the real FS.
- `events.json` reappeared, 118 B: `beltFires:null`, fresh `bandIdx:1`, only a
  new post-wipe `window` sighting — old event state gone.
- `ledger.json`, `contributor.txt`, `vehicle.json`, `places.json`,
  `settings.json`, `consent.json`: stayed absent (no lazy writer needed them).

## Cold relaunch

`simctl terminate` + `launch` → the full welcome carousel re-armed ("Every
Delhi trip has an air price." — shot 05): `welcome_seen_v1` was really gone.
Post-skip home is honest-empty: "your count starts once the phone logs its
first hours", budget **216 µg left of 216**, check-in card blank with "the
pattern needs ~7 days", sidebar shows Saved-places add-only + "My vehicle —
not set" and no trips block (shots 04, 06). `Your trips` sheet: "no trips
yet". Delhi-today sheet renders live city data. No crash, no stale numbers.

## FINDING (real bug) — NSURLCache residue outside Documents/

Container-wide grep after wipe 1 found wiped personal data still on disk under
`Library/`:

| marker | where it survived |
|---|---|
| `anon-c08f9dabb041de33` (wiped contributor id) | `Library/Caches/com.anonymous.app/Cache.db` **and** `Cache.db-wal` — still there even after a relaunch |
| `"q":"India Gate"` + `"bias":{"lat":28.6315,"lon":77.2167}` (the user's query **and their live position at search time**) | `fsCachedData/A148F8D7…` response body |
| `28.615456, 77.229671`, "least-smoke", "Kashturba" (destination coords + route labels) | `fsCachedData/27EDA66B…`, `F1A8771A…` bodies |

iOS persists `fetch()` response bodies via NSURLCache (`fsCachedData/` +
`Cache.db*`), and `clearAllData` only touched `Documents/`. Forensic-readable
until the OS evicts. `Library/Preferences` plist, `Library/HTTPStorages`,
saved-state `data.data`, and `.mapbox` tiles: no personal markers (map tiles
are ambient per-region data; the app-switcher `SplashBoard/*.ktx` snapshot is
an iOS-managed screen image — noted, not actionable from JS).

### Fix (minimal, this lane's gate)

`purgeUrlCaches()` added to `Mobile/src/store/safefile.ts`, called from
`clearAllData` (`settings.ts`). It deletes `fsCachedData/` and `Cache.db*`
inside the app's `Library/Caches/<bundle>/` dir — surgical: metal/gpu caches
are left alone — plus the app's `Library/HTTPStorages/` jar
(`Paths.cache.parentDirectory`). Best-effort try/catch like every purge in the
file. Gates: `tsc --noEmit` clean, `expo lint` clean, `test-runner.mjs`
41/41 green.

### Wipe 2 — verification of the fix (new bundle, pid 10010)

Re-seeded: real search "India Gate" → 2 cache hits; `Cache.db*` still held
`anon-c08f9dabb041de33` from session 1 (no new id minted — proves persistence).
Sidebar → "Delete my data" → confirm.

```
post-wipe-2 container-wide grep:
  anon-c08f9dabb041de33 : 0 files      India Gate      : 0 files
  anon-*                : 0 files      77.229671       : 0 files
  least-smoke           : 0 files      Kashturba       : 0 files
                                       28.6315 (bias)  : 0 files
Library/Caches/com.anonymous.app/ = com.apple.gpuarchiver, com.apple.metal,
                                    com.apple.metalfe   (URL-cache artifacts gone)
Library/HTTPStorages/             = empty
```

Regression: 80 s later a fresh honest daylog sample landed (21:53:08,
amb 54.1), new alive-cache responses wrote at 21:55:52/21:57:08 — networking
and the app's own cache fully functional after the purge; cache dirs re-form
lazily. No crash (UIKitApplication pid 10010 alive throughout).

## Verdict table

| # | check | result |
|---|---|---|
| 1 | populate state on real FS | PASS — 53 files incl. real trip, 3 samples, check-in, recents, settings |
| 2 | delete via real UI (both entry points: Settings row + sidebar row) | PASS |
| 3 | Documents personal files removed | PASS — all 12 gone; reappearing `daysum.json`/`.bak` are honest-empty re-seals |
| 4 | no `.tmp`/`.bak` residue holding wiped data | PASS — only post-wipe-generation `.bak` (contract-correct) |
| 5 | resurrection: post-wipe writes don't restore wiped data | PASS — daylog re-formed with 1 new sample, `checkins:{}` (pocket-engine fix holds on real FS) |
| 6 | cold relaunch = clean empty boot | PASS — onboarding re-armed, no stale numbers |
| 7 | week strip / symptom lens correct pre- and post-wipe | PASS — strip read sealed daysum; lens honestly early post-wipe; budget 216/216 |
| 8 | container-wide personal residue (beyond Documents) | **FAIL → FIXED** — NSURLCache held anon id + search + route payloads; `purgeUrlCaches` added; wipe 2: 0 hits |

## Notes / accepted limitations

- NSURLCache's *memory* tier isn't reachable from JS — it dies with the
  process; cold relaunch after wipe leaves nothing. Disk tier was the bug.
- `SplashBoard/*.ktx` app-switcher snapshot can freeze a screen's pixels; iOS
  retakes it continuously and post-wipe screens already overwrote it. Not
  JS-addressable.
- `purgeUrlCaches` targets the iOS store layout. Android's OkHttp cache
  (`http-cache/`) isn't covered by the dir scan — follow-up for an Android
  box; the function no-ops safely there.
- `settings.json` being absent post-wipe (rather than defaults-on-disk) is
  honest: `mem` is cleared and nothing calls `saveSettings` until the user
  changes a pref — defaults live in code.
- Server-side `DELETE /v2/ledger` raced within its 800 ms cap; on-device FS
  can't prove the server row went. The id it deletes (`anon-…`) is itself
  wiped + cache-purged, so even a missed delete orphans an id this device can
  no longer name.
- Follow-up option for the api lane: `cache: "no-store"` on personalized
  endpoints would prevent disk caching instead of purging after the fact —
  bigger blast radius, deliberately not taken here.
