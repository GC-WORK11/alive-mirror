# Demo-day killer hunt — second pass, 8 October 2026

## Verdict and boundaries

**Five real defects found in the new surfaces, all fixed in source.** The
headline misses were a dead "the map ↓" anchor on the rebuilt landing, a
GRAP line that claimed a nonexistent "stage 0" while `/city` and the board
correctly said "below stage i", and a provenance merge in the app-home
rework that hangs the air-map's age under the personal dose numeral on
counted days. The `/in/<token>` magic link survived a live attack pass —
no leak found; residual notes below.

- Audited `base/v2` at `b2476fe` (deploy-14); production `/health`
  reports `30af6b17` — the same code is live. GET evidence captured
  ~10:58–11:09 UTC / 16:28–16:39 IST.
- **Mid-hunt HEAD moved to `2db17fb`:** the sibling honesty-cluster lane
  landed `2babf6d` (F2/F4/F6/F7/F8 — verified below) and `dd2aec3`,
  which independently caught and fixed the same dead anchor as V1
  (their `id="fieldSec"` on the `<section>` survived the rebase; my
  duplicate was dropped). Prod evidence predates those commits — it
  stands, unchanged, for `30af6b17`.
- Scope: `4101bd8` (rebuilt `/`), `65d413a` (`<mount>/in/<token>`),
  `2f683cb` (app-home), `d05b737` + everything since `6f799ee`.
- **Every production request was GET. No POST, no login, no mutation, no
  deploy.** The magic-link rate bound was measured with 17 wrong-token
  GETs — the brake itself is the thing verified, not the token.
- First-pass open items (F2, F4, F6, F7, F8) are a sibling lane's job —
  see "pending verification" at the end. F3 persists and is re-listed.

## Ranked findings

| Severity | Finding | Evidence | User-visible effect | Fix |
|---|---|---|---|---|
| **visible flaw** | **V1 — "the map ↓" link on the forecast card goes nowhere** | `server/landing.html:593` renders `href="#fieldSec"`; no element carries `id="fieldSec"` (confirmed in served bytes at `30af6b17`) | A judge clicking the spark card's map link gets a dead anchor — the page does not scroll | **Fixed:** v8-sync lane put `id="fieldSec"` on the field `<section>` at `dd2aec3` before my push landed — kept theirs on rebase |
| **visible flaw** | **V2 — Landing claims GRAP "stage 0"; other surfaces say "below stage i"** | Same served payload at one instant: `/v2/city` `grap={equivalent_stage:0, aqi:90}` → `/` printed `stage 0 · aqi 90` (`landing.html:1635`); `/city` prints "below stage i" (`city.html:1471-1473`); the board prints "below GRAP stage I — no restrictions map to this air" (`admin.html:1181-1183`). `/city` + board also disclose "computed here — the official stage is caqm's"; `/` disclosed nothing | Cross-surface contradiction a judge can see in two tabs, and the landing alone presents a computed equivalent as a named legal stage — GRAP's stages are I–IV; "stage 0" doesn't exist | **Fixed:** `vGrap` now prints `below stage i · aqi 90` / `stage ii · aqi N` with a hover title carrying the computed-not-CAQM note |
| **visible flaw** | **V3 — Counted-day dose numeral wears the air map's age** | `Mobile/src/screens/HomeScreen.tsx:1053-1054` sets `airAgeLine` whenever `airSrc==="live"`; the reworked `provLine` (line 1097) joined it without the old `!counted` gate (`git show 2f683cb` removed the `{!counted && airAgeLine != null}` block) | On a counted day the hero reads "you've breathed N µg" and cites "air reading: N min old" beneath it — the field's freshness attributed to a personal on-device dose; en + hi strings both affected | **Fixed:** `airAgeLine` re-gated to `!counted` inside `provLine` |
| **edge** | **V4 — Spark card contradicts itself: "twelve" vs "11"** | `landing.html:588` kchip "the next twelve hours"; `sparkL` printed `the next ${vs.length-1} hours` — `/v2/city` `next_hours` serves 12 slots (11:00→22:00 verified) → "the next 11 hours" | The same card says twelve and 11 | **Fixed:** `sparkL` now prints `vs.length` (12) — matches the kchip |
| **edge** | **V5 — District strip renders blank if `/v2/districts` fails** | `landing.html:1867-1870`: the catch skipped `paintDChips()`, so the honest "district feed resting" message inside it never rendered — `distN` stayed `—`, the strip stayed empty | On a feed outage the districts panel is silently blank instead of saying so | **Fixed:** catch now calls `paintDChips()` when `DIST` is empty, which renders the resting line |
| **edge** | **V6 — F3 persists on the new surface, ×3** | `landing.html:495,530,650` all link `github.com/<owner>/Delhi-Air-108/releases`; unauthenticated GET re-verified **404** at 11:06 UTC | The rebuilt landing advertises "get the app" in three places; every one is a dead end for a judge | **Owner decision (unchanged):** needs a public artifact URL or repo visibility call — no fix made |

## The magic link, attacked — `GET <mount>/in/<token>`

Verified clean, live:

| Attack surface | Result |
|---|---|
| Wrong guess | `HTTP/1.1 404` + `{"detail":"Not Found"}` — **byte-identical** headers/body to an unknown path on the same mount (verified side-by-side) |
| Guessing budget | prod burst test: guesses 1–5 → 404, 6+ → `429` + `retry-after` — the `(0.2, 5)` bucket is bound and live |
| Token compare | `hmac.compare_digest` (`main.py:1728`) — constant-time |
| Cookie | same mint as the form: `HttpOnly`, `SameSite=Strict`, `path=/`, `Secure` iff the request arrived TLS (`main.py:1734-1737`) |
| Replay from cache | `cache-control: no-store` on the 303 (`main.py:1739`) |
| Referrer leak | `referrer-policy: no-referrer` rides **every** response (`middleware.py:322`) — the post-303 request to the mount carries no `Referer`; the token cannot leak downstream that way |
| URL in history | the token URL is one history entry that stays — by design it re-mints a session (notes below) |
| Log capture | request logger rewrites the path to `/in/<redacted>` before the record is built (`observability.py:458-465`); uvicorn runs `--no-access-log` (`server/Dockerfile:117-122`), so the request line never lands in CloudWatch either |
| Metrics | label is the route template `<mount>/in/{secret}` — never the concrete path (`observability.py:149`) |
| Schema leak | `include_in_schema=False`; `/openapi.json` has zero mount/admin paths; public HTML carries zero mount strings |

Residual notes (accepted risk, not findings):

- The comment claims `/in/` "shares login rate bucket" — it doesn't: the
  bucket key is `client|path-prefix`, so `/login` and `/in/` are parallel
  buckets. Combined ceiling is ~0.4 rps (5+5 free) not 0.2 — still a dead
  end for brute force, but the claim is wrong in the margin.
- A burst of wrong `/in/` guesses flips that prefix to 429 while sibling
  mount paths keep 404ing — an attacker who already found the mount learns
  `/in/` exists. Its existence is committed in source anyway; ~zero leak.
- The same brake also locks out the *correct* link for ~25 s if the
  owner fat-fingers five wrong ones — honest, but worth knowing at
  demo-morning.
- `secure` stays off over plain-HTTP prod — same documented owner call as
  the form login; HTTP transport is the previously recorded risk.

## Other verified-clean surfaces (new code)

| Demo beat | Verified invariant (evidence @ `30af6b17`) | Boundary |
|---|---|---|
| Cold `/` load | 200, 95.5 KB; every fetch target 200: `/grid?cells=34&param=pm2_5|us_aqi|pm10` (1156 features, `cell_epoch` fresh), `/v2/reverse` ("near Baba Kharak Singh Marg"), `/today` (24 IST hours, `hour_now_ist`=16 = 4pm IST ✓), `/v2/skill` (ok, mae 23.8, n 475, 63 h graded), `/v2/why` (line + 1 driver + story_age_s), `/v2/districts` (29), both geojsons, `/depart` (12 slots), all 6 new app images | Boot driven by these payloads — no new browser soak |
| Hero numeral | `pm25_stats.mean` = **53.6 µg/m³**, band=satisfactory; "map N min fresh" discloses field age (547–589 s); toplive + anchor + vitals all derive from the same reads | `/v2/city` `cached_s` (~40 s) adds an undisclosed ≤2 min payload-cache layer under "live" — edge note |
| Vitals rail | stations 52 · wind 8.6 km/h NW · segments 903k priced of 1.07m · grap (see V2) · next 12h 64.4–99.1 | — |
| Field raster | lerped `rampCol` anchors are per-pollutant and sane; conf-based alpha; cell inspector + a→b + keyboard path code-verified; honest failure states string-verified | Pixel rendering not re-driven on prod this pass |
| a→b pricing | `/v2/plan` response contract — `options[].{label,mode,tag,recommended,route_geojson,segments[].start_frac/end_frac/pm25,distance_km,eta_s,dose.lo/mid/hi/confidence/sparse/basis,reaches_destination,starts_at_origin,truncated_gap_km,origin_gap_km}`, `degraded`, `took_ms` — all exist in `v2/plan.py` (2096-2289); demo points are inside the priced bbox | POST not fired (GET-only brief) |
| Districts | served payload carries name/aqi/pm25/color/level/parent/state/category/confidence/cells_covered/partial_field_coverage — every field the chips+pop read exists | — |
| Strips | story card reads `why.{line,cause_note,drivers[0].evidence,story_age_s}` — all live; daybars read `hours_ist[24]` + `hour_now_ist` — IST labels honest; skill line gates on `status==="ok"` + real pair counts | — |
| Admin mount secrecy | `/admin` → 404; openapi clean; `/`, `/city`, `/community` bytes carry zero mount strings | — |
| App-home rework | tsc + expo lint green post-fix; `BandScale` gradient/a11y intact; reduce-motion paths honored | No new device drive — sibling lane owns APK evidence |
| Secrets scan | served `/` + `/city` + `/community` bytes: no tokens, keys, mount paths, or admin URLs | Source tree scan was first-pass scope |

## Notes — not findings

- **"a typical october day"** hardcodes the month in `landing.html:598`
  while `/v2/city.typical.month` (=10) is served — goes stale Nov 1.
  Cheap fix: render the month from the payload.
- District chip silhouettes use served **raw** CPCB hues (`#FFFF00`,
  `#92D050`) at 0.85 opacity — the only un-muted band color on the page
  (chip surfaces get `washHex` 0.82). Consistent with `/city` (same
  served color) but the hue is raw on a muted page — design-law call.
- `departAB`: if `pct_less_vs_now` is ever absent while `best` is ahead,
  the line claims "now is the light slot" — server always pairs them
  today (`now`, `pct_less_vs_now`, `best` all present live).
- `BandScale`'s SVG gradient id `bandRamp` is static — two mounted
  instances (Home hero + DelhiToday in the same nav stack) would collide
  in name; invisible today because the defs are byte-identical.
- `dayStrip` keeps its honest-empty if `/today` fails, but `dayWhy`'s
  `vs_now_pct` line (from `/v2/city`) can still paint — mixed fresh/
  recorded state is labelled, acceptable.

## First-pass open items — verified landed at `2babf6d` (sibling lane)

All five landed while this hunt was in flight; each verified in code at
HEAD `2db17fb` (prod still runs `30af6b17`, so none are live yet):

| Item | Verification |
|---|---|
| F2 search substitutes | **Fixed** — `Mobile/src/search/client.ts:43-96` now propagates `match`/`match_rank`/`anchor`/`compound`; the F2 comment cites the old drop |
| F4 yesterday-leak | **Fixed** — `DelhiToday.tsx:78` keys on `cityToday()` = server-stamped `trips.today`/`today_key` (`api/city.ts:127-130`); absent key → honest no-card, yesterday can no longer wear a TODAY title |
| F6 CO₂ bases | **Fixed** — `nav/engine.ts:148-157` `co2Split` emits `co2_moving_g`/`co2_idle_g`/`co2_cold_g` phase bands, consumed by `VehicleSheet` + `CompareSheet` |
| F7 "line you set" | **Fixed** — `i18n/strings.ts:795-802` adds the `*Sugg` suggested-ceiling family (en+hi); the chosen-profile line keeps "a line you set, not a medical rule" (:794) |
| F8 UTC-day | **Fixed by disclosure** — the UTC ledger key (`gmtime`, `city.py:440,471`) stays (correct — it is the bucket key), and the surface now says it: `cityTodayUtc` "utc day · resets 05:30 ist" en+hi (`strings.ts:307,1443`), rendered at `DelhiToday.tsx:633,949` |
| F3 dead download | **Open** — re-verified 404 (V6); owner decision |
| F1 fallback samples, F5 map-age wiring | Fixed-in-source at `f9e6e72` — not re-verified on a device build this pass |

## Checks run

| Check | Result |
|---|---|
| `python3 scripts/check_inline_scripts.py` | PASS — 4 blocks parse clean |
| `cd Mobile && npx tsc --noEmit` | PASS |
| `cd Mobile && npx expo lint` | PASS |
| prod GET sweep (17 endpoints + assets) | all 200; field shapes verified above |
| magic-link prod probes | 404-shape identity, 429 bound, headers — verified |
| `git diff --check` | PASS |
