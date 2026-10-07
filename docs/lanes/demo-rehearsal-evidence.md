# ALive-108 demo rehearsal — emulator lane evidence

Lane: emulator-drive (release APK on Android 15 emulator). Date: 2026-10-07 (UTC; IST = +5:30).
Build: `app-release.apk` @ `341126f` (base/v2 HEAD at build time), `EXPO_PUBLIC_API_URL=http://65.2.28.40`.
APK sha256: `066a2c0e06529c8820661bb2a502e75126c3bcca04fcded9a26507aa847feb5a`.
Bundle grep: `65.2.28.40` = 1 hit; `localhost`/`10.0.2.2` = 0 hits.
Rig: emulator `demo` (api-35 x86_64, SwiftShader, 1536 MB), adb root, geo via `cmd location providers`. Logcat → `~/logcat-all.log` since before first launch.
Screenshots: `docs/lanes/demo-rehearsal-shots/NN-*.png` (74 frames, numbered in beat order).
Method note: all taps via uiautomator-dump bounds where possible; pixel taps retried when eaten (noted below).

---

## Crash / ANR oracle — verbatim grep result (whole session log)

```
$ grep -cE "FATAL EXCEPTION|FATAL SIGNAL|ANR in com.anonymous.app|SIGSEGV|SIGABRT" logcat-all.log
0
$ grep -E "com.anonymous.app" logcat-all.log | grep -icE "fatal|anr|sigsegv|sigabrt|crash|died|killed"
0
```

Zero fatal/ANR/signal lines for `com.anonymous.app` for the ENTIRE session (all launches, nav feeds, offline cycles). The only `signal`/`died` lines in the log are emulator boot housekeeping (init sending signal 9 to vendor services; `Process com.google.android.* has died`). `Displayed` lines for the app were not emitted by ActivityTaskManager on this build — cold-launch timings below were measured by screen-settle observation instead.

**IN-WINDOW PROBE** (separate cold launch, after the timed run): force-stop → `am start` → wait ~30 s → tap "Where to?" at ~t+38 s → ~60 s of sheet use (typed `Connaught Place`, scrolled, a suggestion tap drove straight into the plan ladder, dismiss+reopen). Result: **SURVIVED** — same pid (11526) throughout, sheet mounted on first tap, plan rows rendered, zero crash lines. Verdict: **works-as-scripted** — the 30–90 s search tap is safe on Android in this build.

---

## Phase 0 — install state

| Beat | Timing | Shot | On-screen truth (uiautomator) | Verdict |
|---|---|---|---|---|
| Fresh-install boot → welcome film | film visible <2 s, auto-exits by ~4 s | 01, 01b | "welcome film" card; **notification-permission dialog appears BEFORE location permission** | works-as-scripted |
| Onboarding → consent | ~6 s through pages | 02–04c | consent choices "keep on this phone only" / "share anonymous trips"; flipped once, both render | works-as-scripted |
| Location permission | after notif | 05 | Android system dialog | works-as-scripted |
| Cold launch → ambient | first frame ~0.45–0.52 s (3 cold runs: +450/+481/+518 ms class); ambient hero settled **+2.75 s** (claim ~3 s ✓) | 06 | hero "0 of 3 samples", band arc, "today's air ~N" | works-as-scripted |
| 90-s rule | observed — no sheet taps until t≥90 s | — | first attempt at ~90 s was eaten once; second tap at ~92 s opened sheet | eaten-tap note |

## Phase 1 — the dose gap

| Beat | Timing | Shots | On-screen truth | Verdict |
|---|---|---|---|---|
| Search FROM=India Gate | suggestions instant from bundled gazetteer | 11 | gazetteer rows with areas | works-as-scripted |
| DEST=Huda City Centre | pick → engine rows ~3 s | 12–13 | engine-first rows appear | works-as-scripted |
| Plan call (fresh OD) | **options settled ~11 s** wall; server `took_ms` 5470 in cached envelope | 13–19 | 22-option ladder (below) | works-but-timing (fresh-OD ~11 s vs script's ~35 s window is fine) |
| Recents re-plan | options visible **+5.67 s** | — | cached plan reused | works-as-scripted |

### The ladder (22 options, verbatim, screen + disk-cache cross-checked; HCC dest 28.495771,77.085388)

| Option | dose µg [lo–hi] | vs lightest | km | min | notes |
|---|---|---|---|---|---|
| Car (AC) least-smoky | ≈10 [4–15] | recommended | 24.73 | 29 | "safest route · lightest for you" |
| Car least-smoke alt | ≈11 | +1 | | | |
| Car alt2 | ≈11 | +2 | | | |
| car-open | ≈18 | +8 | | | |
| Bike | ≈23 | +13 · 2.4× | | | |
| Bus | ≈25 | +16 · 2.6× | | | |
| Bike least-smoke | ≈27 | +17 · 2.7× | | | |
| Auto | ≈30 | +20 · 3.1× | | | |
| Auto LS | ≈32 | +22 · 3.3× | | | |
| Bike alt1 | ≈33 | +23 · 3.4× | | | |
| Auto alt1 | ≈35 | +25 · 3.6× | | | |
| Metro+walk | ≈64 [28–99] | +54 · 6.6× | | 90 | |
| Bus 47B→790 | ≈82 [37–127] | +72 · 8.4× | | 124 | |
| Bicycle | ≈148 [63–232] | +138 · 15.2× | | 99 | "lightest for Delhi" + "Lowest emissions… but you'd breathe more" |
| Bicycle LS | ≈144 | | | | |
| alt1 | ≈145 | | | | |
| alt2 | ≈160 [72–248] | +150 · 16.5× | | | |
| **On foot** | **≈333 [142–524]** | **+323 · 34.3×** | | 297 | smokiest-way anchor |
| On foot LS | ≈336 | | | | |

**Spread: car-AC ≈10 µg vs on-foot ≈333 µg — 34.3×.** Plan envelope on disk (`files/alive-cache/a8764c83-….json`, 239 KB): `field{source: waqi+dpcc-stations+open-meteo/cams, samples:101, station_readings:53, kriging:'on', engine:'alive_core', serving:'live'}`.

| Beat | Timing | Shot | On-screen truth | Verdict |
|---|---|---|---|---|
| Depart beat | graph draws instantly | 20 | curve ≈9 µg now → ≈15 at +23 h; callout "+7h · 11:00 ≈ 8 µg". **"leave later" row was SUPPRESSED in this run** — prod `/depart` was serving `ug_saved_vs_now:8` (percent) vs the client gate `>8` at the moment of capture; earlier in the day the row rendered "leave 09:00 → breathe ~13% less" | works-but-field-dependent (boundary value: served 8, gate >8) |
| Why/physics expander | instant | 21 | "smoke you breathe — ≈10 µg this trip (about 4–15)" · "confidence: high" · "smoke your ride puts out — 1.911–5.3757 kg CO2 · 0.0683–3.3017 g PM2.5" · "estimated for vehicles like yours (petrol car, Delhi fleet mix — BS-III–BS-VI)" · "air reading: 7 min old" · "the range is honest — it covers what the meters miss…" | works-as-scripted |
| NAV start → tracking | nav pill live; dose ticks | 22–26 | "N min · N km left · arrive HH:MM", dose counter ≈0.7→… µg, "Head out" instruction | works-as-scripted |
| Off-route → live reroute | teleport ~300 m → reroute fired in-flight | 27–28 | "finding a new way" pill; **proof: new strip written to disk at 04:18 with route_id b3316e79d6a2 ≠ plan's 998212082b88** (POST /v2/reroute) | works-as-scripted (verified via route_id swap + pill) |
| Arrival → receipt | "You're here." after ≥2 fixes <60 m | 29 | "≈4.2 µg about [range] · **79.5× less than on foot** · the smokiest way would have added ≈X µg · ≈Y kg put out · km · min" | works-as-scripted |
| Donate copy | — | 29 | footer "kept on this phone only" when share off | works-as-scripted |
| Done → home | instant | 30–31 | home lands clean; **no phantom re-plan** (bug confirmed FIXED) | works-as-scripted |
| Trips ledger | instant | 32–33 | "2 trips · ≈4.9 µg" 7-day bar; row expand shows km/min | works-as-scripted |
| Delhi Today | ~2 s via sidebar | 34–37 | breath hero; species row **NH3 honestly absent**; "±X% vs decade" = **−46% vs decade norm**; why-line "the air is barely moving — the day's pollution is sitting over the city"; community stats; corridors list | works-as-scripted |
| Settings → Notifications | instant | 38–40 | master "Air alerts" + three kinds (smoke & fires / air turning worse / clean windows); toggle writes `settings.json` immediately (verified on disk) | works-as-scripted |
| Typed honesty: Mumbai | instant | 41 | typed `Mumbai` → gazetteer has no India-outside-NCR entry → local results only; **no fabricated route, no crash** | works-as-scripted (see note) |
| Typed honesty: outside-NCR map pick | ~3 s | 43–45 | pick at 26.136,77.1503 → "**this trip sits outside Delhi NCR — alive-108 only measures the air inside Delhi NCR — this trip leaves the field, so its dose can't be priced honestly.**" + "change the trip" | works-as-scripted |
| Edge coverage pick | ~6 s | 46–50 | pick at 26.865,76.108 (near Alwar side) → "route leaves the priced field — dose is honest for the mapped segment, nothing claimed past it" + "least smoky picks unavailable right now — showing what's live" | works-as-scripted |

Coverage boundary mapped via sanctioned POST /v2/plan probes (GET/plan/reroute only, per lane rules): Alwar (27.0,76.0) plans 7 routes with `confidence:'low'` + basis "est. · dose covers the served segment only — route stops ~154 km short"; Neemrana ~38 km short; Gwalior/Kanpur/Bhopal/Udaipur/Mumbai → `{"code":"outside_service_area","error":"outside service area — dose field covers Delhi/NCR only"}`. Field bbox ≈ lon 76.85–77.75, lat 28.25–28.85.

Note on Mumbai beat: the app's destination search is the **bundled gazetteer only** (124,311 places, zero `outside_ncr` rows, no remote geocoder), so "Mumbai" never reaches the plan call — the honest-outside surface shows via the map-pick path, which is what the demo uses.

## Phase 2 — fallbacks (airplane mode)

| Beat | Timing | Shot | On-screen truth | Verdict |
|---|---|---|---|---|
| Airplane ON: search | instant | 51–52 | gazetteer answers fully offline | works-as-scripted |
| Airplane ON: new plan | ~3 s to honest-empty | 53 | "can't reach the server — trying again" + "**couldn't load the ways there — check the connection**" + "try again" | works-as-scripted |
| Airplane ON: Delhi Today | instant | 54 | "older data — reconnecting" + "offline — showing last known air · updated 10 min ago"; species/grid from cache | works-as-scripted |
| Offline nav → arrival | nav kept running on cached strip | 55 | arrival "You're here." at dest; receipt "≈0.7 µg · 132.2× less than on foot · ≈0.4 kg · 5.6 km · 2 min"; pill "**can't reach the server — trying again · 1 saved to send**"; footer "**saved — will send when back online**" | works-as-scripted |
| Airplane OFF: recovery | **pill cleared +4.7 s** on reconnect probe | 56 | outbox.json still held 1 item at +10 s; **drained to 0 items by ~+35 s** (flush piggybacks the next successful request — Delhi Today fetch) | works-but-timing (pill ≤5 s ✓; actual POST ~≤35 s lazy flush, still inside demo window) |

Note: outbox POST goes to `/v2/trip` — the app's own donation path, fired only when share=on; never a manual call.

## Web surfaces (emulator Chrome, phone viewport — judge-handable)

| Surface | Shot | On-screen truth | Verdict |
|---|---|---|---|
| `/` | 57–61 | hero "What did you breathe today? **60.3 µg/m³ PM2.5 · MODERATE** · a day of breathing today's field ≈ 2.7 cigarettes · LIVE FIELD MEAN · WORST ≈6.4 CIG · 22 µg/m³-DAY ≈ 1 CIG · rebuilt every 15 min from **53** instruments · ticker: 53 STATIONS LIVE · FIELD 15 MIN FRESH · MEDIAN 59 · WIND 9 KM/H · **903K EDGES PRICED**" + field lattice ("PM2.5 — THE FIELD, THIS HOUR · INSPECT/A→B · PM2.5/US AQI/PM10 · REFRESHED 04:28 · arrow keys select a cell") + "▶ WATCH THE DAY — scrub the next twelve hours · CAMS + stagnation model, confidence fades with horizon" | works-as-scripted |
| `/city` | 62–64 | "Delhi NCR air, right now. **61 µg/m³ · MODERATE · AQI 106** · across the map 29.6–89.6 · 29 districts live · easiest East Delhi 84 · heaviest South West Delhi 163 · WHY TONIGHT: the air is barely moving… · GRAP stage I — 'computed here, not the official caqm call' · district map tap-to-read · hours-ahead scrubber · WHERE CAN YOUR LUNGS GO? (walk rings)" | works-as-scripted |
| `/community` | 65 | "What Delhi breathed together — merged, never named. · We can't leak what we never take. · 01 cut on your phone (first/last 300 m trimmed on-device) · 02 merged, never filed (only merged counts at rest) · 03 three phones to appear (k≥3 in 3 days) · The ledger — running totals · street table (stretch/trips/phones/PM2.5-per-trip/main mode/CO₂ per 100 m — e.g. Outer Circle 28.630°N 77.220°E)" | works-as-scripted |
| `/admin` | 66 | public board — **no token prompt**: "UPDATED 10:15:11 AM IST · guest view — OPERATOR SIGN-IN UNLOCKS THE INTERNALS; EVERYTHING BELOW IS LIVE PUBLIC TRUTH · 61.4 µg/m³ MODERATE LIVE · LAST REBUILT 2 m ago · every ~15 m · INSTRUMENTS 51 live govt feeds · MAP POINTS 99 · STREETS PRICED 9,03,058 · FIRES 80 spotted · 20 in the belt · NEXT REBUILD in 13 m · ±16.7 µg/m³ the ± range stamped on every gap-filled read · GAP-FILL ON · ALIVE_CORE · priced of 10,70,459 streets" | works-as-scripted |

## Rig / drive notes for the parent

- Eaten taps: hero "Where to?" once at ~90 s; a couple of sheet taps during plan settle — retried once each, no mis-taps.
- Sheet overscroll can dismiss the compare sheet to home (and one over-Back exited to launcher); recovered by warm `am start` + recents re-plan (+5.67 s).
- Geo feed mechanics (hard-won on this rig): `adb shell` calls inside `while read` MUST end with `</dev/null` or they consume the route file; feed in foreground exec calls (nohup feeders get reaped); verify fixes with `dumpsys location | grep "last location"`; `adb root` first.
- Arrival needs ≥2 fixes <60 m of the planned destination OR the odometer reaching route end on-corridor; parking 230 m short did NOT fire arrival until fixes landed at the point.
- SwiftShader shows no basemap labels — rig quirk, not an app bug.
- `share:false` restored after the outbox beat (consent state back to "phone only").
- 74 screenshots in `docs/lanes/demo-rehearsal-shots/`.
