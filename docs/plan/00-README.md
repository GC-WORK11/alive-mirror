# ALive-108 — Master Plan (v2, from scratch)

Written 2026-10-03. Replaces the build direction in docs/00–32 where they conflict; those docs stay as the research record. Everything in this folder is either **[V] verified** (we ran it / read the primary source this session), **[R] from our research docs** (cited there), or **[P] plan** (a decision, not a fact). Nothing here is a claim we can't defend.

## The product in one sentence
A Delhi map app that, for every trip, shows how much smoke you will breathe and how much your vehicle will put into the air — before you go, live while you travel, and as a receipt when you arrive — and turns everyone's trips, anonymously, into a live picture of what Delhi breathes and emits on its roads.

## Three pillars (owner's definition)
1. **Consumer app** — instant search for any place in Delhi, a detailed dark map, live navigation, a minimal plain-word UI, a real hamburger sidebar holding both ledgers (breathed + emitted).
2. **Backend** — a live air index of Delhi, refreshed all day; trip scoring for breath + emissions; a city dashboard that only ever holds city-wide totals and averages, nothing personal.
3. **Engine** — the hot math (search index, field sampling, dose + emission integration) in C++, with benchmarks; claims of speed only where measured.

## Files
| # | File | Owns |
|---|---|---|
| 01 | `01-mission-and-pitch.md` | Mission, the 4-line pitch, hackathon-requirement mapping, demo arc |
| 02 | `02-consumer-ux.md` | Every screen and flow, word-for-word copy rules, what we delete |
| 03 | `03-design-system.md` | Dark theme tokens, type, icons, motion, map styling |
| 04 | `04-map-search-navigation.md` | Map stack, 3-tier search, routing, live navigation engine |
| 05 | `05-backend-architecture.md` | Services, live air index pipeline, APIs, storage, AWS footprint |
| 06 | `06-science.md` | Dose model, emissions model, bands, ranking rule |
| 07 | `07-city-dashboard-and-privacy.md` | Consumer "Delhi today" view, admin dashboard, privacy design |
| 08 | `08-cpp-engine.md` | `alive_core` C++ module: scope, design, benchmark protocol |
| 09 | `09-build-sequence.md` | Phases, acceptance criteria, test plan, what ships when |
| 10 | `10-claims-ledger.md` | What we say, what we never say, the exact numbers we may quote |

## Decisions already made by the owner
- Both targets: **exposure and emissions** — every trip shows both.
- **Hamburger sidebar** (not avatar-in-pill) — redesigned, not removed.
- **Dark, detailed map** — Google-Pixel/Mobbin-grade, not the current flat style.
- **No personal data** collected centrally — only aggregates.
- **C++** for the engine.
- Coordinator works from a plan; no subagents for this planning phase.

## Open items only the owner can unblock
1. **Live station data key.** OpenAQ v3 returns 401 without a key [V]; our old key is dead. Either regenerate the OpenAQ key (explore.openaq.org → account) or register a data.gov.in key (for CPCB hourly). Without one, the live index runs on the CAMS model + the public OpenAQ S3 archive (hours old), and we must say so on screen.
2. **Event-date rule.** The rules say repo history must match Oct 8–11 and old projects are disqualified "even if you rewrote it" [R: memory of rules page, Oct 2]. Everything built before Oct 8 is at risk. The plan assumes the owner re-confirms the rule text and decides how to handle it; we do not hide history.
3. **Amazon Location spend.** Free-tier allowance is 500k map tiles, 10k suggest, 20k geocode, 10k routes per month for 3 months [V: aws.amazon.com/location/pricing]. Demo traffic fits; a public launch would not. Owner approves the spend cap.
