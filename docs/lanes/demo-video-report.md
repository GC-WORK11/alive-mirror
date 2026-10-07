# Lane report: demo-video — Oct-8 film script, cards, claim verification

**Date:** 2026-10-07 · **Status:** COMPLETE — script + assets shipped; owner films the AWS slot T-morning
**Branch:** `base/v2` · **Service verified live:** build `ce01ec5c`, ap-south-1

## What shipped

| file | what it is |
|---|---|
| `docs/video/shotlist.md` | second-by-second Oct-8 film: 0:00–2:42, 11 beats, exact VO per beat, claims ledger, film-morning checklist |
| `scripts/video/cards/title.html` | restyled to register (was dark #14181f + teal — now warm paper + one forest accent) |
| `scripts/video/cards/cold.html` | NEW — the cold-open felt card: "It's 7 a.m. in Delhi." + live cigarette equivalent, `@@CIGS@@`/`@@UG@@`/`@@DATE@@` injected at assemble time |
| `scripts/video/cards/close.html` | NEW — honesty ledger card: 22.8→10.5 / 6.2 / k≥3 rows |
| `scripts/video/cards/end.html` | restyled; adds the AWS-service line + "ai tools used: Devin (Cognition AI)" disclosure |
| `scripts/video/assemble.sh` | new concat arc for the winner-shape (cold→title→hero→city→dosegap→journey→receipt→ledger→settings→AWS→close→end); live placeholder injection (`@@BUILD@@`, `@@CIGS@@`, `@@UG@@`, `@@DATE@@`) so cards can never disagree with tape; paper `#FAFAF7` padding; AWS slot auto-falls-back to a placeholder card if `80_aws.mov` isn't in `$D` |
| `docs/plan/aws-console-shotlist.md` | frame list updated — DynamoDB `alive108-agg` items frame is now the 5th frame (mandate: "DynamoDB aggregates" must appear); CodeBuild demoted to swap-in if DynamoDB page is slow |

## The arc (why it looks like this)

`docs/15-win-analysis.md` says winners open with a **felt** scenario (~20 s) before
any feature — "clean and obvious beats clever and confusing." The film:

- **0:00–0:07 cold open.** No logo, no app. "It's 7 a.m. in Delhi. The air
  outside your door costs about two and a half cigarettes today — and nobody
  tells you." Cigarette figure is the live `/v2/city → breath` value, injected
  into the card at assemble time, never hard-coded.
- **0:07–1:29 the loop, unbroken.** Hero field → city ledger → the dose gap →
  the app journey (compare → pick → nav ticking dose → receipt → ledger).
  The moment the personal number appears is the felt→feature bridge.
- **1:29–1:38 provenance.** Settings → About, "~2 km" line — the map's honesty.
- **1:38–2:03 AWS console.** The mandatory 25 s: ECS service ACTIVE → task def
  image tag → CloudWatch live logs → NLB healthy target → **DynamoDB
  `alive108-agg` items** (aggregate counters only — privacy made visible in
  the console).
- **2:03–2:35 honesty close.** Admin-tape tail (scorecard, 210 pairs) → close
  card: 22.8→10.5, 6.2, k≥3.
- **2:35–2:42 end card.** Repo, live IP, AWS services, "no device, no uploads."

18 s of headroom under 3:00; trim order protects the AWS slot (shotlist §timeline).

## Claims → proof

Every spoken line is pinned to a live probe (2026-10-07 ~05:30 IST) or a lane
report. Drift-sensitive figures are `[T-45]` — re-run `scripts/verify_numbers.sh`
film morning; cards inject live values regardless.

| narration line | proof | live value at write time |
|---|---|---|
| "about two and a half cigarettes today" | `GET /v2/city → breath.cigarettes.mid` | **2.49** (≈798 µg day inhaled) |
| "fifty-four instruments" | `GET /health → stations` | **54** = 24 WAQI + 30 DPCC (`waqi+dpcc`) |
| "rebuilt every fifteen minutes" | `GET /health → refresh_ttl_s` | **900 s** |
| "a hundred and ninety kilometres … walk on a cleaner pocket" | `GET /v2/reach` walk ≤25 µg | **191.4 km / 4,279 edges** |
| "car eight and a half … walk two-eighty-two — thirty-three times" | `POST /v2/plan` CP→Gurugram | 8.5 vs 282.5 µg → **33.2×** |
| "the difference between two-fifty and eight-fifty for the same trip" | same ladder | 15.5 / 25.2 / 62.7 / 125.2 … full spread 8.5–282.5 |
| "point six micrograms — ninety-eight times less than on foot" | v8 tape frame-verify (26_receipt) | taped ≈0.6 µg, 98× vs On foot — receipt cells are trip-shaped, not live-queryable |
| "a real instrument read under two kilometres away" | `GET /aqi` at CP → `nearest_sample_km` | **1.8 km** |
| "two hundred and ten live pairs grading itself" | `GET /v2/skill` | **219 pairs**, min 5 ✓ |
| "22.8 to 10.5" / "6.2" | `docs/lanes/holdout-reverify-report.md` | fixed numbers, published method |
| "counters — no user rows, no coordinates" | privacy arch: server-side 300 m trim + 100 m thin + sha256 device-id; `/observe` 410; `docs/lanes/judge-proof.md` #3; DynamoDB `alive108-agg` items (owner frame-verifies on camera) | invariant |

Contingencies scripted in shotlist: DPCC stalls >90 min → stations 54→24, line
becomes "twenty-four live, thirty more when their site comes back"; `/health`
build ≠ task-def tag → say the ECR image tag.

## Footage inventory

| beat | file | state |
|---|---|---|
| hero | `10_hero.mp4` | re-taped this lane on `ce01ec5c` — current UI |
| city | `40_city.mp4` | re-taped this lane on `ce01ec5c` — reach solve on tape |
| dosegap | `30_dosegap.mp4` | re-taped this lane on `ce01ec5c` — ladder on tape |
| journey / receipt / ledger / settings | `25` / `26` / `27` / `28` | canonical APK tape `c3bb731` (video-v8 report — every beat PASS, 0 crashes) |
| close beat | `65_community.mp4` | web, `ce01ec5c`; assemble cuts `-ss 5`, 8 s (stats card + k≥3 table) |
| admin tail | `50_admin.mp4` | spare — needs `~/.alive_admin_token` on the capture box |
| **AWS console** | `80_aws.mov` | **owner films T-morning** — `docs/plan/aws-console-shotlist.md` (needs his AWS login); 25 s placeholder card otherwise |
| cold / title / close / end | `scripts/video/cards/` | rendered fresh by assemble.sh with live `@@` injection |

Tapes live on the capture machine (`~/video/beats`); assemble.sh skips-missing so
the pipeline is safe to dry-run anywhere.

## Cards vs register (verified visually, headless-Chrome renders)

- warm paper `#FAFAF7` + white surface, hairlines `#E4E1D8/#D8D5C9`
- ONE accent `forest #3A6844` — used for eyebrow chips, emphases, border on the
  active stat; zero teal, zero gradients, zero emoji
- serif display (Georgia/"New York" stack) + system sans + mono numerals —
  the register's own stacks, no external font downloads
- eyebrow chip pattern per `register-card.md` (accWash bg + accTint border +
  6 px accent square + mono uppercase)
- every card passes the "would a template do this" test: off-grid composition
  (chipped title bar, hanging footer rules, left-ruled ledger rows on close)

## Draft cut — assembled and frame-verified (2026-10-07 ~05:45 IST)

`~/video/cut7.mp4` — **158.0 s (2:38)**, h264 1920×1080@30 + silent AAC
(beats are pixel-only by design; assemble.sh now muxes a silent track so the
file probes `aac,audio` — VO drops in on top later). AWS slot = the paper
placeholder card — by design; owner film drops into `80_aws` and re-assembling
takes ~40 s.

Fresh web tape this lane (the box had no prior tapes; beat files were pulled
from lane-report attachments for the app beats): `10_hero` 12.9 s,
`30_dosegap` 22.6 s, `40_city` 36.2 s, `65_community` 13.5 s — all on build
`ce01ec5c` via `cdp_rec.py --rec screencast` against the live NLB.

Frame-verified in the cut: cold card injected "about **2.6** cigarettes / 814
µg" (live, drifted from 2.49 since the report — the `@@` injection caught it,
proof it can't disagree with tape) · title `ce01ec5c` · city choropleth + day
tiles · app India Gate search mid-arc · AWS placeholder · community
shared-ledger + k≥3 caption · close card 22.8→10.5/6.2/k≥3 · end card AWS +
AI-disclosure rows.

Two script edits forced by reality: **close beat 9a swapped `/admin` →
`/community`** (no `~/.alive_admin_token` on this box — and the community
page's own "at least 3 different phones" line states the k≥3 floor better
than the admin scorecard could); **city + dosegap VO numbers rewritten to the
taped values** (walk ≤50 µg → 683.3 km; ladder 11.4/33.3/38.6/161.9/382.2 µg)
— narration always says what the screen shows.

## Re-tape on prod `aee635eb` (2026-10-07 ~07:15 IST)

Prod moved `ce01ec5c` → `aee635eb` after the first draft (city+community
overhaul `6c36219`, landing overhaul, admin overhaul). All four web beats
re-taped on current prod — app beats (`25/26/27/28`, APK `c3bb731`) unchanged
and still canonical:

| beat | re-taped | on tape now |
|---|---|---|
| `10_hero` 13.6 s | `aee635eb` | "52 STATIONS LIVE · FIELD 13 MIN FRESH · MEDIAN 57 · 903K EDGES" + new field copy ("the field the dosimeter reads — the same surface the router prices on") + self-grade footer (234 pairs · 29.5 µg/m³) |
| `30_dosegap` 21.0 s | `aee635eb` | corridor 31.4 km + ladder Car 11.4 / Bike 34.5 / Auto 38.3 / Bicycle 161.7 / On foot 381.4 µg · "5 options priced in 1.2 s" · depart "leave ~11:00, 15% less" |
| `40_city` 33.0 s | `aee635eb` | NEW layout: named-boundary district SVG + forecast scrub + reach solve **on tape: walk ≤50 µg → 622.2 km / 11,436 segments** + day tiles + "the ledger, today" numbered cards incl. "STREETS WE CAN SHOW 12 ≥3 phones" |
| `65_community` 13.5 s | `aee635eb` | NEW layout: "22 phones · 40 trips · 1,029 µg dodged all-time · bus ×1" + k≥3 corridor caption |

Every recorder hook still resolves post-overhaul (`tlDeep`/`TL.cache`,
`click_geo`, `scroll_el`, reach `armed→solving→cap` — zero selector breakage).
The `@@` injection lives in the CARDS only (never page overlays), so nothing
to re-anchor; `assemble.sh` filled `aee635eb` / "about 2.6" / 818 µg into the
new draft. Shotlist VO re-pinned to the new tape (52→"over fifty" instruments,
622→"over six hundred" km, auto "about forty").

New draft: `~/video/cut7.mp4` — 158.0 s, frame-verified inside the assembled
file (new city district map + new community ledger visible in the cut).

## Oct-8 open items (in order)

1. `scripts/verify_numbers.sh` → update shotlist `[T-45]` figures if drifted
2. `scripts/video/warm_task.sh` → field fresh for tape
3. **Owner films `80_aws.mov`** → drop into `~/video/beats`
4. `scripts/video/assemble.sh` → cards render with live numbers, concat, publish
5. Watch once end-to-end with the VO — the ≤3:00 check and the "clean and
   obvious" check happen there, not in the files
