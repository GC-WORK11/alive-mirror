# weekview — the week strip

Lane: `weekview`. Branch `base/v2`. Built the calendar-like week
distribution detail the owner asked for, as a real component wired into
home. Oct 6–7 2026.

## what it is

`Mobile/src/components/shell/WeekStrip.tsx` — one card, seven day cells,
oldest → today left to right:

- **cell wash** = that day's dose severity (`doseTierIdx` → `bandWashDeepIdx`),
  neutral `surface2` under ~34% of the daily budget. Band color stays
  semantic — it only ever means air/dose.
- **bar** in each cell = dose height scaled to the week's max day, tinted
  `doseDotColor`.
- **numeral** under the bar = `≈ n` via `approx(doseUgRound(ug))`; the
  whole µg numeral language stays mono + "≈".
- **header** = `your week` + `≈ 839 µg this week` (`homeWeek`, existing
  i18n key).

Tap a cell → the card unfolds that day's own detail inline (hairline top,
LayoutAnimation, `useReduceMotion`-gated): `Monday · 5 Oct`, `3h 0m
counted`, the day's `HourArc`, then its accumulator rows
(`dayPartsTitle`). Today and past days share the component; past arcs get
`nh={-1}` so nothing claims a live hour. Tapping again collapses. No new
screen, no sheet — the existing `oaDetail` grammar does the work.

If no day is counted, the card renders nothing (`return null`) — a fresh
install shows no week, which is honest.

## where the data actually comes from — and the ledger gap

**The brief asked for real data from the ledger API. The ledger API does
not serve daily totals — this is the documented data gap.**

`GET /v2/ledger` (verified live and in `server/v2/ledger.py`) returns
donated per-trip summaries keyed by hashed `X-Device-Token` — trip rows
plus an aggregate `totals` object. There is no day-granularity endpoint
anywhere on the server: dose history is not a server concept. Daily dose
only exists on-device, where `reconstructDay(day, samples, trips, now,
lang)` in `src/store/daylog.ts` rebuilds each local day from foreground
ambient reads + logged trips and never uploads it.

So the strip reads what the app already computes: `useDayData` now returns
`week: { day, ug, rec }[]` — seven `DayReconstruction`s (today from the
live rec, past days reconstructed bound at their own 23:59). The tap
detail is the same truth one level down: that day's arc + parts, nothing
invented. Days the phone never covered render neutral and are excluded
from the week total (`thin` days stay honest).

Gap, stated plainly: **no server endpoint serves daily dose totals, and
the daylog never leaves the device** — so there is no remote week history
to sync, restore, or show on a second device. If the owner wants a cloud
week, that's a new endpoint (`/v2/days` keyed like the ledger) plus a
donation decision, not a UI change.

## placement

Brief said "below the hero only if it earns its place." It sits at the
existing week slot — after the `DayCard` (`your day`), before
`DaysAheadCard`. Reason: the hero already carries `heroWeekRow`, the
seven-dot compressed week with the same `week` numbers. Duplicating the
strip inside the hero viewport would show the same week twice — exactly
the clutter the owner asked to avoid. The strip earns its place as the
*detail* layer: severity wash + per-day bar + tap-through to a day's own
reconstruction, none of which the hero dots carry.

## design grammar reused

- Band-washed cells + band-ink day letters + full-ink numerals — the
  `DaysAheadCard` cell grammar, extended with the dose bar.
- Selection = 1.5 accent border (one forest accent, used once).
- Unfold = the `oaDetail` hairline + easeInEaseOut pattern.
- Numerals `famMono`, day letters `weekday: 'narrow'`, `dayLbl_today`
  for today's cell — no icons, no hairline card borders, felt words
  only (`your week`, `where it accumulated`, `not counted — no covered
  hours on the phone that day` for thin-day detail).

## code moved around

- `WeekCard` deleted → `WeekStrip` in `src/components/shell/`.
- `HourArc` extracted to `src/components/shell/HourArc.tsx` (verbatim,
  plus optional `nh` prop for past days) — DayCard and WeekStrip now
  share it.
- `doseDotColor` / `doseTierIdx` moved to `src/theme.ts` (were local to
  HomeScreen; the strip needs them too).
- New i18n key `weekDayThin` (en + hi).

**Real bug fixed while wiring:** the old week loop reconstructed past
days with `now` as the bound — a day reconstructed at 23:00 vs 09:00
gave different answers. Past days now bound at their own 23:59
(`new Date(k + 'T23:59:59')`), today keeps the live bound.

## files

- `Mobile/src/components/shell/WeekStrip.tsx` — new
- `Mobile/src/components/shell/HourArc.tsx` — new (extraction)
- `Mobile/src/screens/HomeScreen.tsx` — week loop → `WeekDay[]`, WeekCard
  → `<WeekStrip>`, HourArc/dose helpers extracted
- `Mobile/src/theme.ts` — `doseDotColor`, `doseTierIdx`
- `Mobile/src/i18n/strings.ts` — `weekDayThin` en + hi

## gates

`npx tsc --noEmit` — 0 errors. `npx expo lint` — clean.

## shots

Rendered on iPhone 17 sim (iOS 26.5), daylog seeded with a real counted
week (34 ambient samples + 2 trips; the app's own foreground-sampling
model — nothing fabricated at render time, just history the device
genuinely holds):

- `weekview-shots/weekstrip-collapsed.png` — strip in home: T/S rose
  (band3), M deep (band4), today amber (band2), quiet days neutral.
- `weekview-shots/weekstrip-day-open.png` — Monday tapped: cell selected,
  `Monday · 5 Oct · 3h 0m counted`, that day's arc + accumulators.
