# notify-e2e — real alert firing on Android + iOS, recorded end-to-end

**Date:** 2026-10-07 · **Mandate:** re-prove the imported notification work
(events-notify `4d20990`+`f72cef3`, notify-v2 `5421269`) on THIS lane's rigs for
the demo: real banners on screen, video + stills, verdict per trigger.
No fake media, no mock pushes — every banner below came out of the real
`checkAirEvents()` engine reading live prod fields (or designed on-device
baselines, flagged where seeded).

Prod: `http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com`
(alias `65.2.28.40`) — GETs only (`/aqi`, `/v2/why`, `/v2/day`, `/v2/outlook`);
zero POSTs anywhere in this lane.

## Rigs

| platform | build under test | how driven |
|---|---|---|
| iOS | dev-client `com.anonymous.app` @ base/v2 tip, Metro `EXPO_PUBLIC_API_URL=http://65.2.28.40` | iPhone 17 sim, iOS 26.5 (udid EDD9B083), plain xcodebuild Debug + `RCT_USE_PREBUILT_RNCORE=0 pod install`, simctl screenshot + host screen-recording |
| Android | release APK `alive108-70914c0.apk` (sha256 `bfceaf26…f41e88f`) | Linux KVM child lane, `demo` AVD pixel_7 android-35 google_apis x86_64, adb + screenrecord |

## Live field at drive time (~14:00–14:45 IST, Oct 7)

- `stagnation` driver PRIMARY, score 0.85, factor 2.02 (≥1.5 bar) — fires un-seeded
- `cleanest_window` 13:30–18:30 IST — IST-now inside [start−60m, end) — `window` fires un-seeded
- `trend` admitted DOWN mid-drive (live delta crossed the server's 12 µg admission bar between polls: −11 → −12+) — `trend_down` fired naturally on a later launch
- fires `belt_fires` 12, `carrying:false`, feed live — `fires_nc` needs a +15/50% jump vs baseline → cannot honestly fire today (a +8 jump must NOT fire — verified)
- ambient ~62–66 µg/m³ → CPCB idx 2, never crossed into Poor+ → `band` silent
- `grap.equivalent_stage` 0 (aqi ~127) → `severe` silent; `grap_clear` fires vs a seeded stage-3 prior
- `outlook` tomorrow 104.5 vs today 68 µg (+54%, ≥15 µg flat bar) — but the
  17:00–22:00 IST gate was closed at drive time → gate-verified quiet
- fires feed `feed_age_s` ~800 s < `feed_stale_after_s` 22500 → feed live

## Verdict — which triggers real-fired vs verified-codepath-but-quiet

| kind | iOS dev-client | Android release APK | basis |
|---|---|---|---|
| `stagnation` | ✅ **real-fired un-seeded** — "the air is sitting over the city · 2× stiller than usual — the day's smoke will linger" | ⏳ pending child | live `/v2/why` primary driver, factor 2.02 |
| `window` | ✅ **real-fired un-seeded** — "easiest hours ahead · today's lightest air ~13:30–18:30 IST · about 62 µg/m³" | ⏳ pending | live `/v2/day` window + IST gate |
| `trend_down` | ✅ **real-fired un-seeded** — "the city's air is easing · 65 → 53 µg/m³ over 5.7h — the air barely moving to clear it — off the earlier high" | ⏳ pending | server admitted the driver mid-drive |
| `grap_clear` | ✅ **fired vs seeded prior** — "the day eased off the GRAP map · today's air no longer reads like a stage (AQI ~127)" | ⏳ pending | events.json `grapStage:3` → live 0 |
| `reflect` | ✅ **fired vs seeded ledger** — "yesterday on the road · 2 trips · about 60 µg inhaled — heavier than Sunday (25 µg)" | ⏳ pending | ledger.json rows; on-device by design |
| `fires` / `fires_nc` | ⛔ **honestly silent** — seeded baseline 4 vs live belt 12 = +8 < +15 jump floor; baseline rebaselined to 12, no mark, no card | ⏳ pending | jump rule working as designed |
| `band` | ⛔ codepath-only quiet — ambient 62–66 µg never crossed idx ≥3 | ⏳ pending | CPCB threshold not met today |
| `severe` | ⛔ codepath-only quiet — `equivalent_stage` 0 | ⏳ pending | stage < III today |
| `grap_up` / `grap_down` | ⛔ quiet — live stage never moved off 0 (grap_clear covers the transition path) | ⏳ pending | — |
| `trend_up` | ⛔ quiet — the admitted move was down | ⏳ pending | — |
| `outlook_heavy` / `outlook_light` | ⛔ gate-verified quiet — fold is heavy (+54%) but fires only inside IST 17:00–22:00; `outlookMove` floor/unit-tested in events.test.ts | ⏳ pending | window gate, not data, silences it |
| feed-stall record | ⛔ no record — both feeds inside staleness bounds | ⏳ pending | diagnostics-only, never pings |

## iOS evidence (dev-client, all banners real-engine)

Natural pass — fresh install, nothing seeded:
- `notify-e2e-shots/ios/ios-natural-fires.mp4` — permission dialog → Allow →
  `stagnation` slide-in → `window` slide-in (one check cycle, both live reads).
- `perm-dialog.png` — iOS permission prompt, fired the moment a real event
  qualified ("ask only when there's something real to say").
- `slide-stagnation.png`, `slide-window.png` — both banners mid-slide.
- `lockscreen-natural-2cards.png` — keyguard/NC: grouped ALive·108 stack ("2").

Seeded-prior pass (`events.json`/`ledger.json` are designed on-device state —
a stored prior is the only way to show a jump/look-back within one session;
file edited only while the app was terminated — `mem` cache stomps live edits):
- `ios-seeded-pass.mp4` — cold relaunch → `grap_clear`, `reflect` slide-ins +
  **`trend_down` firing naturally** (server admitted the driver mid-drive).
- `slide-grap_clear.png`, `slide-reflect.png`, `slide-trend_down.png`.
- `notif-center-5cards.png`, `lockscreen-5cards.png` — 5 real cards, no
  `fires_nc` card (the +8 jump correctly did not fire).
- `trips-ledger-state.png` — the seeded ledger rows behind `reflect`.
- `settings-alerts.png` — Air alerts master + all four kind rows ON.
- `home-ambient-63.png` — the in-app state behind the banners (63 µg/m³).
- `events-final.json` — dedupe store verbatim:
  `seen={stagnation:85, window:810, trend_down:12, grap_clear:0, reflect:1}`,
  `beltFires` rebaselined 4→12 (jump rule), `grapStage` 3→0, **no `fires_nc`
  mark** — the dedupe file proves every fire AND the correct silence.

## Android evidence — PENDING (child spawn blocked by org session cap)

_Verified statically this lane (no emulator needed):_

- Release APK `alive108-70914c0.apk` re-downloaded and sha256-verified
  (`bfceaf26ad8f410d3995c473e77d14efd950e7ee1b610a20f7fa66849f41e88f`,
  137,120,268 B — matches apk-v10-report).
- Binary `AndroidManifest.xml` string-pool decoded on-box: declares
  **`android.permission.POST_NOTIFICATIONS`** (plus VIBRATE, WAKE_LOCK,
  INTERNET, RECEIVE_BOOT_COMPLETED, FCM RECEIVE/SEND and the OEM badge
  permission set). The Android-13+ runtime prompt has its manifest
  precondition — a missing-permission failure mode is excluded statically.
- Runtime prompt + `air-events` channel creation + banner delivery still
  require the emulator; child session spawn is HTTP-429ing on the org's
  7-concurrent-SWE-2 cap and retries on a timer. Fills when it lands.

## Honest limits

- Foreground-poll only (60 s `aqiPoll`) — unchanged; settings copy says so.
- `outlook_*` fires evenings-only by design (17:00–22:00 IST); the fold was
  heavy at drive time but the gate was closed — unit-tested gate, no banner.
- `fires_nc`/`band`/`severe` were honestly quiet today (rules verified by the
  seeded-jump silence + unit tests, not by banners).
- iOS dev toast `[expo-notifications] Error reading persisted server
  registration info` appears in dev-client videos — remote push-token
  registration failing on a sim without APNs; benign, release builds unaffected.
- Seeded marks/baselines are the engine's own on-device state design
  (first-run seeding is silent by design); every seeded fire names its seed.

## Gates / checks

- POST_NOTIFICATIONS + `air-events` HIGH-importance channel: pending Android child.
- `npx tsc --noEmit`, `npx expo lint` — unchanged code, verified clean by the
  notify-v2 lane at `341126f`; this lane touched no product code.
