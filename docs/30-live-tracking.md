# 30 · The live-tracking engine — honest spec

*Research deliverable, 2026-10-03. Question under test: what does
"start a journey → pick vehicle → real-time AQI this second → live
inhalation + emission tickers" actually cost to build truthfully —
in GPS silicon, in battery, in emission physics, and in server load.
Claim tags throughout: **[V]** verified against a cited doc/paper or
our own code · **[I]** inferred / modeled from cited inputs ·
**[C]** arithmetic on verified inputs.*

---

## 0. Verdict up front

The feature is buildable and honest **if the "per-second" is a render
decision, not a network or GNSS decision.** Everything below reduces
to five engineering facts:

1. **The field is quasi-static.** Our kriged field refreshes every
   15 min (`airfield.py` `CACHE_TTL = 900`) and its variogram range is
   15 km (`krige.py`). PM2.5 at a point physically cannot change
   meaningfully second-to-second. So "real-time AQI at that second"
   is honest as a *position-resolved field lookup at fix time* — never
   as a per-second server call. **[V]**
2. **The ticker's 1 Hz motion is free.** Dose accrues
   `C·microenv·VE·dt` — once you hold `C` from the last fix, the
   per-second integral term is a local multiply. GNSS fixes are only
   needed when *position changes enough to change C* — every ~25–50 m,
   not every second. **[C]** from our own dose math.
3. **The emission ticker needs zero traffic APIs.** Emission
   accumulation uses *realized* speed (GNSS Doppler, ~0.1–0.4 m/s
   accurate on modern Androids). Traffic data only feeds the
   *counterfactual* — "this route at free-flow would have emitted Y."
   OSRM free-flow duration is exactly that baseline. **[V]**
4. **Battery cost is dominated by the screen and the LTE radio, not
   the GNSS chip.** Continuous GNSS tracking measured ~430 mW above
   idle (2013 hardware, dual-freq +37% since) → ~2–4 %/h screen-off on
   a modern ~17 Wh pack. The screen adds more. The radio at 1 Hz POST
   never enters idle tail states — *that* is the murderer, and it's
   optional. **[V]** numbers / **[I]** combined model.
5. **Cold-start and idle are the only two places a flat g/km factor
   lies badly.** COPERT's own structure — hot EF speed curve +
   `ECOLD = β·N·M·eHOT·(eCOLD/eHOT − 1)` + idle floor in g/s — is
   directly implementable in ~80 lines. **[V]**

**Spec in one table** (§8 derives it):

| Component | Ship cadence / policy | Why |
|---|---|---|
| GNSS fixes | `distanceInterval` 25 m + time floor 5 s, foreground service | dose needs field-at-position; 25 m ≪ 15 km field range |
| Dose integration | 1 Hz local render, `dt` measured not assumed | the ticking feel is free; keep it |
| Field value | refresh on new fix, max once/60 s, or prefetch route strip | field TTL 15 min — faster polling is decorative |
| Emission rate | `max(idle_gps, ef_gkm(v)·v/3.6)`, cold factor on first ~4 km | COPERT/MOVES structure |
| Server writes | batch 30–60 s or trip-end `/observe` (already exists) | radio tail energy, not server CPU, is the cost |
| Display | banded numbers ("~41 µg so far"), congestion surcharge vs OSRM free-flow | fake precision is the theatrical trap |

---

## 1. What's already shipped (baseline this builds on)

Read of the current code, so the delta is priced correctly:

- `Mobile/App.tsx` nav mode already runs a live dose meter:
  `setInterval(tick, 25000)` → `Location.getCurrentPositionAsync`
  (Accuracy.Balanced) → `GET /aqi?lat&lon` →
  `dose += pm25 · microenv · (VE_lpm/1000) · (25/60)` — receipt at
  ~80 m from destination. **[V]**
- `server/exposure.py` `dose()`: the integral
  `Σ C(x)·ME(mode)·VE(mode)·Δt` over ~250 m geometry samples, krige σ
  propagated to `dose_lo/hi`. Mode tables `MICROENV`/`VENTILATION_LPM`
  are all measured Delhi values. **[V]**
- `server/airfield.py` + `krige.py`: field = de-biased IDW over
  ~150 samples (48-pt Open-Meteo grid + ~105 live CAAQMS instruments
  at 3× weight) with ordinary kriging when ≥20 samples fit a
  variogram. Cost: one ~145×145 solve per 15-min refresh, then O(n)
  per query — **a field lookup is tens of microseconds**. **[V]** (the
  krige.py docstring states the same cost model)
- `server/community.py` `/observe`: stores anonymized traversals
  (≤400 pts), computes implied ambient concentration
  `C = dose/(VE·t·ME)` for the corridor layer — the citizen map
  already inverts the same integral. **[V]**
- `main.py` `/aqi`, `/grid`, `/route`, `/compare`, `/shift` — all
  stateless, field lookups in-memory. **[V]**

So the live-tracking engine is **~70% already deployed**. What is
missing or wrong: fixes are Balanced-accuracy one-shots (not a
tracked stream), `dt` is hardcoded 25 s regardless of real elapsed
time, `/aqi` is polled far faster than the field can change, there is
no emission ticker, no cold/idle handling, no congestion counterfactual,
and nothing runs in a foreground service (screen-off = OS may suspend).

---

## 2. Position sampling — what actually happens in a Delhi canyon

### 2.1 The physics of the error

- Smartphone GNSS in urban canyons: NLOS/multipath-dominated.
  24-hour datasets across open-sky/city-street/canyon classes put
  canyon horizontal RMSE at **13.0 m** (vs 4.7 m after SNR-variability
  weighting); vertical RMSE 19.5 m. NLOS pseudorange error histograms
  grow heavier tails with canyon depth. **[V]** — HK-model paper,
  PMC12349109.
- Uber's own platform team: GNSS error **"50 meters or more"** in
  dense urban areas is routine; their fix is per-satellite SNR +
  3D building maps (shadow-matching class) run server-side. They also
  built *beacon* hardware because phone GNSS + IMU fusion quality
  varies by device; barometers exist on only ~60% of their US
  driver fleet. **[V]** — Uber eng blog, "Rethinking GPS" &
  "Improving Pickups."
- Zepto (operating at Delhi scale, low-end Androids): raw rider GPS
  "spatters coordinates" — 400 m teleports, pings vanished for
  minutes, glass-facade bounces; naive Haversine path length lands
  **30–40% off** true distance. Their pipeline: joint anomaly score
  (speed/accel/bearing/deviation) → OSRM map-matching → H3-HMM
  consensus paths. Ping cadence on rider phones: **"every few
  seconds"**. **[V]** — Zepto eng blog, Route IQ (Aug 2026).
- Flyovers/underpasses (AIIMS, Dhaula Kuan, the Ring Rd stacks): two
  distinct failure modes — (a) signal blockage/NLOS in the box
  section, (b) the 2.5-D ambiguity of stacked carriageways; fused
  location can't always tell which level you're on, and Zepto's own
  copy calls out flyovers as a degradation zone. **[I]** for the
  Delhi-stack specificity, grounded in the cited NLOS behavior.

### 2.2 How the big trackers actually track (Android)

| Mechanism | What it does | Constraint |
|---|---|---|
| `FusedLocationProvider` | fuses GNSS + Wi-Fi + cell + IMU; `setPriority()` picks accuracy tier | `PRIORITY_HIGH_ACCURACY` = "significant battery drain" (Google's words); `BALANCED` rarely uses GPS **[V — Android docs]** |
| `setInterval` / `setMinUpdateInterval` | requested vs guaranteed floor | interval is a *hint*; `setMaxWaitTime` batches delivery — wake every 30–60 min possible on background work **[V]** |
| Foreground service `type=location` | keeps `requestLocationUpdates` alive screen-off | Android 14 requires `FOREGROUND_SERVICE_TYPE_LOCATION` in manifest + a persistent notification; Android 8+ background = **"a few times each hour"** **[V — Android docs]** |
| iOS equivalents | `pausesLocationUpdatesAutomatically`, `allowDeferredLocationUpdates(untilTraveled:timeout:)` (GPS buffers on-chip), significant-change (~500 m+) | deferred updates require best/navigation accuracy **[V — Apple docs]** |
| Expo layer | `startLocationUpdatesAsync(task, {accuracy, timeInterval, distanceInterval, deferredUpdatesInterval, deferredUpdatesDistance, foregroundService:{...}, pausesUpdatesAutomatically, activityType})` → TaskManager callback gets batched `locations[]` | needs `isAndroidForegroundServiceEnabled` plugin flag + dev build (no Expo Go) **[V — expo docs v57]** |

**The operating pattern everyone converges on** (Google nav, Uber,
Zepto): continuous foreground GNSS at ~1 Hz native cadence,
application-level thinning, anomaly filtering before any distance/
dose math, batched network writes. Nobody posts every fix raw.

### 2.3 Honest treatment of position noise

For dose we don't need Zepto's full pipeline — the field is 15-km
smooth, so a 15–50 m position error changes `C` by single-digit
percent. But three cheap guards stop embarrassing numbers:

1. **Accuracy gate**: discard fixes with `accuracy > 50 m` or
   `speed == 0 && accuracy > 30 m` (stationary jitter adds phantom
   µg and phantom distance). **[I]** — threshold consistent with
   canyon RMSE measurements above.
2. **dt from the clock, not the constant.** Current code accrues
   `25/60` per tick even when a tick is skipped or late. Dose must
   integrate *actual* elapsed `dt` between accepted fixes —
   otherwise background throttling silently under-counts.
   **[V — our code]**
3. **Optional map-match**: snap to the traveled road when emitting
   the *traversal* record (`/observe`), never to correct the live
   dose — the dose only needs `C(x)`, not which lane. **[I]**

Vertical ambiguity (flyover vs underpass) is real but **field-
irrelevant**: both levels sit in the same kriged cell and the same
near-road uplift class. It matters for ETA/map-matching, not µg.
**[I]**

---

## 3. The dose accumulator — math and cadence

The integral, honestly stated:

```
dose(µg) = Σ_ticks C_field(lat_t, lon_t) · ME(mode) · VE(mode)[m³/min] · Δt[min]
```

- `C_field` — kriged/IDW value at fix position, refreshed ≤1/min
  (field TTL 15 min; station data hourly). Between fixes it is simply
  the last value — the field's own σ swamps any interpolation error.
- `Δt` — measured wall-clock between accepted ticks; if the app was
  suspended, accrue `C_last · VE · Δt_wall` capped, and mark the gap
  (a 10-min subway stretch shouldn't fake-integrate roadside air).
- `ME`, `VE` — existing per-mode tables (`MICROENV`, `VENTILATION_LPM`;
  VE midpoints trace to Zuurbier 2009's 2.1× cyclist-vs-car ratio and
  Bigazzi & Figliozzi 2014's 2–5× respiration range for active modes).
  **[V — all cited]**
- **Adaptive VE**: literature supports VE rising with exertion/speed
  for active modes (Bigazzi's dynamic-ventilation work: ~0.4–0.8 %/W
  power). Honest version: keep fixed VE per mode but widen the dose
  band for cycling (VE CV ~30–40%). **[I]**
- **Uncertainty**: krige σ already flows to `dose_lo/hi` server-side;
  the live ticker should carry the same band, displayed as
  "~41 µg" or a band, never 41.37. **[V — code exists]**

**Cadence answer to the spec**: fixes every ~25 m (≈5–15 s at Delhi
speeds, slower in jams — distance-triggered automatically stretches
the interval in congestion, which is *exactly* where GNSS is weakest
and dose-per-metre is highest). Render/integration at 1 Hz is free
and should ship. Per-second *network* or *GNSS* sampling buys
nothing measurable. **[C]**

---

## 4. The emission ticker — speed-aware, cold-aware, idle-aware

### 4.1 The two regimes of emission math

| Regime | Correct unit | Why |
|---|---|---|
| moving | **g/km as function of speed** `e(v)` | COPERT Tier-3: `EHOT = EF[g/km]·km`, where `EF` is a U-shaped mean-speed curve; guidebook suggests single representative speeds (urban 20 / rural 60 / highway 100 km/h) or integrating `e(V)·f(V)` over the speed distribution **[V — EMEP/EEA 2023 ch. 1.A.3.b, §3.4.1]** |
| stopped / near-stopped | **g/s idle floor** | as `v→0`, g/km → ∞; idle is fuel-per-time: NRCan's rule ≈ 0.6 L/h per litre of displacement → a 1.2 L engine ~0.7 L/h ≈ **~1.5–1.8 kg CO₂/h ≈ 0.4–0.5 g/s**; Argonne measured restart-vs-idle crossover at ~10 s **[V — NRCan, Argonne "Which is Greener" study]** |

So the per-tick rate is:

```
rate_g_s(v) = max( idle_g_per_s , ef_gkm(v) · v_kmh / 3600 )
emitted += rate_g_s(v) · Δt
```

with `ef_gkm(v)` a calibrated U-curve per mode. **[C]** structure,
**[V]** components.

### 4.2 Cold start — the first kilometres are real

COPERT's formulation, verbatim from the guidebook:

```
ECOLD = β · N · M · eHOT · ( eCOLD/eHOT − 1 )
β   = fraction of mileage driven with cold engine/catalyst
    — tabulated vs ambient temperature and mean trip length ltrip
    (European default ltrip = 12.4 km, bounds 8–15 km)
eCOLD/eHOT = quotient per pollutant vs ambient temp (MEET-derived)
```

Operational translation for a consumer ticker: a **warm-up
multiplier** that decays to 1 over roughly the first **3–6 km**
(petrol catalyst light-off distance; longer in winter, near-zero for
CNG 3-wheelers — BS norms differ). The "first ~3 km" in the spec is
the right order of magnitude. Show it as state ("engine warming up")
not precision. **[V]** formula/parameterization, **[I]** km-range.

MOVES (US-EPA) is the same physics at finer resolution: 23 operating
modes defined on VSP (kW/Mg) within speed classes, plus explicit
idle and coast bins — worth citing as the "why" for the speed curve,
not implementable verbatim (US fleet EFs). **[V — EPA MOVES3 docs]**

### 4.3 Per-mode factors for Delhi's fleet (computed, marked)

CO₂ from fuel economy × DEFRA factors (petrol 2.08 kg CO₂e/L biofuel
blend / 2.66 diesel / CNG ≈ 2.5 kg CO₂e/kg):

| Mode | Typical Delhi fuel economy [I] | Free-flow ~g CO₂e/km | Idle g/s |
|---|---|---|---|
| petrol car | 12–15 km/L city | ~140–175 | ~0.4–0.6 |
| 2-wheeler petrol | 45–60 km/L | ~35–45 | ~0.1–0.15 |
| auto-rickshaw CNG | 25–35 km/kg | ~70–100 | ~0.15–0.25 |
| bus CNG (per vehicle) | ~2–3 km/kg | ~800–1200 | ~1.5–2.5 |
| metro | electric | per-pax grid factor only — off-ticker or tiny | — |
| walk / cycle | 0 tailpipe | 0 (metabolic CO₂ optional easter egg) | 0 |

Speed-curve direction **[V — COPERT curves, Barth & Boriboonsomsin
2008]**: below ~15 km/h CO₂/km climbs steeply (their result: clearing
congestion can cut corridor CO₂ ~20 %); minimum sits ~60–80 km/h;
above ~100 aerodynamic losses dominate again. The congestion delta —
`emitted − freeflow_baseline` — is both the most defensible and the
most dramatic number: *"the jam added 340 g."*

### 4.4 The counterfactual needs OSRM, not a traffic API

OSRM durations are **free-flow** (speed-profile-based, no live
traffic — confirmed; the public demo is also driving-only, already
flagged in our code). That is precisely the baseline for the
congestion surcharge: `E_freeflow = ef_gkm(v_osrm_freeflow)·distance`
vs the accumulated `E_actual`. Two honest numbers on one receipt:
**emitted so far** and **congestion surcharge**. **[V]**

---

## 5. Congestion data — what Delhi can actually get free

| Source | Delhi coverage | Free tier | Verdict for this product |
|---|---|---|---|
| TomTom Traffic (Flow/Incidents) | real probe coverage incl. Delhi; TomTom 2025 index: **Delhi 60.2 % congestion, 24:28/10 km** | 2,500 non-tile req/day, 50 k tiles/day, no card, commercial OK | usable for *pre-trip* route comparison at hackathon scale; NOT needed for the ticker **[V — TomTom FAQ/pricing, index]** |
| HERE Traffic | yes | 1,000 req/day no-card (Limited); ~30 k/mo with card (Base) | same role; thinner Delhi probe density than TomTom **[I]** |
| Google Routes/Directions w/ traffic | best-in-India | Directions Advanced SKU **$10/1k**, 5 k free/mo; traffic = crowdsourced probe speeds + GNN ETA (97 % accurate claim) | overkill for a demo; the pricing is the honest citation for why we don't use it **[V — Google pricing, Maps-101 blog, DeepMind blog]** |
| Google Roads API | — | snap-to-roads only | **no traffic data** — corrects the spec's assumption **[V]** |
| OSRM (our stack) | free-flow only | free/self-hosted | the *baseline* layer; its anomaly vs realized traversal speed becomes our own congestion signal via `/observe` corridors **[V]** |

**Eco-routing literature, what it actually models:**

- **Google's fuel routing runs NREL RouteE** (open source, PyPI
  `nrel.routee.powertrain`): link-level energy models pretrained on
  ~1 M miles of drive cycles + FASTSim simulation fleet; inputs =
  link speed, grade, road class, turns. I.e. the state of the art
  *is* a speed-aware link energy model — the same shape as our
  ticker math. **[V — NREL RouteE docs/repo, BTS policy brief]**
- Independent eval of Google eco routes (Pittsburgh microsim, MDPI
  Sustainability 2024): found discrepancies vs simulated optimum —
  eco-routing is directional, not exact. Salt Lake City macro-sim
  (arXiv 2111.03426): Google traffic-aware nav saves ~**1.7 % CO₂ /
  6.5 % time** fleetwide, ~3.4 %/12.5 % for rerouted users. Honest
  magnitude calibration: don't promise 30 % savings. **[V]**
- Barth/Boriboonsomsin/Vu eco-navigation lineage (UCR CERT, ITSC
  '07 onward): eco-routes trade distance for smoother speed
  profiles; savings land in single digits to ~20 % under severe
  congestion. **[V]**
- **Our defensible variant**: eco-**mode** not eco-route — the big
  Delhi lever is metro-vs-car (we already prove 28× dose), while
  within-mode route choice is ±10–20 %. Emission ticker = awareness;
  mode choice = the action. **[I]**

---

## 6. Server architecture — the tick is cheap, the radio is not

**Cost model for per-tick POST** **[C]**:

- 1 Hz POST = 3,600 req/h/user ≈ 1 rps/user. Even 500 concurrent
  Delhi commuters = 500 rps of ~300 B JSON — a single Fargate task
  serving in-memory field lookups (µs each) does this in its sleep.
  Server-side, per-tick POST is **fine**.
- The phone side is where it dies: every HTTPS request wakes the
  cellular modem; LTE/5G radios hold high-power tail states ~10 s
  after each transaction — at 1 Hz the radio **never idles**, adding
  roughly 1–3 W-class drain on the weakest link of the battery
  budget. This is the documented reason trackers batch.
  **[I — established RRC-tail literature, magnitude modeled]**
- Correct shape: **stateless batched uploads** —
  `{trip_id, fixes:[{t,lat,lon,v,acc}...]}` every 30–60 s, or trip-end
  only (already implemented as `/observe` + receipt). Fix records
  compress to ~12–16 B each with delta-coded ints; an hour trip is
  ~15–50 KB. **[C]**
- Session state is unnecessary: dose/emission are pure accumulators;
  the server only needs the field snapshot id the client used, so
  `/observe` can carry `field_age_s` for auditability. **[I]**
- iOS deferred delivery / Android `maxWaitTime` batching is the same
  pattern pushed into the OS. **[V — Apple/Android docs §2.2]**

---

## 7. Battery budget — the honest numbers

Component anchors (all **[V]**):

- GNSS continuous tracking: **433 mW above idle** measured on Galaxy
  S3 (Carroll & Heiser power instrumentation, 2013); cold fix
  ~400 s/154 J, warm ~30 s. Dual-frequency GNSS adds **~37 %**
  outdoors (arXiv 1910.13041, Xiaomi Mi8 BCM47755).
- Weak-SNR environments cost more battery: measured 38 % vs 13 %
  drain in low vs strong signal conditions (CORE 228341758) — urban
  canyons are literally worse for watts *and* metres.
- EnTracked / MobiSys'09-'11 lineage (Kjærgaard et al.): adaptive
  sensor scheduling + distance-aware sampling is the standard way to
  get "considerable" tracking savings; Android's own guidance: real-
  time = few-second intervals, otherwise ≥2 min; `PRIORITY_NO_POWER`
  passive fixes are free riders on other apps' GNSS.
- Screen: ~0.5–1.5 W typical at map brightness — exceeds GNSS.
  **[I — order-of-magnitude, device-dependent]**

Modeled battery per hour, nav mode, mid-range phone (~17 Wh pack)
**[I — assembled from above]**:

| Policy | GNSS duty | Est. %/h screen-off | %/h screen-on map |
|---|---|---|---|
| 1 Hz continuous HighAccuracy | ~100 % | ~3–5 % | ~10–18 % |
| 5 s fixes | ~40–70 % | ~2–3.5 % | ~9–16 % |
| 15 s fixes | ~25–45 % | ~1.5–2.5 % | ~8–15 % |
| distance-only ~25 m (no time floor) | 10–30 % | ~1–2 % | ~8–14 % |
| distance-only + screen wakes only on maneuver | low | ~1 % | ~5–9 % |

Below ~10 s cadence the GNSS never truly sleeps between fixes —
re-acquisition dominates, so savings vs 1 Hz are modest; the big
levers are **distance-triggering** (a red light = free sampling
pause), **screen policy**, and **no per-second network**. A one-hour
commute at 2–4 % screen-off is acceptable; a 24/7 background mode
(AirTrack-style) is a different product and should not be promised
from this feature. **[I]**

OEM reality check: Xiaomi/Vivo/Oppo battery managers kill
foreground-location services aggressively; Zepto's own copy names
"aggressive battery-saver modes" as a top cause of vanished pings.
Ship the foreground-service notification, ask for "unrestricted
battery" on the journey-start sheet, degrade to distance-only fixes
if the service dies. **[V — Zepto blog] / [I — OEM behavior]**

---

## 8. The honest spec

```
Journey start
  ├─ vehicle pick → sets ME, VE, fuel/emission curve, idle floor
  ├─ server returns: route geometry, field strip along route
  │    (sampled every ~250 m — one request, kills per-tick /aqi),
  │    free-flow baseline ef(v_free)·d for the surcharge
  ├─ Android: foreground service type=location,
  │    requestLocationUpdates(BestForNavigation, timeInterval=5s,
  │    distanceInterval=25m, maxWaitTime ok)
  │  iOS: activityType=automotiveNavigation,
  │    pausesUpdatesAutomatically=true
  │
Per accepted fix (gate: accuracy ≤ 50 m)
  ├─ dose    += C_field(fix) · ME · VE · Δt_wall        [1 Hz render of same]
  ├─ emit    += max(idle, ef(v)·v/3600) · Δt · cold(km)  [cold→1 by ~4 km]
  └─ buffer fix {t,lat,lon,v,acc}
Upload: every 60 s OR trip end → /observe with field_age_s
Receipt: dose_ug [band], dose vs rejected modes, emitted g,
         congestion surcharge g, "engine warming" marker on first km
```

**Real vs theatrical — final call:**

| Real | Theatrical (don't ship) |
|---|---|
| µg ticking 1 Hz from last-fix C | a new `/aqi` fetch every second |
| dose band from krige σ | dose to 2 decimals |
| congestion surcharge vs OSRM free-flow | "traffic-aware emissions" with no traffic data |
| cold-start as visible warm-up state | precise cold grams |
| realized-speed emission curve | per-second grams *predicted* from traffic API |
| batched uploads | per-tick POST streaming |
| "field is 12 min old" timestamp | "live AQI" without age |

The theatrical version demos identically; the honest version survives
a jury that runs the numbers.

---

## 9. Citations

**Location / battery**
- Android Developers — battery & location docs (FLP priorities,
  intervals, maxWaitTime), background location limits (Android 8+:
  few updates/hour), FGS `location` type (Android 14):
  developer.android.com/develop/sensors-and-location/location/battery,
  /background-location-limits, /services/fgs/service-types
- Apple — Energy Best Practices (pausesLocationUpdatesAutomatically,
  deferred updates): developer.apple.com .../LocationBestPractices
- Expo SDK 57 — expo-location `startLocationUpdatesAsync` options:
  docs.expo.dev/versions/v57.0.0/sdk/location
- Carroll & Heiser, power instrumentation of Galaxy S3 (GPS
  tracking 433 mW above idle): USENIX ATC'10 follow-up tech report,
  trustworthy.systems/publications/nicta_full_text/7044.pdf
- Dual-freq GNSS power study (Mi8, +37 %): arXiv 1910.13041
- SNR-vs-battery study (38 % vs 13 %): core.ac.uk/download/pdf/228341758.pdf
- Kjærgaard et al., EnTracked MobiSys'09 (doi 10.1145/1555816.1555839)
  + Energy-efficient Trajectory Tracking MobiSys'11
- Urban-canyon GNSS statistics: ION/NASA NTRS 20250000589; HK-model
  weighting RMSE improvements: PMC12349109
- Smartphone Doppler velocity accuracy: ISPRS Arch. XLVI-3-W1-2022/89/2022
- Uber — "Rethinking GPS" (50 m+ urban error, SNR+3D maps),
  "Improving Pickups" (beacon IMU/barometer), uber.com/blog
- Zepto — Route IQ blog (ping cadence, 400 m teleports, 30–40 %
  Haversine error, OSRM map-matching) + Tile38 scaling blog,
  blog.zepto.com (Aug 2026)

**Emissions**
- EMEP/EEA Guidebook 2023 (upd. 2024), ch. 1.A.3.b — Tier-3 hot/cold
  split, `EHOT=EF·km`, `e(V)` speed curves, cold-start eq. (10),
  β-parameter & ltrip 12.4 km: copert.emisia.com chapter PDF
- EPA MOVES3 emission-rates report (23 opModes, VSP-based):
  nepis.epa.gov P10169P7
- Argonne/NRCan idle fuel: afdc.energy.gov "Which is Greener";
  oee.rncan.gc.ca idle factor 0.6 L/h per litre displacement
- DEFRA 2026 GHG factors (petrol 2.075, diesel 2.66, CNG kg-basis):
  gov.uk conversion factors / sustainmetrics mirror
- CPCB/MoEF–ARAI Indian vehicle EF program (ICAP draft report,
  in-use fleet vintages): learning-cleanairasia.org mirror
- Barth & Boriboonsomsin, TRR 2058 (2008) congestion-CO₂ ~20 %:
  doi 10.3141/2058-20; eScholarship qt4fx9g4gn
- NREL RouteE (Google's fuel-routing engine): nrel.gov RouteE page,
  github.com/nrel/routee-powertrain; BTS brief rosap dot/67950
- Google Maps sustainability study: arXiv 2111.03426
- MDPI Sustainability 2024 eco-route microsim eval: doi
  10.3390/smartcities... (2673-7086/4/4/40)

**Traffic data**
- TomTom pricing/QPS: developer.tomtom.com pricing + docs.tomtom.com
  FAQs (2.5 k non-tile/day freemium); TomTom Traffic Index 2025 Delhi
- HERE RPS limits & plans: here.com/get-started/pricing
- Google Maps Platform pricing (Directions Advanced $10/1k, 5 k/mo
  free): developers.google.com/maps/billing-and-pricing/pricing
- Google Maps 101 traffic blog + DeepMind GNN ETA blog (Sep 2020)

**Our code**: `server/exposure.py`, `server/airfield.py`,
`server/krige.py`, `server/community.py`, `Mobile/App.tsx` nav block.
