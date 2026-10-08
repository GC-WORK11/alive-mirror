# Search & Map UX — how "instant" actually works, and the cheapest path to it for Alive

*Deep-research brief. Every claim is cited; recommendations are grounded in the current Alive code (`Mobile/App.tsx`, `server/main.py`).*

---

## 0. Why our search feels broken today — the diagnosis in one paragraph

Today the request path is: **phone → NLB (ap-south-1, Mumbai) → ECS Fargate → `photon.komoot.io` (komoot's free demo server, hosted in Europe) → all the way back**. That is a transcontinental double-hop for every keystroke, terminating at a shared demo instance that explicitly offers no SLA: *"You are welcome to use the API for your project as long as the number of requests stay in a reasonable limit. Extensive usage will be throttled or completely banned. We do not give guarantees for availability."* ([Photon README](https://github.com/komoot/photon)). On top of that:

- **The `bbox` parameter we pass is a hard filter, not a bias.** Photon docs: *"The bbox parameter restricts results to the given area."* ([api-v1.md](https://github.com/komoot/photon/blob/master/docs/api-v1.md)). `server/main.py` sends `bbox=NCR_BBOX` on every query — so nothing outside NCR can ever be returned, and inside-NCR matches with weak relevance still win by default.
- **The client has no timeout and no abort.** `fetch()` in `App.tsx` has no `AbortController` and no deadline; a stalled socket can leave `searching=true` spinning indefinitely. The 180 ms debounce is fine; the in-flight request is the problem. ([App.tsx doSearch](../Mobile/App.tsx))
- **The reverse endpoint returns whatever single OSM feature is nearest** (`/reverse?limit=1`), with no distance sanity check — the nearest named thing to a GPS point can be a random POI/house rather than the street the user expects.

Everything below is organized as: (a) how the instant feel is actually built, (b) the concrete stack recommendation, (c) reverse-geocode correctness checklist, (d) minimal map style options, (e) on-device RN performance checklist.

---

## (a) Instant-search architecture — reference design + latency budgets

### The perceptual budget

Jakob Nielsen's response-time limits are the canonical budget for "instant": **0.1 s** is the limit where the system feels instantaneous; **1 s** keeps the user's flow of thought; past ~2–3 s users feel they're waiting on the computer ([NN/g, *Response Times: The 3 Important Limits*](https://www.nngroup.com/articles/response-times-3-important-limits/)). Google Maps' autocomplete feels instant because the whole pipeline — debounce, transport, query, render — is engineered to land inside ~100–150 ms p50, and because a large fraction of queries are answered **without a network call at all**.

### What the production systems actually do

**Predictions before typing.** The biggest "speed" win isn't making the API fast — it's not calling it. Uber's destination **predictions account for ~50% of destinations entered** ([Uber, *The Uber Engineering Tech Stack, Part I*](https://www.uber.com/kw/en/blog/tech-stack-part-one-foundation/)). Lyft predicts a rider's destination **60–70% of the time**, restricting candidates to previous ride origins/destinations filtered by physical proximity, then ranking with an attention model ([Lyft Engineering, *How Lyft predicts your destination*](https://eng.lyft.com/how-lyft-predicts-your-destination-with-attention-791146b0a439); [Lyft blog](https://www.lyft.com/blog/posts/how-lyft-uses-ai-to-get-you-where-you-want-to-go-faster)). Both show history/predicted places instantly under an empty search box — zero latency, zero cost.

**Per-keystroke requests, bundled as a session.** Google's Place Autocomplete expects a request per keystroke (debounced ~100–300 ms), wrapped in a **session token** (a UUIDv4) that groups all keystrokes + the final Place Details call into one billable session ([Google Places docs — session tokens](https://developers.google.com/maps/documentation/places/web-service/place-session-tokens); [Autocomplete & session pricing](https://developers.google.com/maps/documentation/places/web-service/session-pricing)). Session tokens are a billing construct for Google, but the pattern matters: **each "search" is a session — a sequence of refinements ending in a selection** — not an isolated query. The client should carry a session id so stale responses are dropped and (if desired) results can be merged/cached per session.

**Locally-biased autocomplete engine close to the user.** Uber describes its autocomplete engine as *"high-speed, locally-biased location search"* ([Uber tech stack](https://www.uber.com/kw/en/blog/tech-stack-part-one-foundation/)). Google Maps' Suggest *"you get the most useful suggestions depending on where you're zoomed into on the map"* ([Google Lat Long blog, 2010](https://maps.googleblog.com/2010/04/google-maps-search-box-just-got-smarter.html)). Both bias ranking by viewport/GPS rather than globally — the same soft-bias knob every OSS geocoder exposes (Photon `lat`/`lon`/`zoom`/`location_bias_scale`; Pelias `focus.point.*`).

**Index internals.** Autocomplete at this scale is an indexing problem, not a string problem: Lucene/Elasticsearch-family stores (Photon → OpenSearch, Pelias → Elasticsearch, Uber's Sia) serve per-keystroke queries in tens of ms via prefix/edge-ngram indexes and completion structures. The four standard techniques are prefix matching, edge-ngram matching, search-as-you-type fields, and completion suggesters ([OpenSearch autocomplete docs](https://docs.opensearch.org/latest/search-plugins/searching-data/autocomplete/)); Pelias originally used Elasticsearch **FST-based completion suggesters** for autocomplete before moving to phrase analysis ([Geocode Earth, *A trip down Memory Lane*](https://geocode.earth/blog/2020/memory-lane/)). Uber eventually replaced Elasticsearch for hot workloads with **Sia**, a custom Lucene-based engine with a memory-resident *Live Index* for real-time queries — but notably concluded most use-cases are fine with Lucene's near-real-time semantics ([Uber, *The Evolution of Uber's Search Platform*](https://www.uber.com/ca/en/blog/evolution-of-ubers-search-platform/)). Spatial sharding for geo workloads is typically a global grid index — Google's S2 and Uber's H3 hex-grid are the standard references ([H3](https://h3geo.org/)).

**The typeahead UX contract.** Pelias' docs capture the industry-standard interaction pattern: fire `autocomplete` on key presses **(throttling appropriately)** and fire a full `search` only on Enter/submit — autocomplete trades accuracy for speed on partial input ([Pelias autocomplete docs](https://github.com/pelias/documentation/blob/master/autocomplete.md)).

### Reference design (what "instant" is composed of)

```
┌─ keystroke ───────────────────────────────────────────────────────────┐
│ 0 ms   show skeleton rows + recents/predictions (local, no network)   │
│ ~120 ms debounce fires → abort previous in-flight request             │
│ 1st    consult on-device index (recents DB / bundled gazetteer) →     │
│        render immediately if confident                                 │
│ async  fetch same-region geocoder (target <150 ms total RTT+query)    │
│        seq-guard: drop stale responses; cache by normalized query      │
│        merge + render (≤60 ms JS work)                                 │
│ enter  full search (not autocomplete) → camera + confirm               │
└────────────────────────────────────────────────────────────────────────┘
```

**Latency budget for a same-region deployment (target p50 ≈ 120–180 ms):**

| Stage | Budget | Today |
|---|---|---|
| Debounce | 120–180 ms | 180 ms |
| Phone→server RTT (same region, keep-alive TLS) | 30–60 ms | ~50 ms to Mumbai + ~180–250 ms to Europe |
| Geocoder query | 10–40 ms (local index) | 10–40 ms at komoot + shared-tenant variance/throttle |
| Render | ≤16 ms (skeleton immediately) | synchronous list re-render per keystroke |
| **Total** | **~180–300 ms** | **~500 ms–8 s, sometimes never returns** |

The single highest-leverage change is **collapsing the Europe hop**: host the geocoder in ap-south-1 next to the FastAPI service, or move autocomplete fully on-device.

---

## (b) Recommended stack for Delhi-first instant autocomplete

### Hard constraints discovered (do not skip)

- **Hosted Nominatim is off-limits for autocomplete** — the OSMF usage policy states: *"Auto-complete search: This is not yet supported by Nominatim and you must not implement such a service on the client side using the API"* ([Nominatim Usage Policy](https://operations.osmfoundation.org/policies/nominatim/)). Also semantically wrong: Nominatim answers exact names ("Ber" → Ber, Mali), not completions ([GIS.SE](https://gis.stackexchange.com/questions/120570/)).
- **`photon.komoot.io` is a demo server**, not a dependency — throttled/banned at scale, no SLA ([Photon README](https://github.com/komoot/photon)).
- **Valhalla's `loki` is not a gazetteer** — it correlates a lat/lon to routing-graph edges (route snapping), not place-name search ([Valhalla loki docs](https://valhalla.github.io/valhalla/loki/)). Keep it out of the search shortlist.
- **`bbox` in Photon = hard filter.** To allow results *outside* Delhi NCR, drop `bbox` and use `lat`/`lon` + `zoom` + `location_bias_scale` as the soft Delhi-first bias ([Photon api-v1.md](https://github.com/komoot/photon/blob/master/docs/api-v1.md)); `countrycode=IN` still scopes to all of India.

### Option A — self-hosted Photon, India extract, same region (recommended)

GraphHopper publishes **per-country ready-to-run Photon DB dumps**. The **India database is ~575 MB compressed** (v1.0) / ~236 MB JSONL — weekly updated ([Photon downloads — india](https://download1.graphhopper.com/public/asia/india/index.html)). Unpacked it is a few GB of OpenSearch index — trivially runnable next to the existing FastAPI task or as a second container on the same Fargate service, or a small EC2/EBS host. Planet dumps exist too (~62 GB, 64 GB RAM recommended — unnecessary) ([Photon README](https://github.com/komoot/photon); [planet index](https://download1.graphhopper.com/public/index.html)). Source data is Geofabrik's `india-latest.osm.pbf` (~1.6 GB) if a custom rebuild is ever needed ([Geofabrik India](https://download.geofabrik.de/asia/india.html)).

Why this is the cheapest path to "instant":

- Same-region hop: phone → Mumbai → localhost/OpenSearch. Server-side Photon query is typically 10–40 ms; the API contract stays *identical* to today (GeoJSON), so `server/main.py` becomes a one-line URL change plus dropping `bbox`.
- Full control of Delhi-first ranking: `lat=28.6139&lon=77.2090&zoom=12&location_bias_scale≈0.3–0.5`, `lang=en`, `limit=8`, `dedupe` on by default ([Photon api-v1.md](https://github.com/komoot/photon/blob/master/docs/api-v1.md)).
- Cost ≈ $0 marginal on existing infra (Fargate vCPU/RAM bump or a t3.small-ish host; EBS for a few GB index).
- Caveat to flag: OSM address/POI coverage in Delhi is thinner than HERE/Google data — good for areas, roads, metros, landmarks; weaker for door-level addresses. Acceptable for FROM→TO flows where areas/stops dominate; see Option B for the data-quality upgrade.

### Option B — Amazon Location Service Places (`Suggest`) in ap-south-1 (strong second; zero ops, judges' AWS points)

Amazon Location **Places** runs in ap-south-1 (`places.geo.ap-south-1.api.aws` — [AWS endpoints doc](https://docs.aws.amazon.com/general/latest/gr/location.html)). `Suggest` is the autocomplete API: returns `Query` refinements and `Place` results; `BiasPosition`/`FilterCircle`/`FilterBoundingBox` give the Delhi-first bias without hard-excluding outside-NCR results ([Suggest guide](https://docs.aws.amazon.com/location/latest/developerguide/suggest.html); [API reference](https://docs.aws.amazon.com/location/latest/APIReference/API_geoplaces_Suggest.html)). Pricing is bucketed: **`Label` ≈ $0.10/1K requests** (Title + PlaceId only — then one `GetPlace` at Core price for coordinates) or **`Core` ≈ $0.20/1K** which returns full address components + position directly ([Places pricing model](https://docs.aws.amazon.com/location/latest/developerguide/places-pricing.html); [AWS Builder Center pricing example](https://builder.aws.com/content/3CLjvOk8OPPeuW24EJTBIqEOpKc/)). Free tier for new accounts: 10K Suggest/Autocomplete (Label) + 20K Core requests/mo for the first 3 months ([AWS Location pricing](https://aws.amazon.com/location/pricing/)). Data comes from HERE/Esri-grade providers — materially better Indian address coverage than OSM, and it's the same provider family Lyft uses for destination search ([HERE/Lyft press release](https://www.here.com/about/press-releases/lyft-and-here-technologies-partner-to-improve-the-rideshare-experience/)). For a hackathon scored on AWS usage this also strengthens the submission. Trade-off: per-request cost at scale, provider lock-in, and results can't be permanently stored below the Stored-price bucket.

### Option C — paid search APIs (reality check)

- **Mapbox Search Box**: session-billed — 1 session = up to 50 `/suggest` + 1 `/retrieve`; **free 2,500 sessions/mo, then ~$11.50/1K sessions** ([Mapbox pricing](https://www.mapbox.com/pricing); [Search Box overview](https://www.mapbox.com/search-box)). Fine for a demo, expensive past a few thousand users, and it's per-keystroke-session billing.
- **Mapbox Geocoding API** (no POIs in v6): **100K free/mo then ~$0.75/1K** temporary; permanent costs more ([Mapbox Geocoding](https://www.mapbox.com/geocoding); [Geocoding v6 docs](https://docs.mapbox.com/api/search/geocoding)).
- **Google Places Autocomplete (New)**: session-token billing ([docs](https://developers.google.com/maps/documentation/places/web-service/session-pricing)) — best data and best latency reputation, but non-trivial cost per session and off-brand for an AWS-scored hackathon.

### Option D — heavier open alternatives (documented, not recommended for the timeline)

- **Pelias** is the most complete open autocomplete geocoder (explicit `/v1/autocomplete`, `focus.point.*` bias, `boundary.*` filters, confidence scores, libpostal address parsing — [services.md](https://github.com/pelias/documentation/blob/master/services.md), [autocomplete.md](https://github.com/pelias/documentation/blob/master/autocomplete.md)) but it's a multi-service Elasticsearch stack: ≥8 GB RAM minimum, metro-area builds ~1 h, planet 600M+ docs ([pelias/docker](https://github.com/pelias/docker); [full-planet considerations](https://github.com/pelias/documentation/blob/master/full_planet_considerations.md)). A Delhi-only Pelias build is feasible but costs more ops than Photon's single-jar + single-dump.
- **Custom gazetteer**: build a name→place index yourself. Source data options: OSMNames' pre-built gazetteer (~21M places planet, ~1.34 GB TSV.gz, with importance ranks + bboxes — filter to India rows) ([OSMNames](https://osmnames.org/); [repo](https://github.com/OSMNames/OSMNames)); or an `osmium` extract of the NCR bbox from `india-latest.osm.pbf` ([Geofabrik](https://download.geofabrik.de/asia/india.html)). Index it in **Meilisearch** — first-class geosearch via `_geo` + `_geoRadius(lat,lng,m)` + `_geoDistance` sorting, single binary, ms-level latencies ([Meilisearch geosearch docs](https://www.meilisearch.com/docs/capabilities/geo_search/getting_started)) — or in SQLite FTS5 (below). This path is the best long-term cost/latency play if OSM coverage suffices; it needs ~a day of ETL.

### The latency killer feature — an on-device gazetteer

The only way to beat network latency entirely is no network. Two practical implementations:

1. **Bundled SQLite FTS5 gazetteer.** `expo-sqlite` ships FTS3/4/5 and R*Tree compiled on both platforms (`enableFTS` defaults `true`) ([Expo SQLite docs](https://docs.expo.dev/versions/latest/sdk/sqlite); [PR #27738](https://github.com/expo/expo/pull/27738)). An NCR-scoped index (name/aliases/type/lat/lon + FTS5 prefix index + R*Tree for distance) built from OSM/photon-dump data lands in the tens-of-MB range — instant per-keystroke results offline, with the network path as fallback for outside-NCR or misses.
2. **Recents + predictions cache.** Store the user's last N picks and frequent routes locally; show them under the empty/short query (Uber-style predictions ≈ half of entries). This is what makes Google/Uber feel instant *even on 4G*.

### Decision table

| Option | p50 latency (est.) | Delhi-first control | Data quality (Delhi) | Cost at hackathon scale | Ops burden |
|---|---|---|---|---|---|
| Today: proxy to photon.komoot.io | 500 ms–8 s (sometimes ∞) | bbox hard-filter only | OSM, uneven | $0 | none (but unreliable) |
| **A: Photon India in ap-south-1** | **~80–200 ms** | full (bias params) | OSM | ~$0–15/mo host | low (1 jar + 575 MB dump) |
| **B: AWS Location Suggest (ap-south-1)** | **~60–150 ms** | BiasPosition/Filter | HERE/Esri (better) | $0 in free tier; $0.10–0.20/1K after | none |
| C: Mapbox Search Box | ~150–250 ms | proximity bias | good | $11.50/1K sessions past 2.5K | none |
| D: Pelias (Delhi build) | ~40–150 ms | full | OSM+WOF | ~$30–60/mo host | medium-high |
| D: Meilisearch custom gazetteer | ~20–100 ms | full | OSM | ~$5–15/mo host | medium (ETL) |
| On-device sqlite FTS + recents | **<30 ms** | absolute | OSM | $0 | medium (pipeline) |

**Recommended order of work:** (1) Option A — drop `bbox`, point `PHOTON` at a same-region India dump; (2) add abort/timeout/cache/recents on-device (§e); (3) if OSM coverage disappoints in Delhi POIs, layer Option B (AWS Location `Suggest`, Core bucket) as the fallback/geocoder-of-record for address queries — also a clean AWS-usage story; (4) optionally bundle the sqlite FTS NCR gazetteer for sub-30 ms feel and offline demos.

---

## (c) Reverse-geocoding correctness checklist — fixing "wrong/random location"

**Why it happens.** A reverse query returns the *nearest indexed feature*, not "the place the user means." With `limit=1` you get whatever OSM object is closest to the coordinate — a shop, a house, a POI — which reads as "a random location" when the user expected the street/area. Additional error sources: GPS accuracy radius (tens of meters indoors), POIs snapped to a centroid vs. the street, hamlet/district features returned when no address exists nearby, and — in our forward search — `bbox` hard-filtering making the *nearest in-bbox* match win over a better-named out-of-bbox one.

**Checklist (apply in order):**

1. **Cap the snap radius and surface distance.** Photon `/reverse` takes `radius` (km, 0–5000) and `limit` ([api-v1.md](https://github.com/komoot/photon/blob/master/docs/api-v1.md)). Query with a small radius (e.g. 0.1–0.5 km for a pin drop / GPS fix), `limit=5`, and read the `distance` on each result — if the nearest feature is >~150–250 m away, say "near X" instead of naming X.
2. **Prefer the right layer for the context.** Photon accepts `layer=` filters (`house`, `street`, `locality`, `district`, `city`, …) ([api-v1.md](https://github.com/komoot/photon/blob/master/docs/api-v1.md)); for a "your location" chip prefer street/address features over POIs; for a dropped pin prefer address/street.
3. **Match result granularity to map zoom.** Nominatim's canonical zoom↔detail table: 13=village/suburb, 14=neighbourhood, 16=major streets, 18=building ([Nominatim reverse docs](https://nominatim.org/release-docs/latest/api/Reverse/)). A country-level result at z18 is a red flag; gate "precise" labels on an appropriate layer/zoom.
4. **Two-stage bias for forward search.** Google Maps biases suggestions by the visible viewport ([Google Lat Long](https://maps.googleblog.com/2010/04/google-maps-search-box-just-got-smarter.html)). Do the same: pass current map-center (not just DELHI_CENTER) as `lat/lon` + `zoom`, keep `countrycode=IN` for scope. Strict-bbox first, then widen only if the strict query returns nothing — never silently return a weak far-away match.
5. **Confidence threshold + disambiguation.** If the top result's kind/distance doesn't fit the context, show 2–3 candidates ("did you mean…") instead of auto-picking; Pelias ships `confidence` scores for exactly this ([Pelias](https://github.com/pelias/pelias)). Never auto-flyTo on a low-confidence match.
6. **GPS-vs-text precedence.** If the user typed text, text wins (never override with GPS). If they tapped the ⌖ locate chip, use `getCurrentPositionAsync` → reverse at address layer; show the returned name *with its distance* and let the user correct it. Uber's reverse geocoder similarly augments GPS with trip-history-derived pickup spots ([Uber tech stack](https://www.uber.com/kw/en/blog/tech-stack-part-one-foundation/)).
7. **Reject stale responses, always.** Keep the existing `searchSeq` guard (it already prevents out-of-order overwrites — `App.tsx`) and pair it with `AbortController` so superseded requests actually stop ([RN `fetch` supports AbortController](https://reactnative.dev/docs/network)); abandoned in-flight requests are wasted radio and can still resolve.
8. **Log mismatches.** Record query→pick coordinates; a repeated far-jump pattern (e.g. consistent snapping to a sibling locality) is a data problem to fix in the gazetteer, not a UI problem.

---

## (d) Minimal monochrome map styles (Google-Pixel-like B/W cartography)

The Pixel/GM minimal look ≈ light gray/white land, hairline roads, restrained labels, near-zero color, POI declutter — that is exactly the **Positron** aesthetic.

- **OpenFreeMap Positron — zero work, zero cost.** We already load `https://tiles.openfreemap.org/styles/liberty`; switching `STYLE_URL` to **`https://tiles.openfreemap.org/styles/positron`** gets the B/W minimal basemap on the same free, keyless, commercial-use-allowed infra ([OpenFreeMap](https://openfreemap.org/); [quick start](https://openfreemap.org/quick_start/)). The Positron fork in `openfreemap-styles` is specifically tuned for the clean look: *"Positron, as a special clean looking style, has POIs removed and some highway labels set to show at higher zooms only"* ([hyperknot/openfreemap-styles](https://github.com/hyperknot/openfreemap-styles/)). OpenFreeMap is donation-funded with **no SLA** — fine for demo, worth a self-host/backup style for production.
- **Custom style JSON (recommended for "down to the last streets").** Take the Positron JSON, open it in **Maputnik** ([openfreemap quick start points there](https://openfreemap.org/quick_start/)), and (a) ensure `transport_name`/`highway-name-*` symbol layers' `minzoom` stays ≤16–17 so street names remain at z18+; (b) thin/darken `highway-*` line widths for the hairline look; (c) kill remaining POI symbols; (d) bump `text-halo-width`/`text-halo-color` for label legibility over the dose overlay. Host the JSON in the app bundle (or behind the NLB) — zero extra tile cost, full control. The schema is unmodified OpenMapTiles.
- **CARTO Positron (vector)** — the original minimal light style: `https://basemaps.cartocdn.com/gl/positron-gl-style/style.json?key=…`. As of the 2026-09 terms it needs a **free API key**; free up to 5M requests/mo non-commercial (1M commercial), attribution required ([CARTO basemaps](https://carto.com/basemaps/); [API key](https://carto.com/basemaps/apikey/)). Also ships `positron-nolabels` and `dark-matter` (for a Pixel-dark look).
- **Protomaps light flavor** — a clean minimal vector basemap distributable as a **single PMTiles file**; you can `pmtiles extract --bbox` a Delhi-NCR-only archive (tiny) and **bundle it inside the app** for instant/offline basemap tiles, with the hosted CDN as fallback ([Protomaps flavors](https://docs.protomaps.com/basemaps/flavors); [downloads](https://docs.protomaps.com/basemaps/downloads); [about](https://protomaps.com/about)). Demo API is a soft ~1M tile requests/mo. This is the most interesting option for the hackathon: Pixel-minimal + fully offline + zero per-request cost.
- **Tilezen**: the schema behind older Mapzen minimal styles — mature but effectively legacy; prefer OpenMapTiles-schema options above (OpenFreeMap and Protomaps both serve OpenMapTiles-derived tiles).

*Note:* "black-and-white down to the last streets" is a **style + data-coverage** combo — vector tiles contain minor roads to z17+ already; what needs care is keeping labels/declutter rules from hiding them. A `dark-matter`/Positron-dark variant is a 1-line swap if a dark Pixel look is preferred.

---

## (e) On-device performance checklist for the RN app

**Context check:** we're on RN 0.86 + `@maplibre/maplibre-react-native` v11 — the **new architecture (Fabric/TurboModules, bridgeless JSI) is already on** ([RN 0.76 release — new arch by default](https://reactnative.dev/blog/2024/10/23/release-0.76-new-architecture); [MLRN v11 = new-arch only](https://github.com/maplibre/maplibre-react-native)). So the lag is not the bridge: it's network latency (§0) plus JS-thread stalls and re-render storms. Checklist:

**Network discipline (the actual "spins forever" fix):**
- `fetch` has **no timeout** — wrap every search call in `AbortController` + `setTimeout` (e.g. 2.5 s); abort the previous in-flight request inside the debounce ([RN Network docs](https://reactnative.dev/docs/network)). A hung socket currently means `searching` never clears.
- Keep the `searchSeq` stale-response guard **and** abort superseded requests; add a per-query **result cache** (`Map`/LRU keyed by normalized `q`) and a **TanStack Query/SWR**-style stale-while-revalidate layer so backspacing is instant (cached results render immediately while a refresh runs in background).
- Warm the connection: one early `fetch(${API}/health)` on app start keeps TLS/keep-alive hot so the first real query doesn't pay handshake cost.
- Server side already uses keep-alive `httpx.AsyncClient` (8 s timeout) — keep it; return results fast and let the client decide (don't let server slowness block the UI skeleton).

**Rendering:**
- Show **skeleton rows / previous results immediately** at each keystroke (optimistic placeholder), then swap in real results — this alone converts "spinner" feel into Google-Maps feel.
- Render search results in a bounded `FlatList` (`windowSize`, `getItemLayout`, `keyExtractor`, memoized row component) — never map-and-mount markers per result; draw result pins via `GeoJSONSource` + `Layer`, not `Marker` components (matches how `FieldLayer`/`ReportsLayer` already work).
- Keep the map unmounted-stable: `mapStyle` prop to a static `STYLE_URL`/bundled JSON; avoid passing new object identities for `paint`/`layout` props each render (memoize layer styles); gate overlays behind `useMemo`.
- Debounce camera/zoom-driven state (`onRegionDidChange` → throttle before it hits React state — every setState re-renders the JS tree; use `runOnJS`-dispatched or batched updates). Prefer imperative camera refs (`flyTo`) over state-driven camera props.
- Batch initial fetches (`/grid`, `/community`, `/shift`…) with `Promise.all` and lazy-mount heavy sheets (`LedgerSheet`, `JourneyDrawer`) behind first-interaction or `InteractionManager.runAfterInteractions` so search focus/typing never competes with drawer mounts for the JS thread.

**Data layer:**
- Recents + frequent-destination store (sqlite/mmkv) rendered under an empty query = the Uber/Lyft "predictions ≈ 50–70% of entries" win ([Uber](https://www.uber.com/kw/en/blog/tech-stack-part-one-foundation/); [Lyft](https://www.lyft.com/blog/posts/how-lyft-uses-ai-to-get-you-where-you-want-to-go-faster)).
- `expo-sqlite` FTS5 is enabled by default → on-device gazetteer is directly buildable ([Expo SQLite docs](https://docs.expo.dev/versions/latest/sdk/sqlite)).
- Prefer `metro`/`expo` production bundling for profiling; measure JS frame times during typing with React DevTools/the built-in perf monitor — a >16 ms JS frame during keystroke→render is the threshold to beat.

---

## Appendix — the citation set

**Instant-search architecture**
- NN/g — Response Times: The 3 Important Limits: https://www.nngroup.com/articles/response-times-3-important-limits/
- Uber — Tech Stack Part I (autocomplete locally-biased; predictions ~50%): https://www.uber.com/kw/en/blog/tech-stack-part-one-foundation/
- Uber — Evolution of Uber's Search Platform (Sia, Live Index, Lucene): https://www.uber.com/ca/en/blog/evolution-of-ubers-search-platform/
- Uber Design — Designing the New Uber App ("Where to?" forward-looking): https://medium.com/uber-design/designing-the-new-uber-app-16afcc1d3c2e
- Lyft — destination prediction (attention, proximity-filtered candidates): https://eng.lyft.com/how-lyft-predicts-your-destination-with-attention-791146b0a439 ; https://www.lyft.com/blog/posts/how-lyft-uses-ai-to-get-you-where-you-want-to-go-faster
- Google — session tokens & session pricing: https://developers.google.com/maps/documentation/places/web-service/place-session-tokens ; https://developers.google.com/maps/documentation/places/web-service/session-pricing
- Google — how autocomplete works (Search): https://blog.google/products-and-platforms/products/search/how-google-autocomplete-works-search/
- Google Lat Long — viewport-relevant suggestions: https://maps.googleblog.com/2010/04/google-maps-search-box-just-got-smarter.html
- OpenSearch — autocomplete techniques: https://docs.opensearch.org/latest/search-plugins/searching-data/autocomplete/
- Geocode Earth — memory lane (completion suggesters/FST): https://geocode.earth/blog/2020/memory-lane/
- Uber H3: https://h3geo.org/

**Geocoder stack**
- Nominatim usage policy (no autocomplete): https://operations.osmfoundation.org/policies/nominatim/
- Photon: https://github.com/komoot/photon ; API: https://github.com/komoot/photon/blob/master/docs/api-v1.md ; usage: https://github.com/komoot/photon/blob/master/docs/usage.md
- Photon dumps — India 575 MB / Asia 9.3 GB / planet 62 GB: https://download1.graphhopper.com/public/asia/india/index.html ; https://download1.graphhopper.com/public/asia/index.html ; https://download1.graphhopper.com/public/index.html
- Pelias: https://github.com/pelias/pelias ; services: https://github.com/pelias/documentation/blob/master/services.md ; autocomplete: https://github.com/pelias/documentation/blob/master/autocomplete.md ; docker reqs: https://github.com/pelias/docker ; planet sizing: https://github.com/pelias/documentation/blob/master/full_planet_considerations.md
- AWS Location: endpoints/regions https://docs.aws.amazon.com/general/latest/gr/location.html ; pricing https://aws.amazon.com/location/pricing/ ; pricing model https://docs.aws.amazon.com/location/latest/developerguide/places-pricing.html ; Suggest https://docs.aws.amazon.com/location/latest/developerguide/suggest.html + https://docs.aws.amazon.com/location/latest/APIReference/API_geoplaces_Suggest.html ; per-1K numbers via AWS Builder Center https://builder.aws.com/content/3CLjvOk8OPPeuW24EJTBIqEOpKc/
- Mapbox: Search Box https://www.mapbox.com/search-box ; pricing https://www.mapbox.com/pricing ; Geocoding https://www.mapbox.com/geocoding ; geocoding docs https://docs.mapbox.com/api/search/geocoding
- OSMNames gazetteer: https://osmnames.org/ + https://github.com/OSMNames/OSMNames
- Meilisearch geosearch: https://www.meilisearch.com/docs/capabilities/geo_search/getting_started
- Valhalla loki (not a gazetteer): https://valhalla.github.io/valhalla/loki/
- Geofabrik India extract: https://download.geofabrik.de/asia/india.html
- expo-sqlite FTS: https://docs.expo.dev/versions/latest/sdk/sqlite

**Reverse geocoding**
- Nominatim reverse (zoom↔granularity): https://nominatim.org/release-docs/latest/api/Reverse/
- Photon api-v1 (radius/layer/dedupe): https://github.com/komoot/photon/blob/master/docs/api-v1.md

**Map styles**
- OpenFreeMap: https://openfreemap.org/ ; quick start https://openfreemap.org/quick_start/ ; styles repo https://github.com/hyperknot/openfreemap-styles/
- CARTO basemaps: https://carto.com/basemaps/ ; https://carto.com/basemaps/apikey/
- Protomaps: https://docs.protomaps.com/basemaps/flavors ; https://docs.protomaps.com/basemaps/downloads ; https://protomaps.com/about
- OSM Liberty: https://github.com/maputnik/osm-liberty

**RN performance**
- RN 0.76 new architecture: https://reactnative.dev/blog/2024/10/23/release-0.76-new-architecture ; https://reactnative.dev/blog/2024/10/23/the-new-architecture-is-here.md
- MLRN v11 (new-arch only): https://github.com/maplibre/maplibre-react-native
- RN fetch/AbortController: https://reactnative.dev/docs/network
