# Sidebar — r4 redesign notes

`Mobile/src/components/shell/Sidebar.tsx` (lane `r4-sidebar`).

## What changed

- **Fixed header** — app mark (accent `wind` glyph on a `surface2` tile) +
  `ALIVE-108` wordmark (accent on `-108`) + round close button; hairline under
  it, stays put while the list scrolls. Close keeps `settingsClose` a11y label.
- **Grouped cards** — `Today` / `This week` / `Trips` stat sections then two
  unlabeled action cards: *navigate* (saved places · Delhi today · my vehicle)
  and *app* (language · trip-data sharing · settings · how ALive works ·
  optional share). Cards are `surface` with `hairlineWidth` borders; separators
  inset to the label edge (50 pt) — iOS-style.
- **Row contract** — fixed 24 pt icon slot · label (+sub/hint) · chevron or
  trailing control · `minHeight` 50 (sub-rows 44) · pressed → `surface2`
  (danger rows → red tint). All pressable rows carry
  `accessibilityRole="button"` + label; expanders report
  `accessibilityState.expanded`.
- **Expanders are inset `surface2` panels** (replaces the left-rail indent).
  Vehicle picker is now a 2-line chip grid (accent border + tinted selected).
- **Language + sharing promoted to first-class rows** (doc 02 §sidebar-7,
  doc 07 §3): EN/हिंदी segmented pill and the donation switch with its one-line
  hint sit directly in the app card — no more digging through Settings.
- **"Delete my data" is a first-class destructive card** — previously it lived
  inside the inline settings expander, which never mounts once
  `onFullSettings` is wired (always, in App.tsx) → the action was dead UI.
- **Put-out stat restored** — doc 02 §sidebar-1 spec is "breathed + put out";
  the second column now renders when today's trips carry real `emit_kg`
  (SEAM(emissions) field already on `Trip`). Still nothing without data.
- **Solid surface** — drawer is opaque `bg`; scrim stays translucent by
  nature. No translucency on any row or card.

## Props — all preserved, three seams added

Unchanged: `open onClose trips lang settings onSettings onDeleteData
onArmBrief onNavigate currentDest onDelhiToday onTripReceipt onFullSettings`.

New optional seams (mission-brief parity; hidden until a parent wires them —
same convention as `onDelhiToday`):

| Prop | Behaviour when wired |
|---|---|
| `onLang?: (l: Lang) => void` | language seg calls it instead of `onSettings({lang})` |
| `onShare?: () => void` | "Share" row appears at the bottom of the app card |
| `onShareTrip?: (tr: Trip) => void` | per-trip share affordance on each Trips row |

## String keys — all reused

No new keys required for this redesign. Proposed via `// SEAM(i18n)` in the
file header if the owner wants text group headers later:

- `sidebarNavigate` — "Navigate" / "नेविगेट"
- `sidebarApp` — "App" / "ऐप"

(Groups currently ship unlabeled — the cards carry the grouping.)

## Verify

`cd Mobile && npx tsc --noEmit` — clean · `npx expo lint` — clean.
