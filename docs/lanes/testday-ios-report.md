# Lane-B — iOS test day on `base/v2` HEAD

Rig: iPhone 17 sim `EDD9B083-63F1-44E6-9A7B-0A6964CC2561` (iOS 26.5), dev-client
build `com.anonymous.app`, `EXPO_PUBLIC_API_URL=http://65.2.28.40` (the ELB's
IP — sim DNS can't resolve the long `*.elb.ap-south-1.amazonaws.com` hostname;
`/health` is byte-identical between the two). Prod touch: GETs + one
`POST /v2/plan` + live `/v2/reroute` during nav — nothing else.

Shots: `docs/lanes/testday-ios-shots/` (36 images, numbered in run order).
Window: ~18:35–19:25 IST on the sim / 13:05–14:25 UTC 2026-10-06.

## Verdicts at a glance

| # | Checklist item | Result |
|---|----------------|--------|
| 1 | Dev-client build vs prod | PASS — `npx expo run:ios` (UTF-8 env required, see env note) |
| 2 | Welcome film once, onboarding 1–3, home real numbers | PASS — verified twice incl. post-wipe |
| 3 | Real-time refresh across field epoch | PASS — ambient 65.8→72→71→77 observed; field_age_s reset caught at 2 s |
| 4 | Profiles: budget changes; delete-data wipe | PASS — 216→72→216; wipe verified on disk + welcome re-armed |
| 5 | Trip: India Gate→CP, dose, receipt, ledger | PASS — dose ≈3.1 µg (2.4—3.9), arrival receipt, "Today" group |
| 6 | Hindi flip, all surfaces | PASS w/ warts — 2 uncovered gazetteer kinds leak; hero numeral collapses |
| 7 | Unverified flows: sheets, lang mid-session, air alerts, layers z-order | PASS w/ notes — alert banner fired live; z-order wart reproduced |
| 8 | Design-law spot check | PASS mostly — 1 Hindi-hero violation (P1) |
| 9 | SIGSEGV watch | **P0 — 4 crashes, incl. 3 on the drawHold-fixed bundle** |

---

## 1. Build

`cd Mobile && LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 EXPO_PUBLIC_API_URL=http://65.2.28.40 npx expo run:ios --device EDD9B083-…` — clean build, 0 errors. **Without the UTF-8 env, `pod install` crashes** `Unicode Normalization not appropriate for ASCII-8BIT` — env gotcha worth landing in the blueprint.

## 2. Fresh install → welcome once → onboarding → home

- Welcome film played once on first boot (missed the frames during install lag; verified via `welcome_seen_v1.json {"seen":true,"ts":…}`) and **never again** across ~8 later cold launches (evidence: `36-second-launch-no-welcome.png` — straight to home).
- Onboarding 3 pages verified twice — intro card, "Nothing personal is stored." (k-anonymity 3+, trip-end 300 m trim), consent page ("Share trips anonymously" vs "Keep everything on my phone"). The Skip-consent footnote fix (`1afccd8`) renders on every page: *"Skipping counts as sharing on — either way, one tap in Settings undoes it."*
- Home first paint: real numbers — "71 µg/m³ · moderate · 4.7× the WHO daily limit" at CP vs prod `/aqi` `pm25_ambient: 70.7` — exact match (`35-en-home-fresh.png`).

## 3. Real-time across a field epoch

- `daylog.json` accumulated live samples while the app sat open: amb 56.4→57.1→67.4→… at successive positions — no restart needed.
- Home "reading age" text ticked **"11 मिनट पुरानी" → "1 मिनट पुरानी"** → poll cycle ran in-app.
- Dose hero ticked **14 → 21 → 27 → 34 µg** across the session while ambient stayed ~70 (accumulation visible on shots 23/25/home).
- Prod `/health` across the session: `field_age_s` observed at 518 s counting up and **2 s** right after an epoch flip (refresh period ~900 s ≈ 15 min) — the app visibly re-read the new field (ambient moved 65.8→72→71, Delhi-today "1 मिनट पहले अपडेट हुआ").

## 4. Profiles + delete-data

- Budget card segment row: general 216 → **sensitive flips to "आज 72 में से 45 µg बाकी"** (72−27=45, bar fill grows) → back to 216 (`31-hindi-budget-sensitive.png`). `settings.json` persisted `profile:"sensitive"`.
- Delete-data dialog (Hindi): *"आपकी यात्राएं, सेटिंग्स और गुमनाम आईडी इस फोन से हट जाएंगे"* → on confirm, `Documents/` emptied except a re-warmed `alive-cache/` — ledger/settings/consent/daylog/welcome_seen all gone. **Welcome + onboarding re-armed on next launch** (`33/34` shots). One nit: the already-mounted home kept showing pre-wipe totals in memory (30 µg hero) until relaunch — cosmetic ghost, see findings.

## 5. Trip — India Gate → Connaught Place (auto-rickshaw PUC set, BS-IV)

- Plan compare sheet: 4 options ranked by dose with honest ranges; auto option ≈7 µg; vehicle chip "2017–2020 ऑटो | PUC".
- Nav chrome live: turn instructions ("460 m Bear right"), "1 min · 1.0 km left · arrive 18:58", running dose + emit counters.
- **Two real reroutes fired** when sim fixes were teleported off-path — route re-planned and re-announced, no stall.
- Arrival at true dest (28.6318, 77.2194 — from `places.json` recents) after ≥2 <60 m fixes → **receipt**: *"You're here. ≈3.1 µg breathed (2.4—3.9), 21× less than by On foot, smokiest way ≈62 µg more, ≈0.2 kg put out · 8 km · 6 min · added anonymously to Delhi's air map"* (`22-receipt-full.png`).
- Done → home cleanly. The **degenerate dest→dest re-plan bug from the Android drive did NOT reproduce** on iOS.
- Ledger: trip under **"आज"/"Today" day-group** with week bar; expansion shows ranged values + delete (`24-trips-ledger.png`).
- **Donation pipeline verified end-to-end**: my trip appeared in Delhi Today community stats — *"1 यात्राएं · 8.0 किमी · ≈3 µg साँस में · ≈0.21 किया छोड़ा"* and *"1 यात्राओं ने हल्का रस्ता लिया"*.
- **Receipt/ledger mode badge read "Bus" while my selected option card was Auto-rickshaw** — most likely my tap hit the Bus option card while the sheet was laying out (emissions still used my auto profile: 0.2 kg ≪ bus-scale ~3 kg — internally consistent). Logging as a UX footgun P2, not a data bug — but the tap-vs-layout class deserves a look (see findings).

## 6. Hindi flip — every surface, mid-session

Flipped mid-session via sidebar "हिंदी" pill — instant, no restart (`25-hindi-sidebar.png`). Verified surfaces:

- **Sidebar**: "आज · साँस में लिया ≈3.1 µg · गाड़ी ने छोड़ा ≈0.2 किग्रा", day letters बु गु शु श र सो म, "मेरी गाड़ी ऑटो", "बस · 3मि".
- **Settings**: vehicle/language/voice/units/privacy/notifications sections — all Hindi (`26-hindi-settings-alerts.png`).
- **Home**: "शुभ संध्या · दिल्ली · मंगलवार 19:04", "41 मिनट गिने · बाहर ~72 · मध्यम", move card Hindi with Devanagari hour axis **"+3घं +6घं +9घं +12घं +15घं"** (hours localized — no Latin leak).
- **Delhi today**: "822 µg · संतोषजनक · WHO की दैनिक सीमा का 3.8×", species table, forecast strip, community stats, k-anonymity disclosure — all Hindi (`28`).
- **Search sheet**: placeholder "कहाँ जाना है?", recents "हाल की जगहें"; gazetteer kinds localized live — **स्मारक (monument), एतिहासिक स्थल, पार्क** — fix verified.
- **Compare sheet**: "सबसे हल्के डोज़ के ~10% के भीतर…", options show **"4.98 किमी · 19:19 तक पहुँचें"** — किमी on the sheet (`30`).
- **Ledger**: "आज" group, "आपकी लोकेशन → Connaught Place, बस, मंगल, 6 अकतू॰ 6:58 अपराह्न", किग्रा throughout.
- **The 4 leak fixes, live-verified:**
  1. किमी/मी — `fmtDist` uses `t("unitsKm")`/`t("unitsM")`; rendered "8.0 किमी" (Delhi Today) + "4.98 किमी" (compare).
  2. Gazetteer kinds — localizeKind active (see P2 note for uncovered tail).
  3. share CO₂ — **pasteboard read of the trip share**: *"मेरी यात्रा आपकी लोकेशन → Connaught Place: अनुमानित ~3µg धुआँ साँस में गया और गाड़ी ने CO₂ ~0.2 किग्रा छोड़ा — ALive-108 का अंदाज़ा"* — no literal `{co2}`.
  4. Welcome-gate/Skip strings — consent footnote renders on all 3 pages.
- **Language switch mid-session**: sidebar language pill flipped hi↔en in place; no crash, no restart.

## 7. Previously-unverified flows + air alerts

- Onboarding all 3 pages — verified (twice: first install + post-wipe).
- Receipt sheet — verified after a real trip.
- Check-in card — "कैसा महसूस हुआ" साँस/आँखें/ताकत pills; tap wrote `daylog.json checkins['2026-10-06'].breath=0` — on-phone write (`29-hindi-checkin.png`).
- Language switch mid-session — verified.
- **Air alerts (events engine)**:
  - Settings rows render: master "हवा के अलर्ट" + sub-rows धुआँ और आग / हवा का बिगड़ना / साफ़ घड़ी — all Hindi.
  - **Master OFF → all 3 sub-rows grey+disabled instantly; master ON → sub-rows restore previous ON state** (`27-alerts-master-off-grey.png`).
  - **Banner fired for real**: after the wipe+relaunch, a stagnation event banner appeared at the top of the welcome card — *"the air is sitting over the city — barely mixing — 8× stiller than usual; expect the day's smoke to linger"* (`34-welcome-rearmed-alert-banner.png`). Prod at the time: wind 5.8 km/h, factor 0.19 — consistent with the stagnation rule. The banner exists, is designed, and fires on a genuine computed event.
- **Layers sheet**: fires/spots/corridors toggles render Hindi; toggling works (verified via accessibility press — fires ON). No fire glyphs inside the Delhi viewport (belt is NW of the city) — mechanics verified, glyph paint unverified at this zoom.
- **Layers-sheet-over-sidebar z-order wart — reproduced**: opening the menu while the layers sheet is up leaves the sheet floating ON TOP of the sidebar (`32-layers-over-sidebar-wart.png`) — sidebar's bottom rows are covered. Matches the android-overhaul §7 wart; still present on iOS.

## 8. Design-law spot check (per screenshot)

- Warm neutral #FAFAF7 base everywhere; forest #35614B only as small accents (toggles, the alerts icon); band colors (slate→umber) used only where color = air (hero numeral, band dots, community badges). No hairline-divider soup; ambient shadows on cards. No sub-11px type spotted. **One violation**: the dose hero in Hindi collapses to ~body size — see F1.

## 9. SIGSEGV watch — the P0

**4 crashes** captured today, all the same signature (`runningboardd … signal(2) code:SIGSEGV(11)`, KeyboardArbiter `stealKB` ~1.5–2.5 s before death):

1. pid 5859 @18:43:57 — pre-pull build (e925451)
2. pid 8628 @18:45:20 — post-pull, drawHold fix landed
3. pid 8829 @18:47:38 — post-pull
4. pid 8942 @18:48:33 — post-pull

Excerpt preserved at `/tmp/sigsegv-1.txt`. Repro shape: cold launch → home → tap "Where to?" within ~10–90 s → stealKB → SIGSEGV.

**Honest read**: after the drawHold fix (d45a55c+c664a8a) the crash rate *dropped but did not zero* on this box. Counter-evidence: after a ~60 s settle, the same sheet mounted cleanly, and every later mount survived — search results, vehicle wizard ×3, compare sheet, nav chrome, 2 live reroutes, Delhi-today, settings, layers, share sheet — zero crashes for the rest of the run (~35 min of heavy sheet use). The residual window looks like early-lifecycle map-tile streaming racing the first sheet mount. The fix lane's "30/30 clean" doesn't reproduce in my environment; whether that's environment (this box's MTLCompilerService behavior) or residual race is for the fix lane to chase. Until then, demo guidance: **don't tap "Where to?" in the first ~90 s after a cold launch.**

## Findings

- **P0 — SIGSEGV on first sheet mount post-launch.** 4× verified, stack captured, repro documented (§9). drawHold reduced but didn't eliminate it here.
- **P1 — Hindi dose-hero numeral collapses.** `HomeScreen.tsx:1061-1064` — `CountUp` has `adjustsFontSizeToFit minimumFontScale={0.55}`; with `famSerif(hi,"light")` → `NotoSansDevanagari_400Regular` the measure shrinks "21"/"34" from 112 pt to ~24 pt (and drifts across mounts). English unaffected; Delhi Today's static 96 pt "822" renders full-size in Noto — so it's the adjust-to-fit path, not the font. Owner-law violation: the hero loses its display scale in Hindi. Drop the prop or bound the shrink.
- **P2 — Delete-data leaves a stale in-memory home.** Post-wipe, mounted home still showed 30 µg/42 min counted until relaunch. Disk wipe verified; add a state reset on `deleteAll`.
- **P2 — Uncovered gazetteer kinds pass through English.** "fountain", "muslim place of worship" rendered Latin in Hindi results — `localizeKind` tail is English-honest by design (`strings.ts:1869`), but the demo story will hit these: extend KIND_LABEL or render a neutral fallback.
- **P2 — Option cards selectable while the compare sheet is still laying out.** My trip recorded mode "bus" though I intended auto — a mid-layout tap retargeted to the card that slid into place. Consider blocking option taps until sheet settle, or an explicit selected-state confirmation.
- **P2 — Layers sheet sits above the sidebar** (reproduced; same wart as android §7).
- **Observed, worth noting**: prod `/health` returned three different `build_sha`s across the session (bc8f82c4 → 3a71549a → aee635eb) — consistent with auto-deploy on push; worth a line in the runbook so lanes don't report stale-SHA confusion.
- **Sim quirks (not app bugs)**: taps eaten while sheets/maps settle — drove most UI via the iOS accessibility tree (`simulator_accessibility_bridge`), which bypasses the pixel path entirely; Metro serves the JS bundle (verified drawHold refs in the fetched bundle before crashes 3–4); ELB hostname won't resolve in-sim — use the IP.

## What I did not exercise

- iOS `Share` destination flow beyond Copy (share sheet opened, composer verified via pasteboard).
- Voice prompts during nav (toggle exists in settings; not exercised — sim has no TTS value to observe).
- Fires-layer glyph paint (no fires inside the Delhi viewport).
- Leave-late reminder + morning brief (time-based; rows render, not triggered live).
