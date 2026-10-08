# RFC: light the dark source legs — OpenAQ corroboration + direct CPCB

Status: build-ready, not built. Researched 2026-10-08. Everything here
is free (zero budget constraint holds) — the only costs are a signup
and, for CPCB, one egress trick.

## RFC-1 — OpenAQ v3 as the corroboration leg *(zero code, key only)*

**What it buys.** An independent second read of the same CPCB/DPCC
instruments — OpenAQ re-ingested India's entire CPCB reference network
in 2025 (their own year-in-data post). With a valid key, the chain
WAQI → CPCB → OpenAQ gains a real third leg instead of a dark one, and
loser legs stop being dead weight: each leg's status already surfaces
(`waqi_status/cpcb_status/openaq_status`, `airindex.py:669-738`).

**The API (v3, verified against docs.openaq.org 2026-10-08):**

- Auth: `X-API-Key` header. Free key via `explore.openaq.org` signup.
- Free tier: **60 req/min, 2,000 req/hr** — plenty: our NCR pull is
  ~50 locations × 1 call each 15 min ≈ 3 calls/min.
- Discovery: `GET /v3/locations?bbox=76.75,28.15,77.95,28.98&parameters_id=2&limit=1000`
  (already implemented, `airindex.py:585-620`).
- Latest values: `GET /v3/locations/{locations_id}/latest`
  (already implemented, `airindex.py:620-666`).
- Freshness on the wire: each latest record carries its own
  `datetime` — this leg *also* fixes the per-station-age disclosure
  gap named in `data-truth.md`.

**Change cost:** put a real key in Secrets Manager `alive108/openaq`
(`scripts/deploy.sh` already injects `OPENAQ_API_KEY`), then
`force-new-deployment`. Zero lines of code — the adapter is live and
tested (`test_station_chain.py`, `test_ingest_openaq` paths exist);
`REPLACE_ME`-class placeholders already degrade to `skipped: no key`
rather than burning a doomed call.

**Failure modes:** revoked/401 → chain logs `unavailable: 401` and the
WAQI leg still wins; OpenAQ lag (it republishes, so ~15–60 min behind
the regulator feed is normal) → its readings age out of QC, no harm;
rate-limit → calls are well under the free ceiling.

## RFC-2 — direct CPCB (`api.data.gov.in`) via an India-reachable egress

**What it buys.** The first-party regulator feed, named stations and
official `last_update` stamps per row — the strongest possible answer
to "are you using CPCB?"

**The API (resource `3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69`, "Real time
Air Quality Index", catalog updated 25/09/2026):**

- `GET https://api.data.gov.in/resource/3b01bcb8-…?api-key=$CPCB_API_KEY&format=json&filters[state]=Delhi&filters[pollutant_id]=PM2.5&limit=1000&offset=0`
  — paged per state (`STATES = Delhi, Haryana, Uttar_Pradesh,
  Rajasthan`, `ingest_cpcb.py:63`).
- Auth: free `api-key` from the resource page's "Generate API Key"
  (MyGov SSO), `docs/plan/cpcb-source.md` §3.
- Shape: `records[]` {country, state, city, station, last_update
  (IST, `DD-MM-YYYY HH:mm:ss`), pollutant_*, avg_value, series[min,
  avg, max]}. **No coordinates** — joined to our 125-station registry
  (`data/delhi_climatology.json.gz`) by normalized name; unresolved
  names are skipped and counted, never placed by guessing.
- Cadence: rows carry a per-station `last_update`; ~hourly upstream.

**The blocker (measured, not assumed):** `api.data.gov.in` returns
**TCP connection refused** — from this dev box *and* from a Fargate
probe in the prod VPC's own subnets, ap-south-1 (2026-10-04,
`docs/plan/cpcb-source.md`). So the key is not the whole fix; NIC
appears to drop AWS address space. Options, cheapest first:

1. **Free egress relay** — a Cloudflare Worker / free-tier function
   (`wrangler` deploy, 100k req/day free) that proxies exactly one
   upstream `api.data.gov.in` and adds nothing else. CF anycast
   egresses from the requesting colo; an India-routed request leaves
   from an Indian IP, which is the whole point. CPCB adapter then
   reads `CPCB_API_BASE` (already overridable, `ingest_cpcb.py:52`).
   Risk: NIC may filter CF too — test costs 10 minutes and $0.
2. **Wait-and-key** — if the refusal is reputation-based and rotates,
   the adapter already works the moment a route exists; keep the key
   staged so a green path lights up with zero code.
3. **Don't bother** — WAQI republishes the *same* CAAQMS instruments
   within minutes; CPCB-direct adds a first-party `last_update` stamp
   but not new physics. Honest answer to judges: we already read the
   regulator's instruments; the direct pipe is provenance, not data.

**Failure modes:** registry misses (station renamed) → `skipped.
unresolved_names` counted, never guessed; partial pages → one state's
failure doesn't sink others; 24 h `series` window → flatline QC only
partially applies from a single snapshot (stated in adapter doc).

## What stays dark on purpose

`airquality.cpcb.gov.in/ccr`'s dashboard JSON (`service.php`, RC4 +
SHA512 private contract) — reachable but a private API; scraping it
is the kind of thing that looks fine until it's abuse. Documented and
rejected in `docs/plan/cpcb-source.md` §4.

## Recommendation

Do RFC-1 (a signup away, zero code) whenever a real OpenAQ key exists.
Do RFC-2 option 1 only if judges press "why not CPCB directly" —
the truthful answer is already on the wire either way.
