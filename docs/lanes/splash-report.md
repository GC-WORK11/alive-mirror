# Lane report — splash-animation: 'a → alive' launch wordmark

**Claim under test (owner, verbatim):** "when I opened the screen, I saw A —
I didn't like that. I want alive comes with the animation: 'a' then 'live'
from it, 'alive', then onboarding screen, then the things. Don't fuck many
things up."

Built and verified on the booted iPhone sim: paper splash → 'a' settles →
'l·i·v·e' sweep in letter-by-letter → beat → ~300 ms crossfade into the
existing onboarding. Returning users (consent on disk) go straight to home —
no wordmark, no replay.

- **Repo/branch:** `<owner>/Delhi-Air-108` @ `base/v2`, rebased on
  `3f9245f`
- **Device:** iOS Simulator iPhone 17, iOS 26.5, UDID
  `EDD9B083-63F1-44E6-9A7B-0A6964CC2561`, dev client `com.anonymous.app`
  (`~/dd-alive` Debug-iphonesimulator, Metro `:8081`)
- **Backend:** `EXPO_PUBLIC_API_URL=http://65.2.28.40` (prod, GET only)
- **Date:** 2026-10-08 ~20:45–21:00 local
- **Shots:** `docs/lanes/splash-shots/` — `wordmark-sequence.mp4`
  (a→alive→onboarding), `relaunch-skip.mp4` (cold relaunch → home direct),
  `sweep-contact.png` + `mid-strip.png` (per-letter proof), `f1–f6` frames

## What shipped

**`Mobile/src/components/SplashWordmark.tsx` (new, ~130 lines)** — the
wordmark overlay. One calm motion, all springs, all `useNativeDriver`:

- 'a' springs in (`damping 18 / stiffness 150 / mass 0.9`, opacity +
  12 px rise + .94→1 scale).
- 'l','i','v','e' each spring in (`damping 15 / stiffness 165`) with the
  stagger carried **inside each spring's own `delay` field**
  (`220 + i·75 ms`) — each also slides right out of a small negative
  `translateX` (−12…−42 px, deeper letters travel farther, so the word
  reads as assembling out of the 'a').
- `HOLD_MS 360` beat, then `OUT_MS 300` opacity-out on the whole overlay;
  `onDone` unmounts.
- Reduce-motion (`useReduceMotion`, OS subscription): all values snap to 1
  and the overlay dismisses after ~240 ms — instant static 'alive'.
- Styling straight from `theme.ts`: `V2T.bg` `#FAFAF7` (identical to the
  app.json `expo-splash-screen` `backgroundColor` — native splash → JS
  overlay is a paper-on-paper handoff, zero flash), `V2T.text` ink,
  `V2Type.heroXL` 62, `Satoshi-Medium` (already loaded by `useFonts`).
- 'alive' is a proper noun — verbatim glyphs, not a `t()` key (same
  precedent as OnboardingScreen).

**`Mobile/App.tsx` (+8 lines, splash path only):**
- `introMark`/`setIntroMark` + `onIntroMarkDone` beside `introSeen`.
- Mount: `{introSeen === false && introMark && <SplashWordmark …/>}` as the
  last child of the gated tree — the wordmark can only exist on the
  first-run branch; `introSeen===null` keeps the gate suspended and
  `introSeen===true` never mounts it.
- Onboarding fires `visible={introSeen === false}` regardless, so the
  sheet materializes *under* the wordmark during its hold and the 300 ms
  fade reads as the wordmark dissolving into the onboarding (visible in
  `f4-crossfade.png`). Consent flow is not delayed.

**`Mobile/app.json`** — untouched; existing splash `backgroundColor`
already equals `V2T.bg`.

## Bug found mid-flight (fixed before evidence)

First capture showed 'a' alone for ~1.8 s, then 'alive' complete — the
per-letter sweep never painted. Cause: the stagger was written as
`Animated.sequence([Animated.delay(d), Animated.spring(v, native)])`.
RN's `delayImpl` is a JS-driver `TimingAnimation` on a throwaway value
(`useNativeDriver: false` hard-coded); in this RN/bridgeless build the
sequence reported `finished` on schedule (the hold+fade fired correctly)
but the native springs' output never reached the view — letters stayed at
opacity 0. Fix: drop the sequence wrapper, carry the stagger in each
spring's native `delay` config — no JS↔native handoff inside the
composite. Re-captured on sim: sweep renders frame-by-frame
(`sweep-contact.png`, `mid-strip.png`).

## Verification

- `a→alive→onboarding` — `wordmark-sequence.mp4` (t≈15.5 'a' rises,
  t≈18.3–18.9 letters land one-by-one, hold, t≈21 crossfade, onboarding
  ~96 µg/m³ poor by t≈22.5). Fresh-install path replays on each launch
  until consent completes — used for the captures.
- **Relaunch skip** — seeded `Documents/consent.json`
  `{"seen":true,"sharing":"on",…}`, terminated, cold-launched:
  `relaunch-skip.mp4` shows paper splash → home (map + "Good morning" +
  coach tour) with **zero** wordmark or onboarding frames
  (`relaunch-contact.png`, 24 frames 4 fps).
- Reduce-motion: code-verified (synchronous `setValue(1)` + 240 ms
  dismiss); sim toggle not driven.

## Gates

- `npx tsc --noEmit` — clean
- `npx expo lint` — clean
- `npm run check:t0` — t0-index fresh (210,000 rows, 62 chunks)
- `xcodebuild … Debug-iphonesimulator` — BUILD SUCCEEDED (incremental
  rebuild after the known mid-build `npm install` stale-.o link trap)
- Ownership: diff = `Mobile/App.tsx` (splash branch only) + new
  `SplashWordmark.tsx` + this report/shots. CompareSheet/ExploreSheet/
  SearchScreen untouched.
