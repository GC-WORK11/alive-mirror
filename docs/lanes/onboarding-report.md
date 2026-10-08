# onboarding-upgrade — lane report

Owner ask (first-open): "remove the loading screen and make the onboarding
screen more better." Loading screen was already dead at HEAD — this lane
redesigned the onboarding flow itself.

## Verified state at HEAD (e3a1183, before)

- `WelcomeScreen.tsx` DELETED (b4c82ce) — no per-launch film, and nothing
  else gates first-open: `needsVehicle` only flips when the first plan
  options arrive (App.tsx, useShellFlow.ts:534), not at boot.
- Fresh install sequence: splash → fonts → home+map → boot `/aqi` poll
  lands the ambient read (DayPeek "now ~N µg/m³") → `gateReady` timer
  4 s (ambient landed) / 9 s (offline fallback) → OnboardingScreen
  (3 pages + skip) → OS location dialog on `introSeen === true`.

## Audit (taste-skill/redesign-skill: what each page DID vs what it should make a Delhi person FEEL)

- **p0 "what ALive does"** — a feature tour: hero + lead + 3 stacked
  JourneyRow cards (kicker/title/1–2 subs each) + 6-icon mode strip ≈ 12
  text elements. It lectured mechanics. The one honest visceral asset —
  the live ambient read — flashed for ~4 s under the opaque sheet, then
  got covered. Nothing on the page made the user FEEL the invisible thing.
- **p1 "privacy"** — 6 text blocks (lead + k-card + 3 fact rows): a
  compliance wall; the k≥3 card was the one strong element.
- **p2 "consent"** — the honest equal choice, but wrapped in a 4-line
  body paragraph and never led with "stays on your phone".
- **location ask** — a bare OS dialog after close; its "why" lived three
  screens back inside the privacy lecture.

## What changed

`Mobile/src/screens/OnboardingScreen.tsx` rewritten — 5 steps =
**3 beats + consent + permission**:

1. **the air right now** — the boot `/aqi` ambient read carried INTO the
   sheet as the page's hero: `~N` at 96 px Satoshi-Light, band-inked
   (`bandInkIdx`), + `µg/m³` + the band word. Live prop — a field tick
   mid-tour updates it. `ambientUg == null` (offline cold open) → the
   statement "You can't see it. You still breathe it." carries the page
   alone; **no fake number, ever**.
2. **the trip arc, one idea** — "Every Delhi trip has an air price." +
   3 one-line icon rows (see the smoke before you go / it counts what
   you breathe as you go / a receipt of it when you arrive). 5 text
   elements, down from ~12. JourneyRow cards + mode strip killed.
3. **nothing personal leaves this phone** — one lead line + the k≥3 card
   kept as the proof. Fact rows killed.
4. **consent** — same equal-weight two buttons; `consent_body` reframed
   phone-first ("Your dose and your routes live on this phone…") and
   roughly halved.
5. **the location ask** — NEW: "One permission — where you are." + the
   plain-words reason + "turn on location" (fires the OS dialog) +
   "not now" (a real decline: no OS ask; the nav engine re-asks when the
   user actually needs position — nav/engine.ts:532).

Mechanics:

- `onDone({ sharing, askLocation })`; App.tsx `locAskOk` gates the
  `introSeen → requestForegroundPermissionsAsync` effect (default true —
  returning-user boot path unchanged).
- Consent persists **on the consent tap** (was: whole-flow finish) —
  quitting on the permission page can't replay the tour.
- Skip + "skipping counts as sharing on" footnote render on beats +
  consent only; on the permission page there's no skip — its two buttons
  are the choice.
- Forward swipe stops at consent (the choice needs a tap, not a drift);
  5 dots, back-swipe free.
- i18n: +11 `onb_*` keys en+hi (conversational Delhi Hindi per
  hi-glossary: लोकेशन, इजाज़त, शेयर, गुमनाम), `consent_body` reframed,
  14 dead keys removed (`onb_num*`, `onb_privacy*`, `onb_whatBody`,
  `onb_arcBDA`, `onboard_*`) — parity is compiler-enforced.

## Gates

- `npx tsc --noEmit` clean; `npx expo lint` clean.
- `node src/{store,nav,api,offline}/test-runner.mjs` — 0 failures.

## iOS-sim fresh-install verification

(rig: iPhone 17 sim EDD9B083 iOS 26.5, Debug dev client + Metro,
`EXPO_PUBLIC_API_URL=http://65.2.28.40`; fresh = `simctl uninstall` +
install — empty Documents/consent.json. Build needed `npm install`
first — partial node_modules lacked expo-build-properties and the
EXConstants "Generate app.config" phase fails on it; then the 3
patch-package patches re-applied — expo-modules-jsi needed a manual
`patch -p1` for the Swift hunks because its .generated/module.modulemap
already exists post-pod-install and makes patch-package bail.)

Screenshots: `docs/lanes/onboarding-shots/`.

1. **beat 1 — ambient** (`01-ambient.png`): live `~56 µg/m³` "satisfactory"
   at 96 px band-inked Satoshi-Light over "You can't see it. You still
   breathe it." — the invisible thing on page one, with a REAL number
   from the boot `/aqi` poll. Skip + footnote + "page 1 of 5" present.
2. **beat 2 — arc** (`02-arc.png`): "Every Delhi trip has an air price." +
   3 one-line icon rows. Swipe-left advanced (PanResponder alive).
3. **beat 3 — phone** (`03-phone.png`): "Nothing personal leaves this
   phone." + sub + forest "3+" k-card.
4. **consent** (`04-consent.png`): "One choice — and it's yours." +
   reframed body + two real buttons, no Next (choice IS the action —
   forward swipe correctly stops here). Tapped "Keep everything on my
   phone" → advanced to page 5, consent persisted immediately:
   `Documents/consent.json = {"seen":true,"sharing":"off"}` and
   `settings.json share:false`.
5. **permission** (`05-location.png`): "One permission — where you are."
   + reason + "turn on location" + "not now". Skip + footnote correctly
   HIDDEN here. Tapped "not now" → straight to Home, **no OS dialog in
   that session** (locAskOk=false did its job).
6. **home lands** (`06-home-after-notnow.png`): full Home renders —
   greeting, day peek, check-ins; location-off hint line honest
   ("turn it on for the air where you actually are").
7. **kill + relaunch** (`07-relaunch-no-onboarding.png`): app went
   straight to Home — **onboarding never re-appeared** (consent.json
   seen:true persisted). The OS location dialog DID fire on this second
   boot — that's the unchanged returning-user boot ask (`locAskOk`
   defaults true per launch, `didAskLoc` is a session ref; iOS stops
   re-showing once answered at OS level). Answered "Allow While Using
   App" → Home switched to "the air expected near you" (positioned
   read) and the easiest-hours local notification fired.

No dead taps: every control used (swipe, consent button, not-now,
OS dialog) responded; Next/Skip verified live in the AX tree. The
`[expo-notifications]` error toast in shots 01–05 is dev-client-only
chrome (can't read persisted server registration on a fresh dev
install) — it covered the Next pill's pixel hitbox but not AX, and it
does not exist in release builds.
