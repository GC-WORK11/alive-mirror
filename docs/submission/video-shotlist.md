# Video — ≤3 min recording checklist & shot list

The video is judged — most importantly on **console proof + real product**.
This document lists what must appear, in what order, and how long each beat
gets. Target: **2:45–2:55** so a beat can overrun without breaching 3:00.
The arc now sells the **dosimeter** — the numbers every beat leans on were
re-verified live 2026-10-05 (~18:00 IST) unless marked otherwise.

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
     stretch ~21:30–23:30 at roughly 250; the least-bad slot ~17:30–19:30
     at roughly 90."*
   - One line: "the card is your forecast as a decision — outdoor exercise
     in the least-bad window, kids indoors before the stretch." Mention
     honestly: the card data ships on the API today; the app day-view is
     the on-device ledger.

3. **The dose gap — /v2/plan** (0:35–1:05)
   - Connaught Place → Gurugram, 23.7 km. Ranked ladder: **car AC ~6 µg,
     auto ~17, metro+walk ~26, cycle ~84, walk ~190 — a ~33× spread on one
     trip.**
   - One line: *"your dose is not the city's AQI — it's decided by the
     vehicle and the route."* Honest surprise: metro+walk doses ~4.6× a
     sealed car — the walk at both ends costs it.
   - Click the least-smoke corridor alternate if it appears (engine-only
     rows, no GTFS) — "via Outer Circle, 19–96 % divergent path."
   - Don't read the whole table — 4 modes and the spread are the story.

4. **Lung reach + the city ledger — /city** (1:05–1:35)
   - `/city` district choropleth for ~8 s (Delhi's public ledger face).
   - Then the **"where can your lungs go?"** veil — a **25 µg walking
     budget from Connaught Place settles ~2,500 road segments (~107 km of
     street)** — the real Dijkstra frontier painted over streets, not a
     smoothed circle. Push the budget: ≤50 µg walks ~9,500 segments
     (~490 km). Contrast: a sealed car on a 10 µg budget settles ~580k
     edges (~39,500 km — directed edges, both directions count).
   - One line: *"that's bounded Dijkstra on the same engine that routed
     your commute — a lung-budget, drawn on the map."*
   - The corridor ledger + the day-in-dose ticker (~540 µg mid for a
     typical day of moving around) sell the "the city's day kept as a
     ledger" line. If corridors publish sparse today, say "k≥3 — honest
     sparsity is the point."

5. **The engine room — /admin** (1:35–2:05)
   - "Every number so far has a source." Field pipeline: **~23–24 live
     WAQI instruments + ~60–70 model samples, ~4-min-old field**; FIRMS
     fires (71 today, 16 inside the belt → ×1.27 modifier); the sources
     trust table names every feed's age and why it's trusted.
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

- Beat 4: say reach in one line ("25 µg walks ~107 km of street; a sealed
  car settles ~370× more road on a smaller budget") and skip the budget
  sweep — saves ~15 s.
- Beat 5: drop the field map pan; keep pipeline + trust table — saves ~10 s.
- Beat 2: skip the decision strings, say the two windows — saves ~8 s.

## Numbers that drift (check T-45 before filming)

| number | last verified | check |
|---|---|---|
| dose ladder CP→Gurugram | 5.7 / 10.4 / 13.1 / 16.9 / 15.0 / 26.4 / 84.1 / 189.7 µg — ~33× | `POST /v2/plan` today; it has run 34–45× this week as smoke swings |
| /v2/day windows | heavy 21:30–23:30 ~247; clean 17:30–19:30 ~94 | `GET /v2/day` — windows shift with the evening peak |
| /v2/reach | 25 µg walk → 2,473 edges / 107 km; 50 µg → 9,524 / 490 km | `GET /v2/reach` — budget settles differently hour to hour |
| field age / station count | ~4 min / ~23–24 WAQI + ~60–70 samples | `GET /aqi`, `GET /health` — model-sample count drifts 59–72 |
| fires / modifier | 71 (16 belt) / ×1.27 | `GET /aqi → smoke` — fires swing daily |
| corridors publishable | 10 of 54 | `GET /v2/city` — grows with donations |
| `/health` build_sha | `c7df5db5` — **but the deployed image tag is `1e93b9f2`** | the BUILD_SHA stamp currently lags the image; show the ECR tag in the console and say the deploy revision, not the stamp |

Don't say numbers you didn't just verify. "About" and "roughly" are the
honest words.

## Rules that keep you inside 3:00

- Never narrate a page load. Cut, don't wait.
- If a beat goes long, tighten the *next* beat rather than racing speech.
- The console window is fixed at ~25 s — protect it above all else. If the
  video is running long at beat 4, shorten the reach story, not AWS.
