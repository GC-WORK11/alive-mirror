# Lane report: apk-final — THE demo binary (vibe + coldread + all fixes)

**Date:** 2026-10-06 · **Verdict: PASS (14/14)** · Drive: Linux/KVM Pixel_7 emulator child ([session](https://app.devin.ai/sessions/28d29d6dea584b63bfa9764d9bb9633a))

## APK

- **URL:** https://app.devin.ai/attachments/3dfb52d6-0ce4-4eab-a2f1-f830e8b85754/alive108-0b11123.apk
- **SHA:** `0b11123` (base/v2 HEAD at drive time). Built from source tree `a77c3c3`; the three intervening commits (`2af1219`, `b19e362`, `0b11123`) are docs-only — verified zero diff to `Mobile/`, `server/`, `Bridge/`, so this is the HEAD binary.
- **Carries:** vibe-polish `9b3abe4` (solid content panes, numeral hierarchy, label qualifiers, receipt weight) + coldread-home `7facc34` (Delhiite-English copy pass) + all shipped fixes through HEAD (incl. `3711ccd` arrival gate, `0fdd597` dedupe/`/v2/trip` floor, `83d47de` GRAP-equivalent surface).
- **Build:** macOS box, `EXPO_PUBLIC_API_URL=http://65.2.28.40 ./gradlew assembleRelease -x lint` (5m20s) → 131MB, 4 ABIs (arm64-v8a, armeabi-v7a, x86, x86_64), debug-signed, `usesCleartextTraffic=true`.
- **Bundle verified** (grep on `index.android.bundle`): `65.2.28.40` baked; coldread strings present — "least smoky way", "µg (micrograms)", "counted", "about", दिल्ली (73×), घं (12×). Non-ASCII strings verified in the UTF-16LE Hermes string table (ASCII grep alone misses them). Retired jargon "least-smoke"/"accounted" absent.
- Supersedes `alive108-0a26f5a.apk` (v5 drive build — predates vibe-polish and coldread).

## Surface × verdict

| Surface | Verdict | Evidence |
|---|---|---|
| Cold-install → onboarding → consent OFF (persisted: `settings.json` share:false, `consent.json` sharing:"off") | PASS | [01](https://app.devin.ai/attachments/0ee6f378-d1ae-4808-a6c9-a65a8c22c302/01-onboarding.png)–[04](https://app.devin.ai/attachments/0ba12789-bcdb-4fd0-849b-80f4c87f714a/04-after-consent.png) |
| Sparse hero (band-dot arc, "today's air", "1 of 3 samples" meter, no fake counts) | PASS | [05-hero-sparse.png](https://app.devin.ai/attachments/8e613c5d-16a3-442f-9af0-f4cc05244e86/05-hero-sparse.png) |
| **Vibe:** Trips/Settings/DelhiToday panes solid — zero map ghosting | PASS | [13-trips](https://app.devin.ai/attachments/1a242e70-428a-4649-b9f8-e9c648c20330/13-trips-pane.png) · [08-settings](https://app.devin.ai/attachments/1723f90c-f15c-4c2d-abc3-f2f148b9f1e8/08-settings-pane.png) · [07-delhitoday](https://app.devin.ai/attachments/72eee652-6c71-4e6a-8793-0f264bf2ff08/07-delhitoday-pane.png)+[06-sidebar](https://app.devin.ai/attachments/922b8047-d608-4170-b02b-be6b42e1d9e3/06-sidebar.png) — parent visually re-verified: clean `bg` sheets, no phantom map/labels |
| **Vibe:** days-ahead numerals full ink | PASS | [45-en-home](https://app.devin.ai/attachments/3e47c9a0-487f-4baa-ad04-8c1d22bd6e0b/45-en-home.png), [35-hero-rows](https://app.devin.ai/attachments/54ee4c29-cffb-4a8c-935a-94ede35f5def/35-hero-rows.png) — numerals own their cells in ink, band reads via wash/dot |
| **Vibe:** ledger dose hero ~30px | PASS | [39-ledger.png](https://app.devin.ai/attachments/cb224d4a-c4e5-4cd1-8306-566887000b8f/39-ledger.png) — "≈ 3 µg breathed" dominates trip-count/kg stats |
| Search → plan → compare (Connaught Place → India Gate) | PASS | [15](https://app.devin.ai/attachments/4a6f3f2f-a308-46d1-ae3f-4ee9e60e0ab2/15-search.png)–[17](https://app.devin.ai/attachments/0b382795-f499-4f43-bf2a-cf070ded0c73/17-plan-sheet.png), [21](https://app.devin.ai/attachments/233642b9-7880-43b9-be49-b941bee9b0c6/21-compare.png)–[26](https://app.devin.ai/attachments/011ce6d9-6d65-4072-aedb-cde4e8c91f99/26-all-cards.png) |
| Non-recommended pick nav (Car windows down over recommended Car AC) | PASS | [27-picked](https://app.devin.ai/attachments/f9513d1f-1d9d-488f-b81d-07312ef9c11f/27-picked.png), [28-nav-start](https://app.devin.ai/attachments/ae6ba712-db88-4366-af99-16953c630a76/28-nav-start.png), [30-nav-mid](https://app.devin.ai/attachments/8df4bb1f-84ae-479c-937e-fa24ad5f04df/30-nav-mid.png) |
| Arrival receipt — "about" not "est." | PASS | [31-nav-end.png](https://app.devin.ai/attachments/2b2930b9-f86e-43c6-85a4-376bba9eedf4/31-nav-end.png) — "≈ 3 µg about 2.2–3.7 µg", "26.5× less than by On foot · least smoky option 2", 4.2 km / 4 min / ≈0.3 kg, "estimated — for vehicles like yours", "kept on this phone only" |
| **Coldread:** "µg (micrograms)" first-use gloss | PASS | hero + DayPeek (also in recording t+6); hi renders "µg (माइक्रोग्राम)" |
| **Coldread:** "least smoky way" (not "least-smoke rd") | PASS | receipt "least smoky option 2"; ledger "less than the smokiest way" |
| **Coldread:** "counted" (not "accounted") | PASS | "2h 9m counted" hero; "0h 41m counted" populated; hi "0घं 32मि गिने" |
| **Coldread:** hi दिल्ली/घं (not DELHI/+Nh), zero tofu | PASS | [42-hi-hero](https://app.devin.ai/attachments/892164d7-9570-4521-9ae3-f550c3459dbc/42-hi-hero.png) — "मंगलवार · 03:46 · दिल्ली", "+3घं…+15घं" ticks; [41-sidebar](https://app.devin.ai/attachments/758ce6ce-396b-454b-8054-e98124e177fd/41-hi-sidebar.png), [43-compare](https://app.devin.ai/attachments/217150c4-9c46-4413-9c5b-f894fe76d267/43-hi-compare.png) |
| Populated surfaces (hero % of ~216µg budget, hour rows, check-in → daylog.json "never uploaded") | PASS | [35](https://app.devin.ai/attachments/54ee4c29-cffb-4a8c-935a-94ede35f5def/35-hero-rows.png), [36](https://app.devin.ai/attachments/17be83ca-6f75-48e2-8838-9e32ca68a137/36-home-checkin.png)–[38](https://app.devin.ai/attachments/bba9f53a-06ea-4ab5-9948-7a0e3203a419/38-checkin.png), [45](https://app.devin.ai/attachments/3e47c9a0-487f-4baa-ad04-8c1d22bd6e0b/45-en-home.png) |
| Cold-open | **+452ms** | logcat `Displayed com.anonymous.app/.MainActivity: +452ms` (force-stop → relaunch); first live hero number ~3.5s on swiftshader — same class as v5's ~3.6s |
| Consent-OFF silent wire (pcap) | PASS | [apkfinal.pcap](https://app.devin.ai/attachments/6f68dc40-0d21-4006-a8ae-81a270eef6ec/apkfinal.pcap) — capture ran before install → after all drives: POSTs only `/v2/plan` (125) + `/v2/reroute` (4). **Zero** `/v2/trip`, `/observe`, `/report`; zero PUT/DELETE/PATCH. GETs only otherwise (/health, /reports, /aqi, /v2/day, /v2/outlook, /v2/search, /v2/strip, /depart). The v5 0-km probe was not re-fired. |

## Recording

- **[apkfinal-r2.mp4](https://app.devin.ai/attachments/2773b36c-c891-4b63-9631-03921232d04b/apkfinal-r2.mp4) — 87s, the take.** Nav mount "Turn left 460m · 7 min · 4.4 km left" with live SMOKE YOU BREATHE counter → mid-nav dose accumulating (0 → ≈0.3 µg, ≈0.2 kg, countdown 4.4 → 1.5 km) → arrival receipt with real stats ("≈0.3 µg about · ≈0.2 kg put out · 4.1 km · 1 min · kept on this phone only") → Done → drawer → Trips ledger ("THIS WEEK 10 trips · ≈4.5µg", new row on top).
- First take: [apkfinal.mp4](https://app.devin.ai/attachments/5e886f84-21b6-4b68-8f76-5e9f81c3f701/apkfinal.mp4) — 90s, cold-open → hero (µg (micrograms) gloss visible) → search India Gate → plan → "Car (AC) · least smoky way" → nav → receipt → drawer → ledger. Its in-frame receipt shows degenerate stats (0 km/0 µg) — fixes were fed during the plan wait to land arrival in-frame; the app honestly reported the teleported drive rather than fabricating numbers. r2 supersedes it for demo use.

## Regressions vs v5 (11/11 PASS @ 0a26f5a)

**None.** Every v5 surface matches or improves at HEAD; no new defects observed.

## Notes (by-design behaviors)

- Plan fetch latency 30–50 s is inherent server behavior (seen off-recording too; v5 documented the same class).
- The first take's degenerate in-frame receipt was a fixture of feeding fixes during the plan wait — r2 re-shot with fixes paced during nav and shows real accumulation; 31-nav-end.png remains the sharpest still of a real driven receipt (≈3 µg / 4.2 km / 4 min).
- Re-take notes from the driver: typed search leaves the soft keyboard over the compare sheet — taps hit the IME, not Start; dismiss with `keyevent 4` first.
- 46 unique screenshots + pcap + mp4 attached to the drive session (exact-duplicate PNGs deduped).

## Rules kept

Live API `http://65.2.28.40`: GETs + `POST /v2/plan` + `POST /v2/reroute` only; consent/share OFF in-app the whole drive. No app code changes — zero smoke defects. Never deployed; no AWS calls.
