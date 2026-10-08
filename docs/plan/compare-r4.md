# r4-compare — CompareSheet premium pass (Alive)

Lane: `r4-compare` · owns `Mobile/src/components/shell/CompareSheet.tsx` only.
Props interface unchanged — `App.tsx` wiring untouched.

## What changed and why

**Option rows → solid cards.** Flat hairline-separated rows became `surface2`
cards (1 px `line` border, `V2Radius.row`, `overflow: hidden`). Selected =
accent border + `rgba(76,141,255,0.10)` tint — the picked way reads at a
glance without a heavy background swap. Replaces `ModeRow` from `ui.tsx`
(that file is another lane's surface; the row is bespoke inside this file now,
and `ModeRow`/`SmokeBar` have no other consumers).

**Two bars read instantly.** The old 4-step `SmokeBar` pair had no key —
you had to know top=breath-in, bottom=ride-out. Now each bar is a
`[glyph][track]` group: `cigarette` = smoke you breathe (warm ramp
`breath1→3`), `smoke` = smoke your ride puts out (cool grey ramp
`out3→out1`, brighter = heavier). Continuous rounded tracks on a `bg`
groove read cleaner than segments; a dimmed empty groove means "no data",
distinct from an empty track = "clean". A one-line legend above the list
maps the glyphs via existing `compare_smokeIn` / `compare_smokeOut`.

**Hierarchy.** Right column: ETA `42 min` (body/semi) → dose `≈120 µg`
(secondary/semi) → bars → all right-aligned. The dose number is coloured
by `doseColor(avg_conc_ugm3)` — the design system's absolute scale, so on
a bad day even the winner glows honestly instead of looking "safe". The
`{lo}–{hi}` uncertainty band renders inline next to the number (was: only
inside the expander) — visible, not hidden. Distance / arrival / stations
stay in the meta line; `reason_line` stays tertiary. µg on the number is a
deliberate deviation from "jargon only in the expander": the mission asks
for a dominant dose *number*, and an unlabelled number is worse than the
real unit — it stays small and dimmed.

**Tags as chips.** Server tags ("lightest for you" etc.) are filled accent
pills; the fallback "our pick" is a neutral outline pill so the stronger
claim reads stronger.

**"How we got this" is inviting now.** Was: hidden long-press + one text
link at the very bottom of the scroll. Now: a labelled `ⓘ` affordance sits
on every card beside the bars it explains (44 pt+ target via hitSlop,
`accessibilityLabel = howWeGotThis`), long-press still works, and the panel
opens *inside the card* under a hairline — no orphaned detached block.
Content is icon-structured (🚬 dose + cigs + confidence · 💨 emissions +
basis/BS class/non-exhaust · 🕐 field age) and closes with `cityBasisBand`
("the range is honest — it covers instrument error…") as the plain-language
explainer.

**Error / retry.** Icon plate + `plan_failed` + the raw server message
(small, honest, 3 lines) + a filled accent retry pill (44 pt) instead of a
ghost outline — the affordance is now unmissable. Empty state gets the same
treatment with a search glyph.

**Pinned footer.** `turn-by-turn` ghost pill (accent when open) + `Start`
filled pill stay visible while the list scrolls (`flexShrink: 1` on the
ScrollView). Steps list keeps its place at the end of the scroll content;
step rows got a proper dot-and-rail connector.

**A11y / i18n.** All consumer strings come from `t()`; every text style
uses `fam(lang, w)` so Hindi gets Devanagari faces (was hard-coded `F.*`
in several places). Icon-only controls keep `accessibilityLabel`; all
touch targets ≥44 pt.

## Proposed new string keys (TODOs left in code — strings.ts is another lane)

- `plan_failedHint` — friendly sub-line under the raw server error
  ("your places are kept — one more try usually lands").
- `compare_doseNA` — short "no estimate" marker for the dose column when
  `dose.mid` is null (currently a bare `—`).
- `a11yCompareHold` (optional) — proper `accessibilityHint` for the
  long-press affordance ("hold for how we got this"); the row currently
  relies on the visible ⓘ label.
