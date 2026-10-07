# Lane report — admin console deep pass (`/admin`)

**File audited:** `server/admin.html` (the console is a server template, not `web/` — no `web/` dir exists on `base/v2`).
**Verified against:** live prod `http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com`, build `ce01ec5c`, 2026-10-06/07 UTC.
**Method:** every `/admin/api/*` endpoint is token-gated (all return 401 without the operator token — by design). Judges and the world see the **guest view**, so the pass was run as a guest: `admin.html` served locally with every other GET reverse-proxied to prod, walked section-by-section in a real browser.

## Bugs found and fixed (all pushed to `base/v2`)

| # | What was shown | What was true | Fix |
|---|---|---|---|
| 1 | cpcb row: "the prod key isn't set yet" | Key attempt runs; egress refused in-region | Copy now says the real reason |
| 2 | openaq row: "its key is ready on the box" | Owner's key is revoked (code comment says so) | Copy now says it rests until a fresh key lands |
| 3 | **dpcc missing entirely** from the sources table | `stations_status.feeds.dpcc="ok"` — live additive feed inside the 54 | New `city monitors · dpcc` row with live/dormant states |
| 4 | Table footer: "waqi first, then cpcb, then openaq — whichever answers first" | Chain is waqi **+ dpcc additive**, early-return → cpcb → openaq | Footer rewritten to the real chain |
| 5 | Guests saw "pm2.5 only — the field serves no other gases" | `/v2/city.species` publicly serves PM10/NO₂/O₃/CO/SO₂ + US AQI | Row falls back to public `CY.species` (now shows PM10 111.5 · NO₂ 21.5 · O₃ 33.1 · CO 677.5 · SO₂ 18.3 · US AQI 79) |
| 6 | Guests saw forecast "cold — warms on the first plan" | `/v2/city.next_hours` (12h) is public | Row falls back: "the next 12h served publicly · the 120h horizon unlocks for the operator" |
| 7 | Guest corridor table empty | `/v2/city.corridors` publishes the same k≥3 street cells | `rows` falls back to `CY.corridors` (10 rows render; gated-only `field_pm25` column reads —) |
| 8 | Guest "delhi's air right now" card empty | `daily.median_pm25` is gated; `pm25_stats.median` is public | Card falls back: "middle of 25 sampled points" = **50.2 µg/m³, satisfactory** |
| 9 | Guest "how wrong the map is" card empty | `/aqi.calibration` (LOO) is public | Third fallback: mae **46.1 µg/m³** labelled "live check · each monitor hidden in turn" |
| 10 | Guest donations summary empty | `/v2/city.trips` publishes identical anonymized aggregates | `dn` synthesized from public days: **39 trips · 167.6 km · 104 µg dose · 12.7 kg CO₂ · 4 cleaner picks · 966 µg + 1.97 kg avoided** |
| 11 | Guest archive tiles: 4× "nothing to show yet" | `/v2/archive` publishes counts | Tiles fill from public payload: **4/6 ist hours today · since 2026-10-05 20:00 · 32 maps all-time · last 05:00 ist · s3://alive108-air/archive/** |
| 12 | "device tokens" in trip ledger | Banned-key contract: aggregates, no identifiers | Now "anonymized phones" |
| 13 | Fires row showed STALE at 3h against the 45-min table default | Feed declares `stale_after_s=22500` (~6.25h updates) | Freshness now judged by the feed's own contract → FRESH |
| 14 | "honesty band (σ)", "gap-fill honesty", "pts", "group-hours", "9 in 10 is the covering bucket edge", "cpcb national / us epa", "ncr lattice", raw mode codes | Jargon | Renamed to plain English (uncertainty band, the ± range stamped on every gap-filled read, map points, groups of 3+ phones, upper edge of the bracket it landed in, india's national aqi bands / the us aqi scale, delhi ncr, MODE_N translation) |
| 15 | pm2.5 METH claimed "95.2% right · 3,550 checks" (stale hardcode); pm10/gas METH claimed "no monitor evidence" | Live skill shows h0 band-hit ~89%; multi-species ingest exists | Copy now generic + honest; per-species wording corrected |
| 16 | Accent was the only surface still blue `#2456D6` | Register is the forest family (city/landing/community) | `--accent #3A6844 / --accent-ink #2B4E32 / --accent-wash #EAF0E4` + 6 rgba leftovers swapped; co₂ "moving" bar de-blued to neutral slate |

## Every displayed stat → API field → live value (guest view)

**Header + cards**
- `the air map · how fresh` ← `/health.field_age_s` = ~10m (fresh; `field_stale=false`, `serving=live`)
- `map detail` ← `/aqi.field.samples` = **100 map points** · `/health.sources.stations.count` = **54 monitors**
- `trips people shared` ← `/v2/city.trips.days[*].trips` sum = **39**
- `shared streets` ← `/v2/city.trips.corridors_publishable` = **12**
- `cleaner choices` ← `days[*].switched` sum = **4**
- `delhi's air right now` ← `/v2/city.pm25_stats.median` = **50.2 µg/m³** (n=25, mean 54.8, max 85.3) — CPCB band "satisfactory"
- `smoke inhaled` ← `days[*].dose_ug` sum = **104 µg** (~2.7 µg/trip, 0.62 µg/km)
- `co₂ from shared rides` ← `days[*].co2_kg_mid` sum = **12.7 kg** (9.3 g tailpipe PM2.5)
- `how wrong the map is` ← `/aqi.calibration` = **mae 46.1 · rmse 71.9 · bias +0.3 µg/m³ · n=94**
- Provenance strip: 54 monitors → 100 forecast points → **±15.3 µg/m³** ((`pm25_hi` 84.2 ÷ `smoke_modifier` 1.08) − `pm25_ambient` 62.7) → **9,03,058 of 10,70,459 streets priced**

**Sources table** — `waqi ok · dpcc ok` (54 blended, ~10m, fresh) · `cpcb skipped` (dormant) · `openaq dormant` · `model 100 pts` (cams·open-meteo) · `wind 6.6 km/h @ 131°` · `fires 67 total / 15 belt · lift ×1.08 · 3h → FRESH` · `amazon location down (no key)` · `router live · 9,03,058 priced`

**Corridors** — 10 k≥3 rows live: hanuman lane 13 trips/10 phones, Motilal Nehru Marg 7/6, Atul Grove Road 7/6, Rajya Sabha Marg 6/5, etc. (all `<3` or non-publishable cells withheld)

**Field state** — built from `waqi+dpcc-stations+open-meteo/cams` · updated ~10m · kriging on · σ per-query · 100 cells · engine `alive_core` · species line (see #5) · grap "below stage I · index 92 · caqm declares official" · forecast "next 12h public"

**Scorecard** — live LOO check 46.1/71.9/+0.3 over 94 monitors (public); weekly/loso/replay rows honestly gated

**Why panel** — driver `stagnation`, strength 1.00, ventilation 372 m²/s vs ~3,000 typical, clears ×8.07 slower, wind 7 km/h @ 131°, fires 15 belt ×1.08 not drifting toward delhi, drift −1.8 µg/m³ over 5.8h, 25 recorded maps

**District map** — 29 boundaries live (1 thin centroid), india's national bands, species pills PM2.5/US AQI/PM10/NO₂/O₃/CO/SO₂/NH₃; +12h scrub on pm2.5 via `/grid?h=12`
**Field map** — 1,600 cells 40×40, pm2.5 27.3–90.8 µg/m³, hover inspector real, 22 fires plotted (45 outside view)

**Riders share** — 39 trips/3 days, 167.6 km, 104 µg, 12.7 kg, 4 picked cleaner, 54 cells · 12 shareable, 72h window; daybars 17/14/8 trips; modes car 82% · auto rickshaw 5% · mode unknown 5% · cycling/metro/walking 3%; co₂ split 91% moving · 1% idling · 9% cold over 28 reporting trips; journeys 62 crossings · 10 corridors; avoided 2 kg co₂ · 966 µg dose
**Archive** — 4/6 ist hours today (gaps 00:00·02:00), since 2026-10-05 20:00, 32 maps, last 05:00, s3://alive108-air
**Skill self-grade** — 219 checks / 30 recorded hours · overall mae 30.9 · bias +25.3 (over-called) · 42.2% right band; +0h: 11 graded, 4.0 miss, 89%

**Honestly gated for guests (correct behaviour):** dose-math constants, api stopwatch, road-map internals, areas-with-riders, rider reviews, busiest-hours feed rows, median-by-day rollup, weekly validation — each shows "locked — sign in as operator", never a fake number.

## Register check
Light theme, muted-expensive ✓ · one forest accent for function (chips, selected pills, share bars, links) ✓ · band colors appear only where color *means* air quality (cards' band word, district/field maps, hour strip) ✓ · no neon/cyberpunk/decorative rainbows ✓ · animated elements (fires, maps, strips) all driven by live data ✓ · banned keys — admin renders aggregates only, no token/lat/lon/uid/device text ✓
