# Alive — THE DEMO KIT (the one file you open at the venue)

Every claim verified in-repo on `base/v2`. If a doc disagrees, the lane report wins.

`NLB = http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com` — HTTP :80
only, never `https://`/`:8000`. Prod **`6bc2b808`** (deploy-7 — transit real
names on the wire); truth = `curl -s $NLB/health` → `build_sha`.

## 1. THE BINARY — ⚠️ RE-CUT REQUIRED

- **Pinned freeze-cut** `alive108-ef5d95f.apk` (`docs/lanes/apk-recut-report.md`):
  https://app.devin.ai/attachments/0febc48c-996a-420e-9d84-a426a05d163a/alive108-ef5d95f.apk
  sha256 `de15ae62e5a3a886a7410148c214535ca9cf0829904499f00eb9c40ff401705a`.
- **BUT it predates the Oct-7 fix wave — 19 Mobile commits ahead of it**
  (`git log ef5d95f..HEAD -- Mobile/`): chooser-4-act `2590598`, visible air
  field `677dc5d`+`e1e9d22`, search t0 `c583cab`, home-truth `3088716`,
  delhi-today gate `7a2cedd`, no-welcome-film `4b8ac8a`, jargon `313ffe5`,
  `edc4666` Android-launch fix… On this binary the stage script's phone
  beats **do not exist** (v1 chooser, invisible field, welcome film, old
  search).
- **Re-cut at `e147dbd` or later — and never `d8c7b41..edc4666`** (the
  map-perf tune alone crashes Android at launch; `edc4666` is its fix).
  Delete first: `70914c0`, `c3f7e9e`. Never: `c3bb731`/`0b11123`.
- **Open the final binary once before the hall** — the first-boot gauntlet
  changed: ambient number beat → onboarding (consent page 3) → location ask;
  **no welcome film**, notif permission is lazy (fires on the first real air
  event after consent, or when you arm a reminder). The vehicle wizard still
  covers the first plan — burn it.

## 2. THE STAGE

- prod API / truth: `$NLB` · landing (v7 live: shipped-app hero + chooser
  film-strip): `$NLB/` · city board: `$NLB/city` · community ledger: `$NLB/community`
- admin engine room: `$NLB/admin` — flow `docs/plan/admin-login.md`; token from
  SM `alive108/admin-token` (ap-south-1), **never printed**.

## 3. THE VIDEO PROOF

- **Chooser beat:** `chooser.mp4` = freeze-dryrun session attachment
  `afbb89341aba489f936fa89ad7907460` (pinned in `landing-v7-report.md`); frames in
  `docs/lanes/landing-v7-shots/` (`choose-ff-8.5/10.5.png`, `choose-f-14.png`,
  `choose-strip-src.png`). ⚠️ This is the **v1** chooser film — the 4-act beat
  (`2590598`) needs a fresh capture if it goes on the landing; today's kit
  still plays the pinned one.
- **Rehearsal-v2, real Android:** `docs/lanes/demo-rehearsal-v2-shots/` (9 PNGs);
  videos indexed in `demo-rehearsal-v2-report.md`.
- **Chooser-craft iOS shots (the NEW beat):** `docs/lanes/chooser-craft-shots/` —
  `act0-frame.png`, `act1-candidate-draw.png`, `settle-bold-winner.png`,
  `pill-cleanest-and-fastest.png` / `pill-53pct-lodhi.png`.
- **Audit-fix wave shots:** `docs/lanes/shots/audit-fix/` (`06-airmap-field.png`,
  `07-airmap-variation.png`) + `docs/lanes/union-regression-shots/`
  (`airmap-after-pan.png` — field stays painted through gestures),
  `docs/lanes/home-truth-shots/` (hero + WeekSheet + WeekDetail),
  `docs/lanes/delhi-today-truth-shots/`, `docs/lanes/search-shots/`
  (`s2_ashookgali.png`, `s3_pawanbakery.png`),
  `docs/lanes/offline-verify-shots/` (airplane-mode renders).
- **Backup on the phone:** `docs/video/cut1.mp4` + `cut2.mp4` — play airplane-mode.

## 4. THE TRUTH CARD — `docs/lanes/judge-answers-v7.md` (re-armed for the wave; know these 5)

1. **"Citizen layer is empty"** → ~34× dose spread on the demo OD right now
   (car-AC 15.5 vs on-foot 535.1 mid, live `6bc2b808`); in service hours add
   "a car beats the metro by ~2.5–7×".
2. **"Privacy is a slide"** → k≥3 PASS live: 55 cells → 12 publishable, every
   hour bucket dark; installs honestly `null`.
3. **"What does it cost"** → 7-day AWS bill literally **$0.00** (₹0);
   `alive108-monthly` $50 budget armed.
4. **"Is it actually live"** → `curl $NLB/health` on the spot: `field_stale:false`,
   `engine:"alive_core"`, `build_sha` = deployed tag.
5. **"iOS crashes"** → "found one today, root-caused it, closed it" —
   the sim-Release SIGBUS class is dead (`849fd4a`: repro 9/35 →
   `withAllocInYoung(false)` → **40/40 clean** under the exact repro).
   0/60 cold launches stands; device hardware honestly unmeasured;
   the Android APK is the stage phone.

## 5. THE MORNING — `docs/plan/demo-morning.md`

T-90 GO/NO-GO (5 checks) → T-45 pre-warm + live curls → T-30 admin sign-in → T-0.
**Pre-warm is load-bearing:** it burns the first-boot gauntlet (onboarding +
wizard over first plan) and seeds the ambient map cache — skip it and the
signature chooser beat plays behind a sheet.

## 6. KNOWN HONEST HOLES

- **Binary staleness (THE hole):** the pinned APK predates the wave — see §1.
  If no re-cut lands, narrate the v1 chooser and skip the air-field /
  raw-search / no-film claims.
- **iOS SIGBUS: closed on sim, device unmeasured** (`849fd4a`,
  `sigbus-release-report.md`): YG-scavenge class root-caused,
  `withAllocInYoung(false)` → 40/40 repro-clean, all gates
  `TARGET_OS_SIMULATOR`. The ~90 s early-search caution only applies to
  a binary predating the fix — irrelevant after the required re-cut.
- **Mid-range Android feel unproven** (`map-perf-report.md`): every Android
  perf number is a SwiftShader delta (~500 ms/present floor) — covered-cap
  (0 presents under the home sheet) and follow-mode p50 501→153 ms are the
  proven deltas; pan/zoom smoothness is "verified on the emulator" only.
- **Offline pack:** verified on Android — r2 pack 744 region_tiles /
  297 resources, airplane-mode cold relaunch → rendered basemap + honest home
  in **938 ms** (`offline-verify-report.md`; the pack rides in `ef5d95f` too —
  that's pre-wave). Venue wifi dead → hotspot or air-gap (gazetteer + ledger
  still work; a *new* plan honestly refuses) → `cut1/cut2.mp4`.
- **Home surface is still a blind list offline** (C4, `offline-verify-report.md`):
  cached daylog/hero offline renders as a container without its numbers —
  honest emptiness, not fake zeros.
- **Community counts are wire/web-only:** `contributors` / `avoided_ug_all`
  live at `curl $NLB/community` and the admin board, not on any app surface
  (rehearsal F3) — show the JSON, don't hunt the screen.
- **The 2 tokenless legacy `/observe` rows** have aged out (were expiring
  Oct-8 ~06:20Z); corridor dose sums are clean now — Outer Circle 14.0 mid
  on tonight's wire (was inflated to 12.2).
- **metro+walk flicker:** GTFS service-hours dependent — absent at the
  ~02:35 IST read, present (~38–53 µg) in daytime hours. Check at T-45.
