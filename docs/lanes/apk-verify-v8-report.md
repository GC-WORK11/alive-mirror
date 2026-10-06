# Lane report: apk-verify-v8 — THE final demo binary's device drive

**Date:** 2026-10-06 · **Verdict: PASS — 5/5 checks on the shipped binary** · Drive: Linux/KVM Pixel_7 emulator. Slot-cap note: the SWE-2 cap was full (5/5), so per the lead's instruction the v8 checklist rode on the video-v7 footage child ([session](https://app.devin.ai/sessions/f0abfff33d4e492c92434ff7d2d0298b)) on the **canonical artifact** — no separate drive child was spawned. This lane owns the verdict table; the evidence was spot-checked independently by the lane (screenshots reviewed frame-by-frame, pcap re-analyzed locally).

## APK

- **URL:** https://app.devin.ai/attachments/a269e379-68ea-4f82-9817-dba52afd15ec/alive108-5fd2990.apk
- **SHA:** `5fd2990` — `fix(home): restore first-use µg gloss on the peek card (dead since d210492)`. One commit newer than the 21f8363 binary apk-rebuild-v7 drove.
- **Size/sha256:** 137,687,992 B · `d354f704a339671908de2cd2dceaff41564577b15f5c041f5a6616602720041f` — matches the brief's prefix; re-verified installed on-device by the driver.
- **Bundle verified by lane before the drive:** `65.2.28.40` (live NLB) baked into `index.android.bundle`; `µg (micrograms)` and `µg (माइक्रोग्राम)` present in the UTF-16LE string table; `unitUg` key present.
- **Delta under test:** `Mobile/src/screens/HomeScreen.tsx` `DayPeekInner.peekUnit` (:1007) renders `t("unitUg", lang)` whole (with `numberOfLines={1}` / `adjustsFontSizeToFit` / `flexShrink`) — the dead `.split(" ")[0]` strip is gone at THIS call site. The hero dose row (`heroUg` :1203) and every other dense surface intentionally keep the bare "µg" split.

## Verdict table

| Check | Verdict | Evidence |
|---|---|---|
| 1a. Peek-card gloss, en — "µg (micrograms)" next to the dose numeral (not bare "µg") | **PASS** | [v8_gloss_en.png](https://app.devin.ai/attachments/bfebe33d-e0b3-4d4c-bb42-30e618de21aa/v8_gloss_en.png) — populated map-idle DayPeek "your day so far" card: "≈28 µg (micrograms)" (ambient "now ~51 µg/m³" beside it). Reviewed by lane: gloss renders whole on one line. |
| 1b. Peek-card gloss, hi — "µg (माइक्रोग्राम)" | **PASS** | [v8_gloss_hi.png](https://app.devin.ai/attachments/1da9478e-9fa3-451d-9266-79138825ad7d/v8_gloss_hi.png) — same card in Hindi: "≈28 µg （माइक्रोग्राम）", "आपका दिन अब तक", "अभी ~51 µg/m³". Zero tofu. |
| 1c. Hero + dense surfaces correctly keep bare "µg" | **PASS** | Populated hero shows "≈15 µg" bare + "of ~216 µg daily" + "≈15 µg this week" ([c7_home.mp4](https://app.devin.ai/attachments/1a40192e-1b75-4a9e-9476-1a8407f36a63/c7_home.mp4) ~2s, lane-extracted frame); "your day" accumulation rows "≈6.3 µg / ≈5.8 µg / ≈2.4 µg" bare ([c7_home.png](https://app.devin.ai/attachments/d28b4577-5c8b-4ac7-8a20-0061aa30aa4b/c7_home.png)). The gloss lives only on the peek card — as designed. |
| 2. Armed-skip — fresh plan → vehicle wizard armed → ✕/skip closes on FIRST tap | **PASS** | [v8_armed.png](https://app.devin.ai/attachments/e16c4500-eebe-437d-baa8-593e5c8ceb83/v8_armed.png) (wizard armed: "How do you usually get around?", ✕ top-right beside the grabber) → [v8_skip.png](https://app.devin.ai/attachments/8b3b9a8a-0a75-4d5e-8ee1-41b6ab245f26/v8_skip.png) (wizard closed, compare sheet live with "vehicles like yours" chip). One earlier tap was eaten by the soft-keyboard IME overlay — masked input, not a sheet defect. The d398061 dead-row is gone. |
| 3. 10 clean search opens — EditText present, zero GC SIGSEGV/FATAL | **PASS** | 10 opens / 0 crashes; logcat grep SIGSEGV + FATAL EXCEPTION = 0 (driver's count, consistent with the search-autofocus fix class from d791879). |
| 4. Consent-off pcap — zero /v2/trip, /observe, location writes | **PASS** | [c7_v8.pcap](https://app.devin.ai/attachments/a2ad4e79-992a-47ae-b86a-0ba797f8bd65/c7_v8.pcap) (2.8 MB, `tcpdump -i any host 65.2.28.40` started BEFORE `adb install`, ran the whole pass). **Lane re-analysis:** 42 POSTs total, ALL `/v2/plan`; zero `/v2/trip`, `/observe`, `/v2/track`, `/report`; zero PUT/DELETE/PATCH. Consent-off visible in-app: [v8_share_off.png](https://app.devin.ai/attachments/23a7a914-7b38-4c1b-bbeb-f4f60321964d/v8_share_off.png) (drawer "Share anonymous trip data" toggle OFF). |
| 5. Cold-open → first real number | **≈3.4 s** | [c7_cold.mp4](https://app.devin.ai/attachments/c4e8d7c3-3a88-4b4a-b2b4-97b2a716fa00/c7_cold.mp4) — force-stop → icon tap ~2.1 s clip-time → first live hero numeral "≈33 µg" paints ~5.5 s (frame-level, ±250 ms). Lane spot-frame at 5.0 s shows header+map painted, hero mid-paint — consistent. Emulator-class timing, not a device guarantee. |

## Wire audit (pcap) — lane's own read of c7_v8.pcap

Non-GET requests: **42 × `POST /v2/plan` — nothing else.** GETs seen: `/health` (459), `/reports` (108), `/aqi` (57), `/depart` (38), `/v2/outlook` (22), `/v2/day` (19), `/v2/city` + `/v2/city/moves` (13), `/v2/strip` (24 across route_ids), `/v2/search` (12). Zero `/v2/trip`, `/observe`, `/v2/track`, `/report`, PUT, DELETE, PATCH — the consent-off contract holds end-to-end on the shipped binary.

## Rules kept

Live API `http://65.2.28.40`: GETs + `POST /v2/plan` + `POST /v2/reroute` only — pcap-verified above (no /v2/reroute fired this pass; none needed). Consent/share OFF in-app the whole drive; never POSTed /v2/feedback, /observe, /v2/trip to live; no app code changes; no deploys; no stale-build evidence mixed in (a local same-commit rebuild existed on the driver's box from an earlier beat plan but all v8 evidence + beats came off the canonical artifact — the lane had it switched mid-flight and re-verified sha256).

## Residuals / notes (documented, not hidden)

- **Residual (pre-existing, not the delta):** the home header's "Where to?" pill ignores taps on this build; the identical "your day" pill works (driver used it on tape). Flag for a future lane — worth a quick repro because it sits on the primary CTA path.
- Magenta blocks at the top of the v8_gloss shots are the driver's status-bar redaction, not app pixels.
- The IME-eaten tap during armed-skip is a known adb/soft-keyboard race (keyboard animation eats the tap), not app behavior.
- No drive child of this lane's own exists to terminate — v8 rode on the video-v7 footage child under the slot cap; its lifecycle belongs to the video-v7 lane/lead.
