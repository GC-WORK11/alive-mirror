# web-drive — public surfaces re-verified on live prod, judged cold at 390px

**Verdict: all three web-audit findings are verified fixed on prod. No stale, contradicting, or fake-looking surface found.** Every displayed number on `/`, `/city`, `/community`, and guest `/admin` traces to a live GET response; the same numbers agree across surfaces (the unified donation store holds — `/community` 40 == `/v2/city` days sum 40 == `/admin` 40). Remaining findings are all **P2** — design-law stragglers and honest-but-awkward renderings. No P0/P1.

- Driven 2026-10-07 ~03:00–03:45 UTC against prod `http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com`, **GET only**. Build served: **`aee635eb`** (14 commits behind HEAD `311fbdc` — delta = city ledger server-key + community hydrate hardening + security tripwires; landing/community/admin HTML identical to HEAD).
- Method: true-390px device metrics via CDP `Emulation.setDeviceMetricsOverride` (390×844×2, iPhone UA) — not `--window-size`, which floors at 500px. Full-page captures + scrolled viewport shots + `innerText` dumps in `web-drive-shots/`. Every claim below is a curl number or a screenshot.
- A **field rebuild landed mid-drive** (~03:20 UTC): city mean drifted 58.2 → 57.0, aqi 97 → 95, wind 6.4@112° → 7.2@108°, map-points 100 → 97. Landing, /city and /admin all tracked the new values on their own refresh cadences — the numbers are live, not stamped.

## The three fixes — re-verified live (all PASS)

| # | original finding | live evidence now | verdict |
|---|---|---|---|
| 1 HIGH | `/city` "ledger, today" served the last populated day (Oct 5's 8 trips under TODAY) | served page shows **SHARED TRIPS TODAY 1 · KM 8** = `days["2026-10-07"]{trips:1,km:8.03}` — real UTC-today key (client-side layer `e572f58` is in `aee635eb`); `city_v_v03.png` | FIXED on prod |
| 2 MED | donation truth contradicted: community 22 vs city/admin 39 | `/community` `obs_total:40` == `/v2/city` `days` sum `17+14+8+1=40` == `/admin` "SHARED TRIPS 40 across 4 days"; `today`/`obs_today` both 1; `latest_obs_age_min` real stamp (64→67 min across the drive, matches `last_ts`); `basis` names `trip_aggregates` as the one store | FIXED on prod |
| 3 MED | `/city` minimap painted 28 hardcoded dots vs "54 live instruments" | page JS `liveStations.length=53` == `field.stations` 53 == `station_readings` 53 == `/health` `stations.count` 53; dots visibly clustered on NCR boundaries in `city_minimap_390.png` beside "53 live instruments … the green squares on it" | FIXED on prod |

## Number-by-number cross-check (curl vs rendered)

`/v2/city` live: mean 57.0–58.2, median 56.4–59.2, max 70.4, aqi 95–97, days {10-03:17, 10-04:14, 10-05:8, 10-07:1}=40, cells_tracked 55, corridors_publishable 12, field.stations 53.

| surface | rendered | source | match |
|---|---|---|---|
| `/` hero | **58.2** µg/m³ · satisfactory · ≈2.6 cig | `breath.pm25_ugm3.mid` 58.2 · `cigarettes.mid` 2.65 (hi 6.24 → "worst ≈6.2") | exact |
| `/` statusline | 53 stations · field 5min · median 59 · wind 6 · 903K edges | `/health` count 53 · `pm25_stats.median` 59.2 · wind 6.4 · edges_priced 903,058 | exact |
| `/` field | 1,156 cells · 22.9–87.4 · 358 measured · 726 interpolated · 72 thin | `/grid?cells=34` 1156 feats, min 22.9 max 87.4, conf {hi:358, med:726, lo:72} | exact |
| `/` skill line | missed by 28.8 µg/m³ · 33 h · 242 pairs | `/v2/skill` overall {mae 28.8, bias +23.0, band 45.4%}, coverage.hours_graded 33, pairs 242 | exact |
| `/` districts | 29 boundaries, worst North Delhi 153 aqi | `/v2/districts` n=29, North Delhi aqi=153 served | exact |
| `/` typical | −49% vs typical hour | `typical.vs_now_pct` −48.6 (median 113.3) | exact |
| `/` edges | 0.90M of 1.07M | 903,058 / 1,070,459 | exact |
| `/` build tag | AEE635EB | `/health.build_sha` aee635eb | exact |
| `/city` hero | 58 µg/m³ · AQI 97 · range 22.9–87.4 · easiest South Delhi 74 · heaviest North Delhi 153 | same payloads (aqi 97 at shot time) | exact |
| `/city` today ledger | breaths 106 · inhaled 3 µg · trips 1 · km 8 · co₂ 0.21 kg · pm2.5 0.016 g · bus 1 | `days["2026-10-07"]` dose_ug 3.1, co2_kg_mid 0.212, pm25_g_mid 0.016, modes {bus:1} | exact |
| `/city` outlook | today 86 (72–100) · 126 · 165 · 133 · 135 · "least-bad ~86 vs ~132" | `/v2/outlook` days verbatim + `best_day.delta_vs_mean` | exact |
| `/city` archive | 7 hours saved · 7 carry forecast | `/v2/archive` recorded_count 7, gaps {0,2}, with_model 7 | exact |
| `/city` stats | 55 stretches · 12 ≥3 phones · rebuilt 5m → next 9m · error ±8.8 · nearest cell 2.2 km | `cells_tracked` 55 · `corridors_publishable` 12 · `/health` field ages · `calibration.mae_ug` 8.8 · `nearest_sample_km` 2.2 | exact |
| `/community` | 22 phones · 40 trips · 1 today · 8.0 km · 3.1 µg · 63 dodged today · 1,029 all-time · last 67 min · bus ×1 | `/community` JSON verbatim (contributors 22, obs_total 40, obs_today 1, km_today 8.0, dose_ug_today 3.1, avoided_ug_today 62.5→63, avoided_ug_all 1028.5, latest_obs_age_min 64, modes_today {bus:1}) | exact |
| `/community` streets | Outer Circle 8/6/14.6/car/51.3 → Maulana Azad 4/4/0.7/car/219.6 | `top_corridors` 5 rows verbatim, per-row devices ≥3 | exact |
| `/admin` hero | 57–58.2 · median 56.4–59.2 · worst 70 · aqi 95–97 · −49/−50% vs typical | same payloads across the rebuild | exact |
| `/admin` honesty | mae 8.8 · rmse 12.7 · bias +0.2 · 70 monitors | `/aqi.calibration` verbatim | exact |
| `/admin` σ band | ±16.8 | `(pm25_hi 92.7 / smoke 1.1) − ambient 67.5 = 16.8` at admin's own pin | exact |
| `/admin` donations | 40 trips · 175.6 km · 107 µg · 12.9 kg · 2.7 µg/trip · 0.61 µg/km · 5 picked cleaner | days sums: km 175.6, dose 107.21, co2 12.945, switched 5 | exact |
| `/admin` modes | car 32/80% · auto 2 · unk 2 · cycle/metro/walk/bus 1 each | modes union across days = 40 | exact |
| `/admin` journeys | 64 crossings · 10 journeys | corridor trips sum 64 over `corridors` n=10 | exact |
| `/admin` co₂ split | moving 91% · idle 1% · cold 9% · 29 trips | computed split = 91/1/9 over `co2_split_trips` sum 29 | exact |
| `/admin` archive | 7/9 ist · missing 00:00,02:00 · 35 all-time · since 10-05 20:00 · last 08:00 | coverage {recorded 7, gaps {0,2}} + skill.coverage.snapshots 35 | exact |
| `/admin` fires | 80 · 20 belt · viirs 74/modis 6 · 57d/23n · wind 110° away · lift ×1.1 | `/fires` 80 feats {VIIRS:74, MODIS:6} {D:57, N:23} belt 20; `/aqi.fire` modifier 1.1 wind_deg 110 | exact |
| `/admin` skill | 12-horizon table · 242 checks · 28.8 · bias +23 (over-called) · 45.4% band | `/v2/skill` verbatim incl. adverse truth | exact |
| feed table | waqi live 53 · dpcc live · cpcb dormant (route refused) · openaq dormant (key revoked) · cams live · fires live · amazon-places down (no key) | `/health.sources` + honest dormant/down states | exact + honest |

## Staleness markers — honest everywhere checked

`latest_obs_age_min` is a real stamp (64 min vs `last_ts`); field ages real (`field_age_s`, rebuilt live mid-drive); archive uses honest gaps (`status:"gap"`, "missing hours: 00:00 · 02:00"), never fabricated hours; `/today` labelled "recorded history, not a forecast" with `source: openaq-s3-climatology`; outlook partial-days labelled "first ~16h only" + "model estimate"; GRAP carries "computed here, not the official caqm call"; corridor doses "est. from donated trips"; `/community` "same day-key as the /city ledger" — true (both read the UTC day now).

## Admin guest view — clean

Guest load fires **zero** authed fetches (`/admin/api/*` → 401 verified; client rejects them pre-flight) and **no token prompt** — the `OPERATOR SIGN IN` button is the only trigger. "8 LOCKED" counters + "NOTHING TO SHOW YET — locked, sign in as operator" states on dose internals and API timing; every public panel is live truth; no demo data, no leaked internals. `admin_v_v00.png`.

## Findings (all P2 — nothing stale/contradicting/fake remains)

| sev | tag | surface | finding | evidence |
|---|---|---|---|---|
| P2 | MOBILE | `/admin` | **Horizontal overflow at 390px** — document scrollWidth 572px; two tables (feed 456px, donations 491px) push past the viewport; feed-table text clips at the right edge. Other three surfaces fit 390 clean. | `admin_v_v02.png`; CDP probe `docW=572` |
| P2 | COPY/TZ | `/` | **"refreshed 07:59 PM" has no timezone label** — `landing.html:1103` renders `cell_epoch` via `toLocaleTimeString` in the *viewer's* TZ. Value is the true field build minute; on an IST phone it reads correctly ("8:29 AM"), on any other clock it looks stale — shot on a PDT clock shows 19:59 next to "FIELD 5 MIN FRESH". `/city` stamps "UPDATED 08:44 AM IST" explicitly — same surface, two conventions. | `landing_390.png`; code line; `grid.properties.cell_epoch` |
| P2 | CONSISTENCY | `/city` vs `/community` | **Two "shared trips" windows**: `/city` contrib reads "9 trips shared in the last 3 days" (Oct 5+7) while `/community` reads "40 trips shared · all-time". Both honestly labelled, and HEAD already serves the all-time+`since` variant — but prod still shows the 3-day window until the next deploy. | `city_v_v03.png` vs `community_390.png`; HEAD city.html |
| P2 | DESIGN-LAW | `/city`, `/admin` | **Green-wash is structural on the ledger tiles** — `city.html` 15 accent-wash rules (`TRIPS SHARED TODAY`, `STREETS WE CAN SHOW`, corridor dose pills run pale green); admin 8. Largest green-dominant surface remaining; owner's law = forest is a small accent. | `city_v_v03.png`; CSS counts at `aee635eb` |
| P2 | DESIGN-LAW | `/city`, `/community` | **Serif display type persists** — city `--serif` on h1/h2 ("Delhi NCR air, right *now.*", "where the numbers come *from*"), district detail cards, day-strip caption; community h1 italic serif ("*merged,* never named."). Landing's overhaul called this the AI-template tell and killed it; the other surfaces still run it — cross-surface register split. | `city_v_v00.png`, `community_390.png`; `city.html:21,62` |
| P2 | DESIGN-LAW | all four | **<11px floor still broken**: admin 51 rules (8px×1, 8.5px×7), landing 30 (8px×1, 8.5px×6), city 33, community 17 at `aee635eb`. The 8–8.5px stragglers sit on the honesty footnotes. | CSS grep at served build |
| P2 | DESIGN-LAW | all four | **Hairlines over ambient shadows**: city 16, admin 13, landing 12 border rules; community/admin have 0 box-shadows; the chip/ticker rows read as bordered-pill catalogues. | CSS counts; `city_v_v02.png` |
| P2 | UNFURL | `/community`, `/city`, `/admin` | **`Accept: */*` still unfurls raw JSON** on `/community` (`{"obs_total":40,…}`); city/community/admin ship zero `og:`/`twitter:` meta (landing has 2). Judges pasting links get a JSON blob or nothing. | curl headers above |
| P2 | FAKE-adjacent | `/` | **Markup still ships plausible prefills** — stnHero 54 / distN 29 / edges 0.90–1.07M sit in the HTML; live 53 overwrote them on render, but a `/health` outage leaves stale-but-real-looking figures (the sin class the page otherwise refuses). | `landing_390.txt` vs served markup |
| P2 | COPY | `/` vs `/admin` | **Cadence claimed two ways** — landing "instruments report every 15 minutes" (the field rebuild cadence) vs admin "dpcc 5-minute pages" (the instrument publish rate). | strings; `field_refresh_in_s` ~730–850 |
| P2 | CONSISTENCY | `/city` | **Corridor table silently truncates** — stat says `STREETS ≥3 PHONES 12`, payload carries 10 corridors, table shows 9 (`slice(0,9)`); a counting judge sees 9 rows under a 12 headline. | `city.html:1650`; `city_v_v05.png` |
| P2 | CONSISTENCY | `/city`+`/admin` vs `/community` | **Street lists don't overlap** — corridors (Punjab National Bank…Howrah–Delhi Railway) vs community cells (Outer Circle…Maulana Azad Road). Declared-subset design (TRIPS aggregates vs traversal projection), but a judge comparing "the streets" sees disjoint sets. | corridor arrays above |
| P2 | COPY | `/city`, `/admin` | **Raw OSM casing** — "hanuman lane", "moti" lowercase in corridor tables; the app title-cases these (6ed9741) but the web surfaces don't. | `city_v_v04.png` |
| watch | — | all four | **DPCC ~02:00 IST stall** — honest-degrade machinery verified in code (timeout → `—`/empty states); dots now ride the same count, so a stall shrinks stations+claim together. Remaining wart: landing's `—` states are honest, but the markup prefills above aren't. | feeds map; `stations_status` |

## Mobile-width verdict

- `/`, `/city`, `/community`: **390px-clean** — no horizontal overflow, numerals scale, chips wrap, tables readable. `landing_390.png`, `city_390.png`, `community_390.png`.
- `/admin`: **overflows to 572px** — tables scroll sideways; functional but the one surface that doesn't fit a phone.
- Boot strip verified first-visit: digit-field resolves to the **live** 57.0 µg/m³ (caught the mid-drive rebuild), sessionStorage-gated, never fakes. `landing_boot_390.png`.

## Not verified (out of scope)

POST routes (`/v2/trip`, `/v2/plan`, `/v2/feedback`) — GET-only mandate. `/depart` interactive flow and `/v2/reach` probing (button-driven). Offline/kill-switch behaviours (covered by `testday-offline-report.md`).
