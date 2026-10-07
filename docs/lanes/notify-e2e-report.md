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
| `stagnation` | ✅ **real-fired un-seeded** — "the air is sitting over the city · 2× stiller than usual — the day's smoke will linger" | ✅ **real-fired un-seeded** — "the air is sitting over the city · barely mixing — 2× stiller than usual; expect the day's smoke to linger" | live `/v2/why` primary driver (factor 2.02 ios / 1.86 apk; APK copy is older build 70914c0 — documented) |
| `window` | ✅ **real-fired un-seeded** — "easiest hours ahead · today's lightest air ~13:30–18:30 IST · about 62 µg/m³" | ✅ **real-fired un-seeded, incl. revision re-fire** — "~14:30–18:30" card replaced in place by "~15:30–19:30 IST" when prod revised the window (level 870→930) | live `/v2/day` window + IST gate; Android pass proved the re-post path |
| `trend_down` | ✅ **real-fired un-seeded** — "the city's air is easing · 65 → 53 µg/m³ over 5.7h — the air barely moving to clear it — off the earlier high" | ✅ **real-fired un-seeded** — "65 → 50 µg/m³ over 5.7h — the air barely moving to clear it — off the earlier high" | server admitted the driver mid-drive on both |
| `grap_clear` | ✅ **fired vs seeded prior** — "the day eased off the GRAP map · today's air no longer reads like a stage (AQI ~127)" | ✅ **fired vs seeded prior** — "our read no longer maps to a stage (aqi ~119)" | events.json `grapStage:3` → live 0 |
| `reflect` | ✅ **fired vs seeded ledger** — "yesterday on the road · 2 trips · about 60 µg inhaled — heavier than Sunday (25 µg)" | ✅ **fired vs seeded ledger** — "2 trips · about 84 µg inhaled — heavier than Sunday (60 µg)" | ledger.json rows; on-device by design |
| `fires` / `fires_nc` | ⛔ **honestly silent** — seeded baseline 4 vs live belt 12 = +8 < +15 jump floor; baseline rebaselined to 12, no mark, no card | ⛔ **honestly silent** — same +8 < +15 floor, held across 3 passes | jump rule working as designed |
| `band` | ⛔ codepath-only quiet — ambient 62–66 µg never crossed idx ≥3 | ⛔ codepath-only quiet — ambient ~59–65 µg → idx 1–2 | CPCB threshold not met today |
| `severe` | ⛔ codepath-only quiet — `equivalent_stage` 0 | ⛔ codepath-only quiet — same | stage < III today |
| `grap_up` / `grap_down` | ⛔ quiet — live stage never moved off 0 (grap_clear covers the transition path) | ⛔ same | — |
| `trend_up` | ⛔ quiet — the admitted move was down | ⛔ same | — |
| `outlook_heavy` / `outlook_light` | ⛔ gate-verified quiet — fold is heavy (+54%) but fires only inside IST 17:00–22:00; `outlookMove` floor/unit-tested in events.test.ts | ⛔ gate-verified quiet — fold +62% real at 15:39 IST, gate still closed when the window ended | window gate, not data, silences it |
| feed-stall record | ⛔ no record — both feeds inside staleness bounds | ⛔ same | diagnostics-only, never pings |

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

## Android evidence (release APK `70914c0` on KVM emulator, session ~15:05–15:50 IST)

_Static pre-checks (this lane, no emulator):_ sha256 `bfceaf26…e88f` re-verified;
binary manifest declares `POST_NOTIFICATIONS`; the JS bundle inside the APK
contains the `air-events` engine + verbatim copy (build `70914c0` — older than
HEAD `9fbd851`, so on-device copy differs slightly from `strings.ts`; not a bug).

_Drive (Linux KVM child `4b6eb8ea`, `demo` AVD pixel_7 android-35 google_apis):_

- **Permission: REAL OS dialog, no breakage.** Cold launch → "Allow ALive·108 to
  send you notifications?" granted via UI (logcat GrantPermissionsViewModel
  result=4) — `perm_dialog.png`, `after_allow.png`. The feared Android-13+
  POST_NOTIFICATIONS showstopper does not exist.
- **Channel:** `air-events` `mImportance=4` HIGH, name "air alerts", sound +
  vibration `[0,250,250,250]`; every record `mIsInterruptive`, AUTO_CANCEL,
  vis=PRIVATE — `dumpsys_final.txt`.
- **Cards on camera:** `shade_events2.png` (trend_down expanded + stagnation),
  `shade_p3/p4.png` (reflect + window + grap_clear), `shade_grap_expanded.png`,
  `shade_now2.png` (the window REVISION re-post replacing its card in place —
  per-kind identifier `air-event-<kind>` works), `shade_stag.png`,
  `keyguard_swipe.png` (both natural cards on the real keyguard),
  `settings_airalerts.png` (+crop — master + 4 sub-toggles ON), `side4.png`
  (sidebar rendering the seeded ledger "3 trips · ≈144 µg"), `home2.png`.
- **Videos:** `n1.mp4` (launch → perm dialog → first fires), `n2`–`n4`/`n6`
  (repeat passes incl. dedupe re-verification), `nt.mp4` (heads-up peek probe).
- **State:** `events_pass1.json` (baselines stored silently on first read —
  first-run seeding is silent by design), `events_final.json` (marks
  `stagnation:60, trend_down:16, window:930, reflect:1, grap_clear:0`, no
  `fires_nc`), `ledger_final.json`, `facts.md` (child's full verbatim account).
- **Dedupe verified:** same-day marks blocked every repeat fire across 6
  relaunches; seeded baselines self-corrected to live (beltFires 4→12).

## Findings / caveats

1. **Heads-up peek never rendered on this AVD** (observation, not proven app
   bug): across ~11 min of footage + 6 launches, cards posted directly to the
   shade; NMS autogroup set `groupAlertBehavior=1` despite `mIsInterruptive`
   and channel importance 4 — most likely the API-35 google_apis emulator's
   autogroup presentation quirk. **Recommend one physical-device (or
   Play-image) check before claiming heads-up peek in the pitch.** Delivery
   itself — post, channel config, shade, keyguard, in-place replace — is
   verified. On iOS the peek DID render (slide-ins in ios-natural-fires.mp4).
2. Cosmetic (known): the OS permission dialog can paint over the intro
   carousel before first-run finishes — `requestPerms()` runs inside `fire()`,
   i.e. the moment the first real event qualifies, which can precede
   onboarding completion. Ordering note, not a bug.
3. APK copy lag vs HEAD strings (documented above — build is `70914c0`).

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
