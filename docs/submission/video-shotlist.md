# Video — ≤3 min recording checklist & shot list

The video is judged — most importantly on **console proof + real product**.
This document lists what must appear, in what order, and how long each beat
gets. Target: **2:45–2:55** so a beat can overrun without breaching 3:00.
The arc now sells the **dosimeter** — the numbers every beat leans on were
re-verified live 2026-10-05 (~19:00 IST, build `a382cdeb`) unless marked otherwise.

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
     stretch runs ~21:30 to day end at roughly 190; the least-bad slot is
     the next hour or two at roughly 60–100."* The endpoint also returns
     the decisions strings — "least-bad window ~18:30–20:30 (avg ~74 vs
     the day's ~137)", "kids outdoors before ~21:30". Re-read them T-45;
     the evening peak moves with the smoke.
   - One line: "the card is your forecast as a decision — outdoor exercise
     in the least-bad window, kids indoors before the stretch." Mention
     honestly: the card data ships on the API today; the app day-view is
     the on-device ledger.

3. **The dose gap — /v2/plan** (0:35–1:05)
   - Connaught Place → Gurugram, ~31 km. Ranked ladder: **car AC ~7 µg,
     auto ~24, cycle ~110, walk ~260 — a ~35× spread on one trip.**
   - One line: *"your dose is not the city's AQI — it's decided by the
     vehicle and the route."* When metro+walk appears (~26 µg GTFS row):
     it doses ~3–4× a sealed car — the walk at both ends costs it.
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
     budget from Connaught Place settles ~4,200 road segments (~187 km of
     street)** — the real Dijkstra frontier painted over streets, not a
     smoothed circle. Push the budget: ≤50 µg walks ~15,000 segments
     (~880 km, engine ~46 ms — paints in ~2 s). Contrast: a sealed car on
     a 25 µg budget settles ~1 M directed edges (~94,000 km — both
     directions count) — but it takes ~5–10 s and the veil paints only
     the nearest 90,000 (the caption says so; `edge_partial` is honest).
     **Show the walk presets live; narrate the car number, don't wait for
     it on camera.**
   - One line: *"that's bounded Dijkstra on the same engine that routed
     your commute — a lung-budget, drawn on the map."*
   - The corridor ledger (10 publishable today — k≥3, so "honest
     sparsity is the point" if asked) + the day-in-dose ticker (~550 µg
     mid for a typical day of moving around) sell the "the city's day
     kept as a ledger" line.

5. **The engine room — /admin** (1:35–2:05)
   - "Every number so far has a source." Field pipeline: **~24 live
     WAQI instruments + ~41 model samples, ~10-min-old field** (the model
     sample count is thinner after a cold task — it thickens through the
     hour); FIRMS fires (79 today); the sources trust table names every
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
| dose ladder CP→Gurugram | car 7.1–7.5 / auto 23–26 / bus ~20–73 / cycle ~110–116 / walk ~261 µg — ~35× | `POST /v2/plan` (no `fast`) today; has run 33–45× this week as smoke swings. Transit rows are cold-start fragile post-deploy — verify `metro`/`bus` present + `degraded` absent |
| /v2/day windows | heavy ~21:30→day end ~178–194; least-bad ~18:30–19:30 ~64–99 (avg ~74 vs day ~137) | `GET /v2/day` — new shape: `hours[]` + `decisions[]` strings; `heavy`/`clean` keys may be null while windows live in the decision lines |
| /v2/reach | 25 µg walk → ~4,200 edges / ~187 km (~16 ms); 50 µg → ~15,100 / ~877 km (~46 ms); car ≤25 → ~1 M edges / ~94,000 km partial (90k paint) | `GET /v2/reach` — budget settles differently hour to hour; wire time ~1–2 s walk, ~5–10 s car |
| field age / station count | ~9–10 min / 24 WAQI + ~41 model samples | `GET /aqi`, `GET /health` — model samples thin to ~40 after a cold task, climb through the hour |
| fires / modifier | 79 fires; belt modifier may be absent at CP (smoke block `{}` at last probe) | `GET /aqi → smoke` — fires swing daily; say "fires feed live" not a pinned modifier |
| corridors publishable | 10 | `GET /v2/city` — grows with donations |
| `/health` build_sha | `a382cdeb` — matches the deployed image tag `alive108-api:a382cdeb` | stamp and tag currently agree — say the revision freely. If a later deploy re-introduces lag, show the ECR tag and say the deploy revision, not the stamp |

Don't say numbers you didn't just verify. "About" and "roughly" are the
honest words.

## Rules that keep you inside 3:00

- Never narrate a page load. Cut, don't wait.
- If a beat goes long, tighten the *next* beat rather than racing speech.
- The console window is fixed at ~25 s — protect it above all else. If the
  video is running long at beat 4, shorten the reach story, not AWS.
