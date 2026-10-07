# ALive-108 Design Language Spec

**Purpose.** Rebuild the ALive-108 consumer app so a Delhi commuter who has never heard the letters "AQI" instantly understands it — and so no one looking at it can say "AI made that." The product is a map that tells you how much a trip makes you breathe. Everything else is chrome.

**The bar** (adapted from the anti-slop literature, sources §S18–21): if someone can look at a screen and say *"AI made that"* without hesitation, it has failed. Restraint without intent now reads as mediocre, not refined. Every choice below must be a choice, not a default.

---

## 1. Reference-app teardown

### 1.1 Google Maps (mobile, current IA)

**What it does now.** Google Maps' 2024 redesign dropped most fullscreen UIs in favor of *sheet-based layouts* — rounded sheets that keep the map visible in more places, "emphasizing that background layer" and making the app "look lighter" while preserving spatial context [S1]. Mode switching moved to the **bottom** of the screen for reachability [S1]. The pin redesign (Aug 2024) shortened the pin into a rounded white pinlet with the category glyph in an inner circle — *less* prominent per pin so more fit per view [S2]. Google builds on Material components but wraps them (e.g., the elevated button under the search box is a custom composable matching their spec, not stock Material) [S3].

**The mechanics worth stealing:**
- **Search pill with the avatar inside it.** One floating rounded field at top; the user's profile lives inside the pill's right edge. No hamburger, no drawer handle, no second navigation system.
- **The map is never fully covered.** Even "fullscreen-ish" sheets leave a map sliver so the user never loses spatial context.
- **Chip row** under the pill for context filters — quiet, same height, scrollable, dismissed by scroll.
- **Traffic pill** on the map is a single line of plain words ("Mucho tráfico…") attached to where it happens — information placed at its location, not in a panel.
- **One accent.** Google Maps UI chrome is essentially grayscale + action blue. Every color that survives is either semantic (traffic red/yellow/green on roads, transit line colors) or the single interactive blue.

**Takeaway for ALive-108:** the map *is* the app; the UI is a pill and a sheet. Anything that doesn't fit those two surfaces doesn't ship. See the captured Delhi viewport: `google-maps-delhi.png` — note how little chrome exists: one pill, one chip row, two FABs (locate/layers), done.

### 1.2 Uber / Lyft — the picker

**What it does.** Uber's ride picker is the canonical "mode comparison" UI: map occupies roughly the top half, a nonmodal sheet below lists options. Each row = **vehicle image left · product name + ETA · price right-aligned in tabular figures** [see `uber-appstore.png` — the "Confirm details" sheet shows the car thumbnail, "UberX · 3 min," `$9.95` with the struck-through reference price]. One tap selects; the sheet never navigates away from the map.

**System details that make it feel engineered, not generated:**
- **Uber Move** — their custom typeface (MCKL × Wolff Olins) is *transportation-signage type*: drawn from Highway Gothic/DIN/Neuzeit Grotesk, engineered for glanceability at speed, not a "tech-brand geometric" [S4, S5, S6]. The lesson isn't the font itself — it's that they picked type *whose job is wayfinding*. Apple's equivalent choice is SF/SF Symbols; the point is type that was built to be read at 80 km/h or in bad light.
- **Base / LPL rigor.** Uber's Base and Lyft's Product Language are token systems where color, type, elevation are *linted* (Lyft literally ships an "LPL Lint" Figma plugin that flags off-system values) [S7, S8]. The premium feel is largely *absence of variance*: one elevation language, one radius scale, prices always the same weight.
- **Rows, not cards.** Options read as a ledger: hairline separators, consistent row height (~64px), price or ETA is the right-aligned column that your eye scans vertically to compare. Nothing is a floating card inside another card.

**Takeaway for ALive-108:** our `/compare` list should read like Uber's picker — vehicle silhouette left, ETA big, meta quiet, and the **dose column** as the right-aligned scannable number (or bar). The 8 modes ranked by inhaled µg are the product's whole reason to exist; present them as a comparison *table*, not a card stack.

### 1.3 Apple Maps

**What it does.** Same grammar as Google Maps (pill + sheet + FABs), executed with Apple restraint: floating sheets with shadow and no visible border, SF Symbols throughout, system font, and Apple's HIG map rules behind it [S9]:
- *"Keep the map interactive… Noninteractive elements that obscure the map interfere with expectations."*
- *Muted emphasis style:* desaturated basemap when you have information-rich overlays — which is precisely our situation (a pollution field is an information-rich overlay).
- *Cluster overlapping points of interest.*
- *Use expected pin colors* — red destination, green start, purple user point in the classic spec; i.e., **don't redefine learned meanings** [S10].

**Takeaway:** pick the *muted* map grammar (our Positron-style monochrome), cluster when dense, and never repurpose a learned color or shape. Our endpoints: keep the teardrop pin language the app already ships — it's learned behavior — but flatten it to ink/paper (no gradient).

### 1.4 Waze — the crowd layer

**What it does.** Waze's defensible advantage is crowd-sourced reports, and its failure mode is also instructive: the reporting affordance is buried behind an ambiguous orange speech-bubble icon, and every hazard reports through the same fiddle-deep menu — widely criticized as dangerous at speed [S11, S12]. Waze's *icon semantics*, though, are the best lesson in the set: every hazard has its own pictograph — police hat, pothole, crash, stalled car — so the map reads wordlessly at a glance. Community requests literally ask for "the icon to picture the hazard instead of a generic triangle" [S13].

**Takeaway for ALive-108:** our `/report` picker (dust | smoke | burning | clean) must be one tap → four **pictographic** options (dust swirl, smoke plume, flame, leaf), and the map must show *that* pictograph at the location — never a generic dot. Waze proves: icon variety is meaning; icon sameness is noise. Keep Waze's semantics, drop its carnival styling.

### 1.5 Rapido / Ola — what Indians read instantly

**What it does.** Rapido's icon system (Liquidink case study) is a set of 12 vehicle icons — metro, e-rickshaw, bike, auto, car — **drawn from the real-world angle a rider sees when the vehicle arrives**, with bold outlines and minimal styling, explicitly built for "instant recognition" by 20M+ daily Indian riders [S14]. Rapido's own design-system writeup adds the scaling lesson: design tokens (`brand-color = #FFCA20` etc.) so "a small change is a single-line change in all components" [S15]. The broader critique worth heeding: Rapido's legacy UI was accused of "unnecessary complexity, clutter, poor navigation" — the icons carried a UI that didn't [S16].

**Takeaway:** Delhi commuters don't read abstract vehicle glyphs; they read **arrival-angle silhouettes** — the auto-rickshaw profile, the bike, the metro front. Our ModeIcon set should be that: flat single-ink silhouettes drawn from the angle the vehicle presents on the street. (We take Rapido's vocabulary, not its 3D-cute styling.)

### 1.6 Citymapper — transit legibility

**What it does.** Citymapper wins under *high cognitive load* — unfamiliar route, running late [S17]. The home is one prompt ("Get Me Somewhere") + quick-access Home/Work. Route options compare as **a list where duration is the huge right-aligned number** and each mode is a chunky pictograph in a circle — bus, metro, bike, walk, cab, scooter visible at a glance (see `citymapper-appstore.png`: the green screen showing 28/32/37/39 min next to glyph circles). Mode filters ("Walk Less", "Turbo", "Price") act as *constraints*, not decoration. In navigation it gives continuous low-effort feedback ("Get off now") — confirmation, not data.

**Takeaway:** comparison = giant aligned numbers + instantly-read glyphs. The list answers "which one?" in under a second; everything else is secondary text.

### 1.7 Plume Air Report — the canonical "air app" (RIP)

**What it did.** Plume hid NO₂/O₃/PM2.5/PM10 "behind a simple index" and answered four questions with four buttons: *can I run, bike, take kids out, eat outside* [S18]. Its 24h forecast was "reminiscent of Dark Sky" — one curve, now-anchored [S18]. The companion Flow sensor won a Red Dot by bridging "personal and collective benefit" — personal exposure → crowdsourced city map [S19]. plumelabs.com still frames the product as *"air quality… as easy as checking the weather"* [S20].

**Takeaways:**
- **Activity-first, never pollutant-first.** Nobody asks "what is the PM2.5?" — they ask "should I take the rickshaw or the metro?" Our mode list IS the Plume button row generalized.
- **One index, one curve, anchored at now.** Plume survived years on a single screen because the screen answered a question.
- **Crowd layer as dignity:** Flow users' measurements powered everyone else's map — our CorridorLayer/community traversal is the same idea; present contributors' data as *the city measuring itself*, not as telemetry.

**Adjacent reference — "Shoot! I Smoke"** (open-source, itself Expo/React Native [S21]): the entire app is one number and one unit — "≈ N cigarettes today" — powered by the Berkeley Earth equivalence (1 cigarette/day ≈ 22 µg/m³ PM2.5 sustained) [S22, S23]. It went viral internationally *because it was wordless*: a cigarette glyph plus a number needs no AQI education. Our codebase already encodes this (CIG_UG = 316 — the inhaled-mass equivalence per cigarette). That equivalence is our dose UI's native unit; see §2.

---

## 2. The wordless number — data that means something without a label

The user's constraint: **no captions, no explaining, no jargon** — a person who has never heard "AQI" must get it instantly.

### 2.1 What the minimalist health apps proved

- **Zero** (fasting): the entire app is one ring/timer. Visual cues replaced text; onboarding happens as coachmarks *in context*, never a manual [S24, S25]. The lesson: **one hero element per screen**, and a ring you can read in peripheral vision.
- **Levels** (glucose): experienced users read charts; new users couldn't. Fix = a **bounded 0–10 "Zone Score"** + a visual ring grouping readings into ranges — "a useful summary first, with detail within reach" [S26, S27]. Bounded scores need no unit: everyone understands 7/10 > 3/10.
- **Bevel / RISE / Whoop pattern**: a single bounded score (strain 0–21, debt in hours) + a color band. One number, one state, zero jargon.
- **Shoot! I Smoke**: one number + one universal unit glyph = press coverage worldwide [S21–23].

### 2.2 The dose unit: cigarettes, not micrograms

Berkeley Earth's equivalence is the most viral risk-communication unit in air quality — Delhi in winter is genuinely 4–10+ cigarette-equivalents/day territory (Beijing avg was 4, bad days 25, worst-recorded cities 60+ [S22]). **Rules:**
- `1 🚬 = 316 µg inhaled PM2.5` (already `CIG_UG` in the codebase) — *always* render dose in cigarette-equivalents at consumer surfaces. Micrograms exist only in the dashboard/provenance layer.
- **Fractional glyph grammar:** a row of cigarette silhouettes where the last one fills proportionally — "2.4 cigarettes" reads as 2 full + one partially-filled glyph. A number with a picture-unit is wordless; a bare number is not.
- The glyph does the labeling. `🚬 2.4` needs no caption. This is the whole trick: **units as pictures, comparisons as bars.**

### 2.3 How a bare number still carries meaning

When a number must appear (ETAs, µg in the dashboard), meaning comes from **type size + comparison + position**, not a label:
- **Hierarchy:** the answer-number is the largest type on screen (Apple Weather's giant `61°` — see `apple-weather-appstore.png`; the degree glyph *is* the label).
- **Comparison adjacency:** every dose sits next to its reference (vs typical, vs budget, vs metro alternative). A number alone on screen is a bug.
- **Position encodes role:** left column = identity (silhouette), center = time, right edge = dose — the eye learns the column once and never re-reads a label.

### 2.4 Color = grammar, not decoration

- **The map speaks first.** Pollution intensity renders only *through the field layer* (single-hue ramp deepening with concentration) — the map itself is the heat language; UI text stays grayscale.
- **Never encode "good" as green.** Green-for-safe is both the traffic-light jargon the user hates and a colorblind trap [S28]. In our system, **the absence of dose color IS the good state** — quiet neutral = nothing to warn about. This is also what keeps the aesthetic monochrome.
- **Sequential ramp beats categorical ramp.** The EPA's 6-hue AQI scale (green→maroon) is built for categories and fails red-green CVD users; South Coast AQMD's own fix moves to a *monotonic-lightness* scale precisely so it survives grayscale [S28, S29]. Our dose ramp is therefore single-hue (§5.1): meaning carried by *depth*, not hue-hopping.

---

## 3. The one-screen story — what deserves pixels

### 3.1 The evidence

- **NN/g on hidden navigation:** hiding navigation behind a hamburger **cuts discoverability almost in half**, raises task time, lowers task success — on every metric, hidden nav loses [S30]. NN/g's 2025 revisit concedes the hamburger is now *recognized* — but the interaction cost remains identical: still hidden [S31].
- **NN/g on bottom sheets:** sheets are *progressive disclosure* that preserve the map context — ideal for contextual detail, **wrong for anything the user always needs**. Their rules: support Back to dismiss; include a visible X (grab-handle-only dismissal fails users); **never stack sheets**; never use a sheet as a substitute page the user must return to repeatedly [S32]. Google Maps' place sheet is NN/g's own canonical example of correct nonmodal use [S32].
- **Apple HIG:** map stays interactive; muted basemap under information-rich overlays; don't redefine learned pin colors [S9, S10].
- **What "drawer" means in 2025:** the navigation drawer is dead in premium consumer apps. Google Maps put the account behind an avatar *inside the search pill*; the "drawer" pattern survives only as (a) a **profile menu** opened from the avatar (settings, history, low-frequency stuff) and (b) the **bottom sheet** for contextual content. A left-edge hamburger sidebar for core features is a 2014 pattern and reads as such.

### 3.2 The screen-space budget

A consumer map app at rest gets exactly this chrome, nothing more:

| Zone | Content | Budget |
|---|---|---|
| Canvas | Map + dose field + user puck + reports + route | ~100% — always the majority visible |
| Top pill | Search field + avatar inside it | one rounded bar, ~52px |
| Top-right column | **maximum 2 floating buttons** (locate, report) | 2 × 44px |
| Bottom | Sheet at peek detent, or nothing | ≤ ~15% at rest |
| Numbers on canvas at rest | **at most one** (live breathing value chip) | 1 |

Everything else — week stats, journeys, cleanest-air times, settings, share — lives **behind the avatar → profile sheet** or inside the main bottom sheet's detents. Our current ☰ JourneyDrawer migrates there (§7). If an element doesn't earn pixels on this budget, it earns a detent level, not a home-screen position.

### 3.3 The hidden-state rule

Features appear *when they're true*: horizon chips only while comparing future departures; the report picker only while reporting; the ledger pill only when today's dose > 0. **Rest state shows the least possible UI that still offers the next action.** This is the single biggest "premium vs slop" separator — the slop version shows every feature always.

---

## 4. The orgasmic dashboard — what premium data-viz actually is

The user wants the maths/physics to surface as a *"sexy orgasmic dashboard of Delhi air."* Studying the references:

### 4.1 The masters

- **Strava Year in Sport** (design by Manual/others): personal data as *celebration* — one stat per screen, huge type, a modular graphic language of "layered color panels, lines, dots" animating each datapoint; 2.5M+ personalized in-app stories. The trick: **data reveals itself through motion**, turning/layering/revealing — not static charts [S33, S34].
- **Spotify Wrapped**: story format (vertical snap, one idea per frame), *shareable by design* — the dataviz doubles as identity expression [S35].
- **Dark Sky** (dead, canonized): the Nightingale eulogy calls it "a hallmark of information design" because **everything was a context-sensitive information graphic** — the 2018 "unified timeline" put current conditions + next-hour + next-24h + week in *one scrolling column anchored at now*; past data was deliberately deprioritized because "I only occasionally care about weather from hours ago" [S36]. Apple absorbed it wholesale into Apple Weather.
- **Apple Weather**: Gestalt *common region* — small bounded boxes group related metrics so the eye files them instantly; "Aesthetic and Minimalist Design" (Nielsen #8): every element earns presence or dies [S37]. Apple's pictogram discipline (SF-style: outline for toolbars/lists, fill for selected/emphasis; strictly gridded to sit with text) is the icon-system model [S38].
- **Windy.com**: the field rendered as a *living particle system* — wind/pollution as animated flow over cartography (see `windy-wind-layer.png` over Delhi). It feels "orgasmic" because **the data is literally moving** — physical intuition (drift, direction, turbulence) is transmitted without a single number. This is our field's true visual: kriged PM2.5 + wind advection as drifting particles.
- **Swiss/International Typographic Style**: mathematical grid, asymmetric layout, huge tabular numerals, hairline rules, vast negative space, one accent color — information as architecture (Müller-Brockmann).
- **Tufte**: maximize the *data-ink ratio* — erase non-data ink (chartjunk: grids, boxes, 3D, moiré); use *small multiples* (same chart shape, different slice, aligned axes); use *sparklines* — word-sized graphics living inline in text. A Tufte dashboard is a *page of sentences where numbers became shapes*.

### 4.2 What makes a chart feel premium vs dashboard-y

| Premium (do) | Dashboard-y (don't) |
|---|---|
| One idea per view; giant single numbers | Grid of equal-weight KPI tiles |
| Unified timeline anchored at *now* | Multiple date pickers / arbitrary ranges |
| Small multiples sharing one axis | Each chart with its own furniture |
| Field/particle viz = the physics itself | Bar chart standing in for a field |
| Black canvas, white type, one ramp | White card grid with colored headers |
| Numbers in sentences ("Delhi breathed 4.2 cigarettes") | Numbers in boxes with icon headers |
| Provenance shown as design (spec table, tick marks) | Settings-style disclaimers |
| Reveal through scroll/motion | Everything on screen at once |

**The orgasmic-dashboard insight:** it is *not* a page in the app — it's a **mode the map transforms into**, or a separate surface (the "Delhi Air" editorial view). The commute UI stays wordless; the dashboard is where the physics gets luxurious. Conflating them is exactly what produced the hated "noisy dashboard" current UI.

---

## 5. The visual system spec

### 5.1 Palette

Monochrome canvas + **one accent** + **one semantic dose ramp**. Nothing else has color.

**Neutrals (the app):**

| Token | Hex | Role |
|---|---|---|
| `ink` | `#1C1917` | Primary text, primary glyphs, pins |
| `ink2` | `#57534E` | Secondary text, quiet icons |
| `ink3` | `#A8A29E` | Disabled, ghosts, hairline-adjacent text |
| `paper` | `#F7F7F6` | App background behind sheets (true-neutral, *not* cream — warm-cream bands are an AI tell [S20]) |
| `surface` | `#FCFCFB` | Sheets, pill, cards |
| `hairline` | `#E7E5E4` | All separation; no shadows+borders combos |
| `ambientInk` | `#06070A` | Dark/ambient mode canvas |
| `ambientPaper` | `#F5F5F4` | Text on dark |

**ONE accent — "go" blue:**

| Token | Hex | Role |
|---|---|---|
| `go` | `#1D4ED8` | Interactive elements only: selected route, primary button, user puck ring, tappable text. (Deep blue — the most-learned affordance color in navigation; safely below the banned AI hue bands. Replaces the teal `#0F766E`, which reads "eco-startup" and sits in the cyan-on-dark reflex band the user already rejected.) |
| `goSoft` | `rgba(29,78,216,0.08)` | Selection tints, active chip fill |

**Dose ramp — single hue, monotonic lightness** (survives grayscale + colorblindness; keyed to *dose vs trip budget*, never to AQI bands):

| Stop | Hex | Meaning |
|---|---|---|
| `doseQuiet` | `#78716C` | Unremarkable — under ~50% of budget. Neutral, not green: "nothing to warn about" has no hue |
| `doseWarn` | `#FB7185` | Approaching/≈1× budget |
| `doseOver` | `#E11D48` | Over budget |
| `doseSevere` | `#9F1239` | ≥2× budget |
| `doseExtreme` | `#4C0519` | Smoke day / GRAP III–IV indicative |

Map field layer = continuous `transparent → #E11D48 → #4C0519` opacity+color interpolation so dense areas deepen like smoke.

**Banned hues:** 260–310 (violet/purple) and cyan 160–200 on dark — the AI fingerprints [S20, S21]. Green is banned as a *semantic* color entirely (never means "safe").

### 5.2 Type

**Family: keep Outfit** (Rodrigo Fuenzalida for Outfit.io [S39]). Honest note: Outfit now appears on "reflex sans" watchlists [S20] — but identity-preservation beats churn when the brand already ships it, and the slop problem was never the font, it was undisciplined use. Make Outfit look *chosen*: tabular numerals always, tight tracking at display sizes, no light weights at small sizes. (If we ever want a more engineered voice, IBM Plex Sans is the non-slop alternative — one family, never mixed.)

**Scale** (8pt grid; RN `fontSize`):

| Name | Size/Weight | Use |
|---|---|---|
| hero | 56 / 700, tracking −2% | Ambient-mode number only |
| display | 34 / 700, tracking −1.5% | The hero dose number, sheet title number |
| title | 22 / 600 | Sheet headers |
| rowTitle | 17 / 500 | Mode rows, list primaries |
| body | 15 / 400 | Body, secondary lines |
| meta | 13 / 400 | Arrival times, distances, captions |
| micro | 11 / 500 | Units next to glyphs, tab labels (never all-caps-tracked) |

**Rules:** `fontVariant: ['tabular-nums']` on every numeral; Outfit Light(300) banned below 34px (Apple HIG: avoid light weights, they vanish [S40]); no italics; no uppercase-tracked "eyebrow" labels (the #1 AI tell [S20]); line-height 1.25× on titles, 1.4 on body; max one display-size numeral per view.

### 5.3 Iconography

- **Custom glyph set only**, ~14 glyphs: walk, bike, moto, auto-rickshaw, e-rickshaw, car, cab, bus, metro; lungs, cigarette, smoke-plume, dust-swirl, flame, leaf, wind; locate, report-flag, clock, bell, share, close-X.
- **Construction:** 24×24 grid, 2px stroke, round caps/joins, single-color ink. Vehicles = **flat filled side-profile silhouettes at the arrival angle** (Rapido vocabulary [S14], flat not 3D).
- **States:** outline = inactive/list, filled = selected/emphasis — the SF Symbols discipline [S38].
- **Meaning table:** every glyph names exactly one thing — a cigarette glyph *always* means dose-equivalent, lungs always mean exposure. No glyph serves two meanings; no two glyphs serve one meaning.
- **Bans:** no emoji, no icon-font mixing (Lucide next to Phosphor etc.), no badges-with-numbers on icons, no decorative icons.

### 5.4 Component inventory

| # | Component | Spec |
|---|---|---|
| 1 | `Basemap` | Custom Positron-derived monochrome style — neutral grays only: land `#F4F4F2`, water `#EAEAE8`, green/park `#E9E9E5`, roads `#FFFFFF` w/ `#D6D4D0` casing, labels `#787670`/`#4A4843`, buildings `#E3E1DE`. (Positron already on our free infra [memory]; de-beige it so canvas is true B&W.) |
| 2 | `SearchPill` | One floating field, h=52, radius full-pill, surface + hairline, avatar inside right edge. Placeholder is the only copy: "Where to?" Origin defaults to 📍current — no second field until needed. |
| 3 | `HorizonChips` | Clock glyph + relative labels (now / +6h / +12h / +24h), h=32 pills, below pill, only while horizon scrubbing is relevant |
| 4 | `ModeRow` | silhouette 28px \| ETA 17/500 tabular \| meta 13 (`km · arrive 18:42`) \| `DoseBar` — hairline separators, h≥56, no card chrome |
| 5 | `DoseBar` | 44×5 track `hairline`, fill = dose color, width = % of 316µg budget; on selected row adds `🚬 n.n` in 13/meta right-aligned |
| 6 | `EndpointPins` | origin = ink dot ringed paper; destination = ink teardrop w/ paper center. No gradients, learned pin shapes kept [S10] |
| 7 | `RouteLine` | selected = `go` 4px + paper casing; alternates = ink 30% dashed. Exactly one colored line on map |
| 8 | `LiveDoseChip` | (nav mode) cigarette glyph + running trip dose, 13/meta tabular, floating bottom-left, surface hairline |
| 9 | `ReportFAB` + `ReportPicker` | FAB → four pictographs (dust swirl / smoke plume / flame / leaf), wordless. Reports render on map as *their* pictograph, never a generic dot [S13] |
| 10 | `ProfileButton` | avatar in SearchPill right edge — replaces ☰. Opens ProfileSheet (journeys, ledger, cleanest-air, reminders, share — the old JourneyDrawer contents) |
| 11 | `BottomSheet` | detents peek(96)/half/full; grabber **and** X (NN/g [S32]); map visible above at all non-full detents; Back dismisses; never stacked |
| 12 | `AlertBanner` | ink full-width strip, paper text, one line + X — reserved for GRAP-level / hazardous events only |
| 13 | `LedgerSheet` | today's dose strip → expands to week (cigarette-glyph bars per day, not a chart) |
| 14 | `AmbientMode` | opt-in full-bleed `ambientInk`; one hero number; one glyph; nothing else |
| 15 | `CityDashboard` | §8 — the orgasmic surface; separate mode, dark editorial |

### 5.5 Motion

- Only state transitions animate: route draw (~300ms ease-out), sheet drag physics, dose-fill tween, pin drop.
- Durations 200–300ms, ease-out, no bounce/spring overshoot, no parallax, no infinite pulses.
- The field layer may *breathe* — particle drift is data, not decoration (Windy lesson).

---

## 6. The anti-slop checklist — 12 don'ts

Keyed to the user's complaints (greenish liquid-glass, noisy dashboard, random icons/graphs/dates, hated sidebar) + the AI-design literature [S20, S21, S41]:

1. **No tinted translucency.** No liquid-glass, no blur stacks, no green/teal-tinted anything. Surfaces are `surface` at ≥95% opacity or solid ink. (The thing he named "cheap vibecoded AI slop.")
2. **No gradients.** Color varies only inside the dose ramp in a data fill. No mesh/aurora backgrounds, no gradient text, no gradient buttons.
3. **No AI hues.** Violet/purple (260–310) and cyan-on-dark (160–200) are banned. Palette = neutrals + `go` + dose ramp. That's all the color that exists.
4. **No unexplained numbers.** Every number carries a glyph-unit (🚬), a comparison, or position-meaning. "AQI" never renders. `µg/m³` appears only inside the dashboard.
5. **No ornamental charts.** Zero graphs on the home canvas or its peek sheet. A chart must be something the user opened deliberately (sheet, dashboard).
6. **No decorative icons.** Every glyph is a verb (tappable) or a unit (means a quantity). If it neither acts nor measures, it doesn't exist.
7. **No navigation drawer.** ☰ is deleted. Low-frequency surfaces live behind the avatar in a profile sheet; contextual content lives in the bottom sheet (NN/g: hidden nav halves discoverability; sheets preserve context [S30–32]).
8. **No context-free stats.** Every metric ships with its reference — vs budget, vs typical, vs yesterday. A bare number is a bug.
9. **No chrome stacking.** No card-in-card, no border+shadow on one element (commit to hairline *or* ≤8px-blur shadow), no colored side-stripe borders, radius ≤16 (pills excepted).
10. **No "safe = green."** Quiet state is neutral gray — absence of dose color *is* the good news. Green appears nowhere as a semantic.
11. **No fake data or fake precision.** No invented dates, placeholder stats, or extra decimals — every number traces to a live endpoint field (the repo's zero-fake-data rule applies to pixels too).
12. **No decorative motion.** Only state transitions animate. No bounce, no pulsing FABs, no shimmer-on-load, no confetti.

---

## 7. The one-screen hierarchy — map home

**Rest state** (no route selected):

```
┌─────────────────────────────┐
│ (avatar) Where to?       ⌕  │ ← SearchPill, top, 16px margins
│                             │
│         ·   ·      ·        │ ← dose field + report pictographs
│      (monochrome map,       │   + user puck (go ring)
│       field layer ON)       │
│                             │
│                    ◎ locate │ ← FAB column (max 2)
│                    ⚑ report │
│ ┌─────────────────────────┐ │
│ │ 🚬 0.4 · breathing here │ │ ← LiveDoseChip (only number at rest)
│ └─────────────────────────┘ │
└─────────────────────────────┘
```

**Comparing** (after destination chosen): sheet rises to half detent — `ModeRow` list ranked by dose (the `/compare` output), map above keeps A/B pins + all alternates as ghosted dashed lines. Sheet never covers the pins.

**Navigating:** everything collapses — maneuver banner top (Apple/Google grammar), `LiveDoseChip` bottom-left, sheet dismissed. Nothing else visible.

**The discipline:** at rest ≤2 tappable clusters besides the pill, ≤1 number on screen. If you added a third FAB or a second number, you removed something first.

---

## 8. The orgasmic dashboard — "The City Breathes"

A separate surface (entered from the profile sheet or a map-layer toggle), full-bleed `ambientInk` canvas, editorial — the physics rendered luxurious:

1. **Hero — the living field.** Delhi's kriged PM2.5 surface rendered as an animated particle/flow field over the monochrome map — smoke drifting with real wind vectors (the Windy mechanic on our own field). The city *moves*. No axes.
2. **The number.** Field-median concentration set in Outfit 56/700 tabular, dead center — then, under it, the cigarette strip: `N` cigarette silhouettes filled proportionally = today's city-average dose (Berkeley-Earth units; winter Delhi ≈ 4–7).
3. **Unified timeline.** Dark Sky grammar: one column anchored at **now**, 24h back faint / 120h forecast dashed — the diurnal double-peak reads as shape, not data. One x-axis, hairline ticks, no grid.
4. **Small multiples.** PM2.5 · wind · boundary-layer height · FIRMS fire count — four same-width strips sharing the time axis (Tufte). Each strip: sparkline + current value + one-word label. No boxes.
5. **Station veil.** The 125 CAAQMS instruments as dots on the mono map, median-colored through the dose ramp; tap → sparkline + station name + last-updated. Provenance visible, not narrated.
6. **Provenance as design.** A Swiss spec-table: instruments blended (54 live — 24 WAQI + 30 DPCC @ 3×), interpolation (IDW p=2.0 + debias), MAE 8.8µg vs stations, coverage % — numbers in a ruled list, tabular, hairlines only. This is the section that makes judges trust the app — the math *is* the aesthetic.
7. **Your week vs Delhi.** Cigarette-glyph bars: your ledger vs city average, per day. The personal/city contrast is the emotional payload (Strava-YIS lesson: data as identity).
8. **Share card.** Generated image in this exact system: `This week, Delhi smoked N cigarettes.` + glyph strip + tiny provenance line — Wrapped-style identity object, wordless enough to post.

The dashboard proves the depth (kriging, blending, forecast, dose math) *by showing it beautifully* — and it never leaks back into the commute UI. Map = wordless utility; dashboard = the orgasm. Two surfaces, one language.

---

## Sources

1. [9to5Google — Google Maps sheets/directions redesign rollout](https://9to5google.com/2024/07/14/google-maps-android-redesign/)
2. [9to5Google — Google Maps pin shape/colors redesign](https://9to5google.com/2024/08/27/google-maps-pin-redesign/)
3. [Google/Material — How Google Maps ships with Material for Compose](https://www.youtube.com/watch?v=XQ_Hvu-s7JY)
4. [MCKL — Uber Move custom typeface](https://legacy.mckltype.com/custom/uber)
5. [Mason R. Field — Uber Move (transportation-signage influence)](https://www.masonrfield.com/work/uber-move)
6. [Creative Bloq — Uber rebrand / Wolff Olins system](https://www.creativebloq.com/news/uber-hails-its-new-logo)
7. [Uber blog — Design system at scale (Base)](https://www.uber.com/ca/en/blog/design-system-at-scale/)
8. [Lyft tap-to-dismiss — Lyft Product Language libraries + LPL Lint](https://medium.com/tap-to-dismiss/user-centered-design-system-resources-2df958d90749)
9. [Apple HIG — Maps](https://developer.apple.com/design/human-interface-guidelines/maps) (mirrored: apple-docs.everest.mt)
10. [Apple HIG (legacy mirror) — expected pin colors](https://codershigh.github.io/guidelines/ios/human-interface-guidelines/ui-views/maps/index.html)
11. [Jack Elliott — Waze redesign critique (report discoverability)](https://www.jack-elliott.com/waze-redesign)
12. [Waze suggestion box — hazard report shortcuts](https://waze.uservoice.com/forums/59223-waze-suggestion-box/suggestions/48188255-shortcuts-for-hazard-reports)
13. [Waze suggestion box — pictograph the hazard, not generic triangle](https://waze.uservoice.com/forums/59223-waze-suggestion-box/suggestions/44247993-picture-type-of-hazard-with-different-icons-on-nav)
14. [Liquidink — Rapido 3D icon system (arrival-angle vehicle icons)](https://www.liquidink.design/project/rapido)
15. [Rapido Labs — building Rapido's design system](https://medium.com/rapido-labs/building-rapidos-design-system-54a0e94bf5dc)
16. [Design Bootcamp — redesigning Rapido case study (clutter critique)](https://medium.com/design-bootcamp/redesigning-rapido-a-case-study-c9c9c8d56f2d)
17. [IXD@Pratt — Citymapper design critiques](https://ixd.prattsi.org/2026/02/design-critique-citymapper-ios-app/)
18. [TechCrunch — Plume Air Report launch analysis](https://techcrunch.com/2015/09/17/plume-air-report-is-a-weather-forecasting-app-for-urban-air-pollution/)
19. [Red Dot — Flow by Plume Labs](https://www.red-dot.org/project/flow-by-plume-labs-38523)
20. [Plume Labs — air quality app product page](https://plumelabs.com/en/air/)
21. [shootismoke/mobile-app — open-source (Expo/RN) cigarette-equivalence app](https://github.com/shootismoke/mobile-app/)
22. [Berkeley Earth — air pollution & cigarette equivalence (22µg/m³ ≈ 1 cig/day)](https://berkeleyearth.wpengine.com/air-pollution-and-cigarette-equivalence/)
23. [PIX11 — "How much do you smoke?" coverage](https://pix11.com/news/how-much-do-you-smoke-app-translates-air-pollution-into-cigarettes-smoked/)
24. [Tim Höfer — Zero design sprint case study](https://timhoefer.de/portfolio/zero-fasting)
25. [ScreensDesign — Zero UI breakdown](https://screensdesign.com/showcase/zero-fasting-health-tracker)
26. [Viktor Engborg — Levels glucose home screen (ring + ranges)](https://viktor.design/projects/designing-the-mobile-ux-for-real-time-glucose-monitoring)
27. [Levels Support — Zone Scores (bounded 0–10)](https://support.levels.com/article/32-about-glucose-response)
28. [South Coast AQMD — color-impaired accessible AQI scale (monotonic lightness)](https://www.aqmd.gov/home/research/pubs-docs-reports/newsletters/may-june-july-2022/accessible-aqi-scale)
29. [AirNow — AQI Technical Assistance Document (official 6-color ramp)](https://www.airnow.gov/sites/default/files/2020-05/aqi-technical-assistance-document-sept2018.pdf)
30. [NN/g — Hamburger Menus and Hidden Navigation Hurt UX Metrics (2016)](https://www.nngroup.com/articles/hamburger-menus/)
31. [NN/g — The Hamburger-Menu Icon Today (2025)](https://www.nngroup.com/articles/hamburger-menu-icon-recognizability/)
32. [NN/g — Bottom Sheets: Definition and UX Guidelines (2023)](https://www.nngroup.com/articles/bottom-sheet/)
33. [Tanner Irwin / designbyti — Strava Year in Sport](https://www.designbyti.com/strava-year-in-sport)
34. [Manual — Strava Year in Sport 2021](https://manual.studio/work/strava-year-in-sport-2021)
35. [Spotify Engineering — building Wrapped in-app](https://engineering.atspotify.com/2020/9/spotify-unwrapped-2019-how-we-built-an-in-app-experience-just-for-you)
36. [Nightingale — A Eulogy for Dark Sky, a Data Visualization Masterpiece](https://nightingaledvs.com/dark-sky-weather-data-viz/)
37. [Olivia Penn — Apple Weather design-principles analysis (common region)](https://olivia-penn.framer.ai/apple-weather-app)
38. [Dergipark — pictograms in weather apps incl. Apple/SF Symbols discipline](https://dergipark.org.tr/en/download/article-file/5765949)
39. [Google Fonts — Outfit (Fuenzalida / Outfit.io)](https://fonts.google.com/specimen/Outfit)
40. [Apple HIG — Typography (avoid light weights)](https://developer.apple.com/design/human-interface-guidelines/typography)
41. [pythoughts-labs designer-skill — avoid-ai-slop ban list](https://github.com/pythoughts-labs/designer-skill/blob/main/skills/designer-skill/reference/avoid-ai-slop.md)
42. [925 Studios — AI slop fonts & gradients tells](https://www.925studios.co/blog/ai-slop-design-tells)
43. [developersdigest — 16 vibe-coded UI patterns](https://www.developersdigest.tech/blog/ai-design-slop-and-how-to-spot-it)

*Reference captures taken this session: `windy-wind-layer.png` (Windy over Delhi), `google-maps-delhi.png` (current Maps chrome), `apple-weather-appstore.png` (hero-number grammar), `uber-appstore.png` (mode picker rows), `citymapper-appstore.png` (glyph-circle comparison).*
