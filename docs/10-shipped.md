# What ALive-108 actually computes — and where every number comes from

This document is the provenance sheet. Every figure the app shows traces
to a named source or a stated assumption. Where we estimate, the response
says so (`duration_model: "estimated"`, `confidence`, `coverage`).

## The product

`FROM → TO` returns what the trip makes you inhale — µg of PM2.5 that
reaches your lungs — for every travel mode, right now, plus the best
hour to leave. Not an AQI map. A dose engine.

## What is measured vs modelled

| Shown as | Source | Honesty |
|---|---|---|
| Live PM2.5 field at any NCR point | Open-Meteo CAMS grid + 28 named CPCB/DPCC station anchors, IDW p=2 | `field` block: sample count + age |
| Inhaled dose per mode (µg) | dose = breathing-zone conc × ventilation × time; breathing-zone = field × microenv | microenv/ventilation ratios are published measurements (Delhi commuter studies); shown under "why?" |
| Car/road durations | OSRM road network | `osrm` |
| Walk/cycle/bus durations | distance ÷ typical Delhi urban speed (walk 5, cycle 15 km/h; bus/auto/bike scale car time) | flagged `estimated` — the public OSRM demo only has the driving graph |
| Metro option | real DMRC network: 62 stations with OSM coords (Overpass), walk→metro→walk legs scored per-leg; metro leg at 0.45 breathing-zone | skipped (`null`, not faked) when either endpoint sits >2.5 km from a station — the honest answer is "metro isn't for this trip" |
| Forecast (leave-later) | Open-Meteo hourly CAMS 120 h + boundary-layer-height/wind stagnation factor (ventilation-coefficient proxy, IMD/IITM convention) | raw model × clamped factor [0.6, 2.5]; factor=1.0 when met data missing |
| Fire-season modifier | NASA FIRMS VIIRS active fires over the NW-India fire belt, gated by wind quadrant | needs `FIRMS_MAP_KEY`; without it modifier=1.0 and `fire.status` says `no-key` — never invented detections |
| Station history (decade) | OpenAQ public S3 archive, Delhi stations 2016→ | merged separately |

## What we refuse to fake

- "Real-time" means the cadence regulators actually publish:
  stations report every 15–60 min; CPCB stations documented to go blank
  at exactly peak hours. When the nearest sample is old or far,
  `confidence` drops — it is never hidden.
- The app cuts *your* exposure. It does not claim to reduce Delhi's
  pollution. Exposure avoidance and emission reduction are different
  things and only one of them fits in a phone.

## The math, honestly

```
dose_ug = Σ_segments [ field(lat,lon) × microenv(mode) × road_uplift ]
          × ventilation_L/min(mode) × minutes_in_segment
```

microenv (breathing-zone / ambient): metro 0.45, car AC 0.55,
car windows-down 0.80, bus 0.70, two-wheeler 1.10, auto 1.15,
cycle 1.10, walk 1.00 — published transport-microenvironment studies.

ventilation L/min: metro/car 7.5, bus 8.0, auto 8.5, bike 9.0,
walk 14.0, cycle 22.0 — breathing rate rises with exertion; walking a
long trip inhales far more volume even at the same concentration.

That is why, live tonight, Karol Bagh → India Gate reads
Car AC 3.8 µg vs On foot 118.6 µg — ~31× — and why "leave at 07:00
tomorrow" can cut the same auto trip ~87%: Delhi's boundary layer
collapses overnight and traps pollution; morning ventilation disperses it.
