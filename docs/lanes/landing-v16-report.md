# landing lane v16 — real 4-feature story + deeper section split

Owner steer: "refine it more cause it's too shit still" + wire the real
product into the feature story. base/v2 HEAD pulled (past 66c0c8e).

## Product story — real frames now

Feature sections retold with the app's actual four:
- 002 the home — "Know the air where you stand." (ios-dose.png)
- 003 the chooser — "Every route, priced in lungs." (ios-choose-priced.png)
- 004 the stay — "Sleep where the air is kindest." (ios-feat-stays.webp — NEW)
- 005 the hour — "Go out when the air lets up." (ios-feat-playtime.webp — NEW)

Dropped: the ledger + the week frames (ios-feat-trips/week now unused).
Story reads count → route → stay → hour.

## Vertical components — one idea per section

- District leaderboard split OUT of the record card into its own
  numbered section (lbl2 "the districts" + "Where the air sits
  heaviest.") — was buried bottom of a two-idea card.
- Privacy pledge split OUT of the mechanics card into its own section
  (lbl2 "what leaves your phone" + "Counted on your phone. Kept on
  your phone.") — one idea per viewport.
- `.dist-sec`/`.pledge` redundant hairlines removed in their new homes.
- `.story-cause` chip box de-boxed (border/radius/padding → plain mono).
- 15 numbered components now; page @1440 height 9757.

## Verify

- 8/8 landing + inline tests.
- Shots @1440 (stays, playtime, districts, mechanics, pledge, journal,
  doors) — all paint, 0 console errors, live readout 89.6 µg/m³.
- Standalone assets copied to branch roots: hero-delhi-smog.webp,
  ios-choose-priced.png, ios-dose.png, ios-feat-stays.webp,
  ios-feat-playtime.webp (trips/week dropped — unreferenced).

## Pushes

- base/v2 — landing.html + this report + shots.
- main + landing — index.html + new ios-feat-*.webp at root.
