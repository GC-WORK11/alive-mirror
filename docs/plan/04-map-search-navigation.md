# 04 · Map, search, routing, live navigation

## 1. Map stack
| Layer | Choice | Status |
|---|---|---|
| Renderer | `@maplibre/maplibre-react-native` v11 (already in app) | shipped |
| Basemap | **Amazon Location Maps v2**, style `Standard`, `ColorScheme=Dark`, `PoliticalView=IND`, tiles from `maps.geo.ap-south-1.amazonaws.com` | style descriptor fetched [V]; client key to create |
| Auth | Amazon Location **API key** restricted to `geo-maps:GetTile`, `geo-maps:GetStaticMap`, `geo-places:Autocomplete/Suggest` (read-only), expiry set | to create |
| Fallback | OpenFreeMap dark (current) if the key fails | shipped |

Why Amazon over OSM tiles: HERE data has far more Delhi POIs and building-level detail than OSM in Delhi (verified on search below), it's AWS (judging), and it's the same data as our search — the pin you pick sits on the map label you see.

## 2. Search — three tiers, merged as they arrive
Target: first suggestion paints in <16 ms; complete list in ~150 ms on Delhi 4G.

| Tier | Where | Data | Latency target |
|---|---|---|---|
| T0 | on device | bundled gazetteer (26.5k Delhi places: localities, metro, landmarks) — shipped; extend to ~150k (doc 08 build) | <5 ms |
| T1 | our server, C++ `alive_core.search` | OSM Delhi-NCR extract (POIs, streets, house/block addresses) + every Amazon result we've ever returned (cached place ids, names, coords), prefix + typo-tolerant index | <2 ms server, + network RTT |
| T2 | Amazon Location `geo-places:Suggest` (v2), `BiasPosition` = user, `IncludeCountries=IND` | HERE | verified: "select citywalk" → Select Citywalk Mall; "lajpat nagar 4" → block-level results; "haldiram chandni" → Haldiram's Chandni Chowk; "dlf cyber hub" → DLF CyberHub [V] |

Mechanics:
- Debounce 80 ms after the first character; cancel in-flight requests on each keystroke (AbortController).
- One HTTP call per keystroke to *our* server; the server queries T1 and T2 in parallel and streams T1 first (or returns both with T1 inline and T2 as soon as it lands — two-phase response).
- Merge/dedupe by normalized name + 75 m radius; rank: exact-prefix > token-prefix > fuzzy; then distance from user; then popularity (count of times picked, aggregate only).
- Selected place → `GetPlace` for exact coords/address only if the suggestion lacks a position.
- **Remove Photon (komoot, Germany) from the hot path** — it's the source of slow and random results reported on the phone.
- Reverse geocode ("your location", tap on map): Amazon `ReverseGeocode`, show block/street + locality.
- Hinglish/typos: normalization table (e.g. "chandni chok" → "chandni chowk", "cp" → "connaught place", "gk" → "greater kailash") in T1.

## 3. Routing
| Mode | Engine |
|---|---|
| Car, cab, auto | Amazon Location Routes v2 `TravelMode=Car` with traffic, 2 alternatives (verified: 3 routes returned for CP → AIIMS) [V] |
| Scooter/bike | Routes v2 `TravelMode=Scooter` (verified returns routes) [V] |
| Walk, cycle | OSRM foot/bike profile self-hosted or current approach (Routes v2 Pedestrian returned no route for the test pair — investigate before relying) |
| Metro, bus | DMRC + DTC GTFS router already shipped (`transit_real.py`) + walk legs |

Every route returns: geometry, duration with traffic, free-flow duration (for congestion → emissions), per-step instructions, speed per span where available.

## 4. Live navigation engine (client)
- Location: `expo-location` `watchPositionAsync` with `Accuracy.BestForNavigation`; during navigation `distanceInterval` 5 m / `timeInterval` 1 s for a smooth puck; outside navigation 25 m / 5 s (docs/30). Background continuation via `startLocationUpdatesAsync` + Android foreground-service notification (verify SDK 57 API at implementation).
- Map matching: snap fix to the nearest route segment if within 30 m and heading within 45°; otherwise mark off-route. 3 consecutive off-route fixes → reroute request.
- Puck animation: interpolate between fixes at display refresh; heading from GNSS course when speed >2 m/s, compass otherwise.
- Camera: follow mode, pitch 55°, zoom by speed (17.5 slow → 16 fast), bearing = heading.
- Turn banner: next maneuver from route steps; announce at 500 m / 150 m / at turn via `expo-speech` in the chosen language.
- Arrival: within 40 m of destination for 5 s, or user taps "End" → receipt.
- Battery: screen dominates; GNSS ~2–4%/h [R docs/30].

## 5. The two live counters (client math, no per-second network)
At trip start the server returns a **route strip**: the field sampled every ~250 m along the route (value + band) and the emission curve for the declared vehicle. Then on every tick:
```
dt      = now - last_tick                     (measured, not assumed)
C       = strip value at snapped position     (refresh strip if off-route)
dose   += C * microenv(mode) * VE(mode) * dt
v       = GNSS speed (m/s)
rate    = max(idle_g_s(vehicle), ef_g_km(vehicle, v) * v / 1000)
out    += rate * dt * cold_factor(km_driven)
```
Render both at 1 Hz with interpolation. Upload the trip summary (+ thinned trajectory, doc 07 privacy) at the end or every 60 s in batch.
