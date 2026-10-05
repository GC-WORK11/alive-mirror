# 10 · Claims ledger — what we may say, what we never say

Rule: every number on a screen, in the video, or in the writeup traces to a row here.

## Say (verified or published, with the label shown)
| Claim | Label we show | Source |
|---|---|---|
| "Same trip, an open auto can mean several times the smoke of a closed car; on foot, up to ~30× metro per km" | "measured on Delhi roads" | Goel et al. / Sci. Total Environ. 2021; Discover Atmosphere 2025 (in `server/exposure.py` header) |
| Dose for this trip: "~41 µg (32–55)" | always a band, "est." | our field + kriging σ (`krige.py`) |
| Cigarette equivalent | "≈ 0.13 cigarettes" | Berkeley Earth equivalence; `CIG_UG = 316` |
| Emissions for this trip: "vehicles like yours: ~1.1–1.6 kg CO2, 0.02–0.06 g PM2.5" | "estimated for a 2016 petrol car (BS-IV)" | docs/29 §3 (ARAI/ICAP 2007 + real-world uplift) |
| Metro trip emissions are not zero | "incl. electricity" | docs/31 §3 (~11–25 g CO2e/pkm) |
| Delhi active fleet ≈ 83 lakh; two-thirds two-wheelers | — | docs/32 §0 (Delhi transport dept; DES via PTI) |
| ~89% of measured on-road vehicles BS-IV or newer | — | ICCT TRUE remote sensing, 111,712 measurements (docs/32) |
| ~31% of active vehicles had expired PUC (Sept 2024) | — | Delhi govt via ET (docs/32) |
| Transport share of Delhi PM2.5: "18–39% depending on the study" | always the range | docs/32 §4 |
| Field accuracy vs real stations: MAE ~22 µg/m³, over-reads in clean hours (clean-air window; LOO live-instrument MAE is 46.1) | shown on the city dashboard | `server/data/field_validation.md` |
| "Data is N minutes old" | always visible | field timestamp |

## Never say
| Killed | Why |
|---|---|
| "Your car emitted 42.0 g" (point value) | per-vehicle truth is unknowable; PUC can't measure PM (docs/29) |
| "Your phone measured the air" | phones measure nothing; they traverse a model field |
| "Delhi's air got cleaner because of ALive" / "we cut X tonnes" | unprovable at our scale (docs/26 kill list) |
| "First pollution-aware routing" | prior art exists (docs/27) |
| "Real-time AQI every second" | field updates every 15 min; the ticker is local math (docs/30) |
| "12M vehicles", "10M gig drivers", "vehicles cause 40%" | wrong or unscoped (docs/32) |
| "CNG is clean" | ICCT TRUE: high-use CNG 1.5–14× over limits (docs/29) |
| Any "AI predicts…" | we use physics + statistics; no ML claims without validation |

## What we CAN say about impact (the honest version)
1. **Per trip, provable:** "This choice cut your smoke by X (band) and the trip's estimated emissions by Y (band) versus the option you'd usually take." Both sides from published tables + our field.
2. **Behaviour, countable:** "N trips switched to a lower-smoke option this week" — a count, from the app, auditable on the dashboard.
3. **Data, real:** "Delhi now has a street-level, hourly picture of what commuters breathe — built from N anonymous trips." It's infrastructure that didn't exist; we don't claim outcomes beyond that.
