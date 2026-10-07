# fix-ios-nits — testday-ios findings closed

Lane: close the five non-P0 findings from `testday-ios-report.md`
(16d7202). SIGSEGV explicitly out of scope — lane 6ae1bca2 owns it
(but see §7, new crash evidence collected on this build).

- **When:** 2026-10-07 ~02:40–03:20 UTC.
- **Tree:** `base/v2` @ `7746c9e` + this lane's commits.
- **Build:** dev client on working tree, iPhone 17 sim `EDD9B083`
  (iOS 26.5), `EXPO_PUBLIC_API_URL=http://65.2.28.40`, sim location
  Connaught Place (set after first-boot state, see §6).
- **Gates:** `npx tsc --noEmit` clean · `npx expo lint` clean ·
  store 29/29 · api 8/8 · offline 6/6 · nav 72/74 (2 pre-existing
  failures, proven below — not from this lane).

## 1. P1 — Hindi dose-hero numeral collapses

**Root cause:** `HomeScreen.tsx` counted hero `CountUp` carried
`adjustsFontSizeToFit minimumFontScale={0.55}` (f5a2717, anti-wrap).
iOS measures the fit box against **Noto Sans Devanagari's taller
glyph metrics** in hi locale → collapses to the 0.55 floor ≈24pt.

**Fix:** drop both props, keep `numberOfLines={1}`. The anti-wrap
intent of f5a2717 is preserved by numberOfLines (wrapping was the
actual hazard, not width); the hero digits are Latin numerals either
locale, so no Devanagari glyph box is ever measured. 4-digit doses
still fit at spec scale — verified on-device.

**Proof:** `fix-ios-nits-shots/f1_hi_hero.png` — hi home, counted
dose hero reads "37" at full spec weight (was ~24pt).
`fix-ios-nits-shots/f1_en_hero.png` — en ambient hero "68" on the
same type ramp for weight comparison.

## 2. P2 — stale home after delete-data wipe

**Root cause:** two-layer leak. (a) `clearAllData` reset the ledger
cache and API cache but never reset `store/daylog.ts`'s `mem`
mirror — its own `scheduleWrite` guard (`if (mem === null) return;
// wiped`) proves a null-reset was intended but missing, so the
mounted home kept serving wiped totals from memory. (b) a `readDisk`
in flight across the wipe could land the stale payload afterwards
(the exact class `api/cache.ts` already guards with `wipeGen`).

**Fix:**
- `store/daylog.ts`: `resetDaylogCache()` (mem=null, inflight=null,
  wipeGen++) + generation capture in `readDisk` — a read that
  started before the wipe resolves empty instead of landing stale.
- `components/shell/settings.ts`: `clearAllData` calls
  `resetDaylogCache()` beside `resetLedgerCache()`.
- `App.tsx` `deleteAll`: `dayNonce++` so the mounted home
  re-assembles its (now empty) reconstruction instead of holding
  pre-wipe totals.

**Proof:** `fix-ios-nits-shots/f2_post_wipe_home.png` — same mounted
home, post-wipe: hero dropped "37" to the sparse state
("आज की पहली हवा रीडिंग का इंतज़ार") with **no relaunch**.
Earlier the same run showed the counted "37" (f1_hi_hero.png) —
the mounted screen invalidated live. Regression tests pin it:
`store/daylog.test.ts` "resetDaylogCache — the delete-my-data wipe"
(mem mirror cleared → reads empty; mid-read wipe → stale payload
discarded).

## 3. P2 — gazetteer tail leaks English

**Root cause:** corpus tail kinds ("fountain", "muslim place of
worship", ~100 more) had no `kind_*` strings and no synonym entry,
so `localizeKind` passed them through verbatim — honest but English.

**Fix:** `i18n/strings.ts`, three layers:
- ~100 new `kind_*` keys in en+hi with real Hindi
  (kind_fountain फ़व्वारा, kind_gurdwara गुरुद्वारा, kind_mosque
  मस्जिद, kind_watchShop घड़ी दुकान, …).
- `KIND_SYNONYMS` (~80 entries): corpus variant spellings → keys —
  "muslim place of worship"→kind_mosque, "sikh place of
  worship"→kind_gurdwara, "coffee shop"→kind_cafe,
  "water body"→kind_water, "watchmaker"→kind_watchShop, etc.
- `localizeKind` normalized (trim/lowercase/`_`→space), splits `·`
  compounds per segment, and a hi-only generic fallback
  (`kind_place` जगह) gated to bare lowercase kind-tokens —
  `/^[a-z][a-z ]*$/`. CAPITALIZED unmatched strings (names, address
  fragments) stay verbatim — real info is never flattened to "जगह".
- `KIND_LABEL` now derived from the en table — cannot drift from
  keys again.

**Proof:** `fix-ios-nits-shots/f3_hi_kinds.png` — hi search
"masjid": every result subtitles **मस्जिद** (was raw
"muslim_place_of_worship" tail). Unit tests in
`store/localize.test.ts` pin: all three wire forms of the worship
labels, fountain→फ़व्वारा, compound "mosque · Hauz Khas"→"मस्जिद ·
Hauz Khas", pyrotechnics→जगह, "Block C, Noida" stays verbatim.

## 4. P2 — compare-sheet option taps land mid-layout

**Root cause:** taps during the sheet's enter spring (0→1,
~0.5s) hit child option rows at their *translated* positions — the
reported "bus logged instead of intended".

**Fix:** `ui.tsx` `Sheet` gains an `enterVeil` — an absolute-fill
`View` rendered last inside the sheet (topmost hit target, no
responder) while `settled=false`; the enter spring's completion
callback lifts it. No timers — the veil exists exactly as long as
the sheet is moving. Eats both wrong-child taps and map
fall-through. Covers every `Sheet` in the app (compare options,
vehicle picker, layers, settings sheets) with one change.

**Proof:** `fix-ios-nits-shots/f4_compare_settled.png` — live plan
CP→Hauz Khas (real backend: Car (AC) 9.59km ≈13µg, Bus 548CL
8.78km ≈27µg, Metro+walk 9.35km ≈18µg). On-device repro: re-picked
destination so the sheet re-enters with options, clicked the
mode-strip position **during entry** → no selection change (mode
chip unchanged, no option opened). Same click after settle →
selects normally. Post-settle taps unaffected.

## 5. P2 — layers sheet floats above open sidebar

**Fix:** `App.tsx` — `openSidebar` now calls `setLayersOpen(false)`
before opening, matching the codebase's own sibling-dismiss
precedents (`onDelhiTodayOpen`, `onTripReceipt`, `onFullSettings`
all close the sidebar). One sheet-class surface at a time.

**Proof:** verified on-device — layers sheet open → tapped menu →
sidebar opened with the layers sheet dismissed (previously floated
on top of the sidebar). Screenshot captured during the same drive.

## 6. Notes for other lanes

- **SIGSEGV still reproduces on HEAD (incl. c664a8a drawHold).**
  3 crashes this session, all post-wipe relaunches, all on the
  "go somewhere" → search-sheet mount path, process age <~110s
  (`launchd_sim: exited due to SIGSEGV | sent by exc handler`,
  e.g. PID 10852 ran 106144ms). Same post-wipe relaunch after a
  ~4min idle warm-up: **zero** crashes for the remaining ~15min of
  driving (search, plan, compare, vehicle picker, layers, sidebar,
  wipe dialog). Evidence points at an early-life window the
  mount-gate doesn't cover when caches/files are empty post-wipe —
  lane 6ae1bca2's territory, logged here as repro data.
- **Pre-existing test failures:** nav runner 72/74 —
  `counters.test.ts` "cold-start uplift tapers linearly over
  cold_start_km" + "no uplift when cold_start_km is 0/absent" fail
  identically with this lane's changes stashed (cold-start math,
  owner lane `d3f48d7`). Not from this lane.
- **Sim logistics:** `simctl location` set does not propagate to
  the app's latched fix until relaunch; NCR-bounded plan flows need
  a Delhi fix *before* picking destinations.

## 7. Files

- `Mobile/src/screens/HomeScreen.tsx` — hero fit-props removal
- `Mobile/src/store/daylog.ts` — resetDaylogCache + wipeGen read guard
- `Mobile/src/components/shell/settings.ts` — wire the reset into wipe
- `Mobile/App.tsx` — dayNonce bump on deleteAll; layers dismiss on sidebar
- `Mobile/src/i18n/strings.ts` — ~100 kind_* strings, KIND_SYNONYMS,
  derived KIND_LABEL, normalized compound-aware localizeKind
- `Mobile/src/ui.tsx` — Sheet enterVeil on spring completion
- `Mobile/src/store/daylog.test.ts` — wipe regression tests
- `Mobile/src/store/localize.test.ts` — tail-kind pin tests (new)
- `Mobile/src/store/test-runner.mjs` — File stub gains delete()
