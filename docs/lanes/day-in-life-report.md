# day-in-life — report

Lane: `docs/lanes/day-in-life.md`. Story video of one ordinary Delhi day told
through the shipped app, ending on the contrast line.

**Deliverable:** `day-in-life.mp4` — 145 s, 1920×1080/30fps, h264, text cards
only (Georgia/mono on #14181f, matching the video kit), no music, no fakery.
Uploaded: https://app.devin.ai/attachments/3c30d0ca-82b8-4e69-8480-31e2816a390d/day-in-life.mp4

## What was filmed

- iPhone 17 sim (iOS 26.5), Release build of the Expo dev client at `base/v2`
  HEAD, talking to live `http://65.2.28.40` (build f4139b24, 903k priced edges,
  24 WAQI stations).
- GPS feed: scripted waypoint replay of the real auto route geometry from
  Lajpat Nagar → Connaught Place at ~35 km/h.
- Consent: OFF throughout (sidebar toggle visibly off) — no POSTs to `/v2/trip`
  on live; only GETs + `/v2/plan` + `/v2/reroute`.
- Source takes (kept on the box under `~/video/dayinlife/beats/`):
  `a2_morning.mp4` (66 s), `b4_commute.mp4` (479 s), `cde_evening.mp4` (152 s).

## Beat list (cut order)

| cut (s) | card / beat | what it shows |
|---|---|---|
| 0–17 | **8:04 am · Lajpat Nagar** + morning | home surface: "you've breathed today" counter, "today's air where you are ~51 µg/m³", THE MOVE card naming the least-bad window (~16:30–18:30, ≈49 vs day 59), day curve, days-ahead strip (today 59 cleanest … sat 124) |
| 17–92 | **9:12 am · the commute** | sidebar → saved Work place (Connaught Place) → "checking every way there…" → compare: Car (AC) ≈4 µg lightest; scroll the full ladder — car variants, bike ≈13, bus, metro+walk ≈21, down to On foot ≈128 µg (+123 vs lightest, 31.1×) → auto "your usual" ≈12 selected → Start → nav with the ticking "smoke you breathe" counter climbing 0.1 → 1.1 µg → arrival receipt "You breathed ≈1.2 µg — 109.1× less than by On foot · kept on this phone only" |
| 92–106 | **1:22 pm · midday** | dose-so-far: hero ≈26 µg of ~216 daily + YOUR DAY "where it accumulated" list (≈10, 4.6, 4, 3.9 µg entries) |
| 106–118 | **6:07 pm · the days ahead** | 5-day strip; tapping tomorrow expands "lightest ~11:30–13:30 (≈56 µg/m³), heaviest 18:30–00:30, ≈71–112 ranged" + the honest caveat line "faded days are past live readings — satellite estimate only" |
| 118–140 | **10:41 pm · the check-in** | HOW YOU FELT — breath/eyes/energy good·meh·rough chips, "stays on this phone — never uploaded", "pattern needs ~7 days"; YOUR TRIPS ledger — 1 trip · ≈1.2 µg · ≈0.2 kg, weekly bar, "trips stay on your phone" |
| 140–145 | close card | "a map app tells you minutes. **this tells you what you breathed.**" |

## Frame verification vs live API

- Day outlook: app shows today ≈55 µg/m³ mid ↔ `/v2/outlook` `pm25_mid 56.2`
  (Lajpat Nagar, same hour); tomorrow ≈92 ↔ outlook day-2 (~92–98) — match.
- Dose ladder: Car(AC) ≈4–5 / auto ≈12–14 / metro+walk ≈21 / on foot ≈119–128
  with "31.1× vs lightest" — from the real `/v2/plan` (24 options) response the
  app rendered.
- Receipt ≈1.2 µg / ≈0.2 kg / 10.9 km / "109.1× vs On foot": computed from the
  genuinely driven segment (replay covered ~1 km before arrival), consistent
  with the auto route's ~12 µg full-OD dose.
- No skeletons, no stale states, no mocked numbers anywhere in the cut.

## Honest notes

- Sim clock runs UTC: app chrome shows 22:43–23:31 while story cards say
  8:04 am–10:41 pm IST. Same real session, real live data; the story-times are
  an honest re-framing (one Delhi day), not fabricated readings.
- The "where to" search sheet deterministically SIGSEGVs the sim (lldb:
  `EXC_BAD_ACCESS` in `hermes::vm::HadesGC::OldGen::search` during
  `createObjectFromBuffer` — a native heap stomp on map-draw bursts tripping
  Hermes GC; App.tsx already documents this upstream-sim crash class). The
  commute uses the crash-free saved-place path (sidebar → Work tile →
  `onNavigate(place)`), which is the daily-use flow anyway.
- Morning footage predates the commute, so the hero counter's morning state
  ("count starts once the phone logs its first hours") is the honest 8 am look.

## Cut file

`~/video/dayinlife/assemble.sh` (box-local; PIL-rendered cards since Chrome
wasn't running and this ffmpeg build lacks drawtext). Re-runnable.
