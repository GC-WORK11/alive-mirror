# video-v6 — cut6.mp4 report

**Deliverable:** `~/video/cut6.mp4` — 168s (2:48), 1920x1080, h264, 4.35 MB.
Uploaded: https://app.devin.ai/attachments/d8d20ea1-a12a-4c2b-a8b7-306727c14beb/cut6.mp4

Assembled by `scripts/video/assemble.sh`. Title card stamps live `build_sha=f4139b24`
from the NLB. All five app beats re-recorded at base/v2 HEAD `a8edbdc` — cut5's tape
predated vibe-polish (`9b3abe4`: solid panes, nested-dim compare qualifiers, ledger
display-30 hero, receipt dose scale/stats) and coldread (`7facc34`: `µg (micrograms)`
gloss, "about"/"estimated" copy, "least smoky", `{h}h {m}m counted`, satellite-note
lines). Kept beats are byte-identical to cut5.

| Beat | Slot dur | Source (cut6) | What changed vs cut5 |
|---|---|---|---|
| `10_hero` | 11s | `~/video/beats/10_hero.mp4` — rec1_home.mp4 sparse (pts ~2–7.5) + rec3_journey.mp4 post-trip hero (pts ~677–683) | **Re-recorded.** Sparse state ("~77 µg/m³ · your count starts once the phone logs its first hours" + 3-dot progress) → populated hero `≈20 µg (micrograms)` + `9% of ~226 µg daily` + `0h 36m counted` + DoseGauge + week dots — new `unitUg` gloss + `dayCovered` + `homeWeek` strings live |
| `20_yourday` | 10s | rec3_journey.mp4 (pts ~687–697.5) | **Re-recorded.** YOUR DAY pane with accumulated segments incl. the just-finished trip row (`Car (AC) · least smoky way ≈2.6µg`), days-ahead ladder `71/101/136/147/125`, and the new `dayOutlookLoNote` line: *"faded days are past live readings — satellite estimate only"* |
| `25_journey` | 14s | rec3_journey.mp4 — compare top (pts ~578.5–583) + dose ladder (pts ~91–94, ~96.5–99.5) + nav landing (pts ~151–155) | **Re-recorded.** New qualifier copy visible: `least smoky way` + `our pick`/`safest route`/`lightest for you` nested-dim runs, `+N vs lightest` delta labels, depart-strip histogram (`leave 16:30 → breathe ~12% less`). Ladder: Car (AC) ≈3 → Bicycle ≈30 → On foot ≈66 µg. Ends on live nav (`Head out`, dose counter running) |
| `26_receipt` | 8s | rec3_journey.mp4 — receipt (pts ~540.5–545.7) + ledger (pts ~622.6–625.5) | **Re-recorded.** Arrival receipt with coldread copy: `You breathed ≈2.6 µg · about 2–3.2 µg`, `33.8× less than by On foot`, `estimated — for vehicles like yours`, `kept on this phone only`. Tail shows Trips ledger display-30 hero (`1 trip · ≈2.6 µg · ≈2.4 kg`) + trip row |
| `28_today` | 8s | rec3_journey.mp4 (pts ~632.5–641) | **Re-recorded.** DelhiToday hero `≈795 µg of fine smoke (PM2.5) inhaled today` + `the air is barely moving` + pollutant strip (PM10 233.7 · NO₂ 23.2 · O₃ 89.5 · CO 626.7 · SO₂ 25.8 · US AQI 140) + **THE NEXT 12 HOURS blend forecast `75 77 76 92`** with `satellite forecast matched to live readings` — the persistence-blend /v2/day copy that postdates cut5 |
| `30_dosegap` | 24s | cut5 beat | Kept verbatim |
| `40_city` | 24s | cut5 beat | Kept verbatim |
| `65_community` | 8s | cut5 beat | Kept verbatim |
| `50_admin` | 22s | cut5 beat | Kept verbatim |
| `80_aws` | 25s | placeholder card | Owner-filmed console slot (`docs/plan/aws-console-shotlist.md`) — drop `80_aws.mov|.mp4` into `~/video/beats/` and re-run assemble.sh |
| `00_title`/`90_close`/`99_end` | 3/6/5s | cards + cut5 beat | Kept (title re-stamps live sha at assemble time) |

Total 168s against the ≤2:50 budget with the AWS placeholder still inside.

## Recording conditions

- Build: iOS-sim Release app at base/v2 HEAD `a8edbdc`, `EXPO_PUBLIC_API_URL=http://65.2.28.40` baked at build time (sim can't resolve the ELB hostname — known quirk)
- Live API `http://65.2.28.40` — GETs + /v2/plan + /v2/reroute only; no /depart, no far-origin plan calls
- Onboarding recorded live: consent **"Keep everything on my phone"** (share OFF) before the recorded nav trip; receipt shows "kept on this phone only"
- Nav driven by real GPS waypoint stream (`simctl location start` over the actual route polyline); arrival fired at the snapped `to` vertex (~28.606,77.218, "near Motilal Nehru Place" — the India Gate hexagon approach road)
- Numbers verified against live endpoints at capture time: /v2/plan doses (car ≈3, bike/auto ≈8, bicycle ≈28–31, metro ≈27, on foot ≈66–88), /v2/day (day-mean drifted 86→71 µg/m³ through the evening shoot; days-ahead 101/136/147/125), /v2/city, DelhiToday day-dose ≈795 µg, next-12h 75/77/76/92

## Known caveats

- **Search mount unusable this shoot.** `SearchScreen` open segfaulted 6× consecutively (two app relaunches + full sim reboot incl. `Documents/` state wipe — the documented `search-open ~2/5` residual RN/keyboard-map race, SearchScreen.tsx L241–298). The journey pick therefore used the shipped **map long-press** path (`onMapLongPress` → `pick()`), which lands on the same compare sheet. The compare surface — the beat's actual target — is identical; only the entry gesture differs. First good pick was "near Motilal Nehru Place" (India Gate hexagon) rather than the search-named "India Gate" POI.
- One earlier pick (rec2 tape) reached the compare sheet + vehicle wizard via search before crashing at plan-submit; that footage is unused. The nav-dose counters and off-route `finding a new way` banner (one ~3s replay during waypoint jiggling) are live product behavior, not UI glitches.
- `10_hero` splices a sparse-home still with the same build's post-trip hero (ambient samples + the recorded trip lifted `thin` mid-shoot — honest state transition, no injected data).
- `26_receipt`'s trip is Car (AC)·least-smoky (the recommended option auto-started when the locate-FAB tap also dispatched the pending Start — the tape keeps the real `Head out` transition rather than a card re-tap; dose ≈2.6 µg vs planned auto ≈6 — same beat, different option).
- rec3 runs ~12 min of VFR; `xcrun simctl io recordVideo` writes sparse frames on stills — all beat segments were cut with output-seek (`-ss` after `-i`) + `fps=30` resample; assemble.sh's `norm()` re-pads to exact slot lengths.
- Chrome CDP (:29229) was down this session — relaunched with a scratch profile (`/tmp/chrome-cdp`) purely to render the title/end cards; no app/auth state involved.
