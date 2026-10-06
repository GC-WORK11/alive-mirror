# cold-eye-v2 — hostile stranger-comprehension pass

Branch `base/v2`. Scope per `docs/lanes/cold-eye-v2.md`: 3-second test on
every surface, residual mini-words, the two documented nits, 420-dpi
contrast/legibility, anti-list sweep. All reading done on source
(`Mobile/src/**`), gates green before each commit.

## Fixed (commits f8e22d0, 1053035)

| Site | Bug | Fix |
|---|---|---|
| `ReceiptSheet` est. line | co2 band gate `hi-lo > 0.05` ran on *raw* values but display rounds via `r1()` — e.g. {0.06, 0.12} printed **`0.1–0.1 kg`** | compare *rounded* values; equal → single `0.1 kg`. Also swapped the literal ` kg` for `t("nav_kg")` so hi reads **किग्रा**, not Latin (latent leak on the same line). NavChrome's collapse precedent, mirrored. |
| `ReceiptSheet` (follow-up) | collapsed single value printed `0` for whole numbers (`r1` returns a number) | `r1(co2.hi).toFixed(1)` — matches NavChrome's `0.1 kg` style exactly |
| `LedgerScreen` `timeLabel` | `toLocaleTimeString("hi-IN", hour12)` leaks Latin **"am"/"pm"** on Android ICU (iOS renders Devanagari पूर्वाह्न/अपराह्न — platform divergence) | new keys `daypart_am`/`daypart_pm` (en `am`/`pm`, hi `पूर्वाह्न`/`अपराह्न`); time composed by hand `${h12}:${mm} {daypart}` — identical output on both platforms, zero locale dependence. Key pair added to both tables; parity 537/537 + mode-table entries. |

Neither nit had an existing key to reuse (verified against strings.ts) —
`daypart_*` is the minimal pair; `nav_kg` already existed for the kg unit.

## 3-second test — per surface

| Surface | Verdict |
|---|---|
| Home hero | PASS — `≈N µg` owns the card, "smoke you breathe" label, dose ring; sparse states labelled honestly, never fake |
| Doors (map/city/trips) | PASS — 3 paper tiles, tinted glyph wells, ≤3-word labels; city chip carries live ambient band |
| The move | PASS — serif felt line ("same plan at 8 breathes ~2× lighter") + sparkline + band chips; conf/age fine print below |
| Day arc | PASS — 24-slot bars, hour numeral every 3rd, covered-vs-blank reads instantly |
| Days ahead | PASS — 5 band-washed cells, expandable, outlook caption from structured fields |
| Check-in (lens) | PASS — 3 facets × good/meh/rough pills + verdict |
| Ledger | PASS after fix — mode well + route + meta (`mode · H:MM pm`) + µg hero + kg sub |
| Compare | PASS — dose owns right column, ETA recedes, safest/pick chips, in/out pair bars, detail expander with jargon zone |
| Receipt | PASS after fix — two counters + honest band footnotes + provenance row |
| Delhi today | PASS — band-washed hero + why-line + freshness chips + species + 12h bars + corridors + travellers + basis expander |
| Map layers | PASS — 3 icon rows, switches, off by default |

## Mini-words sweep

- **"smoke your ride puts out" (5 words)** — flagged, NOT fixed: verbatim
  canon in `docs/plan/02-consumer-ux.md` §3 ("words a 12-year-old uses").
  The paired "smoke you breathe" / "smoke your ride puts out" is the
  product's signature didactic label; compressing it loses the actor
  (you vs the ride). The prior forensic find (`PUTS…` clip) is already
  handled via `adjustsFontSizeToFit` on the cell label.
- `settingsShareData` "Share anonymous trip data" (4w) — a settings row
  title, verb phrase; acceptable under the register.
- Everything else >3 words is a sentence (hints, empty states, "how we
  got this" bodies) — allowed.
- Zero hardcoded consumer literals outside strings.ts (the `ALIVE-108`
  wordmark is a proper noun — same in both languages, by design).

## 420-dpi contrast / legibility

- No washed chips found: placeholders use `text2` (the 4.33:1
  `text3-on-surface2` case was already fixed — SearchScreen comment);
  FreshnessChip deliberately keeps text at `text2` while the dot dims.
- Ellipsis cuts: ledger trip-route + meta + SearchBar label already carry
  `adjustsFontSizeToFit` + `minimumFontScale` (prior lanes); trip meta no
  longer tail-truncates times.
- Devanagari clipping: `includeFontPadding:false` on the 26-pt compare
  dose; hero numerals have lineHeight slack (44→64). No new clips found.
- Smallest live type: DepartGraph `tickClock` 9 pt / NavChrome `cellBand`
  10 pt — at the floor but consistent fine print, mono only (Latin
  digits; Devanagari never lands in `famMono` slots — `famMonoText`
  routes hi to Noto).

## Anti-list sweep (flag only)

- **`Mobile/src/map/v2-light.json` lines 727–770** — `v2-building-extrusion`
  `fill-extrusion` layer (`fill-extrusion-height`, opacity .55): vendor 3D
  building extrusions inside the map style. Same item flagged by the APK
  audit; style file change is out of this lane's remit — **flagged**.
- No neon/cyberpunk/chocolaty-green/cheap-yellow/decorative-SVG in app
  code. Every hex outside `theme.ts` is a documented exception:
  `#1E874B` (FreshnessChip status green — sanctioned), `#E5484D`
  (dest pin, breath-ramp family), `#FBEAEA` (danger-row press),
  `#E8B8A8` (arrive pin on the dark maneuver tile), muted `rgba()`
  hairlines/pressed-fills.

## Notes for other lanes

- en keeps 12 h `am/pm` on the ledger meta while compare/nav use 24 h
  `arrive 08:15` — two clock registers coexist (en `am/pm` is the
  documented "Delhiites write am/pm" convention). Consistent within each
  surface; flagging for awareness, not a bug.
- `dayLabel` still uses `toLocaleDateString("hi-IN")` — weekday/month
  names render Devanagari on both platforms (dates localize; only the
  dayperiod marker leaked). If Android ever shows Latin weekday names,
  same manual-composition fix applies.
- hi headline serif-fallback decision stays open per the APK audit —
  not touched here.

## Gates

`npx tsc --noEmit` ✓ · `npx expo lint` ✓ · `store/test-runner.mjs` 18/18 ✓ ·
`nav/test-runner.mjs` 70/70 ✓ — green before each commit (f8e22d0,
1053035; rebased over 4010790 mid-lane).

No live-sim screenshots: both fixes are deterministic string formatting —
the ledger clock change is byte-identical to what iOS already renders
(verified live by hi-parity-v2: "पूर्वाह्न clock"), and the degenerate
receipt band needs a {lo,hi} pair that collapses at 1 dp, unreachable
through the UI on demand.
