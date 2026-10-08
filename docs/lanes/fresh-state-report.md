# Fresh-state lane — "when app is opened it should be all free for all — all empty because it's your own personalized app"

Lane owner: fresh-state. Branch `base/v2` @ 494bfcf (+this commit). Evidence dir: `docs/lanes/shots/fresh-state/`.

## Verdict

A fresh install is genuinely empty and every cold surface is a designed empty state — no seeds, no fixtures, no demo rows anywhere in the bundle or stores. One real violation found and fixed: two EN strings claimed the default 200 µg dose budget was user-chosen ("the … you set") on an install where the user never set anything. Fixed in `Mobile/src/i18n/strings.ts`; hi already read "your limit". Note: the fix landed after the on-device build — it is verified in code + gates, ships in the next build; shots below show the pre-fix bundle where that copy appears.

## How verified

- Real wipe: `simctl uninstall` + `install` of a Release dev-client build (EXPO_PUBLIC_API_URL=http://65.2.28.40 baked at build).
- Walkthrough video `cold-walkthrough.mp4` (install → onboarding → every surface cold) + `trip-and-relaunch.mp4`.
- Per-surface shots 00–16; app container `Documents/*.json` inspected before and after.
- One real driven trip (Auto-rickshaw · alt 3, ~0.4 km counted, fixes walked via `simctl location set`) → auto-arrive receipt → terminate → relaunch.

## Cold state, surface by surface (code-audited + seen on device)

| Surface | Cold state | Evidence |
|---|---|---|
| Onboarding | Two honest slides (what trips mean, consent+permissions). No marketing filler, no fake numbers. | 01, 02 |
| Home hero | "you've breathed today —" with honest "nothing counted yet" state; no fabricated first-reading. | 03 |
| Week strip | 7 stubs "nothing logged" + copy "only real readings land here — a blank day is a day the app wasn't with you, never a zero". | 04 |
| Sidebar/menu | All real rows, no badges pretending history exists. | 05 |
| Delhi-Today card | Earlier "you travelled" lie is fixed and holds: `own===0` → ownEmpty branch; on device it renders city-level data with no claim about you. | 06, `CityMoves.tsx` (`data===null` → quiet loading line, `insufficient_data` → honest note) |
| Air map peek | Empty state is a designed "nothing peeked yet" line. | 07 |
| Trips/ledger | "no trips yet" designed state; `ledger.json` absent from container until first real arrive. | 08; ledger.ts MAX_TRIPS=500, no seed |
| Search/recents | No recents; after one real search, `places.json` accrued exactly it (`recents:[Karol Bagh Metro Station]`). | 09 + container dump |
| Settings cold | English, voice ON, share anonymous data OFF (consent honored), cigarette comparison OFF, alert toggles as designed. `settings.json` has no home/work/vehicle. | 10 + dump |
| Check-in sheet | Cold renders unselected pills + honest "earns its line" verdict; nothing pre-filled. | code + walkthrough |
| Notification history | `events.json` created only when real events fire; empty cold. | container dump |
| Compare sheet | All rows live numbers from prod `/v2/plan` (Car 1.03 km ≈1 µg … On foot ≈15 µg); nothing mocked. First plan opens honest skippable vehicle wizard ("no sign-in, nothing leaves this phone"). | 12 + video |
| Persisted seeds/fixtures | None. Bundle grep: no seed/fixture/demo JSON; every store defaults empty; `Documents` at cold boot = consent/settings/places only, all user-produced. | grep + dumps |

## Persistence proof (second boot)

After one real trip, terminate + relaunch: skips onboarding (`welcome_seen_v1.json`), hero restores "7.6 µg · 25m counted", "where it accumulated" lists the ambient window + the auto-rickshaw leg, Trips shows exactly `1 trip · ≈0.9 µg · ≈0.1 kg` (your location → Karol Bagh Metro Station), `ledger.json` contains exactly that one entry. Shots 12–16.

## The one fix

`Mobile/src/i18n/strings.ts`
- `budgetWithin`: "…µg left of the {b} µg you set for today" → "…µg left of your {b} µg line for today"
- `weekDayPct`: "{p}% of the daily limit you set" → "{p}% of your daily limit"

Both claimed a user action that never happened on fresh install. hi strings were already honest (unchanged). Shots 04/10 captured the pre-fix copy; the fix is in source, gates-clean, and ships in the next build.

## Gates

`tsc --noEmit` clean · `node src/{store,nav,api,offline}/test-runner.mjs` 152/152 pass. `expo lint` not re-run this pass (string-literal-only change).

## Honest gaps

- Trip drove ~0.4 km of the 1.33 km route before auto-arrive (simctl teleport fixes are jump-capped — expected; receipt logged `endedEarly=false` path via auto-arrive, distance 0.4 km, dose 0.9 µg real).
- Full 942 MB unedited walkthrough kept off-repo; two compressed excerpts in shots dir.
