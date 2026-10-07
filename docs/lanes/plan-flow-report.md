# Lane report — plan-flow: words + visuals a person can stand behind

Owner complaints (verbatim):
1. "'vehicles like yours' — are you mocking me?"
2. "'leave tomorrow, breathe less' — who the fuck are you to tell me go
   tomorrow? you don't know my purpose"
3. "'journey never started' is dead crap"
4. "complex bar graphs nobody understands"
5. "the route colors are literal stool color on my phone"
6. "vehicle selection needs a before-state and better language"

Branch `base/v2`, direct push. Gates: `tsc --noEmit` clean,
`expo lint` clean, node:test store 84 / nav 76 / api 12 / offline 12 —
0 fail. Server pytest absent on this box (no venv) — label changes
reproduced in-process against `emissions.py` (outputs quoted below).

## 1. "for vehicles like yours" → the truth about what's being estimated

The phrase appeared in three shapes: the emissions provenance sentence
server-side, the receipt's doc-art line, and the vehicle-skip copy.

- `server/emissions.py::_label` — every case now starts "estimated for a
  {year fuel class} ({bs range})". Verified in-process:
  - petrol: `estimated for a 2010–2016 petrol car (BS-III–BS-IV)`
  - EV: `estimated for an electric car (incl. grid electricity) —
    tailpipe zero`
  - year unsure: `estimated for a petrol car (Delhi fleet mix —
    BS-III–BS-VI)`
- `server/v2/strip.py` basis fallback — "the vehicle class; band = class
  spread x speed-curve uncertainty" (was "vehicles like yours").
- `ReceiptSheet` doc-art line → "estimated for this kind of ride ·
  1.1–1.6 kg".
- `vehicle_likeYours` → **"a typical Delhi ride"** (en) / **"मामूली दिल्ली
  गाड़ी"** (hi) — shown on the plan chip on sim (shot 04: "metro ›"
  after choosing; "a typical Delhi ride ›" before choosing).
- `vehicleQ_skip` → "skip — a typical Delhi ride works" (en+hi).
- `test_emissions.py::test_label_shape` asserts the new shape.

## 2. Deferral-as-order → neutral information

The app may show when the air is lightest; it may never tell the person
when to go. Ping copy was reworded earlier this wave; the settings
labels now read as descriptions, and the on-sheet row is a fact + a
consent switch, verified on sim (shot 04):

    tomorrow 02:00  →  ~26% less smoke     ping me

No "leave at", no "go tomorrow". The number is a fact about the air;
"ping me" is the person asking the phone, not the phone asking them.

## 3. "Journey never started" → one honest line

The receipt for a trip that died under ~100 m used to show "Trip ended."
over a full grid of zeros — a dead mock of a report. Now it collapses to
a single honest state (ReceiptSheet, `neverStarted`):

    ended before it really started
    under 100 m — nothing counted

No mode chip, no hero number, no share/save rows. New keys
`receipt_notStarted` / `receipt_notStartedSub` (en+hi). Code-verified —
not repro'd on sim (needs a real nav quit under 100 m).

## 4. Bar graph → felt comparison + flat day-ribbon

- `PairBars` (the four-lane comparative bar graph) removed from the
  option cards. Each card now carries ONE dose micro-bar plus a felt
  line under the meta (verified on sim, shot 03):

      Bike / scooter — 4.71 km · arrive 10:44
      ~2.2× more inhaled than car          ≈5 µg 3–6

      Bike / scooter — 5.01 km · arrive 10:46 · via Baba Kharak Singh Marg
      ~3.2× more inhaled than car          ≈7 µg 4–10

  `compare_feltMore` fires when mid-dose ≥2× the lightest option;
  otherwise `compare_moreVs` ("+{n} µg more than {m}"). The comparison
  word names the lightest mode, not "lightest".
- `DepartGraph` (the 24-candlestick graph) replaced by `DayStrip`: a
  flat ribbon of ~24 cells banded by the served concentration/dose,
  accent tick under the lightest hour, "now"/"+Nh" axis, and the line
  `lightest around tomorrow 02:00 — ≈ 1 µg` (shot 04). Real served
  numbers, zero chart chrome.
- Legend reduced to one honest item: "smoke you breathe".

## 5. Stool-color ramp → clean band palette

`theme.ts` retuned so the CPCB ramp reads at phone brightness against
the warm-paper base — muted gold → amber → ember → brick → maroon; the
olive-khaki and stool-browns are gone:

- band1 `#B9A46C → #C7A34F` (muted gold, not olive)
- band3 `#BE6440 → #C05F3A` (ember — also pinDest + breath2)
- band4 `#974532 → #A83D30` (brick red — also breath3)
- band5 `#62392C → #6E2D28` (deep maroon, not stool-brown)

On sim the candidate routes draw warm amber/ember, the verdict callout
sits in ember text on paper, and the day-strip reads gold → blue "good"
cells at the 02:00 low (shot 04). No muddy mid-tones.

## 6. Vehicle picker — a real before-state

`VehicleSheet` opens on an `intro` step when no vehicle is set (shots
01–02):

    before you pick
    the smoke estimate fits what you actually take — a metro cabin, a
    bike, a car on Ring Road breathe different air on the same trip.

    no sign-in, nothing leaves this phone. you can skip it — the Delhi
    fleet average is a decent guess.

    [ tell us what you're taking ]
    skip — a typical Delhi ride works

After the intro the picker head is **"What are you taking?"** with the
honest caption "your pick sharpens the 'your ride puts out' numbers —
saved on this phone only" and plain groups (your own / shared / no
engine). en+hi mirrors added.

## Files

`server/emissions.py`, `server/v2/strip.py`,
`server/tests/test_emissions.py`, `Mobile/src/theme.ts`,
`Mobile/src/i18n/strings.ts` (appended block), `Mobile/src/components/
shell/CompareSheet.tsx`, `.../ReceiptSheet.tsx`, `.../settings.ts`,
`.../types.ts`, `Mobile/src/screens/VehicleSheet.tsx`,
`Mobile/src/store/vehicle.ts`, `Mobile/src/map/routeTint.ts` (comment).

Shots: `docs/lanes/plan-flow-shots/` — 01 vehicle intro, 02 picker, 03
felt lines, 04 day-strip + notify row + route tint.
