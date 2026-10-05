# vision vs live — a brutal audit

*Compiled from every owner prompt across all ALive-108 sessions, tail to head
(~25 sessions mined, 2026-10-01 → 2026-10-04). Each statement → honest status
against the live deploy (`e849bf6f`, verified 2026-10-04).*

## the vision, refined into one paragraph

Delhi commuters shouldn't have to guess what a trip costs their lungs. Type
from and to: in milliseconds a C++ engine searches NCR's ~1.07M priced road
edges — each edge re-priced off the live pollution field (24 WAQI instruments
→ EPA inversion → Kalman → CAMS blend → de-bias → krige) — and returns the
route your lungs pay least for, with an honest uncertainty band. Two faces:
a personal app (Android release, iOS demo) that feels organic, minimal, never
cringe — and a global admin/public surface showing Delhi's aggregate breath:
how the city moves, what it inhales, what it emits — with zero personal data.

## the audit — statement → status

| # | owner's ask (verbatim essence) | status | honest gap |
|---|---|---|---|
| 1 | real-time route-wise aqi/pm2.5 per trip | **live** — every plan option carries dose.mid computed leg-by-leg off the field | — |
| 2 | "maps ditto google maps", light theme | **partial** — MapLibre light theme, live field tint, field+nav layers; POI richness below Google's vector set. Asymptotic goal, honestly ~80% | POI density, 3D buildings absent |
| 3 | Android is the release; iOS = demo | **live** — release APK built & verified on emulator (14/14 surfaces); iOS sim demo recorded (sheet crash proven sim-only GPU kill, zero .ips) | physical-device run is owner-side |
| 4 | exposure AND emission (theme is both) | **live** — dose (exposure) + co₂ trip/corridor split moving/idling/cold-start | — |
| 5 | "google maps fetch my street to my home in ms — millions of houses" | **live** — 124,311-row gazetteer inlined in APK, 172/174 top-1 (98.9%), p50 ~1ms engine | panipat-class outside-coverage = honest ceiling |
| 6 | no hardcoded locations | **live** — zero hardcoded ODs; gazetteer+reverse everywhere | — |
| 7 | decision engine, not hardcoded, milliseconds, "not fastest but safest" | **live** — C++ A* priced objective = displayed integrand; fast paint 77–258ms; engine solve ms-scale | full 15-option plan = 0.8–6.9s (seconds, not ms — engine is ms, pipeline is s) |
| 8 | cigarettes data ok but not default/cringe | **live** — equivalent exists behind Settings toggle, OFF by default | — |
| 9 | "act like me" — every button, scroll, end-to-end | **live** — 14-surface E2E sweep PASS on emulator vs live API; admin browsed every section by eye | — |
| 10 | no dummy code/data/fake numbers | **live** — honest-empty everywhere; banned-key guards; suppressed k<3 never faked | — |
| 11 | $0 infra this month | **live** — free-tier data sources, self-hosted stack, Fargate spot | spot→on-demand switch = owner demo-morning call |
| 12 | recorded product demo | **live** — iOS 4min clean take, admin walkthrough, Android e2e_demo.mp4 (3:19) | final ≤3min hackathon cut = owner's edit |
| 13 | admin = global aggregates only, no profiles | **live** — k≥3 enforced, hashed tokens in k-sets, AGGREGATES ONLY badge | — |
| 14 | users-by-area, journeys per OD, emissions saved | **live** — tiles exist; dose_avoided 99.2µg flowing; areas/OD suppressed honestly until k≥3 | small donation base — tiles sparse by design |
| 15 | "their reviews" | **live** — POST /v2/feedback (stars+≤240 note, NO token/device stored) → Settings row → admin tile. **iOS-sim verified e2e on live API**: tap row → stars → note → send → "thanks — that helps" → server count 2, avg 4.0, hist matches taps. Bodies publish only at k≥3 | — |
| 16 | remove "a breath, today" | **live** — removed | — |
| 17 | Delhi internal districts + NCR (Ghaziabad, Gurgaon) | **live** — 28 tiles: 15 NCR + 13 Delhi sub-areas (OSM has no 14th+ sub-area boundary — real, not faked) | — |
| 18 | field cell click → locality name | **live** — verified: "near NH9 trunk", "DGD Bhorgarh clinic"; 150m honest 404 | — |
| 19 | thousands of tiles + indexing | **live** — 1,600 cells (API max), sectors a01–an40 + degree ticks | "thousands" satisfied at 1,600 real cells; more = client-side subdivide (fake resolution) — rejected |
| 20 | hover → mini organic card with data | **live** — verified: sector ref, coords, district, conf, gazetteer name | — |
| 21 | methodology per metric, area-wise counting | **live** — "how this layer is made": real derivation chain + live counts; districts = mean-of-cells captioned | — |
| 22 | keep district/state UI | **live** — untouched | — |
| 23 | real admin: merged data that doesn't exist anywhere | **live** — corridor×field `air pm2.5` join; pipeline/source-health blocks; archive-replay MAE | — |
| 24 | optimised and fastly | **live** — epoch-keyed grid cache + boot warmer (first 40×40 call per epoch ~1.5s not ~7s), skip-identical-repaint | — |
| 25 | Android: icons not cheap, milky morphism, distributed sidebar | **live** — Material Symbols Rounded, glass token ramp, JourneyDrawer rework; **Pixel_7 verify PASS all surfaces** (icons/milk/drawer/regressions); its 2 flags fixed same-day: emit_kg write (put-out-kg tile had readers, no writer) + stacked-sheet ghost-bleed (tile 0.62→0.84, pane→0.90) | perf vs llvmpipe inconclusive (no hardware GL on box) — physical phone is the real measure |
| 26 | uncrashable | **mostly live** — Android E2E no crashes; iOS sim crash = sim-only GPU (documented, no .ips) | physical Android soak = owner |
| 27 | terminate my lanes except pocket-rig | **done** — all ALive-108 lanes except live ones ended; Pocket Rig untouched | — |
| 28 | loop for days/12h, don't stop | **in progress** — this audit + landing + continued loop | — |
| 29 | marketing landing page, 4-ref genre (supaste/devin/iphone/godly) | **live** — `/` + `/landing` cream-paper serif+italic, no SaaS chrome; verified on prod | — |
| 30 | "ASCII aether shaders animation… not a cheap template… amaze me" | **live** — real 40×40 field as shader lattice; trace births routes from cells rotating 3 ODs; wind-drift on real /health wind; a01–an40 indexing + hottest tag; locality hover card; pull-quote; footer live stamps; dose card+trace share one fetch | landing.html has no pytest coverage — browser-verified only, by design |

## open honest gaps (not faked, ranked by demo impact)

1. ~~Self-hosted OSRM daemon never deployed~~ **RESOLVED 2026-10-04** —
   `alive108-osrm` sidecar in the Fargate task (shared netns, mem cap 1024,
   task 2048→3072); `router_backend: osrm-local` verified live on a real
   31.1km CP→Gurugram /directions call. Public demo is flagged fallback only.
   Runbook: docs/plan/osrm-selfhosted.md.
2. **Full-plan latency is seconds** — engine solve is ms; the 15-option
   pipeline is 0.8–6.9s. Demo script should show fast-paint (ms) first.
3. **users-by-area sparse** — real k≥3 math; needs real devices over days.
4. **iOS-only sim artifacts** — documented; physical Android is the demo.
5. ~~Release APK predates HEAD~~ **RESOLVED 2026-10-04** — fresh
   release APK built on the polish-lane HEAD and delivered
   (emit_kg + review-row + milky morphism all in).

## the one-line pitch (for the landing page)

> *Delhi's air has a price per street. We price it live —
> and route you down the one your lungs pay least for.*
