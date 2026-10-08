# 3-minute demo script — every number real

Run `python3 scripts/research/freshness_probe.py` ~10 min before going
on — it prints every number this script quotes, re-read fresh. If a
number has drifted, say the probe's number. All reads are GET-only
against `http://65.2.28.40` — no token, no POST, no admin paths.
Timing: ~3 min across 6 beats.

---

**[0:00–0:25] Beat 1 — the number nobody tells you**
*(brief: "Delhi's air is the worst in the world and nobody tells you how
much of it you actually breathe")*

> "That number — **79.6** — is the micrograms of PM2.5 in each cubic
> metre of air at Connaught Place right now. US AQI **160**. Nobody in
> this city is told what that costs them. That's what Alive does."

Screen: `/aqi` card — `pm25 79.6`, `us_aqi 160`, `pm10 195.2`,
`no2 46.9`, band `[49.1–110.0]`, `nearest_station_km 1.7`.

**[0:25–0:50] Beat 2 — where it comes from (CPCB/OpenAQ + freshness)**
*(brief: live sources + freshness/sparsity transparency)*

> "This isn't a model guess. **52 real government monitors** — CPCB and
> DPCC instruments — feed it live through two free public pipes, and the
> `/health` page shows which pipes are up: `waqi: ok`, `dpcc: ok`, the
> field **8 minutes old**. When a pipe dies, it says `refused` or
> `unavailable` — it never says `ok`."

Screen: `/health` → `sources.stations` (count 52, feeds waqi+dpcc ok),
`field_age_s`, `model.source "waqi+dpcc-stations+open-meteo/cams"`.
Name the dark legs honestly if asked: `api.data.gov.in` is refused from
our network, the OpenAQ key on file is revoked — the wire shows that
too, it's why two pipes exist.

**[0:50–1:20] Beat 3 — the purest-route picker**
*(announced Day-1: purest-route picker, live air + all routes; brief:
concrete exposure-drop + time penalty)*

> "Same trip — India Gate to HUDA City Centre, **28.5 km**. Car with
> the AC on: **14 µg** breathed. Bus: **36.6**. Two-wheeler: **28.8**
> but you're out in it — and on foot it's **501**. Same start, same
> end, a **36× difference** in what you breathe. Every option is priced
> in dose, not just minutes — AC cabin sealed vs open air is the
> honest answer nobody else shows."

Screen: `/compare` chooser — 8 options, dose µg + `dose_vs_best_pct`
per mode (Car AC 0%, windows down +81%, bike +106%, bus +161%,
metro +walk +181%, auto +194%, bicycle +1487%, foot +3481%).

**[1:20–1:45] Beat 4 — what a day costs, and the best hour**
*(announced Day-1: best hour to go out and play; brief: who-it-helps)*

> "A delivery rider working 8 hours on a two-wheeler starting 7 am
> breathes **403 µg of PM2.5 — 1.3 cigarettes a day, 4.8× what sitting
> at a desk costs.** That's who this is for. And when's the least-bad
> hour? A typical October at this spot dips to **64 around 5 pm** —
> tonight the live forecast says it climbs to **101 by 3 am**, and
> tomorrow's cleanest window is **11:30–2:30 at ~64**."

Screen: `/shift` (dose_ug 402.9, range 260.8–586.9, vs_desk +380%,
cigarettes 1.3), `/v2/today` hourly curve (min ~64 at 17:00 IST),
`/v2/outlook` cleanest windows + verdict.

**[1:45–2:15] Beat 5 — sparse-station honesty**
*(brief: "transparency reads as competence")*

> "Where we don't know, we say so. Jhajjar tonight is covered by
> **1 grid cell** — the wire marks it `confidence: "sparse"` and
> `centroid_read: true`. Delhi's own district reads **86** across 265
> cells with `confidence: "field"`. Every number carries its band —
> 79.6 tonight could honestly be anywhere in **49 to 110** — and that
> band was *measured*: it brackets 95% of held-out station-hours over
> 3,550 replayed hours. The cleanest named place near CP right now is
> Cedar Avenue at **55.6 — 25% cleaner** — because the whole NCR is
> scored from the same field."

Screen: `/v2/districts` (Delhi NCT 86.0/conf field vs Jhajjar sparse,
cells_covered 1, centroid_read), `/escape` best (Cedar Avenue 55.6,
−25%), `/aqi` band lo/hi.

**[2:15–3:00] Beat 6 — tonight's air, explained + AWS**
*(brief: visible AWS; one working feature > five)*

> "Why is it bad tonight? The answer's on the wire: **16 crop fires in
> the Punjab–Haryana belt**, but the wind is carrying it *away* — the
> real driver is the air barely moving: ventilation is **344 m²/s vs a
> typical ~3,000**, and the city's average climbed **59 → 83 in six
> hours**. That's one honest pipeline — stations, model, fires, wind —
> running on AWS Fargate, snapshots on S3, keys in Secrets Manager,
> rebuild metrics in CloudWatch. Delhi doesn't need another dashboard
> that pretends to know. It needs one that says what it knows, what it
> doesn't, and what a breath costs."

Screen: `/v2/why` drivers (fires carrying:false, VC 343.5 vs ~3000
typical, trend +24.2 over 5.9h), `/health` stack (ecs/fargate, S3
history, build_sha) — if the AWS console is shown, ECS service
`alive108` + the `/health` page side by side.

---

*Contingency:* if prod is down, `GET /health` returning anything
non-200 → say so out loud ("the service is down — here's the last
honest read") and open the committed snapshot
`server/data/field/snapshots/` instead — the degradation path is part
of the demo.
