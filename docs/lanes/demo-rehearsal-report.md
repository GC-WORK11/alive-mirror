# demo-rehearsal — the stage script performed literally, beat by beat

Lane: `demo-rehearsal` · pass **2026-10-07 ~03:30–05:15 UTC**
(≈09:00–10:45 IST, a demo-morning-like window).
Script under test: `docs/plan/demo-script.md` (≤2:50, 8 beats, last
re-verified Oct-6 on `4eb9e1e8`) + the phone-facing flow in
`docs/demo-day.md` "the judge's first 90 seconds". The recorded-film
scripts (`docs/11-demo-script.md`, `docs/video/shotlist.md`) are a
different artifact — their claims are checked where they overlap.

- **App under test:** release APK built at `341126f` (HEAD at build
  time; zero `Mobile/` commits in `b0dd079..341126f`), sha256
  `066a2c0e06529c8820661bb2a502e75126c3bcca04fcded9a26507aa847feb5a`,
  bundle grep: `65.2.28.40` ×1, `localhost`/`10.0.2.2` ×0.
  Built + driven on a Linux KVM emulator (api-35 x86_64, SwiftShader)
  by child session `7dd38f23` (macOS parent box has no Android SDK /
  nested virt — the proven pattern).
  ⚠ **APK drift:** `341126f..HEAD` now carries **19 `Mobile/` commits**
  (notify-v2 events-engine rewire, safefile stores, route tint /
  plan-segments seam, nav camera-follow, daysum clamp, pocket-engine,
  plural fixes). Per the runbook's own rule ("demo APK = newest HEAD
  build") the stage build must be re-cut at final HEAD and at minimum
  cold-launch → sheet → compare → depart → notifications re-smoked —
  the evidence below is for the `341126f` build.
- **Live service at drive time:** build **`aee635eb`**
  (`/health build_sha`), NLB HTTP :80. Stations **53** (waqi+dpcc),
  field_age ~738 s, `refresh_in_s` counting, `field_stale:false`,
  engine `alive_core`, edges 1,070,459 / 903,058 priced, transit
  real_feeds metro+bus `true`, fires **80** (20 in-belt, 42.1 MW),
  wind **8.0 km/h @104° — easterly** → smoke modifier **1.1, fires
  REFUSED**. (A sibling lane deployed `a1dca1ec` mid-pass — /health
  re-read at T-45 is mandatory regardless.)
- **Probe discipline:** GETs + sanctioned `POST /v2/plan` +
  `POST /v2/reroute` only. No app/server code touched — report + shots
  are this lane's only writes.

---

## Verdict at a glance

| tally | count |
|---|---|
| works-as-scripted | **6 of 8 stage beats** + every phone-flow step |
| works-but-timing/wording | beats 3 (metro row / drift) + 4 (depart horizon) |
| broken (P0) | **0 on the demo APK** — see below |

**The 90 s question, answered:** a deliberate in-window probe
(force-stop → cold launch → "Where to?" at ~t+38 s → ~60 s of sheet
use) **survived** — same pid throughout, zero `FATAL`/`ANR`/`SIGSEGV`/
`SIGABRT` lines for `com.anonymous.app` across the *entire* session
log (all launches, nav feeds, offline cycles). The crash window is an
**iOS-only hazard as evidenced**; the documented judge flow is safe on
the Android demo build. §3 keeps the doc-fix recommendation (one
explicit ≥90 s line) because the iOS rule isn't disproven — only
Android is verified.

**Headline risks:** (1) APK is already 19 Mobile commits stale —
rebuild before stage; (2) depart "5×/~113" cannot render — the app's
curve is the 24 h window (today: 30.7 → best 26.8@+8 h / worst 55.2);
(3) "car beats metro" stalls on the scripted CP→GGN OD (no metro row)
but **works on the demo OD as judges actually type it** (metro+walk
62.4 vs car-AC 9.3); (4) a real shipped-path bug: the "remind me"
notification overstates the saving ~2.5× (§4).

---

## 1 · Stage beats — `docs/plan/demo-script.md`, in order

| # | scripted | beat / surface | scripted line (abridged) | screen truth today (evidence) | timing | verdict |
|---|----------|----------------|--------------------------|-------------------------------|--------|---------|
| 1 | 0:00–0:12 | `/` landing — raster + wind arrow | "live pollution field … the arrow is today's real wind … scrubber walks the next twelve hours" | phone-Chrome @390 px (shot 57–61): hero "60.3 µg/m³ MODERATE · ≈2.7 cigarettes · LIVE FIELD MEAN", ticker "53 STATIONS LIVE · FIELD 15 MIN FRESH · MEDIAN 59 · WIND 9 KM/H · **903K EDGES PRICED**", lattice + "▶ WATCH THE DAY" scrubber; `/grid` 484 cells (conf hi166/med296/lo22); wind 8.0 km/h @104° E (direction drifted, verbatim safe) | curl 200 ~0.5 s; page paints on-phone | **works-as-scripted** |
| 2 | 0:12–0:30 | `/aqi` @ Connaught Place | "US AQI around 160 … fifty-four live instruments … about sixty-five NASA fire detections" | us_aqi **152–157** (drifted within the hour); instruments **53** not 54 (in accepted 52–54 band); fires **80** not ~65; pm25 63.1/57.3; nearest 1.8 km; `refresh_in_s` ticking; modifier **1.1 — REFUSED** (fires feed, easterly) | endpoint ~0.5 s | **works-as-scripted** (fires aside must run the "refused" wording today — see drift log) |
| 3 | 0:30–1:05 | `/v2/plan` compare sheet | "about twenty options in under two seconds … on foot ~300 µg; auto ~26; metro+walk ~38; sealed AC car ~9 beats the metro … thirty-times spread" | **On the demo OD as typed** ("huda city centre" → metro station 28.4958,77.0854): app ladder shows **22 rows** — car-AC **≈10 [4–15]** vs on-foot **≈333 [142–524] → 34.3×**; **metro+walk PRESENT ≈64 [28–99]**; auto ≈30; bus 47B→790 ≈82; bicycle ≈148. On the scripted CP→GGN OD: 23 opts, car-AC 11.4 vs walk 418.2 → 36.7×, **no metro row**. | fresh-OD plan **~11 s wall to settled** (server `took_ms` 5.5 s); recents re-plan +5.7 s; warm server hits ~0.1–0.7 s | **works-but-wording**: verbatim's "~9/~26/~38" are ~10/~29/~64 on the demo OD; the "beats metro" clause only lands if the demo OD keeps its metro row (verify at T-45 — GTFS service-hours dependent); "under two seconds" only holds on a **warmed** OD — `warm_task.py` at T-40 is load-bearing |
| 4 | 1:05–1:30 | `/depart` curve | "now ~21 µg … worst hour ~113 — over five times worse … best slot ~16 about two days out" | DepartGraph draws instantly (shot 20): **curve ≈9 → ≈15 µg over 24 h** on the demo OD (car-AC trip; /depart now 30.7/best 26.8@+8 h/worst-in-24 h 55.2 at the car mode read); the scripted ~113 @+63 h lives only on `?hours=120` (worst 137.4 @+60 h) — **out of the app's window**. "leave later" row **flickers at the gate**: rendered earlier ("leave 09:00 → breathe ~13% less"), **suppressed at capture** — `/depart` was serving `ug_saved_vs_now:8` vs client gate `>8` | curve <1 s | **works-but-timing**: on-screen worst ≈15–55 not ~113 → re-word to the visible story ("tonight's peak roughly doubles the dose; the multi-day forecast finds the real spike") or point at the curve's own peak, not a memorized number |
| 5 | 1:30–1:55 | `/v2/city` + `/admin` + `/community` | "Fourteen contributors … ~5 km … ~400 µg … over seven hundred all-time … street to street ~52→~86 … k≥3" | contributors **22**, km_today 8.0, obs 40/1-today, avoided **62.5 µg/24 h · 1,028.5 all-time**; `/v2/strip` on minted route: **90 samples @ step_m 250.0, pm25 45.3→73.9 (1.63×)**; corridors 12/55 `min_k` 3; `/city` renders "61 µg/m³ MODERATE · AQI 106 · 29 districts · easiest East Delhi 84 · heaviest South West Delhi 163 · WHY: air barely moving" (shots 62–64); `/community` ledger + street table live (shot 65); `/admin` public board, no token prompt, "INSTRUMENTS 51 · STREETS PRICED 9,03,058 · FIRES 80 · LAST REBUILT 2 m ago" (shot 66) | pages ~0.5–2 s | **works-as-scripted** (re-pin quoted figures; note admin shows "51 instruments" vs health's 53 — ±2 aging skew, cosmetic) |
| 6 | 1:55–2:20 | AWS console — ECS `alive108` | "one service, one task, healthy, Spot-priced … ~$46/mo" | **not verifiable from this lane** (no AWS creds). Last token-probed verify Oct-6: ACTIVE · 1/1 · FARGATE_SPOT · task-def `:181` · image==`/health build_sha` — image has since moved to `aee635eb`; read the task-def off the console live | n/a | works-as-scripted, **conditional** on T-45 CLI understudy from a credentialed box |
| 7 | 2:20–2:40 | `/admin` species pills | "95.2 % @2σ / 3,550 held-out h … ten pollutants … ammonia honestly empty … PM2.5↔NO₂ only +0.34" | `/aqi` @CP: **9 species + pm25 live, nh3 null** ✓; DelhiToday species row shows **NH3 honestly absent** on phone too (shots 35–37); admin surface computes the corr live (was +0.55 at Oct-6 read — "only ~+0.3–0.5" phrasing is safe); "−46 % vs decade norm" now on screen (fix-numbers-drift reframed it to "third-to-half" in docs) | instant | **works-as-scripted** (re-pin corr at T-45) |
| 8 | 2:40–2:50 | back to `/` — close | "dose every 250 metres … emissions per mode" | `/v2/strip` `step_m` **250.0** live; emissions ranges render on the why/physics expander (shot 21: "1.911–5.3757 kg CO₂ · 0.0683–3.3017 g PM2.5 … BS-III–BS-VI fleet mix") | instant | **works-as-scripted** |

**Stage timing arithmetic:** scripted 2:50 with 10 s slack. Measured
interaction costs that eat it: fresh-OD plan **~11 s wall** (if the OD
isn't warmed), cold→ambient ~3 s, search→compare ~10 s of taps. The
only beat that can blow its slice is **beat 3's plan wait on an
unwarmed OD** — the T-40 `warm_task.py` + T-15 full pass are what keep
"under two seconds" honest. Everything else is sub-second-to-few-second.

## 2 · Phone flow — `docs/demo-day.md` "judge's first 90 seconds", driven cold

| step | scripted / expected | observed on the release APK (emulator, logcat clean) | timing from cold launch | verdict |
|------|--------------------|-----------------------------------------------------|--------------------------|---------|
| cold open | map, no spinner theatre | welcome film → onboarding (fresh install); first frame **+450/+481/+518 ms** across 3 cold runs; ambient hero settled **+2.75 s** | ~0.5 s / ~2.8 s | **works-as-scripted** (claim "+452 ms first frame" ✓, "~3 s ambient" ✓) |
| ~5–15 s | consent, flip on camera | consent choices render ("keep on this phone only" / "share anonymous trips"), persist across restarts; **notification-permission dialog appears BEFORE location permission** — the flow's first system prompt is notifs, not GPS (shots 01b, 04–05) | ~6 s of onboarding | **works-as-scripted** (order note: film beat's "notif permission" moment happens at onboarding, not at the depart row) |
| ~15–30 s | sparse hero "0 of 3 samples" | hero shows "0 of 3 samples" meter + band-dot arc + "today's air ~N" (shot 06) | within ~15 s | **works-as-scripted** |
| ~3 s | first real ambient number | ambient read settled at +2.75 s | ~3 s ✓ | works-as-scripted |
| ~30–90 s | three taps → compare | per the 90 s rule the timed run's sheet tap went at ~92 s (one eaten tap at ~90 s — retried); the separate **in-window probe at ~38 s survived** with zero crash lines → the taps themselves are safe on Android | taps ≈3–10 s each | **works-as-scripted on Android** (eaten-tap once — stage note: press deliberately) |
| judge's dose-gap read | "Car AC ≈10 vs On foot ≈355 — about 36×" | screen reads **≈10 vs ≈333 — 34.3×** on the demo OD (22 rows) | — | **works-as-scripted** (script's ≈355/36× → ≈333/34× today — inside "about") |

## 3 · The 90-second window audit

**The rule** (`docs/lanes/testday-ios-report.md` §9): cold launch →
search-sheet tap inside ~10–90 s → mount-vs-draw SIGSEGV on iOS sim
(4 verified crashes).

**Verdict this pass — Android SAFE, verified:** the in-window probe
(tap at ~38 s from cold, ~60 s of sheet use incl. a suggestion → plan
ladder) survived with an identical pid and a **zero-line** fatal/ANR/
signal oracle over the whole session. On the Android demo build the
documented judge flow ("~30–90 s — three taps") is safe as written.

**Still true as a doc gap (P2):** neither doc states the ≥90 s
constraint. If the demo ever runs on an iOS build the documented flow
walks straight into the verified band. One line in both docs —
*"app opened ≥90 s before the first sheet tap; never hand over a
cold-launched app"* — costs nothing and covers the iOS case until the
fix-sigsegv lane lands.

## 4 · Number-by-number drift log (script verbatim → wire `aee635eb`, ~09:00–09:45 IST)

| scripted figure | wire/screen today | verdict |
|---|---|---|
| "US AQI around 160" | **152–157** across the hour | ✓ inside "around" |
| "fifty-four live instruments" | **53** (waqi+dpcc); `/admin` tiles say **51** | ✓ in the 52–54 band (verify_numbers accepts the range; the admin/health ±2 skew is cosmetic aging) |
| "about sixty-five NASA fire detections" | **80** (20 belt, 42.1 MW) | ✓ "about" strained — say "about eighty" or re-pin |
| smoke modifier ×1.24 / fires "carrying" | **1.1 — REFUSED** (easterly 104–108°) | **FLIPPED BACK** — T-45 `curl /v2/why` decides the day's aside |
| CP pm2.5 68.9/63.8 | **63.1 / 57.3** | ✓ |
| "about twenty options" | **22 on screen** (23 on CP→GGN) | ✓ |
| walk ~293 (script OD) / ~355 (demo OD) | **418.2 / ~333 on screen** (route-basis diff: app ladder 333 vs wire 321.6–420.5 by OD point) | ⚠ drifted — quote wire |
| "sealed AC car at about nine" | **≈10–11.4** | ⚠ "about nine" → "about ten" |
| "auto about twenty-six" | **≈29–37** | ⚠ drifted |
| "metro+walk about thirty-eight" | **≈62–64 on the demo OD; absent on CP→GGN** | ⚠ present on the OD the judge drives; re-pin the number |
| "~30× / 36× spread" | **34.3× on screen** | ✓ |
| depart "now ~21 · worst ~113@2.5d · best ~16" | app 24 h: now ~30.7→best 26.8@+8 h/worst ~55; `?hours=120`: worst 137.4@+60 h | **P1 — the 113/5× is outside the app's rendered window** |
| depart "leave later" row | **flickers at the `>8` gate**: served `ug_saved_vs_now` 13 earlier (rendered "breathe ~13% less"), **8 at capture → suppressed** | ⚠ boundary-sensitive — if the row is gone at T-45 the "remind me" affordance is too |
| **`ug_saved_vs_now` unit bug (notification path)** | wire serves **percent** (13; `pct_less_vs_now` identical); `CompareSheet` uses it right, but `useShellFlow.remind` (`Mobile/src/components/shell/useShellFlow.ts:436–441`) treats it as **µg** and recomputes `saved/(best.dose+saved)` → scheduled notification claims **~32 % less** vs true **13 %** | **real shipped-path bug** — ~2.5× overstatement inside the notification copy; not stage-visible (fires +8 h later) but a claims-audit violation → fix-lane material |
| "Fourteen contributors ~5 km ~400 µg ~700 all-time" | **22 contributors · 8.0 km today · 62.5 µg/24 h · 1,028.5 all-time · obs 40/1-today** | ⚠ re-pin all four figures |
| strip "~52→~86 · 82 samples @250 m" | **45.3→73.9 · 90 samples @250.0** | ✓ shape holds |
| "95.2 % @2σ / 3,550 h / 85 stations" | unchanged validation artifact | ✓ |
| "10 species, ammonia empty" | 9 species + pm25 live, **nh3 null** (app species row agrees) | ✓ |
| "r=+0.34" | stale (was +0.55 Oct-6 — drifts) | ⚠ phrase "well under one" |
| "edges 1.07M / 903k priced" | 1,070,459 / 903,058 — admin tile prints "9,03,058" | ✓ exact |
| transit real feeds | metro `true` + bus `true` | ✓ |
| film line "leave 12:30 — 83 % less" | today's row: "~13 % less" | **flag — impossible today** |
| cold-open "2.5 cigarettes" | breath mid **818 µg ≈ 2.59 cigs**; landing hero says ≈2.7 | ✓ |
| "corridors publish at k≥3" | `min_k` 3, 12/55 publishable | ✓ |
| Mumbai honesty | typed → gazetteer local-only (NCR-scoped corpus, no fabricated route); map-pick outside → "**this trip sits outside Delhi NCR — this trip leaves the field, so its dose can't be priced honestly**" | ✓ verified on-screen |
| edge coverage | pick ~40 km E → "route leaves the priced field — dose is honest for the mapped segment" + "least smoky picks unavailable — showing what's live"; bbox ≈ lon 76.85–77.75 × lat 28.25–28.85 | ✓ verified on-screen |
| AWS "$46/mo, 1/1 Spot" | unverifiable this lane | pending T-45 CLI |

## 5 · Fallback-surface audit ("if live breaks") — all verified on the release APK

| contingency promised | exists? | evidence |
|---|---|---|
| `docs/video/cut1.mp4` + `cut2.mp4` on the phone | **YES** | in-repo, valid mp4, **161 s / 157 s** (ffprobe); runbook T-60 says copy to the device — verify on-device at T-60 |
| `degraded:[arms]` honesty line | **YES — latent** | `/health` shows no `degraded` field today (all arms up); the surface + wording verified on earlier passes |
| `field_stale:true` → read the real age | **YES — latent** | `field_stale:false`, `field_age_s` live on the wire |
| planner timeout → `options:[] + error` | **YES — documented** | earlier passes measured the 20 s budget → honest empty |
| **airplane-mode surfaces** | **YES — all driven** | offline search answers (bundled gazetteer); new plan → "can't reach the server — trying again" + "couldn't load the ways there" + try again; Delhi Today → "offline — showing last known air · updated 10 min ago"; **offline nav completes to arrival** on the cached strip with receipt "≈0.7 µg · 132.2× · **saved — will send when back online**" + outbox "1 saved to send" (shots 51–56) |
| reconnect recovery | **YES** | offline pill cleared **+4.7 s** after airplane off; queued donation **flushed ~+35 s** lazy (piggybacks next request) — inside the demo window |
| outside-NCR honesty | **YES** | map-pick + typed paths verified (§4) |
| hall Wi-Fi → phone hotspot | physical | NLB HTTP :80; captive portals break it — hotspot per runbook |

## 6 · Notification-beat feasibility (task item 7)

**The stage script has no notification beat.** The only alert in the
docs is the *film* beat (`docs/11-demo-script.md` 2:05–2:35): depart
"remind me" → permission prompt → Ambient Mode. What the drive found:

- The permission dialog itself appears at **onboarding** (before
  location), so the film's "tap remind me → prompt" ordering is already
  different on the real build — a judge-facing improv must expect the
  prompt to be **already granted** on a rehearsed device.
- The depart "remind me" affordance rides the leave-later row → gated
  at `ug_saved_vs_now > 8` — **boundary-flickering today** (13 at one
  read, 8 at capture). Don't plan around it without a T-45 re-check.
- If a *live air banner* is improvised: today `drivers[0]=stagnation`
  (score 1.0 — the stagnation kind exists and is primary); band pings
  need pm25 ≥ 90 (today ~55–75 — won't fire); fires refused. A
  stagnation banner is **plausible but not guaranteed** (≤10 min poll,
  needs alerts on + baseline already set; first read is silent).
  **Verdict: don't script a live banner; the deterministic version is
  the permission/settings surface, which rendered correctly (master +
  3 kind toggles persist to settings.json — shots 38–40).**
- ⚠ **Upstream churn**: `eeadec9`/`2043f82` (notify-v2) rewired the
  events engine *after* the tested build — whatever the rebuilt APK
  shows for notifications is new code; re-smoke on the final build.

## 7 · Risk list — what could go wrong live

| # | risk | severity | mitigation |
|---|------|----------|------------|
| R1 | **APK staleness**: tested build is 19 Mobile commits old; notify-v2, safefile, route-tint, nav-camera all landed since | **P0 for the stage build** — not the script | re-cut at final HEAD; re-smoke cold-launch→sheet→compare→depart→notifications on the new binary (the cheapest re-run is re-driving the §2 flow) |
| R2 | depart "5×/~113" can't render inside the app's 24 h curve (today ≈13–55 µg) | **P1 script** | re-word to the visible curve, or keep the long-horizon claim verbal-only |
| R3 | "car beats metro" stalls if the chosen OD lacks a metro row | **P1 script** | demo on the search-resolved OD (metro+walk 62.4 present today); T-45 re-check — it's GTFS-service-hours-dependent |
| R4 | plan wait ~11 s wall on a fresh/unwarmed OD vs "under two seconds" | **P1 ops** | `warm_task.py` T-40 + T-15 pass on the same OD keeps it warm (~0.1–0.7 s server); contingency line (>4 s → wait ~12 s once) already scripted |
| R5 | leave-later row boundary-flickers (`ug_saved_vs_now` 8 vs gate >8 at capture) — takes "remind me" with it | **P2** | if absent at T-45, drop that clause of the beat (curve still draws) |
| R6 | fires aside needs the day's wind — refused ×1.1 today | **P2** | T-45 `curl /v2/why` |
| R7 | drifted absolutes (walk ~333–420, car-AC ~10–11, fires 80, contributors 22, avoided 1,028, instruments 53) | **P2** | numbers-sheet re-pin at T-45; verbatim phrasing survives ranges |
| R8 | AWS console beat unverifiable uncredentialed | **P2** | T-45 CLI understudy from a credentialed box |
| R9 | "remind me" notification copy overstates ~2.5× (percent treated as µg) | **P2 code** — off-stage | fix-lane; harmless tonight only because the scheduled fire is +8 h out |
| R10 | live air banner can't be guaranteed | **P3** | don't script one; stagnation is the only fireable kind today |
| R11 | judge-flow still sits inside the iOS crash window **if** an iOS build is ever used | **P3 for Android / P0 for iOS** | Android verified safe (probe + zero-line oracle); iOS unchanged until fix-sigsegv lands |
| R12 | cosmetic: admin shows 51 instruments vs /health 53; `/community` unfurls raw JSON to `Accept:*/*`; first taps occasionally eaten (~90 s tap, sheet-settle taps) | **P3** | press deliberately; known web P2s |

## 8 · Evidence index

- **Child drive:** `docs/lanes/demo-rehearsal-evidence.md` +
  `docs/lanes/demo-rehearsal-shots/` (**74 screenshots**, numbered in
  beat order — welcome/consent/hero/ladder/depart/why/nav/receipt/
  trips/DelhiToday/settings/offline/web surfaces).
- **Crash oracle:** logcat grep — zero FATAL/ANR/SIGSEGV/SIGABRT lines
  for `com.anonymous.app` across the whole session.
- **Live-prod JSONs** (this box, `~/rehearsal/`): health, /aqi@CP,
  /v2/why, /v2/city, /community, /v2/skill, /v2/city/moves, /v2/day,
  /depart 24 h + 120 h, /v2/plan CP→GGN + IG→HCC + IG→HUDA-station,
  /v2/strip (minted `6dd79dc0e5b5` / `b3316e79d6a2`), /v2/archive,
  /grid, /v2/reach.
- **Web beats on-phone:** shots 57–66 (emulator Chrome, 390 px);
  cross-check `docs/lanes/web-drive-report.md` (same build).

*Probe discipline honoured: GETs + POST /v2/plan + POST /v2/reroute
only; no app/server code touched; this report + the shots dir are the
lane's only repo writes.*
