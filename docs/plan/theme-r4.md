# theme-r4 · premium dark token refresh (lane r4-tokens)

Owner complaint addressed: the UI read "cheap" — a greenish cast in dark fills
(worst offender: `mapPark #121A15`, hue 143°) and translucent `rgba()` washes
used as surface fills, which let the map bleed through and muddy every panel.

`Mobile/src/theme.ts` only. Every pre-existing `V2T` key is unchanged in name
and type; all additions are new keys, so all screen files compile untouched
(`npx tsc --noEmit` clean).

## The graphite/ink ramp

Every neutral now sits at hue **216–220°** with **B ≥ G > R** in all three
channels — a strict blue-black ordering that makes a green cast impossible.
Reference territory: Linear / Apple Maps dark.

| Token | Hex | Hue | Role |
|---|---|---|---|
| `bg` | `#090B0F` | 220° | app canvas |
| `surface` | `#12151B` | 220° | cards, rows on canvas |
| `sheet` | `#12151B` | 220° | **new** — bottom sheets (== surface step) |
| `card` | `#12151B` | 220° | **new** — card fills (== surface step) |
| `surface2` | `#1B2029` | 219° | raised: inputs, pressed rows, pills |
| `surface3` | `#242B37` | 218° | **new** — top solid step (floating controls, pressed-on-raised) |
| `line` | `#2A303C` | 220° | dividers, default 1-px edges |
| `hairline` | `#333C4A` | 217° | **new** — crisp card/sheet edge |

Adjacent elevation steps: bg→surface 1.08 · surface→surface2 1.12 ·
surface2→surface3 1.15 — gentle, even, deliberate.

## Solid-surface doctrine

**Elevation is a ladder of solid fills; alpha is never a surface.**

- Sheets, cards, chips, pills → `sheet` / `card` / `surface` / `surface2` /
  `surface3`. No `rgba()` backgrounds on surfaces — the map must not bleed
  through.
- Selected/accent states → **`accentWash` `#171F2D`** (≈ accent @8% over sheet)
  and **`accentTint` `#192436`** (≈ accent @12% over sheet) — pre-composited
  *solid* replacements for `rgba(76,141,255,0.08)` / `rgba(76,141,255,0.12)`.
- Scrims stay `rgba` but are tuned blue-black instead of flat black:
  **`scrim` `rgba(5,7,11,0.45)`** (sheet backdrops — replaces inline
  `rgba(0,0,0,0.35/0.4)`) and **`scrimDeep` `rgba(5,7,11,0.60)`** (drawer —
  replaces `rgba(0,0,0,0.5)`).
- Data overlays on the map (FieldLayer heat, route breath) may stay `rgba` —
  they are data, not surfaces.

Migration map for screen lanes: `rgba(0,0,0,0.35)`/`0.4` → `V2T.scrim`;
`rgba(0,0,0,0.5)` → `V2T.scrimDeep`; `rgba(76,141,255,0.12)` → `V2T.accentTint`;
`rgba(76,141,255,0.08)` → `V2T.accentWash`; card `borderColor: V2T.line` →
`V2T.hairline` where a crisper edge is wanted.

## Text & meaning colours (unchanged families)

| Token | Hex | Notes |
|---|---|---|
| `text` | `#F2F4F7` | primary |
| `text2` | `#A6ADB9` | secondary (was `#A3AAB5`, +2 lightness) |
| `text3` | `#8A94A0` | tertiary/disabled — kept |
| `accent` | `#4F90FF` | same hue, +2 lightness vs `#4C8DFF` so accent *text* clears 4.5:1 even on `surface3` |
| `breath1/2` | `#F2C14E` / `#F08A3C` | inhaled-smoke ramp, kept |
| `breath3` | `#F26366` | severe — brightened from `#EE5A5F` so it clears 4.5:1 on `surface3` too |
| `out1..3` | `#9AA4B2` `#6E7A8A` `#3E4754` | exhaust greys, kept |
| `pinDest` | `#E5484D` | destination pin, kept (deeper than breath3) |

## Verified contrast (WCAG 2.x, `(L1+0.05)/(L2+0.05)` on sRGB-linearized lum.)

| Foreground | on `bg` | on `surface`/`sheet` | on `surface2` | on `surface3` |
|---|---|---|---|---|
| `text` `#F2F4F7` | 17.9 | 16.6 | 14.8 | 12.9 |
| `text2` `#A6ADB9` | 8.7 | 8.1 | 7.2 | 6.3 |
| `text3` `#8A94A0` | 6.4 | 5.9 | **5.3** | **4.6** |
| `accent` `#4F90FF` | 6.3 | 5.9 | 5.3 | 4.6 |
| `breath1` `#F2C14E` | 11.7 | 10.9 | 9.7 | 8.5 |
| `breath2` `#F08A3C` | 7.9 | 7.3 | 6.5 | 5.7 |
| `breath3` `#F26366` | 6.3 | 5.9 | **5.3** | **4.6** |
| `out1` `#9AA4B2` | 7.8 | 7.3 | 6.5 | 5.6 |
| `out2` `#6E7A8A` | 4.5 | 4.2 | 3.8 | 3.3 |
| `pinDest` `#E5484D` | 5.0 | 4.7 | 4.2 | 3.6 |

Every text-bearing colour clears **≥4.5:1 on all four elevations** — `text3`,
the full breath ramp and `accent` included. `out2` and `pinDest` are
graphic-only (dots, pins — ≥3:1 non-text is satisfied or the element is
iconographic, never body text).

Additional checks: `bg` text on filled `accent` buttons **6.3:1** (the app's
accent-fill convention is dark text, not white — white on accent would be
3.1:1, do not use it); `accent` text on `accentTint` **5.0:1**; `text` on
`accentTint` **14.2:1**; `hairline` on `surface` **1.6:1** (non-text edge —
decorative, and visible).

## Map tokens (forward contract for the basemap lane)

`v2-dark.json` ships its own hexes; `V2T.map*` is the token contract the map
lane re-applies at runtime. All moved to the ink family — **no green remains**:

| Token | Old | New | Why |
|---|---|---|---|
| `mapPark` | `#121A15` (green, hue 143°) | `#10151D` | the owner's greenish cast, removed per the "no green anywhere" rule — parks are now "barely tinted" cool slate |
| `mapWater` | `#0E1A24` | `#0C1520` | deeper, less teal |
| `mapBuilding` | `#1C2026` | `#181D25` | matched to surface step |
| `mapMinor` | `#24282E` | `#222730` | ink family |
| `mapPrimary` | `#2E333A` | `#2B313C` | ink family |
| `mapMotorway` | `#3A4049` | `#383F4B` | ink family |

## Legacy `T` aliases

All keys retained. `goSoft` / `accentSoft` now resolve to the **solid**
`accentTint` instead of a translucent `rgba()` string — same `string`
contract, doctrine-compliant. `glass` → `sheet`, `glassBorder`/`hairline` →
`hairline`.
