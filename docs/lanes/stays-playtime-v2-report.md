# stays/playtime-v2 — lane report

Branch `base/v2` @ HEAD after rebase. Lane: dedicated stays + playtime
components (owner: "two features … needs a component itself, so warm").
Ships split components replacing the one half-detent ExploreSheet.

## What landed

- **`Mobile/src/components/shell/StaysSheet.tsx`** (new, 212 ln) —
  'where to stay': real hotel rows on hairlines, card-less. Band square +
  name + localized kind + walk time (`<2.5 km → ~N min walk`, else km) +
  the air story (`~N µg` next-24 h mean at THE STAY'S coords + `N µg
  lighter/heavier/same air` vs the anchor's live read). Header carries
  the area line + the honest disclosure ("each number is the next-24 h
  air at that address"); sparse/now-only reads surface as chips, thin
  reads and unrated rows are said, never filled. Row tap → `onPin` →
  the stay lands on the air map through the map's own tap-read.
- **`Mobile/src/components/shell/PlaytimeSheet.tsx`** (new, ~230 ln) —
  'when to go out': 24 hourly bars in CPCB band colour, heights scaled
  to the day's min–max; forest ground-line under the best contiguous
  window, stone under the heaviest; best bars full opacity, rest dimmed.
  Axis reads `now · HH:MM` … `HH:MM · tomorrow`. Then the server's own
  verdict sentence, the lightest window in words ('today 08:30–18:30 ·
  ~93 µg'), the heaviest callout, the 24 h mean, decision lines.
- **`Mobile/src/components/shell/exploreShared.tsx`** (new, 133 ln) —
  shared warm head (glyph well + serif title + anchor line + disclosure
  + the sibling-door pill) + honesty states (HonestLine/HonestChip) +
  `windowWords`/`dayWordSolo` for the day-offset window phrasing.
- **`Mobile/src/components/shell/ExploreSheet.tsx`** — 422 ln combined
  sheet → 38 ln mode router (stays | playtime, cross-linked).
- **`Mobile/src/screens/SearchScreen.tsx`** (+37) — two discoverable
  doors on the untyped surface under `air answers` (same quiet PlaceRow
  register as the intent rows, no tab bar): `where to stay` and
  `when to go out`, both `nearQuery:null` → App resolves a real fix.
  Typed intent rows (from `exploreIntent`) unchanged and still open
  the same sheets anchored to the typed place.
- **`Mobile/src/i18n/strings.ts`** (+28 keys en+hi) — titles, door
  subs, disclosures, window-in-words, walk/km labels, pin hint,
  now/lighter/heavier/same/unrated, thin-read/now-only chips, honesty
  lines, day words, axis 'now'.

## Verified on iOS 26.5 sim (iPhone 17), real prod data (65.2.28.40)

Shots in `docs/lanes/stays-playtime-v2-shots/`:

- `01-search-doors.png` — untyped search surface: air answers section
  with both doors.
- `02-stays-list.png` — StaysSheet 'near you': 5 real rows (OYO City
  Castle, Sunshine Palace, Metro Star, Bricks), each `hotel · ~5 min
  walk · ~105 µg · N µg lighter`.
- `03-playtime-bars.png` — PlaytimeSheet: banded 24 h strip (forest
  under best 08:30–18:30, stone under worst 21:30–06:30), verdict
  'least-bad window 08:30-18:30 today, ~93 µg/m³ avg — 4 lighter than
  now', `lightest window — today 08:30–18:30 · ~93 µg`, `heaviest —
  today 21:30 – tomorrow 06:30 · ~128 µg`, `24 h avg ~110 µg/m³`.
- `04-stay-pin-map.png` — a stay row's tap drops the pin and the map's
  tap-read answers at that spot (88 µg/m³ · this spot).
- `05-search-intent.png` — typed 'hotels near karol bagh' → intent row
  'stays — lightest air first · near karol bagh' above real results.
- `06-stays-karolbagh.png` — intent-anchored StaysSheet: Hotel Grace,
  Tjs Royale, OYO Royal Holidays, Aster Inn (~109 µg · 1.4–1.5 lighter).

## Fixes made during drive

- Playtime strip: dropped the in-bar 'best' label and the floating
  'now' word — both clipped to two letters inside a 24-cell strip;
  'now' now lives in the axis as `now · 08:30`.
- xcodebuild touched `project.pbxproj` during the sim build — reverted,
  not committed.

## Gates

- `npx tsc --noEmit` clean, `npx expo lint` clean.
- Runners: nav 100/100, search 12/12, api 37/37, offline 16/16,
  store 100/100 — all green.
- xcodebuild Debug iphoneos-simulator build: ** BUILD SUCCEEDED **.

## Notes / leftovers

- House nit, not mine: every top-flowing half-detent sheet's title sits
  under the iOS status-bar clock (same on PlaceSheet today). Left
  consistent rather than diverging inside this lane.
- Stays list shows a couple of near-duplicate OYO names — server data.
- Deferred-input lag on first type (~5 s to first results) on the sim —
  pre-existing `useDeferredValue`+`startTransition` register, not this
  diff.
