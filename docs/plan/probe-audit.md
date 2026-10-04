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

## Second wave (live re-audit by parent)

Four more live misses on the deployed build, all fixed engine-side:

- `house 559 udyog vihar` → was "Mayur Vihar Gaurd House": 'house' is
  real vocab and drowned the number. Now filler tokens
  (house/h.no/flat/plot/no/unit/floor/kothi/bungalow) are stripped when
  the query carries digits → real `559 Udyog Vihar Phase V Road` top-1.
- `b-12 lajpat nagar` → was a mandir: numeric constraint removes it;
  the multi-anchor pass finds `B-12 Sanwal Nagar` — the real B-12 in
  the adjacent colony inside the anchor's extent — with the anchor
  visible in the subtitle ('address · Lajpat Nagar').
- `aiims` → twin 'AIIMS' platform bays 72m apart outranked the
  hospital. Same-name same-kind rows within 100m now collapse to one,
  and accessory kinds (platform/stop_position/stop/bus_stop/
  subway_entrance) demote below a landmark their name expands to —
  'AIIMS' aliases to the institute's full name, so the hospital leads.
- `lodhi garden` → 'Lodhi Garden' platform beat 'Lodi Gardens' park on
  spelling proximity. Same accessory-demotion rule; the park leads.

Comp rows now carry `subtitle = '<kind> · <anchor>'` so the resolved
area stays visible next to the unit row.

Local battery after wave 2: still **171/174 (98.3%)**, p50 0.8ms,
p95 63ms on sub-place-heavy queries (multi-anchor scans; typical
traffic stays at p50).

## Remaining misses — honest, categorized

- `panipat` → empty. Panipat city is at 29.39°N, ~30km north of the
  corpus extract bbox (28.08–29.07°N). Genuine service-area ceiling.
- `subhash nagr` → Subhashnagar. Both spellings are real places in the
  corpus (joined spelling mostly outside Delhi proper); cov-1.0 tie —
  which one the user meant is genuinely ambiguous.
- `25 rajinder nagar` → `25-K` (a real block inside Rajendra Nagar,
  ~1.4km from the locality anchor). The OSM-canonical spelling is
  "Rajendra Nagar"; a literal "Rajinder Nagar" exists only as post
  office/constituency rows. In-area, spelling-canonicalized — the
  classifier counts it wrong on substring, the row is honest.

## Wave 3 — live-path ranking fixes (post-deploy re-audit)

The wave-2 deployment (build c1d96295) surfaced a divergence: local
engine output was correct but the live `/v2/search` merge layer
re-sorted T1 rows by `(match_rank, -score, distance)` — destroying the
engine's deliberate ordering — and its `match_rank` tagger knew only
name-prefix matching (no aliases), so a literal-name platform
("AIIMS") always beat the alias-matched landmark (the hospital).

Fixes landed on the shared live index path:

- `v2/search.py` merge preserves engine position within a match class
  (`_t1_pos`), and the tagger skips rows the engine already classed.
- Engine propagates a resolved accessory's match class to the
  same-name landmark (`_demote_accessory`), so the hospital parks the
  "AIIMS" bays' literal-name rank instead of being re-inverted.
- `match_rank` compare fixed for the falsy-zero case (`cls == 0` is a
  real class — `cur or 99` silently erased rank-0 lifts).
- `_foreign_place(anchor, leftover)`: a house/unit row whose trailing
  alpha tokens resolve to a place lacking every distinctive anchor
  token is a different colony — flagged out of results at any
  distance. The unnamed-anchor fallback (locality top-1) is now
  deterministic rather than lat/lon-bias-fragile.
- Dedupe extended: spelling variants at ≤150m via bounded DL
  ('Lodi Gardens'/'Lodhi Gardens'), exact-name and city-suffix-prefix
  rows at ≤350m ('Lodi Gardens, Delhi').

Live re-audit — before → after (verified on the same merge path):

- `aiims` → was [platform, platform] → now **All India Institute of
  Medical Sciences** top-1; the two bays collapse to one demoted row.
- `lodhi garden` → was [platform, park, park] → now **Lodi Gardens**
  top-1, single park row (spelling/city-suffix dupes folded), the
  platform demoted below every park.
- `b-12 lajpat nagar` → was [B-12 Sanwal Nagar, B-12 Adarsh Nagar
  Extension, B-12 residential] → now **Lajpat Nagar** top-1; the
  foreign-colony rows are gone (a different neighbourhood is never an
  answer); only anonymous B-12 rows trail.
- `house 559 udyog vihar` → still **559 Udyog Vihar Phase V Road**.

Local battery after wave 3: **171/174 (98.3%)** — unchanged; p50
0.7ms, p95 65ms (cold-start first query ~1s).

Live battery vs the deployed build (174 queries over the NLB,
0.4s spacing): **172/174 = 98.9% top-1** — every resolved query was
top-1, zero top-3 fallbacks. Misses: `25 rajinder nagar` → `25-K`
(honest in-area block; substring-classified wrong), `panipat` → empty
(outside the declared 28.08–29.07°N service bbox — service-area
ceiling). `subhash nagr` → `Subhash Nagar` on live (typed spelling
wins; earlier local run had surfaced the `Subhashnagar` row).
HTTP latency from this box: p50 473ms p95 616ms — dominated by the
ap-south-1 round-trip; engine-side p50 is sub-ms.

Same-place row variants observed live (defensible classification, not
divergence — the merged local path produces identical rankings):
`iit delhi` → `IIT Delhi` station (literal exact-name) over the
institute campus row (alias-matched); `chattarpur` → the typed-spelling
row; `vegas mall dwarka` → `Vegas Mall Dwarka` over `Vegas Mall`.
Open judgment call: whether an exact-name *station* should keep its
literal-name class over an alias-matched landmark when no accessory
row exists (`station` is not in `_ACCESSORY_KINDS`).
