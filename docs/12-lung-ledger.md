# 12 — The Lung Ledger

The retention layer: trips are not one-off answers, they accumulate into
a personal exposure account. Every picked option in the compare sheet
writes one ledger entry on-device (expo-file-system, `ledger.json` —
no account, no cloud, private by construction).

## On the sheet

- **today µg** — summed inhaled PM2.5 dose for the calendar day (IST).
- **cigarette-equivalents** — `todayUg / 316`. Berkeley Earth rule of
  thumb: 22 µg/m³ ambient over a day ≈ 1 cigarette; at ~14.4 m³/day
  inhaled volume that is ≈316 µg of inhaled PM2.5 per cigarette.
  This is the number every judge/user instantly understands.
- **daily budget** — `todayUg / 216` as a %. WHO 2021 24-hour PM2.5
  guideline (15 µg/m³) × ~14.4 m³ inhaled/day = ~216 µg. Honest framing:
  it is a *reference budget*, not a medical threshold — the UI says
  "~216 µg daily budget", never "safe".
- **avoided µg** — `worst option dose − chosen dose` per trip, summed
  today and all-time. The measurable impact number for judging:
  "this user inhaled N µg less PM2.5 this week" is real and countable.
- **streak** — consecutive calendar days under budget.
- **trip rows** — today's logged trips, each with its µg.
- **24h curve** — decade-typical diurnal medians at the destination
  (GET /today → station×month×hour IST medians over 9.04M measurements),
  current IST hour highlighted. Answers "is now unusually bad?" at a
  glance.

## Dedupe

`logTrip` drops a write when the same from+to+vehicle was logged within
10 minutes — selecting an option to draw its route isn't a new trip.
Caps at 500 entries.

## Why this is the product, not a feature

Google Maps moves you. ALive-108 moves you *and keeps score on your
lungs*. The dose engine answers "which way"; the ledger answers
"what did today cost me" — the reason to open the app daily.
