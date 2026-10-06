# docs/video/shotlist.md — the Oct-8 film, second-by-second

The submission video: **≤3:00, and it MUST show the AWS console** — "if the
video does not show it, it does not count" (`docs/15-win-analysis.md`).
What won last time: a **felt scenario in the first ~20 s** before any
feature ("Parents want independence…" / "It is 3 a.m., payments are
failing…"), then live product, zero slides until the architecture at the
end. This script follows that shape.

Numbers below were re-derived against the live service **2026-10-07 ~05:10
IST** (build `ce01ec5c`, `scripts/verify_numbers.sh`). Everything that
drifts is marked **[T-45]** — re-run the script on film morning and say
"about". The landing hero computes the cigarette figure live, so tape and
the cold-open card always agree if `assemble.sh` is run fresh.

Narration register: plain English, one idea per beat, "about" for every
drifting number. Never say anything the screen can't defend.

## Timeline

| # | beat | in → out | len | on screen | source |
|---|------|----------|-----|-----------|--------|
| 0 | cold open | 0:00 → 0:07 | 7 s | felt-line card (`cards/cold.html`) — "It's 7 a.m. in Delhi. The air outside your door costs about 2.5 cigarettes today." | NEW card, numbers injected live at assemble |
| 1 | title | 0:07 → 0:11 | 4 s | `cards/title.html` — wordmark + tagline + live build sha | NEW card (restyled) |
| 2 | hero — the field | 0:11 → 0:23 | 12 s | landing `/` hero: statusline chips, live PM2.5 field, watch-the-day scrub h+0→h+10→now | `10_hero.mp4` (taped, build `4eb9e1e8`) — re-tape if field looks flat |
| 3 | city — the ledger | 0:23 → 0:43 | 20 s | `/city`: why-line, district choropleth, reach solve + ink veil, day tiles, corridor table | `40_city.mp4` (taped, `4eb9e1e8`) |
| 4 | trip plan — the dose gap | 0:43 → 1:23 | 40 s | web a→b ladder (`30_dosegap.mp4`, 18 s) → app compare→pick→nav (`25_journey.mp4`, 22 s) | both taped (`5fd2990`/`c3bb731` APK) |
| 5 | receipt | 1:23 → 1:31 | 8 s | "You're here." receipt card | `26_receipt.mp4` (`c3bb731`) |
| 6 | ledger | 1:31 → 1:39 | 8 s | trips ledger + 7-day bar | `27_ledger.mp4` (`c3bb731`) |
| 7 | settings provenance | 1:39 → 1:48 | 9 s | drawer → Settings → About → "a real instrument ~2 km from you" | `28_today.mp4` (`c3bb731`) |
| 8 | AWS console | 1:48 → 2:13 | 25 s | owner-filmed: ECS ACTIVE 1/1 → task-def image URI → CloudWatch tail → NLB healthy → DynamoDB `alive108-agg` | **owner tapes** — `docs/plan/aws-console-shotlist.md` |
| 9 | honesty close | 2:13 → 2:35 | 22 s | `/admin` scorecard tail (8 s) → `cards/close.html` honesty ledger (11 s) → settle | `50_admin.mp4` tail + NEW card |
| 10 | end card | 2:35 → 2:42 | 7 s | `cards/end.html` — repo, live URL, AWS inventory, AI disclosure | NEW card (restyled) |

**Total ≈ 2:42** — 18 s of headroom under the cap. Protect beat 8 (AWS)
above everything; if long, trim in this order: city day-tiles dwell
(−5 s), dosegap depart-line dwell (−4 s), ledger (−3 s).

---

## Beat cards

### 0 · Cold open — felt, before product (0:00–0:07)

- **Screen:** `cards/cold.html` — paper card, neutral chip
  "DELHI · OCT 8 · MORNING", serif: *"It's 7 a.m. in Delhi. The air
  outside your door costs about 2.5 cigarettes today."* — footer line:
  *"and nobody tells you."*
- **VO (7 s):** "It's seven a.m. in Delhi. The air outside your door
  costs about two and a half cigarettes today — and nobody tells you."
- **Numbers:** `@@CIGS@@`/`@@UG@@` are injected by `assemble.sh` from
  `GET /v2/city → breath.cigarettes.mid` / `breath.day_inhaled_ug.mid`
  — **2.49 / 787 µg** at write time. The same computation renders live
  on the landing hero, so the card and the next shot never disagree.
  **[T-45]**

### 1 · Title (0:07–0:11)

- **Screen:** `cards/title.html` — masthead hairline "ALIVE·108",
  eyebrow chip "TRACK 01 · AIR — ENVIRONMENTAL HACKS", serif "A ledger
  for your lungs.", footer "live api 65.2.28.40 · live build `@@BUILD@@`".
- **VO:** "This does." *(beat)* "ALive-108 — a personal dosimeter for
  Delhi air. No device."
- The 4 s brand hold answers the cold open's punch line — the winner
  pattern is felt first, name second.

### 2 · Hero — the live field (0:11–0:23)

- **Screen:** `10_hero.mp4` — landing top fold: LIVE hero stat tile
  ("N cigarettes a day — a day of breathing today's field"), statusline
  chips ("54 stations live · field ~9 min fresh · 903k edges priced"),
  the PM2.5 cell map, then watch-the-day scrub h+2→h+10→now.
- **VO:** "A live pollution field over Delhi — rebuilt every fifteen
  minutes from fifty-four government instruments — that you can scrub
  an hour at a time."
- **Claims:** `stations.count=54` (`waqi+dpcc`, `/health`); field
  refresh cadence 15 min (`field_refresh_in_s`, EventBridge
  `alive108` group — `infra/provision.sh`); ~903k priced edges.
  **[T-45: station count falls to 24 if DPCC stalls — say
  "twenty-four live, thirty more when their site comes back"]**

### 3 · City — the public ledger (0:23–0:43)

- **Screen:** `40_city.mp4` — `/city` hero + "why tonight" chip
  (tonight's live read: *"the air is barely moving — the day's pollution
  is sitting over the city"* — stagnation, fires refused on the
  easterly wind), district choropleth, then the reach solve: a 25 µg
  walk budget paints the ink-vein road frontier, caption "every ink line
  is a real road — solved by the engine", day tiles, corridor table.
- **VO:** "Delhi's day, kept as a ledger. Ask it where your lungs can
  go — a twenty-five-microgram walking budget from Connaught Place
  settles about a hundred and ninety kilometres of street. Every line
  is a real road — not a smoothed circle."
- **Claims:** `/v2/reach` walk≤25 µg → **4,279 edges / 191.4 km** live
  now (drifts; ~136 km at the last doc pass); bounded Dijkstra on the
  same engine — `server/v2/reach.py`. **[T-45]**

### 4 · Trip plan — the dose gap (0:43–1:23) — the money shot

Two tapes back to back; the numbers belong to different ODs and are
both honest — don't mix them in one sentence.

**4a — the ladder, web a→b (0:43–1:01, `30_dosegap.mp4`)**

- **Screen:** a→b armed on the landing field map, Connaught Place →
  Gurugram priced corridor, mode ladder, depart line.
- **VO:** "Same city, same minutes — the mode decides the dose.
  Connaught Place to Gurugram: a sealed car, about nine micrograms.
  An auto, twenty-five. The metro, sixty-three — the clean coach pays
  for the walks at both ends. On foot, two hundred and eighty-two."
- **Claims (`POST /v2/plan` live now):** car 8.5 · car-open 15.5 ·
  bike 19.6 · bus 22.3 · auto 25.2 · metro+walk 62.7 · cycle 125.2 ·
  walk 282.5 µg — **33.2×** on the breathing-zone basis
  (`smoke_modifier` 1.08 on the wire). 31–45× across ODs this week —
  "about thirty-three" is the honest phrasing. **[T-45]**

**4b — the phone does it (1:01–1:23, `25_journey.mp4`)**

- **Screen:** app — "Where to?" → "India Gate" suggestions → compare
  sheet (petrol chip, dose-by-hour sparkline, mode ladder) → pick
  "Bike/scooter · least smoky way · ≈5 µg" → Start → nav: dose ticking
  ≈0.1→0.6 µg, km-left counting down.
- **VO:** "That's about thirty-three times on one commute. On the
  phone it's simpler: pick the least-smoky way — and it navigates,
  counting what you breathe as you go."
- **Claims:** compare-sheet + ticking dose are the shipped binary's
  real renders (`c3bb731` tape, `docs/lanes/video-v8-report.md`).

### 5 · Receipt (1:23–1:31)

- **Screen:** `26_receipt.mp4` — "You're here." card: ≈0.6 µg breathed,
  "98× less than On foot", smokiest ≈63 µg, CO₂ 0 kg, "kept on this
  phone only".
- **VO:** "At arrival it receipts in micrograms — what you breathed,
  what the smokiest way would have added. Kept on this phone only."
- **Claims:** every figure is the tape's own render; the "on this
  phone only" line is the ledger's literal copy. **[T-45 if re-taped]**

### 6 · Ledger (1:31–1:39)

- **Screen:** `27_ledger.mp4` — "1 trip · ≈0.6 µg breathed", 7-day bar,
  rows, "trips stay on your phone · delete all trips".
- **VO:** "Every trip rolls into a ledger that lives on the phone —
  cigarettes, not abstract AQI. No account."
- **Claims:** ledger is an on-device file (`Mobile/src/store/ledger.ts`,
  `PRIVACY.md`); cigarette math is Berkeley Earth (316 µg/cig,
  CIG_UG in ledger.ts).

### 7 · Settings provenance (1:39–1:48)

- **Screen:** `28_today.mp4` — drawer → Settings → About →
  "How numbers are estimated", held on the provenance line: *"right
  now: a real monitoring instrument read ~2 km from you — that's the
  map's honesty, not a model guess."*
- **VO:** "Every number names its source — right now a real instrument
  about two kilometres away, not a model guess."
- **Claims:** `/aqi → nearest_sample_km` = **1.8 km** at Connaught
  Place live now; the explainer line is verbatim on tape (v8 report).

### 8 · AWS console — mandatory (1:48–2:13)

- **Screen:** owner-filmed `80_aws` — click-path and per-frame
  requirements live in `docs/plan/aws-console-shotlist.md` (updated
  for the DynamoDB frame). In order: ECS cluster `alive108` service
  **ACTIVE / 1:1 FARGATE** → running task → **task-def image URI** =
  the deployed build sha → CloudWatch `/ecs/alive108` tail (fresh
  field-refresh lines) → NLB listeners + target group **healthy 1/1** →
  DynamoDB table `alive108-agg` items (aggregate counters, no user
  rows).
- **VO:** "Every number you just saw is this. CodeBuild builds the
  image inside AWS, ECR stores it, ECS Fargate runs it behind a
  Network Load Balancer — the field rebuilds every fifteen minutes,
  and what leaves a phone lands in DynamoDB as counters. Nothing
  per-person exists anywhere."
- **Claims:** `docs/18-aws-architecture.md`, `scripts/deploy.sh`,
  `infra/provision.sh`; `alive108-agg` holds only aggregate counters
  (`docs/submission/writeup.md` §AWS); `/health → build_sha` should
  match the task-def tag — if it disagrees, say the ECR tag (known
  wart, see console shotlist).

### 9 · Honesty close (2:13–2:35)

**9a — the scorecard (2:13–2:21, tail of `50_admin.mp4`)**

- **Screen:** `/admin` — the model-grades-itself card (`/v2/skill`:
  tonight 210 pairs, h+0 MAE 4.2, error widening with horizon) and the
  archive strip (hourly field snapshots since Oct 5, gaps admitted).
- **VO:** "And it grades itself — the forecast we served against the
  hour we recorded, every hour, on the wire."
- **Claims:** `/v2/skill` live; archive `basis:"recorded"`, gaps never
  backfilled (`server/archive.py`).

**9b — the honesty ledger (2:21–2:35, `cards/close.html`)**

- **Screen:** paper card, three rows — "22.8 → 10.5 µg/m³", "6.2
  µg/m³", "k ≥ 3".
- **VO:** "We audit ourselves. Thirty government stations found our
  blind spots at twenty-two-point-eight — after we ingested them,
  ten-point-five, all thirty inside six-point-two. And a street
  publishes only when three distinct devices have crossed it — trips
  never leave the phone."
- **Claims:** `docs/lanes/holdout-reverify-report.md` — former-GAP
  MAE **22.8 → 10.5**, all-30 **27.1 → 6.2**, every station
  `nearest_sample_km = 0.0`, residuals published unexcluded.
  `server/community.py` `_K_MIN_DEVICES=3` — **12 of 54** corridors
  publishable tonight, the rest honestly suppressed (`min_k:3` on the
  wire); trip trims 300 m / thins to 100 m / hashes the device id
  (`server/v2/trip.py`), `/observe` returns 410, pcap-verified
  (`apk-drive-v5-report.md`).

### 10 · End card (2:35–2:42)

- **Screen:** `cards/end.html` — serif "What you breathed — and what
  you didn't." + mono rows: live URL, repo, AWS inventory, data
  credits, "ai tools used: Devin (Cognition AI)".
- **VO:** "ALive-108 — what you breathed, and what you didn't. Live,
  and the code is public."

---

## Claims ledger — every spoken number, traced

| spoken claim | value at write (05:10 IST, `ce01ec5c`) | truth source |
|---|---|---|
| "two and a half cigarettes" | 2.49 mid (hi 6.29) · 787 µg | `GET /v2/city → breath` — landing hero renders same math |
| "fifty-four instruments / every fifteen minutes" | 54 (24 WAQI + 30 DPCC) · refresh 900 s | `GET /health → sources.stations`, `field_refresh_in_s`; `infra/provision.sh` |
| "about a hundred and ninety kilometres" | 191.4 km / 4,279 edges | `GET /v2/reach?mode=walk&budget_ug=25` |
| "nine … twenty-five … sixty-three … two hundred and eighty-two … thirty-three times" | 8.5 / 25.2 / 62.7 / 282.5 µg → 33.2× | `POST /v2/plan` CP→Gurugram (smoke_modifier 1.08 on wire) |
| "point six micrograms, ninety-eight times less" | tape values (`c3bb731` beat 26) | `docs/lanes/video-v8-report.md` beat table |
| "a real instrument about two kilometres away" | 1.8 km at CP | `GET /aqi → nearest_sample_km` + v8 tape line |
| "twenty-two-eight … ten-point-five … six-point-two" | fixed (Oct-6/7 holdouts) | `docs/lanes/holdout-reverify-report.md` |
| "three distinct devices" | `min_k:3`; 12/54 publishable | `GET /v2/city/moves`; `server/community.py` |
| "grades itself … every hour" | `/v2/skill` live, ~210 pairs | `docs/lanes/judge-proof.md` #9; admin scorecard |
| "built by CodeBuild … Fargate … NLB … DynamoDB … Secrets Manager" | deployed, not claimed | `docs/18-aws-architecture.md`; console beat films it |

## Film-morning checklist (in order)

1. `bash scripts/verify_numbers.sh` — re-derive every [T-45] figure;
   update VO numbers that moved (round to "about N").
2. `tools/warm_task.py` exits 0 — no cold-plan spinner on tape.
3. Owner films `80_aws` per `docs/plan/aws-console-shotlist.md`
   (now includes the DynamoDB `alive108-agg` frame).
4. `bash scripts/video/assemble.sh` — fills `@@BUILD@@`/`@@CIGS@@`/
   `@@UG@@`/`@@DATE@@` live, drops cards in, emits the cut.
5. Watch once end-to-end at 1×: the cold-open number must equal the
   landing-hero number on the next shot; the ladder numbers must be
   "about" the live ladder.

## Inventory — what exists vs what's needed

| beat file | taped on | status |
|---|---|---|
| `10_hero.mp4` | web, `4eb9e1e8` | ✅ usable — re-tape only if the field is flat on film morning |
| `40_city.mp4` | web, `4eb9e1e8` | ✅ usable |
| `30_dosegap.mp4` | web, `4eb9e1e8` | ✅ usable — ladder drift covered by "about" phrasing |
| `25_journey.mp4` | APK `c3bb731` | ✅ canonical app take |
| `26_receipt.mp4` / `27_ledger.mp4` / `28_today.mp4` | APK `c3bb731` | ✅ canonical |
| `50_admin.mp4` | web, `4eb9e1e8` | ✅ usable — close beat takes the **tail** (scorecard + archive strip), `-ss ~11` |
| `80_aws` | — | ⏳ **owner tapes on film morning** (console needs his login) |
| `cards/title.html` `cold.html` `close.html` `end.html` | — | ✅ this lane — paper register, live placeholders injected |
| bench: `05_landing`, `20_home`, `22_doors`, `65_community`, `90_close` | mixed | spares if a beat under-runs or needs an alt take |
