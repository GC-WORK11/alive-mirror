# lifecycle-drive — lane report

Real-world phone behaviors, driven on the iOS simulator (iPhone 17 / iOS 26.5,
release build of `Mobile/` on `base/v2@3ce2775` plus this lane's fixes).
Screenshots in `lifecycle-shots/`. Verification was on-device — every "fixed"
line below was re-driven after a rebuild, not just compiled.

## Paths driven

fresh install → onboarding → location denied → manual planning → nav with no
GPS → kill mid-nav → relaunch → background 4.6 min mid-nav → foreground →
notification ask/allow → banner tap → Notification Center tap → ping-me
under denied + under quiet-hours → map-pick for the armed "from" slot.
(Airplane+relaunch skipped — offline-verify lane covers it.)

## FIXED this lane — each re-verified on device

1. **Map pick overwrote the destination.** `App.tsx onMapPress` passed every
   pick to `pick(…, "to")`. A "Where from?" map pick overwrote `to` and bounced
   the user back to the still-empty origin. Now fills the armed `editWhich`
   slot — the offline-verify lane landed the identical fix concurrently
   (`e147dbd`, "catalogue #1"); this lane's device evidence stands:
   `lifecycle-shots/mappick-from.png` — the map tap filled `from`,
   `Coronation Memorial` kept its slot, compare loaded.
2. **Locate crosshair was a dead tap under denied location.** `onLocate`
   silently no-oped. Now a `locDenied` pill says it plainly and opens iOS
   Settings via `Linking.openSettings()`. Evidence:
   `locdenied-pill.png` → `locdenied-settings.png`.
3. **"ping me" had two silent dead-taps.**
   a. OS notifications denied: `remind()` returned invisibly. Now `pingDenied`
      → the row reads "notifications are off — tap to open Settings"
      (`useShellFlow.ts:113-115`, `CompareSheet.tsx` depart row).
   b. `scheduleDeparture` returns null when the best window sits >2h inside
      quiet hours (tonight's best = 4:00 am, slides to 7 am quiet-end = 3h >
      MAX_QUIET_SHIFT_MS `notify.ts:76`) — the tap used to do nothing at all.
      Now `pingQuiet` → "the best window is inside quiet hours — ping skipped".
      Evidence: `pingquiet.png`. (`useShellFlow.ts` remind, `CompareSheet.tsx`,
      `strings.ts` notifDenied + notifTooLate en/hi.)
4. **Nav with zero GPS fixes showed a silently-frozen ETA.** `nav.snapped`
   stays null under denied location while counters tick at trip-start air —
   the ETA banner looked alive and wasn't moving. New pill:
   "no location — counting the air where you started"
   (`NavChrome.tsx` gated on `nav.running && !nav.snapped`, `navNoGps`).
   Evidence: `navnogps.png` — nav ticking 0.1 µg / 3 g, pill live.
5. **Notification taps dead-opened.** No response listener existed — any tap
   resumed the app on whatever surface was last up. Added
   `addNotificationResponseReceivedListener` + `getLastNotificationResponseAsync`
   in `App.tsx`: `air-event-*` → air map; `alive-daily-brief` /
   `alive-departure` → Delhi today (`App.tsx:707-727`).

## Verified honest — unchanged

- **Kill-resume mid-nav.** `simctl terminate` during a running nav → relaunch
  → clean home, no phantom trip, no half-restored nav banner. Honest full
  restart. Evidence: `killresume.png`.
- **Denied-location home.** "the air near central Delhi · 66 µg/m³ moderate ·
  location is off or hasn't locked yet — turn it on for the air where you
  actually are · air reading: N min old". Manual planning works end to end
  (type → pick → compare → Start → nav). Evidence: `home-denied.png`.
- **"couldn't get your location — type a place instead"** (`locPickFailed`)
  shows after a destination pick with no origin — never fabricates one.
- Consent decline persists across restart; settings toggles write back.
- The notification ask is contextual — first real air event inside the 60 s
  poll — and a denial is respected silently (`requestPerms`
  `canAskAgain===false` early-return, `notify.ts:120-132`; the OS dialog never
  re-appears, verified).
- Real local notifications deliver (stagnation event fired on-device twice,
  banner + persisted in Notification Center). Evidence: `notif-in-nc.png`.
  `events.json` dedupe verified by file inspection: `seen.stagnation` written
  only after a real delivery.

## Structural — catalogued, not fixed

- **Cold-start 100 %-CPU storm (~2–2.5 min, 3 repros; once fatal).**
  `ps` showed the process pinned at ~100 % CPU for 2:00–2:37 after launch —
  the UI is dead the whole time (taps queue and fire late). `sample` shows the
  main thread idle (mach_msg waits); the spin sits on a worker — Hermes
  bytecode-less compile and/or MapLibre style load are the candidates. One
  launch ended in the process dying mid-storm (PID gone at 30 s). On a demo
  phone this is the entire first impression; needs an Instruments run on real
  hardware to name the spinning thread.
- **Background catch-up tick accrues silently at stale speed.** 4.6 min
  backgrounded mid-nav → first resumed tick carried the whole gap:
  dose 0.2 → 2.1 µg (defensible — you kept breathing), ride emissions
  19 → 172 g (~153 g ≈ 0.9 km of driving while parked — the weaker claim).
  ETA froze correctly ("8 min · 6.1 km left"). Nothing on screen discloses the
  gap. `engine.ts` `tick()` realDt catch-up `~L479-505` + AppState pause/re-arm
  `~L542-558`. Product call: disclose "back after N min" or cap dt.
  Evidence: `bg-before.png` / `bg-after.png`.
- **Notification tap → route could not be completed on this sim.** The iOS
  26.5 simulator eats every tap on notification surfaces — in-app banner ×3,
  SpringBoard banner, NC entries ×3 incl. long-press — responses never reach
  the JS listener (an instrumented `route()` wrote a marker on launch but
  never on a tap; probe removed before commit). The listener code is in place
  and strictly better than none (previously: guaranteed dead open). Verify on
  real hardware.
- **`simctl privacy` covers location only** on this Xcode — notification
  permission cannot be revoked or granted outside the OS dialog, which is why
  `pingDenied` was code-verified but not driven on-device.

## Files touched

- `Mobile/App.tsx` — `expo-notifications` + `Linking` imports; `locDenied`
  state + pill (`~L398`, `~L1186`); `editWhich` map-pick fix
  (`onMapPress`); notification-response routing (`~L712-727`);
  `pingDenied`/`pingQuiet` destructure + props (`~L343`, `~L1145`).
- `Mobile/src/components/shell/useShellFlow.ts` — `pingDenied`, `pingQuiet`
  states (`L113-119`); `remind()` arms `pingQuiet` on null schedule (`~L500`).
- `Mobile/src/components/shell/CompareSheet.tsx` — `Linking` import;
  `pingDenied`/`pingQuiet` props (`L575-590`); depart row renders all four
  states honestly (`~L760-790`).
- `Mobile/src/components/shell/NavChrome.tsx` — no-GPS pill (`~L361-372`).
- `Mobile/src/i18n/strings.ts` — `navNoGps`, `notifDenied`, `notifTooLate`
  (en + hi).

Gates: `tsc --noEmit` clean, `expo lint` clean, `node:test` 84+76+17+16 pass.

## Sibling coverage

Android mirror of the four paths runs in a KVM child session (canonical APK
`alive108-ef5d95f.apk`); its report lands as a separate lane artifact.
