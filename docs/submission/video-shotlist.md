# Video — ≤3 min recording checklist & shot list

The video is judged — most importantly on **console proof + real product**.
This document lists what must appear, in what order, and how long each beat
gets. Target: **2:45–2:55** so a beat can overrun without breaching 3:00.
The arc now sells the **dosimeter** — the numbers every beat leans on were
re-verified live 2026-10-05 (~20:30 IST, build `07cadfdd`) unless marked otherwise. Re-run `scripts/verify_numbers.sh` before filming — the live column is the truth.

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
   - Numbers to say verbatim (from today's probe): *"tonight's heavy
     stretch runs ~22:30 to day end at roughly 120; there's no clean slot
     left — the lightest hour is around 68 against a ~103 day mean."*
     The endpoint returns the decisions strings — "no clean slot left
     today — lightest is 68", "kids outdoors before ~22:30". Re-read
     them T-45; the evening peak moves with the smoke.
   - One line: "the card is your forecast as a decision — outdoor exercise
     in the least-bad window, kids indoors before the stretch." Mention
     honestly: the card data ships on the API today; the app day-view is
     the on-device ledger.

3. **The dose gap — /v2/plan** (0:35–1:05)
   - Connaught Place → Gurugram, ~31 km. Ranked ladder: **car AC ~8 µg,
     auto ~23, cycle ~115, walk ~260 — a ~33× spread on one trip** (has
     run 31–45× — "about thirty-five times" is the honest line).
   - One line: *"your dose is not the city's AQI — it's decided by the
     vehicle and the route."* When metro+walk appears (~26 µg GTFS row):
     it doses ~4× a sealed car (~33 µg vs ~8 today) — the walk at both
     ends costs it.
   - Click the least-smoke corridor alternate if it appears (engine-only
     rows) — current route names: via Sardar Patel Marg / Benito Juarez
     Marg / Rao Tula Ram Marg.
   - Don't read the whole table — 4 modes and the spread are the story.
   - ⚠ **cold-start fragility (verified)**: GTFS feeds download+parse at
     runtime (gitignored, empty in the image). On a fresh task the transit
     arm first returns silent-empty, then `degraded:["transit"]` timeouts
     (~13 s plans), recovering over ~30–60 min. If the demo deploys
     re-touch the service, verify a metro/bus row exists T-45 (go-nogo
     #6); if transit is still absent on stage, the 5 road modes alone
     still carry the ~35× line.

4. **Lung reach + the city ledger — /city** (1:05–1:35)
   - `/city` district choropleth for ~8 s (Delhi's public ledger face).
   - Then the **"where can your lungs go?"** veil — a **25 µg walking
     budget from Connaught Place settles ~3,000 road segments (~131 km of
     street — drifted; re-check T-45)** — the real Dijkstra frontier
     painted over streets, not a smoothed circle. Push the budget: ≤50 µg
     walks ~10,800 segments (~576 km — paints in ~2 s). Contrast: a
     sealed car on a 25 µg budget settles ~1 M directed edges (~87,000 km
     — both directions count) — but it takes ~5–10 s and the veil paints
     only the nearest 90,000 (the caption says so; `edge_partial` is
     honest).
     **Show the walk presets live; narrate the car number, don't wait for
     it on camera.**
   - One line: *"that's bounded Dijkstra on the same engine that routed
     your commute — a lung-budget, drawn on the map."*
   - The corridor ledger (10 publishable today — k≥3, so "honest
     sparsity is the point" if asked) + the day-in-dose ticker (~735 µg
     mid today — drifts with the field) sell the "the city's day
     kept as a ledger" line.

5. **The engine room — /admin** (1:35–2:05)
   - "Every number so far has a source." Field pipeline: **~24 live
     WAQI instruments + ~71 model samples, ~8-min-old field** (the model
     sample count is thinner after a cold task — it thickens through the
     hour); FIRMS fires (79 today, 17 belt); the sources trust table names every
     feed's age and why it's trusted. If `wind.known` is still `false`,
     the trust table showing wind *unknown* is itself the honesty story.
   - The field map with real detections; the engine tile (1,070,459
     edges, 903,058 priced, C++ `alive_core`); kalman/calibration stats.
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

- Beat 4: say reach in one line ("25 µg walks ~187 km of street; a sealed
  car on the same budget settles ~500× more road — the veil admits it
  paints only the nearest 90,000 edges") and skip the budget sweep —
  saves ~15 s.
- Beat 5: drop the field map pan; keep pipeline + trust table — saves ~10 s.
- Beat 2: skip the decision strings, say the two windows — saves ~8 s.

## Numbers that drift (check T-45 before filming)

| number | last verified | check |
|---|---|---|
| dose ladder CP→Gurugram | car-AC 7.8 / car-open 14.2 / bike 17.9 / bus 20.4 / auto 23.1 / metro+walk 33.0 / bus-GTFS 80.3 / cycle 114.7 / walk 258.8 µg — **33.2×** (max 36.7×) | `POST /v2/plan` (no `fast`) today; has run 31–45× this week as smoke swings. Options count drifts 16–20 — transit rows are cold-start fragile post-deploy; verify `metro`/`bus` present + `degraded` absent |
| /v2/day windows | heavy ~22:30→day end ~122 µg/m³; **no clean slot today** (lightest ~68; day mean ~103) | `GET /v2/day` — `hours[]` + `decisions[]` strings; `heavy`/`clean` keys may be null while windows live in the decision lines |
| /v2/reach | 25 µg walk → ~3,020 edges / ~131 km; 50 µg → ~10,756 / ~576 km; car ≤25 → ~958k edges / ~86,879 km partial (90k paint); car ≤50 → ~1.03 M / ~99,500 km partial | `GET /v2/reach` — budget settles differently hour to hour; wire time ~1–2 s walk, ~5–10 s car |
| field age / station count | ~8 min / 24 WAQI + ~71 model samples | `GET /aqi`, `GET /health` — model samples thin to ~40 after a cold task, climb through the hour |
| fires / modifier | 79 fires, 17 belt; modifier ×1.09 at CP at last probe (sometimes null) | `GET /aqi → smoke_modifier` — fires swing daily; say "fires feed live" not a pinned modifier |
| corridors publishable | 10 | `GET /v2/city` — grows with donations |
| `/health` build_sha | `07cadfdd` — an afternoon deploy landed; `/admin/api/status` can disagree (BUILD_SHA lag wart) | say the ECR image tag / "the afternoon deploy", not the stamp — two surfaces can legitimately disagree |

Don't say numbers you didn't just verify. "About" and "roughly" are the
honest words.

## Rules that keep you inside 3:00

- Never narrate a page load. Cut, don't wait.
- If a beat goes long, tighten the *next* beat rather than racing speech.
- The console window is fixed at ~25 s — protect it above all else. If the
  video is running long at beat 4, shorten the reach story, not AWS.
