# Lane report: testday-offline — degrade-honesty drive on Android emulator

**Date:** 2026-10-07 · **Verdict: 8/8 honesty checks PASS — zero "looks fresh but isn't" violations found**
Rig: `demo` AVD (pixel_7, android-35 google_apis **x86_64**, KVM, `-gpu swiftshader_indirect -no-window`, 2048 MB). Geo via `cmd location providers` fused+gps dual inject (test providers registered first — `add-test-provider` + `set-test-provider-enabled` needed on this image).
Prod anchor (drive start): `GET /health` → `build_sha aee635eb`, stations 52 (waqi+dpcc both ok), `field_age_s 341`, `field_stale false`, wind known 5.8 km/h, fires 80. **GET-only rule kept; the only POSTs observed were app-initiated `/v2/plan` (compare), `/v2/reroute`, and the consented outbox `/v2/trip` flush.**

## Binaries

| artifact | sha256 | built at | used for |
|---|---|---|---|
| coordinator APK (c3bb731) | `a022d9d1…fa4c7` (137,054,180 B) | c3bb731, ELB hostname baked | installed first, superseded mid-baseline by coordinator direction — no findings recorded on it |
| **matrix APK (this drive)** | `6cad0011…6847b` (137,084,952 B) | **39bae99** — contains c674705 outbox guard, c84b5c2 phantom-replan/exhaust, 1afccd8 disclosure, 832e7fa i18n; prod IP alias `65.2.28.40` baked | the whole matrix below |

Between 39bae99 and drive-time HEAD (`aee635e`), `Mobile/` changed only in `3a71549` (community wire field names), `0a68601` (search distKm inline-require guard), `d45a55c` (sim mount-vs-draw throttle) — **none touch offline/freshness/outbox/strip paths, so every finding here stands against HEAD**.

## Evidence map

Shots: `docs/lanes/testday-offline-shots/NN-*.png` (30 files, numbering matches rows below). logcat `~/drive/logcat-all.log` on the box — zero FATAL/ANR/ReactNativeJS errors across the whole drive.

## Results by brief item

| # | Check | Result | Key evidence |
|---|---|---|---|
| 1 | ONLINE baseline | PASS | 03–07: home live "67 µg/m³ · moderate · 4.5× WHO", BandScale pos 3/6, "air reading: 9 min old" (= server field age — ticks honestly), week strip ≈0.8 µg, 5-day forecast (today 74 least-bad vs ~129), DelhiToday 824 µg + "updated 10 min ago" + pollutant table, air map "10 min — live stations + satellite estimate" chip |
| 2 | Warm offline on home (~90s+) | PASS | 09: pill lands ~T+20s "can't reach the server — trying again" (apiOk = /health 15s ×2 misses, App.tsx:348-358). Hero keeps last-known 67 µg/m³ **under the pill** — marked, not fake-fresh. 10: age text ticks 9→11 min. Week strip / day arc / forecast keep last data under the same marker. No spinner anywhere |
| 3 | Cold-open offline | PASS | 16: cached relaunch → restores 67 µg/m³ + "offline — showing last known air · updated 5 min ago" immediately. 17: `pm clear` first-launch-no-net → "waiting for the first air reading today" + pill; no zeros, no confident blanks. 18: **welcome film offline shows its type-only frame — "no live air reading right now · nothing served — never faked"** (the ambientUg-null contract, WelcomeScreen.tsx) — best line in the whole build |
| 4 | Mid-trip offline | PASS | Airplane ON between armed compare and Start (the rubric edge case): 21 nav runs offline with pill, dose accrues **≈0.3→0.4 µg on the cached strip** (fetchStrip = fetchCached 15-min TTL, strip.ts) — **not the feared strip-null ≈0 fake**. 23: arrival receipt "You breathed ≈0.4 µg about · saved — will send when back online" + pill "· 1 saved to send". Honest, not stale-as-fresh |
| 5 | Intermittent | PASS | Pill cleared **<4 s** after airplane-off (beats the 20–30 s probe prediction — the up-event arrives via request outcomes/`probe()`, no NetInfo). 26: fresh numbers painted within ~1 poll cycle (outside 67→49, forecast updated); no stale-as-fresh frame in between |
| 6 | Offline + हिंदी | PASS | 28: pill "सर्वर से संपर्क नहीं — फिर कोशिश हो रही है"; age "हवा की रीडिंग: 1 मिनट पुरानी"; stale variant "ऑफ़लाइन — पिछली ज्ञात हवा दिख रही है · 2 मिनट पहले अपडेट हुआ"; DelhiToday fail state "फिर कोशिश करें" (29). **Zero English leaks observed** — i18n parity holds on every degrade string |
| 7 | Outbox honesty | PASS | Receipt said "saved — will send when back online" (no fake success). `outbox.json` held the full donation (trajectory, `dose_ug 0.4`, `dropped:0`). Airplane-off → **flushed to `items:[]` within ~15 s** (wireAutoFlush on up-event), lands-once |
| 8 | Kill-app offline | PASS | 30: force-stop + relaunch offline restores dose 4.9 µg + trips under the stale pill; hero shows local dose but the "outside" line is withheld rather than stale-shown |

## Supporting observations (not violations)

- **Offline search = bundled gazetteer** (`search/t0.ts`, T0 tier): "India Gate" returned real local results with distances while fully offline (14). Honest — real rows, "a miss rather than a fabricated place" by design.
- **Plan while fully offline fails honestly** (15): "couldn't load the ways there — check the connection / try again" — no fake options, no spinner.
- **DelhiToday has two honest offline states**: cache present → serves data + "older data — reconnecting" (11, English pass, cache from baseline); no cache (post-`pm clear`) → empty sheet + retry (29, Hindi pass). Neither fabricates.
- **Pill state machine verified live**: `offline` ("can't reach the server — trying again") → `stale` ("offline — showing last known air · updated N min ago") once a fetchCached surface serves cache (13) → `offline` + "· N saved to send" while donations pend (23).
- **Outbox trajectory kept 2 points** (the tail fixes) — privacy-favorable trim, consistent with the 300 m end-drop story.
- **c84b5c2 phantom-replan holds**: Done → populated home, no dest→dest re-plan (24).
- **Ledger honest**: "1 trip · ≈0.4 µg · estimates, honestly ranged" (25).

## Findings

| # | What | Severity | Evidence |
|---|---|---|---|
| 1 | Receipt exhaust rounds small mids to bare "**0 kg** put out" on a 4.2 km car trip (outbox `co2_kg_mid 0.04`, `pm25_g_mid 0.132`; receipt still says "incl. 0.13 g of fine dust" + "estimated — for vehicles like yours"). Partly test-feed artifact (teleported fixes ≈226 km/h derived speed), but a real user would also see "0 kg" for a sub-0.05 kg estimate — a "<0.1 kg" floor would read truer than a zero. | nit | 23, outbox.json |
| 2 | Map-screen freshness chip froze at "10 min — live stations + satellite estimate" for the whole offline window (12, 15). It reports the *served* field's age — factually true and the pill marks the connection — but the word "live" over frozen data is the weakest honest label on the build. | nit | 12, 15, 16 |
| 3 | Eaten taps persist — "Where to?" home row, search results rows, compare CTAs each needed a re-tap or 2-px micro-swipe (same emulator-flake pattern as prior lanes; no dead affordance found). | nit | drive log |
| 4 | `air reading: N min old` measures **server field age**, not fetch recency — it kept ticking honestly while offline (9→11) and reset only when the server regenerated (~15-min cadence). Correct but easy to misread as fetch freshness; flagged so demo-narration describes it right. | nit | 10, 26 |

## Findings touching post-binary code — none

`git log 39bae99..aee635e -- Mobile/` = `3a71549`, `0a68601`, `d45a55c`: community wire-field rename, search distKm guard, sim draw throttle. None intersects offline/pill/strip/outbox/i18n paths exercised here. The four commits the coordinator flagged (`c674705`, `c84b5c2`, `1afccd8`, `832e7fa`) are **inside** the tested binary — outbox guard verified live (flush lands-once), phantom-replan verified absent, disclosure line verified rendered, zero i18n leaks found on degrade strings.

## Rules kept

GET-only on prod plus the app's own `/v2/plan`, `/v2/reroute`, and consented `/v2/trip` outbox flush. No product code touched — this lane wrote only this report + `testday-offline-shots/`. No deploys, no AWS calls.
