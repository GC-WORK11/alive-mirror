# fix-web-p2 — closing the web-drive P2 nits

**Verdict: 5 of 6 nits fixed on HEAD; 1 verified already-fixed (deploy lag).** Driven and re-verified locally at true-390px device metrics (CDP, iPhone emulation) against a live local server; every claim below is a diff line or a probed DOM value.

- Base: `base/v2` @ `b0dd079`. Probe rig: headless Chrome + CDP at 390×844×2 (`~/drive-web/probe.py`), pages served by local `uvicorn main:app` on :8099 with real field data (corridors/trips empty on this box — noted where that matters).
- Tests: `cd server && PYTHONPATH=core/build312:. .venv312/bin/python -m pytest -q tests` → **1197 passed, 5 skipped, 1 pre-existing failure** (`test_plan_ranking_invariants_on_real_ods[Sarai Kale Khan → IGI T3]` — dose 19.4 vs min 17.6; verified failing identically on clean HEAD `b0dd079` via `git stash`; `/v2/plan` engine untouched by this diff — a plan-lane bug, not a web one).

## Nit → fix → evidence

### 1. /admin overflows to 572px on 390px — FIXED

Root cause (CDP): the five-column skill table inside `#skillwrap` had **no `.scrollx` wrapper** — its 539px width pushed `document.documentElement.scrollWidth` to 572. The feed/whydrivers/corridors tables were already inside `.scrollx` (clipped silently, never widened the page).

- `admin.html`: `#skillwrap` → `class="scrollx"`; added `@media(max-width:560px)` compaction — `.scrollx td/th` padding 8px/7px, `th` may wrap, `td` 11.5px, prose column 5 capped 118px.
- **Before:** `docW=572`, horizontal page scroll. **After:** `docW=390` — page scrolls zero; wide tables scroll *inside* their panels with the existing scroll-shadow affordance (same contract city/community already use; hiding columns would be feature removal).
- Side effects on the guest view also neutralized while here (see §6).

### 2. Landing 'refreshed' timestamp lacks TZ — FIXED

- `landing.html` `fieldAge`: `toLocaleTimeString([],…)` (viewer TZ, unlabeled) → `toLocaleTimeString('en-IN',{timeZone:'Asia/Kolkata',hour:'2-digit',minute:'2-digit'})+' IST'` — the codebase convention (`timeIST`, admin:752/2512, city:1659/1670).
- Same convention applied to the forecast scrubber clock `tlClock` (`h+N HH:MM` was viewer-local) → `timeZone:'Asia/Kolkata'` + ` IST` suffix.
- **Verified in DOM:** `"refreshed 09:16 am IST"`.

### 3. /city contrib window vs /community all-time — VERIFIED DEPLOY LAG, skipped

HEAD already serves all-time: `city.html:1623-1629` sums `obs_total` over `days` and labels the strip `since <first-day>`; prod just runs `aee635eb` (~14 commits behind). No fix needed — deploy will land it.

### 4. /community unfurls raw JSON — FIXED (two layers)

- `main.py:1377-1394`: `/community` kept serving `community.totals()` JSON to `Accept: */*` — which is exactly what Slackbot/Twitterbot/WhatsApp et al. send, so a shared link unfurled raw JSON. Added `_UNFURL_UAS` — known crawler/link-expander user-agents (slackbot, twitterbot, facebookexternalhit, discordbot, whatsapp, linkedinbot, telegrambot, googlebot, bingbot, duckduckbot, embedly, redditbot, pinterest, vkshare) now get the HTML. **The `*/*` → JSON contract is preserved** — the app and `test_landing_serve.py`'s dual-contract test both still pass.
- og: meta added so the unfurl renders a card: `og:title`/`og:description`/`og:type`/`twitter:card` on `community.html`, `city.html`, `admin.html` (landing already had og:).
- **Verified:** `curl -H 'Accept: */*' -H 'User-Agent: Slackbot-LinkExpanding 1.0' /community` → HTML; `curl -H 'Accept: */*' /community` → `{"obs_total":0,…}` JSON.

### 5. Corridor table truncates 9-of-10 under a "12 streets" stat — FIXED

- `city.html:1650`: `.slice(0,9)` dropped → renders all served rows. The server sends top-5 + bottom-5 by dose (`city.py` `CORRIDOR_TOP/TAIL=5`), so the table now shows all 10 of the publishable 12.
- Honest caption added: `<p id="corrNote">` below the card, populated only when rows exist — `showing 10 of 12 stretches — the heaviest and lightest ends by dose` when `corridors_publishable` exceeds the served set, `every stretch with ≥3 phones, dose-sorted` when it doesn't. **Verified in DOM** (caption text and unhide logic).
- Bonus honesty fix while here: raw OSM street names arrive lowercase (`hanuman lane`) — `tName` title-cases them in city, community, and admin corridor renders (admin shows `r.near`).

### 6. Design stragglers — FIXED (report-cited only)

Serif h1s were **off-system**: landing's own rule is `h1` sans-500; `--serif` lives only in the data register (big numerals, names inside data components). Fixes:

- **city.html**: `h1`, `.sec-t`, `.days-cap`, `.detail .d-name` → sans (data numerals `.stat .v`, `.htoday .hv`, `.d-aqi` keep serif). Green-wash neutralized: `.stat` tiles (accWash → surface + ambient shadow), `.modep`/`.dose-chip` (accWash → surface2), `.eyebrow` (accWash chip → plain ink2 text, sage tick kept), `.whyline` (accWash → surface2, wtag accent → ink2 — same as `#grapline` already was; the duplicate grapline rules folded in), `.sec-n` (accWash chip → surface2 tile), `.rch-pills .on`/`#rchArm` (accWash → the landing's established selection tile: white + inset hairline + shadow). Chips `.chip`/`.m-src`/`.ticker-in span` hairlines → ambient shadows. `.htoday` fallback wash → surface2 (band vars still take precedence — band colour means air, kept).
- **community.html**: `h1`, `.sec-head h2`, `.pt b` → sans (`.lrow .v` data numerals keep serif). `.pt .n` green chip → neutral paper chip; `.pt` tiles and `.lgrid` card gained ambient shadows.
- **admin.html**: `.priv-badge`, `.kchip.accent` (the donation ledger tiles — 4 call sites), `.pipe .n`, `.fmsel button.on`, `.badge.live` → neutral; `.whybig` serif → sans; `.badge`/`.pill`/`.chip2`/`.feed`/`.pipe .st` hairlines → ambient shadows; `.panel`/`.card` gained ambient shadow (16px-radius cards now carry the register's `0 1px 3px -1px` depth). Kept: `.tokbtn` sign-in CTA, `h2::before` tick, `.hero-kick .lv`, `.feed.live i`, `.breathe` ring, link ink — the page's sanctioned little-bit accents.
- **landing**: kept as the convention source — `.routeline`/`.lrow.rec` accWash are result/selection emphasis (the one accent moment), not green-wash structure.

**Font floor:** every `font-size:` px literal under 11 raised to 11px — **140 declarations** (city 33, community 17, admin 51, landing 39). Canvas `ctx.font` furniture (compass 'N', graticule/degree ticks, marker numerals) left at scale — chart annotation, not UI text; the one real-label case (admin ops-map district names) bumped to 11px.

**Honesty fixes bundled** (report P2 + clearly fake-looking):

- landing numeric prefills → `—` placeholders: `stnHero` 54, `distN` 29, `pricedcount` 0.90, `edgecount` 1.07, `pricedcount2` 0.90 — all overwritten by live fetches; `—` is the honest loading state.
- cadence copy: "instruments report every 15 minutes" conflated publish vs rebuild rates → "DPCC posts fresh pages about every 5 minutes and the field rebuilds roughly every 15".

## Verified-on-screen (390px, local server)

- `/admin` guest view: docW 390, no horizontal scroll; priv-badge neutral; hero card intact.
- `/city`: sans h1, band-wash today card (band = air), neutral whyline/stat tiles; corridor section renders (empty-store on this box → honest empty state + no caption, correct).
- `/community`: sans h1, neutral pipe tiles with shadows.
- `/`: sans everything was already; `fieldAge` IST label live in DOM; prefills show `—` then fill (`distN` observed `—`→`29`).

## Not touched (deliberate)

- `/v2/plan` ranking invariant failure — pre-existing on HEAD, engine domain, other lane.
- Canvas annotation glyphs <11px (compass, graticule ticks) — map furniture, not UI text.
- `.tokbtn`/`.lv`/`.breathe`/`h2::before` accent — the register's sanctioned forest accents (small, semantic).
- Prod deploy — `aee635eb` lag is ops, not code.
