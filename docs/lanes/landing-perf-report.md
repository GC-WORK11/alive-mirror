# Lane report — landing speed + perceived-craft pass

**Date:** 2026-10-07 ~10:45–11:35 UTC. **Lane:** landing performance
(honest wins only — every change below carries its before/after number).
**Baseline:** prod `698cf808`, measured from this box (RTT floor to the
ap-south-1 NLB ≈ 470 ms — every row below pays it once minimum).

## What the measurement actually showed

The suggested targets didn't exist: **the landing ships no webfonts and
no pmtiles/maplibre** — it's one self-contained `landing.html` (system
type stacks, all JS/CSS inline). The real profile, per curl
(`--compressed`, TTFB/total in seconds):

| asset (first wave + deferred) | wire bytes | TTFB s | note |
|---|---:|---:|---|
| `/` landing.html | 37,797 gz | 0.475 | 114,108 B raw |
| **`/app-hero.png`** | **530,914** | 0.469 / 1.64 tot | **82% of the whole page** — the only image; shown at 236 CSS px |
| `/grid?cells=34&param=pm2_5` | 20,551 | 1.33 | the field map raster source |
| `/ncr.geojson` | 32,104 | 0.48 | district boundaries |
| `/delhi_subdistricts.geojson` | 8,956 | 0.47 | sub-district boundaries |
| `/v2/city` | 10,373 | 0.81 | **fetched twice at boot** (boot strip + hero numeral, ~700 ms of server rebuild per hit) |
| `/v2/districts` | 1,049 | 1.35 | (has its own 120 s cache; 1.3 s+ when it misses) |
| `/v2/day` | 2,378 | 0.49 | below-fold |
| `/v2/why` | 1,339 | 0.47 | below-fold |
| `/v2/skill` | 761 | **6.00** | a 6 s tail holding one of six HTTP/1.1 slots |
| **boot total** | **~616 KB** | | 11 requests at parse time over 6 connections |

What dominated, in order: the 531 KB PNG > the connection-starved
11-request boot wave (incl. the `/v2/skill` 6 s tail) > ~0.5–0.8 s of
server CPU rebuilt per `/v2/city` hit > the boot overlay's own minimum
time. There was also **no `Cache-Control` on anything** — a judge's
second load re-downloaded all of it.

## What changed (each with its number)

| change | before | after |
|---|---|---|
| **Hero shot** — `<picture>` WebP at real display densities (236 CSS px ⇒ 472 w/708 w), PNG moved to a right-sized fallback + preload starts the fetch during the HTML download | 530,914 B `/app-hero.png` fetched mid-page | **42,890 B** `app-hero-708.webp` (472 w: 26,436 B); fallback `app-hero-708.png` 255,181 B. **−92%** on the image, page total ~616 KB → ~128 KB wire |
| **Boot-wave shape** — below-the-fold feeds (`loadDistricts`, `tlInit`, `dayStrip`, `skillLine`, `whyTonight`) deferred to `requestIdleCallback` (timeouts 1.5 s/2 s); the first wave keeps its connections for the number + the map | 11 requests at parse time, incl. the 6 s `/v2/skill` tail blocking a slot | 6 requests at parse time; the rest at first idle. Proxy-verified: identical set, reordered |
| **Duplicate `/v2/city`** — `api()` now dedupes in-flight GETs (POSTs always fire; the promise is shared, not the body) | boot strip + `heroCity()` each fired → 2× ~0.8 s server rebuilds | **1 request** (confirmed in the verification proxy's log) |
| **`/v2/city` 60 s payload cache** — mirrors the existing `_DIST_CACHE` pattern: key = field key + station-layer signature + `TRIPS._rev` + forecast `_fetched_at`; donation/reset busts it via the new `_rev` counter; `cached_s` discloses the age (contracted, like `V2DistrictsResponse.cached_s`); UTC `today` re-derived per serve | every hit rebuilt lattice+why+corridors+forecast (~0.5–0.8 s server CPU) | local TestClient: cold 3,807 ms → **warm 1–3 ms**; donation → rebuild (key bust verified). Benefits the app's WelcomeScreen + DelhiToday too — they read the same endpoint |
| **Cache headers** — `public,max-age=300` on `/`,`/landing`; `public,max-age=3600` on the baked statics (both geojsons, all hero assets) | no `cache-control` anywhere; second load = full re-download | repeat visit inside the TTL = **0** requests for the page + statics |
| **Boot overlay timing** — number sweeps in over 380 ms (same count-in as the hero numeral, replaces the 500 ms pop-in); `pastMin` 750→550 ms; `bye` 2,350→1,900 ms (+400 ms fade, unchanged); first-interaction skip unchanged | overlay floor ≈ 750 ms, exits at 2,750 ms wall | floor ≈ 550 ms, exits at ≈ 2,300 ms wall; the `/v2/city` fetch races the overlay from t=0 and is shared with the hero numeral, so the real figure is usually already painting when the overlay clears |
| landing.html cost of the above | 114,108 B raw / 37,797 gz | 115,803 B raw (**+1,695 B**, ~+0.5 KB gz) |

Not done (deliberate): no content removal, no dead-CSS prune (page is
one hand-tuned stylesheet — grep shows rules are dense and used;
pruning risk > byte win), no lazy-load on the map raster (it IS the
above-fold payload). The original `app-hero.png` stays as the capture
source — derivatives regenerate from it.

## Verified

- `scripts/check_inline_scripts.py` — **OK** (4 blocks parse clean;
  the f9ea5ae trap avoided).
- `pytest tests/test_landing_serve.py tests/test_v2_hardening.py` +
  contract tests on `V2CityResponse` — **65 passed**. (Full suite
  1,161 pass / 4 fail on this box — all four are `alive_core` missing
  from `core/build312` here, unrelated to this diff: path-legality ×2,
  query-latency, and `test_no_uncontracted_server_fields` which now
  passes after contracting `cached_s`.)
- Cache semantics, local TestClient: cold miss → warm hits at 1–3 ms;
  `record_trip` bump to `_rev` → next call rebuilt (`cached_s: 0.0`).
- Render, both widths, via a local proxy serving the edited page over
  prod data: desktop 1440 px — live **42.3 µg/m³ SATISFACTORY**,
  equation strip, sparkline, statusline (52 stations · map 10 min
  fresh · usual 43 · wind 11 km/h · 903 k segments), field map +
  demo chip + timelapse deck, mech section with the WebP hero shot and
  its caption; mobile 390 px — hero, equation, sparkline, map, chips,
  deck all present. `/v2/city` requested **once** in the boot wave.
- New routes live-checked locally: `/app-hero-472.webp`,
  `/app-hero-708.webp` (`image/webp`, `max-age=3600`),
  `/app-hero-708.png`, plus `cache-control` on `/`, geojsons.

## Honest caveats

- Localhost-rendered numbers (3,807 → 1–3 ms cache) are this box's CPU;
  prod's warm hit should be ≈ the JSON size over the wire (~10 KB), but
  the deployed figure lands wherever the deploy lane puts it — the
  report claims the mechanism, verified, not a guessed ms.
- `/v2/skill`'s 6 s tail is server-side, not landing's; the deferral
  moves it off the critical path but doesn't fix its latency — flagged
  for whoever owns that endpoint.
- Prod `/health` at push time: still `698cf808` (deploy lane's roll not
  yet through — this push will ride whichever build next lands).
