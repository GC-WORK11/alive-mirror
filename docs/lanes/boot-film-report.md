# boot-film-truth lane report — the welcome film is dead code at HEAD, not a per-launch bug

Lane scope (dispatch): resolve the contradiction between the
final-APK KVM drive (`apk-final-report.md` — saw a WELCOME FILM +
consent gate on cold open) and the day's docs (demo-script /
demo-kit — "cold open ~1-3 s, no film"). Find the film path in
Mobile; gate to fresh-install-only if it still plays. Verify the
consent gate honestly blocks data-sharing before POSTs. Measure
returning-boot cold-open→interactive TTI on iOS sim. Report to
`docs/lanes/boot-film-report.md`.

## Verdict

1. **Both docs are true — at different commits.** The KVM drive ran
   APK `alive108-ef5d95f.apk`, built at `ef5d95f` (Oct 7 07:15
   -0700). The film was unmounted by `4b8ac8a` "jank-perf" (Oct 7
   10:55 -0700), and `git merge-base --is-ancestor 4b8ac8a ef5d95f`
   is false — the APK predates the removal by ~4 h. At HEAD
   (`ba2b125`) there is **no film on any boot class**; nothing to
   gate because nothing plays.
2. **Consent gate is correct.** Fresh install → ambient beat ≤ 9 s
   → 3-page onboarding with an explicit share/no-share choice page.
   Boot-time network traffic is GETs only; the single data-sharing
   endpoint (`POST /v2/trip` donation) is `settings.share`-gated,
   written only by the consent answer or Settings.
3. **Returning-boot TTI (iPhone 17 sim, iOS 26.5, Release):**
   `app.mounted` 14-18 ms, first live home paint ~0.45-0.50 s,
   rAF-settled ~1.3 s, real tap→search-open < 2 s. The "ms opens"
   bar is met. Caveat: the process then dies at **~+20 s** on warm
   relaunches (SIGBUS, SIGSEGV — the documented boot-burst window;
   see §5).

## 1. Film-path audit at HEAD (`ba2b125`)

Boot order in `App.tsx` (line refs from this checkout):

- `loadConsent() → setIntroSeen(c.seen)` (~l.609) gates onboarding.
- `loadWelcomeSeen() → markWelcomeSeen()` writes
  `welcome_seen_v1.json` **once per install** (l.613-614). The flag
  is now write-only — nothing branches on it; it survives only so
  Settings "delete my data" (`shell/settings.ts:121
  clearWelcomeSeen()`) has a lifecycle to reset.
- `gateReady` = 4 s ambient beat / 9 s fallback (l.635-640) — the
  only first-boot delay, and it renders *under* the live home, not
  instead of it.
- `<OnboardingScreen visible={introSeen === false && gateReady}>`
  (~l.1288). Returning users (`seen:true`) never mount it.
- Location OS-ask fires only when `introSeen === true` (l.648-651)
  — i.e. after consent resolves on fresh install, immediately on
  returning boots.
- `App.tsx:448-450` comment, left by `4b8ac8a`: "the first-breath
  cinematic is retired (owner: 'slop I never asked for'); the flag
  file still writes once per install".

Grep evidence — zero live paths at HEAD:

- `WelcomeScreen` import/mount: **none** (`git rm`'d below).
- `Film|Cinematic|Lottie|firstBreath` over `Mobile/src`: only two
  stale *comments* (`store/welcome.ts` header, `settings.ts:121`).
- `wel_*` i18n keys: **0 remaining** (5 keys × en+hi removed this
  lane — they were orphaned, `StringKey = keyof typeof en` parity
  enforced by tsc).

Changes landed this lane (hygiene — make the film impossible to
silently resurrect):

- `git rm Mobile/src/screens/WelcomeScreen.tsx` (387 lines, dead
  since `4b8ac8a`, zero importers).
- `src/i18n/strings.ts`: deleted `wel_provAmbient`,
  `wel_provCity`, `wel_neverFaked`, `wel_thenBreathe`,
  `wel_delhiBreathes` from `en` and `hi` (10 keys total).

## 2. Sim evidence — fresh install (no film)

iPhone 17 sim `EDD9B083` (iOS 26.5, booted), Release-
iphonesimulator build from this checkout (+ `PERF_ON`
instrumentation, reverted pre-commit). `simctl install` → `launch`
(bundle `com.anonymous.app`, PID 17122, 17:12:50 UTC):

- l.~4 s: ambient beat resolves, onboarding page 1 visible —
  "Every Delhi trip has an air price." No film frame observed at
  any point (screenshots at 1 Hz cadence through the whole flow).
- p3 consent page: "One choice — and it's yours." → "Share trips
  anonymously" / "Keep everything on my phone" + footnote on every
  page: "Skipping counts as sharing on — either way, one tap in
  Settings undoes it."
- Tapped "Keep everything on my phone" → container written:
  `Documents/consent.json = {"seen":true,"sharing":"off"}`,
  `settings.share = false`, `welcome_seen_v1.json` present
  (written at first open, 17:12:50.784).
- Location ask appeared **after** the consent write; notification
  ask fired once post-consent on first real air event (matches
  "notification permission is lazy", demo-script §cold-open).
- The fresh-install process lived 60 s+ past launch (terminated
  manually, healthy — no warm() crash on boot 1).

## 3. Consent honesty — what can leave the phone before an answer

POST inventory at HEAD (`grep POST|post(` over `src/`):

| endpoint | call site | consent gate |
|---|---|---|
| `POST /v2/plan` | `src/api/plan.ts` | none needed — compute request, not sharing |
| `POST /v2/reroute` | `src/api/reroute.ts` | none needed — same class |
| `POST /v2/trip` donation | `src/nav/engine.ts` | `shareEnabled` ← `settings.share` ← `consent.json` only; default `false`; fires on trip arrival only; privacy-trims (300 m end-cut, 100 m thinning, 4 dp) |
| `POST /v2/feedback` | SettingsScreen | user-initiated only |

Boot-time traffic is **GETs only** (`/health`, `/reports`, `/aqi`,
`/grid` airfield) — nothing outbound carries user data before the
consent answer exists. `skip = finish("on")` (share ON) is real,
but disclosed in `consent_footnote` rendered on **every** page
including p3, and undoable in Settings — a copy decision, not an
honesty bug; the gate still blocks until a tap happens. Prior
pcap proof stands (`apk-final-report.md` line 32: consent-OFF →
POSTs only `/v2/plan` + `/v2/reroute`, zero `/v2/trip`, `/observe`,
`/report`).

## 4. Returning-boot TTI — measured

Rig: same sim/build; `simctl terminate → launch` = true warm
relaunch (consent already saved, `introSeen=true` → no onboarding,
no beat, straight to home). `simctl launch` wall-return ≈ 280-323
ms; JS marks via `src/perf.ts` `perf_log.jsonl`, t = ms since
perf-module eval (≈ launch-return + tens of ms native lead-in —
report honestly as JS-side timing):

| mark (ms) | fresh install | warm run 1 | warm run 2 | warm run 3 |
|---|---|---|---|---|
| app.mounted | 26.8 | 17.7 | 16.8 | 14.0 |
| daydata.first | 151.3 | 170.5 | 147.2 | 146.8 |
| map.rendered | 1747.8 | 448.0 | 476.3 | 498.6 |
| enter.home rAF settle | ~1796 | ~1367 | ~1345 | ~1314 |
| boot renders (total) | 4 | 29 | 29 | 29 |

- Interactivity proof, run 3: desktop tap on the "Where to?" door
  ~1.7 s post-launch → search sheet visibly open ~2.7 s
  (screenshot evidence).
- Honest read: **cold open → live map ≈ 0.45-0.50 s, fully settled
  ≈ 1.3 s, interactive < 2 s** on this sim Release build. Cross-
  platform anchor (demo-script.md §cold-open): release APK `am
  start -W` TotalTime 845 ms; offline cold relaunch → honest
  home+map 938 ms.
- Fresh install is slower to `map.rendered` (1.75 s vs ~0.48 s)
  only because the ambient beat + onboarding overlay run on top —
  by design, one per install.

## 5. Caveat — the warm-boot process death still reproduces

Not film-related, but dishonest to omit from a "returning boot"
measurement: both warm runs I let reach the window died inside it:

- run 1 (PID 17629): launch 17:13:52.6 → `runningboardd` exit
  status `signal(2) SIGBUS(10)` at 17:14:13.198 (**+20.6 s**).
- run 3 (PID 18206): launch 17:17:27.2 → exit `signal(2)
  SIGSEGV(11)` at 17:17:47.139 (**+20.0 s**).
- run 2 was force-quit at +15 s (measurement cycle), never
  reached the window.
- `[coldfix] sim GC sizing applied` logged on **all 4** launches
  → the `withAllocInYoung(false)` sim patch IS compiled into this
  binary and executing; the crash persists anyway — consistent
  with `boot-burst-report.md` ("survives only with `warm()`
  no-op'd"; the mitigation narrowed but did not close the fault
  class). No `.ips` produced on iOS-sim app death; the exit-status
  records above are the evidence.
- Demo impact: a returning boot yields ~20 s of fully interactive
  app before death — TTI itself is unaffected and demo-length
  interactions fit inside the window. Fault class is sim-only so
  far (see boot-burst rig notes; `Device.isDevice` gates
  `drawHold`; the APK class is unaffected).

## Gates

`npx tsc --noEmit` clean · `npx expo lint` clean · `node
src/{store,nav,api,offline}/test-runner.mjs` 16+76+17+16 =
**125/125 pass**. `src/perf.ts` `PERF_ON` instrumentation was
local-only and is reverted (never shipped — its own header warns
against committing it on).

## Pointers

- Dead film: `Mobile/src/screens/WelcomeScreen.tsx` (deleted),
  `App.tsx:448-450,609-651,~1288`
- Consent: `src/store/consent.ts`, `src/screens/OnboardingScreen.tsx`,
  `src/nav/engine.ts` (`shareEnabled`), `shell/settings.ts:121`
- Perf marks: `src/startup/marks.ts`, `src/perf.ts`,
  `Documents/perf_log.jsonl`
- Related lanes: `boot-burst-report.md` (crash class),
  `apk-final-report.md` (stale-APK film sighting + pcap),
  `demo-script.md` §cold-open
