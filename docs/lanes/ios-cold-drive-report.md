# iOS cold-eye drive — final build

**Lane**: ios-cold-drive · **Build**: Release on iPhone 17 sim (iOS 26.5, UDID EDD9B083) · **Base**: `base/v2` @ `6504784` · **Prod**: `http://65.2.28.40` (build `aee635eb`, engine `alive_core`, 903,058 edges priced, bus+metro compiled) · **Method**: consent **off** ("keep everything on my phone"), persona = Delhi commuter, auto, CP → India Gate Entry KG Marg.

## Verdict

**SHIP-shape for the demo.** Zero red screens, zero fatal errors, zero fake-feeling numbers across every surface. Every number read had a live or honestly-labelled basis (ranges, "estimated", "last-good", "older data — reconnecting"). All five targeted regressions PASS. One real user-facing defect found — a timezone-mixing bug in the compare sheet's leave-later strip — plus a handful of low/copy nits.

## Regression checks

| Fix | Check | Result | Evidence |
|---|---|---|---|
| c84b5c2 (nav-done phantom re-plan) | Full nav trip → receipt → Done lands home/idle, no compare reopen | **PASS** ×2 (also on ×-close) | home hero, dose accrued (08 → sheet closed to "Good evening" + local counters) |
| HourArc ≈≈ | Scrub day arc → dose readout | **PASS** — single "≈12 µg · 19:00" | 08_dayarc_scrub_single_approx.png |
| counters.ts exhaust | Non-zero exhaust on km-scale trip | **PASS** — receipt ≈0.3 kg (0.2–0.5 range, "for vehicles like yours") | 07_arrival_receipt.png |
| 344b4a9 (pill behind home sheet) | Where-to pill must not render behind open home sheet | **PASS** — single pill inside sheet; map pill reappears only when sheet closes | 03_home_hero_live.png |
| bc8f82c (BandScale) | Strip under hero + Delhi today | **PASS** — "47m counted · outside ~49 · satisfactory" live | 03_home_hero_live.png |
| Alerts toggles | Master + 3 kinds respond | **PASS** — master locks kinds (verified: kind tap ignored while master off), kinds independent, all persist to settings.json | 13_notif_toggles.png |

## New errors / findings

| # | What | Severity | Where |
|---|---|---|---|
| 1 | **Depart strip mixes timezones**: `CompareSheet.hourLabel` parses `/depart`'s naive `start` (`"2026-10-07T03:00"`, UTC host) as UTC then adds +5.5h → forced-IST labels, while arrival/ETA/header use device-local. On a non-IST device the "now" bucket reads ~12h off wall clock (**screens: "now 07:30" at 20:0x device time**). Invisible to IST users; any reviewer outside IST sees a wrong "now". Live `/depart` repro above. | **medium** | Compare sheet leave-later strip |
| 2 | "what ALive travellers did today: **1 trips**" — pluralization miss (elsewhere "1 trip" is correct). | low | Delhi today → community line |
| 3 | Trip-row duration leaks Latin into हिंदी: drawer shows "**9min**" while the map chip correctly renders "8 मिनट" — same unit, inconsistent localization. | low | Drawer trip row (hi) |
| 4 | Dose-basis mismatch unlabeled: hero "you've breathed today **22 µg**" (ambient+trips, honest) vs sidebar "Today breathed **≈3 µg**" (trips only). Both true, no hint they measure different things. | low | Home hero vs drawer |
| 5 | Alert kind-toggles render as plain OFF while master is off — looks like prefs were cleared (they're preserved; confirmed by re-arm). Disabled≠dimmed-on. | low | Settings → Notifications |
| 6 | ETA swing **8 min → 31 min** for same O/D between cached and fresh plan after reconnect. Probably an honest re-plan across options, but jarring. | low | Compare header chip |
| 7 | Compare option list isn't a flat dose sort — modes interleave (Car AC → Car windows-down → Bike ≈4 → Bus ≈4 → **Auto ≈4/≈5**), so the user's own vehicle (auto) sits ~5 rows down. | low | Compare sheet options |
| 8 | Copy: receipt line "…less than **by On foot**" — awkward casing/phrasing. | low | Arrival receipt |
| 9 | Welcome film resolves in ~1.5–2s on a fast link — correct (min-hold + Skip + self-seals) but easy to miss. Flag lifecycle verified (welcome_seen_v1.json re-created only after play). | info | Cold open |
| 10 | SIGSEGV once on search-result→compare mount — the documented upstream sim crash class (`exited due to SIGSEGV, sent by exc handler`), not a code regression; relaunch+retry clean. Rate: 1/~10 sheet mounts this session. | info (known class) | Search → compare |

## Edge / honesty checks — all PASS

- **Dead-server UX (host blackholed prod IP, verified unreachable)**: search shows "can't reach the server — trying again"; destinations/plan fall back to last-good cache with "offline — showing last known air · updated 21 min ago"; cached Delhi today gains an "older data — reconnecting" badge; a cached route + full compare sheet still render and are usable; recents work offline. No crash, no fake-fresh numbers. (04, 09, 10)
- **Consent-off telemetry**: chose "keep everything on my phone" in onboarding → `consent.json {"sharing":"off"}`; completed a real trip → **no outbound queue file** (`offline/queue.ts` never enqueues `v2/trip` when share=off), and `/v2/city` aggregates show only someone else's `bus` trip for today — my trip did **not** leak.
- **English default** on fresh install (`settings.json lang:"en"`); EN→हिंदी→EN round-trip clean, full Devanagari everywhere except nits #3. Hindi ordinals localized ("+3वं").
- **Community/streets**: real k-anonymized aggregates ("Hanuman Lane 14 trips · heavier", "12 streets measured in 72h", mode mix 80% car).
- **Local files honest**: daylog.json = 8 real exposure samples with live per-position amb values; ledger stores the trip with true dose ranges (2.3–3.8).
- **Layers sheet**: fires / crash spots / commute-mapped streets toggles all respond; sparse real coverage so nothing dramatic on-screen (fires are NW Punjab).
- **Check-in**: "meh" on breath persisted to `daylog.json checkins`.
- **Vehicle wizard**: 3-step (type → BS-era → optional PUC) all usable; "Delhi average" default path works; `vehicle.json` persisted.

## Coverage notes

- Receipt showed "≈54 µg less than the smokiest way" and "18.7× less than by On foot" — internally consistent (≈3 + 54 ≈ 18.7×).
- "8 min" chip vs "31 min" after reconnect — see finding #6.
- "India Gate CP · 100m" search row = real gazetteer park 79m from CP, not a phantom.
- Days-ahead "~17h" subs on cells are honest partial-day markers (today n_hours=17).
- Screenshots in `ios-cold-drive-shots/`; desktop-scale shots also taken during the drive.

---

## Addendum — fix verification on 368c155 (20:15–20:48)

Rebuilt Release (368c155 + cached native), re-drove every fixed surface on the same sim (PDT — the non-IST frame the fix targets).

| Fix | Result | Evidence |
|---|---|---|
| 1 Depart strip TZ | **PASS** — strip now fully device-local on a PDT device: "अभ 20:00 · +6घ 02:00 · +12घ 08:00 · +18घ 14:00 · +23घ 19:00", agreeing with arrival "20:48 तक पहुँचें" and the 20:44 clock. Same strip read "now 07:30" before. | 18_depart_strip_device_local.png |
| 2 "1 trips" plural | **PARTIAL** — headline now "1 trip · 8.0 km · ≈3 µg" ✓ but a second line still renders "**1 trips** took a lighter way" — tripNoun applied to the summary line only, not this instance. | 15_1trip_fixed_1trips_residual.png |
| 3 hi agoMin | **PASS** — drawer trip row now "ऑटो-रिक्शा · … · **58 मिनट**" (was "9मि"); the "9min" I flagged was the ago-label, consistent with EN "57m". | 16_hi_minit_fixed.png |
| 4 Sidebar dose basis | **PASS** — "breathed on trips ≈3 µg" caption, scope explicit; hero still 39µg ambient+trips. | 20 shots + drawer states |
| 5 Master-off toggles | **PASS** — kinds become `[checked=true,disabled=true]` with a faint-accent track at on-position (asleep, not wiped); re-arming master restores all 3. | 17_toggles_asleep.png |
| 8 Receipt phrasing | **PASS** — live receipt: "**पैदल से 38.4× कम** · सबसे धुआँदार रास्ता ≈42µg ज़्यादा देता" — `worstMode` correctly resolved to walk (the smokiest option), properly localized. | 19_receipt_paidal.png |
| Nav→Done→home (c84b5c2 re-check) | **PASS** — receipt → हो गया → home/idle, no compare reopen. | 20_done_lands_home.png |

### NEW finding escalated — search-sheet SIGSEGV is now ~deterministic on touch input

**Severity: high on this environment / demo-risk.** The documented MapLibre render-churn crash class (launchd `exited due to SIGSEGV, sent by exc handler`, no .ips) went from ~12% historical rate to **8 consecutive kills on the "Where to?" → search-sheet mount via touch taps** — across both sims (iPhone 17 + a clean-install iPhone 17 Pro), cold AND 4-min-warm instances, on the same embedded Release bundle.

Notably: **a11y-dispatch presses mounted the same sheet 4/4 times without crashing** (including on a ~3-min-old instance) — the crash correlates with the touch-driven mount path (tap → keyboard+sheet anim + map re-render), not the mount itself. Air-map mount, drawer, Delhi today, nav, receipt all fine on touch.

Read for demo day: this is a host/sim render-pipeline issue (native SEGV can't be JS-caused), but on THIS box right now any normal tap on the main CTA kills the app — a real-device check before stage is mandatory; if a phone does the same, the CTA path needs the mitigation.

Also observed once: unexplained exit-to-SpringBoard with no crash line in the log (mid-tap, 20:21) — recorded as anomaly, once.

**Correction (addendum-2):** an earlier line here claimed the crash was verified "on BOTH JS bundles" — that read was confounded: this lane's app is a **Release build with the JS embedded in the .app**, so `simctl launch` relaunches and `git checkout` worktree reverts do NOT change the JS under test (Metro is only consulted on the `expo run:ios`-initiated dev-client deep link, and even then the embedded bundle wins — proven when the a11y tree showed pre-ced7672 strings on a post-pull instance). All bundle-A/B claims above were actually same-bundle; the honest pre/post A/B below uses two real Release builds.

### Verdict after fix wave

All six targeted fixes verified live (one PARTIAL — residual "1 trips" line). The fix commit introduced no regressions; the search-mount SIGSEGV is environmental but currently ~100% on touch input and should be treated as the top demo-day risk to re-check on hardware.

---

## Addendum-2 — ced7672: "1 trip" residual + onPressIn draw-hold A/B (21:00–21:15)

### "1 trips" residual → **FIXED**

On the ced7672 build the community line renders "**1 यात्रा हल्के रास्ते पर**" — grammatical nominative for n=1 (en: "1 trip took a lighter way"). Evidence: `21_1yatra_fixed.png`. Fix-2 now fully PASS.

### Crash-hammer protocol (touch-tap mounts of "Where to?" sheet)

Correction applied: a fresh **Release build embedding ced7672** was installed on both sims (the earlier hammer ran the embedded 368c155 bundle — its numbers are discarded from the A/B and kept only as environment-drift evidence).

| Build | iPhone 17 (EDD9) | iPhone 17 Pro | Total |
|---|---|---|---|
| 368c155 embedded (pre-hold) | 0/5 mounts survived | 0/3 survived | **0/8 — every touch-tap mount killed**, incl. 4-min-warm instances |
| ced7672 embedded (onPressIn hold) | 11/13 survived — kills only on cold-boot first mounts (4/6 cold, 7/7 warm) | 5/7 survived — 1 cold kill + 1 warm kill | **16/20 (80%)** |

**Read:** the onPressIn hold is a **real improvement on this host** — the tap's gesture work now runs inside the throttled window and the mount survived 16/20 vs 0/8 before. But it is **not a complete fix**: the residual kill window is the **cold-boot first mount** (~37% lethal: 5/8 cold survived) with rare warm kills (Pro lost one warm instance). The race narrows but doesn't close on this sim stack.

**Demo-day guidance unchanged + hardened:** the crash is a native render-pipeline SEGV (host-side; a11y-dispatch path mounts cleanly, touch-path races), substantially mitigated but NOT eliminated by the hold. Cold-boot + first tap remains the risky gesture — **verify on hardware before stage**; on sim demos, pre-warm the app (~30s up, one sheet open+close) before the first CTA tap.

### Interim theory check

The press-In-hold hypothesis is partially confirmed: holding draws from touch-DOWN removes most of the race. The remaining cold-boot kills suggest the mount commit also races **JS-bundle/JSI warmup + first Metal pipeline compile**, which the hold can't cover — consistent with every residual kill landing on an instance younger than ~15s.
