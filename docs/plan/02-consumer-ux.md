# 02 · Consumer UX — every screen, every word

## Principles (enforced at review)
1. **The map is the app.** At rest: map + search bar + hamburger + locate button. Nothing else.
2. **One number per state.** Rest: none (or live breath chip while moving). Compare: one row per option. Trip: two counters. Done: two results.
3. **Words a 12-year-old in Delhi uses.** "smoke you breathe", "smoke your ride puts out", "lighter", "heavier". Never: AQI, PM2.5, µg, dose, exposure, emission factor, BS-IV on consumer screens. Technical terms live only behind "How we got this number".
4. **Show a feature only when it's true.** No empty states pretending to be features; no charts without a question they answer.
5. **Every number has a comparison next to it.** "3× less than auto", never a bare number.
6. **Hindi and English** from day one for all consumer strings (string table, not hard-coded).

## What we delete from the current app
Horizon chips, ambient mode screen, corridor veil toggle, hazard report button on the main map, fires/black-spot layers on by default (move to a layers sheet), "cleanest air near you", lungs widget, streak, every caption explaining a number, the current drawer, the Outfit font, the teal/green accents, glass blur on text surfaces.

## Screen map
```
Rest map ──tap search──▶ Search ──pick──▶ Place card ──"Directions"──▶ Options
   │                                                                    │
   ☰ Sidebar                                                    pick ▶ Trip preview ──Start──▶ Live trip ──arrive──▶ Receipt
```

### S1 · Rest map
- Full-bleed dark map, user puck with heading cone, buildings in 3D at zoom ≥16.
- Top: search bar ("Where to?") with ☰ on its left inside the bar.
- Bottom-right: locate button. Bottom-left: layers button (small).
- Optional, only when moving without a trip: a single chip "breathing heavier smoke here" / "lighter here" (relative to your last 30 min).

### S2 · Search
- Opens full-screen, keyboard up instantly, cursor in field.
- Under empty field: Home, Work (if set), last 5 places.
- Results while typing: first row in <16 ms from on-device index; full results (shops, buildings, blocks, gates) stream in from the server tiers within ~150 ms (doc 04). Each row: icon by category, name, short address, distance from you.
- "Choose on map" and "Your location" rows.
- Outside NCR: result still shown, greyed with "outside Delhi — breath estimates not available".

### S3 · Place card (bottom sheet, half height)
Name, category, address, distance, "Directions" (primary), "Save as Home/Work", "Share". No air numbers here.

### S4 · Options (the core screen)
Map shows all routes; selected route bold, others thin grey. Sheet lists options like Uber's picker:

```
[metro icon]  Metro + walk        34 min   ▮▯▯▯ smoke in   ▮▯▯▯ smoke out    ✓ lightest
[car icon]    Your car             22 min   ▮▮▯▯             ▮▮▮▮
[auto icon]   Auto                 26 min   ▮▮▮▮             ▮▮▯▯
```
- Two 4-step bars (in, out), relative within this trip — no units on this screen.
- Tag on at most one row: "lightest on both", or "lightest for you" + "lightest for Delhi" on two rows when they differ.
- One plain line under the list when it matters: "Metro: about 3× less smoke for you and 6× less for Delhi than your car, 12 min slower."
- Tap a row → S5. Long-press → "How we got this" (numbers, bands, sources).

### S5 · Trip preview
Route on map, ETA, arrival time, distance, the two bars with words ("about 0.1 cigarette of smoke"), "Start".
First trip only: vehicle question appears here (S8) if the chosen mode is a private vehicle and no vehicle is saved.

### S6 · Live trip
- Map tilts to 3D follow-mode, puck snapped to route, next-turn banner at top (arrow, distance, street name), lane/exit when available.
- Bottom bar: ETA · distance left · arrival time.
- Two live counters above the bottom bar: **"You've breathed ≈ 0.04 🚬"** and **"Your ride has put out ≈ 0.3 kg"** — tick smoothly every second (local math, doc 04 §5).
- Voice turn guidance (on by default, mute button).
- Off-route → "Finding a new way…" → new route within ~2 s.
- Tap counters → small sheet: "smoke is heavier on this stretch" segment highlighted on the map.

### S7 · Receipt (auto on arrival)
```
You're here. 31 min.
You breathed ≈ 0.12 cigarettes    — 2.8× less than by auto
Your ride put out ≈ 1.4 kg        — the metro would have put out 0.3 kg
[ Done ]   [ How we got this ]
```
Saved to the sidebar ledger.

### S8 · My vehicle (asked once, editable in sidebar)
Q1 "What do you usually ride?" — scooter/bike · car · auto · cab · bus/metro · cycle/walk (icons).
Q2 (car/scooter/bike only) "Fuel?" — petrol · diesel · CNG · electric.
Q3 optional "Roughly when was it bought?" — before 2010 · 2010–2016 · 2017–2019 · 2020 or later · not sure.
Result line: "Got it — we'll estimate using vehicles like yours." No BS class shown unless they open details.

## Sidebar (hamburger) — redesigned
Full-height, dark, opens from the ☰ in the search bar. Top to bottom:

1. **Header** — app mark + "Today": two big numbers side by side: *breathed* (cigarettes) and *put out* (kg). Under each, one comparison: "less than yesterday" / "about a typical Delhi commuter".
2. **This week** — a 7-day pair of thin bars (in/out). Tap → week detail.
3. **Trips** — list: mode icon, from→to, time, the two numbers. Tap → that receipt.
4. **My vehicle** — current choice; edit.
5. **Delhi today** — opens the consumer city view (doc 07): live map of the city's air, what all ALive trips breathed and put out today, the mission in 3 lines.
6. **Saved places** — Home, Work.
7. **Settings** — voice, language (हिंदी / English), units, data sharing (on by default, explained in one line, one tap off), delete my data.
8. **How ALive works** — one screen, 5 sentences, link to sources.

Rules: no stats dashboard inside the drawer beyond item 1–2; nothing appears without data.
