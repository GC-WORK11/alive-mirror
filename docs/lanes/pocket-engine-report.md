# Pocket-engine lane — report

The question that started this lane, verbatim: *"as a daily user — how does the
app cache that my location is this, I traveled here-there? Is a watch always on?
If the app runs in background, figure out all the OS policies — Android, iOS,
Chinese ROMs — how we cache daily location/dose. Personal analytics should be a
low-RAM engine INSIDE the mobile app — light, fast, uncrashable, low battery."*

Two parts below: **(A)** the honest OS-policy truth table for background
location, and **(B)** what ALive-108 actually does today after the audit, the
gaps found, and what this lane shipped.

---

## A. The OS-policy truth table — "is a watch always on?"

Short honest answer: **no, and ALive-108 should keep it that way.** Every OS
makes continuous background location possible but expensive in exactly the ways
a free, trust-first, personal-dose app cannot pay: battery, permission UX that
reads as surveillance, store-review friction, and — worst — unreliability, so
you'd burn all of the above and *still* get silent gaps.

### Stock Android 10+ (Pixel / AOSP lineage)

| Question | Truth |
|---|---|
| Can we get background location at all? | Only with **"Allow all the time"** (`ACCESS_BACKGROUND_LOCATION`, added API 29). It is **not grantable from an in-app dialog on Android 11+** — the user must be sent to *Settings → Apps → Permissions → Location → "Allow all the time"*. Every drop-off in that flow is a lost user. |
| What does continuous GPS cost? | Rule-of-thumb field numbers: an always-on GNSS fix with frequent wakeups lands roughly **3–6 % battery per hour** on typical hardware — the single largest app drain a phone can have. Batched FusedLocationProvider delivery and Doze deferrals push it lower (~1–3 %) but make fixes *bursty*, not continuous — the OS decides, not you. |
| Foreground service? | Yes — `foregroundServiceType="location"` is **mandatory** for reliable continuous location (required since Android 10; Android 14 additionally requires declaring `FOREGROUND_SERVICE_LOCATION`). Cost: a **permanent visible notification** the whole time it runs. Users read that as "this app is watching me." |
| Geofencing instead? | `GeofencingClient` wakes the app on enter/dwell/exit — but you still need "Allow all the time" for background delivery on Android 10+, you're capped at **100 geofences per app per device**, and triggers are delivered on the OS's own latency budget (commonly ~2 min, longer under Doze). Fine for "near home?" — useless for "what did I inhale on that auto ride?" |
| Deferrable work? | `JobScheduler`/`WorkManager`: minimum periodic interval **15 min**, deferred freely under Doze/App-Standby buckets; expedited work has a daily quota. Fine for daily rollups — which is why our rollup runs on-device and needs no background work at all. |
| Store/policy cost | Google Play requires declaring background-location use in the **Permissions Declaration Form**; apps without a core user-facing feature justification get rejected or pulled. "Personal analytics" is a marginal justification — real risk. |
| **Verdict** | Continuous background location is *possible but product-negative*. Not adopted. |

### MIUI / ColorOS / OriginOS (the kill-list ROMs — most of the target market's phones)

| Question | Truth |
|---|---|
| Does a foreground service survive? | **Unreliably.** These ROMs run aggressive battery managers that kill apps minutes after screen-off or swipe-away, *including apps running foreground services* — this is the entire reason `dontkillmyapp.com` exists. An FGS is protection against AOSP Doze, not against MIUI's "Battery saver: kill apps." |
| Can we opt out programmatically? | **No API.** Each OEM has its own per-app whitelist — MIUI: *Battery saver → No restrictions* **plus** a separate *Autostart* toggle; ColorOS/RealmeUI: similar per-app switches; vivo OriginOS: "Background power consumption management." Toggles can only be deep-linked to settings screens, and the deep links **differ per OEM per OS version** and sometimes move between MIUI releases. |
| Can we even detect it? | No reliable API — the honest field practice is "detect gaps after the fact, nudge on next launch" (i.e. you find out the kill happened because a day of data is missing — exactly the fake-coverage pattern ALive-108 refuses). |
| Xiaomi-specific quirk | MIUI has historically blurred the "while using the app" boundary — location access when the app is merely in the background is treated as background access on several MIUI versions. |
| **Verdict** | Worst of both: highest kill risk, lowest fixability, on the exact phones most of Delhi's users carry. Continuous background tracking here is a promise we'd break silently. Not adopted. |

### iOS 17+

| Question | Truth |
|---|---|
| Can we get "Always" location? | Two-step UX by design: the first prompt can only offer **While Using**; requesting Always later either shows a second prompt *at a moment iOS chooses* or sends the user to Settings. iOS then **periodically re-shows** "this app used your location N times in the background" reminder dialogs — designed to make users reconsider. |
| Continuous GPS in background? | Possible via the `location` background mode — but draws the visible **blue pill / blue location indicator**, is one of the heaviest battery drains iOS allows (~5–10 %/hr), and App Store review requires justification. Same trade as Android, more visible. |
| Cheaper options? | **Significant-change location** wakes the app on ~500 m cell-tower moves (near-free battery, delivers deferred batches, requires Always) — but only fires on movement, so a stationary day under a bad-plume produces zero samples. **Visits service** delivers OS-detected dwell events (free, coarse). **Region monitoring** is capped at **20 regions**. None of these gives per-hour dose coverage. |
| Does swipe-away end it? | Mostly — but significant-change and region monitoring are among the very few APIs that **relaunch even after a force-quit** (and survive reboot without user action). Honest note: that behavior is precisely what privacy-sensitive users find creepy. |
| Deferrable work? | `BGTaskScheduler` tasks are system-scheduled, ~15 min minimum cadence, budgeted by how often the user opens the app — fine for batching, wrong for sampling. |
| Policy cost | iOS 17+ privacy manifests: location APIs are **"required-reason APIs"** — `PrivacyInfo.xcprivacy` must declare a reason code; wrong/absent declaration blocks App Store upload. |
| **Verdict** | Significant-change + visits would be the only *affordable* option, and it still fails the product: sparse hours stay sparse (the app honestly says "covered X of Y min" today instead of lying). Not adopted this lane. |

### The honest answer to "is a watch always on?"

**No — and nothing in ALive-108 tracks the user in the background, by design.**
What the phone actually knows:

- **Location today** comes from what the app already had: a foreground GPS fix
  while the app is open, places the user searched/picked, and real trip
  endpoints the nav engine logged at arrival. All foreground, all user-visible.
- **Ambient samples** are recorded only during the existing ~60 s foreground
  `/aqi` poll (`App.tsx` → `recordSample`) — deduped (<8 min *and* <~450 m),
  bounded (MAX_SAMPLES 4000, 21-day keep window). The header comment on that
  file has always said it: *"no background tracking: battery + the promise on
  the card."*
- **Trips** land in `ledger.json` only on real arrival events — not from a
  passive GPS trail, so there's no trace of "where you were all day" to leak.

The dose math runs on this sparse, honest set: `reconstructDay` trapezoid-
integrates breathing-zone concentration over sample pairs ≤45 min apart and
adds logged trip doses; uncovered hours are *explicitly uncovered*
(`coveredMin`, `thin`) rather than fabricated. That honesty is the product —
it's the same stance as the "k≥3 or you see nothing" aggregation rule.

**Recommended design (adopted):** a sealed per-day rollup living inside the app —
the low-RAM analytics engine, described below — *not* any new location source.
The only number that changes is that past-day analytics are now *computed once
and stored*, instead of recomputed on every render.

---

## B. What shipped this lane

### Audit findings (before)

1. **Recompute-per-render:** `HomeScreen`'s week strip and `symptomLens` called
   `reconstructDay` for *every finished day on every assemble* — up to ~120
   full reconstructions per open. Correct math, wrong caching.
2. **Non-atomic writes:** `ledger.json`/`daylog.json` wrote in place — a kill
   mid-write could leave a torn JSON = lost history.
3. **Mirror resurrection bug (real bug, fixed):** `daylog` kept a `mem` mirror
   but had no reset path — `clearAllData` deleted `daylog.json`, and the next
   `recordSample` **re-wrote every wiped sample and check-in** from the
   surviving mirror. Delete-my-data did not actually delete.
4. **Read/write race:** a disk read started before delete-my-data could resolve
   *after* the wipe and repopulate `mem` (outbox/cache had `wipeGen` guards;
   ledger/daylog didn't).
5. `stats()`/`weekStats()` walked the trip array multiple times per call.

### Shipped

- **`src/store/safefile.ts` (new)** — crash-safe JSON doc IO: write to `.tmp` →
  atomic `moveSync` → previous generation kept as `.bak`; reads fall back
  main→`.bak`. Optional FNV-1a checksum envelope `{v, sum, d}` (same hash as
  `api/cache.ts`). Bare-payload format retained for `ledger.json`/`daylog.json`
  (drive lanes read those files raw via adb/simctl); checksummed envelope only
  on the new `daysum.json`.
- **`src/store/daysum.ts` (new) — the pocket engine.** One sealed record per
  local day: full `DayReconstruction` + `trip_ug`/`stay_ug` split + per-mode
  totals + trip count. Properties:
  - *Computes only from real inputs* (`allSamples` + `loadTrips`) via the same
    `reconstructDay` — a cache of truths, never a source of numbers.
  - *Self-invalidating:* subscribes to the stores' new mutation hooks —
    `logTrip`/`deleteTrip`/`recordSample` dirty exactly their day,
    `clearTrips` dirties all. No call-site invalidates by hand.
  - *Survives kill-before-reseal:* the dirty set is **persisted**, and
    pre-load invalidations merge after boot.
  - *Volatile today:* today's record is always recomputed live; a mid-day
    "partial" seal re-seals final once the day ends.
  - *Bounded:* ≤400 day records (covers the lens's 120-day look-back with
    margin); hour arcs kept only 14 days (the week strip never reads older);
    file stays ~150 KB.
  - *Language-aware:* stored part labels re-seal on hi↔en flips.
- **`ledger.ts` / `daylog.ts`** — moved to safefile atomic writes + `.bak`;
  added `wipeGen` guards on both read and queued-write paths; new
  `resetDaylogCache()` fixes the resurrection bug above; added mutation hooks;
  `stats()`/`weekStats()` now single-pass.
- **`HomeScreen.tsx`** — week strip + symptom lens read sealed rollups via
  `getDay`; only *today* reconstructs live.
- **`settings.ts` `clearAllData`** — now calls `resetLedgerCache()` +
  `resetDaylogCache()` + `resetDaySum()` and purges safefile artifacts
  (`.tmp`/`.bak`) for ledger/daylog, plus the existing file deletions.
  Verified: no daysum/ledger/daylog bytes or mirrors survive.
- **`test-runner.mjs`** — stub FS extended (`delete`, `copySync`, `moveSync`,
  `Directory`, `__DEV__`) so the atomic path and the whole `clearAllData`
  chain run in-process.
- **`daysum.test.ts` (new, 12 tests)** — honest empty, seal-once,
  per-day invalidation through the real hooks, deleteTrip re-seal, lang
  re-seal, persisted dirty marks, checksum verify, `.bak` fallback,
  partial→final, ≤400/14-day retention, batch reads, and **wipe
  completeness** (files *and* mirrors — the resurrection bug's regression
  test).

### Untouched, verified

- **`offline/queue.ts` (the k≥3 outbox)** — not modified; its `wipeGen`,
  ordered flush, 4xx-drop and `wireAutoFlush` behavior unchanged. The outbox
  still only ever carries completed trips under the rotating `anon-XXX`
  contributor id; k≥3 is enforced server-side as before.
- `server/`, `Bridge/contract.ts`, `admin.html`, `landing.html` — untouched
  (other lanes own them).
- No new dependencies; no background location APIs of any kind; no new
  permissions anywhere.

### Verification

| Gate | Result |
|---|---|
| `node src/store/test-runner.mjs` | **30/30 pass** (11 new daysum + 1 wipe test) |
| `npx tsc --noEmit` | clean |
| `npx expo lint` | clean (0 errors, 0 warnings) |
| Delete-my-data | unit-verified: `clearAllData` purges daysum.json + ledger/daylog safefile artifacts; mirrors reset; subsequent reads honest-empty |
| Android sim | impossible on this box (no KVM) — covered by unit tests; iOS-sim smoke optional follow-up |

### Deliberate non-changes (argued, not skipped)

- **No background location added** — the truth table above is the argument:
  every platform makes it cost battery + permission friction + store risk, and
  the kill-list ROMs make it *unreliable* on top, which is the one sin this
  app cannot commit (silent gaps dressed as coverage). The foreground poll we
  already have is the honest source.
- **No checksum on `ledger.json`/`daylog.json`** — those formats are
  documented and read raw by the drive lanes; the `.bak` rollback covers torn
  writes. `daysum.json` is new and self-owned, so it gets the envelope.

*Lane pocket-engine · files: Mobile/src/store/{safefile,daysum,daysum.test,ledger,daylog,test-runner}, Mobile/src/screens/HomeScreen.tsx, Mobile/src/components/shell/settings.ts · verified 2026-10-07.*
