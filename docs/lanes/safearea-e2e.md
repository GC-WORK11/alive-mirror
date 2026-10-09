# safearea-e2e — Android sheet safe-area fix verified on KVM AVD

Lane: safearea-e2e · date: 2026-10-09 · rig: this Linux KVM box
Emulator: `demo` AVD = pixel_7, Android 15 (API 35), google_apis, x86_64 · `-accel on` KVM + SwiftShader (`-gpu swiftshader_indirect`), `-no-window`, 1080×2400 @ 420 dpi · Delhi fix injected via `adb emu geo fix` + fused/gps test providers (`adb root` required for MOCK_LOCATION ops).

**Before build**: `alive-90bc055-universal.apk` (v7, sha256 `77654098…`), the stale release that produced the owner's bug report.
**After build**: release universal built on this box at HEAD **`ea97dab`** ("safe-area: Sheet self-anchors + caps detent at top inset; labelled back on every sheet surface") — 188,884,524 B, 4 ABIs incl. x86_64, `http://65.2.28.40` baked ×1, `usesCleartextTraffic` re-added post-prebuild, hermesFlags `-O -fstrip-function-names -g0`, bundle markers `BackChip`×1 `where to stay`×1 `a11yBack`×1.

## Before evidence — bug reproduced on v7

| surface | shot | what the frame shows |
|---|---|---|
| place sheet (search → Connaught Place) | `before-place-sheet.png` | Sheet head "Connaught Place / Delhi / air there now ~99 µg/m³" rendered at the TOP of the window; status bar (4:41 clock + icons) prints over the sheet's top band; the sheet's corner ✕ collides with the status icons; no labelled exit |
| stays sheet (search → "where to stay") | `before-stays-sheet.png` | Head "stays" + grabber at the top edge under the 4:45 clock; corner ✕ again tangled into the status icon row — the owner's "'8:25' printed over 'Where to stay'" verbatim; no labelled exit |

## The walk — every step at HEAD `ea97dab`

| step | surface | shot | overlap-free | exit present + type | exit works | notes |
|---|---|---|---|---|---|---|
| cold open → splash | first-run 'a→alive' wordmark | `after-00-splash.png` | y | n/a (timed first-run sequence) | n/a | brand frame, no chrome; status bar clear |
| consent/onboarding | consent page 1 | `after-01-consent.png` | y | Skip (header, top-right) | y → location dialog → notif dialog | "Skip" + all text below the bar |
| home | home surface | `after-02-home.png` | y | n/a root surface; menu ≡ below bar | y | live Delhi read ~99 µg/m³ "poor" at injected fix |
| search | from/To card + "Where to?" field | `after-03-search.png` | y — card top edge below bar | ‹ chevron inside field head + system back absorbed by field focus | y → air map | air answers doors visible (stays/playtime) |
| air map | "the air map" surface | `after-04-airmap.png` | y — header card + home button below bar | round **home** MapButton top-right + tap-readout ✕ | y → home | 52 live stations; readout "103 µg/m³ — poor · Connaught Place" |
| where-to · chooser + vehicle card | "before you pick" modal over chooser | `after-05-chooser-backchip.png` | y | modal ✕ + "skip — a typical Delhi ride works"; chooser behind has ‹ back + corner ✕ + top-pill ✕ | scrim correctly eats outside taps (not a dead end) | modal-first ordering is correct behaviour |
| where-to · chooser | option chooser sheet | `after-06-chooser.png` | y — top pill + sheet head below bar | **‹ back** BackChip in head column + corner ✕ + top-pill ✕ | y → back to To-pick surface | Car (AC) options, "start journey" CTA |
| nav mode | turn-by-turn chrome | `after-07-nav.png` | y — "Head out" pill below bar | ✕ in nav pill top-right (+ recenter) | y → journey-end card ("under 100 m — nothing counted") → Done → home | tilted 3D follow view, breathe ≈0.1 µg / emit 4 g counters live |
| place sheet | map long-press pick | `after-08-place-sheet.png` | y — **sheet now a bottom detent, map fills top** | **‹ back** BackChip + corner ✕ | y → air map | "near Baba Kharak Singh Marg" — **pairs with before-place-sheet** |
| stays sheet | "where to stay" | `after-09-stays-sheet.png` | y — head mid-screen, nothing under clock | **‹ back** BackChip + sibling door "when to go out" + corner ✕ | y → air map | live rows ~112 µg each — **pairs with before-stays-sheet** |
| playtime sheet | "when to go out" | `after-10-playtime.png` | y | **‹ back** BackChip + sibling door "where to stay" + corner ✕ | y → search | rolling-24 h banded curve, least-bad window live |
| drawer/sidebar | ALIVE drawer | `after-11-drawer.png` | y — ALIVE title + ✕ below bar | ✕ top-right | y (settings opened from it) | trips/saved places/language visible |
| settings | Settings sheet | `after-12-settings.png` | y — "Settings" title + ‹ below bar | **‹ back** header | y → home | all groups render (vehicle/language/privacy/notifications) |

## Edge checks

- **Full-detent reach**: sheets ship fixed detents (maxHeight cap = window − top inset, not user-draggable); a grabber drag on stays left the detent unchanged — the head can never reach the bar.
- **Gesture-nav pill (bottom)**: no collisions on any frame; list content scrolls under it normally (standard Android edge-to-edge).
- **Sheet edges vs pills/banners**: top pills on chooser/nav and the "13 min old" freshness chip all clear of the status bar and of each other.
- **Modal scrim**: "before you pick" eats taps outside the card by design — verified, then skip exits it cleanly.
- **No dead ends**: every visible exit was tapped and produced a sane destination (search, air map, home, journey-end → home).
- **Logcat sweep**: 0× FATAL EXCEPTION / ANR / crash across the entire session (9 `tombstoned`-service boot-log mentions only — noise).
- Splash handoff frame caught (`sp4` in raw captures) showing consent fading in below the bar — not saved to repo (onboarding, not a sheet).

## Verdict

**PASS** — the fix holds on real Android hardware frames. Every sheet surface at `ea97dab` keeps its head below the status bar (the bottom-detent anchor + top-inset cap works exactly as designed), and every surface carries a visible, labelled, working exit: ‹ back chips inside sheet heads (place/stays/playtime/compare), the round home button on the air map, the ✕ in nav chrome and sheet corners, the ‹ header in settings, scrim+skip on the explainer card. The two before-shots reproduce the owner's bug verbatim on v7; the corresponding after-shots show the same surfaces fixed.

## Failures found

**None.** One UI note, not a bug: on the search surface the system back key is absorbed by the focused field (keyboard dismiss), so the visible ‹ in the field head is the functional exit — which works (verified → air map). If anything, the field-focus back-key swallow is a possible future nit to route through the same exit, but every surface still has a working labelled exit, so no finding.
