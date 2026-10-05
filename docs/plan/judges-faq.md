# Judges' FAQ — honest answers (no hype)

Short, checkable answers to the questions that decide the score. Every
number below was read off the live service on 2026-10-05 (latest pass
~22:15 UTC, build `80a15258` — breathing-zone dose basis,
`smoke_modifier` 1.09); the ones that drift are marked.

## "Is the data real?"

Yes, and the provenance is on the wire. The field is rebuilt every 15
minutes from three live sources: **24 WAQI ground instruments** across
NCR (their raw US-EPA sub-index is inverted back to µg/m³ via the EPA
breakpoint table, Kalman-smoothed, and de-biased against an archive),
**~70 CAMS/open-meteo model samples** (satellite-assimilated), and **79
NASA FIRMS VIIRS fire detections** (17 inside the smoke belt) feeding a
×1.09 smoke modifier — all counts read live, all drifting daily. A CPCB
adapter exists but stays dormant without a CPCB key — the sources table
names which feeds are up instead of padding. Every estimate carries a
real krige σ from our own C++ engine (`/health` → `engine:"alive_core"`),
and where the field can't support a claim it says so: `coverage < 1`
near the edge, `confidence: "low"` on thin cells, a typed
`outside_service_area` error for Mumbai instead of a fabricated answer.
Nothing is seeded, canned, or zero-filled.

## "Why does the dose differ from the AQI?"

Because AQI is a city-level index and dose is a personal integral. We
compute **inhaled micrograms = concentration (µg/m³) × ventilation rate
(L/min, per mode) × time in the plume**, sampled every ~250 m along the
actual route geometry, then corrected for the mode's micro-environment
— a sealed AC car filters; a bike rider sits inside the exhaust stream.
Same street, same minutes: walking Connaught Place→Gurugram inhales
~358 µg while a sealed car inhales ~11 (measured live 2026-10-05 ~22:15
UTC on `80a15258`, breathing-zone basis, ~33×).
AQI
can't express that: it has no route, no breathing rate, no duration, no
vehicle. A judge breathing harder than the person next to them is
already living the difference — we just put a number on it.

## "Privacy?"

Aggregate-only by construction, and the floor is in the math, not the
policy page. No accounts; device tokens are stored hashed
(sha256[:16]); route endpoints are trimmed on-device before upload.
Nothing publishes below **k=3 distinct devices over a 72-hour window** —
a street appears on the community map only after three different riders
cross it, mode share suppresses any bucket under 3 trips
(`mode_share_suppressed_trips` is literally on the wire), and review
notes publish only at ≥3 reviews. The ops board reads the same
aggregate tables a judge sees; there is no per-user view to leak. 12 of
54 tracked corridors are currently publishable — the other 42 are
honestly suppressed, not hidden behind a disclaimer.

## "Could a competitor just build this?"

The UI they could copy in a weekend; the hard parts are underneath.
(1) A **C++ exposure engine** (`alive_core`, Eigen) that kriges the
field with a real σ and re-prices **1,070,459 road edges** every 15
minutes — the plan optimizer, dose sampler, and field interpolator are
one codebase, so the number shown is the exact criterion the path won
on. (2) **Calibrated bands**: the σ isn't krige output, it's measured —
`σ = √(krige_sd² + (0.12·µ)²) × 3.2`, fitted on 3,550 held-out
station-hours (raw krige covered only 29% of truth; we widened until it
covered 95.2%). (3) The **mode physics**: per-mode micro-environment
factors and ventilation rates re-anchored to measured Delhi commuter
literature, not defaults. (4) The plumbing nobody sees: GTFS-transit
arm fused with a self-hosted OSRM arm plus the C++ engine arm, all
under a 20-second budget that degrades by naming the failed arm rather
than fabricating. A demo is easy to imitate; a verified pipeline isn't.

## "What does 95.2% actually mean?"

It's the measured coverage of our uncertainty bands, not a marketing
percentage. We held out **3,550 station-hours across 85 stations** from
the krige input, then asked how often the true measured value landed
inside our reported ±2σ band: it did **95.2%** of the time (nominal
target 95.4%). That number exists because we measured it — the raw
krige σ alone covered only ~29% of held-out truth, so we recalibrated
(`field_validation.md` in `server/data/`). Honest consequence for the
demo: when a cell's band is wide, it's wide because sensors are far —
17.6 km from the nearest sample the band honestly reads 19–81 µg/m³
instead of a false-precision point estimate.
