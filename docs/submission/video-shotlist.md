# Video — ≤3 min recording checklist & shot list

The video is judged — most importantly on **console proof + real product**.
This document lists what must appear, in what order, and how long each beat
gets. Target: **2:45–2:55** so a beat can overrun without breaching 3:00.
The arc now sells the **dosimeter** — the numbers every beat leans on were
re-verified live 2026-10-05 ~16:20 UTC, ~19:30 UTC, and again ~22:15–22:20 UTC on the strip-bz deploy (`/health` `80a15258` — `/v2/plan`/`/v2/strip`/`/v2/reroute` now dose on the breathing-zone basis, `smoke_modifier: 1.09` echoed on the wire; `/admin/api/status` not probeable without the token — check at T-45) unless marked otherwise. Re-run `scripts/verify_numbers.sh` before filming — the live column is the truth (it needs python ≥3.12 and crashes `mid(None)` if a probed mode is absent — metro+walk drops after transit service hours; read the partial table).

**cut3 pass (2026-10-05 ~17:45 UTC, image `a5ab92d8`):** `/v2/skill` is
LIVE — the model-grades-itself card sits in /admin's archive grid and
holds a real table already (7 pairs / 847 cells / MAE 18.4 / bias +18.1 /
55.6% band-hit, every horizon honestly `thin` — min 5 pairs). Both
build-sha surfaces agree (`a5ab92d8` on `/health` AND
`/admin/api/status`) — the lag wart is resolved on this image. Landing
hero reads **3.5 cigarettes ≈1,099 µg** (drifts with the field).
`assemble.sh` cut = `~/video/cut3.mp4` (157 s): app beats re-shot on
iOS-sim dev client at HEAD `321e3c1` (no Android/KVM on this box — the
APK lane covers the release build), web beats re-verified same-day.

## Recording setup

- Browser at 100 %, incognito window, bookmarks bar off, notifications off.
- Record at 1080p 60 fps (OBS). Cut the dead time between clicks.
- Have every page open in a tab *before* recording; the demo must never show
  a loading spinner.
- Warm the backend first: `tools/warm_task.py` (server/ working dir) —
  cold first probes can take 3–8 s and look broken on camera.
- **The AWS console window is filmed by the owner himself**
  (see `docs/plan/aws-console-shotlist.md` — ECS service ACTIVE 1/1, task
  image URI = the commit you last deployed, CloudWatch live logs, CodeBuild
  history, NLB target health). Know which AWS account/region you're in
  before you press record.

## The product arc on screen (in order)

1. **Landing — the dosimeter hero** (0:00–0:12) — `/`
   - Verdict in 5 seconds: *"a personal dosimeter for Delhi air — no
     device."* Say the one line: "the field knows what Delhi breathed; the
     app knows what you breathed."
   - Show the live field canvas breathing; scrub the forecast hours so the
     plume visibly shifts. One click into a→b dose route (don't dwell —
     beat 3 is the full dose beat). The day-note under the hero now
     carries the "why tonight" line (`6e82f29`) — let it be seen on
     frame, don't read it.

2. **Your-day card — /v2/day** (0:12–0:35)
   - `GET /v2/day?lat&lon` at Connaught Place — JSON pretty view or the day
     card: today's heavy window, cleanest slot, and the decisions they
     change.
   - Numbers to say verbatim (tonight's probe, build `80a15258`):
     *"heaviest stretch runs 22:30 IST → day end at ~159 µg/m³, least-bad
     window ~12:30–18:30 at ~45, against a ~105 µg/m³ day mean"* — and
     the `decisions` card translated them: "open ~12:30–18:30; shut from
     ~22:30 IST; before ~22:30 — heavy through day end."
     The `decisions: []` wart is resolved on `6e82f290` (the fallback
     shipped); a flat/no-window day can still return both windows null
     — then read `hours[]` + `day_mean_pm25` out loud. Re-read T-45.
   - One line: "the card is your forecast as a decision — outdoor exercise
     in the least-bad window, kids indoors before the stretch." Mention
     honestly: the card data ships on the API today; the app day-view is
     the on-device ledger.

3. **The dose gap — /v2/plan** (0:35–1:05)
   - Connaught Place → Gurugram, ~31 km. Ranked ladder: **car AC ~11 µg,
     auto ~32, cycle ~159, walk ~358 — a ~33× spread on a Delhi
     commute** (33.2× tonight on the breathing-zone basis, `smoke_modifier`
     1.09 echoed on the wire; has run 31–45× — "about thirty-five times"
     is the honest line).
   - One line: *"your dose is not the city's AQI — it's decided by the
     vehicle and the route."* When metro+walk appears (~44 µg GTFS row):
     it doses ~4× a sealed car (~44 µg vs ~11 tonight) — the walk at both
     ends costs it. Metro rows are honestly absent outside service hours.
   - Click the least-smoke corridor alternate if it appears (engine-only
     rows) — tonight's route names: via Outer Circle–Radial 7 / Gol
     Dakkhana–Pandit Pant Marg / Baba Kharak Singh–Sansad Marg.
   - Don't read the whole table — 4 modes and the spread are the story.
   - ⚠ **transit cold-start — mostly fixed**: GTFS feeds are now baked
     into the image (`tools/bake_gtfs.py` at docker build) and warmed
     before the task goes healthy — the old silent-empty/degraded first
     ~30–60 min is gone on current task-defs. Still verify a metro/bus row
     exists T-45 (go-nogo #6); if transit is somehow absent on stage, the
     5 road modes alone still carry the ~35× line.

4. **Lung reach + the city ledger — /city** (1:05–1:35)
   - `/city` district choropleth for ~8 s (Delhi's public ledger face).
   - Then the **"where can your lungs go?"** veil — a **25 µg walking
     budget from Connaught Place settles ~3,211 road segments (~141 km
     of street — drifted; re-check T-45)** — the real Dijkstra frontier
     painted over streets, not a smoothed circle. Push the budget: ≤50 µg
     walks ~10,510 segments (~554 km — paints in ~1.5 s). Contrast: a
     sealed car on a 25 µg budget settles ~891k directed edges (~75,822 km
     — both directions count; ~1.03 M / ~99,503 km at a 100 µg budget,
     where the 2M-state cap binds before the budget does) — but it takes
     ~4–6 s and the veil paints
     only the nearest 90,000 (the caption says so; `edge_partial` is
     honest).
     **Show the walk presets live; narrate the car number, don't wait for
     it on camera.**
   - One line: *"that's bounded Dijkstra on the same engine that routed
     your commute — a lung-budget, drawn on the map."*
   - The corridor ledger (12 publishable tonight — k≥3, so "honest
     sparsity is the point" if asked) + the day-in-dose ticker (~885 µg
     mid tonight — drifts with the field) sell the "the city's day
     kept as a ledger" line.
   - **New ~6 s, spoken — the "why tonight" beat**: the /city chip under
     the hero reads the day's causal driver from `/v2/why` — tonight:
     *"the air is barely moving — the day's pollution is sitting over
     the city"* (stagnation: boundary layer ~87 m + ~1.1 m/s wind →
     ventilation ~100 m²/s vs ~3,000). One line: *"it says why — and what
     it can't tell: the fires were checked and refused (the wind is
     from the south), the trend honestly says 'not enough history yet'."*
   - **The "what happened" flip is live** (`4ad9e0c` deployed on
     `0908d9ad`+): /city toggles recorded hours from `/v2/archive` over
     the forecast field; pending hours stay unpainted. ~10 s if shown:
     the honest-gap read is the win, not the feature.

5. **The engine room — /admin** (1:35–2:05)
   - "Every number so far has a source." Field pipeline: **~24 live
     WAQI instruments + ~70 model samples, ~2-min-old field** (the model
     sample count is thinner after a cold task — it thickens through the
     hour); FIRMS fires (79 today, 17 belt); the sources trust table names every
     feed's age and why it's trusted. If `wind.known` is still `false`,
     the trust table showing wind *unknown` is itself the honesty story.
   - Point at the **"why tonight · the causal read"** tile (between the
     engine tile and the district chips) — the same `/v2/why` answer,
     on the engine-room side: *"the engine grades its own causality."*
   - The field map with real detections; the engine tile (1,070,459
     edges, 903,058 priced, C++ `alive_core`); kalman/calibration stats
     (LOO calibration MAE 46.1 µg over 94 live stations; weekly LOSO
     MAE 11.31 µg, 24 folds, week 41 — both live on the wire).
   - The **archive tile** — one line: *"the field has recorded Delhi
     hourly since Oct 5 20:00 IST — history, not just forecast;
     `/v2/archive` replays the day, gaps admitted."* (6 snapshots at
     this pass — Oct-5 hours 20–23 + Oct-6 0–1; ~60+ by demo morning —
     the count is itself the proof.)
   - The **model-grades-itself card** (`/v2/skill`, live since the
     `a5ab92d8` deploy) — *"the forecast we served vs the hour we
     recorded": 21 pairs now — h+1 is graded (MAE 16.3 µg/m³, bias
     +15.8, 71.4% cell / 80.0% hour band-hit), h+2 too (29.9/+29.6,
     13.9%/20.0%), and every horizon with under 5 pairs still says
     `thin` instead of pretending."* The honest thin
     state is the story: a scorecard that refuses to bluff.
   - Point at `coverage < 1` / `confidence:"low"` honesty: "where we can't
     support a claim, the field says so itself."

6. **AWS console** (2:05–2:30) — *non-negotiable, owner-filmed*
   - 25 seconds inside the console only (see
     `docs/plan/aws-console-shotlist.md`). ECS → ACTIVE 1/1 → task image
     URI `alive108-api:<deployed_sha>` → CloudWatch live logs → CodeBuild
     Succeeded → NLB targets healthy.
   - **One line spoken over it: "Built on CodeBuild, shipped to ECS
     Fargate, behind a Network Load Balancer — every number you saw was
     this."**

7. **Close** (2:30–2:50)
   - Back on the landing hero (or the ledger in the app). *"Your lungs'
     ledger for Delhi — what you breathed, where it cost you, when to
     breathe easy again. Live at this URL, code public."*
   - Hold the URL on screen ~3 s.

**Total ≈ 2:50.**

## If a beat overruns (the trim plan, in order)

- Beat 4: say reach in one line ("25 µg walks ~141 km of street; a sealed
  car on the same budget settles ~540× more road — the veil admits it
  paints only the nearest 90,000 edges") and skip the budget sweep —
  saves ~15 s.
- Beat 5: drop the field map pan; keep pipeline + trust table — saves ~10 s.
- Beat 2: skip the decision strings, say the two windows — saves ~8 s.

## Numbers that drift (check T-45 before filming)

| number | last verified | check |
|---|---|---|
| dose ladder CP→Gurugram (bz basis — `smoke_modifier` echoes on the wire since `80a15258`) | car-AC 10.8 / car-open 19.6 / bike 24.8 / bus 28.3 / auto 32.0 / metro+walk absent tonight / bus-GTFS 69.3 / cycle 158.8 / walk 358.3 µg — **33.2×** (slowest-vs-best 38.7× tonight) | `POST /v2/plan` (no `fast`) today; has run 31–45× this week as smoke swings. Options count drifts 16–23 (23 now; `metro+walk` absent after service hours — honest, not `degraded`) — GTFS is baked into the image since `c3d9c11`, but verify `metro`/`bus` present + `degraded` absent |
| /v2/day windows | **both present tonight** — heavy 22:30 IST → day end @ ~159.2, cleanest 12:30–18:30 @ ~44.7, day mean ~105.3; `decisions` carried 3 rows | `GET /v2/day` — `hours[]` + `decisions[]` strings; the `decisions: []` fallback is deployed on `6e82f290` (`88e37d5`); a flat/no-window day can still return both windows null — read the extrema out loud |
| /v2/reach | 25 µg walk → ~3,211 edges / ~141 km; 50 µg → ~10,510 / ~554 km; car ≤25 → ~891k edges / ~75,822 km partial (90k paint); car ≤100 → ~1.03 M / ~99,503 km partial (2M-state cap binds) | `GET /v2/reach` — budget settles differently hour to hour; wire time ~1–1.5 s walk, ~4–6 s car |
| field age / station count | ~2 min / 24 WAQI + ~70 model samples | `GET /aqi`, `GET /health` — model samples thin to ~40 after a cold task, climb through the hour |
| fires / modifier | 79 fires, 17 belt; modifier ×1.09 at CP at last probe (sometimes null) | `GET /aqi → smoke_modifier` — fires swing daily; say "fires feed live" not a pinned modifier |
| corridors publishable | 12 | `GET /v2/city` — grows with donations |
| breath/day + community | landing hero **2.8 cigarettes ≈885 µg** this pass (~3.5 ≈1,099 µg at cut3, ~997 / ≈3.16 at 19:30 — drifts with the field); 24 h donation strip donation-dependent (tonight: 6 obs / 14.1 km / 477.3 µg avoided; all-time 22 obs / 14 contributors / 725.9 µg) | landing `/` + `GET /v2/city`, `/community`, `/v2/city/moves` |
| `/v2/why` | live since `0908d9ad`; renders on /city chip + landing day-note + DelhiToday on `6e82f290`. Tonight (`80a15258`): stagnation (VC ~100 m²/s vs ~3,000) — fires refused (S wind 182°), trend `cannot_tell` | `GET /v2/why` — line drifts with drivers; on stage say the live line + one `cannot_tell` item |
| `/health` build_sha | **`80a15258`** on `/health` — the strip-bz deploy, matching the image (wart resolved on this revision; `/admin/api/status` unprobeable without token — check T-45) | if they disagree again on stage, say the ECR image tag / "the afternoon deploy", not the stamp |
| `/v2/skill` | 21 pairs · h+1 graded: MAE 16.3 µg/m³ / bias +15.8 / cell band-hit 71.4% / hour band-hit 80.0% · h+2: 29.9/+29.6/13.9%/20.0% · h=0 and h≥3 still `thin` (min_pairs 5 — says so rather than scoring) | `GET /v2/skill` — pairs grow with the archive; on stage say the live n + the honest-thin line |
| field archive | 8 snapshots since 2026-10-05T20:00 IST (Oct-5 h20–23 + Oct-6 h0–3 recorded; gaps stay gaps) — grows hourly | `GET /v2/archive` → `archive.total_snapshots` + `since_ist` (`?day=` takes YYYY-MM-DD only; bare = today); `/admin` archive tile reads `archive.status()` |

Don't say numbers you didn't just verify. "About" and "roughly" are the
honest words.

## Rules that keep you inside 3:00

- Never narrate a page load. Cut, don't wait.
- If a beat goes long, tighten the *next* beat rather than racing speech.
- The console window is fixed at ~25 s — protect it above all else. If the
  video is running long at beat 4, shorten the reach story, not AWS.
