# Judge-lens audit — the 90-second look

Ranked by "a hackathon judge would notice this in the first 90 s of the demo."
Status noted per item; the fixes shipped on base/v2.

| # | Judge notices | Status |
|---|---|---|
| 1 | "≈ 0 cigarettes" on a fresh install — approximates a known-zero; the receiptSaved line also dropped its unit entirely | **Fixed** — `approx()` folds the ≈ inside, exact zeros render "0"; missing `cigarettes`/`सिगरेट` unit restored (3b0ff3d + earlier) |
| 2 | Hindi mode leaks English — stored sentinel names ("your location", "Dropped pin") stayed English in trip rows, share text, ledger | **Fixed** — `placeNameLabel` re-renders sentinels in the current lang everywhere they surface |
| 3 | Map labels English-only — Google Maps Delhi shows English + Devanagari | **Fixed** — bilingual `latin\nname:hi` on major roads, civic/transit POIs, localities; romanized dupes suppressed (a6e88d6) |
| 4 | Unset Home/Work rows looked tappable but did nothing | **Fixed** — "set" affordance opens search (or choose-on-map) and lands the pick in the slot; verified end-to-end on sim (d41ca6f) |
| 5 | "can't reach the server — trying again" strip flashed during 25 s plan waits while requests were succeeding | **Fixed** — offline strip needs 2 consecutive health misses (150397d) |
| 6 | Delete-my-data confirmed then sat on the same sheets — user couldn't tell it ran | **Fixed** — closes settings + sidebar as the visible ack |
| 7 | Units row in Settings dead-silent — reads broken | **Fixed** — "metric only" hint explains it's informational |
| 8 | Business POI density vs Google — fewer restaurants/shops named | **Documented, not closeable keyless** — OSM Delhi shop coverage is thin; all POI classes are already filtered in (see map-vs-google.md) |
| 9 | Metro line-colour badges (Yellow/Violet pills) absent | **Not closeable keyless** — line refs not in OMT tile attrs |
| 10 | Small icon buttons (sheet close ✕, attribution) — ~28 px hit areas | **Pending Android verification** — queued in the forensic child; if taps land outside, add hitSlop (already 8 on several) |
| 11 | **SIGSEGV on search sheet** — the app's only RN `Modal` segfaulted on present/dismiss (3 live repros: cold present, quick-pick dismiss, first open; `SIGSEGV(11)` in runningboardd) | **Fixed** — search now renders as a plain absolute overlay + `ui.Sheet`-style surface like every other sheet; `BackHandler` covers Android back; focus moves to a rAF post-mount (1e5d9b1 → rebased 8db9635) |
| 12 | **Layers sheet bled behind compare** — toggles rendered stacked under the compare sheet when left open | **Fixed** — layers auto-closes when phase leaves idle (same commit) |
| 13 | **"0–0 µg" / "0.0–0.0 kg"** degenerate bands on the nav card | **Fixed** — band collapses to a single number when lo/hi round equal (a6c4fe8) |

## Verified on-device this leg

- Home/Work set-flow both paths: search pick → "Karol Bagh"; choose-on-map →
  reverse-geocoded "Windsor Place"; clear-X restores "not set".
- Bilingual labels live on sim: Janpath/जनपथ, Ashoka Road/अशोका रोड,
  Jhandewalan/झंडेवालान, Sarvodaya Bal School, Fateha Jame Mosque.
- Layers toggles (fires / crash spots / measured streets) flip and persist.
- Search sheet open ×3, quick-pick → compare, Start → nav (banner + dose
  cards + ETA), banner-X → receipt, Done → idle — all post-Modal-removal,
  zero errors. Ledger + trip-detail expand clean.

## Watchlist (Android forensic pass will confirm)

- Sheet close-X tap precision (small target).
- Switch tap targets (iOS sim ignores coordinate taps on native Switch —
  a11y-verified; Android child logs real-target behaviour).
- Stutter on sheet open during tile-heavy pans.
