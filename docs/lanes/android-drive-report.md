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
