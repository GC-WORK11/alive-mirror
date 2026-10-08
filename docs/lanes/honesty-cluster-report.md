# honesty-cluster — lane report

Closes the open honesty findings in `docs/lanes/bug-hunter-report.md`: F2, F4, F6, F7, F8.
Scope held: no PRs, prod GET-only, no deploy, no rebucketed history, no feature removal,
no invented coordinates or renamed results.

## F4 — DelhiToday showed yesterday's totals on a zero-trip day

- `Mobile/src/api/city.ts` — typed `trips.today_key` / `trips.today` (already served by
  `server/v2/city.py:440–473`, re-derived per serve even on the cache path) and exported
  `cityToday(payload)`, the single truth: the server's stamped UTC-day bucket or `null`.
- `Mobile/src/screens/DelhiToday.tsx` — `latestDay` now returns `cityToday(data)`; the
  `Object.keys(days).sort().pop()` fallback is gone. On a zero-trip day the "what
  travellers did today" card renders nothing — never a stale bucket under a today title.
- Also renders the F8 qualifier under the section head (`cityTodayUtc`).
- Tests: `Mobile/src/api/city.test.ts` — stamped bucket returned; zero-trip day (`today:
  null`, yesterday populated) → `null`; empty days map → `null`; no trips block → `null`.

## F7 — "a line you set" was never set

- `Mobile/src/components/shell/settings.ts` — `ShellSettings` gained `profile_set: boolean`
  (default `false`). The only write is `App.tsx` `onHomeProfile` →
  `patchSettings({ profile: p, profile_set: true })`. No other path sets it.
- `Mobile/src/i18n/strings.ts` — new en+hi pairs: `budgetTitleSugg`, `budgetWithinSugg`,
  `budgetOverSugg`, `budgetQ{General,Sensitive,Child}Sugg`, `refBudgetSugg`,
  `weekDayPctSugg`. Each Sugg string calls the ceiling "a suggested reference" /
  "सुझाई सीमा" and discloses the WHO anchor and assumed breathing volume
  (216 = WHO 24-h 15 µg/m³ × ~14.4 m³; 72 = WHO annual 5 µg/m³ × ~14.4 m³;
  130 = 15 µg/m³ × ~8.6 m³ child volume). `you set`/`your` survive only on the
  post-pick strings (`budgetTitle`, `budgetWithin`, `budgetProfileQ`, …).
- `HomeScreen.tsx` — `BudgetCardInner` / `HeroBlockInner` / `WeekSheet` take `profileSet`
  and switch every affected string on it; no feature removed.
- Tests: `Mobile/src/api/honesty.test.ts` — every Sugg string (en+hi) discloses WHO +
  volume, never claims `you set`/`आपकी`; the `you set` claim survives only post-pick.

## F8 — public "today" is a UTC bucket, unqualified

- `server/community.html` — statusline gains "today = utc day · resets 05:30 ist" beside
  the counters; the ledger intro states "The 'today' rows count the UTC day — they reset
  at 05:30 IST."
- `server/city.html` — ticker labels "shared trips · utc day" / "km shared · utc day"
  (ledger head already said "counted since utc midnight — 05:30 ist").
- Mobile: `cityTodayUtc` ("utc day · resets 05:30 ist" / "utc दिन · 05:30 ist पर रीसेट")
  printed under the DelhiToday section head — the app's only aggregate-today surface.
- No stored history touched, no rebucketing.
- Tests: `honesty.test.ts` asserts the qualifier text in en+hi and that the served
  `community.html` / `city.html` actually print it where the counters render.

## F2 — search substitutes undisclosed

- `Mobile/src/search/t0.ts` — `PlaceResult` gained `match?: "name"|"place"|"category"|"area"`,
  `anchor?`, `compound?`. `query()` marks: kind-rows around a resolved anchor →
  `{match:"category", anchor}`; unit-ask rows satisfied by a re-anchored (different-area)
  scan or a partial satisfier → `{match:"area", anchor, compound:true}`; the anchor
  stand-in when units were asked but unsatisfiable → `{match:"area"}`; near-anchor name
  hits → `{match:"place", compound:true}`. Plain name hits stay unmarked.
- `Mobile/src/search/client.ts` — `RawRow`/`toPlace` carry the server's `match`/`anchor`/
  `compound` through untouched (server already emits them).
- `Mobile/src/screens/SearchScreen.tsx` — when the top row is `match:"category"` and the
  query carried a kind + name tokens, a `substNote` line prints
  `searchSubstCategory` ("nearby alternative — "{name}" not found"); when `match:"area"`
  with units asked, `searchSubstArea` ("area only — "{unit}" not found"). en+hi, polite
  live-region. No coords invented, no results renamed.
- Tests: `Mobile/src/search/subst.test.ts` — kind rows marked category+anchor; unsatisfied
  unit ask marked area; name hit unmarked; server metadata passes `client.ts` untouched.
- Test infra: `test-runner.mjs` gained a `react-native` data-URL stub so `client.ts`
  imports under node's strip-types; `client.ts` dropped its parameter-property
  constructor (same strip-types limit).

## F6 — CO₂ total vs phase-split basis mismatch — choice: disclosure

Picked the disclosure option, not a re-derivation: the split's phase shares come from
each trip's *plan-basis* `emissions.breakdown` (`nav/engine.ts:148,283–320`) while the
counted kg is measured along the actual ride. Computing a same-base split would mean
changing donation accounting — the finding explicitly forbids rewriting aggregates, and
the server can't reconcile historical rows. Minimal honest fix: name the bases where
the numbers print.

- `server/admin.html` — the CO₂ card now reads "co₂ from shared rides · mid estimate ·
  counted-basis" with cap "…integrated along each actual ride"; the split block is
  labelled "plan-basis shares — the counted kg above is measured along each ride, a
  different basis".
- Verified live basis on prod GET `/v2/city` (Oct-8 audit): total 1.988 kg vs split
  2952.1 g — the labels now state why they don't reconcile.

## Gates

- `npx tsc --noEmit` — clean.
- `npx expo lint` — clean.
- `node src/api/test-runner.mjs` — 37/37 pass (incl. new city + honesty suites).
- `node src/search/test-runner.mjs` — 12/12 pass (incl. new subst suite).

Not run: nav/offline suites (untouched by this lane), device rigs (no UI-runner need —
all fixes are copy/logic covered by the unit gates).
