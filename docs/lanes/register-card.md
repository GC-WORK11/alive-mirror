# Register card — ALive-108 mobile (post app-overhaul-v2)

One screen of truth for the component register — the light-theme
"chunky colorful components" language: one hero per screen, tinted
one-idea cards, icon-tile doors, pill grammar, mini-word labels
(number + unit + ≤3-word label does the talking). Source of values:
`Mobile/src/theme.ts` (V2T / V2Tint / V2Elev / V2Type / V2Radius / fam*
are the contract — names + keys stable, values may move). Landing pages
(`server/landing.html`, `city.html`, `admin.html`) carry the same
register in CSS vars — web siblings track this file, not a fork.

## Grammar — the 10 decoded patterns

1. **Hero per screen** — exactly one big serif numeral owns every
   surface (dose µg, city µg/m³, trip count). Everything else is
   component-scale.
2. **One-idea cards** — each card carries one thought (the move, the
   days ahead, how you felt, your budget). No dashboard grids.
3. **Tinted surfaces** — a card CAN wear a wash: band wash for data,
   `V2Tint` wells for identity. Colour lives ON components — the app
   itself is never repainted.
4. **Icon-tile doors** — feature doors are tinted squares with a glyph +
   label (map/forest, city/sky, trips/clay), not list rows.
5. **Pill grammar** — selections are pills (ink fill for primary,
   tinted wash for selectable groups); tabs are segmented pills.
6. **Mini-words** — `number + unit + ≤3-word label`; prose is rationed
   to one-line qualifiers. Eyebrows carry section names.
7. **Single-CTA heroes** — one ink pill per screen leads the eye
   ("Where to?", "Start", "Done"); secondary actions stay quiet.
8. **Honest empties** — no data is a designed state (sparse hero,
   empty ledger, no-streets city) — never fake fills, never blank.
9. **Component rows** — ledger rows / option cards / settings rows are
   designed objects: tinted icon tile + name + one stat + one qualifier.
10. **Colour = identity or data, never decoration** — a band hue still
    means pollution; a tint well means component identity; ink means
    action. Nothing else.

## Surfaces — the ladder, and when translucency is allowed

| step | token | value | where |
|---|---|---|---|
| paper | `V2T.bg` | `#FAFAF7` | canvas, **all full-screen sheets + drawer + receipt** |
| card | `V2T.surface` | `#FFFFFF` | cards resting on paper/sheets |
| raised | `V2T.surface2` | `#F3F2EC` | inputs, pressed rows |
| top flat | `V2T.surface3` | `#EBE9E1` | floating controls |
| scrim | `V2T.scrim` / `scrimDeep` | ink 42% / 58% | dims behind every sheet — *carries* the dim, not the pane |

**Sheet-surface rule:** any pane that covers *content* — DelhiToday,
ledger, settings, search, vehicle wizard, sidebar, receipt — is **solid
`V2T.bg`** with a `hairline` edge. Translucency
(`glass`/`glassDeep`/`glassSoft`/`glassFaint`/`glassSel`/`glassEdge`/
`glassLine`) is reserved for chrome that keeps the *map* legible:
search bar, FABs, chips, DayPeek card, compare sheet, HUD tiles.
A content-bearing pane that lets the layer beneath ghost through reads
as a rendering bug, not frost.

## Ink + hairlines

| token | value | use |
|---|---|---|
| `text` | `#16181D` | ink — headings, owned numerals |
| `text2` | `#4A4E57` | labels, meta |
| `text3` | `#8A8D94` | weakest ink that still reads |
| `text4` | `#A6ACB8` | empty states only |
| `line` | `#E4E1D8` | dividers |
| `hairline` | `#D8D5C9` | crisp card/sheet edge |
| `ink10` | ink 10% | overlay hairline |

## Accent + tint wells + data colour

- `accent #3A6844` / `accentInk #2B4E32` / `accentWash #EAF0E4` /
  `accentTint #DCE7D1` — **forest, not olive**: the muted-expensive
  discipline (deep, saturated, classy). The only non-data hue; fills the
  primary CTA ink is reserved for (`Where to?`, `Start`, `Done` are ink,
  not accent — accent is identity, not action).
- **`V2Tint` component wells** — pastel identity colours that are NOT
  the CPCB ramp: `forest` (map/go doors), `sky` (city surfaces), `clay`
  (trips/ledger), `sand`, `plum`. Each well = `{wash, ink}`: a deep hue
  pulled ~80% toward paper, plus its readable glyph ink. Colour here
  means *component identity*.
- `band0..5` = `#7AAB59 #C8B25A #D58C4A #B85442 #8F3C49 #6E3C54` — the
  ONLY data colour (CPCB breaks `[30,60,90,120,250]`).
- Washes blend solid toward white, never alpha: `bandWashIdx` 90%
  (cell fills), **`bandWashMidIdx` 82% (tinted hero cards — a card
  carries the day's band)**, `bandWashDeepIdx` 74% (tile fills that
  must scan), `bandEdgeIdx` 60%, `bandInkIdx` 15% (band-coloured text).
- `breath1..3` = `#D58C4A #B85442 #8F3C49` (smoke you breathe),
  `out1..3` = `#4A4E57 #8A8D94 #A6ACB8` (smoke your ride puts out),
  `pinDest #B85442`.

## Type + numerals

- Ramp `V2Type`: micro 11 · label 13 · secondary 15 · body 17 · title 22
  · display 30 · hero 44 · heroXL 62.
- Voices: **Fraunces** serif display (`famSerif`), **Inter** body
  (`fam`), **IBM Plex Mono** every numeral + eyebrow (`famMono`, `NUM`
  tabular-nums; `famMonoText` for mono-styled localized text). Hindi →
  Noto Sans Devanagari all slots.
- **Numerals own their card**: dose hero ≈88 serif; stat heroes
  `display`; the unit is a bare `µg` (the `(micrograms)` gloss lives on
  the peek card, not the hero). Cell numerals full ink — band ink is
  for the band *cue* (wash, dot, label), not the figure.

## Radius · elevation · motion

- `V2Radius`: **row 13 · card 20 · sheet 24** · pill 999 — the chunky
  register; cards read as designed objects, not table cells.
- `V2Elev`: card (2/.10/8/+2) · float (5/.16/12/+3) · sheet
  (12/.18/24/−4, cast up) · pop (18/.22/30/−6). Warm-ink shadow; flat
  fills do the lifting, shadows stay low.
- Motion: RN `Animated` only — `pressFx` (opacity .78 · scale .985) on
  every tappable card; sheet enter spring `damping 22 / stiffness 220`;
  drag-dismiss spring-back same tune; `FadeIn`/`CountUp` for mounts +
  counters; `camDur` is 0 on sim (MapLibre SIGSEGV guard). Physics on
  real interactions only — no decorative animation. No new libs.

## Do not

- No cyberpunk / neon / glow / retro, no 3D renders or decorative SVG
  art, no lime-slime / chocolaty-green / cheap-yellow — violations are
  regressions.
- No gradients, no glass-morphism blur, no dashboard metric grids, no
  emoji.
- No repainting the app: colour goes on components (wash, tile, pill),
  never full-bleed pages or chrome.
- No mid-word truncation: qualifiers (`· your usual`, `· least-smoke
  alt N`) are nested dim runs that wrap whole — never `· y…`.
- No system-font fallback: every `Text`/`TextInput` carries
  `fam*`/`famSerif`/`famMono*` explicitly.
