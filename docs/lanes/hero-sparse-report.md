# hero-sparse — lane report

Mandate: `docs/lanes/hero-sparse.md`. The fresh-install home rendered the
centerpiece as a gray skeleton (thin bar + bare "µg" + "still sparse"
text, "0µg this week" + 7 empty dots). The fix shows the truth the phone
already has, labeled — never a fake personal number.

## What changed (all under `Mobile/`)

### `src/store/daylog.ts`
- `THIN_SAMPLE_MIN = 3` — the thin gate's constant, exported so the UI
  meter reads the same number the gate answers to.
- `DayReconstruction.samplesToday` — ambient reads inside this day; the
  sparse hero's honest "how far along" (N of 3). No schema change to the
  persisted file — it's derived in `reconstructDay`.

### `src/screens/HomeScreen.tsx`
- `SparseAirArc` — the day's ambient PM2.5 forecast curve at the device's
  cell, drawn faintly inside the hero zone (band-colored dots on a
  hairline, same vocabulary as The Move's arc, dimmed further).
- Thin branch of `HeroBlockInner` replaced: no skeleton bar, no bare
  "µg", no invented count. Shows, in order: the faint arc → band-dot +
  "today's air where you are: ~N µg/m³" (band-inked) → "your count
  starts once the phone logs its first hours" → a 3-dot sample meter
  ("N of 3 samples"). When neither the poll nor the curve has a read
  yet, the air line degrades to "waiting for the first air reading
  today" — still designed, still honest.
- `airNow` = the poll's own `ambientUg` first, else the curve's first
  non-null slot — whichever the device actually has, never a guess.
- Stat row (covered-hours + "outside now") now renders only when
  `!rec.thin` — in the sparse state the ambient read lives inside the
  hero zone itself, labeled as the field, not the dose.
- Week strip: when no counted day exists (`week.every(ug == 0)`), the
  personal dots can't stand — the city's forecast days
  (`outlook.days.slice(0,7)`) render dimmed at 40% as band dots +
  "Delhi's next days · your week starts counting today". "0µg this
  week" + empty dots is gone.
- DAYS AHEAD tiles: `bandWashIdx` (10% wash — five identical cards)
  → `bandWashDeepIdx` (26% wash) + day label inked in the band's ink.
  The band is the scan cue; worst/best now read at a glance.

### `src/theme.ts`
- `bandWashDeepIdx(i)` — ~26% band wash for fills where the band itself
  must scan (the days-ahead row).

### `src/i18n/strings.ts`
- `howWe_conf`: "how sure the smoke number is: {c}" → "confidence: {c}"
  (en) / "भरोसा: {c}" (hi).
- `dayThin` removed (dead key — the sparse branch no longer uses it).
- New keys en+hi: `daySparseAir`, `daySparseWait`, `daySparseCount`,
  `daySparseSamples`, `homeWeekCity`, `homeWeekSparse`.

### `src/store/daylog.test.ts`
- New test: `samplesToday` counts the day's own reads, `thin` lifts at
  `THIN_SAMPLE_MIN` (0→thin, 2→thin, 3→counted), and a past day's meter
  reads its own reads — yesterday's samples never pad today.

## Copy nits
- Confidence phrasing: done (`howWe_conf`).
- DAYS AHEAD differentiation: done (`bandWashDeepIdx` + band-inked day
  labels).
- Mixed 12h/24h time formats: already fixed on-branch by `bf7c35d`;
  verified live in both locales — "~12:30–01:30", "~22:30–" render
  24h-consistent in en and hi.

## Verification (iPhone 17 sim, Delhi location 28.61,77.21, live server :8000)

| state | before | after |
|---|---|---|
| sparse (fresh daylog) | thin gray bar + "µg" + "still sparse"; "0µg this week" + 7 empty dots | faint ambient arc + "today's air where you are: ~116 µg/m³" + count-starts line + "1 of 3 samples" meter; dimmed city week + "your week starts counting today" |
| populated (39 seeded + live samples) | ≈172µg hero, gauge, week dots | unchanged — no regression; new confidence copy visible |
| sparse, hi | — | all sparse strings Devanagari, arc + meter intact |
| populated, hi | — | hero unchanged, 24h times consistent, "भरोसा: कम" |

Screenshots: before-sparse.png, before-populated.png, after-sparse.png,
after-populated.png, after-sparse-hi.png, after-populated-hi.png
(attached to the session, not committed).

## Gates
- `npx tsc --noEmit` — clean
- `npx expo lint` — clean
- `node src/store/test-runner.mjs` — 14/14 pass (incl. new sparse-meter test)

## Notes
- `expo-device`/`@expo-google-fonts/*` were absent from node_modules on
  this box (snapshot gap) — `npm install` + `pod install` + rebuild
  required before the dev client could bundle. Unrelated to the diff.
- No deploy, per mandate. Nothing outside `Mobile/` touched except this
  report.
