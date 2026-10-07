# ALive-108 — THE DEMO KIT (the one file you open at the venue)

Every claim verified in-repo on `base/v2`. If a doc disagrees, the lane report wins.

`NLB = http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com` — HTTP :80
only, never `https://`/`:8000`. Prod `7c68c8bc`; truth = `curl -s $NLB/health` → `build_sha`.

## 1. THE BINARY

- **`alive108-ef5d95f.apk` — canonical freeze-cut** (`docs/lanes/apk-recut-report.md`):
  https://app.devin.ai/attachments/0febc48c-996a-420e-9d84-a426a05d163a/alive108-ef5d95f.apk
  Verify: `shasum -a 256` → `de15ae62e5a3a886a7410148c214535ca9cf0829904499f00eb9c40ff401705a`.
- **Delete first:** `70914c0` (pre-fix v10), `c3f7e9e` (old freeze, warms zero
  tiles). Never: `c3bb731` / `0b11123` (30–40 commits behind).
- **Open it once tonight** — first boot fires the notif-permission dialog and
  the vehicle wizard covers the first plan. Burn the gauntlet before the hall.

## 2. THE STAGE

- prod API / truth: `$NLB` · landing (v7 live: shipped-app hero + chooser
  film-strip): `$NLB/` · city board: `$NLB/city` · community ledger: `$NLB/community`
- admin engine room: `$NLB/admin` — flow `docs/plan/admin-login.md`; token from
  SM `alive108/admin-token` (ap-south-1), **never printed**.

## 3. THE VIDEO PROOF

- **Chooser beat:** `chooser.mp4` = freeze-dryrun session attachment
  `afbb89341aba489f936fa89ad7907460` (pinned in `landing-v7-report.md`); frames in
  `docs/lanes/landing-v7-shots/` (`choose-ff-8.5/10.5.png`, `choose-f-14.png`, `choose-strip-src.png`).
- **Rehearsal-v2, real Android:** `docs/lanes/demo-rehearsal-v2-shots/` (9 PNGs);
  videos indexed in `demo-rehearsal-v2-report.md` (01-welcome, 03-chooser,
  04-chooser-clean, 05-depart, 06-community-settings).
- **Landing pack:** `docs/lanes/landing-final-pack/desktop/` + `phone/` —
  hero/city/community PNGs + `demo-chip.mp4`, `scroll.mp4`.
- **Backup on the phone:** `docs/video/cut1.mp4` + `cut2.mp4` — play airplane-mode.

## 4. THE TRUTH CARD — `docs/lanes/judge-answers-v6.md` (10 armed; know these 5)

1. **"Citizen layer is empty"** → ~33× dose spread on the demo OD (car-AC
   10.5–12.3 vs on-foot 367–375 mid; `verify_numbers` pairing: 33.3×).
2. **"Privacy is a slide"** → k≥3 PASS live: 55 cells → 12 publishable, every
   hour bucket dark; installs honestly `null`.
3. **"What does it cost"** → 7-day AWS bill literally **$0.00** (₹0);
   `alive108-monthly` $50 budget armed.
4. **"Is it actually live"** → `curl $NLB/health` on the spot: `field_stale:false`,
   `engine:"alive_core"`, `build_sha` = deployed tag.
5. **"iOS crashes"** → Release 0/60 cold cycles; the residual is a dev-debug-only
   inspector race — a post-demo engineering item, say so.

## 5. THE MORNING — `docs/plan/demo-morning.md`

T-90 GO/NO-GO (5 checks) → T-45 pre-warm + live curls → T-30 admin sign-in → T-0.
**Pre-warm is load-bearing:** it burns the first-boot gauntlet (notif dialog +
wizard over first plan) and seeds the ambient map cache — skip it and the
signature chooser beat plays behind a sheet.

## 6. KNOWN HONEST HOLES

- **Offline pack:** verified on Android — 744 region_tiles @ `2607ce0`
  (`offline-pack-android-verify.md`); the r2 pack rides in `ef5d95f`
  (airplane-mode PASS, `apk-recut-report.md`). Any *older* APK warms zero tiles →
  ambient cache + T-45 pan is the plan if venue wifi dies; both dead → air-gapped
  still demos (gazetteer, planned nav leg, receipt, ledger, day log) — only a
  *new* plan honestly refuses → `cut1/cut2.mp4`.
- **Community counts are wire/web-only:** `contributors` / `avoided_ug_all` live
  at `curl $NLB/community` and the admin board, not on any app surface
  (rehearsal F3) — show the JSON, don't hunt the screen.
- **2 tokenless legacy `/observe` rows** inflate two corridor dose sums (Outer
  Circle 12.2→~8.1, Radial Road 4 11.5→~1.6); they age out of the 72 h window
  **Oct-8 ~06:20Z** — lapses right at demo open (`community-sanity-report.md`).
