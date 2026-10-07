# Leftover-fixup lane — report

Lane scope: the day's lane reports catalogued real-but-small defects with no
owner. This lane fixed the copy/code-fixable ones; everything server-side is
committed + marked **DEPLOY-PENDING** (prod is GET-only for lanes).

Head at lane start: `3ce2775` (offline-verify). Gates:
`npx tsc --noEmit` clean · `npx expo lint` clean · `node src/store/test-runner.mjs`
+ `src/nav` + `src/api` + `src/offline` all 0-fail · `node src/search/test-t0.mjs`
probe unchanged for the connaught query (single `Connaught Place` macrohood
row) · server probes run with `python3` against `transit_v2.py` /
`v2/gazetteer.py` directly (no venv on this box — assertions listed below,
all pass).

## Fixed — App / Mobile

| # | Defect (source report) | Fix | Where | Verified |
|---|---|---|---|---|
| 1 | `/health` ping had **no timeout** — a blackholed route leaves the fetch pending forever, so a stall-type dead net produced zero *completed* misses and `apiOk` could never fail honestly (offline-verify catalogue) | Ping now goes through `fetchJson(url, 8000)` (AbortController inside) — bounded to 8 s inside the 15 s cadence; a hang now counts as a miss like any real failure | `App.tsx` boot ping (`~:479`) | tsc+lint; fetchJson's abort pattern is the same one `/aqi` has used all along |
| 2 | `'air reading: N min old'` **froze between dedupe-suppressed renders** — the served field block is verbatim-identical between rebuilds, the JSON dedupe holds `aqiField`, `mapField`'s memo never re-ran, and the displayed age stopped mid-count (android-verify bug #1) | 30 s `ageTick` interval in App state, added to the `mapField` memo deps — every consumer (`fieldAgeS`/`fieldStale` → hero, incidents card, `FreshnessChip`, `AirMapCard`, WeekSheet, CompareSheet) re-derives age on wall-clock and `stale` can cross `stale_after_s` live on a dead network | `App.tsx` `:809–823` | tsc+lint; memo previously computed the live age correctly — the bug was invalidation, so one tick fixes all surfaces |
| 3 | **'Connaught Place · Delhi' vs '· district' dupe** — same place, two entity kinds: the OSM admin-area row + the place row both render (android-verify "candidate dupe rows") | `sameNamedPlace` in `search/client.ts` — same normalized name collapses at <75 m for any kinds, at <400 m when either side is `district`/`administrative` (a polygon centroid sits ~100 m off the place point; the gazetteer district row is ~117 m off the macrohood). `mergeResults` uses it and lets a later **non-admin** row take the admin row's slot; `SearchScreen.samePlace` now aliases it (covers the t0-vs-server filter at `:369` too). The two distinct `Connaught Lane` rows (~620 m apart, both non-admin) are preserved | `client.ts` `:217–247`, `SearchScreen.tsx` `:60–62` | python mirror of the rule asserted: macrohood kept at district's slot, lanes preserved, 'Shahdara' district→locality collapse; t0 probe unchanged. **On-sim: `connaught` search renders ONE `Connaught Place` row while prod `/v2/search?q=connaught` still returns both — client dedupe proven live (see below).** |
| 4 | `pick(p, "to")` **hardcoded on every typed map/search pick** — a pick while "Where from?" was armed silently dropped into `to` (offline-verify catalogue #1) | The three call sites (`onMapPress`, `onMapLongPress`, `onSearchSelect` place branch) now call `pick(p)` so `which ?? editWhich` honors the armed slot; `onNavigate` (saved-place tap) keeps `"to"` — destination intent by design | `App.tsx` `:879–883`, `:888`, `:924–927` | tsc+lint; `pick`'s from-branch already handles `to`-unset (stays in `search` phase). **On-sim: armed-`from` pick landed as `from`, `to` kept — see below** |
| 5 | `to`/`from` **lingered after a finished trip** — next "Where to?" reopened on the ended destination; closing the sheet could silently re-enter compare (offline-verify catalogue #2) | `exitNav` now clears `from`/`to` + all plan artifacts (`options`, `depart`, `departCurve`, `steps`, `strips`, `planError`, `planField`, `planDegraded`) alongside the existing `phase→idle` — ordering safe because `recordTrip` runs inside `onArrive` before Done | `useShellFlow.ts` `:428–437` | tsc+lint; same clear set as `clearRoute`; deps list extended for the wrapped `setOptions`/`setSelected`. **On-sim: 'change the trip' → home pill back to empty 'Where to?'** |
| 6 | `WHO_DAILY_UG = 15` **duplicated** + `DayPeek` re-hardcoded `budgetUg = 216` (component-audit nit tier) | `WHO_DAILY_UG` exported once from `components/shell/settings.ts` (next to `PROFILE_BUDGET_UG`); `HomeScreen` + `DelhiToday` import it; `DayPeekInner` default is `PROFILE_BUDGET_UG.general` | `settings.ts` `:54–56`, `HomeScreen.tsx` `:102/:845`, `DelhiToday.tsx` `:52` | tsc+lint |
| 7 | **NCR bbox divergent in 3 files** — client `inNcr` (t0.ts + net.ts dup) and the photon `bbox` used a *wider* box (76.75–77.95 / 28.15–28.98) than the server's `v2/deps.NCR_BBOX` (76.80–77.90 / 28.20–28.95): fringe points read "in Delhi" app-side while the API said `beyond_field_edge` | `NCR_BOUNDS` single-sourced in `search/t0.ts` at the **server-canonical** box; `net.ts` re-exports `inNcr`; `tileWarm.ts` imports `NCR_BOUNDS`; photon `&bbox=` builds from it. Deliberately aligned *down* to the server box so client-side 'outside NCR' tags agree with the API's verdicts | `t0.ts` `:42–52`, `net.ts` `:17–20`, `tileWarm.ts` `:33/:41`, `client.ts` `:172` | `v2/deps.py:21` + `tiles.py:60` confirmed `(76.80,28.20,77.90,28.95)`; grep found no other importer of the removed `NCR` object |

## Fixed — server (DEPLOY-PENDING, no deploy from this lane)

| # | Defect | Fix | Where | Verified |
|---|---|---|---|---|
| 8 | `0AIRPORTEXP-4(NS)`-style feed ids still surfaced as line names — parens escaped the `^[A-Z0-9_-]{9,}$` suppression regex (deploy-7, verified live on prod) | `line_name` now strips feed service tags first: trailing `([A-Z0-9+-]{1,3})` groups (`(NS)`, `(-)`, `(+)` — word-length qualifiers like `(Night)` stay) and a leading `0` ahead of a letter; then the id test. Added a second shape `^[A-Z]{4,}-[0-9]+$` for short LETTERS-NUMBER slugs (`LNWST-1`) | `server/transit_v2.py` `:103–121` | unit probe — `0AIRPORTEXP-4(NS)`→`Bus`, `0OMS(-)(NS)`→`OMS`, `0TMS(+)(NS)`→`TMS`, `CGOCOMPLEX-2`/`LNWST-1`/`EXPRESS-20A`→`Bus`; `347ACL`/`347AUP→347A`/`101UP→101`/`HOHO`/`0334`/`Airport Express (Night)` survive; metro `BLUE_*`→`Blue` unchanged |
| 9 | Gazetteer `search()` returned **no result-level same-name dedupe** — ingest dedupe only collapses ≤~110 m (name+`round(lat,3)`), so the CP district/macrohood pair at 117 m survived server-side | `Gazetteer._collapse_same_named` runs over the score-sorted candidates before the `out` build — same 75 m / admin-400 m rule as the client; an admin row hands its slot to a later non-admin row of the same name | `server/v2/gazetteer.py` `:546–577` + call at `:608` | python assertions on fixture scored lists: district-first ordering still yields the macrohood row at slot 0; two real same-name neighbours preserved. **Prod evidence (GET-only), pre-deploy: `GET /v2/search?q=connaught` returns both `Connaught Place` rows — `district` 998 m + `macrohood` 936 m.** After deploy this collapses to one row |

## Checked — already fixed at HEAD or deliberately left

| Flag (report) | Disposition |
|---|---|
| jargon-sweep "structural, copy-fixable" trio | All landed already: `why.line` en passthrough rebuilt from `drivers[]` for both languages (`DelhiToday.tsx:186–203`), the `0–237.5` estimate band edges are `Math.round`'d (`:688–693`), `emit_perPax` reads `, per rider ({o} aboard)` (`strings.ts:596`) — no `÷` glyph |
| component-audit nits with named owners | `shortDate()` localized the `2026-10-09` ISO leak (`HomeScreen.tsx:657`, `daywords.ts`); WeekStrip AX name says `weekNoReads` not "T 0" (`WeekStrip.tsx:108`); freshness chip reads "N min old" (jargon-sweep) — all landed |
| Served species decimals (`285.2 µg/m³`), US-AQI tile presence, 24 h/12 h clock split, GRAP roman numerals, `fmtCig` `<0.01`, `receipt_lessVs` `2.3× less` | Design calls / "keep" verdicts in the original reports — not this lane |
| offline-verify: ambient pill hides under the home sheet on dead net | Report calls it a product decision — left |
| android-verify: placePickSlot-then-map-tap, editWhich persistence | Behavior consistent with the armed-slot model; the visible tap path now honors it (fix #4) |

## On-device evidence — iPhone 17 sim (iOS 26.5), dev client → prod `http://65.2.28.40`

Input note: the rig's recorded-press paths (AXPress and pixel taps on this VM)
are unreliable on RN Pressables — verification was driven with `CGEvent`
clicks at computed coords plus `simctl location`/`privacy` toggles.

| Fix | On-sim observation |
|---|---|
| #2 age tick | Home air label advanced across screenshots without any re-render trigger: `2 min old` → `5 min old` → `11 min old` → fresh read resets to `1 min old` |
| #3 CP dedupe | Search `connaught` → single `Connaught Place` row (Delhi). Same query on prod `/v2/search` returns **two** rows (`district` 998 m + `macrohood` 936 m) — the client merge suppresses the dupe until the server fix deploys |
| #4 armed `from` | Location permission revoked + `simctl location clear` → `posNow` null. Picked `to` = *Lajpat Nagar railway station* → sheet re-titled **"Where from?"** + `couldn't get your location — type a place instead`, `to` preserved. Picked *Connaught Place* → landed as `from`: camera flew New Delhi, `/v2/plan` painted real options (`a typical Delhi ride`, `tomorrow 4:00 am → ~26% less smoke`) |
| #5 `to` clear | `change the trip` (outside-NCR error) and post-flow returns both landed on home with an **empty** `Where to?` pill — `to` no longer lingers |
| #1 health timeout | Not directly observable on a healthy net; the ping now shares `fetchJson`'s AbortController path that every other API call on screen exercised all session |
| #7 NCR bbox | Indirect: outside-NCR verdict now follows the server — picking `to` while `from`=stale SF fix rendered the typed `this trip sits outside Delhi NCR` card (server `outside_service_area`), agreeing with the tightened client box |

## Remaining DEPLOY-PENDING notes for the next deploy lane

- `transit_v2.py` `line_name` — rider-facing labels on any GTFS id like
  `0AIRPORTEXP-4(NS)` become `Bus`; service-run ids (`0OMS(-)(NS)`)
  become `OMS`/`TMS`. No wire-format change.
- `v2/gazetteer.py` — `search()` now collapses same-named admin-area rows
  into the place row; t1 result lists can shrink by a row vs prod today.
