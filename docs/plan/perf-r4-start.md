# perf-r4-start — time-to-interactive & startup work

Lane: `r4-perfstart` · branch `feat/r4-perfstart` · scope: `Mobile/index.ts`,
`Mobile/src/store/*`, `Mobile/src/components/shell/settings.ts` (the real
settings persistence module), `Mobile/src/startup/*` (new), this doc.

## What runs before frame 1 (audit)

`App.tsx` gates render on `useFonts` while `expo-splash-screen` holds the
native splash (`preventAutoHideAsync` at module eval → `hideAsync` when
fonts land, `if (!fontsLoaded) return null`). Correct — splash never
blank-screens. The mount effect **fires while fonts are still loading**,
so all of this competes with the font window on the JS thread / IO queue:

- `GET /health` ping + a 15 s interval (`App.tsx`)
- `GET /reports` poll + a 60 s interval (`App.tsx`)
- `loadTrips()` — disk read + `JSON.parse` of `ledger.json` (up to 500 trips)
- `loadSettings()` — disk read of `settings.json`
- `Location.requestForegroundPermissionsAsync()` + `getCurrentPositionAsync`
  — GNSS warm-up at boot, and a permission prompt that can land over splash
- `loadConsent()` — small read, gates the onboarding sheet (frame-1-relevant)
- `useNetStatus()` → `probe(API)` on mount + `queueSize()` reads
  `outbox.json` during first render (`src/offline/*`)
- `Notifications.setNotificationHandler` at `src/notify.ts` module eval
- `getVehicle()` — small read, only needed before the first `/v2/plan`

## Changes (this lane)

**`src/startup/marks.ts`** (new) — perf marks, `performance.now()` offsets
from module-eval t0. Emits `[perf] <name> @ <ms>` on console in dev; always
readable via `globalThis.__alivePerf.dump()` / `.marks`. Also taps
`globalThis.fetch` once to stamp `plan:first` on the first `/v2/plan`
response (observation only — Response passes through untouched; the api/nav
files stay untouched).

**`src/startup/idle.ts`** (new) — `afterFirstFrame()`: resolves after the
first rAF + `InteractionManager.runAfterInteractions`, hard-capped at
1.2 s so nothing can hang on a never-ending animation. Resolution is
memoized — late-session callers pay one microtask.

**`index.ts`** — imports marks first (earliest owned t0), stamps
`index:eval` / `index:registered`, and registers a thin `Root` wrapper that
stamps `app:didMount` + `app:firstFrame`. App itself is rendered
identically — no `App.tsx` edit.

**`src/store/ledger.ts`** — the real win on the critical path:
- `loadTrips` first read is scheduled via `afterFirstFrame()` — disk I/O +
  `JSON.parse` (≤500 trips, ~2–5 ms of JS-thread parse) no longer competes
  with the mount/font window. Trips only paint in the sidebar/ledger.
- In-memory mirror: the file is read + parsed **once per launch** instead
  of on every `logTrip`/`deleteTrip`/`reloadTrips` call (each was a full
  read+parse before). Callers get `.slice()` copies — `mem` stays private.
- Concurrent first callers share one `inflight` read.
- Writes serialize through `writeTail` — read-modify-write races can't
  interleave; a burst flushes last-state-wins.
- Read is bounded (`slice(-MAX_TRIPS)` on parse — same 500 cap writes use).
- `resetLedgerCache()` lets `clearAllData()` drop the mirror with the file.

**`src/store/vehicle.ts`** — same pattern: `getVehicle` read deferred to
after-first-frame + deduped (the profile only matters before `/v2/plan`),
`saveVehicle` write serialized.

**`src/store/consent.ts`** — read kept **eager** (it gates the onboarding
sheet) but deduped via `inflight`; `persist` serialized.

**`src/components/shell/settings.ts`** — the real settings persistence
module (mission's "find the real ones"). `loadSettings` gains a mem mirror
+ `inflight` dedupe — it used to hit disk on **every** call, including
`notify.ts` `prefs()` per scheduled ping. Read stays **eager** (`lang`
paints frame-1 text — deferring would flash English at Hindi users).
`saveSettings` writes funnel through `writeTail`. `clearAllData()` now also
drops the settings + ledger mirrors so wiped data can't resurrect.

**`src/i18n/strings.ts`** — audited, unchanged: `t()` is a synchronous
O(1) table lookup; both tables are small literals. Stays sync per spec.

**`app.json`** — no additions needed; splash handling is already correct.

## Reading the marks

Dev builds print them as they land:

```
[perf] perf:t0 @ 0ms        ← marks module eval (bundle window start)
[perf] index:eval @ 412ms   ← import tree (App.tsx + screens + maplibre) done
[perf] index:registered @ 413ms
[perf] app:didMount @ 480ms ← App committed (splash still up, fonts loading)
[perf] app:firstFrame @ 497ms
[perf] plan:first @ ...     ← first /v2/plan response, whenever it happens
```

Programmatic: `(globalThis as any).__alivePerf.dump()` →
`perf:t0=0ms index:eval=412ms …`.

## Estimated savings

Not device-measured (no device farm here) — reasoned per change:

- `JSON.parse` of `ledger.json` (≤500 trips) moved off the mount window:
  **~2–5 ms** JS-thread on a mid-range device.
- `vehicle.json` + `ledger.json` disk reads moved off the IO queue during
  font/asset loads: **~1–3 ms** effective, plus less contention.
- Repeat `loadTrips`/`loadSettings` calls in-session are now ~0 (were a
  full read+parse each): every ledger-screen open / notify arm.
- Serialized writes remove a real (if rare) read-modify-write race between
  `logTrip` and `deleteTrip`.

Bigger fish are outside this lane's file set — flagged for the owners:

- `App.tsx` boot effect: `Location.requestForegroundPermissionsAsync` +
  `getCurrentPositionAsync` at boot → should be on-demand (locate tap /
  first pick). Permission prompt over splash is also a UX wart.
- `App.tsx`: `/health` + `/reports` fire before first frame alongside
  `useNetStatus`'s own `/health` probe — three probes at once; the
  reports poll could wait for `afterFirstFrame()`.
- `src/notify.ts`: `setNotificationHandler` at module eval.
- `src/offline/queue.ts`: `queueSize()` file read inside `ensureWired()`
  during first render.
- `src/search/recents.ts`: same File/Paths store — already mem-cached,
  could adopt `inflight` dedupe if the search lane wants parity.
