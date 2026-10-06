# Lane report: apk-populated — populated ("used phone") state @ 609a6ef

**Date:** 2026-10-06 · **Verdict: 13/13 PASS** · Drive: Linux/KVM Pixel_7 emulator child ([session](https://app.devin.ai/sessions/a3cac0aae0294f98b78013031290d29e))

## APK

- **URL:** https://app.devin.ai/attachments/d6f7b8ca-cb53-4bce-80c9-b4a050cb9124/alive108-609a6ef.apk — same binary as apk-drive-v4.
- **SHA:** `609a6ef` · 131MB, 4 ABIs, debug-signed, `EXPO_PUBLIC_API_URL=http://65.2.28.40`, `applicationId com.anonymous.app`.
- **Δ vs base/v2 HEAD (`ce1d48c`):** this APK predates `3711ccd` (off-corridor arrival-gating) and `0fdd597` (dedupe-removal / offline-pill). Surfaces asserted here are unaffected: the drive stayed strictly on-corridor so the missing arrival gate never mattered (2 distinct fixes ≤60m satisfied the old odometer path honestly), and the ambient-sample/hero/ledger surfaces asserted below run the same code paths the APK ships. Receipt component is byte-identical 609a6ef→HEAD — the copy asserted is shipped copy.

## Honest seed (nothing hand-edited)

- `daylog.json` at finish: **9 real /aqi reads** — 4 at the Delhi-field centroid (28.6139,77.209; the poll's documented fallback while last-known was null) + **5 route-position reads** along the driven corridor (28.6129,77.2295 → 28.5490,77.2523; amb 54.9→84.3 µg/m³) — the nav `watchPosition` GNSS feed populated last-known, so ambient samples accrued at real positions. THIN_SAMPLE_MIN=3 crossed honestly → sparse→counted flip observed live.
- `checkins`: `{"2026-10-06":{"breath":1}}` — breath→"meh" tapped on the HOW YOU FELT card.
- `ledger.json`: 1 trip written by `nav/engine.ts arrive()` — "Car (AC) · least-smoke alt 1", central Delhi→Nehru Place, 1.3µg (est 0.7–1.8), 0.6 kg, avoided 230.6µg.
- `consent.json`: `{"seen":true,"sharing":"off"}` set at onboarding, never touched.
- Vehicle profile (S8) answered honestly mid-plan: auto + "not sure" year — that's why options carry "for vehicles like yours" copy.
- pcap of the whole session: GETs + `POST /v2/plan` only. **Zero `/v2/trip`, `/observe`, `/report` POSTs.**

## Surface × verdict

| Surface | Verdict | Evidence |
|---|---|---|
| Counted hero + gauge | PASS | [hero-counted-frame.png](https://app.devin.ai/attachments/f68c47f9-4045-4007-8ba4-4770136ca520/hero-counted-frame.png) (recording @0:04) — "YOU'VE BREATHED TODAY ≈31 µg", gauge ring 14%, "of ~216µg daily", "0h52m accounted", "outside now ~84 µg/m³" band-dot. |
| Week dots | PASS | same frame — 7 dots, today filled at dose fraction, 6 honest empty rings, "≈ 31µg this week". |
| Day arc + trip mark | PASS | [home-scroll1.png](https://app.devin.ai/attachments/f037f80e-846a-4092-a5aa-2b09775f0505/home-scroll1.png) — covered-hour bars incl. trip-marked 01h, WHERE IT ACCUMULATED lists windows + "Car (AC) · least-smoke alt 1 · central Delh… ≈ 1.3µg". |
| Days Ahead | PASS | same shot — 5-day chips (today 109 "least-bad"), "avg ~109 vs ~128 µg/m³", honest faded-days caveat line. |
| Symptom check-in + lens | PASS | [bot2.png](https://app.devin.ai/attachments/380524bb-2a28-4869-85e2-e2aec4ae511c/bot2.png) — breath "meh" persisted-selected, "stays on this phone — never uploaded", early line "a few check-ins in — the pattern needs ~7 days" (the early state IS the pass). |
| Budget card | PASS | same shot — "185 µg left of 216 today" bar + general/sensitive/child chips + "a ceiling you set — not a medical line". |
| Ledger | PASS | [trips1.png](https://app.devin.ai/attachments/0cddbca1-525c-4bc3-83bb-668909bcdc02/trips1.png) — "1 trip · ≈1.3µg · ≈0.6 kg", LAST 7 DAYS strip w/ today bar, row "central Delhi → Nehru …" real names; [trip-detail.png](https://app.devin.ai/attachments/d15a5b95-2dc8-4738-b2e8-49f795bcc670/trip-detail.png) expands breathed/put-out bands. |
| Receipt copy | PASS | [receipt1.png](https://app.devin.ai/attachments/a2d258ec-a445-4af7-98c1-3d7881e2c90c/receipt1.png) — "You're here.", picked-option chip "Car (AC) · least-smoke al…", "You breathed ≈1.3 µg est. 0.7–1.8", "179.5× less than by On foot", "≈0.6 kg put out · 12.2 km distance · 3 min time", "kept on this phone only" (consent-OFF private line verbatim). |
| pick → Start (non-recommended) | PASS | [compare11.png](https://app.devin.ai/attachments/af3141aa-ee41-472a-a9ee-02d2b82f824e/compare11.png) picked "Car (AC) · least-smoke alt 1" (12.4km via Rajaji Marg; NOT the "lightest for you" recommended card); [nav1.png](https://app.devin.ai/attachments/a15e7732-da4b-4fc5-9b8a-0feeb06a7363/nav1.png) nav chrome "19 min · 12.4 km left" = the picked card's route, not the 12.07km recommendation. |
| Live nav drive | PASS | [nav3.png](https://app.devin.ai/attachments/f48f2367-6045-4438-a19f-58d329a626b0/nav3.png) — position dot on-corridor, ≈1.1µg breathed / ≈0.4 kg put-out counters ticking, "2.3 km left", arrival landed with 2 distinct fixes ≤60m. |
| DayPeek (map idle card) | PASS | [tour-map.png](https://app.devin.ai/attachments/92228f82-7e05-4b09-8244-2fdba969eb12/tour-map.png) — "YOUR DAY SO FAR ≈31 µg" + week dots + "now ~84 µg/m³" + freshness chip "11 min". |
| "how sure" confidence | PASS | hero-counted-frame.png/home-scroll1.png — THE MOVE card renders "confidence: low" (the compare cards carry dose bands; the confidence line lives on the move card in this build). |
| Consent-OFF silent | PASS | [plan-final.pcap](https://app.devin.ai/attachments/c9752e21-2556-4f8f-84c4-ac66f27c1b8b/plan-final.pcap) — full-session capture: GETs + POST /v2/plan only; donation gate never fired (`engine.ts` `shareEnabled` false). |
| 420dpi overflow | PASS | every populated card above — no clipped text, no overlapping numbers, gauge/dots/strip render whole at `wm density 420`. |

## Recording

- [pop.mp4](https://app.devin.ai/attachments/1e565f97-746a-4759-800b-d17007f0305e/pop.mp4) — 111s, one take: counted hero → THE MOVE → YOUR DAY → DAYS AHEAD → HOW YOU FELT (meh) → DAILY BUDGET → YOUR TRIPS ledger → map DayPeek.

## Notes (no defects)

- `adb emu geo fix` feeds GNSS only — the ambient poll's `getLastKnownPositionAsync`+Balanced path ignored it, which is why 4 honest centroid reads precede the 5 route-position ones. Mocks/test-provider injection is invisible to the app on this build (per-app appop); all samples in `daylog.json` are real `/aqi` responses to real positions the poll resolved.
- First-plan S8 prompt ("How do you usually get around?") fired before the compare sheet — answered honestly (auto, "not sure"); it sharpens the put-out numbers and stays on the phone.
- Sheet taps in the scrolling HomeSheet occasionally absorb as scroll — swipe-taps on TEXT centers are the reliable input here (same quirk as v4 rows).
- THE MOVE "confidence: low" is the build's "how sure" surface; compare-sheet cards show dose bands instead — asserting the line where the app prints it.

## Rules kept

Live API http://65.2.28.40 only — GETs + `POST /v2/plan` + `POST /v2/reroute` (reroute never fired; stayed on-corridor). Consent/sharing OFF before nav. No daylog/ledger/settings hand-edits. No deploys. Zero smoke defects — no code changes.
