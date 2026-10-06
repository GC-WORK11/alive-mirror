# Lane report — admin-overhaul

**Date:** 2026-10-06 · **Lane:** admin-overhaul (spec `docs/lanes/admin-overhaul.md`) · **Verdict: SHIPPED**
**File touched:** `server/admin.html` only (self-contained page — no `server/*.py`, no deps, no build, no new fetches).

## What a judge sees in <60s

The page now answers, top to bottom, in plain English: **the air right now** (9 headline cards, each carrying a right-aligned honest qualifier — `good` / `live` / `quiet` / `watching` / `down`, plus the CPCB band word + muted band colour on the air cards) → **the fire belt** (fires spotted, how many sit inside the smoke belt, the × smoke lift, which way the wind carries it) → **what the sensors see** (every feed honestly labelled live/dormant/down, "no feed is ever shown green when it isn't") → **trips being planned** (street cells ≥3 phones crossed, honest-empty when none) → **how the numbers are made** (dose math, route engine, api stopwatch, map accuracy, methodology) → **why the air is like this** (the causal read, checks that can't run are named) → **district by district** → **the live air map** → **what riders share** → **the archive**.

## Translations (operator → plain English), nothing deleted

- **Masthead/statusline** — "engine up 43m · map live · last rebuilt 12m ago · 0 monitors reporting · 48 map points computed (open-meteo/cams)" replaces `uptime`/`field_age` jargon; priv badge now says "no person is ever shown · groups of 3+ phones only".
- **Sources table** — `waqi_ingest` → "city monitors · waqi — government monitors, republished via waqi — trusted 3× over the forecast"; cpcb "the prod key isn't set yet"; openaq "fallback of last resort"; forecast/wind/fires/places/router all get a "what it is" column entry; headers `the feed | state | readings | age | what it is | freshness`.
- **Pipeline** — ingest→blend→fill→price→dose→share with plain sublines ("the gaps between monitors are filled in — σ shows how honest each fill is"); provenance strip "monitors reporting → forecast points → ±σ gap-fill honesty → streets priced by live air".
- **Field state** — every kv translated: "the map is" (live/snapshot badge), "gap filling", "honesty band (σ)", "area covered — 48 cells · within ~— km of any street", "streets priced — 9,03,058 of 10,70,459 priced by live air · repriced 41m ago", "emergency rules (grap)", "recipe". `f.snapshot_age_s` null-safe.
- **Route engine card** — "road map · N streets · M junctions", "priced by live air", "map fingerprint", "trip ledger"; gated state → "sign in to see road-map internals".
- **Accuracy card** — "live check — misses by mae … (N monitors)", "hidden-monitor test (weekly)", "replay of recorded hours", "above the who/cpcb limit", "the long report".
- **API stopwatch** — route names translated (`/v2/plan`→"plan a trip", `/aqi`→"air at a point", `/grid`→"the air map"…), rows "204ms avg · 9 in 10 under ≤10ms · 130 calls".
- **Corridors** — `street cell | near | trips | phones | smoke inhaled | co₂/100m | air now`; expanded detail explains the ≥3-phones rule in words.
- **Why panel** — driver kinds translated (`fires`→"farm fires", `ventilation`→"wind + mixing height", `trend`→"drift over 6h"…), raw detail chips get plain labels (`wind_ms`→"wind m/s", `vc_m2s`→"clearing m²/s"…), `main driver` badge, un-observable causes named with reasons.
- **Methodology** — rewritten as one honest recipe paragraph; species caveat "forecast layer only — our monitors measure pm2.5"; button reads "how it's made".
- **Districts** — basis "no readings inside this border" / "centre-point read" / "mean of N covered cells — thin coverage"; chips `band · index`; caption "N areas · M with live air · K thin".
- **Cell inspector** — confidence "solid — monitor evidence close by" / "fair" / "thin — far from any evidence"; "grid" not "sector".
- **Community + archive** — tiles "areas with riders", "journeys between places", "smoke + co₂ avoided", "what riders think" (notes hidden until 3+), "hours saved today", "recording since", "saved maps · all time", "last save"; hourly strip "today, hour by hour — one square per hour, coloured by how bad the air was"; skill table "the forecast grades itself".
- **Every empty state** → "nothing to show yet" + a one-line honest why; every gated state → "locked — sign in as operator"; feed pill "refreshes itself · every 30s" / "N feeds down" / "N locked".
- **Section headers** — `01 · the air right now`, `02 · the fire belt`, `03 · what the sensors see`, `04 · trips being planned`, `05 · how the numbers are made`, `why the air is like this`, `06 · district by district`, `07 · the live air map`, `08 · what riders share`, `09 · the archive` — each `<em>` plain.

## Muted ramp, never neon

Raw CPCB/EPA hexes (`#FFFF00`, `#FF0000`, `#00B050`…) caught flooding the district choropleth + legend + archive strip — same trap as the welcome lane's boot strip. Both `CPCB_BANDS` and `EPA_BANDS` now paint with the muted product ramp `#7AAB59 #C8B25A #D58C4A #B85442 #8F3C49 #6E3C54`; **band names stay the official categories**. Verdict chips reuse the same ramp via `--vc` (`.vword`).

## Kept, per spec

- Boot strip + once-per-session + reduced-motion — untouched.
- Token flow — `prompt()` → `sessionStorage.alive_admin_tok`, decline → `alive_admin_tok_no`, guest view, "operator sign in"/sign-out chip — untouched; gated endpoints still pre-rejected client-side (zero 401s).
- Every stat, button, canvas, table row, fetch, element id — nothing deleted; presentation text only.
- Test markers `id="whydrivers"`, `"/v2/why"`, `id="whyeval"` — preserved.

## Gates

- `node --check` on the extracted `<script>` (598–2337): clean.
- `pytest tests -q` (full suite): **1151 passed, 5 skipped** (run earlier this session pre-final-edits) + `pytest -k "admin or landing or why or serve"` after final edits: **106 passed**.

## Proof (`docs/lanes/admin-overhaul-shots/`)

| Shot | Shows |
|---|---|
| `pre-auth-boot.png` | once-per-session boot strip still firing |
| `pre-auth-guest.png` | guest view — "GUEST VIEW — NO OPERATOR TOKEN", cards carry `quiet` verdicts |
| `post-auth-top.png` / `post-auth-fold.png` | signed-in top: plain-English cards, pm2.5 90.6 µg/m³ `poor` muted-brick verdict, statusline |
| `panel-fire.png` | "67 fires spotted · 15 inside the smoke belt · smoke lift ×1.08 · wind 89° — blowing it away from delhi" |
| `panel-feeds.png` | sources table fully translated |
| `panel-trips-dose.png` | corridors honest-empty + dose math + route engine |
| `panel-districts.png` | muted-ramp choropleth (wine = South Delhi severe) |
| `panel-archive.png` | archive tiles + hour strip + skill grader |
| `390-top.png` / `390-mid.png` / `390-scorecard.png` | 390px: masthead wraps, cards 2-up, scroll-x tables, why panel readable |

Inline: [guest](https://app.devin.ai/attachments/b7deb150-6fb0-4ba6-a584-6d7badd5193d/pre-auth-guest.png) · [post-auth](https://app.devin.ai/attachments/710d0740-e168-4dce-85a6-11a1b97b5b46/post-auth-top.png) · [fire belt](https://app.devin.ai/attachments/401c4ee3-ca3b-44a2-b98e-ede8f483d46f/panel-fire.png) · [districts muted](https://app.devin.ai/attachments/0c759933-b263-4be2-95d5-47fcba4d5d5d/panel-districts.png) · [390 top](https://app.devin.ai/attachments/a1f20234-95fd-4e61-bea5-a4195044a7f2/390-top.png) · [390 mid](https://app.devin.ai/attachments/a754edd5-8a56-4e04-ab2d-b82dbed499e5/390-mid.png)

Post-auth shots use a fake `alive_admin_tok` + `alive_boot_v1` primed via sessionStorage — valid on loopback because `/admin/api/*` serves unconditionally without `ALIVE_ADMIN_TOKEN` set; the token wiring itself is unchanged.
