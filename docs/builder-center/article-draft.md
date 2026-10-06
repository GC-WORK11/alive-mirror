# Builder Center article — ALive-108 (draft for builder.aws.com)

## Title options (pick one)

1. **We built a PM2.5 dosimeter with no hardware — then audited it against government instruments it can't see** *(recommended — the honest-engineering hook is the whole story)*
2. Your lungs' ledger for Delhi: honest numbers from a no-hardware air-quality dosimeter on AWS
3. We measured our pollution field against 30 government stations it never reads — here's what missed, and what we did about it
4. A personal dosimeter for Delhi's air, built on ECS Fargate: the build, the misses, the fix

## Submission-form abstract (~120 words)

ALive-108 is a personal PM2.5 dosimeter for Delhi with no hardware: the phone reconstructs what you breathed — timeline × a live concentration field → dose, computed on-device; only consented k≥3 aggregates ever leave. On one measured commute, mode choice alone changed inhaled dose 33×. The field rebuilds every 15 minutes on ECS Fargate from 54 ground instruments, ~70 model samples, and NASA FIRMS fire detections, behind a Network Load Balancer, with S3 field artifacts, DynamoDB aggregates, Secrets Manager, CodeBuild deploys, and EventBridge-scheduled rebuilds. We validated the field against 30 government DPCC stations it never ingests (~23 µg/m³ MAE at provably blind sites), published the misses, then closed the blind spots with a second ingest adapter.

---

## The article

It's 7am in Delhi in October — parali season, the weeks when stubble fires in Punjab and Haryana push the city's PM2.5 to 10–20× the WHO guideline. The air outside your door will cost you roughly four cigarettes' worth of particulate today, and nobody told you. Every tool that exists answers *"how bad is it"* — an AQI lookup. We built the tool that answers *"what did it cost me, and what do I do about it."*

**ALive-108 is a personal PM2.5 dosimeter with no hardware.** Personal-exposure reconstruction — timeline × concentration field → individual dose — is an established research method nobody ships to consumers. The field is sampled per-cell per-hour; the phone already knows where it was. Your day is reconstructed **on-device**; the only things that ever leave are consented, privacy-floored aggregates. Live now at `http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com` — the public API, dashboards, and `/health` are open.

### The field underneath

Every 15 minutes the service rebuilds a kriged concentration surface over Delhi NCR: 54 live ground instruments today + ~70 CAMS/Open-Meteo model samples + NASA FIRMS fire detections (a stubble-smoke modifier gated by wind direction — more on that below), each cell carrying a real σ band. A C++ engine re-prices 903,058 of 1,070,459 road edges so inhaled dose is a first-class routing criterion: `dose = concentration × micro-environment factor × ventilation rate × time`, integrated every ~250 m along real route geometry. On a measured Connaught Place → Gurugram commute, a sealed AC car inhales ~10.8 µg while walking the same 23.7 km inhales ~358 — a 33× gap that matches published Delhi commuter studies (walking ≈28× the metro per km).

### We audited ourselves against instruments we never touch

Honest numbers are easy to claim. So on the evening of October 6 we ran an independent holdout: the Delhi Pollution Control Committee publishes raw 5-minute PM2.5 from 30 government stations — a completely different instrument network than anything our field ingested (our blend carried 24 stations that night, none of them DPCC). For each station we classified whether our field provably cannot see it (nearest field sample ≥1 km), then compared our served `pm25_ambient` against the station's raw reading, three rounds, 81 observations. Nothing tuned, nothing filtered:

| class | stations | obs | MAE µg/m³ | RMSE | bias |
|---|---|---|---|---|---|
| GAP — provably blind (1.5–5.8 km) | 7 | 16 | **22.8** | 26.5 | +3.2 (+6%) |
| LIVE-ADJ — instrument in the blend | 6 | 16 | **16.4** | 19.3 | −9.2 |
| ANCHOR — model point on-site | 17 | 49 | **31.9** | 39.8 | −24.6 |
| **All 30 sites** | 30 | 81 | **27.1** | 34.2 | −16.0 |

The blind sites were the *best-behaved* class — ~23 µg/m³ MAE with near-zero bias. The misses were real and they were at anchors: Jahangirpuri read 143 while we served 73 (−68); Sonia Vihar −63; Rohini −53. Local hotspots flare up to 2× what a blend built from instruments elsewhere can see. We also over-read: IGNOU showed 27 true while we served ~65. That table is the honest answer to "how accurate is it at my home" — tight within ~2 km of an instrument, honest-but-coarse in the gaps, and it's why every estimate on the wire carries its band and the distance to the nearest real reading, not a single confident number.

### Then we closed the blind spots

Publishing the misses was half the story. The other half: the same DPCC 5-minute pages we used as truth became a second ingest adapter — `ingest_dpcc.py`, flag-gated behind `ALIVE_DPCC_INGEST`, appending to the WAQI backbone rather than competing with it. The interesting engineering: the site's index tree lists only 24 stations; the nav bar on each station page carries a 30-station superset — and the 6 hidden stations were exactly our verified blind spots (IGNOU, JNU, CWG Akshardham, NSUT West, Talkatora Garden, SBV Delhi Cantt). The adapter asserts the `µg/m³` unit token per row (if the site ever switches to indices, values are refused, never reinterpreted), drops stale rows and physically impossible ones (PM2.5 > PM10), and is now live: **54 ground instruments** feed the blend, and every former GAP site has an instrument at ~0 km. The residual risk is honestly smaller stuff — instrument-vs-blend disagreement at the ~16 MAE scale, not blind-gap error.

### The parali-season stress test

The same evening, a second watch probed the live service 14 times across ~8 hours — through the evening pollution ramp **and three mid-watch deploys**. The number that mattered: the stubble-smoke claim follows the wind *in both directions*. With wind at 344° (inside the NW fetch quadrant), the engine claimed fires — belt 14 → 15 live FIRMS detections, ×1.24 modifier. When the wind swung to 15°→139° (easterly), the claim was refused: modifier downscaled to exactly ×1.07 (the documented 30% off-quad factor, re-derived against the code each probe), the fires driver vacated `drivers[]`, and stagnation took over the headline — while `evaluated.fires` kept disclosing the checked-but-not-claimed read. Meanwhile the trend recorder caught the regime flip live (−7.5 → +35.7 µg city-scale over 6h), and one >20% dose/ambient ratio flag decomposed to a verified spatial gradient (CP 75 → Gurugram 97 µg/m³ across three independent reads) — honest field structure, not a scaling bug.

### Privacy as architecture, not policy

The dose ledger lives in a file on the phone — 500-trip cap, delete-all, no account. Donation is opt-in: a donated trip is trimmed on-device, then re-trimmed, thinned and rounded server-side, and folded into ~500 m cells at ingest — **no per-trip row exists in memory, on disk, or in S3**. Nothing publishes below k=3 distinct devices over 72 h (`min_k` is literally on the wire; 12 of 54 tracked corridor cells are publishable today and the other 42 are honestly suppressed). The raw-coords endpoint is retired 410 Gone; access logs are off; the contributor id is a 64-bit CSPRNG that rotates every 30 days; `DELETE /v2/ledger` wipes server-side history. We can't leak what we never take.

### What AWS services did the work

- **ECS Fargate** (ap-south-1, FARGATE_SPOT, 1 vCPU / 3 GB) — runs the FastAPI service, the C++ pybind engine, and the osrm sidecar in one task. App Runner refused new accounts (`SubscriptionRequiredException`); Fargate is the same serverless story with no gate.
- **Network Load Balancer** — the stable public endpoint that survives every redeploy; each deploy re-registers the live task's IP.
- **CodeBuild → ECR** — images are built *inside* AWS (`git archive → S3 → buildspec → docker build → push → update-service`); no local Docker needed, ~10–15 min per deploy.
- **S3** — the last-good field snapshot (the field survives task restarts), community aggregate state, the hour-bucketed field archive (`archive/field-*.json.gz` — Delhi's air as replayable history), and the pmtiles basemap artifact. OpenAQ's public S3 archive supplied the decade climatology baked into the image.
- **DynamoDB** (`alive108-agg`) — aggregate trip counters only; no user rows exist anywhere by design.
- **Secrets Manager** — upstream API keys and the admin token; nothing in the repo.
- **EventBridge Scheduler** (`alive108` group) — the 15-minute field-rebuild cadence, a daily rollup, and a weekly validation schedule.
- **CloudWatch + Budgets** — a field-age alarm (missing data breaches, not just errors) and a cost alarm; worst case ~$46/month, inside the event credits.

### What we don't claim

Phones measure nothing — traversals adjust dose *estimates*, never the field. The forecast is CAMS + stagnation physics, not ground truth — thin cells say `confidence:"low"`, out-of-area queries get a typed refusal, and feeds that serve nothing report themselves dormant instead of pretending. We publish that we over-read in clean air and under-read local hotspots; the holdout table above is the claim, not a disclaimer.

### What's next

- **Re-run the holdout on prod with DPCC live** — the number to publish is GAP-class MAE recomputed against the same 30 instruments; expected to collapse toward the ~16 live-adjacent level. Same method, new table.
- **Grow the aggregate layer honestly** — more donated trips means more corridor cells cross the k≥3 floor; the suppression counter on the wire is the scoreboard.
- **Close the refresh gap** — field cycles ran 26–60 min against a 15-min TTL on a heavy night; tightening the rebuild path is the known fix.
- **From detector to driver** — sharper FIRMS-belt resolution and wind-field transport, so the stubble claim gets earlier and more local during the November peak.

The repo, the validation reports, and every number above trace to a live endpoint or a committed file — that was the point of building it this way.
