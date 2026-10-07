# Lane report — home-truth: the ambient number's provenance + the lungs' calendar

Owner complaints (verbatim):
1. "the air around you — verified with my live location it's WRONG by a lot"
2. "what is it even showing, AQI or mixed index?"
3. "your daily budget is cringe — no Delhi guy will get it"
4. "your week = 0.2 — what the fuck is this number"
5. "hundreds of numbers nobody understands"
6. "week should be 'your lungs' calendar' → tap opens a gorgeous
   orgasmic weekly component"

Branch `base/v2`. Gates: `tsc --noEmit` clean, `expo lint` clean,
node:test store 84 / nav 76 / api 12 / offline 12 — 0 fail.
iOS sim verify on this mac — iPhone 17 sim `EDD9B083` (iOS 26.5),
`--configuration Release` build installed on-device, real location
(`simctl location … set 28.6315,77.2167` — Connaught Place), live prod
API (`EXPO_PUBLIC_API_URL=http://65.2.28.40`).

## 1. Where the number actually comes from (the audit)

`GET /aqi?lat&lon` (`server/main.py:1048`) is already a **kriged point
read** at the queried coordinates — `FIELD.value(lat,lon,"pm2_5")` over
27 real CPCB/DPCC stations + fill grid (`server/airfield.py:99`,
Kalman-debiased WAQI/CPCB/OpenAQ feeds). It is NOT a city mean and not a
nearest-station echo. The client already asks at the user's own GPS fix
when one exists (`App.tsx` `aqiPoll` ~L402, `getLastKnownPositionAsync`
→ `getCurrentPositionAsync`).

Live prod check (centroid, 07 Oct ~10:30 UTC): `pm25_ambient 62.7`,
`us_aqi 155`, `nearest_sample_km 1.8`, `field.age_s 139`.

So the "WRONG by a lot" is three lies of presentation, not the number:

- **Silent centroid fallback.** No GPS fix → the poll queries the Delhi
  centroid and the hero still said "the air around you".
- **Unlabelled forecast fallback.** `ambientUg` absent → the hero fell
  back to the day-curve's first non-null hourly point (a forecast
  cell-mid) while still saying "the air around you".
- **Unit confusion.** `62` is µg/m³ — the owner reads it against the
  AQI 154 other apps show ("mixed index?"). The same air, two scales —
  nothing on screen bridged them.

Fixes landed:

- New `AmbientMeta` prop (km to nearest instrument, `atGps`,
  `usAqi`, `beyondEdge`) threaded App.tsx `aqiPoll` → `HomeScreen` →
  hero, plus the `/aqi` field block's own `age_s`/`stale`
  (`mapField` reuse, already aged every frame).
- Eyebrow is now honest about source: live GPS → "the air around you";
  centroid fallback → "the air near central Delhi" + a hint line to
  turn location on; forecast fallback → "the air expected near you".
- Provenance line under the number: "read at your location · nearest
  live monitor ~1.8 km away" (or the edge case: "closest live monitors
  cover Delhi's core — this is their nearest read").
- Freshness line: "air reading: {n} min old" / stale copy — the same
  `fieldAgeLine` the forecast cards use (now shared via
  `components/shell/daywords.ts`).
- The "AQI or what?" answer sits under the figure: "PM2.5 dust per m³
  of air · same air = AQI {a} on other apps" (uses the served `us_aqi`,
  absent → plain "PM2.5 — fine dust per cubic metre of air, right now").
- Counted days get the dose gloss under the number: "µg = micrograms of
  fine dust your lungs took in — counted only when the app was with you".

## 2. "daily budget" and the bare numbers — killed/reworded (en + hi)

- `budgetTitle` "your daily budget" → **"your daily limit"**
  (hi: आपकी दैनिक सीमा).
- `budgetWithin` "{r} µg left of {b} today" → **"{r} µg left of the
  {b} µg you set for today"** — the number now names itself.
- `budgetOver` → "{o} µg over your {p} limit today".
- `budgetProfileQ` → "{b} µg is the most fine dust you want to breathe
  in a day — a line you set, not a medical rule" (now interpolates the
  live profile budget; BudgetCard passes `{ b: budget }`).
- `refBudget` "{p}% of your daily budget" → "{p}% of your daily limit"
  (hero share line).
- Week total: "{n} µg this week" was already labelled; the "0.2"
  complaint came from it showing an unexplained raw value — the sheet
  header now reads "≈ 2.6 µg this week · 1/7 days counted" and every
  surface gets a blank-day explanation line.

## 3. WeekStrip → "your lungs' calendar" + WeekSheet

- `weekTitle` → **"your lungs' calendar"** (hi: आपके फेफड़ों का
  कैलेंडर). The strip header is now a pressable affordance (chevron +
  `weekOpen` a11y label) — cell tap or header tap opens the sheet.
- New `Mobile/src/components/shell/WeekSheet.tsx` — bottom-sheet grammar
  copied from ReceiptSheet (spring rise, warm scrim, grab handle, X).
  - **The calendar**: 7 real day cells — weekday letter over the serif
    date numeral over a dose bar over ≈µg. Cells wash in the day's dose
    severity vs the user's own limit (`doseTierIdx` — same rule as the
    strip). Blank days stay neutral and empty, never zeroed.
  - **The picked day**: weekday + date head, serif dose line
    ("you breathed ≈N µg that day"), "% of the daily limit you set",
    covered-minutes, the real `HourArc` (past days `nh={-1}`), parts
    chips — the exact truth the strip's old inline expander served.
    Thin days get the honest thin copy ("a thin read — too few hours
    logged…" — reworded: a small count can sit in the cell).
  - **The air ahead**: the folded forecast (`data.outlook`) as a second
    ghosted row — day label, band dot + mid µg/m³, partial-hours "~Nh",
    least-bad/cleanest marks, `confidence:"lo"` dimming, the served
    verdict caption, and the unit line "µg/m³ — expected fine dust per
    cubic metre of air". Forecast cells wear the day's air band — a
    different meaning than dose cells, kept in a different section.
  - **Footer**: "only real readings land here — a blank day is a day
    the app wasn't with you, never a zero" + the forecast's own field
    age.
- Shared copy helpers extracted to `components/shell/daywords.ts`
  (`fieldAgeLine`, `dayLabel`, `compactHours`, `outlookCaption`,
  `DAY_LABEL_KEYS`) — HomeScreen imports them now instead of defining
  them; WeekSheet + DaysAheadCard speak identical words.

## 4. Verification

- Build: `npx expo run:ios --configuration Release --no-build-cache`
  → **0 errors**; installed + launched on `EDD9B083`, no crash.
- Home (live GPS): "the air around you / 62 µg/m³ / moderate /
  PM2.5 dust per m³ of air · same air = AQI 154 on other apps /
  4.1× the WHO daily limit / read at your location · nearest live
  monitor ~1.8 km away / air reading: 10 min old" — shot:
  `home-truth-shots/home-1.png`.
- Cold-launch ordering verified live: before the first fix lands the
  hero flashed "location is off or hasn't locked yet…" (the honest
  fallback), then upgraded to "the air around you" once GPS landed.
- WeekSheet open on strip tap: calendar with real date numerals,
  selected-today accent edge, "≈ 2.6 µg this week · 1/7 days counted",
  thin-day honest state, "the air ahead" row (today 62 least-bad · ~2h,
  tomorrow 84, fri 162, sat 130, sun 138 — band-washed), verdict +
  unit line + honesty footer — shot: `home-truth-shots/weeksheet-1.png`.
- Budget card scrolled to: "your daily limit / 213 µg left of the
  216 µg you set for today" — shot: `home-truth-shots/home-3.png`.
- Retitled strip on home ("your lungs' calendar" + chevron +
  "≈ 8 µg this week") next to the move card + day card:
  `home-truth-shots/home-strip.png`.
- Counted hero (after ~12 min of samples landed): "you've breathed
  today / 8 µg / good / 4% of your daily limit / 12m counted · outside
  ~62 · moderate / µg = micrograms of fine dust your lungs took in —
  counted only when the app was with you":
  `home-truth-shots/home-counted.png`.
- Picked a never-counted day in the sheet (Friday 2 Oct): accent edge
  moved, honest empty reads "a thin read — too few hours logged to
  tell this day's story": `home-truth-shots/weeksheet-pickedday.png`.
- A11y: sheet scrim no longer announces a duplicate "Done" button
  (accessible=false; the X owns it).

## 5. Honest limits / not done

- The forecast-fallback path ("the air expected near you" +
  "expected PM2.5 per m³ of air — the forecast cell, not a live read")
  fires only when `/aqi` fails but `/v2/day`/`/grid` succeeded — not
  exercised on-device (prod was healthy); logic reviewed.
- `pm25` (smoke-modified) vs `pm25_ambient` (raw field): hero keeps
  preferring ambient — same policy as before; the smoke blend still
  feeds the dose samples (`bz` in the poll).
- WeekSheet needs ≥1 counted day in the window to appear (the strip
  unmounts below that — unchanged rule).
- hi strings are first-pass human translations — a native speaker pass
  would tighten a few compounds.
