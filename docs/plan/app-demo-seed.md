# App demo seed — the dosimeter's best honest state on demo morning

How to make the app surfaces (DayPeek → DayScreen) show their best *honest*
state for the video. Everything below is verified in code on `base/v2`
(`a382cde`), not assumed: file + line cited for each claim.

## What a FRESH install shows (verified — every card has an honest state)

| card | fresh-install render | code |
|---|---|---|
| DayPeek (idle map) | "no reads yet — open the map, take a trip, this fills in" (`peekEmpty`); still tappable | `DayScreen.tsx:598`, `strings.ts:490` |
| MorningCard | **live immediately** — 12-h sparkline, heavy/clean windows, server decision lines from `/grid` + `/v2/day`; independent of on-device history. Only empty outside NCR (`dayOutsideDelhi`) or outside the field window (`dayMorningNoCell`) | `dayfield.ts` (12 parallel `GET /grid?h=0..11` + `/v2/day`), `strings.ts:461-462` |
| DayCard "your day" | "still sparse — the phone has sampled today's air too little to count it yet" (`dayThin`) | `DayScreen.tsx:371`, `strings.ts:449`; `thin = daySamples < 3 && dayTrips === 0` at `daylog.ts:280` |
| LensCard (check-in) | fully interactive day 0 — three facets tappable; verdict reads `lensEarly` "a few check-ins in — the pattern needs ~7 days" | `symptomLens` needs ≥7 check-in days (`daylog.ts:301`), `strings.ts:473` |
| TileRow | today "—", 7-day dots all empty rings, budget-left "—" | `DayScreen.tsx` TileRow |
| BudgetCard | renders "within" with the full budget remaining (0 µg); profile pills work | `DayScreen.tsx:534-576` |

**A fresh install is not blank** — the morning card, check-in and budget
carry it. What it lacks is the hero arc: the ≈N µg day number, real arc
bars, and named trip parts. Seeding gets those.

## What the day card needs (the mechanics)

- `thin` lifts with **≥3 ambient samples today OR ≥1 completed trip**
  (`daylog.ts:280`).
- Ambient samples come only from the **foreground** `/aqi` poll — once
  per 60 s while the app is open (`App.tsx:217-246`), deduped below
  8 min / ~450 m (`daylog.ts:96-111`) → **one sample per ≥8 min of
  foreground**. A covered stay-span (arc bar + "HH:MM–HH:MM" part) needs
  two samples ≥8 min and ≤45 min apart (`GAP_INTERP_MS`, `daylog.ts:44`).
- A trip lands in `parts` only after a **completed** nav arrival —
  `recordTrip` runs on the real arrival summary, never on option view
  (`useShellFlow.ts:343-365`). The part row reads
  `"<mode> · <from> → <to>"` with the logged `dose_ug` (`daylog.ts:248`).
- The check-in is one tap per facet, any time — the verdict honestly
  stays "early" under 7 days; that IS the pitch (the lens earns its line).
- Week dots show only today lit on day 0 — honest.

## Demo-morning steps (real phone, ~45–75 min)

1. **Install the sibling-lane APK** (must postdate the dosimeter commits —
   `e849bf6` predates DayPeek/DayScreen entirely). Open once: consent,
   allow location, pick a vehicle. This also proves the first-launch beats.
2. **Foreground dwell ≥20 min** at a desk/café — leave the app open.
   → 3+ ambient samples: `thin` lifts, a real stay-span appears on the arc.
3. **Take one real trip through the app's own flow** — search → compare →
   select a mode → Start → ride → arrive → receipt. Any 5–15 min hop.
   → `parts` gains `"Auto-rickshaw · CP → Khan Market · ~N µg"`-style rows
   and the arc gets trip marks. Two trips of contrasting modes (car-AC vs
   auto/walk) show the product thesis directly.
4. **Tap the symptom check-in once** (breath/eyes/energy).
5. **Open DayPeek → DayScreen once** and confirm: ≈N µg hero, arc with
   real bars, part rows, live morning card, budget bar partially filled.
6. On stage: the same sheet. Every number is real and on-device.

## Emulator fallback (if filming on the box Android emulator)

- `adb emu geo fix <lon> <lat>` — lon-then-lat, ~1.2 s/fix.
- Fixes must be ≥5 m apart — the app filters identical fixes
  (`watchPosition` distanceInterval=5 m); arrival = two distinct fixes
  ≤60 m of the destination.
- Feed the **selected option's own geometry** (match by mode +
  `distance_km` from `/v2/plan`) — don't approximate the polyline, the
  off-route banner fires if the path strays.
- Inside a `while read` feeder loop, use `adb emu geo fix $lon $lat </dev/null`
  or adb eats stdin and the loop dies after ~30 fixes.
- `adb shell settings put secure location_mode 3` if the emulator's
  location provider is off.
- Ambient samples need no GPS trickery: leave the app foregrounded and
  the `/aqi` poll samples the fixed position (must be inside NCR).

## What you CANNOT honestly get before demo day (narrate, don't fake)

- **Lens verdict "link"** — needs ≥7 days of check-ins (`daylog.ts:301`).
  It will read "a few check-ins in — the pattern needs ~7 days". Fine —
  the honest-early state is itself the story.
- **Week dots** — only today lit on day 0.
- **Do NOT hand-seed `daylog.json`** — dedupe and the 21-day keep window
  make fabricated rows fragile; the honest thin states already read well.
