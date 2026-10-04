# Probe battery — real-world coverage audit

`tools/probe_battery.json` holds 174 queries a Delhi commuter actually
types, in 17 categories: misspelled localities, bare landmarks,
institutions, markets, hospitals, IT parks, courts/gov, railway
stations, ISBT/bus depots, malls, sector+block compounds, house
numbers, airport/IGI, metro full names, UP/Haryana border towns,
Hinglish spellings, and verbatim user-typed queries. Each entry has an
expected substring set used for classification only.

`tools/probe_battery.py` runs the battery `--local` (in-process
`core_engine.search`) or `--live URL` (GET `/v2/search`, ≥0.35s
spacing) and classifies each query top-1 / top-3 / wrong / empty.

## Live audit, deployed build (NLB http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com)

- resolved **161/174 (92.5%)**: top-1 159, top-3 2, wrong 10, empty 3
- live `/v2/search` latency p50 472ms — that is client network RTT to
  ap-south-1, not engine time (engine p50 ~1ms local)

## After the leg-4 fixes (local, same battery)

- resolved **171/174 (98.3%)**: top-1 168, top-3 3, wrong 2, empty 1
- local engine latency p50 0.7ms, p95 28.4ms (sub-place scans on weak
  queries), max 945ms one-off cold
- fixes vs live: 11 misses resolved, 1 ranking wobble
  (`subhash nagr`, see below)

### What was fixed

- **Sub-place units** (`_subplace` in `core_engine`): block/pocket/
  sector/house-number queries now anchor on the named place and resolve
  the unit inside it — never a same-lettered unit in another colony.
  The "inside" radius scales to the anchor's measured extent (p80
  distance of its namesake rows): locality pockets ~1.5km, city sectors
  up to 6km. `beta 2`/`gamma 2`/`alpha 1` land on real Greater Noida
  sectors; `pocket b sarita vihar` falls back to Sarita Vihar (Jasola's
  Pocket B is correctly not an answer); `a 43 defence colony` finds a
  real `43` address inside Defence Colony.
- **Numeric constraints**: query digits must appear in the answer's
  display (`sector 12` can't land on `Sector 125`); unmatched numbers
  drop to the area-level honest fallback instead of a wrong sector.
- **Conflicting sector markers**: rows declaring a different `sector
  N` than the anchored one are rejected
  (`h block sector 62` no longer surfaces `H Block Market-Sector 22`).
- **Bus-depot/terminal kinds**: `depot`, `terminus`, `isbt`, `adda`,
  `bus depot`/`terminal`/`terminus` phrases map to bus kinds incl.
  `amenity:bus_station` — `badarpur bus depot` now resolves.

## Remaining misses — honest, categorized

- `panipat` → empty. Panipat city is at 29.39°N, ~30km north of the
  corpus extract bbox (28.08–29.07°N). Genuine service-area ceiling.
- `subhash nagr` → Subhashnagar. Both spellings are real places in the
  corpus (joined spelling mostly outside Delhi proper); cov-1.0 tie —
  which one the user meant is genuinely ambiguous.
- `25 rajinder nagar` → Rajendra Nagar (area). The OSM-canonical name
  of the locality is "Rajendra Nagar" — the fuzzy anchor resolves to
  the right area; a literal "Rajinder Nagar" exists only as post
  office/constituency rows. Area-correct, spelling-canonicalized.
