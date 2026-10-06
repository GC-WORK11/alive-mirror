# Lane: cold-eye-v2 — hostile comprehension pass on the OVERHAULED app

Repo `<owner>/Delhi-Air-108`, branch `base/v2`, HEAD `5fd2990`+.
The app got a full component redesign (owner mandate: minimalism,
colorful components, individually-designed surfaces, ZERO features or
numbers removed, no mini-words cringe) plus a palette fix (paper door
tiles + tinted icon chips — one color family per screen, color lives
INSIDE the chip). Now it needs a stranger's eyes before judges get theirs.

## Mission — comprehension audit + FIX what you find
Put yourself in a Delhi person's head on every screen — someone who has
never heard of AQI or µg/m³. For EVERY surface (home hero, doors, the
move, day arc, days ahead, check-in, ledger, compare, receipt, Delhi
today, map layers):

1. **The 3-second test**: is it obvious what the number means and what
   the app wants you to do? Flag anything that needs a second read.
2. **Residual mini-words**: any leftover label >3 words that a chip,
   icon, or layout could carry instead? Fix it — words rationed to
   number + unit + ≤3-word label is the register (docs/plan/design-refs.md).
3. **Known residual nits — fix them:**
   - Receipt fine print can render degenerate bounds like
     "0.1–0.1 kg" when lo/hi round identically — collapse to the single
     value ("0.1 kg") when equal.
   - hi ledger meta shows Latin "am" suffix where Hindi-appropriate
     time markers exist — verify against strings.ts and fix if a key
     already exists for it.
4. **Contrast + legibility** at real density (420dpi class): any washed
   chips, clipped Devanagari, ellipsis cuts? Fix.
5. **Anti-list sweep**: zero neon/cyberpunk/3D/decorative-SVG/
   chocolaty-green/cheap-yellow anywhere. Flag if found (do not fix —
   report).

## Rules
- Mobile gates must pass before commit: `cd Mobile && npx tsc --noEmit
  && npx expo lint && node src/store/test-runner.mjs &&
  node src/nav/test-runner.mjs`.
- Follow the design register: V2T/V2Tint/V2Radius from src/theme.ts —
  no inline hex, no new color families.
- Commit early+often to base/v2 (`git pull --rebase` first). Push, don't
  wait for a batch.
- Report = `docs/lanes/cold-eye-v2-report.md`: what you changed (with
  commits), what you flagged, screenshots for anything visual.
