# docs/16 — Free-API inventory + decision-engine research

Researched 2026-10-01. Every claim cited or marked UNVERIFIED.

## A. Free APIs worth wiring

| API | Auth | What it adds | Latency | Verdict |
|---|---|---|---|---|
| Open-Meteo forecast + CAMS EU | none | field + wind (in use) | ~200ms | done |
| NASA FIRMS active fire | free MAP_KEY | fire-season modifier (module ready, needs user's key) | ~500ms | owe: key |
| data.gov.in OGD | free api-key | CPCB station feed + **MoRTH black-spot dataset** (8,862 rows, 115 in Delhi, per-spot locations) — blackspot.morth.gov.in, dataful.in/datasets/21559 | static CSV | owe: key — **safety layer** |
| OpenAQ v3 | free key | station measurements backup (S3 archive already used for history — no key needed there) | ~300ms | owe: key (optional) |
| Photon (komoot) | none | address search (in use) | ~250ms | done |
| OSRM public demo | none | routing (in use). NOTE: ignores `alternatives=true` — we synthesize alternates via via-points (main.py `_quieter_route`) | ~200ms | done |
| Valhalla (valhalla1.openstreetmap.de) | none | alternates + per-leg OSM attributes incl. surface/unpaved — real safety signal | ~300ms | candidate: UNVERIFIED demo uptime |
| GraphHopper | free tier ~500 req/day | routing w/ alternatives + road-class details | ~300ms | backup router |
| OpenTopoData | none | elevation (delhi flat — skip) | — | skip |
| DTC/DMRC GTFS-RT | UNVERIFIED — Delhi has GTFS static feeds; real-time vehicle positions not publicly confirmed | bus positions | — | UNVERIFIED |
| TomTom/HERE traffic | paid (tiny free tiers) | **no free real-time Delhi traffic feed exists — honest gap** | — | skip: use our own corridor density as the live traffic proxy |

**No free Delhi live-traffic feed.** Honest replacement already shipped:
`top_corridors` — donated traversal density is our own traffic proxy,
and it grows with every user. That is the honest "real-time traffic" story.

## B. Decision engine — what fits

Evaluated: GoRules JDM (Rust, hosted rules — real product but adds a
service + latency), json-rules-engine (JS lib — client-side only),
Drools (JVM, absurd for this), on-device llama.cpp narration (nice-to-have,
not core), **weighted-utility scorer in the service** (what we shipped).

**Shipped: `/decide`** — score = `0.5·dose + 0.3·risk + 0.2·time`
(normalized), safety-first ordering, plain-English reasons per option.
Runs in the same request as compare — zero added latency, fully
inspectable in the writeup. Mode risk tiers anchored to MoRTH "Road
Accidents in India" fatality shares (two-wheelers + pedestrians dominate)
— class-level honest, not fake street-level precision.

```python
score = 100 - (0.5*norm(dose) + 0.3*norm(MODE_RISK[vehicle]) + 0.2*norm(duration))
# reasons: "breathes least" | "safest mode class" | "fastest" | "avoids N µg vs worst"
```

**Next real term, when the data.gov.in key lands:** black-spot proximity
— distance from route polyline to the 115 Delhi MoRTH black spots; a
route threading ≥2 black spots within ~300m gets a safety flag. Data is
real and free; only the key is missing.

## What we deliberately did NOT do

- C++ server rewrite — rewrite risk > all gains; uvicorn already serves
  the full compare pipeline in <1s; hackathon time goes to features.
- Any fabricated accident/black-spot coordinates — the 115 real ones
  come from MoRTH or not at all.
- "AI decision model" branding — a transparent scorer a judge can
  audit beats a magic box nobody can.
