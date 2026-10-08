# Lane report — onboarding-gate: first-surface onboarding + one-time flags

**Claim under test (owner, verbatim):** "when you open the app you go to the
home screen, but then the onboarding screen came. Onboarding should be ONE
TIME only — first time opening — and it should come FIRST rather than the
home screen. It shouldn't come every time."

Two defects, both reproduced-and-fixed: **FLASH** (home painted before
onboarding on first boot) and **REPLAY** (onboarding re-appearing on later
opens). Verified on a fresh-installed dev client on the booted iPhone sim.

- **Repo/branch:** `<owner>/Delhi-Air-108` @ `base/v2`, commit
  `347153e` (rebased on `1243cbb`)
- **Device:** iOS Simulator iPhone 17, iOS 26.5, UDID
  `EDD9B083-63F1-44E6-9A7B-0A6964CC2561`, dev client `com.anonymous.app`
  (built this session: `~/dd-alive` Debug-iphonesimulator)
- **Backend:** `EXPO_PUBLIC_API_URL=http://65.2.28.40` (prod, GET only)
- **Date:** 2026-10-08, ~04:50–05:00 local
- **Shots:** `docs/lanes/onboarding-gate-shots/` (device-truth via
  `simctl io screenshot`)

## Mechanism — why home flashed first

`AppInner` mounted the full overlay tree (home sheet, search bar, chrome,
coach tour) the moment fonts resolved — while `introSeen` was still `null`
mid-read of `consent.json`. The consent sheet itself was gated behind a
deliberate `gateReady` beat (`ambientUg != null ? 4000 : 9000` ms) whose
comment sold it as "value first, consent second". Net effect on a cold
install: **home painted, then onboarding slid over it up to 9 s later** —
exactly the owner's repro.

## Mechanism — why it replayed

`consent.json` (and `welcome_seen_v1.json` / `coach_tour_seen_v1.json`)
were written with a non-atomic `File.create()` + `File.write()` and no
`.bak`. A kill mid-write (OS reaps the app on swipe-up during the onboarding
write, or any crash) left a torn file; `JSON.parse` threw → the catch
returned `seen:false` → **permanent replay loop on every later launch**.
Second contributor: `clearConsent` had no `wipeGen` guard — a queued
pre-wipe `saveConsent` could resurrect the file post-clear.

## Fix

**FLASH (App.tsx):**
- Root render gate: `if (!fontsLoaded || introSeen === null) return
  <View>{mapTree}</View>` — until `consent.json` resolves, the only
  committed surface is the map (which pre-mounts under the splash for the
  tile-warm head start either way). Nothing home-like can paint.
- `gateReady` state + its 4 s/9 s effect **deleted** — the sheet now mounts
  at `visible={introSeen === false}`, the instant the flag says unseen.
  First surface = onboarding, not onboarding-over-home.
- Gate sits after all `AppInner` hooks (last hook `onTourDone` ~L1279,
  gate ~L1330) — no conditional-hooks hazard.

**REPLAY (flag stores → safefile):**
- `consent.ts`, `welcome.ts`, `tour.ts` rewritten onto `safefile.ts`:
  atomic `tmp → .bak → move` writes via `writeJsonDoc`, `.bak` read-fallback
  via `readJsonDoc` — a torn main reads the previous good generation
  instead of `seen:false`.
- `clearConsent` hardened: `wipeGen += 1`, `inflight = null`,
  `purgeJsonDoc` (main + `.tmp` + `.bak`) — same resurrection guard as
  daylog/settings (queued pre-wipe saves die with the wipe).
- Added `resetConsentCache`/`resetWelcomeCache`/`resetTourCache` test
  seams so tests can simulate relaunch (drop the module mirror → disk
  re-read) — same pattern as `resetLedgerCache`.

Distinct flags preserved: consent gate, retired-welcome flag, coach tour
keep separate stores; tour still mounts once on first landing
(`tourSeen===false && introSeen===true && homeOpen && phase==="idle"`).

## Tests

`Mobile/src/store/onboarding.test.ts` — 9 cases, all green under
`node src/store/test-runner.mjs` (98/98 store total, nav 94, api 37,
offline 16; `tsc --noEmit` + `expo lint` clean):

- fresh install reads `seen:false`
- `seen:true` written once **survives a relaunch** (cache reset → disk
  re-read)
- a sharing-only save never clobbers `seen` (the patchSettings merge path)
- concurrent saves serialize — `seen` lands and stays
- **torn main falls back to `.bak`** — the exact old replay wound
- `clearConsent` wipes main+`.tmp`+`.bak` and re-arms
- welcome + coach-tour flags: same persist/clear one-time rules

## Sim drive — verified on the real build

Container: `…/Devices/EDD9B083-…/data/Containers/Data/Application/1D0E1F0E-…`

| step | evidence | result |
|---|---|---|
| fresh install → launch, t+4 s | `00-…t4` | onboarding page-1 is the ONLY surface — no home sheet, no "Where to?" bar anywhere |
| same boot, t+8 s | `01-…t8` | still onboarding (ambient read mid-flight on its own line) — no home underneath |
| earlier install, t+12 s | `02-…t12` | onboarding live with real ambient "~64 µg/m³" on page-1 |
| drive: 3× Next → "Share trips anonymously" → "not now" | — | lands home ("Up late", 64 µg/m³) |
| `Documents/` post-consent | — | `consent.json {"seen":true,"sharing":"on","ts":…}` + `consent.json.bak` (atomic), `welcome_seen_v1.json` + `coach_tour_seen_v1.json` both `seen:true` |
| force-quit + relaunch 1 | `03-…relaunch1` | **home directly — zero onboarding, zero tour** (iOS location ask fires per documented returning-user path) |
| force-quit + relaunch 2 | `04-…relaunch2` | **home directly again — zero onboarding, zero tour** |

Coach tour: `coach_tour_seen_v1.json` written `seen:true` during the first
landing — its one-time rule intact and exercised on the same drive.

## Not verified

- **Android**: this macOS box has no KVM/HVF (`kern.hv_support=0`) — no
  Android emulator possible. Store-layer logic is platform-agnostic JS and
  the safefile path is the same code the shipped APK ran; the
  Android-specific risk (lifecycle kill mid-write) is what the atomic
  write + `.bak` fallback was built against. Flagging for the next Linux
  rig pass.
- **OTA-upgraded installs** (not fresh): same code path — the flag read is
  identical regardless of which build wrote it; old-format
  `{"seen":true,"sharing":…}` records read correctly (schema unchanged).
