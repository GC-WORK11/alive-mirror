# Lane report — daycount-honesty: the numbers sweep

**Claim under test:** "hundreds of numbers at different places and nobody
understands what they mean" (owner). Sweep = every number/percentage/fraction
the app can render, audited for (a) is the unit+meaning self-evident in place,
(b) is it real — traced to data, not derived-from-derived.

- **Repo/branch:** `<owner>/Delhi-Air-108` @ `base/v2`
- **Method:** grepped every render site of `Math.round|approx|doseUgRound|
  fmtUg|fmtKg|fmtKm|fmtCig|×|%|×|/day|streak|stage|bench| ppm|kg|km|min|cig`
  across `Mobile/src`, then traced each to its data source (wire field, ledger
  recompute, or hardcoded constant) and checked what the user sees around it.
- **Gates:** `npx tsc --noEmit` clean, `npx expo lint` clean,
  `node src/{store,nav,api,offline}/test-runner.mjs` all green.

## Fixes landed (confusing-but-real → plain words)

| # | where | before | after | why |
|---|---|---|---|---|
| 1 | `dayArcAir` (HourArc scrub readout) | `"2pm · air ~180"` | `"2pm · air ~180 µg/m³"` | {c} is ambient µg/m³; bare, it read as the same dose-µg the hero counts |
| 2 | `homeOutsideNow` (hero stat row) | `"outside ~180 · poor"` | `"outside ~180 µg/m³ · poor"` | same twin-unit trap — it sits beside "≈42 µg breathed" |
| 3 | `weekCountedFine` (WeekSheet header) | `"180 µg this week · 3/7 days counted"` | `"… · 3 of 7 days counted"` | "3/7" parses as a date or a score, not a count |
| 4 | WeekSheet cell a11y | `"M 42"` (bare) / `"M 0"` (empty day) | `"M, ≈42 µg"` / `"M, nothing logged"` | VoiceOver read a unitless number; empty days spoke a fake zero. Mirrors WeekStrip's grammar |
| 5 | `weekDayDose` (WeekSheet picked-day line) | `"you breathed ≈≈ 5.2 µg that day"` | `"you breathed ≈ 5.2 µg that day"` | the template's literal `≈` stacked on `approx()`'s own mark — caught on sim, removed the literal |
| 6 | `ledger.stats()` | `streak`/`budgetPct`/`budgetUg` computed vs hardcoded `216` | same fields take the caller's profile budget (`budgetUg` param, default unchanged) | latent lie: a 72-µg "sensitive" day over 72 would have streaked "under budget". Dead fields today — fixed before they surface |

All string changes carried en + hi (hi: `"बाहर ~{n} µg/m³ · {w}"`,
`"{h} · हवा ~{c} µg/m³"`, `"{m} में से {n} दिन गिने"`). Fix 5 needed the same
de-literal on the hi twin (`"उस दिन आपने {n} µg साँस में लिया"`). Other
`≈{…}` templates were audited call-site by call-site — `dayArcDose`,
`dayMorning*`, `dayOutlookRange`, `cityTravellersLine*` all pass bare
numbers (`doseUgRound`/`Math.round`/`fmtCig`/`fmtKg`), so their literal `≈`
is the only mark.

## Suspects from the brief — resolved honest

- **Compare-ladder %:** `chooser_lessVsFastest` = one served ratio
  `(1 − selDose/foDose)×100`, gated ≥4%, base named ("than fastest"). Real.
- **"up to 5× more" plan-picker flag:** no live UI string carries a baseless
  ×-claim. Every × form names its base: `compare_feltMore` "~2.4× more
  inhaled than metro" (× gated ≥2, else falls back to absolute
  `+{n} µg more than {m}`), `receipt_lessVs` "about {n}× less smoke than by
  {m}", `dayMorningMove` "…breathes ~{x}× lighter than at {g}",
  `notify_departure_body` "~{p}% less smoke than the smoky hours".
  The 5.3× figure is a server comment constant (`server/exposure.py:13`,
  rickshaw-vs-metro per-km), not a rendered claim.
- **day-count/streak semantics:** `streak` was dead code *and* computed
  against the wrong budget — see fix 6. `dayCovered` "{h}h {m}m counted" is
  honest (phone-logged coverage); the hero gloss `homeDoseWhat` says in place
  what "counted" means.
- **offline "N min old":** already fixed (`fieldAgeCompact`); verified —
  `FreshnessChip` and `AirMapCard` both render it verbatim.
- **settings dose-goal %s:** `weekDayPct` "{p}% of the daily limit you set" and
  `refBudget` "{p}% of your daily limit" both name the base; BudgetCard's
  `budgetProfileQ` states the µg value in the same card ("{b} µg is the most
  fine dust you want to breathe in a day"). Honest.
- **settings toggles w/ unactionable numbers:** none found — settings numbers
  are provenance (`~{n} km` to nearest instrument, app version) or labelled
  user inputs (PUC `CO %`, `HC ppm`, `smoke %` with range limits).

## Inventory — every number the app can show

All verified real (wire field, ledger recompute, or cited constant) unless
flagged in §fixes/§dead. "Plain" = unit+meaning self-evident in place.

**Home hero (counted day):** `≈{n} µg` dose (reconstructed covered dose);
`{p}% of your daily limit` / `{x}× the WHO daily limit` ref line (both named
bases); `±{n} µg vs yesterday` absolute delta; `{h}h {m}m counted`;
`outside ~{n} µg/m³ · {w}` (fix 2); sparse progress = 3 segments +
`daySparseCount` label; `~{k} km` monitor provenance.
**BudgetCard:** fill vs `{b} µg`; "{r} µg left of the {b} µg you set" /
"{o} µg over your {p} limit"; profile segments (no numerals); basis footnote.
**DayPeek:** `≈{n}` + `µg` unit; `now ~{n} µg/m³` ambient; 7 week dots
(colour = dose tier, no numerals).
**WeekSheet:** `{n} µg this week` header; `{n} of 7 days counted` (fix 3);
cells ≈N dose numerals (unit context = the sheet header; a11y carries the
unit — fix 4); picked day `≈{n} µg that day`, `{p}% of the daily limit you
set`, `{h}h {m}m counted`, parts chips `≈{n} µg`; forecast cells bare + the
`weekAheadUnit` gloss "µg/m³ — expected fine dust per cubic metre of air".
**WeekStrip:** same cell grammar; a11y "letter, ≈N µg / nothing logged".
**HourArc:** scrub `≈{n} µg · {h}` (dose) / `{h} · air ~{c} µg/m³` (fix 1) /
`{h}` flat; tick labels are hour positions, not values.
**CompareSheet:** per-option `≈{mid} µg` + `{lo}–{hi}` / `up to {n}` /
`{lo}+` band (unit sits beside the numeral); felt gap `~{x}× more inhaled
than {m}` ≥2× else `+{n} µg more than {m}`; `{km} · arrive {t} · board→alight`
meta; `howWe_in/out/conf/coverage` provenance ("only the {pct}% inside it is
counted"); emissions `{kg CO2}`/`{g PM2.5}` bands; `chooser_lessVsFastest`
"{n}% less smoke than fastest"; `departSavedPct` "→ ~{n}% less smoke — ping
me" (verbatim-served percent — see caveats); `bandScale` a11y "position {n}
of 6".
**Receipt:** `≈{n} µg` dose + `about {lo}–{hi} µg` band; `{n}× less smoke
than by {m}` or plain-fraction "a third of {m}"; `+{n} µg saved`;
`≈{n} cigarettes` (opt-in); `{lo}–{hi} g of fine dust` emitted PM;
`{n} km` / `{n} min`; `{n} kg`/`{n} g` put out incl. per-rider breakdown;
`{n} min ago` field age; "under 100 m — nothing counted" threshold.
**NavChrome:** `{min} min · {km} km left`; `in {d} metres — {i}`; live `≈{n}
µg` counter + `{n} kg`/`{n} g` emit + `≈{n} cigarettes` (opt-in); honest
`strip_unavailable`/`navNoGps`.
**DelhiToday:** hero `{n} µg` day-inhaled + `cityHeroUnitUg` + likely
`{lo}–{hi}` range; `{x}× the WHO daily limit` / `within…`; `~{n} µg/m³` city
average now; cigarettes secondary (opt-in); species tiles mean + `WHO limit
{n}` per gas (µg/m³ stated in the section note) + `US AQI` on its stated
0–500 scale; `{p}% below/above the 10-year average for this hour ({med}
µg/m³)` — names the base AND gives its value (the gold standard); next-12h
bars bare `µg/m³` gloss in `cityForecastNote`; `{n} live stations counted
in`; `{n} trips`/`{km} km`/`≈{cigs} cigarettes`/`≈{kg} kg` traveller
aggregates (k≥3); `{n} streets measured over {h} hours`; `+{n} more trips
stay private — fewer than {k}`; `typical trip ≈{p50}`; `{n} trips took a
lighter way`.
**Ledger:** per-trip `≈{n} µg` / `about {lo}–{hi} µg` / `{n} kg put out` /
`{n} µg less than the smokiest way` / `≈{n} cigarettes`; week sum `≈{n} µg`
+ `≈{n} kg`; all-time breathed/put-out sums; `est` honesty labels.
**Sidebar:** `{n} min/hr/day ago` recency; `{p}% less/more than yesterday`
(named base).
**Settings:** `~{n} km` instrument distance; PUC `CO %`/`HC ppm`/`smoke %`
user readings; `one dot per 100 m, rounded to ~11 m`; `3+ different devices`;
version; 1–5 rate stars.
**Onboarding/Welcome:** `3+` k-card numeral; `page {n} of {m}`; live ambient
`{n}` + `live · the air here, this hour` provenance or the `never faked`
empty state.
**Check-in lens:** `{n} days in — no pattern yet`; `~7 days` threshold; the
`your rough {f} follow heavy-smoke days` link is computed from real logged
pairs, not asserted.
**DepartGraph:** `leave {h} ≈ {n} µg` per hour; `lightest around {time} —
≈ {n} µg`; `{n}h` axis ticks.
**Notifications:** `{f}× stiller than usual`; `clearing at ~{p}% of its usual
pace`; `reads like GRAP stage {s} of 4 — our estimate, not the official
call`; `{a} → {b} fires`; `{kmh} km/h` wind; `{a} over ~{h}h` belt deltas;
departure/reflect bodies all served-or-ledger numbers.
**Search:** `{n} m/km away` distances; `{n} m away — basically here`.
**Vehicle/PUC:** instrument fields with % / ppm units in-label, hard range
caps.

## Catalogue — numbers that could not be honestly explained

**None rendered.** No fake or unexplainable number reaches the UI. The
leftovers are all dead code, catalogued (not removed — owner rule):

| item | status | note |
|---|---|---|
| `streak`, `budgetPct` in `ledger.stats()` | dead fields | never rendered anywhere (grep-verified); the hardcoded-216 bug fixed pre-emptively |
| `compare_vsLightest` `"+{n} µg vs lightest"` | dead key | no render site |
| `daySparseSamples` `"{n} of {m} readings"` | dead key | superseded by `daySparseCount` |
| `noteStagVc` `"{vc} m²/s vs ~3,000 typical"` | dead key | superseded by `noteStagPct`; kept for stale-wire compat per its comment |
| `homeOfBudget`, `daySparseAir`, `shareTripBody`, `nav_dose`, `sub_counted`, `arrivedLine` | dead keys | no render sites; `share` is a stub button |
| `BUDGET_UG = 216` in `ledger.ts` vs `PROFILE_BUDGET_UG.general` in `settings.ts` | duplicated constant | one source of truth would prevent drift |
| `hour ${h.hour}` a11y in HourArc | i18n gap | English literal; un-translated — cosmetic, not a lie |

## Caveats (honest-but-shaky, watch list)

- **`departSavedPct` / `notify_departure_body` percents** are taken verbatim
  off the wire (`pct_less_vs_now`, documented 2.5×-overstatement caveat in
  `api/depart.ts`). If the server percent is ever wrong, the UI shows the
  wrong-but-labelled number — flagged for the server lane, not masked here.
- **`{x}× the WHO daily limit`** compares a point-in-time ambient read to a
  24-hour guideline — same convention AQI apps use; the base is named. Kept.
- **US AQI tile** carries its own "0–500 scale" note so it can't read as
  µg/m³; verified.

## Verification

- `tsc --noEmit`: clean. `expo lint`: clean. `test-runner.mjs` ×4: all pass.
- en + hi parity enforced by the `Record<StringKey, string>` compiler gate.
- **iOS sim (device EDD9B083, dev client `com.anonymous.app`, prod API
  `http://65.2.28.40`):** logged real coverage by setting sim location at
  3 Delhi spots ≥70 s apart so the 60 s `/aqi` poll landed ≥3 samples —
  the counted hero rendered. Verified on screen:
  - fix 2 — hero stat row reads **"outside ~68 µg/m³ · moderate"** beside
    "≈5.2 µg" breathed (unit travels with the ambient number now)
  - fix 3 — WeekSheet header reads **"≈ 5.2 µg this week · 1 of 7 days
    counted"** (was "1/7 days counted")
  - fix 5 — picked-day line reads **"you breathed ≈ 5.2 µg that day"**
    (double-≈ gone; this is the bug the sim caught)
  - HourArc scrub on a covered hour: **"≈5.2 µg · 5pm"** — `dayArcDose`
    correct. `dayArcAir` (fix 1) only renders for a covered-but-zero-dose
    hour — `conc` exists only where coverage exists (`daylog.ts:281`),
    i.e. a genuinely clean covered hour, which Delhi doesn't give on a
    hackathon day. Path verified by inspection; the string change itself
    is one unit token.
  - hero µg gloss, "2% of your daily limit", "7m counted", BudgetCard
    "211 µg left of the 216 µg you set", forecast "µg/m³" section unit +
    per-day gloss "average ~79 vs ~129 µg/m³ across the 5-day forecast" —
    all named-base, verified.
- Screens: `/tmp/sim6.png` (hero + fix 2), `/tmp/sim8.png` (WeekSheet fixes
  3 + 5). Build on this VM required fresh `npm install` + `pod install`
  (CocoaPods 1.17/Ruby 3.4 needed `LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8`)
  + `npx expo run:ios`.
- **Not verified on sim:** hi render (English default per design law —
  strings parity-checked at compile time, not eyeballed).
