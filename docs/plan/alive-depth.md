# ALive depth map — the honest ladder

Owner mandate (2026-10-05): deeper than travel, deeper than psychology —
"living in Delhi is itself an entire lifestyle; the app should become the
lifeline of Delhiites; deeply personal without taking personal data; no
cringe, no fake."

## What the graveyard teaches

- **Plume Labs Flow** ($200 hardware personal PM dosimeter): discontinued
  2023 — hardware can't scale; knowledge pivoted to research.
- **BreezoMeter**: consumer app killed twice — its own VC cut it ("we
  realized we needed to build the data"), then Google bought the data for
  ~$200M and shut the app (Sept 2023).
- Lesson: nobody sustained consumer AQ because every product sold *"how
  bad is it"* — a lookup. Retention needs *"what do I do"* — a decision.

## What retains (researched, not invented)

- **Japan's pollen apps** are the closest proven template — pollen is
  Japan's Delhi-smog (seasonal, universal, personal). 花粉Watch and
  Aeras share one shape: a **morning score answering "can I go out, what
  do I prepare"**, a widget glance, notifications only on days that
  matter, a seconds-long symptom diary, and a correlation engine that
  finds **your** triggers. Every feature answers one question.
- Delhi's documented season behavior: kids confined indoors Oct–Jan,
  schools move sports inside, morning walkers/cyclists stop, parents told
  to check AQI daily. The daily decision surface is real: morning-run
  timing, kids' outdoor play, park hours, window open/shut, mask or not,
  which mode home.

## The never-done claim (defensible)

**The personal PM2.5 dosimeter without hardware.**
Personal-exposure reconstruction (trajectory × concentration surface →
individual dose timeline) is an established research method — papers show
residential-only exposure is wrong and phone GPS suffices. Nobody ships
it to consumers. Plume needed a device; we need nothing — the field is
already sampled per-cell per-hour and the phone already knows where it
was. Privacy is the architecture, not the policy: the timeline is
reconstructed on-device; only consented k≥3 aggregates ever leave. We
can't leak what we never take.

## The ladder

- **L0 — exists**: live field (24 stations + model + fires), C++ engine,
  dose-priced routing, departure curves, k≥3 community, honest bands.
- **L1 — your day, reconstructed**: on-device timeline × field history →
  "your day in dose" — where each µg accumulated. The ledger grows a
  spine: attribution by place and hour.
- **L2 — the morning card**: one honest answer per day for your area —
  today's heavy window, the clean slot, the one decision it changes
  ("run after 11", "kids out before 5"). Not a dashboard — a card.
- **L3 — the symptom lens**: five-second log (breath / eyes / energy) →
  on-device correlation: "your rough mornings follow your heavy days by
  ~14h." Your triggers, computed locally, never uploaded.
- **L4 — budget + reach**: your µg budget → lung reach ("where your
  lungs can go today") + routes flagged against it.
- **L5 — the Delhi rhythm**: school-play windows, park hours, market
  runs, purifier timing — each a one-line honest answer off the field.

## Form

One vertical feed — morning card, your day, budget, the field — each
card answering a question in one breath. No dashboard chrome, no charts
for charts' sake, no badges. The register stays: serif headline number,
mono provenance, hairline, CPCB-muted color only where color means data.

## What we refuse

- No fake precision (bands stay visible; confidence is stated)
- No health-outcome claims ("you will lose X years" — GBD math is
  population-level; honest version is directional at best)
- No behavioral nagging ("leave at 6am" fails people with jobs)
- No personal data leaving the phone unconsented — the checkable line
  is on the receipt: "kept on this phone only"
- No per-trip records at rest — donations fold into cell/hour/day
  aggregates at ingest; the server can't leak a journey it never kept
  (PRIVACY.md, `community.py`)
- No feature slop: every card must answer a question a Delhiite actually
  asks today
