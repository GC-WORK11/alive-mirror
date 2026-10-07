# ALive-108 — 3-minute demo video script (v2, matches shipped product)

Judging sees a recorded video, not a live demo. Every number below is a
real verified response from the server (numbers drift with the live
field — re-verify on recording day). Re-pinned Oct-7 on live build
`698cf808` (Karol Bagh → India Gate, 24 options, `smoke_modifier` ×1.06):
Car AC 3.8 µg → on foot 117.1 µg (~31×), metro+walk 43.4, depart now
~20.7 on the demo OD → leave-later −16% there today (row present;
0/absent on the script OD — always day-read, see the 2:05 beat).
**New since this script last synced: the route chooser animation
(`e2ff634`) — fold it into the 0:18–0:45 beat as written there.**

## Beats (≈180 s)

**0:00–0:18 — the problem, in one breath**
Cold-open is a FELT line (winner-video pattern — scenario before
product, docs/15): "It's morning in Delhi. The air outside your door
is four cigarettes today — and nobody told you." (≈1,386 µg day ÷ 316
µg/cig — re-derive the count on recording day from /v2/day breath.)
Then the pivot: "Every Delhi commuter does this twice a day. Nobody
checks what the trip puts in their lungs — because nobody could."
On screen: the home hero breathes its band edge — ≈N µg already
breathed — then tap the map → chip "67 µg/m³ · PM2.5 here · nearest
sample 1.3 km".

**0:18–0:45 — a decision, not a dashboard**
Type FROM: Karol Bagh → TO: India Gate. Real Photon suggestions down to
street addresses. Hit GO and let the **chooser animation play**
(`e2ff634`, shipped Oct 7): up to three candidates draw as equals, the
camera unions all bounds, then the winner settles bold ~1.5 s in and the
**verdict pill** pins the server's own reason line ("cleanest · N% less
than fastest") beside the winning path. Only then zoom: the route is
*coloured by dose*, segment by segment (slate→crimson→dark-red) — the
trip as a hot-zone map.

**0:45–1:25 — the dose card (money shot)**
24 options served on this OD today; the sheet sorts by actual inhaled
mass:

| Option | Inhaled PM2.5 (Oct-7 `698cf808`) |
|---|---|
| Car (AC) | 3.8 µg — "least inhaled" |
| Car (windows down) | 6.9 µg |
| Bike | 8.1 µg · Bus | 9.9 µg |
| Auto-rickshaw | 11.2 µg |
| Metro + walk | 43.4 µg (station names shown) |
| Bicycle | 51.9 µg |
| On foot | 117.1 µg — ~31× the car |

Voiceover: "Breathing-zone ratios measured on Delhi roads, your
ventilation by exertion, live field from 52 WAQI+DPCC anchors + ~97
CAMS-grid samples. Tap 'why?' — the physics is on screen." Open
why-expander — it now also carries the day's `cause_note` (fires ·
carry wind · ventilation · trend, measured-not-reported). Then tap
Auto — the whole polyline repaints crimson.

**1:25–2:05 — the Lung Ledger (the product)**
Tap "today" pill. Sheet rises: **11.5 µg inhaled today · 0.04
cigarette-equivalents · 5% of the ~216 µg daily budget · avoided
167.9 µg** + the 24-hour decade-median curve (current IST hour lit).
Voiceover: "Every trip rolls into your lung account — cigarettes, not
abstract AQI. That's Berkeley Earth math. And 'avoided' is the number
that matters: real µg this commuter did NOT inhale because they picked
the car over the walk."
(For the walk commute it's the reverse pitch: the ledger makes the
invisible cost visible — that's the point.)

**2:05–2:35 — time as a lever + ambient**
"leave HH:MM — same trip, N% less PM2.5" — read the percent + slot
straight off the compare sheet's leave-later row ON RECORDING DAY.
The row only exists when the served percent clears 8 (`pct_less_vs_now`
> 8): it read **16% on the demo OD / 0 — absent — on the script OD** at
the Oct-7 `698cf808` pin; the Oct-1 "83%" was a uniform-field day and can
never be promised. If the row isn't up, narrate the DepartGraph 24-h curve's
own dip→overnight climb instead, don't force the beat. → tap
**remind me** → real iOS notification permission → "set ✓". Then
crescent → **Ambient Mode**: black screen, clock, giant PM2.5,
"breathe least at HH:MM" (the day's best slot).
Voiceover: "Delhi's boundary layer traps pollution overnight; we model
it hourly about four days out. Your phone tells you when the same trip
costs less — then keeps it on the glass where you glance."

**2:20–2:40 — AWS beat (mandatory)**
Screen-record the AWS console, ~10 s: ECS cluster `alive108` (service
RUNNING) → Elastic IP `65.2.28.40` → NLB listener → phone browser on
`http://65.2.28.40/health` returning JSON (125-station climatology,
build_sha `698cf808`) → Secrets Manager `alive108/openaq` +
`alive108/waqi` + `alive108/admin-token` (where the keys live — the
token now mints an HMAC-signed HttpOnly session cookie via
`POST /v2/admin/login`, no client-side storage). Voiceover:
"CodeBuild builds the image inside AWS, ECR stores it, Fargate runs it
serverless, a Network Load Balancer fronts it — the same engine the app
on this phone is talking to."

**2:40–3:00 — honesty close**
Tap a thin-field point → confidence drops, "nearest sample X km" shows.
"AQI apps show a number from an hour ago at a station kilometres away
and call it real-time. We show where every number comes from — and when
the field is thin, confidence drops instead of hiding. Real data only:
every µg traceable." End card: repo + tagline.

## Recording notes

- iOS sim or Android emulator, light theme. Server:
  `server/.venv312/bin/uvicorn main:app --port 8000`. Metro:
  `cd Mobile && npx expo start` (never `CI=1`).
- Text input on sim: `xcrun simctl pbcopy <udid>` + Cmd+V (typing drops
  chars).
- Re-verify day-of numbers:
  `curl "localhost:8000/compare?from_lat=28.6517&from_lon=77.1907&to_lat=28.6129&to_lon=77.2295"`
- Mixed-colour segment spans need a non-uniform PM day; on uniform days
  the whole line is one bin — that's honest, narrate it as such.
- Never overlay fabricated doses. Ever.
