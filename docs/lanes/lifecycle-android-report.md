# Lane — lifecycle report (real Android, KVM)

Android mirror of `lifecycle-report.md` (iOS sim): the same four
real-world behaviors driven on the canonical release APK on a KVM
emulator — kill-resume mid-nav, permission denials, a real notification
tap, a 5-minute backgrounded trip. Verdict matches iOS: honest in every
path — no dead screens, no fabricated state — with one shipped fix
(settings-card OS-denial row, which the iOS lane's compare-sheet fix
left uncovered) and catalogue items that converge with theirs.

- **Rig**: this KVM box, AVD `demo` (Android 35, google_apis x86_64,
  SwiftShader, `-no-window`), `adb root`. Geo reached the app only via
  `cmd location providers set-test-provider-location` injected to **both**
  `fused` and `gps` (`adb emu geo fix` does not reach fused on this
  image). UI driven by `uiautomator dump` + `input tap`; the image eats
  some taps — a 2 px micro-swipe registers reliably.
- **Build**: canonical release APK `alive108-ef5d95f.apk` (commit
  `ef5d95f`, sha256 `de15ae62e5a3a886a7410148c214535ca9cf0829904499f00eb9c40ff401705a`,
  137,140,424 B). **APK staleness**: predates home-truth `3088716`, so a
  denied-location hero reads generic "the air around you"; HEAD already
  shows "the air near central Delhi" — not a new bug. The APK also
  predates the iOS lane's lifecycle fixes (`App.tsx` response routing,
  `pingDenied`, `navNoGps`), so those surfaces are pre-fix here.
- **Evidence**: `docs/lanes/lifecycle-android-shots/` (33 shots, named
  per step).

## Path 1 — KILL-RESUME mid-flow: PASS (honest restart) + gap G1

Started a live trip (CP, follow mode running, dose strip accruing),
`am kill`'d the process from recents, relaunched via launcher icon.

- Relaunch lands on the **home sheet** with the ambient dose preserved
  ("you've breathed today 11 µg") — the day counter survives because
  `daylog.json` is persisted per-sample (shots 26/27).
- **No trip restore, no phantom nav sheet, no partial-trip ledger
  entry** — the trip is silently dropped. Honest restart: nothing
  claims the trip continued or completed.
- Gap **G1 (silent abandon)**: the restart never acknowledges the
  interrupted trip — no "your trip ended early" line, and the leg's dose
  is lost entirely (`donate()` only runs on the End path).
  Structural, catalogued below.

## Path 2 — PERMISSION DENIALS: PASS w/ fix F1

Fresh install → denied POST_NOTIFICATIONS at the first real ask → denied
location.

- **Notif ask timing**: the OS dialog did not fire at boot — it fired at
  the first real event the engine had something to say about (stagnation
  was live). Matches `fire()`'s "ask only when there's something real to
  say" design (`src/store/events.ts:~196`) — verified live, shot 02.
- **Denied location**: every surface degraded honestly, nothing dead —
  search gazetteer works (shots 05–08), destination pick works, the
  compare sheet renders full dose/vehicle numbers (shots 11–13), map
  drop-pin works (shots 14–16), manual plan completes. Origin silently
  falls back to last-known fused fix (`posNow()`,
  `src/components/shell/net.ts`); on a dead-cold phone the honest
  `locPickFailed` refusal exists (`useShellFlow.ts:~171,191`) — code-
  verified; on this rig the fused cache held the injected fix so the
  fallback legitimately succeeded.
- **Denied notifications**: no dead surface, no "you'll get alerts" lie.
  `requestPerms()` reads OS state, so fire() skips quietly
  (`notify.ts:~120`). The settings **re-grant path works**: toggling the
  master alerts row off→on re-fired the real OS dialog while
  `canAskAgain` was still true (shots 20–22).
- **The lie, now fixed (F1)**: with notifications OS-denied, the
  settings toggles still rendered ON — a silent failure (shot 19, toggles
  on while `NotificationManager` importance=USER-BLOCKED). Fix shipped:
  a "notifications are blocked in system settings — tap to open and
  allow" row now heads the notifications card when
  `canAskAgain === false`, re-checked on every foreground, tap →
  `Linking.openSettings()`. `src/notify.ts:133-147` (`notifPerm()`),
  `SettingsScreen.tsx:125-143` + row at ~`455-478`,
  `strings.ts` `settingsNotifBlocked` en+hi. tsc clean, `expo lint`
  clean. (Source-side fix — lands in the next APK build.)

## Path 3 — NOTIFICATION TAP: honest open on Android → deep link already fixed at HEAD

A real `stagnation` event fired through the real engine on-device —
channel `air-events`, tag `air-event-stagnation`, heads-up importance,
verbatim body "6× stiller than usual — the day's smoke will linger · 16
fires in the Punjab–Haryana belt — the wind isn't carrying it this way
right now" (dumpsys notification + shade shot 30). No staging needed —
the live field was enough.

- Tap → `PendingIntent startActivity com.anonymous.app` → resumed the
  task on the **current surface** (mid-nav sheet — live trip intact,
  strip still counting). Honest: AUTO_CANCEL, real resume, nothing
  invented (shot 31). Unlike the iOS sim — which ate every notification
  tap — **Android delivered the tap** cleanly, so the response listener
  the iOS lane landed will actually fire here.
- Deep link: none existed on this build — `notifyAirEvent` sets no
  `data` payload (`src/notify.ts:~245-275`) and nothing registered a
  response listener. **Already fixed at HEAD by the iOS lane**
  (`App.tsx:~707-727`: `air-event-*` → air map, `alive-daily-brief` /
  `alive-departure` → Delhi today). Unverified on Android until the next
  APK ships — worth one re-run of this path on the next build, since the
  OS-side delivery mechanics differ.

## Path 4 — BACKGROUND 5 min mid-trip: PASS + nit N1

Mid-nav (`≈0.3 µg`, 1.2 km left) → HOME for ~5 min while the fed fixes
kept marching ~2 km (user keeps driving) → foreground via the
notification tap.

- **Dose strip consistent + honest**: `≈0.3 → ≈2 µg` across the gap —
  `tick()` uses measured `realDt` (`src/nav/engine.ts:489-490`), so the
  backgrounded minutes are billed as real elapsed breathing time in one
  honest chunk on resume. Counting continued normally after.
- **GPS continued honestly**: AppState pause removes the watcher +
  interval (`engine.ts:542-560`), re-arms on 'active'. The position jump
  past the destination was treated as real: off-route snap →
  `postReroute` (`engine.ts:~393`) → new route "7 min · 5.2 km left ·
  arrive 23:06" (shot 32). Arrival was **not** faked; ETA recomputed;
  counters did not reset.
- Nit **N1**: for ~1–2 s after foreground the strip shows the stale
  pre-background "1.2 km left" until the first re-armed fix lands. It
  self-corrects; no marker that the read is stale. Catalogue, no fix.
- **N2 converges with the iOS lane's structural item**: the gap's dose
  chunk is billed in one catch-up tick (`engine.ts:489-491` realDt) at
  the resume position's exposure — iOS saw the identical mechanism
  (dose 0.2→2.1 µg, emissions including ~0.9 km of "driving while
  parked"). Their product call stands: disclose "back after N min" or
  cap dt. Not re-catalogued here as Android-specific.

## Catalogue — structural (file:line, not fixed)

- **G1 silent trip abandon** — `src/nav/engine.ts`: all trip state lives
  in refs (`runningRef`, `lastFixRef`, `countersRef`); nothing persists
  an in-progress trip; `donate()` runs only on End (`~L327`). A killed
  app loses the leg's dose with no marker. Fix would be a periodic
  trip-state file + resume/interrupt affordance — out of this lane's
  "small bugs" scope.
- **G2 notification deep link** — absent in the tested APK
  (`src/notify.ts:~245-275`, zero response-listener hits), but **fixed
  at HEAD** by the iOS lane's `App.tsx` response routing. Left here as a
  re-verify item for the next APK: Android taps do reach the app.
- **N1 stale strip on resume** — `engine.ts:489-549` re-arm path; the
  strip repaints on the next fix, nothing marks the interim read.
- **N2 gap-billing at landing point** — `engine.ts:489-491` realDt
  chunk × current microenv; honest but one-position-priced.
- **Not a bug — APK staleness**: generic denied-location hero label is
  the `ef5d95f` build missing `3088716`; HEAD already renders
  "the air near central Delhi".

## Delta vs the iOS lane

- They fixed compare-sheet denial states (`pingDenied`, `pingQuiet`,
  `navNoGps`); this lane's **F1** is the settings card — their build
  still showed toggles ON under OS denial there too. Complementary, not
  duplicative.
- Android ate no taps: the notification tap delivered; the off-route
  reroute path was exercised for real (iOS saw the frozen-ETA variant of
  the same gap story).
- Their cold-start CPU storm (~2 min pinned, once fatal) did **not**
  reproduce here — this release APK cold-started clean every launch
  (4+ cold launches, none >few s to interactive). Different build/
  device class; worth a hardware check on the demo phone specifically.

## What I verified vs inferred

Verified live: kill-resume restart state, every denied-permission surface,
the real stagnation ping's shade presence + tap landing, the 5-min
background accrual + off-route reroute, the OS re-grant dialog, trip-end
donation summary. Code-verified only: `locPickFailed` refusal (rig's
fused cache made it unreachable), `fire()`'s silent skip under OS denial
(permission grant timing made the window untestable on-device).
