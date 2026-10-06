# Lane report: app-overhaul-v2 — THE component redesign

**Date:** 2026-10-06 · **Drive:** macOS iPhone 17 sim, iOS 26 (Expo dev client, `localhost:8000` backend, live GETs only) · Lane: `docs/lanes/app-overhaul-v2.md` (incl. DECODED REGISTER @6d919dc + HARD ANTI-LIST @00943cb)

**Scope:** every visible surface restyled to the new register — every feature and number kept, expression changed. Light theme only; Fraunces/Plex Mono stay.

## Register deltas (theme.ts — the contract)

- `accent` olive `#4D7C0F` → **forest `#3A6844`** (muted-expensive: deep/saturated/classy; washes re-harmonised). `glassSel` follows.
- `V2Radius` squared → **chunky**: row 8→13, card 12→20, sheet 20→24, pill 999.
- **New `V2Tint` wells** — pastel identity colours (not the CPCB ramp): `forest` (map/go), `sky` (city), `clay` (trips/ledger), `sand`, `plum`; each `{wash, ink}`.
- **New `bandWashMid{,Idx}`** (~18%) — the tinted-hero grammar: a card carries its band.
- `register-card.md` updated in place (web sibling lane shares it — no fork).

## Per-surface before → after

| Surface | Before | After | What changed |
|---|---|---|---|
| Onboarding 1/3 | [img](https://app.devin.ai/attachments/8881cb8f-4f47-4537-b9a8-3e67f619c193/01-onboarding.png) | [img](https://app.devin.ai/attachments/688b5f22-470a-4e83-9ce7-2f0f28e946c1/19-onboarding.png) | serif display headline + three tinted preview cards (sky/clay/sage icon-tile doors previewing the product beats) + ink Next pill |
| Onboarding 2/3 | [img](https://app.devin.ai/attachments/6a27f01e-ed31-46f7-a8a6-a4d0d2fa9145/02-onboarding-p2.png) | [img](https://app.devin.ai/attachments/812d594d-28a6-4e7d-b7ea-08327f177642/20-onboarding-p2.png) | "Nothing personal is stored." serif hero + `3+` hero-numeral card (sage wash) + component bullet rows |
| Onboarding 3/3 | [img](https://app.devin.ai/attachments/fc8b1dd1-78f4-45fc-a5a3-95b9467427b1/03-onboarding-p3.png) | [img](https://app.devin.ai/attachments/199e3711-e68d-404c-bf38-a487f85d3b57/21-onboarding-p3.png) | consent choice = two designed option cards (forest "Share trips anonymously" primary vs ink-bordered keep-local) |
| Home — hero zone | [img](https://app.devin.ai/attachments/454ec37e-79a8-4582-950f-e006c21281e4/04-home.png) | [img](https://app.devin.ai/attachments/8fb53d60-b2ff-4679-a46f-2da52f8f10d1/01-home.png) | band-tinted hero card (≈29 µg serif + % ring + bare `µg` unit + week dots + covered-hours stat row) → ink "Where to?" pill → **DoorRow**: three icon-tile doors (air map/forest · Delhi today/clay-band · your trips/clay) |
| Home — the move + day | [img](https://app.devin.ai/attachments/8eb57bda-b9b9-439c-971c-11bf57d6e394/05-home2.png) | [img](https://app.devin.ai/attachments/48995bb8-1cf5-4261-8a58-45d8b4142d42/02-home-mid.png) | "the move" one-idea card (least-bad window + mini arc + heaviest/lightest winChips); "your day" arc card with accumulated-rows |
| Home — days + felt + budget | [img](https://app.devin.ai/attachments/461d9ab1-cf1e-4c77-a15e-f7e112044a21/06-home-bottom.png) | [img](https://app.devin.ai/attachments/a8a86fd0-dfb8-4ca5-bc39-ac9aa4d372ba/03-home-low.png) | "the days ahead" = five band-tinted day tiles (deep wash); "how you felt" pill rows (good/meh/rough); "your daily budget" segmented pills + bar |
| Sidebar | [img](https://app.devin.ai/attachments/80a62539-5a87-45fc-bd8e-e5af24f732b4/07-sidebar.png) [bottom](https://app.devin.ai/attachments/1d0bdb2a-a38d-48ed-8273-96fd56dd74bb/19-sidebar-bottom.png) | [img](https://app.devin.ai/attachments/d95c7c8f-ffae-4fb8-af54-0db1e6e1ac7f/04-sidebar.png) [bottom](https://app.devin.ai/attachments/838e514c-11db-4c89-968b-8ba7afb379cb/05-sidebar-bottom.png) | stat cards (Today ≈µg / put-out kg), week strip card, **Saved places = 4 icon-tile doors**, language pill group, quiet rows for Settings/How/Share/Delete |
| Search | [img](https://app.devin.ai/attachments/608ccc80-bdd2-4fdc-9a77-ff5a567f6454/10-search.png) [results](https://app.devin.ai/attachments/afd86920-bd74-4b0e-ad9c-ec7b4a3af59b/11-search-results.png) | [img](https://app.devin.ai/attachments/629b55be-29d6-493b-b4f1-69e82f87e2dc/11-search.png) [results](https://app.devin.ai/attachments/d191c461-7576-4127-a1de-42cfd042fd26/12-search-results.png) | style-only (chunky rows, letterSpacing/caps off) — **mount/lifecycle/keyboard-autofocus untouched per search-crash lane guard (5cde4064)** |
| Compare sheet | [img](https://app.devin.ai/attachments/2b3a5456-f4e3-4132-b883-e2ce821ce2a0/12-compare.png) | [img](https://app.devin.ai/attachments/ad70712e-9bde-430a-bd5b-ae42b02f2002/13-compare.png) | vehicle chip, forest leave-by chip, 24h candles, segmented "smoke you breathe / puts out" pills, ink Start |
| Compare — option cards | [img](https://app.devin.ai/attachments/de07275c-b86b-4ac2-96a1-a197b177db4c/15-depart.png) | [img](https://app.devin.ai/attachments/cae1f8c7-ae60-4007-be79-ac4ff29bb1a7/14-compare-options.png) | each option = tinted icon tile + serif ≈µg + band band + eta + radio dot; "lightest for you" forest tag |
| Nav chrome | [img](https://app.devin.ai/attachments/dbe43afe-91d3-495a-b0e8-f39918606052/13-navchrome.png) | [img](https://app.devin.ai/attachments/8eb7606a-9957-458b-bf5e-91c226b08030/15-navchrome.png) | instruction card (tinted turn-tile + distance) + counters card (breathe/puts-out progress bars + ETA strip) |
| Arrival receipt | [img](https://app.devin.ai/attachments/6953607f-e552-42d6-900d-da0060cfb164/14-receipt.png) | [img](https://app.devin.ai/attachments/f20114ac-89f7-4cf5-8b71-93d4e3a0c256/16-receipt.png) | "You're here." + breathed-µg serif hero + vs-foot savings line + 3 stat tiles + "kept on this phone only" + ink Done / quiet Share |
| Map idle (DayPeek) | — (not re-shot before) | [img](https://app.devin.ai/attachments/9dfa0501-d078-4b2b-9311-aa26ba0fc92d/17-map-peek.png) | peek card = today µg + week dots + ambient chip (solid glassFaint chrome, per surface rule) |
| Layers sheet | — (not re-shot before) | [img](https://app.devin.ai/attachments/f162b152-5ca9-423d-98a6-bdc0e192ff99/18-layers.png) | layer rows = tinted glyph tiles + switches |
| DelhiToday | [img](https://app.devin.ai/attachments/bf058371-b4c9-43c7-98d9-5a039c892ead/17-delhitoday.png) | [img](https://app.devin.ai/attachments/5ae8119a-33e1-4745-8465-bb2f3e36f86f/09-delhitoday.png) [low](https://app.devin.ai/attachments/096c43e9-37e1-4227-8663-95f6feb1dd67/10-delhitoday-low.png) | clay-tinted hero (≈1217 µg serif) + pill chips (updated / estimated-from-satellites) + pollutant chips card + 12h candles + honest empties for streets/community |
| Ledger | [img](https://app.devin.ai/attachments/2b90d452-f3c8-40e0-8246-6d1997b0e752/18-ledger.png) | [img](https://app.devin.ai/attachments/90fa06cd-cf45-4c74-af13-b1516225165f/08-ledger.png) | dose hero (trips · µg breathed · kg out) + week-bars card + trip rows as designed objects (tinted tile + O→D + µg + "less than the smokiest way" line) |
| Settings | [img](https://app.devin.ai/attachments/81107dcb-84d8-408d-9fb5-aca783f3dd06/20-settings.png) | [img](https://app.devin.ai/attachments/6cab9a83-29d6-4eca-b685-c5c1c9a0747a/06-settings.png) | My-vehicle card w/ tinted tile + change link; grouped cards instead of caps sections; forest toggles; ink language pill |
| Vehicle wizard | [img](https://app.devin.ai/attachments/73396e13-1e07-4750-a4b6-f68a7782588b/21-vehicle.png) | [img](https://app.devin.ai/attachments/c31fec90-f4c0-4fa2-a1b3-b05b291fc5a5/07-vehicle.png) | option grid cards; selected = forest wash + radio dot |

## Live-function smoke (sim, backend on localhost:8000)

- Full round trip driven: search "Connaught Place" → plan → compare → Start (Car AC) → `simctl location start` over the real 67-pt polyline → nav counters ticked (≈1.5 µg in-flight) → **arrival receipt fired** (≈1.8 µg / ≈0.6 kg / 1.2 km / 3 min / "16.6× less than by On foot") → Done → ledger now lists 2 trips / ≈1.9 µg.
- Honest empty verified live: DelhiToday "streets travellers crossed" + "how Delhi moves" render the designed empty states (no community data on this server).
- Consent OFF persisted through the cycle (`consent.json` sharing:"off" restored); onboarding re-shot via consent reset.

## Gates — all green at HEAD

```
cd Mobile && npx tsc --noEmit         ✔
npx expo lint                          ✔
node src/store/test-runner.mjs         ✔ 18/18
node src/nav/test-runner.mjs           ✔ 68/68
```

## What an APK rebuild must re-verify

- **Numeral fit on a real device:** hero `µg` unit clip was caught+fixed on the sim (title-size "(micrograms)" overflowed the hero row → hero/peek now render bare `µg`; the gloss survives on the peek card only). Re-check hero, ledger hero, DelhiToday hero at EN + HI, plus Dynamic Type at largest text size.
- **New tint wells in the release bundle:** `V2Tint`/`bandWashMid` are pure JS — no native changes — but re-verify dark-adjacent colors under HDR/True Tone (forest vs band0 can read close on OLED).
- **Chunky radii on Android:** shadow math unchanged, but `card: 20` radii + hairline edges deserve one visual pass on the release APK (Android elevation renders darker than the sim).
- **Search interaction path:** untouched behaviorally, but the crash lane's fix will land on top — after it merges, re-drive search→plan on device (keyboard autofocus is exactly where the segfault lived).
- **Onboarding flow on cold install:** re-run consent ON + OFF paths; the three pages are new components.
- **Compare option cards:** tap every row incl. `ⓘ` expander targets — card hit areas changed with the tile layout.
- **Layers/receipt/nav surfaces:** same content, new shells — check drag-dismiss + scrim behavior on device.

## Known non-issues

- 4 spaces of existing `expo lint` warnings? — **zero** warnings emitted; clean.
- `MODULE_TYPELESS_PACKAGE_JSON` warning on test runners is pre-existing package.json shape, unrelated.
- Trip recorded as "Car (AC)" during the after-pass: that was the selected option at Start (geometry cache read bike's polyline for waypoint feed; the driven route overlapped the CP circle so no off-route fired).
