# Lane report — city + community overhaul

**Date:** 2026-10-06 · **Lane:** city-community-overhaul (sibling of `landing-overhaul` + `admin-overhaul`) · **Verdict: SHIPPED**
**Files touched:** `server/city.html`, `server/community.html` only — two self-contained pages, no `server/*.py`, no deps, no new fetch routes.

## Diagnosis (what read AI-generated)

**`/city`** — the page had all the right machinery (choropleth, forecast scrubber, reach painter, archive replay, outlook strip, ticker, ledger, corridors) but **buried the one number a judge lands for**: the live city mean appeared only as a chip inside the ticker, below the map, after a 5-line prose dek that explained acronyms before showing air. The choropleth painted **raw official CPCB hexes** (`#00B050 #92D050 #FFFF00 #FF6500 #FF0000 #C00000`) — neon against the warm register, the same trap the admin lane caught. The one breathing edge lived on today's *outlook tile*, a mid-page row, instead of on the page's actual answer.

**`/community`** — the privacy story was **three paragraphs of prose before a single number**. k≥3 — the thing that makes "no profiles" true — was mentioned once, buried mid-paragraph 2. `dose_ug_24h` was fetched from `/community` but never surfaced in the hero count. The claim "we can't leak what we never take" was asserted as text, not shown as mechanism.

## What a judge sees in <60s now

- **`/city`**: eyebrow → h1 → **the today card**: one hero numeral (live NCR mean µg/m³), the band chip with the official CPCB word + AQI, the honest range across the served map squares, and district texture (count live, easiest vs heaviest). The card sits in the deep band wash with the **breathing band-ink edge** — the page's one ambient motion. Then one 3-line dek, `why tonight`, `grap`, then the map with its three control rows, legend, and the 5-day strip — ticker, ledger, minimap, corridors below the fold, unchanged.
- **`/community`**: eyebrow → h1 (*"What Delhi breathed together — merged, never named."*) → 2 tight deks → **the proof strip**: three numbered pipe tiles showing the actual privacy mechanism (cut on your phone → merged, never filed → 3 phones to appear) — k≥3 made visible instead of described → links → the live count line (now including trips all-time + µg breathed 24h). Ledger, corridor table, flags, footer unchanged.

## Decisions

- **Today card over prose** — `/v2/city` already serves `pm25_stats.mean` + `grap.aqi`; the card renders them first, prose second. `hWhat` is a static plain-English label, everything else is live or an honest placeholder ("reading the live field…" / "live feed unreachable" / "the live field is still warming" / "district feed resting").
- **District denominator consistency** — the hero count uses *all* `/v2/districts` rows with `aqi != null` (29, same as the ticker's "districts live" chip), not just `level==='district'` (16) — hero and ticker can never disagree. Extremes come from the same rows.
- **k≥3 as structure, not text** — the mechanism is already enforced in `server/community.py` (`_K_MIN_DEVICES=3`, 72 h window, no per-trip rows at rest). The three tiles state it as rules; the ledger and corridors table remain the evidence. The `tnote` under the table no longer re-explains k≥3 (it pointed at prose that didn't exist — now points "above").
- **`dose_ug_24h` surfaced** — fetched since forever, never displayed; now in the count line as "µg breathed · 24h" (renders honest `0.0 µg` when the day is quiet).
- **`obs_total` added to the count line** — "trips shared · all-time" alongside the 24h figures, so an all-quiet day still shows the ledger has history.
- **No second accent** — the pipe tiles' number chips are the forest accent family (`--accInk` on `--accWash`/`--accTint`); band hues stay reserved for air-quality meaning. Community's `:root` gains the acc token family + `--surf2`, matching landing/admin.

## Muted ramp, never neon

`BANDS` in city.html now paints the product ramp `#7AAB59 #C8B25A #D58C4A #B85442 #8F3C49 #6E3C54` (same `--b0..5` as landing + admin). **Band names stay the official CPCB categories** — only the hexes changed. This recolours the choropleth fills, the legend chips, the day-strip washes, the detail popover's category chip, the dose chips, and the archive mosaic in one move. District detail `.d-cat` now picks ink text on the three light band surfaces instead of the old two-name whitelist (same behaviour, band-ramp-safe).

## Breath edge relocated

The page's single ambient motion moved from `.day.breathe` (today's outlook tile, mid-page) to `.htoday.breathe` (the today card) — same 4.4 s sine opacity 0.12↔0.32 on a 1.5 px band-ink ring, `prefers-reduced-motion` gated. Today's day tile keeps its deeper wash (`--dw` .74) and band-edge hairline; the CSS rule for `.day.breathe` stays defined but unused.

## Kept, per spec — nothing removed

Every id queried by the script, every control row (`#tl`, `#rch`, `#rc`), the detail popover, minimap canvas, `whyline`/`grapline`, all nine ledger stats, the corridors table, the report lines, the statusline, both refresh loops, the honest-empty states, the noscript block — all still present and wired. Test markers `id="whyline"` + `cy.why` preserved.

## Stat-truth spot-checks (page ⇐ live prod field)

| Page figure | Live field | Verified |
|---|---|---|
| hero numeral `56` µg/m³ | `/v2/city` `pm25_stats.mean` = 55.6 → round 56 | ✓ |
| chip `Satisfactory · aqi 93` | `/v2/city` `grap.aqi` = 93 → `bandOf` = Satisfactory | ✓ |
| `across the map: 26.6–88.2` | `/grid` served cells min–max (ticker prints same pair) | ✓ |
| `29 districts live` | `/v2/districts` rows with `aqi != null` = 29 | ✓ |
| `easiest east delhi 71 · heaviest sonipat 146` | per-row `aqi` min/max over the same 29 | ✓ |
| `14 phones sharing` | `/community` `contributors` = 14 | ✓ |
| `22 trips shared · all-time` | `obs_total` = 22 | ✓ |
| `0.0 µg breathed · 24h` | `dose_ug_24h` = 0 (honest zero) | ✓ |
| `726 µg pm2.5 dodged · all-time` | `avoided_ug_all` = 725.9 → `IN` = 726 | ✓ |
| corridors 01–05 | `top_corridors[0..4]` name/trips/devices/dose/co₂ | ✓ |

## Gates

- `node --check` on both extracted `<script>` bodies: clean.
- `pytest tests -k "city or community"`: **70 passed, 1 skipped** (includes `test_city_html_has_why_line`).
- Served-check via local proxy (local HTML + live prod APIs): both pages fetch, paint, and degrade honestly when feeds fail. (Proxy had to mirror main.py's `Accept: text/html` content negotiation for `/community` — fetch sends `*/*` → JSON.)

## Proof (`docs/lanes/city-community-overhaul-shots/`)

| Shot | Shows |
|---|---|
| `before/city-1280-fold.png` | fold before: mean buried in ticker, wall of dek prose, neon map |
| `before/city-390.png` | 390 before: same, stacked |
| `before/community-1280.png` · `before/community-390.png` | before: 3 privacy paragraphs, no proof structure |
| `after/city-1280-fold.png` | fold after: today card (56 µg/m³ · satisfactory · aqi 93 · range · districts), muted map |
| `after/city-390.png` | 390 after: hero card reads perfectly stacked |
| `after/city-1280-full.png` | full page: muted ramp everywhere, all controls intact |
| `after/community-1280.png` · `after/community-390.png` | hero + 3-tile proof strip at both widths |
| `after/community-1280-full.png` | full page: live ledger (14/22/726), corridor rows, honest empties |

Inline: [city fold before](https://app.devin.ai/attachments/c1d0c40b-ec5b-484e-9090-9e4af4c93919/city-1280-fold.png) → [after](https://app.devin.ai/attachments/a91da753-72ea-40ee-a50d-800fa9eb8a89/city-1280-fold.png) · [community fold before](https://app.devin.ai/attachments/95f5a5f7-dd81-4fe4-955e-155aaba7097b/community-1280.png) → [after](https://app.devin.ai/attachments/989fa35d-a042-4e6c-b37b-b1f39465509f/community-1280.png) · [city 390 after](https://app.devin.ai/attachments/6eb73781-780e-4f61-801e-8863c57dfd9b/city-390.png) · [community 390 after](https://app.devin.ai/attachments/62cdceac-c191-45c2-92d4-600b11b9c927/community-390.png)

Shots taken against the local proxy (`/tmp/web_proxy.py`, :8410) — local HTML from the working tree, every data call proxied to prod. Prod itself was not touched; these pages ride the next deploy.
