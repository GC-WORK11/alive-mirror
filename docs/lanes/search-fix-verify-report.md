# Search-fix verify report — independent regression pass on b869bd0

Lane: second-box verification of `b869bd0` ("kill residual SIGSEGV —
no programmatic focus") + `b944d7f` (i18n km/m). Fix lane reported
15/15 clean cycles on its own sim; this pass guards against a lucky
environment. **Result: the crash still reproduces — reduced, not
eliminated.** Verdict honest, evidence below.

- **When:** 2026-10-06 ~16:29–16:38 UTC.
- **Build:** fresh `expo run:ios` dev client off the working tree at
  HEAD `b869bd0` (+`b944d7f`), iPhone 17 sim `EDD9B083` (iOS 26.5),
  Metro `--clear`, `EXPO_PUBLIC_API_URL=<prod ELB>` — prod backend,
  no local server. Sim location: India Gate.

## Verdict per criterion

| # | check | result |
|---|---|---|
| a | map → 2 pans → "Where to?" ×8, zero crashes | **FAILED — 1 SIGSEGV in 8 opens (~12.5%), plus a 2nd crash on a different sheet** |
| b | sheet opens without keyboard, showing recents | PASSED (every surviving open, 8+) |
| c | tap field → keyboard raises → search → pick | PASSED |
| d | Hindi recents localized किमी/मी | PASSED (`Karol Bagh · 5.3 किमी`) |
| e | hero matches prod /aqi | PASSED (hero ~46 vs ambient 45.5 µg/m³, pm25 49.1 / US-AQI 126) |

## The crashes (unified log, exact signature)

**Crash 1 — cycle 1/8** (two map pans → tap "Where to?" → sheet
opening → app gone ~1.6 s later, SpringBoard on video):

```
16:29:53.648 launchd_sim: [UIKitApplication:com.anonymous.app[5238]]
            exited due to SIGSEGV | sent by exc handler
16:29:53.657 runningboardd: <RBSProcessExitStatus|
            domain:signal(2) code:SIGSEGV(11)>
16:29:53.649 MTLCompilerService: XPC_ERROR_CONNECTION_INVALID
```

**Crash 2 — a NEW path** (search pick → metro vehicle choice →
compare sheet mid-render "checking every way there…"):

```
16:34:23.440 launchd_sim: [UIKitApplication:com.anonymous.app[5477]]
            exited due to SIGSEGV | sent by exc handler
16:34:23.445 runningboardd: <RBSProcessExitStatus| domain:signal(2)
            code:SIGSEGV(11)>
```

## What this means

- **The focus-removal did not remove the crash.** The stealKB/focus
  hypothesis was incomplete: with zero programmatic focus, the same
  `SIGSEGV(11)` + Metal XPC signature still fires ~1.6 s after a sheet
  mount over a drawing map. Cycles 2–8 were clean — observed rate this
  sample ≈12.5% vs ~40% pre-fix, so frequency dropped, but the
  acceptance bar was zero and it failed on the first cycle.
- **The crash is not specific to the search sheet.** The second
  SIGSEGV hit the *compare* sheet's mount. That's consistent with the
  fix commit's own stated root cause — "one giant mount commit against
  the map's draw thread" — which is a mount/render race, not a
  responder-chain race. Any large sheet mounting while MapLibre draws
  can trip it.
- **Next fix target:** the mount-vs-draw commit itself — e.g. fully
  staged sheet mount (no giant first commit), or pausing/reducing map
  draw during sheet transitions. Alternatively accept "reduced crash
  rate" explicitly rather than "killed" — but the acceptance bar was
  0/8 and it failed on cycle 1.
- What genuinely landed: the open-without-keyboard grammar (b) is
  correct and consistent, keyboard-on-tap works (c), and the i18n fix
  is real (d). The behavioral change is right; the crash claim isn't.

## Evidence

- Recording (both crashes + all checks):
  `/Users/devin/screencasts/rec-c665ed8f-130d-4e77-bae4-3a64bce55084/rec-c665ed8f-130d-4e77-bae4-3a64bce55084-edited.mp4`
  (raw segments + annotations alongside).
- Crash log dump: `/tmp/sigsegv-evidence.txt`.
- Screenshots: crash-1 SpringBoard `/Users/devin/screenshots/ss_a84bdfde.png`,
  crash-2 SpringBoard `/Users/devin/screenshots/ss_3b4c0e5b.png`,
  recents no-keyboard `/Users/devin/screenshots/ss_5810c917.png`,
  keyboard-on-tap `/Users/devin/screenshots/ss_974691c3.png`,
  results `/Users/devin/screenshots/ss_6c4a2af9.png`,
  Hindi किमी `/Users/devin/screenshots/ss_428dd4ab.png`,
  Hindi hero `/Users/devin/screenshots/ss_c34bc036.png`.

## Loose ends for the next lane

- The verification sim is left with `settings.json` lang=hi — reset if
  a clean baseline matters.
- Known sim quirk hit once (not a product bug): a tap eaten while the
  map was still decelerating — retap opened fine.
- The product-side lesson stands from the holdout reports: report what
  was measured (1/8 + 1), not what was hoped (0/8).
