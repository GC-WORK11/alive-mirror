# ALive-108 — 3-minute demo video script

Judging sees a recorded video, not a live demo. Every number below is a
real verified response from the server (numbers drift with the live
field — re-verify on recording day).

## Beats (≈180 s)

**0:00–0:20 — the problem, in one breath**
Voiceover over a Delhi smog shot or the app's live field chip:
"Every Delhi commuter does this twice a day. Nobody checks what the trip
puts in their lungs — because nobody could. Today they can."
On screen: tap the map → floating chip "82 µg/m³ · PM2.5 here · live
field · nearest sample 1.3 km".

**0:20–0:50 — the check that doesn't exist anywhere**
Type FROM: Karol Bagh → TO: India Gate. Real suggestions appear —
down to personal addresses (Photon over OSM). Say: "not a dashboard.
A decision."

**0:50–1:30 — the dose card (the money shot)**
The ranked list fills in, live:

| Option | Inhaled PM2.5 |
|---|---|
| Car (AC) | 3.2–3.8 µg — "breathes least" |
| Car (windows down) | ~5 µg |
| Bike | ~7.4 µg |
| Bus | ~7.4 µg |
| Auto | ~10.1 µg |
| Metro + walk | ~37.7 µg (Karol Bagh → Mandi House stations shown) |
| Bicycle | ~62.7 µg |
| On foot | ~108.9 µg |

Voiceover: "Every number is real — breathing-zone ratios measured on
Delhi roads, your ventilation by exertion, ambient concentration from
live CPCB anchors + CAMS model grid. Tap 'why?' — see the physics."
Open the why-expander on screen.

**1:30–2:10 — time as a lever**
"leave 12:30 — same trip, 86% less PM2.5" hint under the card.
Voiceover: "Delhi's boundary layer collapses overnight and traps
pollution. We model it hourly for five days ahead — the app tells you
when the same trip costs less." (Longer trip → metro can win on dose;
show Karol Bagh → Noida for contrast if time allows: metro 28 µg vs
auto ~75 µg.)

**2:10–2:45 — honesty as the feature**
"AQI apps show you a number that happened an hour ago, at a station
kilometres away, and call it real-time. We show where every number
comes from: measured 40 min ago at RK Puram, 1.2 km away — and when the
field is thin, confidence drops on screen instead of being hidden."
Show a confidence: medium/low row or the field-status line.

**2:45–3:00 — close**
"This is ALive-108: a dose engine for Delhi. Same map apps use —
checked against your lungs." End card: repo link + 'real data only —
every µg traceable'.

## Recording notes

- iOS sim or Android emulator, light theme, notifications off.
- Server locally: `server/.venv312/bin/uvicorn main:app --port 8000`.
- Metro: `cd Mobile && npx expo start` (never under `CI=1` — kills
  watch mode and serves stale bundles).
- Re-verify the day's numbers first: `curl
  "localhost:8000/compare?from_lat=28.6517&from_lon=77.1907&to_lat=28.6129&to_lon=77.2295"`.
- Keep the video to live numbers — never overlay fabricated doses.
