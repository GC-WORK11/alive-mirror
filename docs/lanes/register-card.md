# Register card — ALive-108 mobile (post vibe-polish)

One screen of truth for the paper/ink register. Source of values: `Mobile/src/theme.ts`
(V2T / V2Elev / V2Type / V2Radius / fam* are the contract — names + keys stable,
values may move). Landing pages (`server/landing.html`, `city.html`, `admin.html`)
carry the same register in CSS vars.

## Surfaces — the ladder, and when translucency is allowed

| step | token | value | where |
|---|---|---|---|
| paper | `V2T.bg` | `#FAFAF7` | canvas, **all full-screen sheets + drawer + receipt** |
| card | `V2T.surface` | `#FFFFFF` | cards resting on paper/sheets |
| raised | `V2T.surface2` | `#F3F2EC` | inputs, pressed rows |
| top flat | `V2T.surface3` | `#EBE9E1` | floating controls |
| scrim | `V2T.scrim` / `scrimDeep` | ink 42% / 58% | dims behind every sheet — *carries* the dim, not the pane |

**Sheet-surface rule (this lane):** any pane that covers *content* — DelhiToday,
ledger, settings, search, vehicle wizard, sidebar, receipt — is **solid `V2T.bg`**
with a `hairline` edge. Translucency (`glass`/`glassDeep`/`glassSoft`/`glassFaint`/
`glassSel`/`glassEdge`/`glassLine`) is reserved for chrome that keeps the *map*
legible: search bar, FABs, chips, DayPeek card, compare sheet, HUD tiles.
A content-bearing pane that lets the layer beneath ghost through reads as a
rendering bug, not frost.

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

## Accent + data colour

- `accent #4D7C0F` / `accentInk #3D610A` / `accentWash #EEF2E2` / `accentTint #E3E9D3` — the only non-data hue.
- `band0..5` = `#7AAB59 #C8B25A #D58C4A #B85442 #8F3C49 #6E3C54` — the ONLY data colour (CPCB breaks `[30,60,90,120,250]`).
- Washes blend solid toward white, never alpha: `bandWashIdx` 90%, `bandWashDeepIdx` 74% (cell fills that must scan), `bandEdgeIdx` 60%, `bandInkIdx` 15% (band-coloured text).
- `breath1..3` = `#D58C4A #B85442 #8F3C49` (smoke you breathe), `out1..3` = `#4A4E57 #8A8D94 #A6ACB8` (smoke your ride puts out), `pinDest #B85442`.

## Type + numerals

- Ramp `V2Type`: micro 11 · label 13 · secondary 15 · body 17 · title 22 · display 30 · hero 44 · heroXL 62.
- Voices: **Fraunces** serif display (`famSerif`), **Inter** body (`fam`), **IBM Plex Mono** every numeral + eyebrow (`famMono`, `NUM` tabular-nums; `famMonoText` for mono-styled localized text). Hindi → Noto Sans Devanagari all slots.
- **Numerals own their card**: dose hero ≈88 serif; stat heroes `display`; cell numerals full ink — band ink is for the band *cue* (wash, dot, label), not the figure.

## Radius · elevation · motion

- `V2Radius`: row 8 · card 12 · sheet 20 · pill 999.
- `V2Elev`: card (2/.10/8/+2) · float (5/.16/12/+3) · sheet (12/.18/24/−4, cast up) · pop (18/.22/30/−6). Warm-ink shadow; flat fills do the lifting, shadows stay low.
- Motion: RN `Animated` only — `pressFx` (opacity .78 · scale .985) on every tappable card; sheet enter spring `damping 22 / stiffness 220`; drag-dismiss spring-back same tune; `FadeIn`/`CountUp` for mounts + counters; `camDur` is 0 on sim (MapLibre SIGSEGV guard). No new libs.

## Do not

- No gradients, no glass-morphism blur, no dashboard metric grids, no emoji.
- No mid-word truncation: qualifiers (`· your usual`, `· least-smoke alt N`) are nested dim runs that wrap whole — never `· y…`.
- No system-font fallback: every `Text`/`TextInput` carries `fam*`/`famSerif`/`famMono*` explicitly.
