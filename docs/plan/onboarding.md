# Onboarding — first-run flow + consent gate

Implements doc 07 §3 ("Disclosure: one-screen plain explanation at first
launch, no dark patterns") and the doc 02 first-run expectations. Three
slides, tap-next, one persistent Skip.

## Files
- `Mobile/src/store/consent.ts` — persisted state machine
  `{ seen: boolean, sharing: "on" | "off" | null, ts: number | null }`
  in `consent.json` (document dir, expo-file-system; same File/Paths
  pattern as `src/search/recents.ts`). Exports `loadConsent`,
  `saveConsent(patch)`, `needsOnboarding()`, `clearConsent()`.
  `needsOnboarding()` is true while `!seen || sharing == null`.
- `Mobile/src/screens/OnboardingScreen.tsx` —
  `<OnboardingScreen visible lang onDone({ sharing }) />`. Persists the
  answer itself via `saveConsent`, then reports it on `onDone`.
- Strings: `onb_*` / `consent_*` in `src/i18n/strings.ts` (en + hi).

## Slides
1. **What ALive does** — one line ("every Delhi trip has an air price")
   plus the two numbers shown as sample cards: smoke you breathe
   (≈ 0.1 🚬) and smoke your ride puts out (≈ 1.4 kg). Doc 02's "one
   number per state" / comparison-first copy.
2. **Privacy promise + location primer** — plain words for doc 07 §3's
   table: no name/number/account; shared trips are trimmed at both ends
   (first/last 300 m), thinned, rounded, and counted on the H3 grid with
   a ≥3-person threshold — "a street shows only when at least 3 people
   crossed it"; location stays on the phone and only steers the map and
   navigation. This slide IS the location-permission primer: because the
   gate shows before any system prompt, the "why" always precedes the OS
   dialog. (3-slide cap → primer merged into the privacy slide rather
   than a 4th slide.)
3. **The sharing choice** — two equal-weight buttons, neither
   pre-selected: "Share trips anonymously" and "Keep everything on my
   phone", each with a one-line sub. Footnote states the skip rule
   plainly.

## Decisions
- **Skip → sharing ON.** Doc 07 §3 marks "Share anonymous trip data" on
  by default (also doc 02 §7 settings: "data sharing (on by default …
  one tap off)"). Skipping therefore adopts the documented default —
  NOT "keep on phone". Honesty guardrails: the choice slide discloses
  "skipping counts as sharing on" (`consent_footnote`), the choice is
  reversible in Settings in one tap, and `needsOnboarding()` re-arms if
  `sharing` is ever null.
- **Both choice buttons equal weight** — same size, same emphasis
  hierarchy; "share" fills accent (the doc default), "keep" is a solid
  surface button, not a ghosted link. No dark patterns.
- Whatever is picked, every feature works (doc 07 §3 opt-out: "local
  ledger still works").

## Integration seams (other lanes)
- App shell: call `needsOnboarding()` before the first
  `Location.getCurrentPositionAsync`/permission prompt and render
  `<OnboardingScreen>` over the map; on `onDone`, mirror
  `sharing` into `settings.share` (`patchSettings({ share: r.sharing === "on" })`).
- `components/shell/settings.ts` `clearAllData()` should also call
  `clearConsent()` (add `"consent.json"`) so delete-my-data re-arms the
  gate — noted, not edited here (different owner).
- Settings' existing "Share anonymous trip data" toggle should write
  `saveConsent({ sharing, ts: Date.now() })` so consent and settings
  never disagree.
