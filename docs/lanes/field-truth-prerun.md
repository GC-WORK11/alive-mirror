# Field-truth pre-run — Oct-6 21:14→22:11 IST (Lane A dry run)

**Verdict: sampler works, prod field is live and moving, claim-checks consistent — with one bias to watch.**

Script: `scripts/testday/field_sampler.py` (stdlib only, GETs only).
Run: 5 epochs × ~14 min against prod `http://65.2.28.40` — raw data in
`docs/lanes/field-truth-prerun/samples-20261006-56min.jsonl`.

## Working DPCC fetch path (for tomorrow's lanes)

- Station list: `GET https://www.dpccairdata.com/dpccairdata/display/index.php`
  embeds `stName=<base64(slug)>` links inside a JS tree (parse out
  `<!-- -->` comments first — dead stations are commented).
- Station page: `GET …/display/AallStationView5MinData.php?stName=<b64>`
  → flat `<td>` table, rows are `param | date | time(IST) | concentration
  | standard | remarks`. PM2.5 row = "Particulate Matter < 2.5 µg",
  PM10 = "Particulate Matter < 10 µg".
- **Reality check:** pages titled "5 Min Data" ran **11–34 min stale**
  tonight — the IST timestamp inside the row is the truth, not fetch time.
  Several stations repeated identical values across epochs (Narela pinned
  114.0 for 3 epochs) — treat any cell whose stamp lags >~10 min as
  "their last read", not "now".
- 24 live stations tonight; 12 chosen for geographic spread (see script
  `STATIONS` — each sampled cell sits AT the station coordinate, so
  field-vs-instrument is same-place).

## The numbers — our field (ambient) vs DPCC holdout, µg/m³

| epoch | station | ours | DPCC | diff | DPCC stamp (lag) |
|---|---|---|---|---|---|
| 21:14 | Narela | 47.6 | 90.0 | **-42.4** | 20:50 (25m) |
| 21:14 | Bawana | 54.1 | 77.0 | -22.9 | 20:50 (25m) |
| 21:14 | Jahangirpuri | 37.5 | 91.0 | **-53.5** | 20:45 (30m) |
| 21:14 | Rohini | 45.1 | 132.0 | **-86.9** | 21:00 (15m) |
| 21:14 | Mundka | 52.8 | 57.0 | -4.2 | 20:55 (20m) |
| 21:14 | Punjabi Bagh | 49.2 | 79.0 | -29.8 | 20:55 (20m) |
| 21:14 | Mandir Marg | 51.8 | 75.0 | -23.2 | 21:00 (15m) |
| 21:14 | National Stadium | 49.7 | 53.0 | -3.3 | 20:50 (25m) |
| 21:14 | Anand Vihar | 70.8 | 80.0 | -9.2 | 20:55 (20m) |
| 21:14 | Nehru Nagar | 56.4 | 74.0 | -17.6 | 20:50 (25m) |
| 21:14 | R.K. Puram | 58.7 | 105.0 | **-46.3** | 21:00 (15m) |
| 21:14 | Najafgarh | 48.4 | 53.0 | -4.6 | 20:55 (20m) |

(median -23.0; 9/12 inside our own LOO calibration MAE of 46.1 µg)

By epoch, medians: **-23.0 → -22.4 → -27.1 → -16.1 → -12.8**;
within-MAE count 9 → 9 → 8 → 10 → 10 of 12. Per-station medians over
the 5 epochs:

| station | median diff | read |
|---|---|---|
| Punjabi Bagh | -66.7 | persistent under-read |
| Jahangirpuri | -65.6 | persistent under-read |
| Rohini | -52.2 | under-read, DPCC itself swung 132→60→88 |
| Narela | -43.6 | under-read, DPCC pinned 114 ×3 epochs |
| R.K. Puram | -36.8 | under-read |
| Mundka | -26.4 | inside disagreement |
| Bawana | -25.7 | inside disagreement |
| National Stadium | -7.2 | good |
| Najafgarh | -3.6 | good |
| Mandir Marg | +2.1 | good |
| Nehru Nagar | +17.5 | inside disagreement |
| Anand Vihar | +28.6 | over-read — DPCC dropped 80→47 while field rose |

**Pattern:** the under-reads are all W/NW (Punjabi Bagh, Jahangirpuri,
Rohini, Narela, RK Puram) — roadside DPCC sites genuinely hotter than
our spatial blend, or our W-Delhi instrument coverage is thinner. Worth
a real look tomorrow with a longer window and tighter DPCC timestamps;
the sign-flip at Anand Vihar and Rohini's 132→60→88 shows station-level
noise is real on their side too.

## Did ambient move across epochs?

Yes — real evening climb, field tracking it: 12-cell ambient mean
**51.8 → 64.0 → 68.3 → 70.6 → 70.3** µg/m³ over 56 min (+35%).
DPCC pages that refreshed agreed on direction (Jahangirpuri 91→143,
Punjabi Bagh 79→136); static pages stayed pinned. `field_age_s` ran
727 → 633 → 513 → **2** → 839 — caught one rebuild live at ~21:56
(2 s old field) and another between 21:28–21:42; TTL 900 s behaving.

## Did the "stubble smoke" claim track the wind?

Every epoch: `fires_claimed=False`, `carrying=False` — engine saw
67 fires / 15 in-belt / ×1.08 modifier applied to the field, but did
**not** name fires a driver because wind was 89–95° (≈ easterly — not
advecting the NW belt into Delhi). Consistent=true all 5 epochs.
Headline stayed "the air is barely moving — the day's pollution is
sitting over the city"; at 22:10 a `trend` driver joined
("levels still climbing" — matches the +35% ambient above).

## Tomorrow's checklist for Lane A

- Rerun ≥3 h: `python3 scripts/testday/field_sampler.py --loop
  --every-s 840 --minutes 180 --out <dir>` then `--report`.
- The NW under-read is the one number to chase — compare against WAQI
  raw at the same stations to split "their instrument hot" vs
  "our blend low".
- DPCC staleness varies by station; weight comparisons by stamp lag.
