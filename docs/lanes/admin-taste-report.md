# Lane report — admin taste pass (`/admin`)

**Owner brief:** *"use the taste skill on the admin dashboard too — lil touch to find flaws and touch with taste, NOT overhaul."*
**File audited:** `server/admin.html` (2,785 lines — the whole console; there is no `web/` dir on `base/v2`).
**Verified:** real Chrome against a local `uvicorn main:app` (`ALIVE_ADMIN_TOKEN` set to a throwaway local value per `docs/plan/admin-login.md`; the gate, cookie session and sign-out all exercised). Prod untouched — GET-only lane, no deploy.
**Method:** audit-first per `docs/design/taste-skill/{redesign-skill,minimalist-skill}/SKILL.md`. Drove every section hero→footer signed in, desktop ≈975–1,280 CSS px and phone ≈310–410 CSS px (crossing the 900/860/560/420 breakpoints). Every visual anomaly was traced to its JS source line before being logged as a flaw. No redesign performed — polish only.

## Fixed in place — small flaws, small edits (`server/admin.html`)

| # | Surface | Before | After | Why it was a flaw |
|---|---------|--------|-------|-------------------|
| 1 | sources table — `city monitors · cpcb` / `· openaq` rows | state pill `down`/`dormant` **+ age `0s` + badge `FRESH`** | age `—` · badge `—` | a down feed claiming to be fresh — the page's own honesty rule ("never green-wash a feed that isn't") broken in the trust table itself. `mk()` was passed `feeds.cpcb?0:null`; the `0s`/`fresh` came from a truthy-feed branch. `dpcc` already passed `null` — these two now match |
| 2 | scorecard — `replay of recorded hours` | `unavailable: ValueError: too many values to unpack (expected 5)` | `unavailable — check couldn't run (ValueError)` | raw Python exception leaking into UI copy. New `chk()` helper keeps the honest "couldn't run" + the error class name, drops the stack-trace accent. Applied to `loso` + `archive_replay` rows; plain statuses (`insufficient stations`, `ok`) pass through unchanged |
| 3 | scorecard — `yesterday, in full` | `· 1 snapshots` | `· 1 snapshot` | missing plural |
| 4 | why — `drift over 6h` + history caption | `1 recorded maps` | `1 recorded map` | missing plural (3 sites — trend row both branches + `whysub`) |
| 5 | why — `wind` row | `7 km/h from 121° · field · 3m` | `… · 3m ago` | bare `3m` reads as *metres* mid-sentence, not minutes-old. Every other `ago()` call site already suffixes `ago`/`old` — this was the one outlier |
| 6 | timing — `how fast the api answers` | `9 in 10 under ≤25ms` | `9 in 10 ≤25ms` | doubled comparator: the `≤` is already inside the bracket token, `under` + `≤` = "under ≤". Also fixes the null branch (`9 in 10 >5s+`) |
| 7 | route engine — `trip ledger` | `memory · ledger memory · 0 anonymized phones` | `memory · 0 anonymized phones` | stuttered "memory" twice — backend + ledger backend are the same store; deduped only when equal, still prints ` · ledger <b> · ` when they differ |
| 8 | scorecard — all three error metrics | `big-miss score (rmse) 12.7` | `… 12.7 µg/m³` | the one unlabeled number in a page where every number carries a unit (live check, hidden-monitor, replay rows) |
| 9 | scorecard — `tested week` | `generated 2026-10-04 12:14:41Z` | `generated 2026-10-04 05:44:41 pm IST` | the only UTC `Z` timestamp on a board that otherwise speaks IST |
| 10 | archive cards + captions | `09:00 ist`, `1 / 10 ist` | `09:00 IST`, `1 of 10 IST` | page convention is uppercase `IST` (masthead, why caption); 9 lowercase literals + the cryptic `/`-for-`of` ratio, harmonized |
| 11 | `.cols` / `.cols3` grids | cards stretch to row height → dead space *inside* the shorter card (route-engine card ran ~50% empty next to the dose-math block) | `align-items:start` | the emptiness now sits in the open gutter where the page's whitespace already lives, not inside a bordered instrument card |

Before/after screenshots live in [`admin-taste-shots/`](admin-taste-shots/) — pairs: `before-sources-freshbug`↔`after-sources`, `before-scorecard`↔`after-scorecard`, `before-timing-p90`↔`after-ledger-timing`, `before-ledger`↔`after-ledger-timing`, `before-archive-ist`↔`after-archive-ist`, plus `after-why-age-plural` (fixes 4+5), `after-cols3-ragged` (fix 11), `gate`, `after-hero`, `mobile-firemap`, `before-mobile-sources`.

## Checked and deliberately left alone

- **Empty states are the opposite of dead.** Every quiet card says what it would show and why it's empty ("nothing to show yet — a cell appears here only after 3+ different phones cross it inside 72h"). This is the page's best pattern; kept.
- **Mobile tables already scroll honestly** — `.scrollx` + a local-scroll shadow that peeks only while columns sit past the edge, and prose cells wrap at ≤560px. The clipped `FRESHNESS` column in `before-mobile-sources` is reachable by design.
- **Palette is clean.** Band colors appear only where they mean air (hero chip, choropleths, legend); severity accents are the muted bronze→brick→wine ramp; no off-palette colors found.
- **Numbers carry units everywhere else** — the three rmse rows were the only unlabeled ones.
- **`fetched 11m ago` / `6m old`** — two idioms, both unambiguous in context; left.
- **`⚠ can't tell:`** — a functional marker, not decoration; wire text anyway.
- **Sign-in gate + sign-out** — exercised; gate copy is consistent with the page voice ("sessions last ~8 h · sign-in is rate-limited").

## Structural items — catalogued, NOT implemented

1. **`cols3` rebalance.** `align-items:start` cured the inside-card dead space; the underlying asymmetry remains — the dose-formula prose block is ~3× the height of its row-mates. If it grows, move the citation prose behind a `<details>` or into the section caption.
2. **Why-driver chips are wire-verbatim tokens** (`age s 176`, `× less clearing 3.57`). `CHIPK` maps the keys but the values still read as variable names. A `label: value` chip format would finish the job — a formatter change, not polish.
3. **`SHARING · LAST 24H / 7D` renders `0/0`.** Captioned, so honest — but if a third window ever lands, switch to two named rows instead of encoding windows into the number.
4. **`LAST SAVE` prints the absolute box path** (`/Users/devin/repos/...`). Correct for an operator surface; worth trimming to repo-relative if the board is ever shown outside ops.
5. **Scorecard `dd` prose.** Fine today; if the weekly rollup gains another check per row, split mae/rmse/bias into their own kv rows rather than lengthening the sentence.

## Local-data caveats (not flaws)

`0 monitors reporting`, `goes dark — 6m`, `1 recorded map in 6h` reflect this box honestly (no govt feeds, archive hours old locally, CAMS forecast only). The board renders true zeros and names dormant feeds rather than inventing freshness — exactly the behavior the fixes above had to preserve.
