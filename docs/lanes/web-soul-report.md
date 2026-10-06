# web-soul report

Lane: `docs/lanes/web-soul.md` — carry the app's soul pass (breathing hero edge, deeper band washes, hour-aware greeting, verdict-washed cards) to `/`, `/city`, `/community`, and lightly `/admin`. Plus two owner mid-flight mandates applied inside this pass:

1. **One accent, everywhere** (same psychology as app commit `57092e0`) — every functional chip / icon well / action accent on landing, city, admin uses the forest family; the muted CPCB ramp survives only where hue *means* air quality.
2. **Ink3 contrast** (app commit `25bc92c`) — `#8A8D94 → #6E7278` (≈4.6:1 on paper, AA) where text must read; deliberately-faint furniture moved down to `--ink4`.

## What changed

### `/` — landing
- `.hnum` hero tile is now verdict-washed in the day's band: JS reads `pm2_5.mean` → `bandIdx` → `--hw:var(--bd{band})` (the deep, 74%-white wash — the app's "26% band feel"), `--ht` a 60% wash, `--nv/--ni` the band ink. Numeral + provenance sit in band ink, not plain ink.
- Breathing edge: `@keyframes breath{0%,100%{opacity:.12}50%{opacity:.32}}` on `.hnum.breathe::after` — 1.5px band-ink ring, `4.4s ease-in-out infinite`, `inset:0`, `pointer-events:none`, `border-radius:inherit`. `prefers-reduced-motion:reduce` → `display:none`. The page's only breathing element.
- Hour-aware greeting (web is English-only): an IIFE computes IST (+330) part-of-day and prepends it into the hero eyebrow's text node — `good evening · delhi ncr — a dosimeter without hardware`. One warm line, then the existing stamp; nothing else touched.
- One-accent sweep: `.door.alt` class deleted (both doors now identical forest wells), `.step.s1/.s2/.s3` band parades → `--accWash` for all three, `.sec-tick.t-b2/.t-b3` band variants → `.t-acc` forest. Band hues remain on AQI chips, day raster cells, district chips — where colour is the data.

### `/city`
- The big day-AQI card: `/v2/outlook` `days[0]` (today) `.day` tile takes `--dw = washHex(band,.74)` (deep) vs `.78` for the other four, `--de` a 60% wash border, `--he` the band-ink edge, `class="day breathe"` — same `breath` keyframes + reduced-motion gate. One breathing element per page, honoured.
- Per-day band washes unchanged elsewhere; the map keeps true CPCB fills.
- Empty-state row "no street has enough phones yet…" moved ink3→ink4 (deliberately-faint furniture). "feed unreachable — retrying" stays on ink3 (a live status that must read).

### `/community`
- "The ledger" totals card gets the clay-ish wash: `#E8DDDA` bg, `#D0BBB6` border, `#DCC8C3` internal row hairlines, radius 16 — the app's clay register. Forest accent untouched; zero numbers removed or invented.
- `td .empty` / `.rline .empty` → `--ink4` (empty-state furniture).

### `/admin`
- Light touch per the brief: the "field state" panel (the status hero over the feeds table) takes `class="panel breathe"` + the same `breath` keyframes in the admin accent-ink — it reads as aliveness (the field is live), not decoration. One breathing element.
- One-accent sweep: `.kchip.brick`/`.kchip.wine` rules removed; `'brick'`/`'bronze'` card classes → `'accent'` on the dose and CO₂ cards. Kept semantic hues: the `doseInk` severity ramp (it encodes dose level), `.badge.stale`/`.crit` status, band dots — those hues carry meaning.
- Admin `--ink3:#65707F` left alone — it's the backstage's equivalent weakest-reading ink and already measures ≈5:1 on paper.

### ink3 contrast (all four)
- `--ink3:#8a8d94` → `#6e7278` on landing, city, community (community also gains `--ink4:#a6acb8` it never declared). Every `var(--ink3)` label/caption/provenance line gets AA automatically.
- Furniture kept faint on ink4: landing "no named place within 150m" + "district feed resting…", city "no street has enough phones yet…", community `.empty` states.
- Literal fallback `#8a8d94` (district chip unknown-colour) → `#6e7278` to match the token.
- Non-text ink3 uses (`.tl-range` progress, `.lbar` dose ticks, the dose-curve polyline stroke) stay on ink3 — they're data-bearing marks, and the bump makes them *more* legible, not less.

## Verification

Local serve: `/tmp/web_proxy.py` on `:8410` — serves the edited `server/*.html` for `Accept: text/html`, proxies every other route to the live ELB (mirrors `main.py`'s `/community` content negotiation). Captures via `tools/cdp_shot.py` against headless Chrome (`CDP setDeviceMetricsOverride`, DSF 2, 11s settle, full-page).

Before/after PNGs (1280px + 390px mobile metrics) in `docs/lanes/web-soul-shots/{before,after}/`. All live numbers intact — 24 stations, 1.7 cig-day ≈527µg, 5-day outlook row, ledger counters, district chips, admin tables.

**Breath evidence** — two techniques:
1. CDP `getComputedStyle(el,'::after')` sampled twice ~2.1s apart on live animations: landing `0.31→0.14`, city `0.30→0.13`, admin `0.30→0.15` — all inside the .12↔.32 sine, 4.4s period.
2. Phase-locked captures (`*-breath-a/b.png`): injected stylesheet pauses the `::after` animation at opposite phases (~.12 vs ~.32). On city's today tile the ring rows read `rgb(244,244,131) → rgb(251,251,167)` — a ~36pt blue-channel delta on exactly the 2px edge line. Perceptible across two frames, subtle.

Note on method: plain `Page.captureScreenshot` pairs 2s apart came out byte-identical — headless composites deterministically and never produced a new frame mid-animation; that was a harness artifact (plus the tile initially sat below the 900px capture viewport), not a missing breath. The phase-locked pair is the honest pixel proof.

`prefers-reduced-motion:reduce` → `display:none` on all three `::after`s (verified in the rules, no breathing element under reduce).

Script blocks of all four pages pass `node --check`.

## Caveats

- ELB is flaky under parallel page fetches: `/ncr.geojson` and `/grid` occasionally starve past their 15s abort, and Chrome's shared-profile cache pinned a stale gzip entry early on (cleared with a fresh profile + `disk-cache-size=1`). The retaken city shots show 1192 map nodes + 5 tiles; when the feed misses, the page already degrades honestly ("boundaries unreachable — the numbers below still load"), unchanged by this pass.
- Today-tile breath exists only when `/v2/outlook` answers — no tile, nothing to breathe. Same contract as the app's hero card.
