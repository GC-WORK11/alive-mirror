# NavChrome r4 — live-nav HUD polish

Lane `r4-navchrome` — owns `Mobile/src/components/shell/NavChrome.tsx` only.

## What changed

**Top card (next-turn banner)**
- New glance hierarchy: 52×52 maneuver tile → distance-to-maneuver (22 pt,
  tabular, semi) → instruction sentence (15 pt, 2 lines).
- Maneuver arrows are stroked SVG paths drawn in-file on the shared 24-px
  grid (icons.tsx is another lane's file and carries no turn glyphs).
  Semantic kinds reuse `Icon`: arrive → `pin` in `pinDest`, walk/transit →
  `vehicleGlyph(mode)`.
- `maneuverOf()` maps the server's instruction vocabulary
  (server/v2/deps.py: Turn/Bear/Keep/U-turn/roundabout/ramp/merge/
  continue/head/arrive + transit legs) — and OSRM `type`/`modifier` when a
  payload carries them — onto `left | right | slight* | uturn | roundabout
  | merge | exit | straight | arrive | walk | transit | mode`.
- Recenter + exit are real 44×44 pt targets with pressed-state opacity;
  a11y labels kept (`nav_recenter`, `end`).

**Bottom instrument cluster** (the signature counters)
- Two floating pills → one solid card: channel A = cigarette icon +
  "smoke you breathe" (uppercase micro-label) + `≈ n cigarettes`; channel
  B = smoke icon + "smoke your ride puts out" + `≈ n kg` (only when the
  mode emits). Hairline divider between cells.
- lo–hi band stays honest and subtle: a 3-px band bar (lo→hi slice of the
  band's own scale, brighter mid tick) + a small range label
  (`12–38 µg` / `0.2–0.4 kg`). No fake precision, no clutter.
- Route progress hairline at the card's top edge (`nav.progress`, accent —
  echoes the route line colour).
- Footer row: `min · km left · arrive HH:MM` (doc 02 §S6 bottom bar),
  tabular, centred, shrinks to fit.
- `stripOk === false` → cells dim to 50 % and the existing grey pill
  explains "counters paused".

**Off-route** — same pill slot, but a warm `breath1` dot + full-brightness
text: reads "finding a new way" (working), not an error.

**Bug fix** — the old `kmLeft()` returned `"350 m"` into the
`"{km} km left"` template → "350 m km left". `kmNum()` now always feeds a
plain km number (2 dp under a kilometre).

## Backward compatibility

Props signature unchanged. `NavView` gained only optional fields:
`progress` and `nextStep.type/modifier` — the engine's `NextStep`
(`{instruction, distM}`) still satisfies the shape; a future engine can
pass OSRM modifiers through for sharper glyph mapping.

Verify: `cd Mobile && npx tsc --noEmit` + `npx expo lint` — both clean.
