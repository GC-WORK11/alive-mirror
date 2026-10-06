# Lane: vibe-polish — the felt-quality pass the owner keeps missing

## Why
Owner's verbatim complaint after the dosimeter rebuild: "still looks a
little odd… not giving me vibe". Structure is right (dose hero, THE MOVE,
day arc, budget, ledger) — the complaint is SURFACE: the felt quality of
type, color, density, motion, edge-treatment. This is craft work, not
features. Reference register: Oura/WHOOP hero restraint, CRED's type
weight, Uber's calm chrome, Apple Health glanceability —
docs/plan/design-refs.md has the committed refs.

## Scope — Mobile only, additive-safe (journey untouched)
1. **Audit first**: screenshot every populated surface at 420dpi
   (HomeSheet hero→bottom, compare sheet, nav, DayPeek, DelhiToday,
   ledger). Put each next to its reference's equivalent surface and
   write the concrete delta — not "feels off" but "hero numerals are
   28pt/regular vs reference 64pt/light", "cards all share one gray",
   "bands read as fills not tints".
2. **Type hierarchy pass**: numerals own their card. Dose figure, gap
   figure, budget remainder — real size+weight contrast vs labels.
   Check Fraunces/PlexMono actually apply on every surface (any label
   still falling back to system default is a defect — hunt them all).
3. **Tonal layering**: paper background → card → elevated-card needs a
   readable three-step ladder; band washes must tint WITHOUT flattening
   text contrast. Kill any mid-gray mush.
4. **Motion/press**: press-states on every tappable card; sheet drags
   feel sprung not linear; counters tick with a settle, not a pop.
   No new animation libs — Reanimated already shipped.
5. **Hairline + edge discipline**: consistent hairlines where the
   register calls for them; no double-borders, no orphan shadows.
6. Deliver: before/after pairs per surface (emulator shots are fine),
   plus a one-screen "register card" doc capturing the final tokens so
   later lanes don't drift.

## Hard rules
- `cd Mobile && npx tsc --noEmit && npx expo lint` before every push;
  store/nav runners must stay green (node src/store/test-runner.mjs,
  node src/nav/test-runner.mjs).
- Structure frozen: no new screens, no removed cards, no copy rewrites
  except where copy itself is the defect (truncation, casing).
- Journey (search→vehicle→compare→nav→receipt) must stay working —
  drive it after the visual pass.
- Live API GETs only. Commit to base/v2 (pull --rebase).
  Report → docs/lanes/vibe-polish-report.md.
