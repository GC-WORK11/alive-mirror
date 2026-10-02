# Field validation — model vs OpenAQ archive ground truth

## What was compared

- **Truth**: hourly PM2.5 medians at CAAQMS stations from the public OpenAQ S3 archive (`records/csv.gz`, anonymous reads). Archive pull: 2026-10-02T18:37Z, 86 stations reporting, freshest row 2026-09-30T00:00:00+05:30.
- **Model**: the same field the API serves — Open-Meteo/CAMS pm2_5 over the 48-point NCR grid, kriged (`krige.KrigeField`) with advection-weighted IDW fallback, rebuilt per IST hour from archived Open-Meteo hourly output.
- **Window**: 2026-09-28 01:00:00+05:30 → 2026-09-30 00:00:00+05:30 IST (~48h trailing; the archive lags real time ~1-2 days, so a live `/aqi` pull cannot overlap it — the model is reconstructed for the same hours from the identical upstream).
- **Not included**: the OpenAQ live-instrument blend (API key dead — the deployed field is pure model today, which is exactly what this validates) and the community corridor layer.

## Headline

| pairs | stations | MAE µg/m³ | RMSE µg/m³ | bias µg/m³ | bias % |
|---|---|---|---|---|---|
| 3550 | 85 | 47.1 | 50.7 | +45.1 | +150.6% |

IDW-only fallback (no kriging): MAE 46.4, RMSE 50.0, bias +44.5 (+148.6%) — kriging does not beat IDW on this window.

## Per-station (n≥6 pairs, sorted by |bias%|)

| station | n | obs µg/m³ | model µg/m³ | MAE | RMSE | bias % |
|---|---|---|---|---|---|---|
| IGNOU_Maidan Garhi, Delhi - DPCC-6224597 | 45 | 7 | 82 | 75 | 75 | +1002% |
| Cantonment Area, Delhi - DPCC-6227749 | 45 | 10 | 77 | 67 | 68 | +695% |
| Govindpuram, Ghaziabad - UPPCB-6281265 | 45 | 11 | 78 | 67 | 67 | +588% |
| JNU, Delhi - DPCC-6224594 | 45 | 13 | 82 | 69 | 70 | +525% |
| Amity University, Panchgaon - IITM-3379939 | 45 | 12 | 64 | 52 | 53 | +447% |
| Major Dhyan Chand National Stadium, Delhi - DPCC-6929 | 35 | 14 | 75 | 61 | 61 | +432% |
| Wazirpur | 39 | 16 | 69 | 54 | 54 | +346% |
| Sardar Patel Inter College, Baghpat - UPPCB-311989 | 42 | 16 | 73 | 56 | 58 | +339% |
| Sri Aurobindo Marg, Delhi - DPCC-10484 | 45 | 19 | 82 | 63 | 64 | +332% |
| SRM University, Modinagar - UPPCB-6269545 | 20 | 19 | 77 | 57 | 58 | +295% |
| Yamunapuram, Bulandshahr - UPPCB-6985 | 45 | 22 | 84 | 63 | 64 | +291% |
| NSIT Dwarka, Delhi - CPCB-5622 | 41 | 19 | 74 | 55 | 56 | +285% |
| Anand Vihar, Hapur - UPPCB-8319 | 45 | 20 | 77 | 57 | 58 | +283% |
| IGI Airport (T3), Delhi - IMD-5650 | 45 | 21 | 80 | 59 | 59 | +276% |
| Nehru Nagar | 38 | 22 | 81 | 60 | 61 | +275% |
| Dr. Karni Singh Shooting Range, Delhi - DPCC-6934 | 43 | 22 | 82 | 60 | 61 | +267% |
| Lodhi Road | 45 | 22 | 81 | 59 | 60 | +265% |
| Patparganj | 29 | 20 | 69 | 49 | 50 | +250% |
| Kalindi Kunj, Khurja - UPPCB-357040 | 45 | 24 | 82 | 58 | 59 | +246% |
| Alipur, Delhi - DPCC-6932 | 42 | 20 | 69 | 49 | 51 | +242% |
| Ashok Vihar | 17 | 20 | 69 | 49 | 49 | +239% |
| Okhla Ph-2 | 45 | 25 | 82 | 57 | 58 | +229% |
| Mundka, Delhi - DPCC-10486 | 44 | 21 | 70 | 49 | 51 | +229% |
| Nathu Colony, Ballabgarh - HSPCB-6972 | 45 | 25 | 82 | 57 | 57 | +227% |
| NASA GSFC Rutgers Calib. N8-2994922 | 41 | 20 | 64 | 44 | 45 | +226% |
| Sanjay Nagar, Ghaziabad - UPPCB-10919 | 45 | 24 | 77 | 53 | 55 | +226% |
| Shadipur | 41 | 21 | 69 | 48 | 48 | +223% |
| Wave City, Ghaziabad - UPPCB-6428455 | 43 | 25 | 80 | 55 | 57 | +219% |
| Najafgarh, Delhi - DPCC-10488 | 29 | 21 | 65 | 45 | 46 | +216% |
| Ved Vihar-Loni, Ghaziabad - UPPCB-6269620 | 44 | 22 | 70 | 47 | 48 | +212% |
| Vikas Sadan, Gurugram - HSPCB-301 | 45 | 25 | 77 | 52 | 53 | +212% |
| Noida Sec-125 | 45 | 28 | 82 | 55 | 57 | +192% |
| CRRI Mathura Road, Delhi - IMD-5627 | 45 | 28 | 81 | 53 | 54 | +186% |
| IIT Delhi, Delhi - IITM-6118616 | 45 | 29 | 82 | 53 | 54 | +186% |
| Aya Nagar | 44 | 29 | 82 | 52 | 54 | +181% |
| Narela | 44 | 26 | 69 | 43 | 45 | +168% |
| NISE Gwal Pahari, Gurugram - IMD-10921 | 45 | 31 | 82 | 51 | 54 | +167% |
| Talkatora Garden, Delhi - DPCC-6224525 | 45 | 27 | 72 | 45 | 46 | +163% |
| RK Puram | 44 | 31 | 82 | 50 | 52 | +159% |
| Dwarka Sec-8 | 42 | 32 | 81 | 49 | 51 | +154% |
| Knowledge Park - III, Greater Noida - UPPCB-6978 | 45 | 35 | 88 | 53 | 55 | +154% |
| Anand Vihar | 43 | 27 | 69 | 42 | 44 | +153% |
| Rohini | 44 | 28 | 69 | 42 | 44 | +152% |
| DTU | 44 | 28 | 69 | 42 | 45 | +151% |
| Vivek Vihar | 45 | 28 | 69 | 41 | 44 | +147% |
| Sonia Vihar | 44 | 28 | 69 | 41 | 44 | +147% |
| Sector 30, Faridabad - HSPCB-10820 | 45 | 34 | 83 | 49 | 49 | +144% |
| Prashant Garden, Khora - UPPCB-6269436 | 45 | 30 | 72 | 43 | 44 | +142% |
| Burari | 43 | 29 | 69 | 40 | 43 | +140% |
| New Delhi (Anand Lok)-6115517 | 47 | 34 | 82 | 48 | 49 | +139% |
| North Campus, DU, Delhi - IMD-5610 | 44 | 29 | 69 | 40 | 42 | +138% |
| Santushti Apartments, Vasant Kunj-4634402 | 47 | 34 | 82 | 47 | 48 | +137% |
| Knowledge Park - V, Greater Noida - UPPCB-6986 | 45 | 37 | 88 | 51 | 54 | +136% |
| Sector-116, Noida - UPPCB-6988 | 45 | 35 | 82 | 48 | 50 | +134% |
| New Industrial Town, Faridabad - HSPCB-10920 | 15 | 35 | 82 | 46 | 46 | +131% |
| Loni, Ghaziabad - UPPCB-7005 | 44 | 31 | 70 | 41 | 46 | +128% |
| Commonwealth Sports Complex, Delhi - DPCC-6224596 | 45 | 32 | 72 | 40 | 42 | +127% |
| Punjabi Bagh | 40 | 31 | 69 | 39 | 42 | +124% |
| Jawaharlal Nehru Stadium, Delhi - DPCC-6957 | 45 | 37 | 82 | 44 | 46 | +119% |
| ITO | 41 | 32 | 69 | 37 | 39 | +116% |
| Arya Nagar, Bahadurgarh - HSPCB-6936 | 45 | 30 | 64 | 34 | 36 | +111% |
| Murthal, Sonipat - HSPCB-6951 | 45 | 34 | 72 | 38 | 38 | +111% |
| NSUT Jaffarpur, Delhi - DPCC-6224595 | 45 | 30 | 63 | 33 | 34 | +110% |
| Bawana | 35 | 33 | 69 | 37 | 41 | +109% |
| Mandir Marg | 43 | 33 | 69 | 37 | 40 | +107% |
| Sector-1, Noida - UPPCB-6980 | 45 | 36 | 75 | 39 | 41 | +107% |
| Sector-2 IMT, Manesar - HSPCB-6953 | 45 | 32 | 66 | 34 | 34 | +104% |
| Shyam Nagar, Palwal - HSPCB-7280 | 40 | 40 | 81 | 40 | 40 | +101% |
| Uptitude Cloud Pvt Ltd-6095421 | 47 | 41 | 82 | 41 | 43 | +100% |
| Pusa | 45 | 35 | 69 | 34 | 38 | +99% |
| Vasundhara Nagar_UIT, Bhiwadi - RSPCB-3379929 | 45 | 31 | 61 | 30 | 32 | +97% |
| IHBAS, Dilshad Garden, Delhi - CPCB-6359 | 42 | 37 | 69 | 32 | 34 | +87% |
| Sirifort | 32 | 44 | 81 | 38 | 39 | +87% |
| GK1 (Oberoi Terrace)-2830181 | 47 | 44 | 82 | 38 | 40 | +86% |
| Indirapuram Ghaziabad | 45 | 38 | 69 | 36 | 40 | +84% |
| Rishi Nagar, Kaithal - HSPCB-6971 | 40 | 39 | 70 | 32 | 33 | +83% |
| Sector - 62, Noida - IMD-5616 | 43 | 39 | 71 | 34 | 37 | +83% |
| Chandni Chowk, Delhi - IITM-11603 | 42 | 40 | 68 | 28 | 31 | +70% |
| Air Check-6188596 | 47 | 43 | 72 | 29 | 32 | +65% |
| Teri Gram, Gurugram - HSPCB-10900 | 45 | 52 | 82 | 34 | 38 | +58% |
| Sector 1, Noida extension-6075738 | 47 | 54 | 83 | 29 | 31 | +54% |
| Jahangirpuri | 44 | 45 | 69 | 33 | 42 | +53% |
| Vasundhara, Ghaziabad - UPPCB-5665 | 37 | 47 | 69 | 33 | 37 | +49% |
| Sector 51 Gurugram | 40 | 116 | 81 | 93 | 123 | -30% |

## By IST hour-of-day (pooled across stations)

| hour IST | n | MAE | RMSE | bias % |
|---|---|---|---|---|
| 00 | 153 | 37 | 41 | +94% |
| 01 | 154 | 54 | 60 | +185% |
| 02 | 155 | 50 | 53 | +188% |
| 03 | 158 | 48 | 52 | +169% |
| 04 | 159 | 48 | 51 | +173% |
| 05 | 161 | 48 | 52 | +152% |
| 06 | 159 | 48 | 50 | +164% |
| 07 | 158 | 50 | 61 | +125% |
| 08 | 159 | 46 | 49 | +141% |
| 09 | 158 | 44 | 47 | +139% |
| 10 | 157 | 42 | 48 | +104% |
| 11 | 156 | 41 | 45 | +119% |
| 12 | 156 | 43 | 46 | +129% |
| 13 | 160 | 46 | 48 | +142% |
| 14 | 156 | 48 | 50 | +165% |
| 15 | 155 | 51 | 53 | +187% |
| 16 | 150 | 51 | 53 | +205% |
| 17 | 153 | 51 | 53 | +200% |
| 18 | 152 | 49 | 51 | +188% |
| 19 | 156 | 46 | 49 | +153% |
| 20 | 161 | 45 | 52 | +114% |
| 21 | 85 | 48 | 50 | +167% |
| 22 | 89 | 47 | 49 | +164% |
| 23 | 90 | 46 | 49 | +152% |

## Verdict

The model field over-reads Delhi stations on this window (bias +150.6%, MAE 47 µg/m³ on a mean observed 30 µg/m³).
- **Overshoots** IST hours 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 00 (bias > +15%).
- Largest station-level drift: IGNOU_Maidan Garhi, Delhi - DPCC-6224597 (+1002%), Cantonment Area, Delhi - DPCC-6227749 (+695%), Govindpuram, Ghaziabad - UPPCB-6281265 (+588%)
- Regime caveat: this window is clean post-monsoon air (mean 30 µg/m³). The instrument-vs-model LOO calibration (data/field_calibration.json) was fit on higher pollution where CAMS *under*-reads — bias is regime-dependent, and this window only characterises the clean-air end.
- Kriged estimates carry a σ band; the live `/aqi` response exposes it as `pm25_lo`/`pm25_hi`. These error stats are what that band must honestly cover.

## CPCB live feeds — reachability (tested from this deployment network)

| endpoint | result |
|---|---|
| `airquality.cpcb.gov.in` (official CPCB live portal, all paths) | TCP connect timeout ~8s — geo-blocked/unreachable |
| `api.data.gov.in` (CPCB hourly mirror, resource 3b01bcb8) | TCP connection refused — blocked |
| `cpcb.gov.in` | reachable (200) but CMS pages only — no station JSON feed |
| `app.cpcbccr.com` | reachable (200) — but it is a rebranded third-party portal; the old `aqi_dashboard`/`fetch_table_data` APIs are gone (404/405) and its own footer says it sources Open-Meteo, not CPCB instruments |

**No CPCB public JSON endpoint is reachable from this box**, so no live-station fallback was wired into `airfield.py`. The OpenAQ archive above already carries the same CPCB/DPCC/HSPCB instruments (lagged ~1-2 days); a live instrument path still needs a working OpenAQ key or an India-based exit for CPCB.

*Generated 2026-10-02 18:40Z by server/validate_field.py — real archived measurements only.*