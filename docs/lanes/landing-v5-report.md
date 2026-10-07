# landing v5 — the "max mode" editorial pass

Lane: landing v5 · file `server/landing.html` · base `base/v2` @ `5fc3a5b`
Rendered against live prod data via a read-only local proxy
(`/v2/city`, `/health`, `/grid`, `/districts`, `/skill`, `/archive-day`,
`/v2/plan` — everything the page actually calls).

## what made the old page read "assembled"

Diagnosed the tells before touching anything (docs/20 +
landing-overhaul-report as the baseline):

1. **Identical chrome per section** — every section opened with the same
   `sec-tick` colour square + mono label. A template stamp on every
   band: the opposite of authored.
2. **Hairlines as the structuring device** — top bar rule, section
   rules, `.steps` ink rules, and a 1px edge on nearly every surface
   (fwrap, dchip, trow, daybars, lrow, depart, routeline, psel track).
   The register reserves hairlines for selection/emptiness/list
   dividers; using them as walls is the kit tell.
3. **The hero was a status card** — numeral + side rail + chips row +
   two button-doors stacked at the top of the page. A dashboard module
   promoted to hero; the page had no voice, only inventory.
4. **Uniform section rhythm** — equal padding, equal label chrome,
   equal tile spacing → the scroll felt catalogued, not read.
5. **The privacy story was a footer tag** — "aggregates only · k≥3 · no
   profiles" was meta text at the bottom. It is the product's most
   honest idea; it deserved a designed object, not a credit line.

## the v5 structure — one editorial flow

Sections now read in an order a person reads: statement → proof →
mechanics → the city → the close. Each zone has its own register.

- **`.open` — the statement.** `GOOD MORNING · DELHI NCR — A DOSIMETER
  WITHOUT HARDWARE` (live greeting) over a felt lede:
  *"A ledger for your lungs, kept on your phone."* Sans 500, one quiet
  `em` — no card, no chrome. The sub carries the live station count
  inline in a sentence.
- **`.proof` — the readout as THE proof object.** The only band-washed
  zone on the page (`--hw` set by JS, same as before): CPCB band label,
  the 250-weight numeral (up to 192px), the felt cigarette line, the
  mono basis line, the breathing 1.5px baseline — and the provenance
  strip (`#status`) as ONE flowing text line under it, not a row of
  tiles.
- **`.mech` — the honest mechanics.** Lead *"How a breath becomes a
  number."*, the three numbered steps (unchanged copy — measure /
  interpolate / dose, live counts inside), the `.why` proof line, then
  the new **`.pledge` block**: *"The ledger stays yours."* — three
  ledger rows, term then claim (`your dose` / `a shared trip` / `the
  rest`), the privacy story drawn as the thing it describes. The
  app-shot figure sits beside it as artifact, smaller and quieter.
- **`.city` — the city strip.** Lead *"The city, right now."* then the
  instrument: the field map (ambient shadow now, no edge), the tonal
  `trow` control strip, captions, the archive day-bars drawn **bare on
  paper** (no card — the chart is the content), and the district chips
  on depth instead of outlines.
- **`.close` — the felt line at statement weight** (*"The field knows
  what Delhi breathed — the app knows what you breathed."*) then the
  two doors as underlined mono text links, and a footer that is air,
  not a rule.

## hairline sweep (register law enforced)

Borders removed where they were walls: `.fwrap` (now ambient shadow),
`.dchip`, `.daybars` (de-carded entirely), `.trow` + button (tonal
strip + lifted card button), `.depart`, `.routeline`, `.lrow`
(`.lrow.rec` keeps a 1.5px inset ring — that one IS selection),
`.psel` track, `.steps` rules, section rules, top-bar rule, footer
rule. Hairlines that survive mark selection, emptiness, or the
breathing baseline — per `docs/lanes/register-card.md`.

## live contract — unchanged

Every mapped number is still live: `#hnum*` (city PM2.5 → numeral +
band ink + wash), `#status` provenance (`stations live · field fresh ·
median · wind · edges priced`), `#fieldLbl/#fieldAge`, the three
canvases (`raster` + `grid` + `fx`), `#capLeft/#legendStrip/
#legendTick/#confSplit`, `trow` timeline, `#daybars/#dayNote/#dayWhy`,
`#dscroll` districts, `#skillLine/#whyLine/#routeline/#departline/
#ladder`, `#stnHero`, `#buildTag`. No fetch added or removed; no test
marker touched (verified: `hero-grid`, `statusline`, `confSplit`,
`fieldAge`, `buildTag`, `bandCol`, `/grid`, `/health`, `/city`,
`/community`, `/app-hero.png`, `the app knows what you breathed`,
`fetch(`, `setInterval`).

## motion

One new behaviour: `[data-rv]` elements get a single quiet rise
(.6s expo-out, 12px, once per element, IntersectionObserver). The
class is added **by JS**, so no-JS and `prefers-reduced-motion` both
see fully-visible content. Nothing else moves that didn't before —
boot strip, breathing baseline, arrow nudge, chip lift unchanged.

## before / after

Before: `docs/lanes/landing-v5-shots` was not kept in-repo (local
proof): hero was numeral+side-rail+chips+doors at docH 4105 (390px) /
3112 (1440px). After: statement → proof → mech → city → close at
docH 4750 / 3709 — longer, because air is now doing the separating.
Verified rendered at 390×844 and 1440×900, scrolled through every
section: no overflow (`docW` == viewport), no console errors, every
live field populated from prod (`62.4 µg/m³`, `≈2.8 cigarettes`,
`903K edges priced`, `29 districts`, day strip `−42% vs typical`).

## tests

`PYTHONPATH=core/build312:. .venv312/bin/python -m pytest -q tests` —
reported below (run on this lane's HEAD). The pre-existing
`test_plan_ranking_invariants_on_real_ods[Sarai Kale Khan → IGI T3]`
failure is data-dependent and unrelated.

## structural diff, one line each

- opening: question-hero + status-card → greeting + felt lede + sub
- proof: flex numeral+side rail+chip tiles → stacked readout, wash owns
  exactly one zone, provenance as text line
- mechanics: mono-label header + ruled step rows → felt lead, air-spaced
  steps, new `.pledge` ledger (privacy as design), shot demoted to
  artifact
- city: standalone labelled blocks → led by a statement; day-bars
  de-carded; all tiles on ambient depth
- close: footer tag → statement-weight felt line + text-link doors
