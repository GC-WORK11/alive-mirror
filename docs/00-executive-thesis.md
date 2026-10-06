# 00 · Executive Product Thesis

## 1. Problem definition

Delhi residents inhale some of the worst urban air on earth. PM2.5 regularly exceeds WHO limits by 10–20× in the Oct–Feb season. The tools available today all stop at *information*: AQI dashboards, color-coded maps, health advisories ("stay indoors"). Nobody answers the operational question a commuter actually faces:

> **I must travel from A to B today. Which route, at what time, in which mode, minimizes what I breathe — and what does it cost me?**

Movement decisions — route, mode, departure time — are the only exposure levers a person controls daily. Software that measurably improves those decisions reduces real inhaled dose. That is the product.

## 2. The user

Primary: a Delhi commuter who travels on a schedule — student, office worker, delivery-linked worker — traveling mixed-mode (walk + auto + metro, or 2W/car). Secondary: parents deciding how kids get to school on bad-AQI days (GRAP stages directly affect this), cyclists/joggers choosing *when*, not whether.

Non-user: someone looking for a general air-quality report. That product exists 40 times over.

## 3. Why Delhi-only is the advantage

A generic product can interpolate a handful of global feeds. Delhi specialization lets us win where global products can't:

- **46 CAAQMS stations** (30 DPCC + 10 IMD/IITM + 6 CPCB) — the densest government monitoring network in India, published free via CPCB/OpenAQ paths. (Shipped reality Oct-6: 54 instruments live — 24 WAQI + 30 DPCC; data.gov.in is TCP-refused from ap-south-1, OpenAQ key dormant — `docs/plan/handoff.md`.)
- **Official open transit data**: Delhi Govt + IIIT-D publish GTFS for **543 bus routes / 3,464 stops** and **DMRC metro (262 stations, 36 routes)** at otd.delhi.gov.in — including real-time vehicle positions. Almost nobody builds on this.
- **Seasonally predictable physics**: Oct–Nov stubble burning in Punjab/Haryana contributes ~20% avg PM2.5, up to 50–75% on event days (peer-reviewed). NASA FIRMS gives us the fire detections that drive those events — a Delhi-specific forecasting edge.
- **Published Delhi exposure studies** for every transport mode (metro, AC car, rickshaw, bus, cycle, walk) — defensible dose factors specific to this city's fleet and street geometry.
- **GRAP stages** create legible decision context: Stage III/IV change school/office rules on exactly the "bad days" the track brief names.

## 4. Product definition

A web app (PWA-first) with one primary interaction:

**FROM → TO → 2–4 real itineraries → ranked by estimated inhaled PM2.5 dose, with time/cost trade-offs and confidence.**

Secondary, one-glance surfaces:
- "Leave now vs leave at 10:30" — dose-by-departure-time curve
- "Your trip, your exposure ledger" — estimated dose avoided by past choices
- Bad-day mode: GRAP stage + tomorrow's fire-driven outlook

## 5. What makes it a breakthrough (not a wrapper)

Three things nobody shipping today combines:

1. **Mode-aware dose routing.** Metro and AC-car legs score orders of magnitude lower per km than rickshaw/walk legs. The optimizer therefore produces mixed-mode itineraries that pure road routers never find ("auto to Azadpur → Yellow line to Nehru Place → short walk" beats "drive the whole way" on exposure by ~4–6×, for +9 min).
2. **A Delhi-calibrated concentration field**, not an API echo: the NCR instrument network (54 live today) + land-use + near-road traffic increments + meteorology (wind, boundary-layer height) + stubble-fire transport signal — fused into a gridded surface *with uncertainty*.
3. **Honest numbers.** Every figure labeled measured/modeled/estimated with a confidence band. Judges see a system that knows what it doesn't know — more credible than fake precision.

## 6. What it is not

- Not a dashboard. Not a chatbot. Not an AQI map clone.
- Not "reduce Delhi's pollution" — it reduces *personal exposure*. Different claim, honestly scoped (impact framework in doc 05 keeps these separate).
- Not a Google Maps replacement for navigation — it is a thin decision layer *on top of* real routing infrastructure.

## 7. Success definition for the hackathon

A judge opens the demo URL, types "Kashmere Gate → Hauz Khas", and sees:
- 3 itineraries: drive vs metro+walk vs 2W — with dose µg, % difference, minutes, rupees, confidence
- a map showing the pollution field the routes pass through
- one honest recommendation and why
- live Delhi data underneath (real instruments timestamped on the wire — `/health.sources.stations`)

That demo is undeniable because every number traces to a real station, a published factor, or a labeled model.
