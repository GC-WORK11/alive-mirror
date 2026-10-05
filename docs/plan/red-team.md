# Red-team report — ALive-108 (lane: red-team, 2026-10-05/06 UTC)

Adversarial pass over the live deployment
(`alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com`, build `033aa866`,
engine `alive_core`, 1vCPU/3GB Fargate Spot, single worker).
~280 live probes across every endpoint + a full privacy code audit.
Rules honored: GETs + POST /v2/plan + POST /v2/reroute only — **zero
writes to live** (no /v2/trip, /observe, /v2/feedback POSTs, no deploys).
Evidence JSONL: `~/redteam/evidence/*.jsonl` on the macOS box.

## Verdict

The build is hard to embarrass. 229 edge probes → **zero stack traces,
zero 500s, zero leaked internals**. Every bad input returns a typed 422,
an honest empty answer, or a labeled degraded result. Two real breaks
found — both fixed in this commit. The posture survives a skeptical
judge with curl.

## Findings — fixed in this commit

| # | Sev | Endpoint | Break | Evidence | Fix |
|---|-----|----------|-------|----------|-----|
| F1 | **HIGH** | `GET /directions` | Fabricated a route for out-of-NCR ODs — `/route` guards with `in_service_area`, `/directions` didn't, so OSRM snapped Mumbai→CP ~1,100 km onto the Delhi graph and served a real-looking route + steps for a trip it never planned | `?from_lat=19.07&from_lon=72.87&to_lat=28.61&to_lon=77.21` → 200, geometry starts at 76.82,28.18 (Delhi), `"steps": 6` | added the same `in_service_area` guard as `/route` → `{"steps": [], "error": OUT_OF_AREA}` (main.py) |
| F2 | **MED** | `GET /escape` | `limit` had `le=10` but no floor — `limit=-5` made `cand[:-5]` return ~185 cells each getting a sequential Photon reverse-geocode call → 19.5 s request on a single-worker task (and silently skipped the 5 best cells) | `?limit=-5` → 200 in 19.5s vs ~800ms at limit=5 | `limit: Query(ge=0, le=10)` — negative → 422 |

## Findings — documented, not fixed (small blast radius)

| # | Sev | Surface | What a judge sees | Why it's documented not patched |
|---|-----|---------|-------------------|----------------------------------|
| D1 | low | `/v2/plan` `depart_at` | Garbage `depart_at` ("abc", [1,2], 1e20) → transit arm silently plans for *now*; far-future valid ISO → transit rows honestly absent. The top-level `depart_at` echoes the garbage input verbatim | The transit option rows carry their own real `depart_at`/`arrive_at` timestamps — nothing fabricates; the waste is one echo field. A `depart_at_resolved` note would be tidier but touching plan.py's response shape late isn't worth it |
| D2 | low | gazetteer | `gaz:870` "Gateway of India, bombay, mumbai" sits at 28.506,77.243 (Delhi); `/v2/reverse` near CP can name "presidencies and provinces in British India" | Community OSM data quirks — responses honestly say `source: gazetteer`. Fallback line: "the gazetteer is OSM community data — quirks ride along; routing math never reads the names" |
| D3 | low | `/v2/feedback` | Per-IP rate limit keys `request.client.host` — behind the ALB that's the balancer's address, so the 6/hr cap is effectively global not per-user | Weaker than intended, not dishonest; review notes still coord-redacted + k≥3-gated before publish |
| D4 | note | `/v2/reroute` `route_id` | A made-up route_id gets a fresh plan rather than an error — `rerouted_from` echoes it back | Stateless replan by design; the echo shows exactly what was ignored |
| D5 | note | `/metrics` | Public, shows per-route request/error counters (a judge can see red-team probes' own 4xx counts) | Aggregate-only, no user data; honest enough to leave on |
| D6 | note | `/v2/reach` Mumbai | Returns 200 with `edge_count:0, nodes:0` instead of the `outside_service_area` code `/v2/plan` uses | Empty is honest; inconsistency between the two v2 contracts is cosmetic |

## Honesty audit — claims vs the wire

Verified live 2026-10-06 ~01:40 IST:

| Claim (demo-script/judges-faq) | Live check | Result |
|---|---|---|
| 24 WAQI + ~71 CAMS samples | `/aqi` stations:24 ✓; `/health` field block | holds |
| 1,070,459 edges / 903,058 priced | `/v2/city` | exact match |
| engine `alive_core`, local OSRM | `/health` + option `router_backend` | holds |
| "33–35×" walk/car spread | CP→GGN plan: walk 400.6 / car 11.4 = **35.1×** | holds — drifts with field (was 29.3× earlier) |
| k≥3 corridor gate | `/v2/city/moves` min_k:3; 10/54 corridors publishable; suppressed counters on wire | holds |
| transit compiled metro+bus | `/health` `real_feeds {metro:true,bus:true}` | holds |
| breath ≈ 2.33 cig/day | `/v2/city` breath.mid = **2.98**, hi 7.08, 940 µg/day | **drifted** — say "~3 cigarettes", or just read the tile live |
| depart "110 slots" | `/depart` currently serves ~100 (honest gaps skipped) | **drifted** — say "~100 honest slots out of 120" |
| skill MAE 26.2 | `/v2/skill` is **thin right now** — 11 pairs, all horizons "thin" | **risk** — see fallback |
| 95.2% coverage @±2σ, 3,550 station-hours | `/admin/api/validation` live LOSO: **79.2%**, MAE 11.31, n=24 | different metrics — needs the spoken reconciliation |
| "only k≥3 aggregates leave the phone" | code audit + DDB schema — holds | holds |

### The 95.2% vs 79.2% reconciliation (say it before they ask)

- **95.2%** = band coverage over **3,550 held-out station-hours × 85
  stations** — the temporal validation run that calibrated σ (source:
  `server/data/field_validation.md`). Offline, reproducible, the number
  the FAQ quotes.
- **79.2%** = the admin tile's **live leave-one-station-out spatial
  check** on *this week's* field, n=24 stations — recomputed weekly,
  deliberately a harder question (predict a station it never saw).
- One line kills the mismatch: *"95% is the temporal coverage the σ was
  fitted on; 79% is the live spatial holdout — a harder test we publish
  anyway."*

### `/v2/skill` fallback

Self-graded skill only publishes a MAE per horizon once ≥5 pairs exist;
recording started ~1 day ago so it's honestly `thin`. If asked:
*"the self-graded MAE needs five recorded-vs-forecast pairs per horizon —
it's day one of recording; the 26.2 figure comes from the held-out
replay, reproducible offline."*

## Races & timing

- 10 concurrent `/v2/plan` on one worker: 9×200 (7–10.7 s), 1×429 — the
  per-client token bucket (2 r/s, burst 6) fires honestly with
  `retry_after_s`; no corruption, no mixed-state responses.
- Mixed endpoint fan-out (plan+city+grid+why+day+reach+aqi) → all 200,
  ≤1.8 s each.
- Engine arm under load degrades by name (`degraded:["engine"]`,
  options return dose-less rather than fabricated) — verified.
- Hour-boundary archive: `recorded/pending/gap/unreadable` states are
  honest; partial snapshots labeled, never treated authoritative.

## Privacy audit (code + rest state)

- `/v2/trip` handler: 300 m edge-trim + 100 m thin + 4-dp round + H3
  res-8 fold *at ingest*; `_BOUNDS` sanity caps; `sha256[:16]` token;
  per-day dedupe. Only aggregates land in DynamoDB
  (`cell#/day#/hour#` items, k≥3 string-sets of hashed tokens, 30-day
  cell TTL). **No per-trip row at rest — verified `server/v2/trip.py`,
  `store.py`, `agg_ddb.py`.**
- Logs: uvicorn `--no-access-log`; observability allowlist-only fields
  (no body/query/token/lat/lon); `scrub_log_line` truncates >2-dp
  decimals + redacts secret patterns.
- Mobile consent: donation fires only when `shareEnabled` (default
  false) and traj>1 point (nav/engine.ts:321); consent-off → `/v2/trip`
  never called; outbox flush only holds prior donations. `/v2/plan`
  carries no device token — just OD coords + vehicle.
- Judge's donated trip linkability: server sees hashed token + rounded
  cells + summary; k≥3-device gate before any publish. A judge CANNOT
  be re-identified from what's stored. Holds.
- `/v2/feedback`: stars validated, note ≤240 chars + coordinate-pattern
  redaction before persist, notes publish only past k≥3.

## The 3 scariest things left

1. **Single-worker cold path on stage.** Fresh OD during a cold 15-min
   repricing window can hit the 20 s plan budget → `options:[] +
   "planner timed out"` (seen live: KG→Faridabad cold). Survivable:
   retry answers warm in ~6 s, the error is typed and honest, and the
   script already rehearses "retry once — that's the budget being
   honest." Run `verify_numbers.sh` at T-45 as scripted.
2. **`/v2/skill` thin on demo day.** Archive recording started
   2026-10-05; horizons stay `thin` until 5 pairs each. If a judge hits
   it live they see honest thinness, not the 26.2 claim. Survivable:
   the thin state IS the honesty demo — "it refuses to quote a number
   until it has enough of its own receipts."
3. **Drifting demo numbers.** breath 2.98 not 2.33; slots 100 not 110;
   spread swings 29–35×; option count 16–20 as transit rows come and
   go. Survivable: script already says "quote ranges"; every number is
   a live fetch so saying "about three cigarettes" keeps it true.

## What I did not do

- No writes to live (`/v2/trip`, `/observe`, `/v2/feedback` unprobed as
  POSTs — audited in code instead).
- No deploys — fixes ride the next image build.
- No admin-API writes; admin GETs only.

## Fix commits this push

- `server/main.py` — `/directions`: `in_service_area` both-endpoints
  guard mirroring `/route` (F1).
- `server/main.py` — `/escape`: `limit` `ge=0` (F2).
