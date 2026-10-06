# Holdout-reverify report — prod /aqi vs DPCC live instruments (post-ingest)

Lane: re-run of `accuracy-holdout-report.md` after `ALIVE_DPCC_INGEST=1`
shipped to prod. GET-only probes against prod + the same DPCC 5-min
station pages; nothing tuned, nothing filtered.

One structural caveat up front: the DPCC pages are now **both** the truth
source and an ingest source — this pass can no longer measure blindness
at these sites (they're all instrumented). What it measures now is
**blend fidelity**: does the field actually serve each instrument's own
reading at its own cell, and did anything else get distorted in the
process.

- **When:** 2026-10-07, two probe rounds ≈ 02:05 / 02:29 IST
  (20:35 / 20:59 UTC), ~24 min apart.
- **Field under test:** prod `alive108-…elb.ap-south-1.amazonaws.com`,
  `build_sha=ce01ec5c`, `stations_src=waqi+dpcc`, 54 station readings
  (24 WAQI + 30 DPCC), 102 total field samples, field age ~2–15 min.
- **Truth source:** same 30 DPCC 5-min pages (raw µg/m³). Compared
  against `pm25_ambient` (pre-smoke-overlay), as before.

## Headline

| class | stations | obs | MAE µg/m³ | RMSE | bias | yesterday's MAE |
|---|---|---|---|---|---|---|
| former-GAP sites (6 named + Mundka) | 7 | 14 | **10.5** | 11.9 | +0.8 (+1.5%) | 22.8 |
| all 30 DPCC sites | 30 | 60 | **6.2** | 7.9 | +1.0 (+1.8%) | 27.1 |

Every one of the 30 station coordinates now reports
`nearest_sample_km = 0.0` — under the holdout rule (km ≤ 0.4 AND
model_km ≥ 0.5) all 30 classify LIVE-ADJ; the former GAP sites sit
1.8–7.6 km from the nearest *model* point, so what bends them is the
ingested instrument, not the model lattice. Distribution of |err|,
all-60 obs: ≤5µg 28, ≤10µg 48, ≤15µg 53, ≤20µg 60 — no observation
missed by more than 19.1 µg/m³.

## Per-station (truth → served; `**` = yesterday's GAP class)

| station | yesterday (class km) | km today | r1 true→served | r2 true→served | mean \|err\| |
|---|---|---|---|---|---|
| Alipur | live-adj 0.1 | 0.0 | 81→74.7 | 84→77.2 | 6.5 |
| Anand Vihar | anchor 0.0 | 0.0 | 34→37.7 | 34→37.8 | 3.8 |
| Ashok Vihar | anchor 0.0 | 0.0 | 41→41.6 | 41→42.2 | 0.9 |
| Dr. Karni Singh Shooting Range | live-adj 0.3 | 0.0 | 56→50.5 | 56→51.4 | 5.1 |
| Dwarka, Sector 8 | anchor 0.0 | 0.0 | 61→59.7 | 61→59.8 | 1.2 |
| Jahangirpuri | anchor 0.0 | 0.0 | 64→58.4 | 64→59.5 | 5.1 |
| Jawaharlal Nehru Stadium | live-adj 0.3 | 0.0 | 55→54.6 | 55→53.9 | 0.8 |
| Major Dhyan Chand National Stadium | live-adj 0.1 | 0.0 | 34→49.9 | 34→49.4 | 15.6 |
| Mandir Marg | anchor 0.0 | 0.0 | 47→62.3 | 47→61.2 | 14.8 |
| Mundka ** | GAP 3.4 | 0.0 | 53→55.4 | 53→55.2 | 2.3 |
| Najafgarh | live-adj 0.3 | 0.0 | 74→80.1 | 74→78.2 | 5.1 |
| Narela | anchor 0.0 | 0.0 | 86→80.9 | 86→82.0 | 4.5 |
| Nehru Nagar | anchor 0.0 | 0.0 | 38→44.7 | 38→44.2 | 6.5 |
| Okhla Phase-2 | anchor 0.0 | 0.0 | 41→47.0 | 41→46.2 | 5.6 |
| Patparganj | anchor 0.0 | 0.0 | 39→39.5 | 39→39.8 | 0.6 |
| Pooth Khurd, Bawana | anchor 0.0 | 0.0 | 68→67.7 | 68→68.3 | 0.3 |
| Punjabi Bagh | anchor 0.0 | 0.0 | 72→65.4 | 72→65.0 | 6.8 |
| Pusa | anchor 0.0 | 0.0 | 50→53.0 | 50→51.6 | 2.3 |
| R.K. Puram | anchor 0.0 | 0.0 | 59→64.3 | 59→62.1 | 4.2 |
| Rohini | anchor 0.0 | 0.0 | 62→58.0 | 62→59.3 | 3.4 |
| Sonia Vihar | anchor 0.0 | 0.0 | 67→61.5 | 67→62.8 | 4.9 |
| Sri Auribindo Marg | live-adj 0.3 | 0.0 | 40→46.4 | 40→46.0 | 6.2 |
| Vivek Vihar | anchor 0.0 | 0.0 | 57→51.3 | 57→51.9 | 5.4 |
| Wazirpur | anchor 0.0 | 0.0 | 39→42.2 | 39→42.6 | 3.4 |
| IGNOU ** | GAP 4.1 | 0.0 | 15.6→29.6 | 15.6→29.2 | 13.8 |
| JNU ** | GAP 2.7 | 0.0 | 83.6→64.5 | 83.6→65.9 | 18.4 |
| CWG Sports Complex, Akshardham ** | GAP 1.8 | 0.0 | 62.7→51.3 | 62.7→51.3 | 11.4 |
| NSUT (West Campus) ** | GAP 3.6 | 0.0 | 94.8→90.9 | 94.8→90.1 | 4.3 |
| SPM-SPC Talkatora Garden ** | GAP 1.5 | 0.0 | 54.9→62.0 | 54.9→61.6 | 6.9 |
| SBV Delhi Cantt ** | GAP 5.8 | 0.0 | 14.1→30.4 | 14.1→30.6 | 16.4 |

## The former blind spots, honestly

| station | yesterday km | km now | yesterday MAE | tonight MAE |
|---|---|---|---|---|
| Mundka | 3.4 | 0.0 | 20.1 | **2.3** |
| IGNOU | 4.1 | 0.0 | 39.1 | **13.8** |
| JNU | 2.7 | 0.0 | 7.6 | 18.4 |
| CWG Akshardham | 1.8 | 0.0 | 26.9 | **11.4** |
| NSUT West | 3.6 | 0.0 | 0.6 | 4.3 |
| Talkatora Garden | 1.5 | 0.0 | 23.2 | **6.9** |
| SBV Delhi Cantt | 5.8 | 0.0 | 41.3 | **16.4** |

Five of seven improved sharply. JNU (+18.4) and NSUT (+4.3) serve worse
than last night's *blind* numbers — but last night the flat field
happened to sit near those instruments' readings; tonight's residual is
instrument-vs-blend disagreement, not blindness. The three largest
residuals are all instruments reading far off their regional field:
JNU 83.6 vs neighbors ~55–65, SBV Cantt 14.1 and IGNOU 15.6 vs
neighbors ~30–55. At IGNOU the instrument also reports pm25/pm10 =
15.6/104 ≈ 0.15 — the same suspect-sensor signature flagged yesterday
at Rohini (3 vs 339). Where an instrument reads far off the region the
blend lands between them — hedging a possibly-glitchy sensor rather
than echoing it. Honest framing either way: those residuals are in the
MAE above, unexcluded.

## New blind spots — the honesty frontier moved to the NCR edge

`nearest_sample_km` over a 7×7 NCR scatter (lat 28.35–28.95 ×
lon 76.85–77.50, 49 cells): **36/49 cells >3 km, and every one sits
outside the instrumented ring.** Inside the DPCC+WAQI ring
(28.55–28.75 × 77.05–77.30) all cells are ≤ ~4 km, most ≤ 3 km.

| frontier | cells (examples) | nearest_sample_km |
|---|---|---|
| north rim → Sonipat side | 28.85–28.95 × 76.85–77.50 | 5.5–15.7 (worst: 28.95,76.95 = **15.7**) |
| west rim → Bahadurgarh/Rohtak side | lon 76.85–76.95, lat 28.45–28.75 | 5.5–12.4 |
| southwest → Rewari side | 28.35–28.45 × 76.95 | **12.4** |
| east rim → Ghaziabad / far Noida | lon 77.40–77.50 | 5.5–7.8 |
| south → beyond Faridabad | 28.35 × 77.10–77.20 | 7.8–7.9 |

These fringes are beyond both the instrument ring and the model fill
lattice (which ends ~28.85N / 77.45E) — the field there is
extrapolation, and the API honestly reports it (nearest_sample_km >
10 at the worst cells). The sentence is now "tight inside the
instrumented ring, coarse at the NCR fringe" — yesterday it was
"coarse even inside the city, at named stations."

## Locality sanity — does each instrument own its cell without
cratering its neighbors?

Served ambient at 3 instrumented cells vs ~3 km N/S/E/W neighbors:

| site (DPCC read) | served @site | served @ +3 km neighbors |
|---|---|---|
| NSUT West (94.8 — local peak) | 90.9 | 80.8 / 85.4 / 88.3 / 92.6 |
| SBV Delhi Cantt (14.1 — local low) | 30.4 | 45.6 / 46.0 / 47.4 / 47.8 |
| IGNOU (15.6 — local low) | 29.6 | 40.9 / 41.5 / 41.6 / 45.0 |

Each instrument pulls its own cell toward its reading (within the
blend's shrink — ~4 µg at NSUT, ~16 µg at the two low outliers), and
the pull dies within ~3 km into the regional background. No cratering
outward, no ignoring inward: a genuinely local low stays local instead
of being washed to the field mean, and a peak stays a peak.

## Temporal robustness — DPCC publishing froze mid-run

- Served field stable: every cell moved ≤ ~2 µg across the ~24-min gap.
- **29/30 DPCC pages are pinned across both rounds** — identical pm25,
  pm10 *and* page timestamp. Tree-station pages last stamped
  01:45–01:55 IST, nav-bar stations 02:00. The site itself stopped
  publishing after ~02:00 IST; the pins are a publishing stall, not 29
  simultaneous sensor deaths. Only **Alipur** advanced
  (01:50: 81 → 02:05: 84) — and it's healthy again, not yesterday's
  dying 3.0/3.0 flatline.
- Implications, honestly: r2 truth rows were 29–44 min old (same order
  as our field age — still a fair pairing, but freshness can no longer
  be proven intra-run); and if the stall runs past 90 min, our
  staleness guard drops all 30 DPCC obs and the field silently reverts
  to WAQI-only — worth watching `field.stations_status.dpcc` in
  /health, and `nearest_sample_km` at these 30 coords climbing back off
  0 is the earliest tell.

## Verdict (2 sentences, for the Builder Center article)

After DPCC ingest, the sites our independent holdout had proved blind —
up to 5.8 km from the nearest thing the field could see — now carry
their own government instruments in the blend, and the former-gap error
collapsed from 22.8 to 10.5 µg/m³ (all-30-station agreement: 6.2). The
remaining honesty frontier is no longer inside the city: it's the
unmonitored NCR fringe, 5–16 km out, which the API reports as
distance-to-nearest-real-reading rather than hiding.

## Method files

- `/tmp/hr_r1.json`, `/tmp/hr_r2.json` — per-station probe + truth rows.
- Probe script: `/tmp/holdout_reverify.py` (stdlib, GETs only; browser
  UA for ModSecurity-fronted DPCC pages; DPCC slug aliases needed for
  the site's own typos: `DwarkaSectro8` (sic), `JLNStadium`,
  `SriAurbindoMarg`).
- Station coords: `server/ingest_dpcc.py` STATIONS (registry-verified);
  model-point set for `model_km`: `airfield.py` STATIONS + fill grid.
