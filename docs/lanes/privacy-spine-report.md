# privacy-spine lane report — does the admin board ever show a person?

Date: 2026-10-07 · Branch: `base/v2` (HEAD `0c13dd9`) · Scope: every
field served to the operator board — `/v2/usage`, `/admin/api`,
`/admin/api/*`, the `/admin` page source — plus the public surfaces that
carry the same data (`/v2/city`, `/reports`, `/v2/ledger`).

**Verify, not fix.** No code changed. Live evidence from prod build
`c86074ff` (matches `/admin/api/status` build_sha), dumps taken
~13:19 UTC (~18:49 IST) via the documented flow in
`docs/plan/admin-login.md` (POST `/v2/admin/login` → `alive_admin`
cookie; `alive108/admin-token` from SM).

---

## 1. The pipeline — where a person could leak

`POST /v2/trip` (`server/v2/trip.py`) is the only way usage data enters:

1. trajectory → drop first+last **300 m**, thin to ~100 m, round 4 dp
   (≈11 m) → **H3 res-8 cell keys** (`privacy_pipeline`, trip.py:185-209).
   The raw list never touches a store or a log — `cells` are computed,
   `traj` dies.
2. `device_token` → `sha256[:16]` **before** it can reach any store
   (trip.py:241; same treatment for community `contributor`,
   community.py:123-129).
3. `record_trip` only accepts cells + scalar summary + hash
   (`v2/store.py:129`). Stores hold: day counters, per-cell
   {count, dose_sum, **token set**}, per-hour {sums, **device set**},
   per-area/OD {sums, device set}. No point, no ordered chain (cells are
   a set — trip order dies at ingest, store.py:177-178/community.py:572-573).
4. Device ledger (`v2/store.py:429`) keeps per-device sanitized summaries
   (km/dose/co2/mode/ts — **no coords, no cells**) readable only via
   `GET /v2/ledger` with the raw token — verified live: no token → 422,
   random token → 200 with empty ledger. `devices_tracked` scalar only.

So the privacy promise is *structural*: a person-identifying row cannot
be served because none exists at rest. What remains to audit is whether
any **aggregate** is thin enough to collapse back to one person.

## 2. Wire audit — every field on the gated surface

Auth verified first: `/v2/usage` and `/admin/api` → **401** anonymous,
200 with cookie, 200 with `Authorization: Bearer`, 401 with a wrong
Bearer. Cookie `alive_admin=v1.<exp>.<sig>` — HttpOnly, SameSite=Strict,
Max-Age=28800. Guest `GET /admin` returns the 167 KB static shell: gate
card only, **zero embedded data** (no JSON blob, no coords; "token"
appears only in JS comments/labels). View-source is safe for judges.

A recursive scan of every dumped response for identifier-shaped keys
(`token|device|contributor|install|user|uuid|hash|email|_id` at any
depth) and hex-id values:

- **Zero identity fields on any wire.** Every `devices`/`contributors`
  key is an integer count. The only hex strings are H3 cell indexes
  (`883da11409fffff`, res-8 ≈ 531 m edge — the documented public
  aggregate unit) and `routing.graph_sha` (the OSM PBF checksum).
- The only lat/lon pairs served belong to **government monitoring
  stations** (`field.stations[]`, CPCB/WAQI public locations) and
  ~500 m corridor cell centres — never a user.

Per-endpoint field inventory (live values in `~/privacy-spine/*.json`):

| Endpoint | Fields | Basis |
|---|---|---|
| `/v2/usage` | `devices{total,seen_24h,seen_7d}`, `installs:null`, `trips{total,km,dose_ug,co2_kg_mid,switched,days_tracked,today,last_24h,per_hour[24],latest_donation_age_min}`, `dose{mean,median,median_n,daily[]}`, `corridors{tracked,publishable}`, `feedback{reviews,hazard_reports}` | all scalars/counts; `per_hour`/`daily` are bare counts and day means |
| `/admin/api` | `field.stations[]` (govt), `fire`, `community.totals`, `corridors[10]`, `contributors[day-rows]`, `recent_journeys[]`, `reports[]`, `journeys_per_hour[24]`, `reviews` | day/hour rows are aggregates; see §3–4 |
| `/admin/api/corridors` | `cell`(H3), `near`(gazetteer name), `trips`, `devices`, `avg_dose_ug`, `co2_*`, `field_pm25` | k≥3 re-asserted → 500 on violation |
| `/admin/api/donations` | `totals`, `mode_share`, `recent[]`, `days{}`, `distinct_devices:null` | day counters; `recent` is hour-buckets k≥3 |
| `/admin/api/global` | `areas[]`, `od_pairs[]`, `suppressed{}`, `dose_avoided`, `co2_avoided`, `reviews` | district names, never coords; k≥3 |
| `/admin/api/status|sources|timing|model|validation` | ops/model/provenance | nothing personal — engine, feeds, latency histograms, model constants, validation scores |

## 3. k≥3 — the boundary, live-verified

The gate is **in the stores under lock**, with the API re-asserting it
(fail-loud 500, not silent publish). Live prod evidence that it fires:

| Surface | Evidence |
|---|---|
| Corridors (admin + public `/v2/city`) | `cells_tracked:55` → `publishable:12` — **43 cells suppressed**. Every served row `devices≥3`; three rows sit exactly at k=3 (Fire Brigade Lane, Howrah–Delhi Railway, Tyagraj Marg). |
| `recent_journeys` / `recent[]` | **Empty on live data** — today's 5 trips from 3 devices spread across 4 UTC hours; every hour bucket holds <3 devices → all suppressed. If the gate were absent or broken, 4 rows would exist. |
| `/admin/api/global` | `od_pairs_tracked:2`, served 1, **`suppressed.od_pairs:1`** — a sub-k OD pair counted, never shown. Areas: 1 tracked, 1 shown (9 devices). |
| Reviews | `count:1` → `notes:[]` + **`notes_withheld:true`** — note bodies suppressed below 3 reviews (one lonely review is identifiable by timing alone). |
| Corridor field samples | `corridor_field_samples` requires ≥3 fresh traversals AND ≥3 distinct devices before a cell's implied PM2.5 exists (community.py:826-831). |
| Tripwire | `test_corridors_k_floor_tripwire` + `test_global_k_floor_tripwire` force a k<3 row past the store → endpoint 500s instead of publishing. |

k is counted in **distinct hashed devices**, not trips — three donations
from one phone is k=1 (`test_recent_obs_counts_devices_not_trips`).

## 4. Findings — what could still identify someone

### F1 — `contributors[]` day-rows carry a `contributors` count but no k-gate *(moderate, currently latent)*

`/admin/api` → `community.contributors_detail()` (community.py:610-631)
emits one row per UTC day: `{day, trips, km, dose_ug, avoided_ug,
contributors, last_seen_min_ago, modes}`. **Unlike its sibling
`recent_obs` — which suppresses buckets under `_K_MIN_DEVICES` with a
comment naming exactly this leak ("a trips:1 or trips:2 bucket still
collapses to someone's exact hour/mode/duration/km/dose") — the day
rows have no suppression.** A sparse day with 1-2 donors would emit a
*labelled* single-person day-slice: everything one device did that day,
plus its last donation to the minute.

Live data currently has every row ≥3 (3, 3, 7, 4 contributors over the
4 recorded days), so nothing identifying is being served *now*. The gap
is structural, not hypothetical: Oct 6 has no row at all (zero
donations), and demo traffic is bursty — a quiet UTC day with a lone
donor makes this live. No test covers a sub-k day row
(`test_contributors_detail_is_day_rollup_not_devices` asserts shape at
k=3 only). **Fix for a follow-up lane**: suppress rows with
`len(v["devices"]) < _K_MIN_DEVICES` and count them, the same shape as
`global_aggregates`' `suppressed` block — one `if`, one counter, one
test.

### F2 — windowed totals degenerate to one person when the device count drops to 1 *(minor)*

`/v2/usage` `last_24h` reports `devices:3` alongside `trips/km/dose` — and
`today`/`dose.daily` emit day counters with `latest_donation_age_min`.
When the unioned count in a window is 1, the block is a single person's
totals (today: 5 trips · 31.4 km · 10.9 µg · modes bus+car · last
donation 383 min ago — if `seen_24h` were 1, that row is one phone).
Disclosed honestly on the wire, but a judge reading raw JSON on a
1-device window gets a day of one person's life. Bare-count vectors
(`per_hour`, `journeys_per_hour`) additionally reveal a lone donation's
existence + UTC hour, attributes-free. Same fix class as F1 if the
contract is read strictly; the counts-only rows are arguably fine (a
count is not a person — `test_usage_k_guard_is_structural` asserts this
deliberately).

### F3 — authored hazard pins are single-user location data by design *(informational)*

`/admin/api.reports` and public `/reports` GeoJSON carry `{kind,
lat(3dp≈110m), lon, age_min}`, 6 h TTL, no contributor id. Each pin is
authored, meant-to-be-public content (the feature is warning strangers),
and 3-dp rounding was deliberately chosen over 5 dp for exactly this
reason (community.py:589-591). Not a leak — worth one sentence if a
judge asks. Currently zero active.

### F4 — `live_users` is mislabeled, not a leak *(cosmetic)*

`sum(1 for c in contributors if c["last_seen_min_ago"] <= 30)` counts
*day-rows* with fresh activity, so it reads 0/1, never real concurrency.
Harmless; judge-facing copy just shouldn't over-read it.

### Checked and clean

- **No timestamps precise enough to re-identify a person**: corridor rows
  carry none; day rows carry `last_seen_min_ago` (minutes, and see F1);
  hour buckets carry `age_min`. `days{}` exposes `last_ts` epoch on
  today's counter — a city-level field, no device attribution.
- **No single-trip anything**: `recent`/`recent_journeys` are hour
  aggregates k≥3; per-trip rows were removed (commit `3ef3677`).
- **Token never on the wire**: hashed at ingest; stores keep only hashes;
  no endpoint emits them (verified by recursive scan + tests
  `test_usage_never_leaks_identity`, `test_no_identity_or_coordinate_fields_anywhere`).
- **Dedupe signature** (`_DEDUPE`, trip.py:47-80) holds
  token-hash+endpoint-cell digests in memory only — never served.
- **Session cookie**: stateless HMAC, HttpOnly+SameSite=Strict — cannot
  be read by JS and never rides cross-site. Logout is cookie-deletion
  only (documented bound: a copied cookie lives ≤8 h — stateless by
  design, rotation is the kill).
- **`/admin` guest view-source**: static shell, gate card, no data — the
  gated fetches simply never fire for a guest.

## 5. "Installs are unknowable" — honesty verified

- Wire: `/v2/usage` → `"installs": null` + `installs_note` ("true
  install count is unknowable server-side by design…"); `/admin/api/
  donations` → `"distinct_devices": null` + `devices_note`.
- UI: `admin.html:2270` renders `installs_note` under an "installs"
  label — the board shows the *reason*, never a number. The devices tile
  reads "phones that ever shared" with the minting note ("a phone mints
  its token at install but the server only learns it when a trip is
  shared… never installs").
- Consistent with the code: no install registry exists anywhere
  (`LEDGER.devices()` counts donation-seen tokens; nothing registers at
  install — app-side install is purely local).

## Verdict

**PASS with one latent gap.** On prod today every gated surface serves
only aggregates — no token, coordinate, per-trip, or per-device field
exists on the wire, and the k≥3 contract is demonstrated firing in four
independent places (cells 43/55 suppressed, hour buckets all dark, 1 OD
pair suppressed, review notes withheld). The "installs unknowable" claim
is rendered as a reason, not a fabricated count.

The single structural finding is **F1**: `contributors_detail()` day
rows ship `contributors:N` ungated — the day-level sibling of the leak
`recent_obs` was specifically hardened against. Nothing identifying is
served at current volumes, but a sparse day flips it live. Recommend a
one-line suppression patch + test before the demo window, not a rewrite.

Evidence dumps: `~/privacy-spine/` (this box) —
`v2_usage.json`, `admin_api*.json`, `admin_page.html`,
`login_headers.txt`, `ledger_probe.json`.
