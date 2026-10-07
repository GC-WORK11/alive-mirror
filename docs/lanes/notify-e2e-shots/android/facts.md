# notify-e2e — Android emulator drive (KVM, release APK vs live prod)

**Rig:** `demo` AVD (pixel_7 · android-35 google_apis x86_64 · KVM `/dev/kvm`, 1536 MB, swiftshader, `-no-window`).
**Binary:** `alive108-70914c0.apk` → sha256 `bfceaf26ad8f410d3995c473e77d14efd950e7ee1b610a20f7fa66849f41e88f` **VERIFIED** (137,120,268 B). Package `com.anonymous.app`, label `ALive·108`, `POST_NOTIFICATIONS` declared in manifest (aapt).
**Prod:** `http://65.2.28.40` (ELB alias) — GET only, never POSTed.
**Session window:** ~09:35–10:20 UTC Oct 7 2026 (= 15:05–15:50 IST). Emulator clock = UTC.

## Permission path used

**REAL OS dialog.** Cold `am start` landed on the intro carousel; ~2 s later the system grant dialog appeared: "Allow ALive·108 to send you notifications? / Allow / Don't allow" — granted by a 2 px micro-swipe on "Allow" (`perm_dialog.png`, `after_perm.png`, `after_allow.png`). logcat: `GrantPermissionsViewModel` `result=4` at 09:40:55. Not `pm grant`. This proves `requestPermissionsAsync` was invoked from the engine's `fire()` path before first banners (intro overlay ordering is the known cosmetic note).

## Channel

`air-events` exists, `mImportance=4` HIGH, mName "air alerts", `mSound=notification_sound`, vibration `[0,250,250,250]` — matches `notify.ts`. Every posted record: `mIsInterruptive=true`, `AUTO_CANCEL`, `vis=PRIVATE` (dumpsys_final.txt).

## Banners fired — verbatim (title / body)

| kind | verbatim title | verbatim body | how it fired |
|---|---|---|---|
| `stagnation` | "the air is sitting over the city" | "barely mixing — 2× stiller than usual; expect the day's smoke to linger" | **NATURAL** — live `/v2/why` primary stagnation driver, factor 1.86 ≥ 1.5, score 0.717 → level 60 |
| `trend_down` | "the city's air is easing" | "65 → 50 µg/m³ over 5.7h — the air barely moving to clear it — off the earlier high" | **NATURAL** — live trend driver falling −15.5 µg/5.7 h |
| `window` | "easiest hours ahead" | "today's lightest air ~14:30–18:30 IST · about 59 µg/m³" — **re-posted** "~15:30–19:30 IST · about 59 µg/m³" | **NATURAL** — cleanest_window inside [start−60 m, end); prod revised the window and it re-fired (level=startM 870→930), replacing the card in place |
| `grap_clear` | "the day eased off the GRAP map" | "our read no longer maps to a stage (aqi ~119) — still our computed read" | **SEEDED** — events.json baseline grapStage 3 → live 0 = clear. (First fire rendered "(aqi ~120)"; live read drifted.) |
| `reflect` | "yesterday on the road" | "2 trips · about 84 µg inhaled — heavier than Sunday (60 µg)" | **SEEDED** — ledger.json 2 trips yesterday (42+41.5≈84 µg) vs 1 trip 3 days ago (60 µg) |

On-device copy differs from current `strings.ts` (e.g. "our read no longer maps to a stage (aqi ~119) — still our computed read" vs HEAD's "today's air no longer reads like a stage … our estimate") — consistent with the APK being built from commit `70914c0`, older than HEAD `9fbd851`. Not a bug.

## Honestly quiet (correct silence = evidence)

- **`fires_nc`** — seeded baseline beltFires=4, live belt=12 → jump +8 < max(15, 4·0.5)=19 floor → silent across 3 passes. Rule works.
- **`band`** — ambient ~59–65 µg/m³ → bandIdx 1–2 < BAND_MIN_IDX 3. Baseline silently tracked (2→1).
- **`severe` / `grap_up` / `grap_down`** — live grap.equivalent_stage=0.
- **`outlook_heavy`** — gate closed: IST 15:39 probe → tomorrow pm25_mid 106.1 vs today ~65.5 (+62 %, ≥ shift floor) but `OUTLOOK_EVE_FROM_IST=17`, `OUTLOOK_EVE_TO_IST=22` (events-core.ts:52–53,254) — session ended before 17:00 IST. Fold is real; gate state documented instead of faked.
- **`trend_up`, `fires`, `outlook_light`** — conditions absent (trend falling, carrying=false, fold heavy not light, no evening gate).
- **`stagnation` re-fire** — cleared its seen mark and relaunched; honestly silent because the live driver list at 10:18 UTC contained only `trend` (ventilation recovered to factor 0.87). Correct.

## seen-marks dump

Pass 1 (`events_pass1.json`): baselines stored silently `beltFires:12, bandIdx:2, grapStage:0`; `seen:{stagnation:{day:2026-10-07,level:60}, trend_down:{day:2026-10-07,level:16}}`.

Final (`events_final.json`, after all passes):
```json
{"beltFires":12,"bandIdx":1,"grapStage":0,"feedHealth":null,
 "seen":{"stagnation":{"day":"2026-10-07","level":60},
         "trend_down":{"day":"2026-10-07","level":16},
         "window":{"day":"2026-10-07","level":930},
         "reflect":{"day":"2026-10-07","level":1},
         "grap_clear":{"day":"2026-10-07","level":0}}}
```
Seeded values were overwritten by live ones (beltFires 4→12, bandIdx →1, grapStage →0) — baselines self-correct, as designed. `window.level=930` = 15:30 start-minute — the revision re-fire. Dedupe: same-day marks blocked every repeat fire (passes 2/3/5/6 re-verified).

`ledger_final.json` — seeded trips rendered in-app: sidebar "3 trips · ≈ 144 µg" (42+42+60), rows "auto · CP → home · 1d ≈42 µg ×2 / · 3d ≈60 µg" (`side4.png`).

## Shade / lock-screen behavior

- Cards post under "ALive·108 · now" in the shade, collapsed title+truncated body, expandable chevron (shade_events2, shade_p3, shade_p4, shade_grap_expanded).
- Real keyguard (locksettings disabled→enabled) shows both notification cards with the same copy (keyguard_swipe.png, lockscreen_notifs.png).
- Per-kind identifier `air-event-<kind>` replaces the earlier card in place — verified by the window revision re-post (12 m age in `shade_now2.png`).

## Bugs / findings

1. **Heads-up peek never rendered on this AVD** (observation, not proven app bug): across 6 cold launches + 6 screenrecords (~11 min footage incl. frame-delta scans) + dense screencaps, no floating banner ever appeared; posts land directly in the shade. Records show `groupKey=0|com.anonymous.app|g:silent` + `groupAlertBehavior=1` (NMS autogroup) with `mIsInterruptive=true`, channel importance=4 — likely the API-35 google_apis emulator's autogroup presentation quirk. **Recommend one physical-device or Play-image check before shipping the peek claim.** Everything else about delivery (post, channel, sound+vibrate config, shade, keyguard, in-place replace) is verified.
2. **No POST_NOTIFICATIONS breakage** — the feared showstopper does not exist: real dialog, grant, channel, and posts all work.
3. Cosmetic: permission dialog fires over the intro carousel before first-run ends (known ordering note).
4. `cmd statusbar expand` absent on this build — used swipe-down (rig note only).

## Artifact index (~/evidence)

- Videos: `n1.mp4` (173 s, pass-1 launch→perm dialog→carousel), `n2.mp4` (169 s), `n3.mp4` (119 s), `n4.mp4` (89 s), `n5.mp4`, `n6.mp4` (68 s), `nt.mp4` (peek probe).
- Screens: `perm_dialog.png`, `after_perm/after_allow.png`, `shade_events2.png` (trend_down+stagnation), `shade_p3/p4.png` (reflect+window+grap_clear), `shade_grap_expanded.png`, `shade_now2.png` (window re-post), `keyguard_swipe.png`, `lockscreen_notifs.png`, `settings_airalerts.png` (+crop — master + 4 sub-rows all ON), `side4.png` (sidebar w/ seeded trips), `home2.png`, plus ~140 pass frames.
- State: `events_pass1.json`, `events_final.json`, `ledger_final.json`, `dumpsys_final.txt`, `facts.md` (this file).
