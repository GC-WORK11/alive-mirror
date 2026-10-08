# android-taste lane report

Restrained design-critique pass on the current app (post-fix-wave), per the vendored
`docs/design/taste-skill` method: audit first, fix only the small things that made it
feel less crafted. No layout rebuilds, no new components, no copy rewrites.

**Scope driven:** onboarding, home hero + incidents, move card, door rows, sidebar,
settings, trips (ledger) empty state, compare/week sheets (stylesheets + partial drive).
Android rig: `devin-101f225a70824f31a7ebbf79a96e2917` (Pixel-class emulator, origin HEAD
before-shots). iOS sim corroboration: iPhone 17, stash/pop before↔after toggle.
All fixes verified live on sim; shots in `docs/lanes/android-taste-shots/`.

## Grammar map (what "correct" looked like before touching)

- Card radii: home editorial paper cards = 24; utility cards = `V2Radius.card` (20);
  glass/chrome = 20; inner sidebar/sheet tiles = 16 (a deliberate sub-grammar — left alone);
  rows/wells = `V2Radius.row` (13); pills = 999.
- Stepped numeral/headline literals (112/96/62/44/40/30/26/21) are deliberate hierarchy
  steps, not off-ramp errors — left alone.
- Icon wells tune *size* per row (40/42/44) but share the row radius — the radius is the
  grammar, not the size.
- Press-state spectrum: bigger surfaces dip less (0.85–0.9 cards, 0.8 mid, 0.7 rows,
  0.55–0.65 chips/icon buttons). The 0.55/0.6 split on same-size buttons was incoherence.

## Fixes (all value-only style edits, 7 files, +7/−10)

| # | Flaw | Fix | Where |
|---|------|-----|-------|
| 1 | incidentsCard had `marginTop: 10` inside a `gap: 16` stack — 26px vs the 16px rhythm every other card keeps. Card sat like it forgot its spacing. | Removed the margin — card now keeps the stack rhythm. | `Mobile/src/screens/HomeScreen.tsx` (`incidentCard`) — shots `before-/after-02-home.png` |
| 2 | Trips header carried a `borderBottom` hairline — every other screen header is line-free; the hairline made Trips look like a web page. | Removed `borderBottomWidth/BorderColor` (Settings parity). | `Mobile/src/screens/LedgerScreen.tsx` (`bar`) — shots `before-/after-05-trips-empty.png` |
| 3 | Trips empty state used a **forest-wash** icon well — the only green wash on a screen where nothing means "air yet". An accent that decorated instead of meant. | `V2Tint.forest.wash` → `V2T.surface2` (Quiet-primitive grammar). | `Mobile/src/screens/LedgerScreen.tsx` (`emptyBadge`) — shots `before-/after-05-trips-empty.png` (clearly visible) |
| 4 | Ledger `modeBox` icon well `borderRadius: 14` — off-grammar (row-wells are 13). | → `V2Radius.row`. | `Mobile/src/screens/LedgerScreen.tsx` |
| 5 | ~~Onboarding `jIcon` well `borderRadius: 14`~~ — **superseded**: `fbecd3e` landed a parallel onboarding rewrite (new arc/kCard/choice grammar, `arcIcon` 38px/r12) while this lane was in flight; the fix was dropped in the rebase, not carried. | — | (conflict resolution) |
| 6 | CompareSheet `modeWell` `borderRadius: 15` — same drift. | → `V2Radius.row` (44px size kept). | `Mobile/src/components/shell/CompareSheet.tsx` |
| 7 | Three 40px icon buttons pressed to `opacity: 0.6` while the same-size grammar elsewhere is `0.55` — a feel difference you notice mid-tap, not in stills. | All → `0.55`. | `WeekSheet.tsx` (`closeBtn`), `Sidebar.tsx` (`closeBtn`), `SettingsScreen.tsx` (`headerBtn`) |

Gates: `npx tsc --noEmit` + `npx expo lint` clean before and after; jest store suite
16/16 (its known pre-existing `msSinceInput` export error is unrelated, present on a
clean checkout too).

## Judged-and-left (the restraint part)

- **Tile-16 radius inside sidebar/sheet cards** — intentional sub-grammar (nesting
  depth cue), consistent everywhere it appears.
- **Stepped font literals** — deliberate editorial scale, not token drift.
- **Onboarding wind icon rendered in band color** while siblings are stone — a
  deliberate accent beat (air = the one colored glyph). Consistent with the law.
- **Move card**: post-fix-wave it already carries a full-sentence verdict
  ("cleanest hours ~8:30am–11:30am — around 57 µg/m³, against 67 across the day"),
  labeled day-graph with hour ticks, and heaviest/lightest legend bullets — it
  *explains* itself. The `moveTitle` label "the move" is abstract but it's a card
  name, not the verdict; renaming = copy change → catalog only.
- **Press-opacity spectrum elsewhere** (0.85 cards / 0.8 mid / 0.7 rows / 0.55
  icons) — coherent size-scaled grammar after fix 7.

## Catalog for a future lane (needs real redesign — NOT fixed here)

1. **Onboarding third card clips at small heights**: on iPhone 17 the "when you
   arrive" card's sub-line ("and what your ride put out") is cut by the consent
   footnote; likely scrollable but the fold reads cramped. Android repro: rig
   child's `before-01-onboard` shot. Fix = scroll affordance/spacing rethink,
   beyond a value tweak.
2. **Move-card title "the move"** is abstract for first-time users; a clearer
   label ("when to go"?) is a copy decision → owner call, not a taste fix.
3. **Hindi layout watch list** (from strings audit, not driven): `nav_recenter`
   (9→21 chars), `compare_yours`, `tripsEmpty`, `savedWork`, `boardMetro`,
   `kind_*` chips — needs a Hindi-language drive to check truncation/wraps.
4. **Push-notification banner styling** — the `[expo-notifications] Error reading
   persisted…` toast is dev-build noise, not shipping UI; no action.

## Evidence

- `docs/lanes/android-taste-shots/` — `before-*/after-*` pairs (iOS sim, iPhone 17):
  `02-home` (fix 1 spacing), `03-sidebar`, `04-settings`, `05-trips-empty`
  (fixes 2+3 — the visible ones), `00-launch`/`01-onboard`.
- Android (Pixel-class): rig child session shot the same catalog at origin HEAD;
  its after-reshoot runs against the pushed fixes. Where both rigs show the same
  rendering (they do for these value-only changes), iOS shots are representative.
- Static audit trail: `~/taste-audit-findings.md` (grammar map + per-site grep log).
