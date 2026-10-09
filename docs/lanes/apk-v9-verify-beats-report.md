# Lane report: apk-v9-verify-beats — footer-CTA verify + cut8 app beats

**Date:** 2026-10-06 · **Verdict: PASS — 6/6 checks on the FINAL canonical binary** ·
Drive: Linux/KVM Pixel_7 emulator (android-35, google_apis, x86_64) via child
session [devin-1c97d968a9b743c7b3db93c5fd6f3f62](https://app.devin.ai/sessions/1c97d968a9b743c7b3db93c5fd6f3f62);
lane spot-checked evidence independently (screens reviewed, beats ffprobe-verified).

## Binary under test

- **URL:** https://app.devin.ai/attachments/62395036-9498-4e4c-a06d-45be9923cbef/alive108-25bc92c.apk
- **SHA:** `25bc92c` — FINAL canonical. Carries `4f60b28` footer-CTA fix +
  `6b0bacf` DelhiToday species stat tiles + soul pass (`881593a`/`aca9da8`/`549ab7c`:
  hour-aware greeting, band-mood hero + BreathEdge, verdict-washed move card,
  clay ledger) + `59bf92d` colour discipline + `57092e0` one-accent system +
  `518ff95` accent onboarding well + text3→AA contrast.
- **Size/sha256:** 137,691,316 B · `e1399ac3735590ab61d54725061682884425fd8e8489cbd5775861f18a298ae1`
  — sha-verified by BOTH lane and driver before install; `65.2.28.40` baked into
  `index.android.bundle`; installed cold after `adb uninstall`, populated-hero
  reseeded honestly on-device.
- **Superseded binaries** (same footer fix, earlier visual registers — evidence
  kept secondary): `6b0bacf` (`d62c7ed8…9f63`), `b22ee71` (`6ff9be3a…4dea`),
  `59bf92d` (`5fcbe5a1…1e8`), `57092e0` (`0c9e5517…ba92`).

## The delta under test

apk-verify-v8 flagged the scroll-embedded "Where to?" pill dispatch-dead on
Android only — topmost clickable in uiautomator, zero covering nodes, dead to
every input mode, populated-hero dependent. `4f60b28` moved it OUT of the
HomeScreen ScrollView into a pinned footer bar (`ss.ctaBar`) +
`collapsable={false}` on the Pressable. iOS was verified by the lead;
this lane owns the Android verdict.

## Verdict table — alive108-25bc92c.apk (populated-hero state)

| Check | Verdict | Evidence |
|---|---|---|
| a. Footer pill pinned at bottom of home | **PASS** — own bottom bar, outside scroll | [v9_footer.png](https://app.devin.ai/attachments/d5bfd556-6898-4df7-bf80-d752cbc137d6/v9_footer.png) |
| b. 3 cold taps open search, every time | **PASS 3/3** — all via `input swipe 540 2237 540 2237 100`; EditText + Recent list each open | [v9_pill_open.png](https://app.devin.ai/attachments/1e505f1a-a7da-4d9d-b1d3-7ce7d5a890af/v9_pill_open.png) |
| c. Other touchables | **PASS** — ☰ drawer, door tiles, your-day inline expand | [v9_menu.png](https://app.devin.ai/attachments/2852325a-99d5-4fd7-bbb1-cd707a9c6ad9/v9_menu.png) · [v9_doors.png](https://app.devin.ai/attachments/dec8d2b4-4025-49a2-9662-dace5dd85c5c/v9_doors.png) · [v9_daypeek.png](https://app.devin.ai/attachments/a99e9c05-709d-4961-9289-e4248aa6b836/v9_daypeek.png) |
| d. 10 consecutive search open/close | **PASS 10/10** — 0 SIGSEGV / 0 FATAL EXCEPTION | [logcat_v9.txt](https://app.devin.ai/attachments/2a0f858f-c6f3-4f47-8f71-7093431b5681/logcat_v9.txt) |
| e. Scroll-bottom: footer vs BudgetCard | **PASS** — "your daily budget" fully clear | [v9_scroll_bottom.png](https://app.devin.ai/attachments/b6968069-280e-44b0-807b-2564b73ba837/v9_scroll_bottom.png) |
| f. Cold-open → first real numeral | **~3.8–4.0 s** — force-stop → relaunch under screenrecord, ffmpeg frame walk (blank @3.5s → shell @3.75s → numeral @4.0s) | [v9_coldopen.mp4](https://app.devin.ai/attachments/4705008e-bbb8-4a5b-ae03-f52c6750841d/v9_coldopen.mp4) |

**Ship verdict: the dead-pill class is dead.** Every input path that was dead
on the scroll-embedded pill now opens the search sheet — the dispatch failure
mode is gone because the CTA is no longer in the scroll/elevation path.
Confirmed on the bug-repro binary (6b0bacf) AND the final canonical (25bc92c).

## Soul / one-accent spot-checks (all render on Android)

- Hour-aware greeting under brand: "GOOD AFTERNOON · TUESDAY · 13:05 · DELHI" ✓
- Band-mood hero + breathing edge + week dots + gauge ✓
- Verdict-washed "the move" card ✓
- Clay-washed ledger summary + 7-day strip ✓ ([v9_soul_ledger.png](https://app.devin.ai/attachments/e1615929-d4bd-494b-ba92-034097bd99ca/v9_soul_ledger.png))
- Forest-accent door chips + filled-icon forest wells (sidebar / saved places /
  trips / compare) ✓ ([v9_soul_sidebar.png](https://app.devin.ai/attachments/6e6cb986-76cb-4ce9-8b6f-68c40c5be347/v9_soul_sidebar.png) · [v9_soul_compare.png](https://app.devin.ai/attachments/a1143ea4-f851-450a-9339-1663d6088535/v9_soul_compare.png))
- Species row = neutral stat tiles + clay US-AQI tile ✓ ([v9_soul_today.png](https://app.devin.ai/attachments/54cde837-70d8-4a5e-a43d-74fa562987ed/v9_soul_today.png))
- AA contrast clean on every captured surface ✓

## cut8 beats — all taped on 25bc92c (package re-confirmed per beat)

| slot | file | len | on tape |
|---|---|---|---|
| 20_home | [c8_20_home.mp4](https://app.devin.ai/attachments/5eef1d47-fce0-4bda-aa44-da515d7a7efe/c8_20_home.mp4) | 16.1 s | home tour — greeting, counted hero (≈12 µg), forest doors, verdict move card, your-day arc, **footer-pinned Where to?** |
| 22_doors | [c8_22_doors.mp4](https://app.devin.ai/attachments/c1f5a8e9-3712-4bab-b47b-7d5ea1cece6c/c8_22_doors.mp4) | 10.0 s | Delhi-today + your-trips doors opened |
| 25_journey | [c8_25_journey.mp4](https://app.devin.ai/attachments/611a5638-8f51-4b08-8701-9617f91c5722/c8_25_journey.mp4) | 15.8 s | 4-segment cut, one trip: search → "checking every way" plan → compare → Start → nav counters ticking |
| 26_receipt | [c8_26_receipt.mp4](https://app.devin.ai/attachments/750763b8-7b54-43d0-841a-cf5f0c21080a/c8_26_receipt.mp4) | 9.7 s | "You're here." held — ≈2.7 µg · 4.5 km · 8 min · Car (AC) |
| 27_ledger | [c8_27_ledger.mp4](https://app.devin.ai/attachments/e6dc6571-7e50-4e83-8e23-b0859b3074c9/c8_27_ledger.mp4) | 9.1 s | trips ledger — 3 rows + last-7-days strip |
| 28_today | [c8_28_today.mp4](https://app.devin.ai/attachments/3783b7d5-2030-4904-861d-43483a6e2d37/c8_28_today.mp4) | 11.7 s | DelhiToday — ≈543 µg deep hero + **species stat tiles** (neutral grid + clay US-AQI) + 12 h candles + streets |

All clips 1080×2400 native, ffprobe-clean (lane-verified durations).

## Consent-off wire proof (bonus — pcap whole session)

`Share anonymous trip data` = OFF ([v9_consent_off.png](https://app.devin.ai/attachments/633e24b8-d294-4108-b2e2-9baa05ce3c2a/v9_consent_off.png)).
tcpdump of the full drive ([c8_v9.pcap](https://app.devin.ai/attachments/e09a4764-22ff-4ef9-b227-30203f71150b/c8_v9.pcap) +
[b](https://app.devin.ai/attachments/01161bf3-1112-41a8-91ef-014782162307/c8_v9b.pcap) +
[c](https://app.devin.ai/attachments/34a5aa2f-be83-489a-aaac-8525310e65a8/c8_v9c.pcap)):
only GETs + `POST /v2/plan` + `POST /v2/reroute`. Zero `/v2/trip`, `/observe`,
`/v2/feedback`, `/report` POSTs.

## Secondary evidence — superseded binaries (fix verified across builds)

- **57092e0** (`0c9e5517…`): full a–f PASS — 3/3 swipe taps, 10/10 cycles,
  0 crashes, no-overlap, cold-open ~3.2–3.5 s; 2 beats taped before supersede
  (c8_20_home_57092e0.mp4, c8_22_doors_57092e0.mp4).
- **6b0bacf** (`d62c7ed8…`, the bug-repro build): full a–f PASS on the
  populated-hero state where the scroll-embedded pill died — 3/3 swipe taps
  (EditText + Recent each open), 10/10 cycles, ~3.2–3.5 s cold open. Artifacts
  suffixed `_6b0` ([v9_footer_6b0.png](https://app.devin.ai/attachments/27b9c6cb-cb2b-4953-92d6-b269ffbe1157/v9_footer_6b0.png) ·
  [v9_pill_open_6b0.png](https://app.devin.ai/attachments/65707ba2-d906-46ec-8807-e63b60fc1601/v9_pill_open_6b0.png) ·
  [v9_scroll_bottom_6b0.png](https://app.devin.ai/attachments/3a11c084-403e-4b21-b5c1-b288aa3678e7/v9_scroll_bottom_6b0.png) ·
  [v9_coldopen_6b0.mp4](https://app.devin.ai/attachments/8776e490-7f39-4d16-af3f-b7c3ee0d1918/v9_coldopen_6b0.mp4)).
- **b22ee71 / 59bf92d**: sha-verified, never installed (superseded pre-install).

## Method notes / residuals

- All taps via `input swipe x y x y 100` — `input tap` remains unreliable on RN
  rows on this stack generally (pre-existing, not the pill bug). Anyone driving
  by hand should expect tap to work; the adb-tap quirk is input-injection only.
- Populated state seeded honestly on-device: onboarding → consent OFF → vehicle
  wizard answered (car/petrol/2021+) → real geo-fix nav trips (India Gate,
  Connaught Place, Rajiv Chowk — ≈1.9–3.5 µg each) → ambient reads to counted hero.
- screenrecord emits ~0 encoded frames on fully static surfaces; the receipt
  take uses short map pans for encoder liveness. One doors take and one early
  receipt take were discarded and retaken.
- Drive child terminated after artifact upload — no slot held.

## Rules kept

Live API http://65.2.28.40: GETs + `/v2/plan` + `/v2/reroute` only (pcap-verified);
consent OFF throughout; no hand-edits of app state; no rebuilds (sha-checked
uploads only); no deploys; no code changes; repo commits = this report only.
