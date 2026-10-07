# Lane report — demo-rehearsal-v2 (Android emulator, freeze APK)

**Rig:** Linux KVM box, 31 GB / 8 cores. AVD `demo` = pixel_7, android-35 google_apis x86_64, `-no-window -gpu swiftshader_indirect -memory 1536`.
**APK under test:** `alive108-c3f7e9e.apk` — sha256 `4faa08ed…7c72`, 137,133,148 B — verified before install.
**Live server at drive time:** `/health` → `build_sha=43913dc0`, `engine=alive_core`, `field_age_s=194`, `field_stale=false`, `smoke_modifier=1.06` on every plan (curl at 12:28 UTC).
**Drive window:** ~11:45–12:29 UTC (17:15–17:59 IST), 2026-10-07.
**Oracle:** `logcat | grep -cE 'FATAL EXCEPTION|SIGSEGV|SIGABRT'` = **0** at end of drive; app process stable (one intentional force-stop for the consent-persistence check).

Every claim below is tagged with its evidence: `shot NN` = `docs/lanes/demo-rehearsal-v2-shots/NN-*.png` committed in this repo, `video:` = attachment URL, `curl HH:MM` = live prod curl, `video-frame t≈Ns` = frame timestamp inside a recording.

---

## Beat × verdict

| # | Beat (script order) | Verdict | What the screen showed |
|---|---|---|---|
| 1 | Welcome (cold open) | **works, with drift** — film plays, but it is interrupted mid-play by the POST_NOTIFICATIONS dialog, then a 3-page onboarding carousel (consent = page 3) + location permission before home | `01-welcome-film.png`; video 01-welcome.mp4 frames: launcher 0–13.8 s → paper splash ~14.2 s → home painted ~14.5 s → welcome film mounts ~15.6–16.6 s *over* the already-painted home → notif dialog ~18.2 s. `am start -W` TotalTime = 845 ms (release). On SwiftShader the film renders very dark (emulator-only caveat). |
| 2 | Home live numbers | **works-as-scripted** | Hero graduated to a live count during the drive: "you've breathed today **13 µg · good · 6% of your daily budget · 23m counted · outside ~53 · satisfactory**" (`02-home-hero.png`, also 8.8→17 µg across the window — it is counting). "air reading: N min old" present. Move card verbatim: "no meaningful window today — satisfactory air all day (55–62 µg/m³)" — matches `/v2/day` decision wire read at ~11:55 UTC word-for-word. Outside ~53–56 vs same-moment `/aqi` pm25 59.2 — agree within the 15-min refresh. |
| 3 | From/to (India Gate → HUDA City Centre) | **works-as-scripted** | "Where to?" → typed `huda city centre` → suggestion list resolved "HUDA City Centre Metro Station · railway station · 18 km" from the bundled gazetteer (no server needed for the row). `03-suggestions-huda.png`. Rig note: suggestion rows eat micro-swipe taps even with keyboard closed — needed a **long-press** (same-point swipe ≥300 ms) to select. |
| 4 | THE CHOOSER | **drifts (see timing §)** — pill + verdict copy play and hold exactly ~4.2 s, but (a) on a fresh profile the whole first chooser is occluded by the vehicle wizard, (b) the candidates-as-equals pre-stage was not visually separable in either recording | `04-chooser-pill.png` (pill "cleanest · 51% less than fastest" mid-map), `04-compare-ladder.png` (full sheet). Videos: 03-chooser.mp4 (cold, behind wizard), 04-chooser-clean.mp4 (warm re-plan). Compare ladder today: **18 rows** — Car(AC) ≈7–9 ×4, car-open ≈13, bike ≈15/21/24/24 ×4, bus ≈18 + Bus-850LTD ≈67, auto ≈20 + ≈26, **metro+walk ≈30 (72 min, Udyog Bhawan→Sikanderpur)**, bicycle ≈98/100, on foot ≈222/234. Winner tag "least smoky · lightest for you", `reason_line` verbatim on card: *"Within ~10% of the lightest dose and the lightest exhaust of those — a fair trade."* |
| 5 | Depart / leave-later / remind | **works-as-scripted** — row present, no boundary flicker | On-screen row: "leave tomorrow 10:00 → breathe ~25% less", depart strip now→+23h with the 10:00 bar green, caption "about +22h · 10:00 ≈ 5 µg". `05-depart-armed.png`. Tap armed it: row flips to "we'll ping you" and `dumpsys alarm` shows `RTC_WAKEUP NOTIFICATION_EVENT origWhen=2026-10-08 10:00:00` for `com.anonymous.app` (verified 12:21 UTC). Wire `/v2/depart` same OD car: now 6.9 µg / best +22h 10:00 = 5.2 µg / `pct_less_vs_now=25` — row is serving real numbers (script pin ~16% → today 25%, still far over the `>8` gate; no flicker). |
| 6 | Community | **drifts** — km matches the wire, but the scripted contributors/avoided numbers are not on the surface | Delhi-today bottom section (`06-community.png`): "what ALive travellers did today — **5 trips · 31 km · ≈11 µg breathed · ≈5.1 kg put out** — 5 trips took a lighter way"; "how Delhi moves — last 7 days · 44 trips — car 82% / other 18%"; street readings heavier/lighter + "a street shows up only after 3 different travellers crossed it in 72 h". Wire `/community` (12:28 UTC): obs_total 44 ✓, obs_today 5 ✓, km_today **31.4** ✓, dose_today 10.9 ✓ — but `contributors: 24` and `avoided_ug_all: 1278.9` are **not shown anywhere in the app** (checked Delhi-today fully + Your trips — the latter is an empty local ledger). |
| 7 | Settings / consent | **works-as-scripted** | `07-settings.png`: Satoshi/quiet register, honest copy ("off by default — your dose stays in µg"). Toggle states at drive end: share-anonymous ON, leave-later reminders ON, air alerts ON, smoke & fires ON, morning air alert OFF. Deep-verify: morning-air-alert ON → `dumpsys alarm` gains `NOTIFICATION_EVENT 2026-10-08 07:00:00`; OFF → app alarms drop back to the one depart ping. Consent persisted across `force-stop` + cold relaunch (614 ms to home; no welcome/onboarding/consent re-prompt; `consent.json {"seen":true,"sharing":"on"}` and `welcome_seen_v1.json` still on disk). |

## Chooser timing (from `04-chooser-clean.mp4`, 10 fps frames)

Warm re-plan on the demo OD (recent pick, ~1.2 s to plan data):

| Event | Video t | Note |
|---|---|---|
| Recents row picked | ≈26.3 s | sheet mounts, "checking every way there…" |
| Camera union-fit animating | ~27–29.5 s | no candidate lines visible during the move |
| Verdict pill A **"cleanest and fastest"** fully visible | **30.1 → 35.3 s** | **hold ≈ 4.2 s — exactly the narrated ~4.2 s** |
| Winner polyline drawn bold | first visible ~32.7 s | persists; one hairline alternate also visible |
| Pill B **"cleanest · 51% less than fastest"** | **39.5 → 43.7 s** | second ~4.2 s hold; pill is absent 35.3–39.5 |
| Pill gone, route persists | ≥43.7 s | compare sheet stays |

So: **pill hold = ~4.2 s, twice, matching the narration**. The "candidates draw as equals → winner settles bold ~1.4–1.7 s" sub-beat was **not separable** in this recording — on a warm (~1 s) plan the draw compresses to pill-in → bold in ~2.5 s with no visible equals plateau at 10 fps. On the cold first plan the equals/settle played *behind* the vehicle wizard (03-chooser.mp4 ~t 125–145 s shows the winner + one hairline through the visible map band, sheet covering the rest).

Demo-morning implications:
- Run the demo OD once on the demo phone before doors — the vehicle wizard only intercepts the **first-ever** plan; after that the chooser plays clean.
- The pill cycles TWO verdict strings: "cleanest and fastest" (~4.2 s) then "cleanest · 51% less than fastest" (~4.2 s). If the narrator reads one, pick the second — it names the quantified claim.
- Winner picked between two near-tied car-AC variants across hits (≈7 direct 22.03 km vs ≈8 least-smoky-way 23.47 km, both "your usual") — dose gap is <1 µg so the story holds, but the pinned µg in the narration should read the screen, not the script.

## Plan-call table (bare `POST /v2/plan`, cold then one warm retry)

| OD | opts cold/warm | winner (dose µg) | reason_line | car-AC / walk mids | spread | metro+walk | took_ms cold→warm | degraded |
|---|---|---|---|---|---|---|---|---|
| CP → Noida | 23 / 23 | Car (AC) **3.5** | "Within ~10% of the lightest dose and the lightest exhaust of those — a fair trade." | 3.5 / 118.2 | 33.8× | **13.5 present** | 2842 → 390 | none |
| CP → Dwarka | 24 / 24 | Car (AC) **6.0** | same | 6.0 / 200.4 | 33.4× | 25.4 present | 6657 → 575 | none |
| **IG → HCC (demo OD)** | 20 / 20 | Car (AC) **7.4** | same | 7.4 / 254.3 | **34.4×** | **48.5 present** | 6187 → 721 | none |
| CP → Gurugram (script OD) | 17 / 17 | Car (AC)·least-smoke rd **8.7** | same (direct Car AC 8.5 loses on emission tie-break) | 8.5 / 311.7 | 35.8× | **ABSENT — no metro+walk option today** | 7156 → 825 | none |
| Karol Bagh → IG (film OD) | 24 / 24 | Car (AC) **3.2** | same | 3.2 / 100.1 | 31.3× | 33.3 present | 1071 → 198 | none |

`smoke_modifier=1.06` on all; no `error`/`degraded` fields on any response; `depart_at`/per-option `depart` are null on a bare plan — leave-later data comes from `GET /v2/depart` (called by the app itself).

## Script-pin vs wire-today (drift log)

| Script pin (docs pinned at 698cf808) | Wire today (12:0x–12:2x UTC) | Screen today | Verdict |
|---|---|---|---|
| demo OD car-AC **7.4** | **7.4** | ≈7–8 | exact ✓ |
| demo OD walk **255.0** | **254.3** | ≈222–234 | wire ✓; screen plan reads −13% low (app's own OD/params — narrate from screen) |
| demo OD spread **~34.5×** | **34.4×** | 32.2–33.9× | wire exact; screen −7% |
| demo OD metro+walk **53.2** | **48.5** | ≈30 | PRESENT both, dose drifted −9% wire / −44% screen |
| demo OD auto **22.8** | **22.7** | ≈20 | ✓ |
| demo OD "about twenty options" | 20 | 18 | ✓ inside the 9–24 swing |
| script OD 17 opts / 7.2 / 237.9 / 33.0× / metro 32.5 | 17 ✓ / 8.5–8.7 (+18%) / 311.7 (+31%) / 35.8× / **metro+walk ABSENT** | — | drifted; the metro-absence kills the "car beats metro" beat on this OD |
| film OD 24 / 3.8 / 117.1 / ~31× / metro 43.4 | 24 ✓ / 3.2 (−16%) / 100.1 (−15%) / 31.3× ✓ / 33.3 (−23%) | — | count + spread hold; absolute doses lower |
| leave-later ≈16% | **25%** (`pct_less_vs_now`, /v2/depart 12:2x) | "~25% less" + "10:00 ≈5 µg" | present and stronger; no flicker (gate is `>8`) |
| community 24 · 31.4 km · 1,278.9 µg | wire exact: 24 / 31.4 / 1278.9 | **only 5 trips · 31 km visible** | wire ✓, screen can't back the contributors/all-time numbers |
| winner `reason_line` | "Within ~10% of the lightest dose and the lightest exhaust of those — a fair trade." | same verbatim on the card | ✓ |
| pill text `chooserVerdict` | n/a on wire (client-composed) | "cleanest and fastest" → "cleanest · 51% less than fastest" | plays, 4.2 s each |

## Re-check of earlier rehearsal findings

1. **Leave-later boundary flicker** (earlier pass: served 8 vs gate `>8` → row flapped): **not reproducible today** — served 25, row stable across both plan hits. Nothing to fix; the flicker only exists at served==8.
2. **`useShellFlow.remind` percent-as-µg** (`Mobile/src/components/shell/useShellFlow.ts` ~l.450): **FIXED in the freeze build's source** — `git show c3f7e9e:…useShellFlow.ts` carries `departSavedPct(depart)` verbatim-read + the self-documenting comment ("`ug_saved_vs_now` is the legacy alias for the same percent") + depart.test.ts pin. Dead finding, don't carry it into the demo narrative.

## New findings (fresh-profile / rig)

- **F1 — first-plan chooser is occluded by the vehicle wizard.** On a wiped profile the plan lands *behind* the fuel/year/PUC sheet; the equals→bold→pill sequence runs under it (03-chooser.mp4). Not a bug — by design the wizard intercepts first pick — but it means a factory-reset demo phone would lose the signature beat. Rehearsed devices are already past it.
- **F2 — winner alternates between near-tied car-AC rows** (≈7 direct vs ≈8 least-smoky-way) across identical-OD hits. Cosmetic jitter; narration should not pin which car row wins.
- **F3 — the scripted community numbers are wire-only** (contributors 24, avoided 1,278.9 µg all-time absent from every in-app surface). If a judge asks to *see* the numbers, they live at `GET /community`, not in the app.
- **F4 — cold-open order differs from the script's "film → home"**: film → POST_NOTIFICATIONS dialog → 3-page onboarding (consent on page 3) → location permission → home. Consent is a swipeable page, not a dedicated screen.
- **F5 — suggestion rows need a long-press on this rig** (micro-swipe taps eaten ×3, keyboard closed). Possibly real app friction on Android beyond the known IME fix (b12c6b3 covers non-search phases); can't isolate emulator vs app — flagged, not fixed.
- **Note — two AQI anchors:** Delhi-today shows "US AQI 86" (city average) while `/aqi` at CP point-read gave `us_aqi 151`. Both honest; different anchors — don't conflate them in narration.
- **Note — wind shifted during the drive:** `/v2/why` evidence line moved from "wind 12.9 km/h W" (11:55) to "wind 5.9 km/h from the N" (12:28); `carrying=true`, belt 12 fires / 26.2 MW, modifier ×1.06 stable.

## Media

Videos (attachments):
- 01 welcome → home (45 s): https://app.devin.ai/attachments/993caaa1-a22c-4333-8177-9b8921192e31/01-welcome.mp4
- 03 from/to → wizard → first plan land (203 s): https://app.devin.ai/attachments/2960bec8-59b4-4f44-9ab1-57c84554fefd/03-chooser.mp4
- 04 chooser clean re-plan — pill timing source (84 s): https://app.devin.ai/attachments/b3630306-f733-4421-b130-2c6c0befaa96/04-chooser-clean.mp4
- 05 depart / leave-later tap → armed / settings toggles (169 s): https://app.devin.ai/attachments/a1ce8a93-6d3a-49dc-97ce-5abda1c46314/05-depart.mp4
- 06 community + settings (36 s): https://app.devin.ai/attachments/481b98d8-d969-4de2-b928-278b7a7e975a/06-community-settings.mp4

Shots (repo): `docs/lanes/demo-rehearsal-v2-shots/` — 01-welcome-film, 02-home-hero, 03-suggestions-huda, 04-chooser-pill, 04-compare-ladder, 05-depart-armed, 06-community, 06-delhi-today, 07-settings.

Raw plan JSONs were captured per OD (cold + warm) during the drive; report numbers above are verbatim from them.

*Nothing in app or server code was touched; the only writes are this file + the shots dir.*
