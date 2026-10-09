# safearea — status-bar overlap + real exits on every sheet surface

Lane: safearea · date: 2026-10-09 · code: `ea97dab` on `base/v2` · Android E2E: Linux KVM child ([devin-c2997ae38ab74bd7a755af2a4c6d524d](https://app.devin.ai/sessions/c2997ae38ab74bd7a755af2a4c6d524d)) — evidence in `docs/lanes/safearea-e2e.md` + `safearea-shots/`

Owner's live complaint on Android: sheet header text printed under the system status bar ('8:25' over 'Where to stay'), and sheets had no visible way back — "no complete flow end to end".

## FIX 1 — the overlap: cause, not padding

**Root cause (verified by reading, not guessed):** `Sheet` in `Mobile/src/ui.tsx` rendered a plain **in-flow** `Animated.View` — no `position`, no anchor. Where the parent happened to be a `position:absolute; bottom:0` wrapper (CompareSheet's `s.wrap`, LayersSheet's `s.wrap`, VehicleSheet's `s.overlay` + `s.sheet`), the sheet sat correctly at the bottom. Where it was mounted **bare** inside `s.root`'s column flow (PlaceSheet, StaysSheet, PlaytimeSheet via ExploreSheet), it laid out at the **top of the screen** — head row inside the status-bar inset. That is the '8:25' printed over 'Where to stay'.

**The contract fix — at the primitive, so all six consumers inherit it:**

- `us.sheet` is now `position: "absolute", bottom: 0, left: 0, right: 0` — the sheet owns its seat; callers mount it bare.
- `elevation: 30` on the primitive — Android dispatches sibling touches by elevation before mount order; the sheet must ride above the home pane (24) and the offline pill (26) even while home is mid fade-out. Same z-contract the app's other modal sheets already kept.
- `maxHeight: Math.min(detent, WIN_H() - insets.top)` — the top detent can never reach the status bar, the same contract every flat surface keeps via `paddingTop: insets.top`. Chosen over header `paddingTop` so the head's designed padding stays intact.
- `paddingBottom: insets.bottom` kept — gesture-nav pill never sits on sheet content.

**Regression the fix would have caused, caught and fixed:** CompareSheet and LayersSheet wrapped `<Sheet>` in a `bottom:0` auto-height container. Once `Sheet` itself became absolute, those wrappers collapse to **zero height** — visually identical (child anchors to the strip's bottom edge) but on iOS UIKit's `pointInside` gates hit-testing, so every tap above the strip would never reach the sheet. Both now mount `Sheet` bare (fragments). VehicleSheet's `absoluteFill` overlay + backdrop was already the correct pattern — untouched.

## FIX 2 — a labelled way back on every surface

New **`BackChip`** in `ui.tsx`: a hairline pill in the sibling-door register — `back` glyph + `t("a11yBack")` word (en "back" / hi "पीछे", both already in strings.ts — parity kept, zero new keys), `hitSlop={10}`, `accessibilityRole="button"`. It sits **inside the head's text column** — never the top-right dead zone where the iOS status cluster eats taps (the existing `exploreShared.tsx` workaround comment already documented that corner).

Per surface:

| surface | labelled exit (new) | existing secondary exits (kept) |
|---|---|---|
| StaysSheet / PlaytimeSheet | `BackChip` beside the sibling-door pill inside `ExploreHead`'s text column (new required `onClose`) | grabber-drag + corner ✕ |
| PlaceSheet | `BackChip` inside the head text column | grabber-drag + corner ✕ |
| CompareSheet | `BackChip` → `onBack` — App wires it to `invalidatePicks() + setPhase("search")`: back to the search this plan answered for | grabber-drag + corner ✕ (dismiss to home) |
| Air-map surface | round `MapButton glyph="home"` at top-right, `top: insets.top + 10` (air card owns the left lane; map compass sits at +76) | DayPeek card remains the designed door onto home |
| SearchScreen | — (already had the `a11yBack` glyph arrow at `marginTop: insets.top + 8`) | Android hardware back closes it |
| NavSession | — (already had ✕ in the chrome banner at `insets.top + 12` → `onNavExit` → home) | hardware back consumed by the dispatcher |
| Settings / DelhiToday / Ledger | — (already had back headers at `marginTop: insets.top + 8`) | hardware back |
| Sidebar | — (already had ✕ in header at `paddingTop: insets.top + 14`) | scrim tap |
| WeekSheet / ReceiptSheet | — (already had ✕ / Done actions) | scrim tap |
| Onboarding / CoachTour | — (already had Skip / Next) | — |

## Gates (this box, macOS)

- `npx tsc --noEmit` — clean
- `npx expo lint` — clean
- `node src/store/test-runner.mjs` (18) ✓ `src/nav/test-runner.mjs` (70) ✓ `src/api/test-runner.mjs` (8) ✓ `src/offline/test-runner.mjs` (16) ✓

## FIX 3 — Android AVD end-to-end — **PASS**

Full per-step table in `safearea-e2e.md` (child commit `7fbd428`); 15 frames in `safearea-shots/`. Rig: `demo` AVD = pixel_7 Android 15 google_apis x86_64, KVM + SwiftShader, headless, 1080×2400@420dpi, Delhi fix via `adb emu geo fix` + fused/gps test providers.

- **Before**: stale v7 `alive-90bc055-universal.apk` reproduced the owner's report verbatim — place/stays sheet heads rendered at the top edge with the clock + status icons printed over the band, corner ✕ tangled into the status row, no labelled exit (`before-place-sheet.png`, `before-stays-sheet.png`).
- **After**: a release universal APK built at `ea97dab` on the child (188.9 MB, 4 ABIs incl. x86_64, prod URL baked — bundle markers `BackChip`/`a11yBack` verified) shows every one of 13 walked surfaces with heads clear of the status bar and a working exit tapped: cold open → splash → consent → home → search → air map → where-to (chooser + vehicle modal → nav) → place sheet → stays → playtime → drawer → settings.
- Edge checks: fixed detents mean the maxHeight cap isn't user-draggable (a grabber drag can't raise a head under the bar); no gesture-nav-pill collisions; modal scrim eats outside taps by design; **zero** FATAL/ANR/crash in the full-session logcat sweep.
- **Failures: none.** One non-bug nit logged for a later lane: on the search surface the hardware back key is absorbed by the focused text field (keyboard dismiss) — the visible ‹ in the field head is the functional exit and works (→ air map).

## Verdict

PASS — fix holds on real Android frames. The Sheet primitive owns its seat (absolute bottom detent, elevation 30, top-inset-capped), every surface carries a visible labelled exit inside its head column, and the before/after pairs prove the owner's complaint dead at `ea97dab`.
