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
