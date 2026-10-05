# Video — ≤3 min recording checklist & shot list

The video is judged — most importantly on **console proof + real product**.
This document lists what must appear, in what order, and how long each beat
gets. Target: **2:45–2:55** so a beat can overrun without breaching 3:00.
The arc now sells the **dosimeter** — the numbers every beat leans on were
re-verified live 2026-10-05 ~16:20 UTC (deployed image + `/health` `cb862533`; `/admin/api/status` still stamps `ec51c882` — wart live) unless marked otherwise. Re-run `scripts/verify_numbers.sh` before filming — the live column is the truth.

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
     beat 3 is the full dose beat).

2. **Your-day card — /v2/day** (0:12–0:35)
   - `GET /v2/day?lat&lon` at Connaught Place — JSON pretty view or the day
     card: today's heavy window, cleanest slot, and the decisions they
     change.
   - Numbers to say verbatim (from tonight's probe): *"no sustained
     window left today — the lightest hour reads ~78 now, rising to ~105
     by 23:30, against a ~90 µg/m³ day mean; heaviest hour ~23:30."*
     ⚠ on the deployed build (`cb862533`) a no-window evening returns
     `decisions: []` — read `hours[]` + `day_mean_pm25` out loud instead;
     the plain-words fallback is fixed in code and rides the next image.
     Re-read them T-45; the evening peak moves with the smoke.
   - One line: "the card is your forecast as a decision — outdoor exercise
     in the least-bad window, kids indoors before the stretch." Mention
     honestly: the card data ships on the API today; the app day-view is
     the on-device ledger.

3. **The dose gap — /v2/plan** (0:35–1:05)
   - Connaught Place → Gurugram, ~31 km. Ranked ladder: **car AC ~10 µg,
     auto ~30, cycle ~148, walk ~335 — a ~35× spread on a Delhi
     commute** (33.1× tonight; has run 31–45× — "about thirty-five times"
     is the honest line).
   - One line: *"your dose is not the city's AQI — it's decided by the
     vehicle and the route."* When metro+walk appears (~39 µg GTFS row):
     it doses ~4× a sealed car (~39 µg vs ~10 tonight) — the walk at both
     ends costs it.
   - Click the least-smoke corridor alternate if it appears (engine-only
     rows) — current route names: via Sardar Patel Marg / Benito Juarez
     Marg / Rao Tula Ram Marg.
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
     budget from Connaught Place settles ~2,300 road segments (~98 km of
     street — drifted; re-check T-45)** — the real Dijkstra frontier
     painted over streets, not a smoothed circle. Push the budget: ≤50 µg
     walks ~8,900 segments (~449 km — paints in ~1.5 s). Contrast: a
     sealed car on a 25 µg budget settles ~836k directed edges (~69,500 km
     — both directions count; ~1.03 M / ~99,500 km at a 100 µg budget,
     where the 2M-state cap binds before the budget does) — but it takes
     ~4–6 s and the veil paints
     only the nearest 90,000 (the caption says so; `edge_partial` is
     honest).
     **Show the walk presets live; narrate the car number, don't wait for
     it on camera.**
   - One line: *"that's bounded Dijkstra on the same engine that routed
     your commute — a lung-budget, drawn on the map."*
   - The corridor ledger (10 publishable today — k≥3, so "honest
     sparsity is the point" if asked) + the day-in-dose ticker (~944 µg
     mid tonight — drifts with the field) sell the "the city's day
     kept as a ledger" line.
   - **Optional ~10 s if the next image lands before filming**: the
     "what happened" flip — /city toggles recorded hours from
     `/v2/archive` over the forecast field; unrecorded hours say "no
     snapshot recorded" (commit `4ad9e0c` is on base/v2 but NOT deployed
     tonight — verify on the morning build; skip the line if the toggle
     isn't there). The honest-gap read is the win, not the feature.

5. **The engine room — /admin** (1:35–2:05)
   - "Every number so far has a source." Field pipeline: **~24 live
     WAQI instruments + ~71 model samples, ~14-min-old field** (the model
     sample count is thinner after a cold task — it thickens through the
     hour); FIRMS fires (79 today, 17 belt); the sources trust table names every
     feed's age and why it's trusted. If `wind.known` is still `false`,
     the trust table showing wind *unknown* is itself the honesty story.
   - The field map with real detections; the engine tile (1,070,459
     edges, 903,058 priced, C++ `alive_core`); kalman/calibration stats
     (LOO calibration MAE 46.1 µg over 94 live stations; weekly LOSO
     MAE 11.31 µg, 24 folds, week 41 — both live on the wire).
   - The **archive tile** — one line: *"the field has recorded Delhi
     hourly since Oct 5 20:00 IST — history, not just forecast;
     `/v2/archive` replays the day, gaps admitted."* (2 snapshots at
     re-verify; ~60+ by demo morning — the count is itself the proof.)
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

- Beat 4: say reach in one line ("25 µg walks ~98 km of street; a sealed
  car on the same budget settles ~700× more road — the veil admits it
  paints only the nearest 90,000 edges") and skip the budget sweep —
  saves ~15 s.
- Beat 5: drop the field map pan; keep pipeline + trust table — saves ~10 s.
- Beat 2: skip the decision strings, say the two windows — saves ~8 s.

## Numbers that drift (check T-45 before filming)

| number | last verified | check |
|---|---|---|
| dose ladder CP→Gurugram | car-AC 10.1 / car-open 18.3 / bike 23.2 / bus 26.4 / auto 29.9 / metro+walk 38.7 / bus-GTFS 60.8 / cycle 148.3 / walk 334.6 µg — **33.1×** (max 35.6×) | `POST /v2/plan` (no `fast`) today; has run 31–45× this week as smoke swings. Options count drifts 16–22 (22 tonight) — GTFS is baked into the image since `c3d9c11`, but verify `metro`/`bus` present + `degraded` absent |
| /v2/day windows | **both null tonight** — rising evening remainder, no ≥2 h run either side; day mean ~90.2, heaviest hour ~23:30 IST (~105 µg/m³) | `GET /v2/day` — `hours[]` + `decisions[]` strings; on `cb862533` a no-window day can return `decisions: []` (fallback fixed in code, rides next image) — read the extrema out loud |
| /v2/reach | 25 µg walk → ~2,293 edges / ~98 km; 50 µg → ~8,927 / ~449 km; car ≤25 → ~836k edges / ~69,527 km partial (90k paint); car ≤100 → ~1.03 M / ~99,503 km partial (2M-state cap binds) | `GET /v2/reach` — budget settles differently hour to hour; wire time ~1–1.5 s walk, ~4–6 s car |
| field age / station count | ~14 min / 24 WAQI + ~71 model samples | `GET /aqi`, `GET /health` — model samples thin to ~40 after a cold task, climb through the hour |
| fires / modifier | 79 fires, 17 belt; modifier ×1.09 at CP at last probe (sometimes null) | `GET /aqi → smoke_modifier` — fires swing daily; say "fires feed live" not a pinned modifier |
| corridors publishable | 10 | `GET /v2/city` — grows with donations |
| breath/day + community | ~944 µg mid (≈2.99 cig); 24 h 4 obs/12.9 km/137.3 µg avoided; moves 33 trips over 3 days (car 78.8% / 'other' pool 21.2%, suppressed 0) | `GET /v2/city`, `/community`, `/v2/city/moves` — donation-dependent, drifts hourly |
| `/health` build_sha | `cb862533` live on `/health` and matching the deployed image tag — `/admin/api/status` still reads `ec51c882` (BUILD_SHA lag wart is live again) | say the ECR image tag / "the afternoon deploy", not the stamp — two surfaces can legitimately disagree |
| field archive | 2 snapshots since 2026-10-05T20:00 IST (hours 20,21 recorded; 0–19 honest gaps; 22,23 pending) — grows hourly, gaps stay gaps | `GET /v2/archive` → `total_snapshots` + `since_ist` (`?day=` takes YYYY-MM-DD only; bare = today); `/admin` archive tile reads `archive.status()` |

Don't say numbers you didn't just verify. "About" and "roughly" are the
honest words.

## Rules that keep you inside 3:00

- Never narrate a page load. Cut, don't wait.
- If a beat goes long, tighten the *next* beat rather than racing speech.
- The console window is fixed at ~25 s — protect it above all else. If the
  video is running long at beat 4, shorten the reach story, not AWS.
