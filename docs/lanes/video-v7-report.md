# video-v7 — cut7 report

Cut: `scripts/video/cut7.mp4` (delivered via session attachment, not git —
beats stay in `~/video/beats`, assembled by `scripts/video/assemble.sh`).
All footage is real: app on a Pixel_7 Android emulator (the shipped
release binary **`alive108-5fd2990.apk`**, base/v2 @5fd2990 incl. the
restored "µg (micrograms)" peek-card gloss; sha256
`d354f704a339671908de2cd2dceaff41564577b15f5c041f5a6616602720041f`)
against live backend `http://65.2.28.40`; web via headless-Chrome CDP
screencast at 1920x1080. Live `/health` build_sha at record time:
**c1fbfb88** (web-overhaul-v2 on wire).

The AWS-console slot is a marked 25 s placeholder card
(`docs/plan/aws-console-shotlist.md`) — the owner films it himself.

## Beat-by-beat frame verification

Recorded ~2026-10-06 14:40–15:00 IST (web) and ~15:45–16:05 IST (app,
on the canonical binary). Numbers below were read off actual frames of
the cut, not from the API — that is the point of this table.

| slot | source file | on tape (frame-verified) |
|------|-------------|--------------------------|
| 00 title (3s) | cards/title.html | build sha `c1fbfb88` burnt in |
| 05 landing (7s) | `05_landing.mp4` (new beat) | Overhauled top fold: serif "A ledger for your lungs.", LIVE hero stat tile "1.9 cigarettes a day — a day of breathing today's field, ≈614 µg inhaled" + provenance cap (≈14.4 m³ breathed/day · 22 µg/m³-day ≈ 1 cigarette), two door tiles ("Open the live field — the city, this hour" / "Community — k≥3 aggregates only"), phone mock showing the new app home (≈32 µg hero, Where to? pill, THE MOVE card). Slow pass: daybars strip → band-washed `.dchip` district tiles (New Delhi 87, Gautam Buddha Nagar 79, Old Delhi 79, Bulandshahr 78 aqi) → pastel step tiles |
| 10 hero (10s) | `10_hero.mp4` | Statusline chips "24 stations live · field 3 min fresh · median 44 µg/m³ · wind 6 km/h · 903k edges priced"; live PM2.5 field map; WATCH THE DAY scrub h+0→h+10→now; cell captions (1,156 cells · 26.7–66.0 µg/m³ h+0 / 31.9–73.3 h+6 · 351 measured/733 interpolated/72 thin) |
| 20 home (13s) | `20_home.mp4` (emulator, shipped binary) | Overhauled home tour: hero card "you've breathed today **≈15 µg** · **7%** of ~216 µg daily · **32 m counted** · outside ~50 µg/m³ · ≈15 µg this week" + ink "Where to?" pill + 3 paper door tiles (the air map / Delhi today / your trips) → "the move — no meaningful window today · satisfactory air all day (50–64 µg/m³)" + air-quality trend bar → "your day" arc (09:54–10:02 ≈6.3 µg · 10:02–10:10 ≈5.8 µg · Auto-rickshaw least-smoky ≈2.4 µg) → band-tinted days-ahead tiles (today 56 cleanest · tomorrow 98 · thu 150 · fri 185 · sat 127) |
| 22 doors (7s) | `22_doors.mp4` (emulator) | Two door openings on tape: "Delhi today" door → **≈575 µg** hero (likely 0–1,471) + chips PM10 171.4 · NO₂ 13.9 · O₃ 184.4 · CO 421.8 · SO₂ 23.3 · US AQI 109 · "-35.1% of the 10-year average of 62" · 12 h candles 69→82 · streets (Punjab National Bank 3 trips); back to home → "your trips" door → ledger "1 trip · **≈2.4 µg** breathed · last-7-days bar · your location → India Gate · ≈70 µg less than smokiest" |
| 25 journey (15s) | `25_journey.mp4` (emulator) | Full arc as a 4-segment cut on one take: compare sheet "India Gate · Car (AC) least smoky · **our pick ≈2 µg** (2–3) · 3.74 km · arrive 10:35" + depart histogram → option cards scrolled, **Auto-rickshaw "your usual" ≈6 µg** highlighted (Bike ≈5, windows-down ≈4, other Car ≈2–3) → Start → nav ticking "smoke you breathe ≈0.1 µg · 0 kg · 3 min · 1.7 km left · arrive 10:33" → **"You're here." receipt ≈0.2 µg · smokiest way would have added ≈73 µg · 0 kg · 3.7 km · 1 min · <0.01 g PM2.5 · kept on this phone only** |
| 26 receipt (7s) | `26_receipt.mp4` (emulator) | "You're here." card held on tape: **≈0.6 µg** breathed · **132× less than by On foot** · the smokiest way would have added ≈73 µg · 0 kg · 3.7 km · 1 min · incl. <0.01 g fine dust (PM2.5) · "kept on this phone only" · Done/Share |
| 27 ledger (5s) | `27_ledger.mp4` (emulator) | Trips ledger: "**4 trips · ≈3.5 µg** breathed · all saved trips, estimates, broadly judged" + last-7-days bar + four rows "your location → India Gate" ≈0.2 / 0.3 / 0.6 / 2.4 µg · each "≈73 µg less than smokiest" · "trips stay on your phone · delete all trips" |
| 28 today (7s) | `28_today.mp4` (emulator) | App drawer on tape (Today breathed **≈3.5 µg** · this week 4 trips ≈3.5 µg · saved places: Home set / Work set / Delhi today / My vehicle auto) → "Delhi today" sheet: **≈570 µg** of fine smoke inhaled today (likely 0–1,494) · "the air is barely moving" · PM10 170.1 · NO₂ 14 · O₃ 174.7 · CO 427.8 · SO₂ 22.3 · US AQI 108 · "running -30.2% of the 10-year average of 57 µg/m³ for this hour" · next-12-h candles 70→83 · streets travellers crossed |
| 30 dosegap (18s) | `30_dosegap.mp4` | a→b armed on the field map; priced corridor readout on tape: "Car (AC) · least-smoke rd — 10.8 µg inhaled (4.4–17.2) · 31.6 km · ~36 min · lightest for you · 5 options priced in 3.4 s"; depart line "now is the light slot — dose climbs to 12.2 µg by 18:00"; 5-mode ladder Car 10.8 / Bike 33.5 / Auto 37.9 / Bicycle 159.5 / On foot 377.1 µg; budget line (109 mg vs 5.4 mg) |
| 40 city (20s) | `40_city.mp4` | Top fold: hero + "WHY TONIGHT" tinted callout (easing off the earlier high; air barely moving — stagnation line) + GRAP chip; watch-the-day plays to +5 h 19:45; reach armed → tap CP → **solved on tape**: "walk · ≤50 µg dust — 638.2 km of roads reachable · 11,805 road segments drawn" (await-eval polls #rchCap, no fixed guess); THE DAY SO FAR chips (15 recorded hours); band-washed `.day` tiles TODAY 80 / TOMORROW 103 / THURSDAY 141 / FRIDAY 161 / SATURDAY 131 + "today looks least-bad — avg ~80 vs ~129 µg/m³" line; ticker chips (PM2.5 NCR avg 42.8 · CO 386.3 · US AQI 112 · govt monitors 24 · districts 29 live · map rebuilt 10 min ago); "the ledger, today" tiles (434 breaths · 9 µg · 8 trips · 2.5 kg CO₂ · 12 streets ≥3 phones); corridor table (Punjab National Bank 3 trips 11 µg heavier-than-typical …) |
| 65 community (7s) | `65_community.mp4` | Live ledger stats: 14 phones sharing · 22 trips all-time · 3 last 24 h · 4.6 km · 2.0 µg breathed · 392 µg dodged · car ×3; "The streets enough phones have crossed" table (Outer Circle 8 trips / 6 phones / 14.6 µg / CAR / 51.3 g CO₂ per 100 m) |
| 50 admin (19s) | `50_admin.mp4` | Engine room live: statusline "UPTIME 1H · BUILD C1FBFB88 · FIELD LIVE · 70 SAMPLES · 24 STATIONS · AGE 13M"; `.kchip`/`.cap` stat tiles (field age 13m FRESH · 70 pts · donated trips 39 · publishable corridors 12 · trips switched lighter 4 · daily median 105.9 µg/m³ · cumulative dose 104 µg · CO₂ 12.7 kg · model error 11.31 µg/m³); 01·THE FIELD PIPELINE stage tiles (24 instruments → 70 model samples → σ ±14.7 → 9,03,058 edges priced); 05·THE ENGINE dose-math table + routing internals (PathEngine 10,70,459 edges / 8,19,846 nodes · graph sha 83ef9b91051bbd29 · dynamodb ledger · 21 device tokens) + measured API latency (/plan 726 ms · /aqi 177 ms · /grid 565 ms · /depart 219 ms); `.fmsel` repaint PM2.5→NO₂ on the 1,600-cell map (17 fire detections · wind 6 km/h 326°); model-grades-itself scorecard (+1h MAE 10 → +11h 64.6 · 114 pairs over 17 recorded hours) |
| 80 aws (25s) | placeholder card | marked "AWS console — owner footage · docs/plan/aws-console-shotlist.md" |
| 90 close (6s) | `90_close.mp4` | landing top-fold hold (hero stat tile + doors) |
| 99 end (5s) | cards/end.html | — |

Total slot budget: 174 s ≈ **2:54** (≤3:00 cap).

## VERIFY-V8 (folded in — apk-verify-v8 lane, slot cap)

All five checks ran on the shipped binary `alive108-5fd2990.apk` by the
footage child (pcap `tcpdump -i any host 65.2.28.40` started BEFORE
`adb install`, kept running across the whole pass; consent/share OFF
the entire drive). Verdicts + evidence (v8_*.png, c7_v8.pcap) were
uploaded with the beats; final verdict table is owned by
`devin-e866a72bcc4544ebad3e477b06b94e57`.

| check | verdict | evidence |
|-------|---------|----------|
| 1. peek-card gloss renders on Android | **PASS** | `v8_gloss_en.png` ("µg (micrograms)" on the populated map-idle card) + `v8_gloss_hi.png` ("µg (माइक्रोग्राम)") |
| 2. armed-skip closes on FIRST tap | **PASS** | `v8_armed.png` (wizard armed) → `v8_skip.png` (closed after one ✕ tap) |
| 3. 10 clean search opens | **PASS** | 10 opens, 0 crashes — no GC SIGSEGV/FATAL in logcat |
| 4. consent-off pcap | **PASS** | `c7_v8.pcap`: 42 POSTs total, **all `/v2/plan`** — zero `/v2/trip`, `/observe`, or location-write POSTs (`v8_share_off.png` shows the toggle off) |
| 5. cold-open → first real number | **≈3.4 s** | `c7_cold.mp4` force-stop → icon tap → first live number painted |

## Provenance notes

- Backend: `http://65.2.28.40` (EIP+NLB; the scripts' `alive108-…elb…`
  hostname resolves to the same service). Only GETs + `/v2/plan` +
  `/v2/reroute` were exercised; consent/share OFF before recorded nav.
- /v2/reach walk-≤50µg solve on tape returned the live engine numbers
  (11,805 edges / 638.2 km) — identical to `scripts/verify_numbers.sh`.
- App beats were recorded by child session
  `devin-f0abfff33d4e492c92434ff7d2d0298b` on a KVM Pixel_7 emulator,
  verified + recorded on the **shipped binary** `alive108-5fd2990.apk`
  (sha256 `d354f704…2720041f`, confirmed installed on the device). Each
  source clip was duration/integrity-checked (ffprobe >0 s) and
  frame-verified before assembly; the journey slot is a 4-segment cut
  of one continuous take (compare → pick → nav → receipt), same trip.
- No fake data anywhere; the AWS slot stays a placeholder per mandate.
