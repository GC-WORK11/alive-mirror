# field-drift-watch report — high-PM regime, 2026-10-06 03:06–05:19 UTC

**Verdict: CLEAN WATCH. No drift, no field-freeze, no driver
contradictions, nothing live-lying.** Every served number stayed honest
through the night's peak and the morning ventilation transition: the
field tracked a real +23µg/m³ overnight rise and a real −40µg/m³
morning fall, and the surfaces that expose internals (/v2/why,
/v2/skill, /admin/api/sources) told the truth about their own staleness
when it happened.

Two latent issues documented (neither is fake numbers on surfaces —
both are capacity/honesty-edge observations, see below):

1. `/v2/why` under-counts its own snapshot history (serves 26–32 builds
   where S3 holds ~30–31) — the 4 s S3 fetch budget truncates the
   *oldest* rows, so the reported count oscillates with CPU contention.
2. FIRMS public-CSV feed crosses its own `stale_after_s=2700` marker
   between refreshes — the feed flags itself stale honestly, but a
   45-min+ refresh cycle means it spends real time marked stale.

Watch covered 8 ticks at ~20–25 min cadence, 03:06–05:19 UTC
(ended at 2h13m on lead's wrap call). Raw numbers per tick:
`field-drift-watch-log.md`. Observe-only: zero POSTs, zero deploys.

---

## What the field actually did tonight

Delhi came off the overnight stagnation peak while the watch ran:

| tick UTC | 6-pt pm25 range | city mean | breath mid | /v2/why trend | ventilation vc m²/s |
|---|---|---|---|---|---|
| 03:06 | 88.2–118.0 | 90.3 | 1297 µg | +23.3µg rising | 533 |
| 03:27 | 88.8–123.8 | 88.7 | 1274 | +23.3 rising | 533 |
| 03:46 | 84.2–103.4 | 83.2 | 1196 | +22.2 rising | 533 |
| 04:06 | 79.6–100.0 | 80.4 | 1155 | +15.2 rising | 533 |
| 04:25 | 75.7–99.1 | 75.8 | 1089 | Δ=10.0 → driver dropped | 922 |
| 04:45 | 68.3–85.7 | 61.0 | 876 | Δ=+1.7 flat | (rising) |
| 05:04 | 64.4–83.3 | 55.4 | 795 | Δ=−6.0 flat | — |
| 05:19 | 60.4–81.7 | 52.9 | 759 | Δ=−11.8 flat | — |

The physics read is coherent: boundary layer 308 m → 536 m and
ventilation 533 → 922 m²/s as the morning mixed layer formed; the field
mean fell ~90 → ~53 µg/m³ and the breath figure tracked it
1297 → 759 µg. Spatial spread stayed real throughout (e.g. Rohini
118.0 vs Dwarka 98.9 at 03:06; never identical values, never nulls,
never 0).

Per-tick checks all clean:

- **`/aqi` × 6 spread points** (CP, Anand Vihar, Gurugram, Noida,
  Rohini, Dwarka): every read live, `stale=false`, `serving=live`,
  `field_age_s` 18–649 s — always under the 30-min flag line.
  `built_at` advanced every tick (02:56→03:25→03:40→03:55→04:25→
  04:40→04:55→05:10 builds); no freeze.
- **`/v2/city` breath**: 1297→759 µg, monotonic decline matching the
  falling field — no >2× jumps.
- **`/v2/skill` pairs**: 62→61→71→71→71→80→80→80. Accrues per IST
  hour-bucket landing (+10 at 09:00 IST, +9 at 10:00 IST) — healthy.
- **`/fires`**: 89 fires, 22 belt, constant all watch (daily VIIRS —
  acq_date 10-04/10-05; this is the dataset's real cadence, not a stall).
- **`/admin/api/sources`**: stations readings=24 and model samples=71
  constant; routing `osrm-local` up; location disabled by config
  (known). No source dropped to 0.
- **S3 `s3://alive108-air/field/`**: builds landing every ~10–15 min
  all watch; worst observed gap 10.5 min — never near the 30-min flag.

## Finding 1 — `/v2/why` snapshot-series under-count (low severity)

**Observed:** `trend.n_snapshots` read 26 at 03:06, 32 at 03:27, 32 at
03:46, 30 at 04:06, 30 (unevaluated) at 04:25, 29 at 04:45/05:04/05:19.
The mandate's "~30–34 builds/6h" expectation flagged it at 03:06 (n=26
< 28) and again on the 32→30 dip.

**Reproduced + root-caused:** S3 itself held ~30–31 in-window builds at
every check — e.g. at 03:08 UTC, builds from 21:15 to 02:55 UTC =
30 objects vs n_snapshots=26, and `span_h` read 4.9 h with the oldest
*visible* build at ~22:11 (the 21:15–22:01 builds existed in S3 but
were missing from the series). In `server/v2/why.py`, `_s3_series`
fetches newest→oldest under `_SNAP_S3_GET_BUDGET_S = 4.0` with an
early-`break` on deadline — under CPU contention the oldest rows get
dropped, which is exactly the side that vanished. The count then
recovers when a tick's fetch runs faster (26→32 between 03:06 and
03:27 with no new history arriving — impossible for a real shrink).

**Impact:** the trend driver still reads real builds and its verdict
was right all night; what drifts is the *denominator* — reported
`n_snapshots`/`span_h` can understate history by ~15%, and on a slower
task the series could starve further (the code comment already records
a 15-row starvation at the old serial budget). Not live-lying — the
number is honest about what it fetched — but the UI's "31 recorded
builds" claim is a lower bound presented as an exact count.

## Finding 2 — FIRMS feed stale-flapping (low severity, honest)

**Observed:** `sources.fires.stale=true` with `age_s` 4340 at 03:06
and 3246 at 05:19; cleared to 137 s at 03:27 after a refresh. The feed
marks itself stale past `stale_after_s=2700` (45 min) — so the public
CSV refresh cycle is running >45 min and the marker flaps on/off.

**Assessment:** `feed_status` stays `"live"` and `carrying` stayed
`false` correctly all watch (wind 102–132° — from the east/southeast,
not the Punjab/Haryana belt), so the fires modifier (1.11, applied)
never misattributed. The stale marker is the system telling the truth
about a slow refresh — good — but if the feed were to die entirely the
surface would show `fires=89` marked stale rather than 0; worth knowing
that "count constant + stale flag" is the failure signature to watch
for, not `fires=0`.

## Non-findings (checked, clean)

- **Trend-driver admission churn** at 04:25: the `trend` driver dropped
  from `drivers[]` when |Δ| fell to 10.0 < `TREND_MIN_DELTA_UG=12` —
  `evaluated.trend` kept reporting n=30, Δ=10.0 honestly, and the spoken
  `line` correctly dropped "levels still climbing". Correct-by-design;
  noted so the drop isn't mistaken for a trend-data failure.
- **Driver contradictions:** fires was never claimed while
  `carrying=false`; stagnation was claimed primary all night with real
  vc/blh evidence. Zero contradictions.
- **Breath band `lo=0.0`:** `max(0, mid − 1.96σ)` clips negative in a
  high-spread regime — mathematical clip, disclosed basis line, fine.
- **skill pairs −1 dip** (62→61 at 03:27): single-pair transient
  (archive enumerate/doc load miss), recovered and accrued normally.

## Method

GETs only: `/aqi?lat&lon` ×6, `/v2/why`, `/v2/city`, `/v2/skill`,
`/fires`, `/admin/api/sources` (Bearer `~/.alive_admin_token`, from
Secrets Manager `alive108/admin-token`), plus
`aws s3api list-objects-v2` on `s3://alive108-air/field/` (ap-south-1).
Per-tick flag rules per the lane brief; cross-tick checks for
field-freeze (`built_at` unchanged), history shrink, trend flips,
breath jumps, source drops. Probe script: `~/field_watch_tick.py`
(not committed; logic mirrored in the log's columns).
