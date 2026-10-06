# Lane report: apk-drive-v5 — release APK @ 0a26f5a

**Date:** 2026-10-06 · **Verdict: 11/11 PASS** · Drive: Linux/KVM Pixel_7 emulator child ([session](https://app.devin.ai/sessions/e89b174925c04f81bd1baa97db577efb))

## APK

- **URL:** https://app.devin.ai/attachments/efb4bf26-7351-4fb8-afad-f81f63c36cbb/alive108-0a26f5a.apk
- **SHA:** `0a26f5a` (base/v2 build-point HEAD — includes `3711ccd` odometer-arrival offset gate, `0fdd597` ledger dedupe removal + `/v2/trip` plausibility floor). Drive-time repo HEAD `0f9ab81`.
- **Build:** macOS box, `EXPO_PUBLIC_API_URL=http://65.2.28.40 ./gradlew assembleRelease -x lint` → 137.7MB, 4 ABIs (arm64-v8a, armeabi-v7a, x86, x86_64), debug-signed, `usesCleartextTraffic=true`, bundle verified to contain `65.2.28.40` (grep -a on index.android.bundle).
- Supersedes `alive108-609a6ef.apk` (the v4 drive build — predates the arrival-gate and dedupe/422 fixes).

## Surface × verdict

| Surface | Verdict | Evidence |
|---|---|---|
| Cold-install sparse hero | PASS | [hero-sparse.png](https://app.devin.ai/attachments/2b624ee3-1958-42ac-b5b8-dab6a6bf4ec8/04-hero-sparse.png) — ambient band-dot arc, "today's air where you are: ~70 µg/m³", "your count starts once the phone logs its first hours", "1 of 3 samples" dot meter. No gray bar / fake counts. |
| Non-recommended pick → nav | PASS | [nav-start.png](https://app.devin.ai/attachments/27bc7645-cc15-4cc9-8e22-361c5f11f6e5/06-nav-start.png) — plan Connaught Place → India Gate offered recommended "Car (AC) · your usual" on top; tapped the lower "Car (windows down)" card → Start → nav on the 3.98 km corridor. |
| Off-corridor jitter no-arrive (`3711ccd`) | PASS | [jitter-no-arrive.png](https://app.devin.ai/attachments/2b68d4ae-dc2c-4869-8a6a-4e644253add2/07-jitter-no-arrive.png) — 2 fixes ~1.2 km lateral off corridor placed so their nearest route point sat near the destination: nav kept running ("1 min · 0.55 km left"), zero phantom receipt. Arrival gate now requires `snap.offsetM <= 40` (`engine.ts` ~L384). ≤2 fixes → below `OFF_ROUTE_FIXES=3`, no reroute. |
| Real arrival + receipt honesty | PASS | [receipt.png](https://app.devin.ai/attachments/da37c32e-63e0-49c8-a983-6456370cdb65/08-receipt.png) — "You're here." Car (windows down): ≈3.7 µg (est. 2.7–4.7), 5.6 km, 5 min, ≈0.3 kg put out, "kept on this phone only". Honest non-zero km. |
| Second same-O/D trip lands — dedupe removal (`0fdd597`) | PASS | [receipt2.png](https://app.devin.ai/attachments/89f10060-e2ae-49ce-b7f1-086db5a0deb0/09-receipt2.png) + [ledger.png](https://app.devin.ai/attachments/01e7c3ed-dc4b-42cc-9bae-e0502a35fcef/10-ledger.png) — second Connaught Place → India Gate arrival landed ≈0.2 µg / 4 km / 1 min; ledger shows BOTH "central Delhi → India Gate" rows separately (2:12 am, 2:13 am). |
| Offline queue lands-once | PASS | Seeded outbox (`1` item → local stub `10.0.2.2:8899`, outside the pcap host filter): flushed on the next inferred "up" — stub logged exactly **1** POST, `outbox.json` drained to `items:[]`, still **1** line after a second up-cycle. Lands-once semantics hold. |
| 0-km `/v2/trip` plausibility floor (`0fdd597`) | PASS | `POST /v2/trip {"distance_km":0,...}` → **HTTP 422** `{"detail":"missing or implausible distance_km"}` — the drive's single deliberate live POST, fired only after pcap stopped. |
| Consent-OFF silent wire (pcap) | PASS | [v5.pcap](https://app.devin.ai/attachments/0c74d098-1d1d-485c-a8e4-cf483e5f3e43/v5.pcap) — across install → onboarding → 2 full nav drives → check-in → hi locale: POSTs only `/v2/plan` (34) + `/v2/reroute` (4); **zero** `/v2/trip`, `/observe`, `/report`. `settings.json` `share:false`, `consent.json` `sharing:"off"` persisted on disk. |
| Cold-open | **+390ms** | logcat `Displayed com.anonymous.app/.MainActivity: +390ms`. |
| hi locale no-tofu | PASS | [hi-sidebar](https://app.devin.ai/attachments/84a29bb4-eb36-4311-a794-4860887899bc/13-hi-sidebar.png) + [hi-hero](https://app.devin.ai/attachments/5bfeb6df-8e27-43ff-aabf-0d2bba376e8a/15-hi-hero-top.png) + [hi-compare](https://app.devin.ai/attachments/e8673127-8885-42fd-ae84-27f58202247b/16-hi-compare.png) — full Devanagari (सेटिंग्स, कहाँ जाना है?, शुरू करें, कार (खिड़कियाँ खुली), हवा की रीडिंग: 1 मिनट पुरानी), zero □. Saved check-in renders in hi too. |
| Populated surfaces | PASS | [hero-populated.png](https://app.devin.ai/attachments/e6d94f7b-9516-44be-9e19-496a10aace44/11-hero-populated.png) — ≈21 µg / 10% of ~216 µg / 0h52m accounted + per-hour attribution rows; [checkin.png](https://app.devin.ai/attachments/351a6627-66fc-42e9-8b68-819a45fc4700/12-checkin.png) — breath·eyes·energy chips saved to `daylog.json` ("never uploaded"). |

## Recording

- [v5.mp4](https://app.devin.ai/attachments/f79fd3e7-a7ff-44e9-9240-b4a4cced4da2/v5.mp4) — 89 s, one continuous take: cold-open → populated hero → search "India Gate" → plan → Start → nav (distance countdown 4.0 → 0.18 km) → "You're here." receipt (≈0.1 µg, 3.8 km, 1 min) → Done → drawer → Trips ledger with **5 same-O/D rows** (3 × Car (AC) + 2 × Car (windows down)).

## Notes (no defects; by-design behaviors)

- On the recording pass `/v2/plan` returned a **single** option card (Car (AC)) for this O/D — the option set is server-decided per request; earlier plans in the same drive offered the windows-down alternative. The Start you see in the video is the only card offered; the scripted non-recommended pick is the trip-1 evidence above.
- First cold plan can paint without the transit card — same async-refine behavior documented in the v4 report; unchanged here.
- Offline/queue pill never rendered (everything stayed online; the outbox flush is invisible by design — the pill only shows on pending/stale).
- Symptom check-in stores only to `daylog.json` `checkins` — verified on disk; nothing left the device (pcap row).
- Jitter kept to 2 fixes so `OFF_ROUTE_FIXES=3` couldn't legitimately fire a `/v2/reroute` — a clean no-arrive assertion of the `3711ccd` gate.
- The recorded drive's ledger grew to 5 rows across verification runs — dedupe removal keeps each arrival its own row, which is the point of the fix.

## Rules kept

Live API `http://65.2.28.40`: GETs + `POST /v2/plan` + `POST /v2/reroute` only, plus the one permitted post-pcap 0-km `/v2/trip` probe (422). Consent/share OFF in-app the whole drive. No app code changes — zero smoke defects. Never deployed; no AWS calls.
