# Landing final pack — what the owner is looking at

Captured **2026-10-07 ~17:25 IST** against prod `http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com`
running **build `43913dc0`** (landing v6 + perf pass, footer tag confirms it). Driven in real Chrome via CDP —
no mocks, every number on screen is live API data. Desktop at 1440×900, phone pass at 390×844.
Media in `docs/lanes/landing-final-pack/{desktop,phone}/`; raw timings in `timing.json`.

## Felt speed (perf-pass claim, verified)

Request → live number painted, measured in-page (`#hnumV` first non-`—` mutation):

| run | document | `/v2/city` | number painted |
|---|---|---|---|
| warm TCP, cold page | ttfb 239 ms, end 472 ms | 477→715 ms | **745 ms** |
| cached doc | — | 16→255 ms | **286 ms** |
| cached doc | — | 18→417 ms | **437 ms** |

Sub-second on every repeat view. A cold-profile first-ever load from this US VM measured 4.2 s —
~3.4 s of that was document download across geography (ELB is in Mumbai), not server time; a demo-room
device in India should sit near the repeat numbers. `/v2/plan` pricing: **2.5 s** server-side (routeline says so itself).

## Shot by shot

### Boot + hero (the open)

- `boot-digit-flip.png` — the once-per-session boot strip mid-flip: faint mono digits cycling under
  "reading the live air…" with corner marks, `skip →`. This is the projector-room intro frame.
- `boot-resolved-number.png` — the flip resolving into the **real NCR mean, 35.4 µg/m³**, band-coloured
  satisfactory with `LIVE · THE NCR-WIDE AVERAGE` and `the app counts what you breathe`. Not a canned
  number — it is `/v2/city` painted after a 380 ms sweep.
- `hero.png` — first fold as a visitor lands it: `A ledger for your lungs`, the live **35.4 µg/m³**
  numeral, `a day of breathing today's air ≈ 1.6 cigarettes`, `53 INSTRUMENTS ACROSS THE NCR`.

### The proof strip

- `equation-sparkline.png` — the aqi→dose translation as an instrument equation:
  `35.4 µg/m³ × 14.4 m³/day = ≈509 µg ≈ 1.6 cigarettes`, then the live forecast sparkline
  (`next 11 hours · 55.8–68.3 µg/m³`) with `watch it move on the map ↓`, and the statusline:
  `53 stations live · map 7 min fresh · usual 35 · wind 13 km/h · 903K road segments priced`.

### The field + one-tap demo

- `field-map.png` / `field-map-demo-chip.png` — the kriged live raster over real district boundaries:
  1,156 cells, 22.6–75.1 µg/m³, cell fade = distance to nearest station; pollutant pills
  (pm2.5/us aqi/pm10), INSPECT/A→B pills, wind arrow (277°). Bottom-left: the **watch it work** chip —
  `connaught place → i.g.i. — a real trip, priced live`.
- `demo-chip.mp4` (~6 s) — the chip tapped: it fires a **real POST `/v2/plan`** (never a canned path),
  the banded route draws on the map CP→IGI over ~1.1 s, then the routeline + ladder slide in.
- `demo-route-settled.png` — settled state: `Car (AC) · least-smoke rd — 6.8 µg inhaled (2.2–11.4) ·
  18.8 km · ~27 min · lightest for you · 5 options priced in 2.5 s`; departure note
  `now is the light slot — dose climbs to 8.2 µg by 23:00`; mode ladder Car 6.8 / Bike 18.7 /
  Auto 20.1 / Bicycle 84.6 / On foot 188.8 µg; `94 mg vs 3.4 mg a year` kicker.

### Mechanics + the city, kept

- `mechanics-app.png` — measure → interpolate → dose (`95.2% of 3,550 held-out station-hours inside
  ±2σ`), `0.90 million of 1.07 million road segments priced under this hour's map`, plus the real
  Android app shot (≈32 µg breathed today) drifting on scroll.
- `city-kept-districts.png` — `the day, recorded`: typical-October hour bars with the NOW marker
  (−39% vs typical hour) and the live district rail (Central North Delhi 93 aqi worst-first).

### `/city` on live data

- `city-hero.png` — `Delhi NCR air, right now. 35 µg/m³ · satisfactory · aqi 60`, range 22.6–75.1,
  `29 districts live · easiest Rewari 42 · heaviest Central North Delhi 93`.
- `city-parali-watch.png` — the three why-tiles on measured data:
  **WHY TONIGHT** stubble smoke on the westerly wind · **GRAP** below stage I (computed, not the
  caqm call) · **PARALI WATCH** `12 fires in the Punjab–Haryana belt — a W wind at 12.9 km/h is
  carrying it toward Delhi · measured, not reported`.
- `city-districts-map.png` — the district choropleth on govt AQI colours (Rewari green, belt mustard)
  with `the hours ahead` scrubber and the `where can your lungs go?` reach planner
  (walk/cycle/auto/car × ≤25/≤50/≤100 µg).
- `city-days.png`, `city-corridors.png` — recorded-days replay strip and corridor table further down.

### `/community` on live data

- `community-hero.png` — `What Delhi breathed together — merged, never named.` + the three privacy
  rules (cut on your phone · merged never filed · 3 phones to appear).
- `community-ledger.png` — the running totals, live: **24 phones · 44 trips all-time · 5 today ·
  31.4 km today · 10.9 µg breathed · 313 µg dodged today · 1,279 µg all-time** · last shared trip
  5.0 h ago · 0 live rider flags.
- `community-corridors.png`, `community-reports.png` — top corridor table (Outer Circle etc.) and the
  reports/flag section.

### Videos

- `scroll.mp4` (desktop) / `phone/scroll.mp4` (390 px) — one continuous top→bottom pass, ~15–18 s:
  hero → equation + sparkline → live map (route still drawn) → mechanics + app shot → day bars +
  district rail → close + footer `BUILD 43913DC0`.
- `demo-chip.mp4` per width — the one-tap demo as a user would see it.

## Honest notes

- Numbers move hourly; these are the ~17:25 IST reads. DPCC's ~02:00 IST stall drops station count
  54→~24 and the surfaces re-label — not a bug.
- Screenshots are viewport-captured at CSS pixels (1440×900 / 390×844) — what a visitor literally sees.
- Phone pass is emulation-viewport-accurate, not a device; safe for layout judgement.
- Captured on Chrome 154, a US-located VM; the 4.2 s cold load is geography-dominated (see table).
