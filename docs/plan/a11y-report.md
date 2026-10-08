# Accessibility audit — v2 dark shell (Alive)

**Scope:** `Mobile/src/**/*.tsx` + `Mobile/App.tsx`. **Method:** `python3 scripts/a11y_audit.py`
(static JSX scan — interactive elements, labels, roles, touch-target sizes from
`StyleSheet.create`, font-scale caps, live counters) + a WCAG 2.x contrast pass over
the `V2T` palette in `src/theme.ts`. Advisory only — always exits 0; heuristic style
resolution may miss sizes hidden behind nested style objects.

**Re-run:** `python3 scripts/a11y_audit.py --mobile-dir Mobile`

## Toolkit for fixes — `Mobile/src/a11y/index.ts`

| Export | Use |
|---|---|
| `a11y(label, hint?, role?, opts?)` | bundles `accessibilityLabel/Role/Hint/State` (+ `accessibilityLanguage` via `opts.lang`) — spread onto every `Pressable`/`Touchable*` |
| `MIN_TOUCH` (44) · `ensureTouch(style)` · `slop(px)` | floors `minWidth`/`minHeight` at 44 pt; `hitSlop={slop()}` for controls that must look small |
| `MAX_FONT_SCALE` (1.3) · `DYNAMIC_TYPE` · `scaledFont(size, lang)` · `fontScale()` | doc 03's 130% dynamic-type cap — spread `DYNAMIC_TYPE` on every `<Text>`/`<TextInput>`; `scaledFont` adds the ~4% Devanagari bump for `hi` |
| `contrast(fg,bg)` · `contrastPass()` · `assertContrast()` | WCAG ratio (handles `#rgb(a)`/`rgba()`, composites translucent fg over bg); `assertContrast` warns in `__DEV__` only |
| `liveRegion` · `useA11yAnnounce(text, throttleMs)` | nav-counter pair: Android TalkBack announces text diffs via `accessibilityLiveRegion:"polite"`; VoiceOver ignores it → the hook announces on iOS only, leading+trailing, on *meaningful* change — a 1 Hz tick stays a ≤1-per-10 s voice |
| `useReduceMotion()` | doc 03 §motion — swap springs/camera glides for fades when on |

Severity legend — **HIGH**: silent/unusable with a screen reader. **MEDIUM**: announced wrong or
missing role/label. **LOW**: works but fragile or sub-44 pt mitigated by hitSlop. **INFO**: verify.

## Static findings — 70 total (HIGH 7 · MEDIUM 35 · LOW 27 · INFO 1)

| Severity | Location | Finding | Suggested fix |
|---|---|---|---|
| HIGH | `src/components/shell/NavChrome.tsx:37` | <Pressable> without accessibilityLabel — icon-only control is silent to screen readers | spread {...a11y(label, hint, 'button', opts)} from src/a11y |
| HIGH | `src/components/shell/SearchBar.tsx:35` | <Pressable> without accessibilityLabel — icon-only control is silent to screen readers | spread {...a11y(label, hint, 'button', opts)} from src/a11y |
| HIGH | `src/components/shell/Sidebar.tsx:115` | <Pressable> without accessibilityLabel — icon-only control is silent to screen readers | spread {...a11y(label, hint, 'button', opts)} from src/a11y |
| HIGH | `src/components/shell/Sidebar.tsx:132` | <Pressable> without accessibilityLabel — icon-only control is silent to screen readers | spread {...a11y(label, hint, 'button', opts)} from src/a11y |
| HIGH | `src/components/shell/Sidebar.tsx:139` | <Pressable> without accessibilityLabel — icon-only control is silent to screen readers | spread {...a11y(label, hint, 'button', opts)} from src/a11y |
| HIGH | `src/ui.tsx:164` | <Pressable> without accessibilityLabel — icon-only control is silent to screen readers | spread {...a11y(label, hint, 'button', opts)} from src/a11y |
| HIGH | `src/ui.tsx:39` | <Pressable> without accessibilityLabel — icon-only control is silent to screen readers | spread {...a11y(label, hint, 'button', opts)} from src/a11y |
| MEDIUM | `App.tsx:236` | <Pressable> without accessibilityLabel — label likely inferred from text child — verify it reads cleanly | spread {...a11y(label, hint, 'button', opts)} from src/a11y |
| MEDIUM | `App.tsx:236` | <Pressable> missing accessibilityRole | a11y() emits it; screen readers then announce 'button' |
| MEDIUM | `App.tsx:253` | <Pressable> without accessibilityLabel — label likely inferred from text child — verify it reads cleanly | spread {...a11y(label, hint, 'button', opts)} from src/a11y |
| MEDIUM | `App.tsx:253` | <Pressable> missing accessibilityRole | a11y() emits it; screen readers then announce 'button' |
| MEDIUM | `src/components/shell/CompareSheet.tsx:55` | <Pressable> without accessibilityLabel — label likely inferred from text child — verify it reads cleanly | spread {...a11y(label, hint, 'button', opts)} from src/a11y |
| MEDIUM | `src/components/shell/CompareSheet.tsx:55` | <Pressable> missing accessibilityRole | a11y() emits it; screen readers then announce 'button' |
| MEDIUM | `src/components/shell/CompareSheet.tsx:83` | <Pressable> without accessibilityLabel — label likely inferred from text child — verify it reads cleanly | spread {...a11y(label, hint, 'button', opts)} from src/a11y |
| MEDIUM | `src/components/shell/CompareSheet.tsx:83` | <Pressable> missing accessibilityRole | a11y() emits it; screen readers then announce 'button' |
| MEDIUM | `src/components/shell/CompareSheet.tsx:88` | <Pressable> without accessibilityLabel — label likely inferred from text child — verify it reads cleanly | spread {...a11y(label, hint, 'button', opts)} from src/a11y |
| MEDIUM | `src/components/shell/CompareSheet.tsx:88` | <Pressable> missing accessibilityRole | a11y() emits it; screen readers then announce 'button' |
| MEDIUM | `src/components/shell/LayersSheet.tsx:36` | <Switch> without accessibilityLabel — announced as bare 'switch, on/off' | add accessibilityLabel (the row text next to it isn't associated) |
| MEDIUM | `src/components/shell/Sidebar.tsx:107` | <Pressable> without accessibilityLabel — label likely inferred from text child — verify it reads cleanly | spread {...a11y(label, hint, 'button', opts)} from src/a11y |
| MEDIUM | `src/components/shell/Sidebar.tsx:107` | <Pressable> missing accessibilityRole | a11y() emits it; screen readers then announce 'button' |
| MEDIUM | `src/components/shell/Sidebar.tsx:115` | <Pressable> missing accessibilityRole | a11y() emits it; screen readers then announce 'button' |
| MEDIUM | `src/components/shell/Sidebar.tsx:119` | <Pressable> without accessibilityLabel — label likely inferred from text child — verify it reads cleanly | spread {...a11y(label, hint, 'button', opts)} from src/a11y |
| MEDIUM | `src/components/shell/Sidebar.tsx:119` | <Pressable> missing accessibilityRole | a11y() emits it; screen readers then announce 'button' |
| MEDIUM | `src/components/shell/Sidebar.tsx:132` | <Pressable> missing accessibilityRole | a11y() emits it; screen readers then announce 'button' |
| MEDIUM | `src/components/shell/Sidebar.tsx:188` | <Pressable> without accessibilityLabel — label likely inferred from text child — verify it reads cleanly | spread {...a11y(label, hint, 'button', opts)} from src/a11y |
| MEDIUM | `src/components/shell/Sidebar.tsx:188` | <Pressable> missing accessibilityRole | a11y() emits it; screen readers then announce 'button' |
| MEDIUM | `src/components/shell/Sidebar.tsx:212` | <Pressable> without accessibilityLabel — label likely inferred from text child — verify it reads cleanly | spread {...a11y(label, hint, 'button', opts)} from src/a11y |
| MEDIUM | `src/components/shell/Sidebar.tsx:212` | <Pressable> missing accessibilityRole | a11y() emits it; screen readers then announce 'button' |
| MEDIUM | `src/components/shell/Sidebar.tsx:242` | <Switch> without accessibilityLabel — announced as bare 'switch, on/off' | add accessibilityLabel (the row text next to it isn't associated) |
| MEDIUM | `src/components/shell/Sidebar.tsx:249` | <Pressable> without accessibilityLabel — label likely inferred from text child — verify it reads cleanly | spread {...a11y(label, hint, 'button', opts)} from src/a11y |
| MEDIUM | `src/components/shell/Sidebar.tsx:249` | <Pressable> missing accessibilityRole | a11y() emits it; screen readers then announce 'button' |
| MEDIUM | `src/components/shell/Sidebar.tsx:266` | <Switch> without accessibilityLabel — announced as bare 'switch, on/off' | add accessibilityLabel (the row text next to it isn't associated) |
| MEDIUM | `src/components/shell/Sidebar.tsx:279` | <Switch> without accessibilityLabel — announced as bare 'switch, on/off' | add accessibilityLabel (the row text next to it isn't associated) |
| MEDIUM | `src/components/shell/Sidebar.tsx:282` | <Pressable> without accessibilityLabel — label likely inferred from text child — verify it reads cleanly | spread {...a11y(label, hint, 'button', opts)} from src/a11y |
| MEDIUM | `src/components/shell/Sidebar.tsx:282` | <Pressable> missing accessibilityRole | a11y() emits it; screen readers then announce 'button' |
| MEDIUM | `src/components/shell/Sidebar.tsx:85` | <Pressable> without accessibilityLabel — label likely inferred from text child — verify it reads cleanly | spread {...a11y(label, hint, 'button', opts)} from src/a11y |
| MEDIUM | `src/components/shell/Sidebar.tsx:85` | <Pressable> missing accessibilityRole | a11y() emits it; screen readers then announce 'button' |
| MEDIUM | `src/screens/SearchScreen.tsx:212` | hard-coded accessibilityLabel="back" bypasses the i18n string table (doc 02 §6 — Hindi + English) | use t() string key, e.g. a11y(t('a11yBack', lang), …) |
| MEDIUM | `src/screens/SearchScreen.tsx:230` | hard-coded accessibilityLabel="clear" bypasses the i18n string table (doc 02 §6 — Hindi + English) | use t() string key, e.g. a11y(t('a11yBack', lang), …) |
| MEDIUM | `src/ui.tsx:164` | <Pressable> missing accessibilityRole | a11y() emits it; screen readers then announce 'button' |
| MEDIUM | `src/ui.tsx:74` | <Pressable> without accessibilityLabel — label likely inferred from text child — verify it reads cleanly | spread {...a11y(label, hint, 'button', opts)} from src/a11y |
| MEDIUM | `src/ui.tsx:74` | <Pressable> missing accessibilityRole | a11y() emits it; screen readers then announce 'button' |
| LOW | `App.tsx:1` | 8 <Text>/<TextInput> without maxFontSizeMultiplier (lines 214,228,231,234,237,251,252,254) — system scale >130% can break layouts (doc 03) | spread {...DYNAMIC_TYPE} from src/a11y on each <Text> |
| LOW | `App.tsx:253` | padding-only pressable (≈42 pt tall) may fall under 44 pt | ensureTouch(style) floors minHeight at 44 |
| LOW | `src/components/FieldLayer.tsx:1` | 1 <Text>/<TextInput> without maxFontSizeMultiplier (lines 141) — system scale >130% can break layouts (doc 03) | spread {...DYNAMIC_TYPE} from src/a11y on each <Text> |
| LOW | `src/components/shell/CompareSheet.tsx:1` | 9 <Text>/<TextInput> without maxFontSizeMultiplier (lines 50,57,84,89,96,100,101,109,113) — system scale >130% can break layouts (doc 03) | spread {...DYNAMIC_TYPE} from src/a11y on each <Text> |
| LOW | `src/components/shell/CompareSheet.tsx:55` | padding-only pressable (≈36 pt tall) may fall under 44 pt | ensureTouch(style) floors minHeight at 44 |
| LOW | `src/components/shell/CompareSheet.tsx:83` | padding-only pressable (≈34 pt tall) may fall under 44 pt | ensureTouch(style) floors minHeight at 44 |
| LOW | `src/components/shell/CompareSheet.tsx:88` | padding-only pressable (≈40 pt tall) may fall under 44 pt | ensureTouch(style) floors minHeight at 44 |
| LOW | `src/components/shell/LayersSheet.tsx:1` | 2 <Text>/<TextInput> without maxFontSizeMultiplier (lines 31,35) — system scale >130% can break layouts (doc 03) | spread {...DYNAMIC_TYPE} from src/a11y on each <Text> |
| LOW | `src/components/shell/NavChrome.tsx:1` | 3 <Text>/<TextInput> without maxFontSizeMultiplier (lines 27,32,43) — system scale >130% can break layouts (doc 03) | spread {...DYNAMIC_TYPE} from src/a11y on each <Text> |
| LOW | `src/components/shell/NavChrome.tsx:37` | padding-only pressable (≈30 pt tall) may fall under 44 pt | ensureTouch(style) floors minHeight at 44 |
| LOW | `src/components/shell/SearchBar.tsx:1` | 1 <Text>/<TextInput> without maxFontSizeMultiplier (lines 29) — system scale >130% can break layouts (doc 03) | spread {...DYNAMIC_TYPE} from src/a11y on each <Text> |
| LOW | `src/components/shell/SearchBar.tsx:23` | touch target ≈38.0×38.0 pt — hitSlop extends it; verify ≥44 incl. slop | prefer ensureTouch(style) so the box itself is ≥44 |
| LOW | `src/components/shell/SearchBar.tsx:35` | touch target ≈30.0×30.0 pt — hitSlop extends it; verify ≥44 incl. slop | prefer ensureTouch(style) so the box itself is ≥44 |
| LOW | `src/components/shell/Sidebar.tsx:1` | 27 <Text>/<TextInput> without maxFontSizeMultiplier (lines 89,90,109,110,120,138,145,149,150,152,165,176…) — system scale >130% can break layouts (doc 03) | spread {...DYNAMIC_TYPE} from src/a11y on each <Text> |
| LOW | `src/components/shell/Sidebar.tsx:107` | <Pressable> uses disabled={} but doesn't announce it | pass disabled via a11y(…, { disabled }) → accessibilityState |
| LOW | `src/components/shell/Sidebar.tsx:188` | <Pressable> uses disabled={} but doesn't announce it | pass disabled via a11y(…, { disabled }) → accessibilityState |
| LOW | `src/components/shell/Sidebar.tsx:188` | padding-only pressable (≈36 pt tall) may fall under 44 pt | ensureTouch(style) floors minHeight at 44 |
| LOW | `src/components/shell/Sidebar.tsx:212` | padding-only pressable (≈36 pt tall) may fall under 44 pt | ensureTouch(style) floors minHeight at 44 |
| LOW | `src/components/shell/Sidebar.tsx:249` | padding-only pressable (≈30 pt tall) may fall under 44 pt | ensureTouch(style) floors minHeight at 44 |
| LOW | `src/components/shell/Sidebar.tsx:282` | padding-only pressable (≈36 pt tall) may fall under 44 pt | ensureTouch(style) floors minHeight at 44 |
| LOW | `src/components/shell/Sidebar.tsx:85` | <Pressable> uses disabled={} but doesn't announce it | pass disabled via a11y(…, { disabled }) → accessibilityState |
| LOW | `src/components/shell/Sidebar.tsx:85` | padding-only pressable (≈40 pt tall) may fall under 44 pt | ensureTouch(style) floors minHeight at 44 |
| LOW | `src/screens/SearchScreen.tsx:1` | 8 <Text>/<TextInput> without maxFontSizeMultiplier (lines 81,83,85,88,119,215,272,293) — system scale >130% can break layouts (doc 03) | spread {...DYNAMIC_TYPE} from src/a11y on each <Text> |
| LOW | `src/screens/SearchScreen.tsx:212` | padding-only pressable (≈30 pt tall) may fall under 44 pt | ensureTouch(style) floors minHeight at 44 |
| LOW | `src/screens/SearchScreen.tsx:230` | padding-only pressable (≈30 pt tall) may fall under 44 pt | ensureTouch(style) floors minHeight at 44 |
| LOW | `src/ui.tsx:1` | 7 <Text>/<TextInput> without maxFontSizeMultiplier (lines 79,80,82,85,86,126,162) — system scale >130% can break layouts (doc 03) | spread {...DYNAMIC_TYPE} from src/a11y on each <Text> |
| LOW | `src/ui.tsx:39` | padding-only pressable (≈26 pt tall) may fall under 44 pt | ensureTouch(style) floors minHeight at 44 |
| INFO | `src/components/shell/NavChrome.tsx:43` | live counter text (updates ~1 Hz during nav) has no announce path | wrap in {...liveRegion} + call useA11yAnnounce(text) — src/a11y |

## Contrast audit — V2T tokens × dark backgrounds (WCAG 2.x ratio)

| Token | Hex | on `bg` | on `surface` | on `surface2` | Verdict (text needs ≥4.5) |
|---|---|---|---|---|---|
| `line` | #2A2F36 | 1.44 | 1.32 | 1.19 | n/a — non-text (WCAG non-text floor is 3:1) |
| `text` | #F2F4F7 | 17.66 | 16.15 | 14.50 | PASS |
| `text2` | #A3AAB5 | 8.32 | 7.60 | 6.83 | PASS |
| `text3` | #6B7280 | 4.02 | 3.68 | 3.30 | FAIL (3.30 < 4.5) |
| `accent` | #4C8DFF | 6.08 | 5.56 | 4.99 | PASS |
| `breath1` | #F2C14E | 11.59 | 10.60 | 9.52 | PASS |
| `breath2` | #F08A3C | 7.79 | 7.12 | 6.39 | PASS |
| `breath3` | #E5484D | 4.97 | 4.55 | 4.08 | FAIL (4.08 < 4.5) |
| `out1` | #9AA4B2 | 7.72 | 7.06 | 6.33 | n/a — non-text (WCAG non-text floor is 3:1) |
| `out2` | #6E7A8A | 4.46 | 4.08 | 3.66 | n/a — non-text (WCAG non-text floor is 3:1) |
| `out3` | #3E4754 | 2.07 | 1.89 | 1.70 | n/a — non-text (WCAG non-text floor is 3:1) |
| `pinDest` | #E5484D | 4.97 | 4.55 | 4.08 | n/a — non-text (WCAG non-text floor is 3:1) |
| `mapMotorway` | #3A4049 | 1.86 | 1.70 | 1.53 | n/a — non-text (WCAG non-text floor is 3:1) |
| `mapPrimary` | #2E333A | 1.53 | 1.40 | 1.26 | n/a — non-text (WCAG non-text floor is 3:1) |
| `mapMinor` | #24282E | 1.31 | 1.20 | 1.08 | n/a — non-text (WCAG non-text floor is 3:1) |
| `mapBuilding` | #1C2026 | 1.19 | 1.09 | 1.02 | n/a — non-text (WCAG non-text floor is 3:1) |
| `mapWater` | #0E1A24 | 1.10 | 1.01 | 1.10 | n/a — non-text (WCAG non-text floor is 3:1) |
| `mapPark` | #121A15 | 1.10 | 1.00 | 1.11 | n/a — non-text (WCAG non-text floor is 3:1) |

**2 token(s) below the 4.5:1 floor the doc claims.**

## Contrast verdict vs doc 03's claim

Doc 03 claims **"all text ≥ 4.5:1 on `bg`/`surface`"**. Computed result: **the claim fails for
`text3` everywhere** — #6B7280 measures 4.02 on `bg`, 3.68 on `surface`, 3.30 on `surface2`.
`text3` is currently used for captions/meta/placeholder text (mode meta, section labels,
trip meta, placeholder colour in SearchBar, `dayLabel`, `hint`, `sub` rows) — all
sub-AA as *text*. `breath3`/`pinDest` (#E5484D) passes on `bg`/`surface` but fails on
`surface2` (4.08) — relevant wherever red text sits on a pressed/elevated fill
(e.g. `AlertBanner` uses `surface2`; the delete row is safe at 4.97 on `bg`).

Suggested remediation paths for the integrator (no token changes made here):
1. Brighten `text3` to ≈#8A919C+ (needs ≈#9AA4B2 for 4.5 on `surface`, ≈#96A0AC for `surface2`),
   or re-scope it as decorative-only and move all *meaningful* tertiary text to `text2` (8.32 ✓).
2. For red-on-`surface2` cases use `breath2`-or-lighter, or put red text only on `bg`/`surface`.
3. Non-text tokens (`line`, `out*`, `map*`) are exempt from the 4.5 text rule but `line`-on-`bg`
   at 1.44 and `out3`-on-`bg` at 2.07 are also under the 3:1 *non-text* floor where they carry
   meaning alone (e.g. unlit `SmokeBar` segments) — bars keep a length signal, which doc 03
   already mandates, so this is a watch item not a violation.
