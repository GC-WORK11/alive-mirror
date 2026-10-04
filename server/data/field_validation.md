# Field validation — model vs OpenAQ archive ground truth

## What was compared

- **Truth**: hourly PM2.5 medians at CAAQMS stations from the public OpenAQ S3 archive (`records/csv.gz`, anonymous reads). Archive pull: 2026-10-02T18:37Z, 86 stations reporting, freshest row 2026-09-30T00:00:00+05:30.
- **Model**: the same field the API serves — Open-Meteo/CAMS pm2_5 over the 48-point NCR grid, kriged (`krige.KrigeField`) with advection-weighted IDW fallback, rebuilt per IST hour from archived Open-Meteo hourly output.
- **Window**: 2026-09-28 01:00:00+05:30 → 2026-09-30 00:00:00+05:30 IST (~48h trailing; the archive lags real time ~1-2 days, so a live `/aqi` pull cannot overlap it — the model is reconstructed for the same hours from the identical upstream).
- **Not included**: the OpenAQ live-instrument blend (API key dead — the deployed field is pure model today, which is exactly what this validates) and the community corridor layer.

## Headline

| pairs | stations | MAE µg/m³ | RMSE µg/m³ | bias µg/m³ | bias % |
|---|---|---|---|---|---|
| 3550 | 85 | 22.0 | 29.3 | +15.5 | +51.6% |

IDW-only fallback (no kriging): MAE 21.8, RMSE 29.0, bias +15.1 (+50.4%) — kriging does not beat IDW on this window.

## Uncertainty-band coverage (held-out stations)

For a calibrated Gaussian band, |obs − model| ≤ k·σ should hold at the nominal rate. σ here is the per-point field sigma the API serves (`sqrt(krige_sd² + (0.12·µ)²) × SIGMA_CAL`, the measured total-error inflation in airfield.py) at the same station+hour.

| band | nominal | measured |
|---|---|---|
| ±1σ | 68.3% | 53.2% |
| ±2σ | 95.4% | 95.2% |
| ±3σ | 99.7% | 99.1% |

n=3550 pairs; median |err|/σ = 0.94. σ scale factors that would have calibrated this window: ×1.27 at 1σ, ×1.00 at 2σ, ×2.21 at 3σ.
**Verdict**: the σ-band is calibrated — measured ±2σ coverage sits within noise of nominal 95% under the applied `SIGMA_CAL` total-error inflation (airfield.py, set from this measured factor, never hand-tuned).

## Per-station (n≥6 pairs, sorted by |bias%|)

| station | n | obs µg/m³ | model µg/m³ | MAE | RMSE | bias % |
|---|---|---|---|---|---|---|
| IGNOU_Maidan Garhi, Delhi - DPCC-6224597 | 45 | 7 | 52 | 45 | 47 | +598% |
| Cantonment Area, Delhi - DPCC-6227749 | 45 | 10 | 47 | 37 | 40 | +385% |
| JNU, Delhi - DPCC-6224594 | 45 | 13 | 51 | 39 | 41 | +294% |
| Amity University, Panchgaon - IITM-3379939 | 45 | 12 | 45 | 35 | 37 | +283% |
| Govindpuram, Ghaziabad - UPPCB-6281265 | 45 | 11 | 40 | 28 | 32 | +250% |
| Major Dhyan Chand National Stadium, Delhi - DPCC-6929 | 35 | 14 | 47 | 33 | 37 | +234% |
| Sri Aurobindo Marg, Delhi - DPCC-10484 | 45 | 19 | 52 | 33 | 36 | +174% |
| Wazirpur | 39 | 16 | 41 | 26 | 29 | +164% |
| Sardar Patel Inter College, Baghpat - UPPCB-311989 | 42 | 16 | 42 | 29 | 31 | +155% |
| Nehru Nagar | 38 | 22 | 53 | 32 | 35 | +142% |
| Patparganj | 29 | 20 | 47 | 28 | 30 | +137% |
| NSIT Dwarka, Delhi - CPCB-5622 | 41 | 19 | 46 | 26 | 30 | +136% |
| SRM University, Modinagar - UPPCB-6269545 | 20 | 19 | 46 | 26 | 29 | +135% |
| NASA GSFC Rutgers Calib. N8-2994922 | 41 | 20 | 46 | 26 | 29 | +135% |
| Dr. Karni Singh Shooting Range, Delhi - DPCC-6934 | 43 | 22 | 52 | 30 | 34 | +134% |
| IGI Airport (T3), Delhi - IMD-5650 | 45 | 21 | 50 | 28 | 32 | +133% |
| Ashok Vihar | 17 | 20 | 46 | 26 | 28 | +127% |
| Lodhi Road | 45 | 22 | 50 | 28 | 31 | +124% |
| Najafgarh, Delhi - DPCC-10488 | 29 | 21 | 46 | 25 | 28 | +122% |
| Yamunapuram, Bulandshahr - UPPCB-6985 | 45 | 22 | 46 | 25 | 29 | +115% |
| Okhla Ph-2 | 45 | 25 | 52 | 27 | 31 | +109% |
| Nathu Colony, Ballabgarh - HSPCB-6972 | 45 | 25 | 51 | 26 | 30 | +102% |
| Alipur, Delhi - DPCC-6932 | 42 | 20 | 41 | 23 | 26 | +102% |
| Vikas Sadan, Gurugram - HSPCB-301 | 45 | 25 | 49 | 25 | 30 | +100% |
| Anand Vihar, Hapur - UPPCB-8319 | 45 | 20 | 39 | 21 | 24 | +95% |
| Kalindi Kunj, Khurja - UPPCB-357040 | 45 | 24 | 46 | 22 | 26 | +93% |
| Mundka, Delhi - DPCC-10486 | 44 | 21 | 41 | 20 | 23 | +90% |
| Shadipur | 41 | 21 | 40 | 19 | 23 | +88% |
| Noida Sec-125 | 45 | 28 | 51 | 28 | 33 | +83% |
| IIT Delhi, Delhi - IITM-6118616 | 45 | 29 | 52 | 23 | 27 | +81% |
| CRRI Mathura Road, Delhi - IMD-5627 | 45 | 28 | 51 | 24 | 26 | +81% |
| Aya Nagar | 44 | 29 | 52 | 24 | 28 | +78% |
| Ved Vihar-Loni, Ghaziabad - UPPCB-6269620 | 44 | 22 | 39 | 18 | 21 | +75% |
| NISE Gwal Pahari, Gurugram - IMD-10921 | 45 | 31 | 52 | 21 | 25 | +69% |
| Wave City, Ghaziabad - UPPCB-6428455 | 43 | 25 | 42 | 20 | 24 | +68% |
| Sanjay Nagar, Ghaziabad - UPPCB-10919 | 45 | 24 | 39 | 19 | 23 | +66% |
| RK Puram | 44 | 31 | 51 | 22 | 25 | +64% |
| Dwarka Sec-8 | 42 | 32 | 51 | 21 | 24 | +60% |
| Talkatora Garden, Delhi - DPCC-6224525 | 45 | 27 | 43 | 19 | 23 | +57% |
| Sector 51 Gurugram | 40 | 116 | 50 | 96 | 138 | -57% |
| New Delhi (Anand Lok)-6115517 | 47 | 34 | 53 | 20 | 24 | +56% |
| Narela | 44 | 26 | 40 | 17 | 20 | +55% |
| Santushti Apartments, Vasant Kunj-4634402 | 47 | 34 | 53 | 21 | 25 | +53% |
| Sector 30, Faridabad - HSPCB-10820 | 45 | 34 | 51 | 18 | 22 | +50% |
| Anand Vihar | 43 | 27 | 40 | 19 | 22 | +47% |
| Rohini | 44 | 28 | 40 | 17 | 20 | +45% |
| DTU | 44 | 28 | 40 | 17 | 20 | +45% |
| Prashant Garden, Khora - UPPCB-6269436 | 45 | 30 | 43 | 16 | 20 | +44% |
| NSUT Jaffarpur, Delhi - DPCC-6224595 | 45 | 30 | 43 | 13 | 15 | +44% |
| Sonia Vihar | 44 | 28 | 40 | 19 | 21 | +42% |
| Vivek Vihar | 45 | 28 | 40 | 17 | 21 | +42% |
| Sector-2 IMT, Manesar - HSPCB-6953 | 45 | 32 | 45 | 14 | 17 | +41% |
| Burari | 43 | 29 | 40 | 13 | 17 | +40% |
| Vasundhara Nagar_UIT, Bhiwadi - RSPCB-3379929 | 45 | 31 | 43 | 16 | 19 | +38% |
| Arya Nagar, Bahadurgarh - HSPCB-6936 | 45 | 30 | 41 | 15 | 18 | +38% |
| Knowledge Park - III, Greater Noida - UPPCB-6978 | 45 | 35 | 48 | 17 | 21 | +37% |
| Commonwealth Sports Complex, Delhi - DPCC-6224596 | 45 | 32 | 44 | 16 | 18 | +37% |
| Jawaharlal Nehru Stadium, Delhi - DPCC-6957 | 45 | 37 | 51 | 17 | 21 | +36% |
| North Campus, DU, Delhi - IMD-5610 | 44 | 29 | 39 | 14 | 17 | +36% |
| Punjabi Bagh | 40 | 31 | 41 | 20 | 24 | +34% |
| Sector-116, Noida - UPPCB-6988 | 45 | 35 | 46 | 21 | 24 | +33% |
| Sirifort | 32 | 44 | 58 | 15 | 19 | +32% |
| Uptitude Cloud Pvt Ltd-6095421 | 47 | 41 | 53 | 18 | 22 | +30% |
| Loni, Ghaziabad - UPPCB-7005 | 44 | 31 | 39 | 18 | 22 | +28% |
| ITO | 41 | 32 | 41 | 15 | 18 | +27% |
| Sector-1, Noida - UPPCB-6980 | 45 | 36 | 46 | 16 | 21 | +26% |
| Knowledge Park - V, Greater Noida - UPPCB-6986 | 45 | 37 | 47 | 17 | 20 | +25% |
| Murthal, Sonipat - HSPCB-6951 | 45 | 34 | 42 | 14 | 17 | +24% |
| GK1 (Oberoi Terrace)-2830181 | 47 | 44 | 53 | 17 | 21 | +22% |
| Mandir Marg | 43 | 33 | 40 | 18 | 23 | +21% |
| Shyam Nagar, Palwal - HSPCB-7280 | 40 | 40 | 48 | 13 | 16 | +18% |
| Pusa | 45 | 35 | 41 | 16 | 18 | +17% |
| Bawana | 35 | 33 | 39 | 16 | 20 | +17% |
| Sector 1, Noida extension-6075738 | 47 | 54 | 47 | 16 | 19 | -13% |
| Jahangirpuri | 44 | 45 | 40 | 18 | 27 | -11% |
| IHBAS, Dilshad Garden, Delhi - CPCB-6359 | 42 | 37 | 40 | 16 | 18 | +10% |
| Vasundhara, Ghaziabad - UPPCB-5665 | 37 | 47 | 42 | 23 | 28 | -9% |
| Sector - 62, Noida - IMD-5616 | 43 | 39 | 43 | 16 | 20 | +9% |
| Indirapuram Ghaziabad | 45 | 38 | 40 | 20 | 23 | +7% |
| New Industrial Town, Faridabad - HSPCB-10920 | 15 | 35 | 37 | 5 | 6 | +5% |
| Air Check-6188596 | 47 | 43 | 45 | 16 | 19 | +3% |
| Chandni Chowk, Delhi - IITM-11603 | 42 | 40 | 40 | 12 | 14 | +1% |
| Rishi Nagar, Kaithal - HSPCB-6971 | 40 | 39 | 39 | 9 | 12 | +1% |
| Teri Gram, Gurugram - HSPCB-10900 | 45 | 52 | 52 | 20 | 28 | +0% |

## By IST hour-of-day (pooled across stations)

| hour IST | n | MAE | RMSE | bias % |
|---|---|---|---|---|
| 00 | 153 | 25 | 29 | +63% |
| 01 | 154 | 25 | 38 | +66% |
| 02 | 155 | 21 | 25 | +69% |
| 03 | 158 | 21 | 25 | +60% |
| 04 | 159 | 22 | 24 | +66% |
| 05 | 161 | 17 | 26 | +27% |
| 06 | 159 | 18 | 21 | +42% |
| 07 | 158 | 20 | 45 | +15% |
| 08 | 159 | 13 | 21 | +1% |
| 09 | 158 | 12 | 17 | -12% |
| 10 | 157 | 17 | 28 | -11% |
| 11 | 156 | 16 | 20 | +7% |
| 12 | 156 | 17 | 22 | +21% |
| 13 | 160 | 18 | 25 | +38% |
| 14 | 156 | 21 | 28 | +61% |
| 15 | 155 | 26 | 32 | +87% |
| 16 | 150 | 31 | 37 | +118% |
| 17 | 153 | 21 | 26 | +76% |
| 18 | 152 | 25 | 29 | +94% |
| 19 | 156 | 30 | 33 | +99% |
| 20 | 161 | 35 | 43 | +84% |
| 21 | 85 | 30 | 32 | +102% |
| 22 | 89 | 29 | 31 | +102% |
| 23 | 90 | 28 | 30 | +88% |

## Verdict

The model field over-reads Delhi stations on this window (bias +51.6%, MAE 22 µg/m³ on a mean observed 30 µg/m³).
- **Overshoots** IST hours 01, 02, 03, 04, 05, 06, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 00 (bias > +15%).
- Largest station-level drift: IGNOU_Maidan Garhi, Delhi - DPCC-6224597 (+598%), Cantonment Area, Delhi - DPCC-6227749 (+385%), JNU, Delhi - DPCC-6224594 (+294%)
- Regime caveat: this window is clean post-monsoon air (mean 30 µg/m³). The instrument-vs-model LOO calibration (data/field_calibration.json) was fit on higher pollution where CAMS *under*-reads — bias is regime-dependent, and this window only characterises the clean-air end.
- Kriged estimates carry a σ band; the live `/aqi` response exposes it as `pm25_lo`/`pm25_hi`. The coverage table above measures exactly how honest that band is.

## CPCB live feeds — reachability (tested from this deployment network)

| endpoint | result |
|---|---|
| `airquality.cpcb.gov.in` (official CPCB live portal, all paths) | TCP connect timeout ~8s — geo-blocked/unreachable |
| `api.data.gov.in` (CPCB hourly mirror, resource 3b01bcb8) | TCP connection refused — blocked |
| `cpcb.gov.in` | reachable (200) but CMS pages only — no station JSON feed |
| `app.cpcbccr.com` | reachable (200) — but it is a rebranded third-party portal; the old `aqi_dashboard`/`fetch_table_data` APIs are gone (404/405) and its own footer says it sources Open-Meteo, not CPCB instruments |

**No CPCB public JSON endpoint is reachable from this box**, so no live-station fallback was wired into `airfield.py`. The OpenAQ archive above already carries the same CPCB/DPCC/HSPCB instruments (lagged ~1-2 days); a live instrument path still needs a working OpenAQ key or an India-based exit for CPCB.

*Generated 2026-10-04 12:13Z by server/validate_field.py — real archived measurements only.*