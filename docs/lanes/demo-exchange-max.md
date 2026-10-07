# Demo exchange — hostile audit (max lane)

Audit of live prod `http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com`
on 2026-10-07, ~05:40–06:15 UTC (~11:10–11:55 IST). Judge-style drive: every
surface clicked in the mobile viewport (390×844), every mapped number
cross-checked against its wire, contract.ts diffed against the served shape.
No fixes — flags only.

**Prod build at audit time: `dc6d0cc2`** — all four served pages are
byte-identical to HEAD `dc6d0cc`. Verified by diffing `curl`'d pages against
`git show` at each revision.

---

## Surface-by-surface verdicts

### `/` landing (v5) — **REAL**
Every number in the editorial flow populated from live wires during the drive:

- Hero `57.4 µg/m³ · SATISFACTORY` → matches `/v2/city` mean 57.4 and band
  `satisfactory` at that moment. Cigarette line "≈ 2.6 cigarettes" is the same
  22 µg/m³-day basis used elsewhere.
- Statusline "53 STATIONS LIVE · FIELD 5 MIN FRESH · MEDIAN 57 · WIND 7 KM/H ·
  903K EDGES PRICED" → all five values verified against `/health`,
  `/grid` (client-computed median of 1,156 cells = 57.0), `/v2/city`.
- Mechanism step 2's "95.2% of 3,550 held-out station-hours inside ±2σ" →
  matches `server/data/field_validation.md` (measured 95.2 vs nominal 95.4,
  n=3550) — and the linked file publishes the *tie* on MAE, not a cherry-pick.
- The earned A→B surface (`#routeline`, `#departline`, `#ladder`) renders only
  after real map clicks and fires real `POST /v2/plan` (24 options, ~3.5s) +
  `/depart`. Served "Car (AC) 15.7 µg · 7.4–24.0 · 34.8 km · ~47 min" and
  "leave ~11:00 — 1% less dose" — both real.
- Prefills fixed: markup now ships `—` and "reading the field…", no plausible
  fake numbers in the HTML skeleton (earlier P2 closed).
- Felt language audit: "a ledger for your lungs", "the air is barely moving" —
  every felt claim traces to a wire field (`/v2/why` line, band idx through the
  same `feltKeyForBand` source). No oversell found.

### `/city` — **REAL**
- "the ledger" renders today's recorded hours from `/v2/archive`;
  wire coverage `[1,3,4,5,6,7,8,9,10,11]` + gaps `{0,2}` matches the rendered
  "10 recorded · 2 gaps · missing 00:00·02:00" (12 arrived at noon between the
  render and the fetch — live drift, consistent).
- Breath/dose totals match `/community` wire (`146` breaths est., `4 µg`
  inhaled, `117.8` avoided today — all derived from the same totals).
- Outlook at the page's own bias point `/v2/outlook?lat=28.63&lon=77.22`
  serves `92.7 (77.8–107.6)` — the rendered `93 / 78–108` is exact.
- Corridors table "SHOWING 10 OF 12" with title-cased street names (earlier
  truncation + casing P2s closed).

### `/community` — **REAL**
- `41 trips · 23 contributors · 2 today · 12.0 km · 4.2 µg inhaled · 117.8
  avoided today · 1,083.8 all-time` — matches the wire to the decimal.
- Every top-corridor row shows devices ≥3 (k-anonymity holds on the wire, not
  just in copy).
- "last shared 1.8h ago" is a real timestamp; "no flags right now" is an honest
  empty (`/reports` = empty FeatureCollection; rider flags have 6h TTL).
- Unfurl: `Accept: */*` + generic UA → JSON (app contract preserved);
  slackbot/twitterbot/whatsapp/discordbot/etc. → HTML with og:/twitter: meta.
  The earlier "paste a link, get raw JSON" P2 is closed.

### `/admin` guest view — **REAL + honestly gated**
- Hero card "57.4 µg/m³ · SATISFACTORY · mean across 25 sampled cells · median
  56.4 · worst 72.1 · aqi 96 · 41% below typical Oct · wind 6.9 km/h @150°" —
  every clause verified against `/v2/city` + `/health` wind.
- "9 LOCKED — sign in as operator" — count is exact: 8 `/admin/api/*` +
  `/v2/usage`. Guest page pre-rejects gated fetches (`isGatedPath`) — **zero
  authed network calls fire for a guest**; the usage card renders its locked
  state client-side.
- Corridor table "AIR NOW" column is all dashes: `field_pm25` rides the gated
  feed, public `/v2/city` rows emit null → `—`. Honest but reads broken (see
  attacks).
- LOO calibration now reads `mae 8.8 · rmse 12.7 · n 70` — the stale-46.1
  deploy lag is closed. `41% below typical Oct (≈97.7)` disclosed as the
  climatology reference. "below stage I — computed here, CAQM declares the
  official one" carries the right qualifier.
- Archive strip matches `/v2/archive`; "forecast grades itself" table matches
  `/v2/skill` (262 graded pairs, mae 27.1, bias +21.2, band 48.3%).

### `/v2/plan` (POST, CP→IGI drive) — **REAL**
24 options, ~3.5s. `ranking` policy block present; `duration_basis:"freeflow"`
on engine rows; `took_ms` real; field provenance echoed. `segments[]` on every
option including the GTFS bus leg.

### `/v2/reroute` (POST) — **REAL**
23 options, `segments` parity on the flattened selected option, fresh
`route_id`, honest error bodies on bad input.

### `/aqi` + segment spot-check — **REAL**
All 12 painted spans of the walk option's gradient land within ±5% of `/aqi`
at each span midpoint (seg/aqi ratios 0.96–1.10 — consistent with the ×1.06
smoke modifier). The gradient honestly reflects the field.
(`demo-exchange-max-shots/seg_midpoints.txt`)

### `/v2/usage` guest — **401, correct**
`{"detail":"admin token required"}` — same gate as `/admin/api/*`. Code audit
(`server/admin_agg.py:786-1014`): aggregate scalars only, `installs: null`
with "unknowable server-side", `devices_basis` disclosure, no dimensional cuts,
k_min 3 enforced on any group breakouts.

### Notify banners (mobile, code-level) — **HONEST**
`Mobile/src/notify.ts` + `store/events.ts`: 14 event kinds all raise off real
`/v2/why` evaluated drivers (fires belt count + carrying flag, band crossings,
GRAP stage moves, trend, outlook). Felt words go through `feltKeyForBand`
single-source; fires has a real `fires_nc` variant for "wind not carrying";
GRAP pings say "our read, not the official call". Immediate delivery is
deliberate — "air just turned poor at 7am isn't 'just'".

### Mobile contract — **MATCHES, no drift**
`V2PlanSegment {geometry, pm25, band, start_frac, end_frac, dist_m}` in
`Bridge/contract.ts:434-457` == served wire exactly. All option keys served
(`safest_path`, `your_vehicle`, `eta_model`, `router_backend`, `freeflow_s`,
`tag`, `reason_line`…) are declared. `routeTint.ts` consumes segments-first,
band-name wins, CPCB ramp only, MAP_QUIET for nulls — renderer and contract in
sync.

---

## Numbers-match table

| Number | Appears on | Live value | Consistent? |
|---|---|---|---|
| Stations live | landing statusline, admin "instruments" | `/health` `sources.stations.count`=53 | ✅ |
| Field mean | landing hero 57.4, admin hero 57.4 | `/v2/city` pm25 mean 57.2–57.5 (drifting) | ✅ |
| "Median" | landing "MEDIAN 57", admin/"city" "median 56.4" | grid median (1,156 cells) 57.0; lattice median (25 pts) 56.4 | ⚠️ two populations — see attacks |
| Max/worst | admin "worst 72.1" | `/v2/city` max 71.7–72.1 | ✅ (drift) |
| Indian AQI | admin "aqi 96" | `/v2/city` aqi 96 | ✅ |
| Edges priced | landing "903K" | `/health` edges_priced 903,058 | ✅ |
| Edges total | — (not surfaced) | 1,070,459 | — |
| Model samples | — | 99→101 live | live drift |
| Field age | admin "rebuilt 5–6m ago", "every ~15m" | `field_age_s` 89–717, refresh_in 183–811 (TTL ~900s) | ✅ |
| Wind | landing "7 km/h", admin "6.9 km/h @150°" | `/health` 6.5–7.3 @147–152° | ✅ |
| Fires | admin "44 · 12 belt · 31 day/13 night · viirs" | `/fires` 44 feats, all VIIRS (NOAA-21×29, NPP×9, NOAA-20×6), D31/N13, belt 12 | ✅ exact |
| Smoke modifier | `/aqi` ambient×1.06 | `/v2/why` fires.modifier 1.06 | ✅ |
| Community totals | community page, city chips | `/community` 41/23/12.0/4.2/117.8/1083.8 | ✅ to the decimal |
| Corridors | city "10 of 12", moves | `/v2/city/moves` publishable 12 / tracked 55, min_k 3 | ✅ |
| Skill | admin "grade itself" table | `/v2/skill` 262 pairs · mae 27.1 · bias +21.2 · 48.3% · 36h | ✅ |
| LOO calib | admin | mae_ug 8.8 · rmse 12.7 · n 70 (rebuilt) | ✅ stale-46.1 closed |
| Archive | admin hourly strip | `/v2/archive` recorded [1,3–12], gaps {0,2} | ✅ (12th saved at noon) |
| GRAP | admin "below stage I", city "below stage i" | stage 0 computed, aqi 96, qualifier present | ✅ |
| 95.2% kriging | landing mechanism | field_validation.md: 95.2 measured vs 95.4 nominal, n=3550 | ✅ |
| Depart saving | landing earned surface | `/depart` today: ~1% | ⚠️ honest but unimpressive — see attacks |
| build | admin header | `/health` build_sha dc6d0cc2, served pages == HEAD | ✅ |

**Drift observed live during the audit** (real donations/measurements, not
bugs): obs_total 40→41, contributors 22→23, obs_today 1→2, wind 6.9→7.3,
samples 100→101, trend +5.1→+4.9/34 snapshots.

---

## The 3 worst things a judge can still attack

### 1. The citizen layer is still thin — and the admin gate hides the best defense
41 donated trips / 23 phones all-time, **2 today**, 12 km. A judge asks "who is
actually using this?" and the honest answer is "almost nobody yet". The k≥3
suppression rule is real (verified on the wire), but it means the corridor
evidence table looks sparse (12 publishable of 55 tracked). Worse: `/v2/usage` —
the one surface that would prove adoption honestly — returns 401 to every
guest judge. The usage tab *says* "aggregate counts only, never a person",
but nobody outside the org can verify a single number in it live.

### 2. `depart` saves ~1% today — the pitch promises more
The earned landing surface (the flagship "leave at a cleaner hour" proof)
currently renders "leave ~11:00 — **1% less dose**" on the demo OD. Honest —
but a judge screenshotting the marquee interaction sees a 1% saving on the
product's core promise, 5 hours out. On a good-ventilation day the whole
leave-later narrative visibly underdelivers; the pitch script needs a better
day or a better caveat.

### 3. Mid-demo deploys mean a judge *can* catch a real inconsistency
During this audit, `/v2/usage` went 404→401 and `build_sha` flipped
aea1c688→dc6d0cc2 within ~15 minutes. Both self-healed, but for a window a
guest could load admin.html@HEAD against an old-task API and see "usage feed
unavailable", or screenshot `/health` build ≠ served page. Rolling-deploy
skew is normal — but on a 10-minute judge pass it reads exactly like the
"numbers don't match their siblings" failure this audit was hunting.

## Watch-level flags (not headline attacks)

- **`/health` carries two "stations" numbers in one payload**:
  `sources.stations.count=53` (live instruments — what the landing claims)
  vs `history.stations=125` (climatology archive). A judge curling /health to
  "prove the 53" will see `"stations":125` first. Naming ambiguity, P3.
- **Admin corridor "AIR NOW" all dashes for guests** — honest nulls rendered
  as `—`, but a column of `—` reads broken next to "every number is measured
  live". Defensible, costs a sentence of explanation.
- **Two medians**: landing "MEDIAN 57" (1,156 grid cells) vs admin/city
  "median 56.4" (25-point lattice). Both real; the difference is population.
  A judge comparing screenshots calls it drift.
- **Serif display type persists** on /city + /community headlines
  (carried P2 — off-system per design law; serif allowed in data register only).
- **Community/city street lists are disjoint** (corridor subset vs cell subset
  by design — carried P2, still true).
- **Plaintext HTTP** — known gap, in judge-answers-v3.
- **Hairline borders**: admin still renders ~29 1px border rules (landing 11,
  city 18, community 10) — the v5 sweep left selection/emptiness marks; admin
  is the densest residue. Design-law nit, not a realness failure.
- All `<11px` font violations are gone on all four surfaces (0 rules; was
  30–51 each). ✅

## Verified-fixed earlier P2s

og:/twitter: meta on all four surfaces · markup prefills honest (`—`/reading)
· landing explains both cadences in one sentence (DPCC ~5min pages, field
rebuild ~15min) · corridor names title-cased · contrib window = all-time +
since-date · admin 390px overflow gone · LOO 8.8 on prod (stale 46.1 closed)
· unfurl UA list comprehensive.

## Evidence

`demo-exchange-max-shots/` — mobile-viewport screenshots (hero, mechanism,
A→B earned surface, city ledger, community, admin guest + archive/skill) and
wire dumps: `health-wire.json`, `community-wire.json`, `moves-wire.json`,
`skill-wire.json`, `aqi-wire.json`, `plan_excerpt.json` (24-option scalar
summary), `seg_midpoints.txt` (segment-vs-/aqi spot-check table),
`usage-guest-401-body.json`.
