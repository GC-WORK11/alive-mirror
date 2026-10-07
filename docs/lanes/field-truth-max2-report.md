# Field-truth max2 — Lane A 3-hour pre-run + NCR frontier sweep

**Verdict: PASS.** Over 14 epochs (04:48→07:50 IST, Oct-7) the prod field
served instrument-faithful PM2.5 — MAE **8.4 µg/m³**, median diff **+0.8**,
**91.7%** of live DPCC truths inside our own [lo,hi] band — and it stayed
honest at the uninstrumented NCR rim: smooth gradients (≤7.3 µg/step
outside instrument pull), bands widening to ~92–132 µg at 9.5–15.7 km
out, and `nearest_sample_km` reporting real distance rather than hiding
it. Fires claims consistent all 14 epochs, including across a live feed
update.

Run command (as briefed):
`ALIVE_PROD=http://alive108-…elb.ap-south-1.amazonaws.com python3
scripts/testday/field_sampler.py --loop --every-s 840 --minutes 180
--out docs/lanes/field-truth-max2`
Raw data: `docs/lanes/field-truth-max2/samples.jsonl` (14 epochs),
`epoch-*.json`, `frontier.jsonl` (3 rounds). Companion probe:
`scripts/testday/frontier_probe.py` (stdlib, GETs only).

**Structural caveat (same as holdout-reverify):** DPCC pages are now
both the truth source and an ingest source, so this measures blend
fidelity — "does the field serve each instrument's own reading at its
own cell" — not blindness.

**Builds under test:** prod was deployed twice mid-run — epochs 1–7 on
`ce01ec5c`, epochs 8–14 on `bc8f82c4`, frontier round 3 on `aee635eb`.
Both deploys were UI/hardening (BandScale, tripwires, ledger token_via,
XFF rate-limit) — no field-math change; ambient continuity across the
boundary confirms it (64.2 → 63.3 µg mean, no step).

## Epoch table — ours (`pm25_ambient`) vs live DPCC 5-min pages

| epoch IST | n | med diff | mean | MAE | max\|d\| | ≤5 | ≤10 | ≤20 | ambient mean | field_age s | stn readings | DPCC lag | wind | fires claimed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 04:48 | 12 | -0.2 | +1.0 | 9.1 | 23.3 | 6 | 8 | 10 | 55.5 | 2–23 | 54 | 4–14m | 6.7@134° | no ✓ |
| 05:02 | 12 | +1.3 | +1.4 | 8.8 | 23.3 | 6 | 8 | 10 | 55.5 | 834–858 | 54 | 2–18m | 6.7@134° | no ✓ |
| 05:16 | 12 | -1.8 | -9.3 | 11.8 | 58.3 | 6 | 7 | 10 | 55.7 | 746–768 | 54 | 2–26m | 6.6@131° | no ✓ |
| 05:30 | 12 | +1.7 | -4.6 | 9.7 | 50.5 | 7 | 9 | 10 | 57.1 | 674–696 | 54 | 6–26m | 6.6@127° | no ✓ |
| 05:44 | 12 | +2.6 | -3.4 | 9.5 | 45.0 | 7 | 9 | 10 | 58.3 | 570–593 | 54 | 14–30m | 6.6@125° | no ✓ |
| 05:58 | 12 | +2.8 | -3.1 | 9.2 | 42.2 | 7 | 9 | 10 | 58.7 | 459–480 | 54 | 14–24m | 6.6@111° | no ✓ |
| 06:12 | 12 | -2.3 | -0.9 | 6.8 | 17.5 | 6 | 9 | 12 | 64.2 | 116–138 | 54 | 12–28m | 6.4@108° | no ✓ |
| 06:26 | 12 | +3.1 | +1.2 | 8.3 | 18.7 | 3 | 9 | 12 | 63.3 | 25–47 | 54 | 12–26m | 6.3@105° | no ✓ |
| 06:40 | 12 | +3.1 | +1.2 | 8.3 | 18.7 | 3 | 9 | 12 | 63.3 | 865–887 | 54 | 10–20m | 6.3@105° | no ✓ |
| 06:54 | 12 | +3.4 | +1.0 | 8.1 | 17.4 | 3 | 9 | 12 | 63.2 | 799–821 | 53 | 10–24m | 6.1@104° | no ✓ |
| 07:08 | 12 | +3.4 | +2.3 | 7.3 | 14.2 | 3 | 9 | 12 | 63.0 | 709–732 | 53 | 8–18m | 5.9@104° | no ✓ |
| 07:22 | 12 | -1.4 | -1.2 | 7.2 | 20.3 | 6 | 8 | 11 | 62.0 | 87–109 | 53 | 8–18m | 5.7@108° | no ✓ |
| 07:36 | 12 | -1.7 | -1.5 | 7.1 | 20.4 | 6 | 8 | 11 | 61.6 | 17–38 | 52 | 6–22m | 5.8@110° | no ✓ |
| 07:50 | 12 | -1.7 | -1.5 | 7.1 | 20.4 | 6 | 8 | 11 | 61.7 | 423–445 | 52 | 6–16m | 5.8@110° | no ✓ |

All 168 obs: **MAE 8.4, RMSE 12.2, median +0.8, mean bias −1.2**;
\|diff\| distribution ≤5:75 ≤10:119 ≤15:142 ≤20:153 (p90 18.7, p95 23.0).
For contrast, the Oct-6 pre-DPCC-ingest run of this same sampler had a
median diff of **−23.0** with cells at −87; the blend now owns the
instruments.

**Final epoch in full (07:50, most representative):**

| station | ours | DPCC | diff | DPCC stamp (lag) |
|---|---|---|---|---|
| Narela | 62.4 | 62.0 | +0.4 | 07:35 (15.5m) |
| Pooth Khurd, Bawana | 75.4 | 86.0 | −10.6 | 07:40 (10.5m) |
| Jahangirpuri | 94.2 | 102.0 | −7.8 | 07:35 (15.5m) |
| Rohini | 74.4 | 64.0 | +10.4 | 07:45 (5.5m) |
| Mundka | 52.3 | 56.0 | −3.7 | 07:35 (15.5m) |
| Punjabi Bagh | 63.6 | 84.0 | −20.4 | 07:40 (10.5m) |
| Mandir Marg | 62.7 | 61.0 | +1.7 | 07:40 (10.5m) |
| Major Dhyan Chand Nat. Stadium | 50.8 | 44.0 | +6.8 | 07:35 (15.5m) |
| Anand Vihar | 42.8 | 41.0 | +1.8 | 07:40 (10.5m) |
| Nehru Nagar | 46.3 | 34.0 | +12.3 | 07:40 (10.5m) |
| R.K. Puram | 52.5 | 57.0 | −4.5 | 07:45 (5.5m) |
| Najafgarh | 62.7 | 67.0 | −4.3 | 07:40 (10.5m) |

## The max|d| epochs are instrument step-changes, not blend error

The three big-diff windows all decompose the same way:

- **Jahangirpuri**: DPCC stepped 42 → 105 µg at ~05:05–05:15. Field
  lagged one rebuild cycle (−58 → −42 over 05:16–05:58) then converged
  to −8…−13 by 06:12 and held. A real plume the instrument saw first;
  krige shrink + the 15-min rebuild cycle = the transient, then the
  instrument owns its cell.
- **Pooth Khurd, Bawana**: same signature — 62 → 86 at ~05:05, field
  −27 → −20 through 05:58, then ≤ ~10.
- **Narela**: instrument drifted 102 → 55 across the run; field tracked
  it down, diffs −12 → +18 → +0.4.

Per-station median diffs over all 14 epochs sit between −12.5
(Jahangirpuri — dominated by the lag window) and +11.0 (Nat. Stadium,
whose instrument reads ~10–20 below its neighbours all night — the same
"instrument off its regional field" signature holdout-reverify flagged
at IGNOU/SBV Cantt; the blend hedges rather than echoes, and it lands
inside the band either way).

## Did ambient move?

Yes — a real mid-run rise: 12-cell ambient mean **55.5 → 64.2 → 61.7**
(+15% peak ~06:12, then decay). `/v2/why` trend delta tracked it the
whole way (−4.3 → +4.0 → +2.2 µg/h). The instruments moved with the
field (Jahangirpuri/Bawana jumps above are part of it).

## Field cadence

`field_age_s` reset observed at 5 epochs (min ages 2s, 25s, 116s, 87s,
17s) — rebuilds land ~every 15.5 min, TTL-900 behaviour clean for the
full 3h, no stalls. **Pre-run note:** at 04:47 the field was 2890s
stale (`field_stale:true` on /health, honestly flagged) — it rebuilt at
04:48:29, coincident with the first probe hit, and never went stale
again. If the demo is overnight-adjacent, worth confirming the refresh
path warms before first request.

## Instruments churn honestly

`station_readings` 54 → 53 (06:54) → 52 (07:36) — the staleness guard
aged out two instruments mid-run; the field kept serving with no
discontinuity (ambient mean 63.2 → 61.7 across the drops). `feeds:
{waqi:ok, dpcc:ok}` throughout. All 12 sampled DPCC pages kept
publishing tonight (13 distinct stamps over 14 epochs, lag 1.5–29.5
min) — no repeat of the Oct-7 02:00 29/30 mass-pin.

## Fires-claim honesty under a live feed update

All 14 epochs: `drivers=[stagnation]`, `fires_claimed=False`,
`carrying=False`, `consistent=True`. The fires feed updated mid-run
(67 → 80 fires, 15 → 20 in-belt, modifier ×1.08 → ×1.10 at ~06:12) —
the modifier is applied to the field but never *named* a driver, which
is correct: wind held 104–134° (E–SE) all run, not advecting the NW
stubble belt into Delhi. Headline stayed "the air is barely moving —
the day's pollution is sitting over the city" (ventilation factor
7.6–9.0, poor dispersion — matches).

## Frontier — the NCR rim stays honest (3 rounds, 04:50 / 06:18 / 08:00 IST)

Transects inside-ring → rim (per-step ambient change; band = pm25
lo–hi width):

| transect | ambient in→rim (r1/r2/r3) | max step | km in→rim | band in→rim |
|---|---|---|---|---|
| north → Sonipat (worst col, 76.95E) | 70.8→66.6 / 74.7→72.1 / 64.6→64.0 | 5.8 | 7.7→15.7 | 93→111 |
| north → Narela column (77.09E) | 55.4→72.1 / 75.4→71.7 / 70.8→61.4 | 18.8¹ | 2.4→10.9 | 68→110 |
| west → Bahadurgarh (28.68N) | 55.7→71.8 / 57.9→78.2 / 52.2→68.2 | 6.6 | 0.3→2.2² | 61→85 |
| southwest → Rewari (76.95E) | 73.7→65.6 / 75.5→70.0 / 67.8→66.0 | 2.6 | 2.9→12.4 | 86→100 |
| east → Ghaziabad (28.62N) | 35.9→44.0 / 41.3→52.1 / 42.4→49.2 | 5.6 | 1.5→9.5 | 55→89 |
| south → beyond Faridabad (77.15E) | 45.3→53.7 / 45.9→57.8 / 43.5→60.7 | 7.3 | 3.8→11.8 | 68→93 |

¹ the one large step is walking into Narela's genuinely-hot instrument
cell (89.2 served vs 102 DPCC at that moment) — instrument pull, not an
artifact. ² west rim km *decreases* toward 76.85E — a model-lattice
point sits near Bahadurgarh; nearest_sample_km is distance to nearest
sample (instrument or lattice), so it's non-monotonic along some lines.
Geometry, not a bug.

Named rim cells (round 3, 08:00 IST, build `aee635eb`):

| cell | served ambient | band | nearest_sample_km |
|---|---|---|---|
| sonipat-worst (28.95, 76.95) | 64.0 | 15.0–125.8 | **15.7** |
| north-rim-far-e (28.95, 77.50) | 51.0 | 3.2–108.9 | 12.4 |
| bahadurgarh-edge (28.68, 76.85) | 68.2 | 33.2–116.8 | 2.2 |
| west-rim-n (28.75, 76.85) | 67.6 | 27.2–121.6 | 5.6 |
| west-rim-s (28.45, 76.85) | 67.7 | 27.3–121.7 | 5.6 |
| rewari-edge (28.40, 76.95) | 66.4 | 23.0–123.1 | 11.1 |
| ghaziabad-far (28.62, 77.50) | 49.2 | 8.1–100.2 | 9.5 |
| faridabad-beyond (28.35, 77.15) | 60.7 | 18.4–115.1 | 11.8 |

Across all 3 rounds × 45 cells: **0 errors, 0 insane values, 0
flatlines, 0 flagged artifacts** — the rim serves plausible ambient with
honestly wide bands and truthful distances, stable across two field
epochs and two deploys. The spatial structure is sensible too: rim cells
track the same direction as the city (N/W hotter ~64–78, E cooler
~42–52) and move with the field between rounds.

## /v2/city + /health cross-checks (frontier rounds)

city `pm25_stats.mean` 61.1 (06:18) / 56.9 (08:00), `freshness:
live`, `enough_data: true`, `station_readings` matching /health
(54/52), `field_samples` 100, source `waqi+dpcc-stations+open-meteo/
cams`. GRAP equivalent stage 0, computed-from-today note present.

## Verdict

The field is demo-ready on truth: it serves instruments their own
readings (MAE 8.4 over 3h live), discloses staleness, hedges rather
than echoes glitchy sensors, names stagnation not stubble when the wind
says so, and at the unmonitored NCR rim it extrapolates smoothly with
wide bands and real distances — "tight inside the ring, honestly coarse
at the fringe" holds under live conditions. Watch-items for test day:
the pre-run 48-min stale field (warm the refresh before demo start) and
instrument step-changes give ~1-cycle lag ≈ up to −58 µg transient at a
station cell — that's the field chasing reality, not an error.

## Method files

- `docs/lanes/field-truth-max2/samples.jsonl` — 14 epochs × 12 cells
- `docs/lanes/field-truth-max2/epoch-*.json` — per-epoch dumps
- `docs/lanes/field-truth-max2/frontier.jsonl` — 3 rim rounds
- `scripts/testday/field_sampler.py` (Lane A sampler, existing),
  `scripts/testday/frontier_probe.py` (new rim probe)
