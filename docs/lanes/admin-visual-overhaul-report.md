# Lane report — admin visual/structural overhaul

**Lane:** admin-visual-overhaul · **File owned:** `server/admin.html` (layout, rhythm, register — not stat labels)
**Date:** 2026-10-06 · **Branch:** `base/v2` (merged on top of `dc889cd`, the max2-admin-deep pass)
**Verify:** guest view at `/admin/` against live prod — `python3 tools/admin_mirror.py 8080` → `http://127.0.0.1:8080/admin` (the mirror serves the local file and proxies every other GET to the NLB, so before and after see the *same* data).

---

## 1. Diagnosis — what the page actually failed at

| Defect | Evidence |
|---|---|
| **The product's most legible number never appeared.** Delhi's live PM2.5 mean (`/v2/city pm25_stats.mean`, public) was absent from the page — the fold led with a status line and 9 ops cards. A judge glancing at it saw a dashboard, not a live system. | `before/top-1280.png` |
| **The card grid lied about what it proved.** In guest view 6 of 9 cards read "nothing to show yet" because they read gated `/admin/api/*` fields — while public feeds already served equivalents (`/v2/city` median, `/aqi` calibration, `/v2/city` trip aggregates). An honest gate looked like a broken system. | `before/sec-stats.png` |
| **No narrative order.** Sections ran pipeline → fires → sensors → trips → guts → maps → riders → archive: an ops tour, not a demo. The "is it honest" evidence (validation, causal read) sat below corridor minutiae. | `before/full-1280.png` |
| **Rhythm was flat.** Every element the same size: a uniform grid of same-size cards, then uniform panels. Nothing owned the page; nothing told the viewer where to look first. | `before/full-1280.png` |
| **The fires section ran a full-page beige slab** for what is a stat-rail plus one map. | `before/sec-firemap.png` |

The bar was the ent-01 loading register: *a complex message delivered aesthetically — restraint with intent.* One resolved number, then quiet.

## 2. Decisions — what changed and why

**A live hero owns the fold.** One serif numeral — Delhi's live PM2.5 mean — wearing the page's only breathing edge (`breathe` moved off the field panel; one breathing element per page, per the register card). The CPCB band word is the only colour on the hero, as a muted wash chip. Under it, one plain-English line ("the mean across 25 sampled cells — median 52.5 · worst 83.5 µg/m³ — **every cell** above the WHO 24-hour guideline · indian aqi 95") and one provenance line (vs-typical %, GRAP stage, wind). A right-hand vitals rail carries the seven proof-stats (map state, rebuild cadence, instruments, map points, streets priced, fires, next rebuild). Every row traces a served field — see §4.

**The card grammar split by what it proves.** `cards` became two grids: `cardsA` (4 air-vitals, under the hero — all publicly fillable) and `cardsR` (5 rider-total cards, moved inside "06 · what riders share" where an honest-empty reads as "nothing shared yet" instead of a broken dashboard). Guest cards now say "locked — sign in" instead of the vaguer "nothing to show yet" when the field is truly token-gated, and fill from public feeds where they exist (max2's `/v2/city` trip-aggregate fill makes all five rider cards live for guests).

**Sections reordered to the demo arc.** `alive → made of → honest → right now → riders → archive`:
- **01 · what it's made of** — pipeline + feed table (folded together; feeds *are* what it's made of)
- **02 · is it honest** — field-state + scorecard first, then the causal read, then the guts (dose math, route engine, api stopwatch)
- **03 · fire belt** — now a rail+map grid (`firepanel`), killing the beige slab; `·` seps become invisible line-break items so each fact stacks (a `display:none` sep merges adjacent text runs into one anonymous flex item — found and fixed)
- **04/05** — district + field maps, unchanged
- **06 · what riders share** — rider cards + corridors + donations + shared-picture tiles
- **07 · archive** — the recorded history, last

**Register kept strict.** Light warm register, ONE accent (now the merged forest canon — the hero is accent-agnostic, everything reads `var(--accent)`), band colours only where colour means air quality (hero chip + verdict words). No gradients, glass, dials, or invented series anywhere; the only decorative motion is the breathing ring (off under `prefers-reduced-motion`). Band washes are solid blends toward white (`mixHex`, `.82` wash / `.55` ink pull) — never alpha-on-paper.

**The statusline slimmed.** With the vitals rail carrying the counts, `#stamp` is now just uptime + "as of" + the gate notice — one honest ticker, not a second dashboard.

## 3. Merge compatibility

The max2-admin-deep lane (`dc889cd`) landed mid-work. Resolution kept **my structure + their copy/logic**: their forest-accent canon, DPCC/idle-feed wording, `MODE_N` names, public `dn` fill from `CY.trips.days`, `calM` calibration fallback, `let dn`, species/forecast public fallbacks, and gated-row trims all merge intact; my hero, vitals rail, card split, section order, `firepanel` rail, and stamp slim survived. The median + MAE public-fallback logic was convergent — both lanes wrote it; theirs won (`calM`, "each monitor hidden in turn") with my `medW` caption kept.

## 4. Stat-truth spot-checks — every displayed stat → served field

Guest view, prod data at shoot time. Nothing on the page is computed except the band wash.

| Displayed stat | Source field | Check |
|---|---|---|
| Hero **56.7** µg/m³ | `GET /v2/city → pm25_stats.mean` = 56.7 | ✅ real, sampled |
| Band chip "satisfactory" | client `bandV(mean)` over `PM25BREAKS[30,60,90,120,250]` | ✅ computed label, declared |
| "mean across **25** sampled cells" | `pm25_stats.n` = 25 | ✅ |
| median 52.5 · worst 83.5 | `pm25_stats.median`, `.max` | ✅ |
| "every cell above WHO 24-h" | `pm25_stats.above_who24h_15` = 100 | ✅ |
| "indian aqi 95" | `grap.aqi` = 95 | ✅ |
| "49% below a typical oct day (≈110.4)" | `typical.vs_now_pct` = −49, `.median` | ✅ |
| "below emergency-rules stage I" | `grap.equivalent_stage` = 0 | ✅ labelled computed-here |
| "wind 6.6 km/h from 125°" | `CY.wind.speed_kmh/from_deg` | ✅ |
| vitals: map is LIVE | `S.field.serving` (fallback `A.field`) | ✅ |
| vitals: last rebuilt 2m · every ~15m | `field.age_s` + `CY.field.refresh_ttl_s` (900s) | ✅ |
| vitals: instruments 54 · govt feeds | `field.station_readings` + `stations_src` (waqi+dpcc) | ✅ |
| vitals: map points 100 | `field.samples` | ✅ |
| vitals: streets priced 9,03,058 | `S.routing.edges_priced` → `/health routing.edges_priced` | ✅ |
| vitals: fires 67 · 15 belt | `GET /aqi → fire.fires`, `.belt_fires` | ✅ |
| vitals: next rebuild in 13m | `CY.field.refresh_in_s` (fallback `/health field_refresh_in_s`) | ✅ |
| card: air-map freshness 2m | `field.age_s` + `stale` flag | ✅ |
| card: 100 map points · 54 monitors | `field.samples`, `station_readings` | ✅ |
| card: delhi median 52.5 | `daily.median_pm25` (gated) → `CY.pm25_stats.median` | ✅ labelled "middle of 25 sampled points" |
| card: how wrong 46.1 µg/m³ | `loso.mae_ugm3` → `archR.mae_ugm3` → `/aqi calibration.mae_ug` (n=94) | ✅ labelled "live check · each monitor hidden in turn" |
| rider cards: 39 trips / 12 streets / 4 switches / 104 µg / 12.7 kg | `dn.totals` — gated `/admin/api/donations`, else public `/v2/city trips.days` fold (max2's fill) | ✅ same store, k≥3 |

**Removed/un-traced:** nothing was removed; the only previously-unlabelled gaps (guest-view internals) are now explicitly labelled "locked — sign in" or filled from public equivalents. The hero emits no number until `/v2/city` answers — offline degrades to the em-dash state with an honest "the city feed is unreachable — retries every 30s, never fills a number in."

## 5. Before / after

- `before/top-1280.png` → `after/top-1280.png` — ops grid → hero + vitals rail + live cards
- `before/full-1280.png` → `after/full-1280.png` — flat tour → demo arc
- `before/top-390.png` · `mid-390.png` → `after/*` — hero stacks, vitals go two-col then one-col at ≤400px, tables keep `scrollx`
- `before/sec-stats.png` → `after/sec-stats.png` — 6× "nothing to show yet" → 4 live vitals (gated cards relocated)
- `before/sec-firemap.png` → `after/sec-firemap.png` — beige slab → stat-rail + map
- `after/sec-hero.png`, `after/sec-donations.png` — hero detail + rider section with public fills

Verification: `node --check` on the extracted `<script>` — clean. Every `id` queried in JS, every JS-emitted class, and every test-mandated string survives (DOM/JS contract preserved — wrapper markup + CSS + emit tweaks only). Boot strip untouched (once-per-session ≤2.5s, skippable, real number only — `before/boot*.png`).

## 6. Follow-ups worth a later lane

- **Operator (authed) view** now shows `locked` only where fields are truly missing — worth one post-auth shoot on demo day to confirm no regression behind the token.
- The **fires rail** would read slightly tighter if the emit grouped number+label per item — cosmetic, left alone to keep the max2 lane's label strings byte-identical.
