# Lane report: apk-rebuild-v7 — demo binary full pass + audit-fix delta

**Date:** 2026-10-06 · **Verdict: PASS — 13/14 mandated surfaces on the full pass (1 genuine FAIL documented below), and all audit fixes + the new hi covered-hours phrasing confirmed on the final binary** · Drive: Linux/KVM Pixel_7 emulator child ([session](https://app.devin.ai/sessions/d427683e559946bbacf8c934905b9e13))

This lane ran **two passes** because base/v2 HEAD moved twice mid-drive:

- **Pass A — full pass on `alive108-134d92e.apk`** (= palette `d3c4c06` + hi-parity-v2 `ba99bd4` + search-autofocus fix `d791879` + app-overhaul-v2 `d210492`): the entire mandated 14-surface set, overhaul deltas, ≥15 crash-regression search opens, the full hi sweep, pcap, cold-open. Evidence series `v7h-*` (76 shots).
- **Pass B — delta pass on `alive108-21f8363.apk`** (= android-audit fixes `d398061` + `8638825`, plus natural hi covered-hours): armed-skip closure, 420dpi shrink-to-fit deltas, hi covered-hours phrasing, cold-open + smoke. Evidence series `v7f-*`.
- An intermediate `alive108-8638825.apk` delta pass was started and **superseded** by 21f8363 before completion — its evidence is not carried into this report (no mixed-build evidence). A still-earlier `alive108-d3c4c06.apk` was likewise discarded when HEAD moved.

## APKs

### Pass A binary: alive108-134d92e.apk
- **SHA:** `134d92e` — base/v2 HEAD at drive time. Bundle verified by parent: `65.2.28.40` baked, all copy + Devanagari in the UTF-16 table.
- Cold `adb install` after a full `pm uninstall` of the previous build; fresh pcap before install.

### Pass B binary: alive108-21f8363.apk — **the final demo binary**
- **SHA:** `21f8363` — `8638825` (optMeta/tripMeta shrink-to-fit at 420dpi, sheet X reserved inside grabberRow, LayersSheet opacity 0.97, hi reason line wraps) + `d398061` (armed VehicleWizard honours skip/close — clears `wizArmed`, fixing the dead row) + natural hi covered-hours ("{m} मिनट गिने" under an hour, "{h} घंटे {m} मिनट गिने" above — the stilted "0घ 31मि गिने" is gone).
- Repo HEAD at report time is `845f8c0`, a docs/scripts-only commit (`scripts/video/*`) — zero app-code diff, so this binary carries HEAD's app code exactly.

## Pass A — 14-surface verdict table on 134d92e

| Surface | Verdict | Evidence |
|---|---|---|
| Cold-install → onboarding → consent OFF (persisted `settings.json` share:false, `consent.json` sharing:"off") | PASS | [01](https://app.devin.ai/attachments/f01469ac-3800-4827-85a4-d5f9d253fe76/01-launch.png)–[04](https://app.devin.ai/attachments/7abc852f-9a39-4a4b-bfaa-68d10ce1c296/04-perm.png), post-drive state dump [66-state](https://app.devin.ai/attachments/8ab46a03-28be-4d39-a037-67d0b0f83cbc/66-state.png): `{"share":false,"brief":false,"vehicle":null}` + `{"seen":true,"sharing":"off"}` |
| Sparse hero (band-dot arc, "today's air", sample meter, no fake counts) | PASS | [05-hero-sparse](https://app.devin.ai/attachments/af3c01ad-ba8f-4880-9a69-db1e0de0b2b4/05-hero-sparse.png) |
| Solid Trips/Settings/DelhiToday panes — zero map ghosting | PASS | [10-trips](https://app.devin.ai/attachments/2798d477-6f2a-4c5c-b159-585c0864f5f3/10-trips.png) · [12-settings](https://app.devin.ai/attachments/40ebb24d-0b82-4143-ac07-0d407e5b758e/12-settings.png) · [09-delhitoday](https://app.devin.ai/attachments/646e9ccc-d8f0-42b6-80da-ee0fb0d34eae/09-delhitoday.png) · [11-sidebar](https://app.devin.ai/attachments/612cca8e-05b1-47c5-a611-fac863b9e868/11-sidebar.png) |
| Days-ahead numerals full ink | PASS | [06-home-mid](https://app.devin.ai/attachments/1fa342cc-ab5d-42c7-bde2-c20fee26e76f/06-home-mid.png), [07-home-low](https://app.devin.ai/attachments/b202506a-65fa-45fb-af27-8b832f2bb049/07-home-low.png) |
| Ledger dose hero ~30px | PASS | [10-trips](https://app.devin.ai/attachments/2798d477-6f2a-4c5c-b159-585c0864f5f3/10-trips.png) (en), [58-trips-hi](https://app.devin.ai/attachments/34905d92-144a-4757-bb9e-a51d0352936f/58-trips-hi.png) (hi) — big "≈N µg breathed" dominates trip stats |
| Search → plan → compare (Connaught Place → India Gate) | PASS | [13-search](https://app.devin.ai/attachments/b8fafd14-6b08-42a9-b4e5-945b577d1eec/13-search.png) · [13b-results](https://app.devin.ai/attachments/b1fdc9c1-5397-4698-b129-35d06554ae88/13b-results.png) · [24-plan-cp](https://app.devin.ai/attachments/bc0f48f6-c405-4503-b43c-81f9f08f80ce/24-plan-cp.png) · [26-compare-cp](https://app.devin.ai/attachments/1667798c-6b13-40fe-9472-51596cac4c97/26-compare-cp.png) · [33-ig-search](https://app.devin.ai/attachments/cb677186-8f3f-4df6-999e-490ba6feb92a/33-ig-search.png) · [34-compare-ig](https://app.devin.ai/attachments/9e97eef9-0b0d-4418-9835-9b264e70a4ca/34-compare-ig.png) |
| Non-recommended pick nav (Auto-rickshaw over recommended Car AC) → mid-nav | PASS | [39-auto-pick](https://app.devin.ai/attachments/f739dc29-de15-4740-af7f-93f4f65bd450/39-auto-pick.png), [29-navstate](https://app.devin.ai/attachments/dcba8878-ee15-4f84-b83e-e58936dc5979/29-navstate.png), recording below (mid-nav live counter in-frame) |
| Arrival receipt — honest copy ("about" not "est.", kept-on-phone) | PASS | [40-receipt2](https://app.devin.ai/attachments/cd711e8f-d9bc-44c5-ad2d-8bbdf2d1a89a/40-receipt2.png) + nav3 end-frame — "≈1.7 µg **about**", "41.3× less than by On foot · least smoky option 2", "estimated — for vehicles like yours", "kept on this phone only" |
| **"µg (micrograms)" first-use gloss** | **FAIL** | Hero + DayPeek render bare "µg" — **both** `unitUg` call sites deliberately strip the gloss: `HomeScreen.tsx:1003` + `:1199` render `t("unitUg", lang).split(" ")[0]` since `d210492`. Not a rendering bug — the gloss string exists in the bundle but no code path displays it. Documented, not fixed (no app code changes allowed). |
| "least smoky way" (not "least-smoke rd") | PASS | receipt "least smoky option 2" / "the smokiest way"; ledger "less than the smokiest way" — [40-receipt2](https://app.devin.ai/attachments/cd711e8f-d9bc-44c5-ad2d-8bbdf2d1a89a/40-receipt2.png), [10-trips](https://app.devin.ai/attachments/2798d477-6f2a-4c5c-b159-585c0864f5f3/10-trips.png) |
| "counted" (not "accounted") | PASS | [44-home-mid](https://app.devin.ai/attachments/50acec5a-0f87-4c93-98fe-c69180e643d3/44-home-mid.png) — "Nm counted" under hero; hi renders "Nमि गिने" (pre-21f8363 phrasing) |
| hi locale surfaces (hero/doors/ledger Devanagari, zero tofu, zero English leaks) | PASS with residuals | Full ba99bd4 sweep: [54-drawer-hi](https://app.devin.ai/attachments/7b1cb744-0cb1-414a-9197-e4761526fa36/54-drawer-hi.png) (सेटिंग्स · "आपकी लोकेशन → …" row) · [55-home-hi](https://app.devin.ai/attachments/7bd89ac6-cc44-400c-956f-f820ddb090cd/55-home-hi.png) hero "आज आपने साँस में लिया ≈4.5" · [59-delhitoday-hi](https://app.devin.ai/attachments/729746b3-1d2b-46a2-8d90-cb10ac1feea8/59-delhitoday-hi.png) · [61-compare-hi](https://app.devin.ai/attachments/6afb7318-ac11-4c37-99d6-82b065a58824/61-compare-hi.png) · [62-nav-hi](https://app.devin.ai/attachments/07bc0f2c-8168-4997-b670-8ac012094c9b/62-nav-hi.png) · [63-receipt-hi](https://app.devin.ai/attachments/8816b983-88f8-45f7-807c-c733ccf41a88/63-receipt-hi.png) · [65-settings-hi](https://app.devin.ai/attachments/804af3c2-c50a-4fcb-b115-f3103ccfa133/65-settings-hi.png). Zero tofu anywhere. **Residual nits:** ledger row meta shows Latin "8:32 am" suffix; receipt fine print prints a degenerate "0.1–0.1 kg" range. |
| Populated surfaces (hero % of ~216µg budget, hour rows, check-in → `daylog.json` "never uploaded") | PASS | [44-home-mid](https://app.devin.ai/attachments/50acec5a-0f87-4c93-98fe-c69180e643d3/44-home-mid.png) (≈4.5 µg hero, "2% of ~216 µg daily" ring, hour rows) · [45-home-checkin](https://app.devin.ai/attachments/1758c4bc-8d63-4b9b-9a5c-fd98f3b557f2/45-home-checkin.png) → [47-checkin-done](https://app.devin.ai/attachments/749a463a-0277-4783-8610-bb45807c60d3/47-checkin-done.png); daylog written locally only |
| Cold-open timing | **+521ms** | `Displayed com.anonymous.app/.MainActivity for user 0: +521ms` (force-stop → relaunch, logcat). Whole-pass spread +390ms–+582ms across 15 launches. |

## Pass A — app-overhaul-v2 deltas (d210492), all visible

| Delta | Verdict | Evidence |
|---|---|---|
| Tinted hero on home | PASS | [05-hero-sparse](https://app.devin.ai/attachments/af3c01ad-ba8f-4880-9a69-db1e0de0b2b4/05-hero-sparse.png), [44-home-mid](https://app.devin.ai/attachments/50acec5a-0f87-4c93-98fe-c69180e643d3/44-home-mid.png) |
| Icon-tile doors on home | PASS | same shots — "the air map / Delhi today / your trips" as paper tiles with tinted glyph chips |
| Option tiles on compare sheet | PASS | [26-compare-cp](https://app.devin.ai/attachments/1667798c-6b13-40fe-9472-51596cac4c97/26-compare-cp.png), [34-compare-ig](https://app.devin.ai/attachments/9e97eef9-0b0d-4418-9835-9b264e70a4ca/34-compare-ig.png) |
| Stat tiles on arrival receipt | PASS | [40-receipt2](https://app.devin.ai/attachments/cd711e8f-d9bc-44c5-ad2d-8bbdf2d1a89a/40-receipt2.png) — "0 kg put out · 5.8 km distance · 2 min time" tile row |

## Pass A — crash regression (d791879 autofocus-gate)

**15/15 search-sheet opens, 0 crashes** — 3 rounds × 5 opens across force-stop/relaunch cycles, plus every search open in the normal drive (all EditText-detected via uiautomator, not just visually). logcat: zero FATAL / SIGSEGV / tombstone; `com.anonymous.app/.MainActivity` stayed top process throughout. [69-postcrash](https://app.devin.ai/attachments/eacb3224-7416-46f2-876b-ade24db3c07b/69-postcrash.png) — app alive and healthy after the final batch.

## Pass A — bot addenda (hi-parity-v2 verification items)

| Item | Verdict | Evidence |
|---|---|---|
| `notify.ts fmtHr` renders Devanagari "N बजे" in the hi morning-brief notification | **VERIFIED** | Not triggerable live (fires 06:45 next day) — verified by arming the brief in hi mode ([68-brief-armed](https://app.devin.ai/attachments/e45b97e0-f042-4e11-a085-5521530119aa/68-brief-armed.png)) and decoding the persisted scheduled-notification body in `expo.modules.notifications.SharedPreferencesNotificationsStore.xml`: "**4 बजे–7 बजे — हवा 31% हल्की रहेगी। धुआँदार काम इसी समय रखें।**" — Devanagari hours, not "4am–7am". |
| Place names no longer clip to ~2 chars (adjustsFontSizeToFit) | PASS | Full names render everywhere: search results "India Gate Entry Kashturba Gandhi Marg" complete ([13b-results](https://app.devin.ai/attachments/b1fdc9c1-5397-4698-b129-35d06554ae88/13b-results.png)), ledger trip OD titles full, sidebar saved-place rows shrink-to-fit or width-ellipsis honestly ("your locat…" — the pre-fix 2-char clip is gone) ([11-sidebar](https://app.devin.ai/attachments/612cca8e-05b1-47c5-a611-fac863b9e868/11-sidebar.png), [31-trips-row](https://app.devin.ai/attachments/6b9a9d47-4d7e-4c14-a233-3eac3a65b907/31-trips-row.png)) |

## Pass B — delta pass on 21f8363 (final binary)

| Check | Verdict | Evidence |
|---|---|---|
| Consent OFF persisted + `vehicle:null` baseline | PASS | [v7f 02-state](https://app.devin.ai/attachments/5be63b5f-ff6a-41e1-8974-101667b6757b/02-state.png) |
| **Audit #1 (d398061)**: armed VehicleWizard "skip — estimate for vehicles like yours" closes the sheet (onClose clears `wizArmed`; no dead row) | PASS | Armed by planning with no saved vehicle ([04-armed](https://app.devin.ai/attachments/0f9e26e7-356c-4e8b-b394-cfcf22bf6a13/04-armed.png), [05-armed2](https://app.devin.ai/attachments/e4eab0b7-576d-42aa-8376-a018e420e0c4/05-armed2.png) — "How do you usually get around?"); one tap on skip → sheet fully closes, plan proceeds with "vehicles like yours" chip ([06-after-skip](https://app.devin.ai/attachments/220c314c-716d-4de2-8b9c-b2bdc9db6c0a/06-after-skip.png)). The pre-fix dead-row is gone. |
| **Audit #2**: `arrive HH:MM` full on compare option cards at 420dpi | PASS | [07-options](https://app.devin.ai/attachments/3cfce7d1-9e0b-4851-b924-a881638c58b7/07-options.png) — "arrive 09:15/09:16/09:17" complete on every card, no tail-ellipsis |
| **Audit #3**: ledger row meta time full | PASS | [10-ledger](https://app.devin.ai/attachments/8dee7e66-88e7-49e8-bdca-c25763b0e96b/10-ledger.png) — "Car (AC) · least smoky way · 9:13 am" complete |
| **Audit #4**: ledger OD titles preserve destination | PASS | same shot — "your location → India Gate Entry Kashturba Gandhi Marg" full, shrunk not clipped |
| **Audit #6**: sheet X reserved inside grabberRow, clear of card content | PASS | [06-after-skip](https://app.devin.ai/attachments/220c314c-716d-4de2-8b9c-b2bdc9db6c0a/06-after-skip.png) — X top-right beside the grabber, no overlap with cards below |
| **Audit #5**: hi reason/benefit line wraps without `—…` artifact | PASS | [18-hi-compare](https://app.devin.ai/attachments/ef76c7df-fd7c-443c-af65-36029b658f82/18-hi-compare.png) — recommended card reason renders complete: "सबसे हल्के डोज़ के ~10% के भीतर और उनमें सबसे हल्का उत्सर्जन — उचित समझौता।" (full sentence, terminates with danda) |
| **Audit #7**: LayersSheet opacity 0.97 | PASS | [20-layers](https://app.devin.ai/attachments/9cb15f91-d29f-4b4a-9452-2953f916b488/20-layers.png) — "लेयर / आग / एक्सीडेंट स्पॉट / सफ़र से बनी सड़कें" near-opaque; only a faint ghost of the underlying day-bar remains (inherent to 0.97 glass — legible-content bleed fixed) |
| **NEW**: natural hi covered-hours on the hero (`dayCovered`) | PASS | [17-hi-hero](https://app.devin.ai/attachments/7405c067-bb13-40f3-ae05-8bd518e90a87/17-hi-hero.png) — "**21 मिनट गिने**" (not "0घ 21मि गिने"); en shows "21m counted". Full hi hero: "मंगलवार · 09:16 · दिल्ली / आज आपने साँस में लिया ≈4.5 / ~216 µg दैनिक में से / बाहर अभी ~47 µg/m³". |
| hi drawer/sidebar | PASS | [16-hi-drawer](https://app.devin.ai/attachments/f59f1672-47ce-4135-b676-f0e181dcdbe6/16-hi-drawer.png) — आपकी लोकेशन → India Gate Entry Kashturba Gandhi Marg, "कार (AC) · सबसे कम धुआँ वाला रास्ता · 4मि", share OFF persisted |
| Arrival receipt on final binary | PASS | [09-receipt](https://app.devin.ai/attachments/1fd7f06c-6896-4151-ab01-66a142ff1a68/09-receipt.png) — "≈0.4 µg about · 3.6 km · 1 min · estimated — for vehicles like yours · kept on this phone only" |
| Cold-open | **+504ms** | logcat `Displayed com.anonymous.app/.MainActivity: +504ms` (force-stop → relaunch) — same class as 134d92e's +521ms |
| Search-open smoke | PASS | 5/5 opens, EditText detected each time, 0 FATAL/SIGSEGV, process alive |

## Wire audit (pcap)

| Capture | Scope | Result |
|---|---|---|
| [v7-head.pcap](https://app.devin.ai/attachments/d49ea169-61be-47e6-9612-a5dd7581ac51/v7-head.pcap) (3.3MB) | 134d92e full pass | POSTs: **81× `/v2/plan` + 3× `/v2/reroute` — nothing else.** Zero `/v2/trip`, `/observe`, `/report`; zero PUT/DELETE/PATCH; GETs only otherwise (/health, /reports, /aqi, /v2/search, /v2/plan, /v2/reroute, /v2/strip, /v2/day, /v2/outlook, /depart). Consent-OFF respected end-to-end. |
| [v7-delta2.pcap](https://app.devin.ai/attachments/57e2eea5-9005-473a-9d29-52220f269d32/v7-delta2.pcap) (642KB) | 21f8363 delta pass | POSTs: **8× `/v2/plan` only.** Zero other methods; all traffic to 65.2.28.40. Clean. |

## Recording

- **[v7-head-nav3.mp4](https://app.devin.ai/attachments/d5c17353-9b98-415b-b6fe-3bcd91a8e9d0/v7-head-nav3.mp4) — 95s, the take (on 134d92e).** Mid-nav live counter ("smoke you breathe ≈1.4 µg · 1 min · 0.60 km left · arrive 08:33") accumulating → arrival receipt with real stats ("You're here. ≈1.7 µg about · 41.3× less than On foot · least smoky option 2 · 0 kg put out · 5.8 km · 2 min · kept on this phone only") → Done → ledger. Earlier takes (v7-take*.mp4, v7-head-nav-take1/2) were superseded — not linked.

## Failures & residuals (documented, not hidden)

1. **FAIL — "µg (micrograms)" first-use gloss never renders.** `Mobile/src/i18n/strings.ts:173` defines `unitUg: "µg (micrograms)"` (hi: "µg (माइक्रोग्राम)"), but both call sites render `t("unitUg", lang).split(" ")[0]` (`Mobile/src/screens/HomeScreen.tsx:1003` and `:1199`), stripping the gloss at every surface since `d210492`. Verified at HEAD `845f8c0`. The gloss string is dead code; the mandate's first-use-gloss requirement is unmet.
2. **Residual nit (hi):** ledger row meta uses a Latin time suffix ("8:32 am") rather than the hi time format; Devanagari elsewhere is complete.
3. **Residual nit:** receipt fine print can show degenerate ranges ("0.1–0.1 kg") when put-out upper/lower bounds round identically.
4. LayersSheet at 0.97 still lets a faint ghost of the pane below show through — by design (near-opaque), flagged only for completeness vs the audit's glass-bleed complaint.

## Notes (by-design behaviors)

- Plan fetch latency ~10–40s is inherent server behavior (same class as prior lanes).
- Arrival gate (routeLen>90m && remaining≤60 && snap.offsetM≤40) means degenerate <100m plans can't produce receipts — destinations were chosen ≥2km out for receipt evidence.
- 134d92e hi covered-hours used the pre-fix phrasing ("Nमि गिने" with घ/मि units); 21f8363 is the binary carrying the natural phrasing — evidence kept strictly per-build.

## Rules kept

Live API `http://65.2.28.40`: GETs + `POST /v2/plan` + `POST /v2/reroute` only — pcap-verified on both passes. Consent/share OFF in-app the whole drive; no app code changes; never deployed; no stale-build evidence mixed in.
