# Android drive — base/v2 on emulator (design-v4 pass)

- Repo `<owner>/Delhi-Air-108`, branch `base/v2` @ `c5762e8` (contains 31dbfdb design-v4 pass-2 + 823323e neutral ledger glyphs).
- Build: `Mobile/android` release APK (`app-release.apk`, 137 MB, 4-ABI, debug-signed), `EXPO_PUBLIC_API_URL=http://65.2.28.40` baked into the JS bundle (verified by grepping the bundle — port 80 only).
- Rig: `demo` AVD (pixel_7, android-35 google_apis x86_64), KVM, `-gpu swiftshader_indirect -no-window`, 1536 MB RAM. Geo via `cmd location providers set-test-provider-location` on fused+gps (dual inject — reaches both the app's fused watch and nav GNSS).
- API discipline: only GETs + `POST /v2/plan` + `POST /v2/reroute` observed/made. **No /v2/feedback, /observe, /v2/trip POST was ever sent by me.** /health → 200, build_sha ce01ec5c.
- Shots: `docs/lanes/android-drive-shots/NN-*.png` (76 files). Evidence also in `~/drive/logcat-all.log` + 3 pcaps on the box.

## Verdict

**build_ok, drive complete, no blockers.** Every feature on the list was exercised with real user gestures; two full nav trips completed to real arrival receipts; consent gate proven on the wire. Design-v4 holds: warm neutral base, band color only where it means air quality, felt words everywhere, English default. Two mediums (post-arrival degenerate re-plan, exhaust model is idle×time only) and one device-flagged high (no basemap labels render — suspected SwiftShader; verify on hardware) to chase.

## Feature results

| Feature | Result | Shots |
|---|---|---|
| Cold open → welcome film → home hero | Works. English default on fresh install (settings.json `lang:"en"` before any toggle). Consent prompt first, honest copy. | 01*, 02–05 |
| Where-to sheet | Search field + typing works (`input text` with %s spaces); results geo-ranked with distance; **recents work** — "India Gate, historic site" persisted and re-listed (49). | 07–10, 49, 50 |
| Plan options → compare sheet | Trip 1 (centroid→India Gate): multi-option compare, mode rail, "safest route"/"lightest for you" verdicts, leave-later chips, hour-arc. Trip 2 (India Gate→CP): car-only option set + leave-later strip. Vehicle pick flow (auto 2017–2020) remembered. | 11–17, 51 |
| Nav trip (geo feed) | Two real arrivals. T1 centroid→India Gate 4.3 km: instructions ("390 m Continue onto Radial Road 1"), pin tail <60 m → "You're here." receipt with breathed/put-out/leaving-earlier comparisons. T2 →Connaught Place: **live reroute fired twice** when I fed fixes off-path ("2 min · 1.3 km left" re-planned, `POST /v2/reroute` ×5 on pcap), then arrived on exact dest fixes. | 18–20, 52–54 |
| Arrival receipt | Numbers ranged ("≈1.7 µg about", "0.2–0.4 µg"), comparisons vs smokiest/least-smoky modes ("38.9× less than by On foot"), "kept on this phone only" under consent-off; Done returns home. | 21, 54 |
| Trips ledger | "2 trips · ≈2 µg · about 0.1 kg put out", 7-day bar (today highlighted), per-trip rows expand to detail ("smoke you breathed"/"put out", ranges, delete affordances). | 24–26, 56, 57 |
| Delhi today | City dose 865 µg moderate, WHO-referenced pollutant table (PM10/NO₂/O₃/CO/SO₂ + US AQI), next-12h strip, "46% below the 10-year average", honest narration. | 27–32, 58 |
| City/community | "streets travellers crossed" — real /reports streets (Punjab National Bank, hanuman lane, Fire Brigade Lane, Atul Grove Road, moti, Motilal Nehru Marg, Howrah–Delhi Railway…) with per-street trip counts + heavier/lighter tags; "what ALive travellers did today". | 59, 60 |
| Sidebar | Right-side `menu` node opens it (left hamburger dead once hero populated — known). Sections: trips/share/what-we-store/settings/how-it-works/delete; close X works (scrim node is a trap — tap the X). | 33–35 |
| Settings | Vehicle (auto·change), Language EN/हिंदी seg, Voice, Cig comparison (off by default — "your dose stays in µg"), Units km metric-only, Share-anonymous-trips, What we store (full honesty bullets: no account, 300 m end-drop, ~11 m rounding, counts-only grid, random id), notifications, About v1.0.0. | 41–45 |
| Language toggle | हिंदी renders fully (settings, hero, week initials, forecast). English restored cleanly, `lang:"en"` persists in settings.json. Fresh install defaults English. | 35–38, 74–76 |
| Day arc scrub | Scrubs both directions; readout updates ("≈≈ 12 µg · 1:00") over "hour 0"/"hour 1" track. | 72, 73 |
| Week card + days ahead | "your week" 7-chip strip (today ≈24 highlighted, past days faded = "past live readings — satellite estimate only"); "the days ahead" 5-day forecast (today 78 least-bad vs ~130 avg) — honest qualifiers. | 06, 71 |
| Air map + layers | Full-screen map + day-strip card ("your day so far ≈18", "now ~70 µg/m³", freshness dot — flipped 14 min→0 min on refetch). Layers sheet: fires / crash spots / commute-mapped streets. Blue AQ segments painted on streets. | 61–63 |
| Consent-off → no telemetry | `share:false` + `consent.json sharing:"off"` both written. Trip 2 arrived → receipt says "kept on this phone only", outbox.json stays `{"items":[],"dropped":0}`. Pcap across toggle+trip+2 reroutes: **zero** telemetry POSTs — only GETs (/health, /aqi, /reports, /v2/search, /v2/strip, /depart) + allowed `POST /v2/plan` ×2 and `POST /v2/reroute` ×7. | 46, 54 |
| Logcat | Zero FATAL/ANR/ReactNativeJS errors (748 app-tagged lines; only benign Firebase-not-configured + emulator HWUI/WebView warnings). | — |

## Errors found

| # | What | Where | Severity |
|---|---|---|---|
| 1 | **Basemap renders zero text labels at every zoom** — road names, place names, POI glyphs all absent on-device (61–69). mbgl-offline.db proves glyph ranges fetched (Noto Sans Regular/Bold/Italic, incl. Devanagari range); style+fonts verified; `latinLabels` wiring correct (App.tsx:72,140). Rendering the same EN style in maplibre-gl-js shows perfect Latin-only labels (70). So either a SwiftShader SDF-glyph quirk or a native label-pipeline bug in this build — **needs one physical-device check to classify.** | map surface, all zooms | high (if real) |
| 2 | **"Done" on the arrival receipt re-opens a degenerate dest→dest compare sheet** — after every arrival, dismissing the receipt pops the identical "4.31 km" plan sheet for the destination just reached (21→22, 54→55). Recoverable via sheet close, but every trip ends in a phantom re-plan. | compare sheet after Done | medium |
| 3 | **Exhaust metric is idle-rate×time, never distance** — receipts/ledger show ≈0.00 kg (trip 1) and ≈0.1 kg (trip 2) because test-provider fixes carry no GNSS speed; `counters.ts` integrates `rate·dt` where rate needs v (distance-only `travelledM` is never used for emissions). Part test artifact, part real model gap: a user genuinely stationary gets idle-only math but the ~25 g over 4 km of trip 1 still displays "0.00 kg". | receipt + trip detail | medium |
| 4 | **"≈≈ 12 µg" double tilde** on the arc-scrub readout (72). | home hero hour strip | low |
| 5 | **Intermittently eaten taps** — hero "go somewhere" CTA, map-chrome "Where to?" pill, map-layers FAB and some sidebar rows each needed a second tap or a 2-px micro-drag to register (repeatable pattern, possibly emulator touch flakiness, but consistent across surfaces). | home pill, map chrome, layers FAB, sidebar | low |
| 6 | Street-name casing inconsistent in community list — "hanuman lane", "moti" lowercase beside "Fire Brigade Lane", "Atul Grove Road". | Delhi today → streets | nit |
| 7 | Header "Where to?" map-chrome pill is dead once the hero is populated (same note as prior lane — flagged again because it reproduced on this build). | map chrome | nit |

## Design-v4 verification

- **Warm neutral base, band colors only for meaning** — verified across ~30 surfaces: cream/sand base, terracotta-amber for outside/forecast numbers, blue-teal for "your" dose, forest accent only as small state dots; no mauve/red-mix anywhere.
- **Neutral mode glyphs** — no colored icon wells; vehicle/layers/settings icons all neutral ink.
- **Felt words per CPCB band** — good / satisfactory / moderate / heavier / lighter / least-bad / lightest/heaviest all present next to numbers.
- **Latin-only map labels (EN)** — verified at style level: `App.tsx` applies `latinLabels()` (rewrites the 5 bilingual `name:hi` text-fields to `name:latin/name_en/name`) in EN mode, and the same EN style rendered in maplibre-gl-js shows all-Latin labels with zero Devanagari (70). On-device couldn't show it because of error #1 — flag for hardware.
- **English default** — fresh install boots English; हिंदी only via toggle.

## Notes for next lanes

- Arrival requires ≥2 consecutive fixes <60 m of the **plan's** dest (use `/depart` to_lat/to_lon or the receipt pin); sweeping guesses triggers live reroutes (which is itself a nice feature to watch).
- The exhaust counter needs speed-bearing fixes to show non-idle accumulation — `set-test-provider-location --location lat,lon` doesn't carry speed; compute-and-pass it if prod parity matters.
- `input text` wants `%s` for spaces; `keyevent 4` dismisses the keyboard (111=ESC exits the app).
- adb root works on this image; app files under `/data/data/com.anonymous.app/files/` are directly readable (settings.json, consent.json, outbox.json, alive-cache/*, mbgl-offline.db).

## v2 verify pass

Verification pass on the fix commits landed in response to this report — `c84b5c2` (phantom re-plan, ≈≈ readout, exhaust-without-GNSS-speed), `344b4a9` (Where-to? pill yields), `4d20990` (air alerts engine), `bc8f82c` (BandScale), `8346460` (air-events channel).

- Build: same rig, release APK rebuilt at **`base/v2` @ `39bae99`** (contains all five). `Mobile/android/app/build/outputs/apk/release/app-release.apk`, 137 MB — **this APK is the demo-morning artifact**. Bundle rebaked fresh (index.android.bundle rm'd first; `alerts_fires`/`bandScaleA11y` strings confirmed inside the new bundle).
- Fresh `adb install -r` on the same `demo` AVD.

| Verify item | Result | Shots |
|---|---|---|
| a. Post-Done phantom re-plan | **FIXED.** Full nav trip (central Delhi → Connaught Place, live reroute en route) → "You're here." receipt → Done lands on populated home, phase idle — **no compare sheet, no dest→dest re-plan.** | 95, 97, 98 |
| b. "≈≈" scrub readout | **FIXED.** Arc scrub now renders single tilde: "≈39 µg · 1:00". | 94 |
| c. Exhaust needs GNSS speed | **FIXED** (derived-speed path verified). `set-test-provider-location` still carries no speed channel — but `counters.ts` now derives v=ddM/dtS (cap 45 m/s) when `speedMps` is absent. Same speedless feed that printed 0.00/0.1 kg now shows **"put out ≈0.2 kg · incl. 0.28–0.38 g PM2.5" over 7.7 km** and the counter visibly accumulated mid-trip (0.1 kg at 1.6 km left). Note: `adb emu geo fix lon lat alt sats velocity_knots` exists, but its fixes never surfaced through fused on this AVD — GNSS-speed path still untested on the emulator (hardware check). | 96, 97 |
| d. Where-to? pill yields | **FIXED.** With the home sheet open the top map-chrome pill no longer renders — only the sheet's own "Where to?" search row (which answers taps — it opened the search sheet for this trip). Previously it sat painted but dead. | 80 |
| e. Air alerts (4d20990) | **WORKS.** Notification permission prompt on first launch (78). Settings → Notifications shows master "Air alerts" + "smoke & fires" / "air turning worse" / "clean windows" kind toggles; kind taps write settings.json instantly (`alerts_fires:false` observed), master off writes `alerts:false` and visually disables the three kind rows; no truncation at 1080px. Restored all-on after. | 78, 89, 90 |
| f. BandScale (bc8f82c) | **WORKS.** Six-segment good→severe strip renders under the hero on **home** (segment 2 solid at ~57 satisfactory) and on **Delhi today** (same anchor under "3.8× WHO"). Pure positional anchor, zero new words. Note: correctly gated on `airNowIdx != null` — it was absent while the box read "can't reach the server" (transient, cleared when geo moved into Delhi). | 83, 84, 98 |
| g. Basemap labels re-check | **STILL BLANK at street zoom** — two separate viewports (99, 102) show zero road/place/POI text. Could not reach a tile-zoom: no pinch on this rig (`input` is single-pointer; sendevent multi-touch on the virtio nodes doesn't reach the view; double-tap-hold-drag fell outside MapLibre's gesture window and only panned). Unchanged verdict: style/latinLabels verified correct and renders Latin-only in web maplibre-gl-js — **needs one physical device to classify**. | 99, 102 |
| h. APK artifact | `Mobile/android/app/build/outputs/apk/release/app-release.apk` built @ `39bae99` — attached to the session message as the demo build. | — |

### Original findings — status after this build

| # | Finding | Status |
|---|---|---|
| 1 | No basemap labels | **UNRESOLVED on emulator** — still zero labels at street zoom (99, 102); classification still needs hardware. |
| 2 | Phantom dest→dest re-plan after Done | **FIXED** (item a). |
| 3 | Exhaust = idle×time, no distance path | **FIXED** — derived speed from position deltas (item c). GNSS-speed path itself still unverifiable on emulator. |
| 4 | "≈≈" double tilde | **FIXED** (item b). |
| 5 | Intermittently eaten taps | UNVERIFIED — not formally re-tested; this trip's gestures (search, options, Start, Done, toggles, scrub) all registered, though several needed the usual re-tap/micro-swipe pattern earlier in the pass. |
| 6 | Community street casing | UNVERIFIED — community list not re-opened this pass. |
| 7 | Dead header Where-to? pill | **FIXED** by removal-under-sheet (item d). |
