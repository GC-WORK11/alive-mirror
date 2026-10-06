# field-watch-2 — live-model honesty watch under the parali ramp

Lane: field-watch-2. Window: 2026-10-06 **11:51–19:30 UTC** (14 probes @ ~35 min + 3 manual spot-curls).
Live base: `http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com`
(NLB :80). Build at watch start: `4eb9e1e8` (`/health.build_sha`).
Probe rules honoured: **GETs + POST /v2/plan only** — no feedback,
observe, trip or admin writes. Every number below is a curl this lane
ran; raw JSON archived in-session at `~/fw2/raw/`.

Prior pass anchor (demo-reverify-v2, same build ~11:07–11:40 UTC):
fires **claimed** (14 belt / 34.0 MW / NW wind / ×1.24), day windows
both null on flat-moderate, trend lit +5.4 µg/28 snaps.

## What this watch is checking

- **fires claim vs wind** — gate is the NW quadrant 270–360°
  (`server/fires.py: smoke_modifier`). In-quad → full modifier
  (1 + belt/160 × 2.75); off-quad → 30% of uplift and `carrying:false`.
  A claim that ignores the wind is a bug.
- **smoke_modifier band** — 1.0–1.5 sane tonight; >1.6 = suspect.
- **field_age_s < 900 s** (field rebuilds ~10–15 min).
- **edges_priced** stable (~903k of 1,070,459).
- **dose/ambient proportionality** — plan dose ÷ `/aqi` pm25_ambient
  tracked across probes; >20% ratio drift = flag.
- **trend recorder** — `n_snapshots`/`span_h` must keep growing as
  builds land; stall = flag.
- **PM ≥150 µg/m³ contingency** — `/v2/day` GRAP surface must stage up
  honestly; "no meaningful window" on a flat-bad day is CORRECT.

## Observation table

| # | UTC | build | amb µg/m³ | walk dose µg | car-AC µg | walk/amb | modifier | belt fires | wind | carrying | field age | snaps | span h | Δtrend | opts | took ms | verdict |
|---|-----|-------|-----------|--------------|-----------|----------|----------|------------|------|----------|-----------|-------|--------|--------|------|---------|---------|
| 0 | 11:51 | 4eb9e1e8 | 69.8 | 323.2 | — | 4.63 | 1.24 | 14 (34.0MW) | 344°/6.6 | true | 462s | 28 | 5.8 | +6.9 | 24 | 7879 | baseline OK |
| 1 | 11:52 | 4eb9e1e8 | 69.8 | 292.1 | 8.8 | 4.19 | 1.24 | 14 (34.0MW) | 344°/6.6 | true | 515s | 28 | 5.8 | +6.9 | 24 | 595 | OK |
| 2 | 12:27 | **7a808d0b** | 68.3 | 258.7 | 7.8 | 3.79 | **1.07** | 14 (34.0MW) | **15°/7.8** | **false** | 68s | 28 | 5.6 | +4.0 | 9 | 8154 | FLIP verified + new build |
| 3 | 13:02 | 7a808d0b | 63.9 | 248.0 | 7.5 | 3.88 | 1.07 | 14 | 35°/7.8 | false | 362s | 28 | 5.8 | −0.0 | 9 | 8014 | engine-timeout window persists |
| 3w | 13:08 | 7a808d0b | — | — | — | — | — | — | — | — | ~800s | — | — | — | 9 | 8196 | warm re-hit still degraded |
| 3w2 | 13:11 | 7a808d0b | — | — | — | — | — | — | — | — | 771s | — | — | — | 22 | 744 | engine arm recovered post-window |
| 4 | 13:38 | **f0ccea16** | 64.5 | 270.1 | 8.1 | 4.19 | 1.07 | 14 | 56°/? | false | 522s | 27 | 5.6 | −4.9 | 22 | 6255 | 2nd deploy, still honest refuse |
| 5 | 14:13 | f0ccea16 | 59.0 | 270.1 | 8.1 | 4.58 | 1.07 | 14 | 67°/? | false | **1703→10s** | 27 | 5.7 | −7.1 | 8 | 8100 | build mid-probe; cycle slipped ~29min once |
| 6 | 14:48 | f0ccea16 | 57.5 | 280.5 | 8.5 | 4.88 | 1.07 | 14 | 89°/8.6 | false | **1110→10s** | 28 | 5.9 | −7.5 | 24 | 7825 | 2nd ~35min cycle; wind-null race; engine held |
| 7 | 15:23 | f0ccea16 | 58.6 | 285.7 | 8.6 | 4.88 | 1.07 | 14 | 90°/8.6 | false | 557s | 27 | 5.7 | −4.3 | 24 | 7742 | steady; cycle ~26min |
| 8 | 15:58 | **f2ee6bff** | 73.6 | 302.5 | 9.1 | 4.11 | **1.08** | **15** | 89°/8.6 | false | 638s | 28 | 5.9 | −4.3 | 24 | 6107 | 3rd deploy; FIRMS refreshed belt 15 |
| 9 | 16:34 | f2ee6bff | 77.6 | 346.9 | 10.5 | 4.47 | 1.08 | 15 | 95°/? | false | 431s | 29 | ~5.9 | −4.3→? | 24 | 6251 | ambient climbing; doses track |
| 10 | 17:09 | f2ee6bff | 76.3 | 374.0 | 11.3 | 4.90 | 1.08 | 15 | 118°/? | false | 503s | 27 | 5.8 | **+22.1** | 24 | 6178 | evening buildup; route field 93.9 vs amb 76.3 |
| 11 | 17:44 | f2ee6bff | 75.4 | 452.1 | 13.6 | **6.00** | 1.08 | 15 | 119°/? | false | 725s | 26 | ~5.8 | +22.1→? | 24 | 6473 | **RATIO FLAG — verified honest** |
| 12 | 18:19 | f2ee6bff | 72.8 | 472.1 | 14.2 | 6.49 | 1.08 | 15 | 115°/? | false | **968→9s** | 26 | 5.9 | **+35.7** | 23 | 6872 | mid-probe build #3; trend screaming up |
| 13 | 18:54 | f2ee6bff | 70.6 | 472.7 | 14.3 | 6.70 | 1.08 | 15 | 125°/? | false | 225s | 26 | ~5.9 | +35.7→? | 23 | 7090 | steady |
| 14 | 19:30 | f2ee6bff | 69.5 | 458.9 | 13.8 | 6.60 | 1.08 | 15 (67 total) | 139°/? | false | 1s | 24 | 5.6 | +26.8 | 23 | 7431 | fires total climbing 60→67 |

### Off-schedule check — `/v2/day` GRAP + windows (18:57 UTC)

Ambient never hit 150 tonight, so the severe branch stayed armed —
this GET verifies the surface works at today's levels: GRAP
`equivalent_stage 0` on `aqi 179` ("cpcb aqi of day_mean_pm25",
"computed from today's air, not the official CAQM declaration" —
the honesty copy holds); `day_mean_pm25` 83.6; windows now populated
(cleanest ~13:30–15:30 IST avg 60, heavy ~19:30→day-end) — correct:
windows appear on structured days, null on flat ones; 3 decision
rows live. **OK.**

## Notes landed so far

- **Probe 2 — the fires claim flipped honestly.** Wind moved 344°→15°
  (out of the 270–360° gate). `carrying` → `false`, modifier downscaled
  to exactly `1 + (1.24−1)×0.3 = 1.07` (code-checked against
  `fires.py:smoke_modifier`), the stubble_smoke driver left `drivers[]`
  (stagnation is primary now, VC 1,825 m²/s vs ref 3,000, BLH 757 m) —
  `evaluated.fires` still discloses belt 14 / FRP 34.0 / feed live.
  The claim follows the wind in both directions. **No bug.**
- **Probe 2 — a new deploy landed mid-watch:** `4eb9e1e8`→`7a808d0b`,
  fresh field build at 12:26:37 (age 68–77 s on the probe). First
  `/v2/plan` after it returned `degraded:["engine"]` at took 8.15 s —
  the engine arm hit its ~8 s cold budget while the boot raster ran
  (known cold-path contention; the flag is the honest disclosure, not
  a silent drop). Option count fell 24→9 = base mode rows + GTFS Bus
  729 + metro+walk only (least-smoke alternates are the engine arm).
  Watching whether the engine arm stays degraded once warm — a
  persistent engine outage on `7a808d0b` would be escalation.
- **Dose/ambient ratio** 4.19→3.79 across the build boundary (−18%
  vs probe-0 baseline, inside the 20% band). Causal read: modifier
  1.24→1.07 cuts the breathing-zone basis ~14%; walk avg_conc moved
  81.2→65.0 with the rebuilt krige — direction consistent, not
  superlinear.
- **Trend recorder — NOT stalled.** `n_snapshots` is a 6-h windowed
  count (earlier passes saw 32→30 slide and called it expected): at
  probe 3 `history.points` has a fresh record (t≈12:56, pm25 23.6,
  modifier 1.07), `newest_age_s` 370 s, span back to 5.8 h. Builds are
  being recorded; the count stays 28 because old points expire as new
  ones land. `delta_ug` went −0.0 (from/to 29.6) — field flattened
  into early evening.


## Probe-3 deep check — engine-arm timeouts vs the new build

Probes 2 + 3 plus a manual warm re-hit all returned
`degraded:["engine"]` at ~8.0–8.2 s (`ENGINE_BUDGET_S = 8.0`,
`plan.py:1324`). Suspected regression on `7a808d0b` ruled out:

- `git diff 4eb9e1e8..7a808d0b -- server/` touches **only
  landing.html / city.html / community.html** — zero engine or
  pricing code. The arm is byte-identical between builds.
- Second warm re-hit at field age 771 s: **744 ms, degraded:None,
  22 options** — the engine arm completes fine once the field-cycle
  busy window passes. `edges_priced` stable at 903,058/1,070,459.
- Reading: each ~15-min field build is followed by a ~10-13-min
  reprice window where the engine arm is busy-joined and plan calls
  degrade honestly. Probe 0 on the old build hit the same window at
  7.88 s and squeaked *under* the budget (no degrade); the same
  physics on the new build runs ~0.2 s over. **Contention margin,
  honestly flagged — not a code regression.** Watch continues: if a
  probe lands post-window and still degrades, that becomes a bug.

## Probe 4 notes

- **Second deploy mid-watch** — build `f0ccea16` live by 13:38.
  `git diff 7a808d0b..f0ccea16 -- server/` = HTML surfaces +
  `tests/test_v2_why.py` only; engine/wire code still untouched.
- Engine arm healthy this cycle: 6,255 ms fresh-field plan, no
  `degraded`, 22 options. Ratio back to 4.19.
- Wind drifting 15°→56° (ENE) — claim stays refused; `line` still
  stagnation-led. Trend delta went negative (−4.9 µg, 32.2→27.3) as
  the evening field mix shifts — recorder still writing
  (`newest_age_s` 522 s).

## Probe 5 notes

- `/health` at 14:13:17 reported `field_age_s 1703` (≈28 min — over
  the 900 s expected cadence, `refresh_in_s 0` overdue) — then the
  `/v2/plan` seconds later carried `field.built_at 14:13:21, age 10 s`.
  **A field build landed mid-probe**: the 13:44→14:13 gap was ~29 min
  vs the ~15-min TTL. Not stale (`stale_after_s 2700`, `stale:false`),
  but the first over-TTL cycle this watch — tracking: if a probe reads
  age >2700/`stale:true` it becomes a reportable flag.
- Engine-arm timeout #3 again coincides with a fresh field (the
  reprice busy-join) — same contention signature, still consistent.
- Options back to 8 (metro+walk present, GTFS bus absent this read,
  alternates absent w/ the engine arm). Dose set sane at ambient 59.
- Ratio 4.58 — ambient fell 64.5→59.0 with walk dose pinned 270.1;
  ratio vs baseline probe-0 4.63 is −1%. Stable, not drifting.
- Wind now 67° (ENE) — fires refuse state unchanged for ~1.7 h.

## Probe 6 notes

- **`/health` wind went null** (`known:false`) at 14:48:32 — and
  `/v2/why` seconds later shows wind 8.6 km/h @89° `age_s 1`. A
  sampling race mid-field-build, not a dead feed: the wind refresh
  landed between the two curls. The fires block still resolved the
  refuse correctly (downscale applied on why's own wind read).
- **Second consecutive ~30–35-min field cycle** (builds ~13:44,
  14:13, 14:48 — gap ~35 min vs the 900 s TTL). `stale_after_s 2700`
  not breached; if this keeps up, plans mid-cycle ride a ~30-min-old
  field for longer stretches than the demo docs assume. Watching —
  breach of 2700 or a runaway gap = flag.
- Engine arm survived a mid-build plan this time (7,824 ms, no
  degrade, 24 opts incl. alternates) — the timeout window is
  contention-timed, not binary.
- **Ratio 4.88** — decomposed: walk `avg_conc_ugm3` = 70.4 vs CP
  `pm25_ambient` 57.5. The CP→Gurugram krige is honestly ~22% hotter
  than the CP point read; dose follows route geography, not the
  single anchor station. Drift vs probe-1 = +16.5%, under the 20%
  bar; mechanism understood, not a scaling bug.
- Trend delta −7.5 µg (32.6→25.2 over 5.9 h) — field genuinely
  cooling into evening; `newest_age_s` 211 s, recorder live.
- Wind swung to 89° (E) — refuse state holds for ~2.3 h straight.

## Probe 8 notes

- **Third deploy mid-watch** — build `f2ee6bff`. This one *does*
  carry server diff (53 files): new `upstreams.py` single-sourcing
  upstream URLs + comment/literal cleanup across transit, deps,
  validate_field — verified: the same Open-Meteo/OSRM/OpenAQ/Photon
  endpoints verbatim, zero behavior change to the engine or the why
  surfaces. The refresh-cycle slowdown started one build earlier, so
  it is environmental, not this diff.
- **FIRMS refreshed**: belt 14→15 fires, modifier recomputed
  15/160=0.09375 → 1.258 → ×0.3 downscale = **1.08** — exact match
  to the code path. Feed still `live`, feed_age_s was 5,641 s last
  read (inside its 22,500 s contract).
- Ambient climbed 57.5→73.6 (+28%) while walk dose rose 280.5→302.5
  (+7.9%) — dose scales with the field but stays sub-linear to the
  point ambient: exactly the "10× ambient ≠ 100× dose" sanity the
  lane exists to check.
- Field cycle ~34 min again (builds 15:14→15:48). Still ~2× TTL —
  now the dominant watch item, everything else green.

## Probe 10 notes

- **Trend flipped live**: `delta_ug` −7.5 → **+22.1** µg over the
  5.8-h window as the evening stagnation bite arrives (~22:40 IST).
  The reader caught the regime change in-band — that's the trend
  surface doing its job.
- Walk `avg_conc` 93.9 vs CP ambient 76.3: the krige is legitimately
  hotter along the CP→Gurugram corridor than at the anchor point.
  Ratio 4.90 = +17% vs probe-1, still inside the 20% bar with the
  mechanism verified per-probe.
- `us_aqi` 162 at CP. Severe contingency (ambient ≥150 µg/m³) not
  triggered yet — ambient 76.3 is ~half-way. Wind 118° ESE —
  stubble claim correctly stays off.

## FLAG-1 (triggered at probe 11) — dose/ambient ratio drift >20%

`walk_mid ÷ CP pm25_ambient`: 4.19 → 6.00 (**+43%** vs probe-1
baseline; +30% vs probe-0's 4.63). Threshold crossed — dug into the
decomposition rather than calling it a bug:

| point | /aqi pm25 | /aqi ambient | us_aqi |
|---|---|---|---|
| CP anchor | 81.4 | 75.4 | 161 |
| mid-route 28.55,77.15 | 94.6 | 87.6 | 168 |
| Gurugram dest | 104.5 | 96.8 | 186 |

The corridor itself is running ~30-40% hotter than the CP anchor —
walk `avg_conc_ugm3` 113.5 matches a route whose ambient mid-points
read ~87-97 × modifier 1.08 plus open-mode microenv. **All open
modes read the same conc band** (auto 113.5, bike 104.8, cycle 96.0)
→ it's the field, not a mode artifact. `exposure.dose` carries no
time-of-day multiplier — pure spatial sampling × microenv × VE, so
the +21% single-probe dose jump = a real field rebuild along the
route (SW Delhi genuinely hotter tonight).

**Verdict: honest spatial gradient, not a dose-scaling bug.** The
>20% bar tripped because one ambient anchor can't represent a
23.7-km corridor on a gradient night — the check stays armed; if
avg_conc diverges from *independent* station reads (not just the
anchor), that's when it becomes a bug.

## Probe 12 notes

- `delta_ug` now **+35.7** (26.8→62.6 city-scale over 5.9 h) — the
  parali ramp is arriving in the field exactly as the lane was
  spawned to watch. Trend reader has never missed a beat tonight.
- Third mid-probe field build (built ~18:19 inside the plan call) —
  the cycle gaps tonight ran ~26/29/35/26/34/35/60 min vs the 15-min
  TTL. Still under the 2,700-s stale bar every read; logged as the
  recurring degradation below.
- Walk avg_conc 118.5 — Gurugram-end heat keeps intensifying;
  ambient at CP meanwhile slid to 72.8 (west-hot gradient widening).


## Verdict — watch close (19:35 UTC)

**The model stayed honest through the whole evening ramp.** No bug
found that belongs to a server patch; two watch-items recorded for
the lead's radar, neither demo-blocking.

**Verified honest:**
- Fires claim followed the wind in BOTH directions tonight: claimed
  at 344° (×1.24, in-quad), refused at 15°/35°/56°/67°/89°/90°/95°/
  115°/118°/119°/125°/139° (×1.07–1.08 = the documented 30%
  off-quad downscale; math re-derived exact each time, belt 14→15
  tracked the live feed refresh). The driver vacated `drivers[]` and
  stagnation took over — correct editorial behavior, and
  `evaluated.fires` kept disclosing the checked-but-not-claimed
  read throughout.
- Dose/ambient proportionality held under the ramp: ambient 57.5→77.6
  with doses tracking the *route* krige (avg_conc 65→118.5 along the
  corridor) — sub-linear to the point anchor, exactly the "10× ambient
  ≠ 100× dose" invariant. FLAG-1's >20% trip decomposed to a verified
  spatial gradient via three independent /aqi reads (75.4 → 87.6 →
  96.8 CP→Gurugram) — NOT a scaling bug; the check remains the right
  tripwire.
- Trend recorder never stalled: history points landed every field
  build across 3 deploys and the S3-backed history survived each
  restart; `delta_ug` honestly read −7.5 → +35.7 as the evening
  regime flipped. `n_snapshots` flatness (24–29) is the 6-h window
  sliding, per the earlier lane's own note.
- Degrades are told, not hidden: `degraded:["engine"]` on 4 calls,
  all inside post-field-build reprice windows; recovered warm
  (744 ms, 22 opts). `cannot_tell:[]` throughout.

**Watch-items for the lead (not escalated — not bugs):**
1. *Field refresh cycle running ~1.7–2.3× its 900-s TTL tonight*
   (gaps 26–60 min; ages up to 1,703 s at sample time). Never crossed
   the 2,700-s `stale_after_s` bar and `field_stale` stayed false,
   but plans mid-cycle ride a ~30-min-old field — if a demo probe
   ever reads `stale:true` that becomes the T-45 story.
2. *Engine-arm busy window (~10–13 min post-build)* — plan calls in
   that window hit `ENGINE_BUDGET_S` and honestly degrade (options
   drop to base rows). Probe-0 on the old build squeaked under at
   7.88 s; the same physics is now ~0.2 s over the budget. One knob
   turn (`ENGINE_BUDGET_S` 8.0→9.0 or a tighter reprice join) would
   erase the visible degrade during demo-hour probing; call is the
   lead's.
3. *Three deploys landed mid-watch* (4eb9e1e8→7a808d0b→f0ccea16→
   f2ee6bff): diffs verified — first two were HTML-only, the third a
   URL-single-sourcing refactor with zero engine/wire change. Build
   flips on the wire were clean each time (health.build_sha tracked).

Ambient at the CP anchor topped ~78 µg/m³ and slid back to ~70 —
the ≥150 severe path stayed armed but untriggered; `/v2/day` GRAP
surface verified honest at today's levels (stage 0, aqi 179,
windows populated on a structured day). Raw probe JSONs:
`~/fw2/raw/*_{health,why,aqi,plan,day}.json` in this session.
