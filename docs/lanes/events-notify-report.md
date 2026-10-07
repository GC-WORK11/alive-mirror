# events→notification engine — lane report

Mandate: `docs/lanes/events-notify.md` — honest air-event detection off real
server fields, immediate local notifications, minimal settings surface,
foreground-poll only. Built on `base/v2` (`6ff5596`), verified on iPhone 17 /
iOS 26.5 simulator against the live backend (`http://65.2.28.40`).

## What shipped

| piece | file | what it does |
|---|---|---|
| detection engine | `Mobile/src/store/events.ts` | `checkAirEvents()` runs piggyback on the existing 60 s `aqiPoll`; reads baselines + dedupe from `Documents/events.json` (expo-file-system); self-throttles `/v2/why` to 10 min, `/v2/day` to the poll's own cadence |
| notification plumbing | `Mobile/src/notify.ts` | `air-events` channel (Android HIGH importance), `notifyAirEvent()` — immediate `trigger: null` local notification, felt-line title + number+reference body, `en`+`hi` via `t()` |
| settings | `settings.ts`, `SettingsScreen.tsx`, `strings.ts` | master "Air alerts" + 3 sub-rows (smoke & fires / air turning worse / clean windows), persisted; master-off greys sub-rows; copy says "checked while the app is open" because `expo-task-manager` is not installed — no background task, honest |
| grap passthrough | `src/api/dayfield.ts` | `/v2/day` `grap.equivalent_stage|aqi` surfaced into `DayCurve.server` (server's own "maps to" read — never invented client-side) |
| integration | `App.tsx`, `useShellFlow.ts` | `armAirEvents` = notification-permission check only (nothing to schedule); `deleteAll` also wipes `events.json` |

## Trigger table — every rule traces to a live field

| event kind | real field(s) | threshold | dedupe (per UTC day) | verified on device |
|---|---|---|---|---|
| `fires` / `fires_nc` | `GET /v2/why` → `evaluated.fires` (`belt_fires`, `carrying`, `feed_age_s < feed_stale_after_s`) | belt ≥ 10 **and** jump ≥ max(15, 50%) vs stored baseline | re-ping only on a bigger jump | ✅ fires_nc: live belt 20 vs stored 4 → banner |
| `band` | `/aqi` `pm25_ambient ?? pm25` (krige) → `bandIdx()` CPCB breaks | crossing **up** into idx ≥ 3 (>90 µg/m³) since last read | every higher band re-pings | code-path only — today ambient peaked ~84 µg (NW sweep 16 pts), honestly never crossed |
| `window` | `GET /v2/day` → `cleanest_window` (`start_label`/`end_label` IST + `pm25_mid`) | IST now ∈ [start−60 min, end) | new start time re-pings | code-path only — cleanest window 10:30–16:30 IST, checked ~06:30 IST |
| `stagnation` | `GET /v2/why` → `drivers[kind=stagnation, weight=primary].score` + `detail.factor` | primary + score ≥ 0.6 | re-ping at score +0.2 | ✅ live: score 1.0, factor 8.21 → "8× stiller than usual" banner |
| `severe` | `GET /v2/day` → `grap.equivalent_stage` | stage ≥ 3 | every higher stage re-pings | code-path only — today `equivalent_stage` 0 (AQI 108), correctly silent |

## Evidence

- `docs/assets/events-notify/stagnation-banner.png` — "the air is sitting over
  the city / barely mixing — 8× stiller than usual; expect the day's smoke to
  linger" — pure-real first poll, no seeding.
- `docs/assets/events-notify/fires-banner.png` — "fires up in the burn belt /
  4 → 20 fires northwest — the wind isn't bringing it to Delhi right now" —
  `carrying:false` chose the `fires_nc` variant; baseline `belt_fires: 4`
  seeded into `events.json` to exercise the jump rule (the baseline file is
  designed on-device state — first-run seeding is silent by design, so a
  stored prior is the only way to show a jump within one session).
- `docs/assets/events-notify/settings-rows.png` — master + 3 sub-rows ON.
- `docs/assets/events-notify/settings-master-off.png` — master OFF greys all
  sub-rows; `settings.json` persisted `alerts:false` while sub-values kept.

## Dedupe semantics (`fired()` in events.ts)

One `seen[kind] = {day, level}` mark per kind. A new UTC day resets all kinds.
Within a day: fires/belt re-ping at +max(15, 50%); band & severe re-ping at a
strictly higher level; stagnation at score +20 (=0.2 wire); window when the
start minute differs.

## Honest limits

- Foreground only — no `expo-task-manager` in `package.json`; settings copy
  says so. Adding it later is a follow-up, not this lane.
- `/v2/why` self-throttled to 10 min per app — fires/feed move on that scale.
- `band` and `severe` verified by code path only — real air today never met
  the honest thresholds (ambient max ~84 µg/m³ NW sweep; GRAP-equivalent 0).
- `window` can't fire before the window — needs IST ≥ start−60 m.

## Rules kept

- Zero POSTs invented; only `GET /aqi` (existing 60 s poll), `GET /v2/why`,
  `GET /v2/day`. Never touched `/v2/feedback|/observe|/v2/trip`.
- `npx tsc --noEmit` clean; `npx expo lint` clean.
- en default + hi mirrors for every new string key.
