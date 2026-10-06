# Lane report: video-v8 — app beats re-tape on alive108-c3bb731.apk

**Date:** 2026-10-06 · **Status:** COMPLETE — all 7 beats PASS on the Android APK, 0 crashes
**Binary:** `alive108-c3bb731.apk` · sha256 `ebe3d2c327b1837727993c3610021dd63154252e4094892195b7ee58bd91cc49` ·
installed on Linux/KVM Pixel_7 emulator (android-35 google_apis x86_64) ·
backend = baked NLB `http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com` (live throughout)

Driver child session: https://app.devin.ai/sessions/25fcd5b91b104d53b0c4cff4ca83fc10
(its full evidence file: BEATS_REPORT.md — https://app.devin.ai/attachments/c84b5218-fbfe-4ffc-93ed-51ce0ec1953e/BEATS_REPORT.md)

## Why this re-tape

The demo video's app beats must show the newest UI. `c3bb731` carries:
top-pinned search row (`3d3df49` maps-grammar — was footer-pinned on the v9
binary), week card (`de01a11`), live provenance line (`419680f`), welcome
film (`16b9c2e`, fires once on fresh install), ALive·108 launcher label
(`c3bb731`). Previous cuts taped on `25bc92c`/`5fd2990` — superseded.

## Beat status (Android APK — canonical)

| beat | file | duration | verdict | on tape (frame-verified) |
|---|---|---|---|---|
| 15_welcome | [mp4](https://app.devin.ai/attachments/80c75742-4683-44b0-a576-7f8ecf67cc94/beat_15_welcome.mp4) | 43.8s | PASS | Cold launch on clean install: **welcome film** (digit-field scramble "reading Delhi's air…", ALIVE·108—DELHI NCR brackets, Skip) → resolved live **72.1 µg/m³ MODERATE · field mean over the ncr lattice** → 3-page consent pager → home ~73 µg/m³ |
| 20_home | [mp4](https://app.devin.ai/attachments/da7f4d76-9f57-4840-87f6-1b1e8e256da7/beat_20_home.mp4) | 23.4s | PASS | **top-pinned "Where to?" row** under ALive-108 header → hero ≈15 µg · 7% of ~216 · 34 m · outside ~71 → doors → the-move arc (least-bad 11:30–14:30 ≈61 vs day 84; heaviest ~18:30 ≈125) → your-day rows → **week card W–T 7 cells, today lit ≈15** → days-ahead 87/141/168/119/175 → check-in → daily budget |
| 22_doors | [mp4](https://app.devin.ai/attachments/35ca902e-23c7-4e20-a27a-4ef8078e9ffa/beat_22_doors.mp4) | 19.3s | PASS | "Delhi today": ≈942 µg + chips PM10 201.3 / NO₂ 25.7 / O₃ 59.4 / CO 657.7 / SO₂ 20.3 / US AQI 124 · −34.3% vs 10-yr avg · 12-h bars → back → trips door → populated ledger |
| 25_journey | [mp4](https://app.devin.ai/attachments/d2201cc7-b03e-4da7-b1d5-c8003410aa1e/beat_25_journey.mp4) | 91.1s | PASS | search row → "India Gate" → suggestions → compare sheet (petrol chip, sparkline now≈2→+23h≈4, ladder Car≈2→Bike≈4–5→Bus≈5) → **Bike/scooter · least smoky way · 3.29 km ≈5 µg** → Start → nav ticking dose ≈0.1→0.6 µg, km-left 3.3→0.34, arrive 18:42→18:46 → arrival |
| 26_receipt | [mp4](https://app.devin.ai/attachments/dc9f301a-3722-42ff-855b-d12d7bf32192/beat_26_receipt.mp4) | 17.1s | PASS | "You're here." ≈0.6 µg breathed · 98× less than On foot · smokiest ≈63 µg · 0 kg out · 3.2 km · 1 min · "saved — will send when back online" |
| 27_ledger | [mp4](https://app.devin.ai/attachments/bf6da4be-1d12-4a86-8979-0459440658fa/beat_27_ledger.mp4) | 11.0s | PASS | "1 trip · ≈0.6 µg breathed · all saved trips, honestly ranged" + 7-day bar (T lit) + row → India Gate · Bike/scooter · ≈63 µg less than smokiest + "trips stay on your phone" |
| 28_today | [mp4](https://app.devin.ai/attachments/61c00122-f70f-4a9f-ab87-bc02e9c39446/beat_28_today.mp4) | 31.0s | PASS | ☰ drawer (Today / This week / saved places / vehicle / share toggle) → Settings → About → "How numbers are estimated" → **provenance line held ~6s: "right now: a real monitoring instrument read ~2 km from you — that's the map's honesty, not a model guess."** |

## New-UI confirmation

| item | verdict | evidence |
|---|---|---|
| top-pinned search row | PASS | "Where to?" pill pinned under header on every home frame (20, 22, 27, 28); independently frame-verified by lane owner |
| week card (7-cell strip) | PASS | 7 weekday cells W–T with dose bars, today lit ≈15 µg (beat 20; "last 7 days" variant in 27); lane-verified |
| welcome film (fresh install) | PASS | digit-field → live 72.1 µg/m³ MODERATE → consent pager → home (beat 15, `pm clear` + fresh install); lane-verified film frame at t≈2s |
| ALive·108 launcher label | PASS | in-app header "ALive-108" + film bracket "ALIVE·108 — DELHI NCR" |
| provenance line | PASS | Settings → About → numbers explainer: "~2 km" instrument line, held ~6 s (beat 28) |

## Bugs found on this binary

**None.** Zero crashes, zero ANRs, zero "keeps stopping" dialogs, zero dead
taps attributable to the app. All MapLibre surfaces (air map, door sheets,
compare sheet, nav follow-cam) ran clean.

## Logcat summary

77.6k-line rolling logcat — grep-clean for FATAL/ANR/SIGSEGV.
**Crash count: 0** (vs ~7 SIGSEGVs seen on the iOS-simulator build of the same
code — that class is the documented iOS-sim-only MapLibre teardown, does not
reproduce on Android or real devices).

## Observations (not bugs)

- Receipt ≈0.6 µg vs compare-sheet ≈5 µg estimate: dose integrates
  concentration×time; paced mock GPS crossed 3.2 km in ~1 min of ticks — honest
  math. For a "5 µg on a scooter" narration, pace fixes at real ride time.
- Receipt footer "saved — will send when back online": share POST queues
  offline-style; numbers still rendered.
- Driver notes for future tapers: `adb emu geo fix` does NOT feed this app's
  fused location — working mock is `cmd location … set-test-provider-location gps`
  paced along the `/v2/plan` polyline (~0.55 s/fix). screenrecord under
  `-gpu guest` drops frames on heavy map transitions; stalls were retaped.
  Drawer needs scroll-to-bottom before Settings tap is stable.

## iOS interim pass (superseded context)

First driver child (macOS box — parent spec error, no Android emulation
possible) sha-verified the APK, then fell back to an iOS Release build of
`d1d8a4f` (Mobile/ byte-identical to `c3bb731` — verified `git diff` empty).
7 beats taped on iPhone sim with live backend; new-UI items confirmed except
welcome film (flag survived install-over-top) and provenance (Settings not
filmed). ~7 SIGSEGVs on plan transitions = the known iOS-sim-only MapLibre
teardown class (App.tsx documents it; no .ips written; doesn't repro on
devices). Kept as fallback footage only — iOS links available on request.
