# demo-vid-landing — one continuous video of the live landing page

Lane: `demo-vid-landing` · HEAD `1ff8d62` (`base/v2`) · recorded 2026-10-08 ~14:15 IST against live prod `http://65.2.28.40` (GET-only probing + one brief-mandated `POST /v2/plan` fired by the page's own demo chip). No deploy, no code changes.

## Deliverable

`alive-landing-93s.mp4` — **93.5 s**, 1440×900, 30 fps, h264 (~11 MB). One unbroken take: fresh tab → boot → full top→bottom journey → real trip priced → /city → /community → back to landing → ends held on the close block.

Capture: `playwright-core` over CDP on a dedicated Chrome 154 (`--remote-debugging-port=29229`, isolated `--user-data-dir`, `Emulation.setDeviceMetricsOverride` 1440×900 dsf 1). `Page.startScreencast` (jpeg q82, every frame) → concat-demuxer with real per-frame timestamps → libx264 crf 20. Scrolling via `mouse.wheel` in decelerating ~66 ms steps — reads as a human glide, not jumps. Screencast frames carry no OS cursor; hover states (nav CTA underline, close-CTA arrow shift) render via real `:hover` from CDP input.

## Beats (marks.json, verified against the mp4)

| t | beat | what the live page showed |
|---|------|---------------------------|
| 0–5.6s | boot strip → hero | digit-flip resolves into the live field mean; hero numeral painted **60.8 µg/m³ · moderate** (52 stations, map 1 min fresh) |
| 13.0s | dose equation | 60.8 × 14.4 m³/day = **≈874 µg ≈ 2.8 cigarettes**, all live |
| 17.0s | forecast sparkline | next-11-hours curve, 72.0–101.7 µg/m³ range label |
| 24.0s | kriged Delhi map | full field rendered, district borders, `refreshed 02:15 pm ist` |
| 24→31.6s | **watch-it-work chip** | real click → real `POST /v2/plan` → route draws connaught place → i.g.i.; routeline: *"bike / scooter · least-smoke rd — 28.3 µg inhaled 0.1–56.6 · 21.9 km · ~34 min · 5 options priced"* |
| 40.1s | chooser film-strip | real app capture (India Gate trip, vehicle chooser sheet) |
| 48.8s | mechanism + pledge | steps 01–03, 0.90 M priced / 1.07 M road segments |
| 52.7s | "the city, kept" | typical-October daybars + district rail (29 real boundaries, worst-first) |
| 65.0s | **/city** | parali-watch line live: *"15 fires in the Punjab–Haryana belt, down from 27 over ~5.7 h — a NW wind at 8.2 km/h is carrying it toward Delhi · measured, not reported"*; GRAP card; district choropleth |
| 69.9s | **/community** | "merged, never named" ledger, 3 privacy rules |
| 79.3s | nav CTA | `get the app` hover underline (releases link) |
| 93.6s | close block | "the field knows what delhi breathed — the app knows what you breathed" + `get the app — android & ios builds` + footer `BUILD 63B7ED42` (= live prod sha, proof of prod) |

## Honest notes

- Every number painted live — no dead `—` states anywhere in the take. PM2.5 read 59.5→60.8 across the hour (band satisfactory→moderate); that's the field moving, not a defect.
- The routeline prints engine pricing time; second take read `0.0 s` (cache-warm) vs `1.3 s` on the first — the real displayed value, left as-is.
- Boot replayed because each capture used a fresh tab (`sessionStorage alive_boot_v1` per-tab); the return visit to `/` correctly skips it — one boot, once, exactly like a real session.
- A first 84.5 s take exists (`take1/`) — re-shot only to give the hero numeral, district rail and close block more read time into the 90–120 s window.
- No OS cursor is baked into CDP screencasts; interaction shows through real `:hover` styling and the route draw itself.

## Shots

`shots/` — 01-hero, 03-sparkline, 05-demo-route, 09-city, 10-community, 12-close (jpeg, 1440×900).
