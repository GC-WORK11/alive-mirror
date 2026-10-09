# admin v3 — live-prod audit + fix pass

**lane:** admin → analytics, second pass. **base:** `base/v2` HEAD `c5bb130` (pulled `--rebase` mid-work — sibling landed v16 landing). **push:** `5c3d1aa`, direct push, no PR. **deploy:** sibling-owned — this lane did not run `deploy.sh`; prod `90bc055d` serves the pre-fix build until then.

**method:** prod `http://65.2.28.40` audited GET-only over the admin mount (SM token → `/in/` → cookie jar; token never printed). every section walked at 1440px + 390px in Chrome, and every number traced to the API that serves it. local re-verify on `uvicorn :8108` after fixes.

## audit table — what each block serves, where it reads from, verdict

### 01 live air

| block | serves | source | verdict |
|---|---|---|---|
| pm2.5 numeral + band + how stale | live aqi, band word, feed age | `api/status.field` (pm, band, age_s) | ok |
| "the live blend right now" | per-feed station states (waqi/dpcc/cpcb/openaq ✓/✗) | `status.field.stations_status` — **absent on the native engine**; lives on `/v2/city`'s embedded field | **fixed** — page now merges `city.field` under `status.field`; prod was showing "the feed reports nothing" while 52 stations were live |
| stations reporting | live station count | `field.stations` | **fixed** by same merge (was blank) |
| serving / wind / vs a typical day | field serving mode, wind, seasonal median delta | `status.field` + `api` | ok |
| next 12 hours sparkline | forecast curve | `city.forecast` | ok |

### 02 coverage

| block | serves | source | verdict |
|---|---|---|---|
| stations into the blend | count + feed list | `field.stations`, merged | ok after merge |
| between the stations | kriging mode | `field.kriging` | **fixed** — was raw `kriging: ordinary`; now "smoothed by the full spatial model" / "simple distance-averaging" with a plain-words sub |
| how sure each cell is | sigma coverage | `field.sigma_coverage` | **fixed** — was "sigma: per-query"; now "every query gets an honest certainty band" (partial/none also plain) |
| the served field | cell count + bounds | `field.cells`, `field.bounds` | ok |
| the archive | snapshots, today's hours, gaps | `status.archive` | ok — "79 snapshots · today 8 of 9 hours on disk · missing 6 hours" |
| the route engine | priced edge share | `status.routing` | **fixed** — "edges priced" → "9,03,058 of 10,70,459 streets priced" |

### 03 usage

| block | serves | source | verdict |
|---|---|---|---|
| requests served | total + status split + in-flight | `admin_agg /api/timing.requests`, `gauges.alive_requests_in_flight` | **fixed** — sub now says "4 in flight right now · /health alone is 1,890 — uptime monitors pinging, real but not people" (prod: /health = 76% of all traffic) |
| route leaderboard | top routes × hits × mean latency | `timing.routes` | **fixed** — each row carries "≈76 ms each"; raw paths kept (they're urls, not jargon) |
| journeys sparkline | trips/hour, last 24 | `usage.trips.per_hour` | **fixed** — was `api.journeys_per_hour` (UTC-day buckets → all-zero at day's start); now the rolling 24h window |
| devices seen | all-time / 24h / 7d device counts | `usage.devices` | ok — copy already says "devices that shared; true installs unknowable" |
| the last 24 hours | trips/km/dose/phones in rolling window | `usage.trips.last_24h` | **fixed** — was a `today` row that read "—" because prod `today:null`; now rolls with the window (4 journeys · 5.3 km · 5.3 µg · 4 phones on prod) |
| NEW: contributors by day | last 5 days: trips + phones each | `api.contributors` | **added** — the closest honest answer to "who's using it" (Oct 7: 6 journeys · 4 phones) |
| NEW: where phones actually went | top corridors by samples | `api.community.top_corridors` | **added** — "Outer Circle · Tolstoy Marg · Radial Road 4" with samples + phones |
| privacy note | suppressed day-slices | `api.contributors_suppressed` | ok — "1 day-slice withheld under the 3-phone rule" |

### 04 health

| block | serves | source | verdict |
|---|---|---|---|
| alarm verdict | named conditions, counted | `field.alarms/stale`, per-feed states, disk, ledger | **fixed** — verdict and feed rows now share one computed word each; a feed reading `down` names itself in the alarm line even when the engine didn't raise one |
| feed rows | per-source state + what it is | `api/sources` + `/health.sources` | **fixed** — `routing` reported `up:true` **and** `stale:true`; verdict order now puts stale first (was printing "up" in brick). stations/fires rows carry `/health` counts ("52 monitors — waqi ✓ · dpcc ✓", "N fires · N in the belt") since the native detail string is a config note |
| secrets blob | — | `stations.detail` literally contains `— secrets alive108/{...} (WAQI_API_KEY… set)` | **fixed** — `clean()` strips the `— secrets …` tail and env-var parentheticals from every detail string |
| trailing "· —" | — | feeds with no `age_s` printed a bare dot-dash | **fixed** — age fragment is conditional |
| errors since boot | 4xx/5xx counts + per-route rows | `timing.requests.by_status`, `timing.errors` | **fixed** — plain words: "turned away 21 · server errors 0", `unmatched` → "paths that don't exist (scanners, mostly)", `/in/{secret}` → "wrong sign-in links" |
| disk / ledger / build | free %, device tokens, sha | `status.disk/ledger/build` | ok — "84.5% free", "dynamodb · 31 device tokens", "90bc055d" |

## what "who's using it" honestly is on this box

no user accounts exist — the truest served signals, all now on the page: **devices seen** (ledger-tracked tokens: 31), **contributors by day** (4 phones shared Oct 7), **journeys last 24h** (4), **active right now** (donations in 30 min), **top corridors** (where those phones went). requests-from-uptime-monitors is called out as "real but not people" so request totals don't masquerade as humans.

## verify

- `python3 scripts/check_inline_scripts.py` — clean (4 blocks).
- local `:8108` signed-in render @1440 + @390 — all four sections, new blocks, no NaN/`undefined`.
- prod audit shots → `admin-v3-shots/prod-*.png`; post-fix local renders → `local-v3-*.png`.
- deploy is the sibling's lane: prod still runs `90bc055d` until their push lands.

## known honest limits (unchanged by design)

- counters reset on deploy — the page says so under "usage".
- `today` is UTC-day on prod's `usage`/`api` payloads; the page prefers rolling 24h everywhere so a quiet morning never reads as "nobody".
- installs are unknowable; the page never says "users".
