# Lane report: apk-drive-v4 — rebuilt demo APK @ 609a6ef

**Date:** 2026-10-05 · **Verdict: 9/9 PASS** · Drive: Linux/KVM Pixel_7 emulator child ([session](https://app.devin.ai/sessions/f223c10ec03f441385ed850bbe6feee1))

## APK

- **URL:** https://app.devin.ai/attachments/d6f7b8ca-cb53-4bce-80c9-b4a050cb9124/alive108-609a6ef.apk
- **SHA:** `609a6ef` (base/v2 HEAD — includes `dbbc76a` sparse hero, `59a7da8` nav-start-pick, `bf7c35d` window-format fix)
- **Build:** macOS box, `EXPO_PUBLIC_API_URL=http://65.2.28.40 ./gradlew assembleRelease -x lint` → 131MB, 4 ABIs (arm64-v8a, armeabi-v7a, x86, x86_64), debug-signed, `usesCleartextTraffic=true`, bundle verified to contain `http://65.2.28.40` (grep -a on index.android.bundle).
- Supersedes `alive108-b4a96d2.apk` (the demo phone's build — predates all three fixes).

## Surface × verdict

| Surface | Verdict | Evidence |
|---|---|---|
| S1 fresh-install sparse hero | PASS | [hero-sparse.png](https://app.devin.ai/attachments/5c9ce304-595c-46b8-b530-4da1465a1ed6/alive108-609a6ef-hero-sparse.png) — ambient band-dot arc, "today's air where you are: ~64 µg/m³" band ink, "your count starts once the phone logs its first hours", 1-of-3 dot meter. No gray bar / '0µg this week' skeleton. |
| S2 pick-metro → Start | PASS | [nav-metro.png](https://app.devin.ai/attachments/87a5432a-316b-45b4-abb2-70c7d3893a5f/alive108-609a6ef-nav-metro.png) — tapped Metro+walk → transit nav banner "board Janpath → Botanical Garden · Violet", station steps (Mandi House→Violet→Kalkaji→Magenta→Botanical Garden). |
| S2 no-pick → recommended | PASS | [nav-recommended.png](https://app.devin.ai/attachments/5f6039e0-9bd7-4d66-8a81-0f01d80b17d6/alive108-609a6ef-nav-recommended.png) — no-pick Start on fresh O/D launched the top (recommended) card. |
| S3 open-ended window label | PASS | same hero shot — "heaviest ~22:30–" trailing dash; live `/v2/day` confirms `end_label:null`. Never a '–7pm' tail. |
| Cold-open | **1023ms** | logcat `Displayed com.anonymous.app/.MainActivity: +1s23ms` |
| Journey end-to-end | PASS | [receipt.png](https://app.devin.ai/attachments/885db144-c025-457a-9288-ae297039a9d5/alive108-609a6ef-receipt.png) — "You're here." ≈0.5µg, 17.6km after 62 geo fixes along the car polyline. |
| Consent-OFF silent | PASS | [consentoff.pcap](https://app.devin.ai/attachments/77540004-7bbc-42cb-bd92-a5c50fb2f16e/alive108-609a6ef-consentoff.pcap) — zero POST /v2/trip, /observe, /report across plan→nav→drive; only /v2/plan + /v2/reroute (planning calls). Gate: `Mobile/src/nav/engine.ts:322` `if (shareEnabled && trajRef.current.length > 1)`. |
| hi locale no-tofu | PASS | [hi-hero.png](https://app.devin.ai/attachments/e795c4ef-ce78-4fcc-becd-6473e17e8065/alive108-609a6ef-hi-hero.png) + [hi-compare.png](https://app.devin.ai/attachments/26a1505c-9483-4757-85e7-8d08e2cb5156/alive108-609a6ef-hi-compare.png) — all Devanagari, zero □ (सबसे भारी ~09:30–13:30, कहाँ जाना है?, शुरू करें, सेटिंग्स). |
| D1 sheet drag | PASS | drawer, DelhiToday sheet, compare sheet all scroll up+down (elevation:30 fix `4270ab8` holds). |

## Recording

- [alive108-609a6ef-take.mp4](https://app.devin.ai/attachments/40e169e0-ddee-41c7-bf98-eaef2d32f620/alive108-609a6ef-take.mp4) — 175s, one continuous take: cold-open → onboarding → sparse hero → plan → pick → nav.

## Notes (no defects; two by-design behaviors)

- First cold plan painted 22 options without "Metro + walk"; it appeared on re-plan ("Metro + walk · your usual"). By design: `planEngineFirst(fast:true)` paints engine rows, transit lands async (`refining`/`planDegraded`, `useShellFlow.ts:82–87`, `CompareSheet.tsx:450`).
- Re-planning the SAME O/D after a metro pick auto-reselects metro — pickRef/sameOption identity persistence (`useShellFlow.ts:189`). The regression check used a different destination.
- Take is 175s — screenrecord's 180s hard cap cut it before the S3 re-check pass; every surface is screenshot-proven separately.

## Rules kept

Live API http://65.2.28.40 only (GETs + /v2/plan + /v2/reroute). No deploys, no hand-edits under android/ or ios/. No code fixes needed — zero smoke defects. tsc + expo lint clean on HEAD.
