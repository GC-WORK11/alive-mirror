# Lane report — iOS landing captures re-shoot (Oct 8)

**Brief:** owner's call — "the app iOS demos are so freaking bad". Re-capture the product screens at their best moments for the landing's numbered feature sections. High-res device captures (1206×2622 simctl, not windowed), clean state, same filenames so landing refs don't break.

**Rig:** iPhone 17 sim `EDD9B083-63F1-44E6-9A7B-0A6964CC2561` (iOS 26.5), Expo dev client `com.anonymous.app` pointed at prod `EXPO_PUBLIC_API_URL=http://65.2.28.40`. Captures via `xcrun simctl io <udid> screenshot`. Raw frames in `~/vidrig/ios-shots/` (not committed — they are 1-2 MB png intermediates).

## Seeded state (same believable-week seed as the vid lane)

- `ledger.json` — 10 trips ≈152 µg this week (auto/metro/walk mix, honest ranges, emit_kg, donated)
- `daylog.json` — ~2.6 h ambient samples ≈88-94 µg/m³ so the dose reads ~80 µg, "3h counted"
- `vehicle.json` — car/petrol/2017-2020 (clears the "what do you ride" gate)
- consent/welcome/settings flags seen — zero dialogs on camera

## Shot → asset map

| landing asset | section | raw frame | what's on it |
|---|---|---|---|
| `ios-dose.{png,webp}` 720×1566 | the home | `01-home-hero.png` | 86 µg giant numeral, moderate band, 40 % of daily limit, "3h 8m counted · outside ~90", live "18 fires in the Punjab—Haryana belt" field note, door rows |
| `ios-choose-priced.{png,webp}` 720×1566 | the chooser | `02-chooser-deltas.png` | CP trip priced on foot: ≈33 µg (16-49 honest range), **~20.5× more inhaled than car** delta line, alt 2 ≈34 (~20.9×), Start CTA |
| `ios-feat-trips.webp` 662×1440 | the ledger | `04-trips-ledger.png` | 10 trips ≈152 µg breathed, ≈26 kg put out, "honest ranges, never fake-exact", last-7-days dot chart, today/yesterday rows with "≈N µg less than the smokiest way" |
| `ios-feat-week.webp` 662×1440 | the week | `03-drawer-week.png` | ALIVE drawer: today ≈9.6 µg (29 % less than yesterday), FSSMTWT week bars, "10 trips · ≈152 µg", saved places + trip preview |
| `ios-feat-stays.webp` 662×1440 | *new — spare* | `06-stays-ranked.png` | ExploreSheet stays: "near Lodhi Garden", 5 hotels ranked lightest-air-first, each with ~100 µg + "N µg lighter" delta |
| `ios-feat-playtime.webp` 662×1440 | *new — spare* | `07-playtime-curve.png` | verdict "least-bad window 13:30-17:30 today ~84 µg/m³ avg — 9 lighter than now", banded 24 h bar curve, heaviest run ~144, open/shut guidance |
| `ios-feat-airmap.webp` 662×1440 | *new — spare* | `08-airmap-readout.png` | 53 live stations legend, redder=worse scale, tap-readout "91 µg/m³ — poor · this spot", "your day so far ≈86 µg" strip |

The three `ios-feat-{stays,playtime,airmap}` frames aren't referenced by landing.html yet — captured per the brief's 5-shot list so the landing lane can wire them as the page grows. **All three have registered FileResponse routes** (server/main.py `_ios_shot_route` block) — no 404 trap.

## Why these beat the old shots

- Old dose shot: 14 µg, "good" band — flat, unthreatening, no story. New: **86 µg moderate, 40 % of limit, fires note** — the product's whole premise in one glance.
- Old chooser: mode rows without the delta. New: the **20× multiplier** is the money shot.
- Old ledger/week: thin stats. New: honest ranges + per-day bars + smokiest-way deltas.

## Verification

- `sips` on every shipped file — exact dims (720×1566 png+webp; 662×1440 webp).
- Landing refs on base/v2: `/ios-dose.webp|png`, `/ios-choose-priced.webp|png`, `/ios-feat-trips.webp`, `/ios-feat-week.webp` — all filenames preserved, zero landing.html edits needed.
- Routes: png+webp for choose*/dose names; webp-only for all five `ios-feat-*` names.

## Not done

- Landing video NOT re-filmed — landing lane is restructuring the page (per orders).
- `ios-choose-verdict`/`ios-choose-bold`/`ios-choose-*` png+webp pairs left as-is (still referenced by older markup paths).
