// Shared wire contract between Mobile/ apps and server/.
// Source of truth for API shapes; behavior lives in server/main.py.
//
// Mobile sync convention: Mobile/src/api/*.ts do NOT import this file —
// the app maps wire payloads onto its own narrowed view types (e.g.
// api/plan.ts FieldStatus ⊂ FieldStatus below, api/city.ts
// CityMovesPayload ⊂ V2CityMovesResponse). The mapping is deliberate:
// clients read through guarded mappers, so extra wire keys are always
// legal. Drift is caught server-side by server/tests/test_contract_sync.py
// (required fields must exist on the wire; emitted keys must be declared
// here). When you change a shape here, mirror it in the api/*.ts type
// comments — each file names the contract interface it shadows.

export interface Place {
  name: string;
  subtitle: string;
  lat: number;
  lon: number;
  kind?: string;
  // emitted on wire, previously undeclared (both /search and /v2/search):
  id?: string | null;
  place_id?: string;
  distance_m?: number;
  match?: "exact-prefix" | "token-prefix" | "fuzzy" | "category" | "area" | "other";
  match_rank?: number;
  score?: number;               // gazetteer ranking score (T1 rows)
  cov?: number;                 // SearchIndex token-coverage ratio (T1)
  fuzzy?: boolean;              // SearchIndex DL-only match flag (T1)
  compound?: boolean;           // kind+place compound hit ("atm near cp")
  anchor?: string;              // resolved place the compound anchored on
  subplace?: boolean;           // unit hit inside the anchor ("h block sector 62")
  locality?: boolean;           // area-level fallback: the anchor place itself
  source?: string;              // gazetteer | amazon | photon | ...
  sources?: string[];           // tiers that found it, e.g. ["t1","t2"]
  outside_ncr?: boolean;
}

export interface SearchResponse {
  results: Place[];
  error?: string;               // present on the "no matches" path
}

export interface RouteGeometry {
  type: "LineString";
  coordinates: [number, number][];
}

export interface ExposureFactors {
  // metro options report descriptive strings ("walk 1.0 / metro 0.45")
  // instead of scalars — union types match the wire.
  microenv: number | string;        // in-vehicle/ambient ratio (published, per mode)
  ventilation_lpm: number | string; // breathing rate L/min
  road_uplift: number;              // near-road multiplier applied
  activity?: string;                // dose() factor echo ("rest" | "moderate" | ...)
  mode_known?: boolean;             // false = fell back to walking factors
}

export interface Exposure {
  dose_ug: number | null;          // PM2.5 mass inhaled this trip
  confidence: "high" | "medium" | "low" | "none";
  factors: ExposureFactors;
  // present on every dose() result and the dose_error path; absent on
  // metro's hand-built reduced exposure block:
  avg_conc_ugm3?: number | null;   // breathing-zone average
  peak_conc?: number | null;
  coverage?: number;               // fraction of route with field data
  sparse?: boolean;
  warnings?: string[];             // e.g. "field_no_coverage", "speed_implausible"
  // emitted on wire, previously undeclared (dose() krige band + speed check):
  dose_ug_lo?: number | null;      // dose band from segment σ propagation
  dose_ug_hi?: number | null;
  implied_speed_kmh?: number;      // sanity echo — >120 km/h flags low conf
  dose_vs_best_pct?: number;
  ug_saved_vs_worst?: number;
}

export interface RouteResult {
  mode: TravelMode;
  distance_km: number;
  duration_min: number;
  geometry: RouteGeometry;
  exposure: Exposure;
  // emitted on wire, previously undeclared (/route options):
  duration_s?: number;
  duration_model?: "osrm" | "estimated";
  segments?: RouteSegment[];       // _annotate_segments: ~90 s spans
  hotspots?: RouteHotspot[];       // top-3 dose stretches
}

export interface FieldStatus {
  // airfield.FIELD.status() verbatim — present wherever a `field` key ships.
  // The degraded fallback (server/v2/plan.py `_field_status`) can emit just
  // {"source": "unavailable"}, so only `source` may be relied on.
  source: string;
  samples?: number;                // model lattice samples in the blend
  age_s?: number | null;           // seconds since served field fetched/built
  // the served field's own build instant — 'as of' without back-computing
  // age_s against the client's clock (snapshot stamp or live-fetch epoch)
  built_epoch?: number | null;     // unix seconds of the served build
  built_at?: string | null;        // the same instant, ISO UTC
  station_readings?: number;       // live station readings blended — 0 = dark
  /** the live instrument set behind station_readings — real feed coords,
      so surfaces draw these dots and never a baked-in list (e572f58) */
  stations?: { lat: number; lon: number; name?: string | null }[];
  stations_src?: string | null;    // "waqi" | "cpcb" | "openaq" — winning feed
  stations_status?: Record<string, string> | null; // per-feed verbatim verdicts
  wind?: Record<string, unknown>;
  kriging?: string;            // "on" | "idw"
  engine?: string;             // "alive_core" | "python" — which engine serves
  // --- serving-honesty block (airfield.py status(), always emitted) ---
  serving?: "snapshot" | "live" | "none"; // built index | live blend | empty
  stale?: boolean | null;       // age_s > stale_after_s; null = age unknown
  stale_after_s?: number;       // server stale threshold (2700 = 45 min)
  refresh_in_s?: number | null; // seconds until the next scheduled fetch
  refresh_ttl_s?: number;       // field cache TTL the refresh timer uses
  sigma_coverage?: string;      // "full" | "per-query" | "none" | "partial:N/M"
  load_warnings?: number;       // corrupt snapshot files skipped at load
  load_warn_files?: string[];   // basenames of recent skips (≤8)
  coverage?: {
    bbox?: number[];            // [w, s, e, n] lon/lat
    out_beyond_km?: number | null;
    cells?: number;
    sigma_cells?: number | null;
  } | null;
  snapshot?: {
    path?: string;
    built_at?: string | null;
    built_epoch?: number;
    grid?: string;
    cells?: number;
  } | null;
}

export interface RouteResponse {
  routes: RouteResult[];
  field?: FieldStatus;          // absent on the "router unavailable" path
  router_backend?: string;      // which router answered: osrm-local
                               // (self-hosted Delhi daemon) |
                               // osrm-public-demo (rate-limited fallback)
  error?: string;
}

export interface AqiResponse {
  pm25: number | null;
  pm10?: number | null;
  no2?: number | null;
  nearest_sample_km?: number;
  /** true when the point is inside the service margin but outside the
      served field's own extent — the value is the nearest edge evidence
      extrapolated, not a local read (edge-honesty marker) */
  beyond_field_edge?: boolean;
  smoke_modifier?: number;         // fire-season multiplier (1.0 = none)
  field?: FieldStatus;             // absent on the "field unavailable" path
  error?: string;
  // emitted on wire, previously undeclared:
  pm25_ambient?: number;
  pm25_lo?: number | null;
  pm25_hi?: number | null;
  us_aqi?: number | null;          // max EPA sub-index over served species
  us_aqi_basis?: string | null;    // driving pollutant key, e.g. "pm25"
  us_aqi_model?: number | null;    // raw CAMS index cell, for provenance
  european_aqi?: number | null;
  o3?: number | null;
  co?: number | null;
  so2?: number | null;
  nh3?: number | null;
  dust?: number | null;
  aod?: number | null;
  conditions?: Record<string, unknown>;
  fire?: Record<string, unknown>;
  wind?: Record<string, unknown>;
  grap?: Record<string, unknown>;
  calibration?: Record<string, unknown> | null;
  typical?: { month: number; hour_ist: number; median: number | null;
              p25?: number | null; p75?: number | null;
              vs_now_pct?: number | null } | null;
}

export interface ReverseResponse {
  name: string;
  lat?: number;                  // /reverse (v1) emits {name, subtitle} only;
  lon?: number;                  // /v2/reverse adds lat/lon/distance_m/source
  subtitle?: string;
  distance_m?: number;           // /v2/reverse only
  source?: string;               // /v2/reverse only
  kind?: string;                 // /v2/reverse: gazetteer category / amazon kind
  dropped_pin?: boolean;         // /v2/reverse: explicit "no named place" marker
  // /v2/reverse error bodies: 404 {error, lat, lon} / 503 {error, detail, hint}
  error?: string;
  detail?: string;
  hint?: string;
}

export interface HealthResponse {
  ok: boolean;
  ts: number;
  // emitted on wire, previously undeclared:
  version?: string;
  build_sha?: string;
  field_age_s?: number | null;
  field_refresh_in_s?: number | null;  // FieldStatus.refresh_in_s surfaced
  field_stale?: boolean | null;        // FieldStatus.stale surfaced
  engine?: string;                     // "alive_core" | "python" — serving engine
  wind?: { speed_kmh?: number; from_deg?: number; factor?: number } | null; // FieldStatus.wind — serving wind the router prices on
  transit?: { on_disk?: boolean; compiled?: string[]; real_feeds?: Record<string, boolean> } | null; // GTFS readiness — feeds baked/fetched and CSA indexes compiled
  routing?: { loaded?: boolean; edges?: number; edges_priced?: number } | null; // engine road graph — edges_loaded / edges carrying a live price
  sources?: Record<string, unknown>;
  history?: unknown;
}

export interface CompareOption {
  vehicle: string;
  label: string;
  mode: VehicleClass;
  distance_km: number;
  duration_min: number;
  duration_s: number;
  duration_model: "osrm" | "estimated" | "gtfs"; // osrm=road traffic, estimated=distance/speed, gtfs=GTFS stop_times medians
  geometry: RouteGeometry;
  stations?: { board: string; alight: string; access_km: number; egress_km: number;
               lines?: string[]; via?: string[]; transfers?: number;
               stops_ridden?: number }; // metro only
  transit?: { board_stop: string; board_km: number; alight_stop: string;
              alight_km: number; direct_routes: string[]; source: string }; // bus only — real DTC/DIMTS stop hint
  segments?: RouteSegment[];  // ~90 s spans, own dose+color each (road modes)
  hotspots?: RouteHotspot[];  // top-3 dose stretches
  legs?: unknown[]; // metro walk-metro-walk decomposition
  assumptions?: Record<string, unknown>; // metro only — model constants echoed
  exposure: Exposure;
  // added by /decide's safety-first rank (server/decide.py):
  decision_score?: number;    // 0-100, higher is better
  decision_reasons?: string[]; // plain-English, e.g. "safest mode class"
  night_black_spots?: { name: string; severity: string; dist_m: number }[];
}

export interface CompareResponse {
  options: CompareOption[]; // ranked, best first
  best?: string | null;     // vehicle key of the lowest-dose option;
                            // absent on the error path
  field?: FieldStatus;      // absent on the error path
  router_backend?: Record<string, string | null>;  // per-profile router
                            // backend: driving|cycling|walking ->
                            // osrm-local | osrm-public-demo | null
  error?: string;
}

export interface DecideResponse {
  // every field except `options` is absent on the error path, which
  // returns {"options": [], "error"} verbatim from /compare.
  options: CompareOption[]; // safety-first ranked (dose+risk+time)
  pick?: string | null;     // label of the recommended option
  best?: string | null;
  field?: FieldStatus;
  error?: string;
}

export interface DepartSlot {
  hours_ahead: number;
  start: string | null;      // ISO hour label
  dose_ug: number;
  avg_conc_ugm3: number;
}

export interface DepartResponse {
  // NOTE: every field below is absent on the error path, which returns
  // {options: [], error} — all marked optional to match the wire.
  vehicle?: string;
  mode?: VehicleClass;
  duration_min?: number;
  distance_km?: number;
  now?: DepartSlot;
  best?: DepartSlot;
  worst?: DepartSlot;
  ug_saved_vs_now?: number | null; // % less PM2.5 by leaving at best hour
  // honest name for the same percent — the ug_* key lied about its unit;
  // kept alongside until every client reads this one (claims-audit §4)
  pct_less_vs_now?: number | null;
  slots?: DepartSlot[];
  // forecast.FORECAST.status() verbatim — same block /v2/day carries
  forecast?: V2ForecastStatus;
  field?: FieldStatus;             // the live field the horizon anchors to
  field_age_s?: number | null;     // its age — the 'as of' for the curve
  // present only when the epoch-keyed cache answered — lets clients/tests
  // prove warm hits without timing the request
  served_from_cache?: boolean;
  options?: CompareOption[];       // error path emits this (empty)
  error?: string;
}

// per-segment dose breakdown — route split into ~90 s spans, each scored
// on the live field; `color` is the client paint for the polyline span
export interface RouteSegment {
  start_frac: number;
  end_frac: number;
  minutes: number;
  coords: [number, number][];
  avg_conc_ugm3: number | null;
  dose_ug: number | null;
  color: string;
}

export interface RouteHotspot {
  label: string;
  dose_ug: number | null;
  share_pct: number;          // share of the whole trip's dose
  midpoint_coord: [number, number];
  span_frac: [number, number];
}

export interface TodayResponse {
  // lat/lon/station were declared but are NOT emitted by the server —
  // marked optional to match the wire (drift found by contract sync).
  lat?: number;
  lon?: number;
  month: number;
  station?: string;
  hours_ist: (number | null)[]; // 24 medians, index = IST hour
  hour_now_ist: number;
  source?: string;              // emitted, previously undeclared
}

export interface GridResponse extends GeoJSON.FeatureCollection {
  features: (GeoJSON.Feature<GeoJSON.Polygon> & {
    properties: { pm25: number; conf: "hi" | "med" | "lo" };
  })[];
  // stamped by /grid so clients can skip re-painting an identical epoch
  properties: { cell_epoch: number[] };
}

export const ENDPOINTS = {
  health: "/health",
  search: "/search",
  route: "/route",
  compare: "/compare",
  decide: "/decide",
  depart: "/depart",
  reverse: "/reverse",
  aqi: "/aqi",
  today: "/today",
  grid: "/grid",
  // /city (v1) is the "City Breathes" editorial HTML page — text/html,
  // intentionally NOT a JSON contract surface.
} as const;

// ---------------------------------------------------------------------------
// /v2 surface (server/v2/*) — additive; v1 shapes above are unchanged.
// Wire-verified against live responses by server/tests/test_contract_sync.py.
// ---------------------------------------------------------------------------

export interface V2SearchResponse {
  q: string;
  bias: { lat: number; lon: number };
  results: Place[];
  count: number;
  t1: Place[];                  // tier-1 rows (engine named by t1_engine)
  t2: Place[];                  // tier-2 rows (Amazon Location when keyed)
  /** "ok" | "disabled:<reason>" — Amazon tier status (was BUG-T1: a
   *  duplicate "t2" dict key shadowed the row list; fixed — status moved
   *  here so t2 stays a Place[]). */
  t2_status: string;
  tiers: string[];              // ["t1"] or ["t1","t2"]
  t1_engine: string;            // alive_core | alive_core_ref | gazetteer
  took_ms: { t1: number; t2: number | null; total: number };
}

/** Every dose on the v2 wire prices the breathing-zone field —
    ambient × FIRES smoke_modifier — the same basis /aqi's pm25
    and the stays ledger count (strip-bz lane): a trip over a
    street and a stand on it must agree. `smoke_modifier` on the
    plan/strip/reroute responses is the multiplier applied. */
export interface DoseBand {
  lo: number | null;
  mid: number | null;
  hi: number | null;
  avg_conc_ugm3?: number | null;  // breathing-zone average (ambient × smoke_modifier)
  confidence?: "high" | "medium" | "low" | "none" | null;
  basis?: string | null;
  note?: string;
  /** fraction of sampled route inside the field — <1 on edge-crossing
      trips (the uncovered span is excluded, never clamped). For leg-based
      doses (transit) it is the weakest leg's coverage. */
  coverage?: number | null;
  sparse?: boolean | null;
  /** worst single-segment concentration along the option (µg/m³) —
      server emits it on every dose block (exposure.py, plan.py). */
  peak_conc?: number | null;
}

export interface EmissionBandValue {
  lo: number;
  mid: number;
  hi: number;
}

export interface EmissionBand {
  co2_kg: EmissionBandValue | null;
  pm25_g: EmissionBandValue | null;
  basis: string;
  occupancy?: number | null;
  /* provenance surface server/emissions.py emits — all optional
     (subset varies by mode/engine) */
  nox_g?: EmissionBandValue | null;
  label?: string;               // plain-English basis, e.g. "petrol car,
                                // Delhi fleet mix"
  bs_class?: string | null;     // BS bucket picked for the vehicle
  bs_options?: string[];        // buckets the caller may choose among
  confidence?: string | null;   // high | medium | low
  fuel?: string | null;
  class?: string | null;
  puc_calibrated?: boolean;     // true when live PUC data shifted the band
  puc?: Record<string, unknown> | null;
  non_exhaust?: Record<string, unknown> | null; // resuspend/brakes/tyres
                                // block — never folded into tailpipe
  breakdown?: Record<string, unknown> | null;   // moving/idle/cold split
  distance_km?: number | null;
  mode?: string | null;
  engine?: string | null;       // provenance tag, e.g.
                                // "server/emissions.py"
}

export type V2PlanTag =
  | "lightest on both"
  | "lightest for you"
  | "lightest for Delhi"
  | null;

export interface V2PlanStep {
  instruction: string;
  distance_m: number;
  lat?: number;
  lon?: number;
}

/** per-segment field pollution on a /v2/plan option — the served path
    cut into ~10-15 equal-length spans (server/v2/plan.py
    _option_segments), each carrying the breathing-zone PM2.5 read at
    its arc midpoint and the CPCB band that read lands in. Vertex-
    boundary spans share endpoints, so the painted ramp tiles the path
    without gaps. Additive: older servers omit the key and clients fall
    back to a flat route tint. */
export interface V2PlanSegment {
  geometry: RouteGeometry;      // LineString slice of the option path
  pm25: number | null;          // bz PM2.5 µg/m³ at the span midpoint;
                                // null = field can't read here
  band: string | null;          // CPCB category — "Good"…"Severe",
                                // "No data" when pm25 is null
  start_frac: number;           // span's share of the whole path [0,1]
  end_frac: number;
  dist_m: number;
}

export interface V2PlanOption {
  mode: string;                 // car|car_open|bike|auto|bus|cycle|walk|metro
  label: string;
  route_geojson: RouteGeometry;
  geometry?: RouteGeometry;     // alias of route_geojson
  segments?: V2PlanSegment[];   // per-stretch pollution for the
                              // band-coloured route ramp (additive)
  steps?: V2PlanStep[];         // turn list — client needn't call /directions
  steps_source?: string;        // osrm | amazon | transit | none
  distance_km: number | null;
  eta_s: number | null;
  freeflow_s: number | null;
  eta_model: string;            // amazon-location | osrm-freeflow | estimated | gtfs
  dose: DoseBand;
  emissions: EmissionBand;
  router_backend?: string;    // osrm rows: which router answered —
                              // osrm-local | osrm-public-demo
  tag: V2PlanTag;
  recommended: boolean;
  safest_path?: boolean;        // true on the lowest-dose option — leaf chip
  engine?: string;              // "alive_core-path" on least-inhalation engine rows
  duration_model?: string;      // engine rows: "estimated" (graph speeds)
  duration_basis?: string;      // engine rows: "freeflow" — OSM maxspeed/
                              // class speeds, no congestion feed (real
                              // Delhi traffic is slower → dose higher)
  via_names?: string[];         // engine rows: street names the path takes
  snap_m?: { from_m: number; to_m: number }; // engine rows: endpoint snap distance
  alternative_index?: number | null;  // engine rows: 1..N on corridor-diverse
                                      // least-dose alternatives; absent on the
                                      // primary route
  engine_dose_ug?: number | null;     // engine rows: inhaled µg summed over the
                                      // priced edges — the exact objective the
                                      // path minimized; server ranking keys on
                                      // it. Breathing-zone basis (ambient ×
                                      // smoke_modifier — uniform scalar, same
                                      // argmin). Display dose stays `dose` (the
                                      // raster band, one surface per response)
  reason_line: string;
  your_vehicle: boolean;
  reaches_destination?: boolean; // false when the served geometry stops
                                 // >3km short of the requested
                                 // destination (field/graph edge) —
                                 // truncated options are never
                                 // `recommended` and carry dose
                                 // confidence "low"
  truncated_gap_km?: number;    // how far short the geometry ends, km
  starts_at_origin?: boolean;   // false when the served geometry BEGINS
                                // >3km from the requested origin (the
                                // router snapped an out-of-graph point to
                                // the field edge) — same truncation class
                                // at the start; never `recommended`,
                                // dose confidence "low"
  origin_gap_km?: number;       // how far the geometry starts from the
                                // requested origin, km
  route_id: string;             // opaque, /v2/strip key, ~1 h TTL
  stations?: CompareOption["stations"]; // metro only
  /* transit legs (metro/bus via transit_v2) — absent on road modes */
  legs?: unknown[];             // per-leg board/alight/line detail
  lines?: string[] | null;
  transfers?: number | null;
  walk_m?: number | null;
  depart_at?: string | null;    // ISO timestamp
  arrive_at?: string | null;
  transit_source?: string | null;
  /* metro only: station-model honesty flags — the option is built from
     a station-to-station model, not a live GTFS timetable */
  approximate?: boolean;
  approximation?: string;
}

export interface V2PlanResponse {
  from: { lat: number; lon: number };
  to: { lat: number; lon: number };
  vehicle: string;              // canonical class the engine modelled
  vehicle_requested: string;    // raw client echo ("unicycle" stays honest)
  vehicle_profile?: Record<string, unknown> | null;
  depart_at: string | null;
  /** present whenever depart_at was sent: false = the string echoed
      verbatim but never parsed (GTFS falls back to the approx
      station model — the marker keeps that honest) */
  depart_at_parsed?: boolean;
  options: V2PlanOption[];      // recommended first when scored
  ranking: string;
  /** FIRES breathing-zone multiplier applied to every dose block —
      same number /aqi reports (1.0 = fires feed down or no burn) */
  smoke_modifier?: number;
  field: FieldStatus;
  took_ms: number;
  error?: string;               // malformed from/to path
  /** stable machine code on the error path — 'outside_service_area';
      clients key on this, never on error text. */
  code?: string;
  partial?: boolean;            // fast:true — engine rows only
  puc_calibrated?: boolean;     // server honoured the PUC card
  /** arms that timed out/cancelled/raised — e.g. ["engine"]. Absent
      arms ≠ empty arms: when present the option set is real but
      incomplete. */
  degraded?: string[];
}

export interface V2StripSample {
  lat: number;                  // 5-dp rounded
  lon: number;
  dist_m: number;
  /** breathing-zone µg/m³ (ambient × smoke_modifier) — same basis
      /aqi's pm25 serves, so the live counter and the stays ledger
      read one field */
  pm25: number | null;
  lo: number | null;
  hi: number | null;
}

export interface V2StripRoad {
  name: string;               // OSRM step street; "unnamed road" when blank
  dist_m: number;             // chunk-overlap metres attributed to the road
  samples: number;            // chunks touching the road's spans
  avg_pm25: number | null;    // distance-weighted; null = nothing sampled
  dose_share: number | null;  // fraction of the strip's sampled dose
}

export interface V2StripResponse {
  route_id: string;
  mode: string;
  vehicle?: Record<string, unknown> | null;
  route_age_s?: number | null;
  step_m: number;               // 250
  samples: V2StripSample[];
  roads?: V2StripRoad[];        // [] when the route record carried no steps
  emissions_curve: Record<string, unknown>;
  /** breathing-zone multiplier baked into every sample's pm25 */
  smoke_modifier?: number;
  field: FieldStatus;
  // 404 path emits {error, detail}:
  error?: string;
  detail?: string;
}

export interface V2RerouteResponse {
  // POST /v2/reroute — fresh option set from the current fix, plus the
  // selected option flattened to top level AND under `option`. Only
  // route_id/options/error ship on every path (incl. the early
  // {"route_id": null, "options": [], "error"} validation failures).
  route_id: string | null;      // fresh ~1 h-TTL key; null on routing-fail
  options: V2PlanOption[];      // full ranked set; [] on every error path
  rerouted_from?: string | null;
  from_fix?: { lat: number; lon: number };
  to?: { lat: number; lon: number };
  vehicle?: string;
  // flattened selected option (mode hint matched, else ranked winner):
  geometry?: RouteGeometry;
  route_geojson?: RouteGeometry;
  eta_s?: number | null;
  duration_s?: number | null;   // alias of eta_s
  distance_km?: number | null;
  steps?: V2PlanStep[];
  segments?: V2PlanSegment[] | null; // same paint strip as the option rows
  dose?: DoseBand;
  emissions?: EmissionBand;
  mode?: string;
  option?: V2PlanOption | null;
  // when the selected continuation is motorized and the remaining leg
  // is walkable (<=1.5 km), the real least-dose walk option's numbers —
  // the "park and finish on foot" honesty check
  finish_on_foot?: { distance_km: number; eta_s: number;
                     dose: DoseBand | null; route_id: string };
  smoke_modifier?: number;      // same bz basis as /v2/plan
  /** same marker as /v2/plan — present whenever depart_at was sent;
      false = the departure string never parsed */
  depart_at_parsed?: boolean;
  field?: FieldStatus;
  took_ms?: number;
  error?: string;
}

export interface V2ReachResponse {
  // GET /v2/reach?lat&lon&mode&budget_ug — the dose-budget reachable
  // region ("where your lungs can go inside today's µg budget"): a
  // bounded Dijkstra over the same directed-edge-state expansion as
  // the least-dose engine, settling every edge whose dose stays inside
  // the budget. The veil is the real settled edge set, never a
  // smoothed region.
  from: { lat: number; lon: number };
  mode: string;                 // resolved engine mode (unknown → "car")
  budget_ug: number;            // dose budget actually applied (>=0)
  snap_m: number | null;        // origin snap distance; null on early errors
  // settled road-edge polylines, flat micro-degree ints [lon,lat,...]
  // — the graph's native coord format; when edge_count exceeds the
  // serve cap the served set is a uniform stride across settle order
  // (dose bands sampled evenly, full reachable extent painted)
  edges_e6: number[][];
  edge_count: number;           // settled undirected edges (>= edges_e6.len)
  edge_partial: boolean;        // true when the veil was payload-sliced
  expanded: number;             // directed edge states the Dijkstra settled
  nodes: number;                // distinct graph nodes reached (incl. origin)
  distance_km: number;          // summed length of settled edges
  frontier_budget_ug: number;   // max settled dose — <= budget_ug
  truncated: boolean;           // true when the ~2M-state cap cut the search
  field_age_s: number | null;
  took_ms: number;
  error?: string;
  // typed rejection: outside_service_area | engine_unavailable |
  // no_snap | bad_request | timeout
  code?: string;
}

export interface V2TripRequest {
  device_token?: string;        // opaque; hashed server-side, never stored
  summary?: { mode?: string; distance_km?: number; duration_s?: number;
              dose_ug?: number; co2_kg_mid?: number; pm25_g_mid?: number;
              switched?: boolean };
  trajectory?: ([number, number] | { lat: number; lon: number })[];
  coords?: ([number, number] | { lat: number; lon: number })[];
}

export interface V2TripResponse {
  stored: boolean;
  cells_traversed: number;
  points_used: number;
  privacy: {
    endpoint_trim_m: number;    // 300
    thin_m: number;             // 100
    rounded_decimals: number;   // 4
    cell_scheme: string;        // "h3:8"
    trimmed_start_m: number;
    trimmed_end_m: number;
    raw_trajectory: string;
  };
  ts: number;
  ledger_recorded?: boolean;    // false when no device_token was supplied
  deduplicated?: boolean;       // true when an identical donation replayed
}

export interface V2LedgerTrip {
  ts: number;                   // epoch seconds of the donation
  mode?: string;
  distance_km?: number;
  duration_s?: number;
  dose_ug?: number;
  co2_kg_mid?: number;
  pm25_g_mid?: number;
  switched?: boolean;
}

export interface V2LedgerResponse {
  trips: V2LedgerTrip[];        // newest first, per-device rows only
  totals: { trips: number; km: number; dose_ug: number;
            co2_kg_mid: number; pm25_g_mid: number };
  devices_tracked: number;
  privacy: string;
  token_via?: "query";          // present only on the deprecated ?token=
                                // back-compat path — X-Device-Token header
                                // is the supported transport
}

export interface V2Place {
  id: string;
  name: string;
  subtitle: string;
  lat: number;
  lon: number;
  kind: string;
  source: string;
  error?: string;               // 404 path emits {"error": "unknown place id"}
}

export interface V2Band { lo: number | null; mid: number | null; hi: number | null }

export interface V2CityCorridor {
  cell: string;
  name: string | null;
  lat: number;
  lon: number;
  trips: number;
  devices: number;
  avg_dose_ug: number;
  /* g CO2 per 100 m of corridor — null when no crossing trip carried
     a co2 figure (never a fake zero) */
  co2_g_per_100m?: number | null;
  relative: "heavier" | "lighter";
}

export interface V2CityResponse {
  ts: number;
  generated_at?: string;
  /** Payload-cache disclosure — seconds since this body was built
      (same contract as V2DistrictsResponse.cached_s). The endpoint
      serves a 60 s payload cache keyed on its inputs; 0.0 = built
      for this request. */
  cached_s: number;
  /** "Why tonight" — the one-line causal read of the city's air plus
      the drivers that cleared the bar (fires only when the wind
      carries them in; stagnation/trend from the field's own record).
      Null when the explainer can't run — the hero figure stands alone
      before it guesses. Full detail: GET /v2/why. */
  why?: { line: string | null;
          /** The parali/news line — the belt's fires + carrying wind +
              the day's drivers in plain words, every figure a measured
              field (measured-data-as-news; no external feed exists that
              is both free and licensable). `cause_note_fields` is the
              ingredient set a client re-localizes from. */
          cause_note?: string | null;
          cause_note_fields?: Record<string, unknown> | null;
          drivers: { kind: string; weight: string; score: number;
                     evidence: string }[];
          why_url: string } | null;
  pm25_stats: Record<string, unknown>;
  /** Field-mean stats per extra species over the same NCR lattice —
      a species is omitted (not nulled) when the serving field has
      no data for it. Keys are open-meteo names. */
  species?: Record<string, { mean: number; median: number; max: number;
                             n: number }>;
  /** Decade-climatology at the city centroid (openaq-data-archive,
      ~9M measured station-hours): median/p25/p75 for this month+hour
      and the live-vs-typical delta. Omitted when the archive or the
      live mean is unavailable — never a guess. */
  typical?: { month: number; hour_ist: number; median: number;
              p25?: number | null; p75?: number | null;
              vs_now_pct?: number | null } | null;
  /** Next 12 hourly PM2.5 forecast at the city centroid — live-anchored
      CAMS horizon (same model /depart uses). Null when the forecast
      field is cold. */
  next_hours?: { h: number; start: string | null; pm25: number }[] | null;
  breath?: {
    pm25_ugm3: V2Band;
    day_inhaled_ug: V2Band;
    cigarettes: V2Band;
    n_points: number;
    basis: string;
  } | null;
  field: FieldStatus;
  field_age_s: number | null;
  freshness?: { field_age_s: number | null; age_min: number | null;
                label: "live" | "stale" | "unknown" };
  provenance?: {
    model: { name: string; source: string; samples: number; up: boolean };
    stations: { count: number; live: boolean; note: string };
    trips: { publishable_corridors: number; cells_tracked: number;
             window_h: number; k_min: number };
  };
  corridors?: V2CityCorridor[];
  enough_data?: boolean;
  /** GRAP-equivalent of the live field summary — the CAQM stage the
      city's air maps to under the rules (computed from pm25_stats.mean,
      never the official declaration). Absent when the field is cold —
      no stage is claimed. */
  grap?: V2Grap;
  wind: Record<string, unknown>;
  sources: Record<string, { up: boolean; [k: string]: unknown }>;
  trips: { days: Record<string, unknown>;
           /** the UTC day the store keys itself on — served so the page
               never keys 'today' on the last populated day */
           today_key?: string;
           /** days[today_key] or null when nothing was shared today —
               the honest-empty state, never an older day's numbers */
           today?: Record<string, unknown> | null;
           cells_tracked: number;
           corridors_publishable: number };
}

// --- GET /v2/city/moves — "how Delhi moves" aggregate view -----------------
// Aggregates only (TripAggregates store): day counters + publishable
// corridor cells. Every emitted row clears k>=3; a mode below threshold
// pools into "other" (itself k-gated) or ships as a suppressed count.
// n_trips < min_k → insufficient_data: true — counts still ship, no
// distribution is drawn from them.
export interface V2MovesBand {
  p25: number;
  p50: number;
  p75: number;
  n: number;                    // qualifying rows behind the band
}

export interface V2CityModeShare {
  mode: string;                 // server mode id or pooled "other"
  trips: number;                // >= min_k on every row
  share: number;                // trips / n_trips
}

export interface V2MovesWindow {
  days: number;                 // trailing UTC day buckets (server: 7)
  from: string;                 // ISO date
  to: string;
}

export interface V2MovesCorridors {
  window_h: number;             // corridor rule's own window (server: 72)
  active: number;               // publishable cells right now
  tracked: number;              // every cell ever seen
  avg_dose_ug: V2MovesBand | null; // per-cell mean-dose distribution
  /* g CO2 per 100 m of corridor — band over cells whose trips carried
     co2; null when none did (never a fake zero) */
  co2_g_per_100m: V2MovesBand | null;
}

export interface V2MovesPerTrip {
  n_days: number;               // qualifying days (>= min_k trips)
  dose_ug: V2MovesBand | null;
  co2_kg: V2MovesBand | null;
  pm25_g: V2MovesBand | null;
  basis: string;
}

export interface V2CityMovesResponse {
  ts: number;
  generated_at: string;         // ISO-8601 UTC
  window: V2MovesWindow;
  min_k: number;                // 3
  n_trips: number;
  n_days: number;
  insufficient_data: boolean;   // n_trips < min_k
  mode_share: V2CityModeShare[];
  mode_share_suppressed_trips: number;
  corridors: V2MovesCorridors;
  per_trip: V2MovesPerTrip;
  basis: string;
}

/* /v2/districts — district/subdistrict AQI choropleth. Field rollup of
   the live field over NCR districts; ages are honest (field_age_s,
   cached_s), geojson keys are relative paths to the shape endpoints. */
export interface V2DistrictRow {
  name: string;
  state: string;
  level: string;                // "district" | "subdistrict"
  parent: string | null;
  partial_field_coverage: boolean;
  cells_covered: number;
  pm25: number | null;
  confidence: string;           // "field" | "sparse" | "none"
  /* sparse districts (<3 covered cells) read the field at their
     centroid — centroid_read: true marks that path so the client can
     badge it honestly */
  centroid_read?: boolean;
  aqi: number | null;
  aqi_us: number | null;
  category: string;
  color: string;
}

export interface V2DistrictsResponse {
  districts: V2DistrictRow[];
  bands: { min: number; max: number; category: string;
           color: string }[];   // CPCB scale legend
  geojson: string;              // path → /ncr.geojson
  subdistrict_geojson: string;  // path → /delhi_subdistricts.geojson
  scale: string;                // "cpcb"
  field_age_s: number | null;
  ts: number;
  cached_s: number;
}

/* /v2/day — the morning card's day-at-a-point (docs/plan/alive-depth.md
   L2). The remaining hours of the current IST day from the live-anchored
   CAMS horizon (same model as /depart and /grid?h=), folded into the
   day's heavy stretch + cleanest slot and the one decision each window
   changes. Flat days say so; slots with no model value are skipped. */
export interface V2DayHour {
  h: number;                    // hours ahead (slot index into hours[])
  start: string | null;         // ISO UTC slot start (forecast's own label)
  ist_label: string;            // "17:30" — slot start on the Delhi clock
  pm25_mid: number;             // anchored CAMS x stagnation, ug/m3
  pm25_lo: number | null;       // krige-sigma band now, blended toward the
  pm25_hi: number | null;       // hour's climatological IQR as the ~9h
                                // live-anchor decays; null = no honest band
  us_aqi: number | null;        // US-EPA projection (same def as /aqi)
  band: string;                 // CPCB category of pm25_mid
  confidence: "hi" | "med" | "lo"; // anchor-decay grade; 'med' cap without
                                // a krige band at the point
}

export interface V2DayWindow {
  start_h: number;              // h of the window's first hour
  end_h: number | null;         // null = still open at day's last hour
  start_label?: string;         // IST clock label of window start
  end_label?: string | null;    // IST clock label of window end
  pm25_mid?: number;            // window mean ug/m3
  basis: string;                // why this run qualified (real numbers)
}

export interface V2DayDecision {
  label: string;                // "outdoor exercise" | "kids outdoors" | ...
  line: string;                 // one honest line generated from the windows
}

// forecast.FORECAST.status() verbatim — emitted by /v2/day (and matches
// the inline forecast block on DepartResponse).
export interface V2ForecastStatus {
  aq_points: number;              // CAMS grid points fetched
  met_points: number;             // met grid points (may be 0)
  hours: number;                  // hourly slots in the horizon
  age_s: number | null;           // seconds since the forecast fetch
  fetched_at: string | null;      // the fetch instant itself, ISO UTC —
                                  // 'as of' for days-ahead cards
  live_anchor: { enabled: boolean; source: string | null;
                 tau_h: number; max_age_s: number };
}

/* The GRAP-equivalent block emitted beside a served PM2.5 field mean —
   which CAQM stage that air maps to under the legally binding rules
   (CAQM 'Comprehensively revised GRAP Schedule' for NCR: stage triggers
   are Delhi's CPCB national AQI — I 201-300, II 301-400, III 401-450,
   IV >450). The stage is computed through districts.cpcb_aqi — the one
   PM2.5→AQI formula the whole API shares — so surfaces can't disagree.
   equivalent_stage 0 = below the Stage-I floor, a real answer; the key
   itself is absent when no field value exists to map. */
export interface V2Grap {
  equivalent_stage: number;   // 0-4 — stage the served air maps to
  aqi: number;                // CPCB national AQI of the served pm2.5 mean
  basis: string;              // which mean the aqi was computed over
  note: string;               // "computed from today's air, not the
                              //  official CAQM declaration"
}

export interface V2DayResponse {
  lat: number;
  lon: number;
  date_ist: string;             // the IST civil date the hours belong to
  tz: string;                   // "Asia/Kolkata"
  hours: V2DayHour[];           // remaining slots of the IST day
  now_idx: number | null;       // index into hours of the slot holding now
  day_mean_pm25: number | null; // mean of served mids
  heavy_window: V2DayWindow | null;   // today's contiguous heavy stretch
  cleanest_window: V2DayWindow | null;// the best contiguous run
  decisions: V2DayDecision[];   // <=3 lines, data-generated; flat days say so
  model: string;                // honesty string — CAMS + stagnation, anchored
  band_basis: string;           // how pm25_lo/hi were derived
  field_age_s: number | null;   // live-field age (seconds)
  field: FieldStatus;
  forecast?: V2ForecastStatus;
  /** GRAP-equivalent of the served day — computed from day_mean_pm25.
      Absent on the cold/error path (hours: []), never a claimed stage. */
  grap?: V2Grap;
  error?: string;               // "outside service area…" / "forecast
                                //  unavailable" paths emit hours: []
}

/* /v2/outlook — the morning card's honest companion: the days ahead,
   inside the REAL forecast horizon. CAMS serves 120 h, so the fold is
   today's remainder plus up to 4 more IST days — the last is often a
   sliver, labeled partial, never padded into a week. Same anchored
   model + band machinery as /v2/day, folded per day. */
export interface V2OutlookDay {
  date_ist: string;             // IST civil date this row folds
  label: string;                // "today" | "tomorrow" | weekday name
  partial: boolean;             // fewer than the day's 24 slots served
                                // (today's remainder, or the horizon's
                                // last-day sliver) — never padded
  n_hours: number;              // hourly slots folded into this day
  pm25_mid: number;             // day mean of served hourly mids
  pm25_lo: number | null;       // day mean ± the mean of its hours' band
  pm25_hi: number | null;       // halves (krige→climatology blend; no
                                // sqrt-n narrowing — errors correlate);
                                // null when no band source exists
  band: string;                 // modal CPCB category — the day's character
  heavy_hours_ist: string[];    // IST start-labels of every hour ≥ mean
                                // +¼·spread; [] on flat days (noise, not
                                // a stretch — same rule as the card)
  cleanest_window: V2DayWindow | null;  // best contiguous ≥2h run below
                                        // mean −¼·spread; null on flat
                                        // or <3h days
  confidence: "hi" | "med" | "lo";      // anchor-decay grade at the day's
                                        // mid-horizon — 'lo' where raw
                                        // CAMS leads (day-4 says so)
  anchor_w: number;             // the day's anchor weight (e-fold) itself
  note?: string;                // plain caveat on lo-confidence days
}

export interface V2OutlookBestDay {
  date_ist: string;
  label: string;                // "today" | "tomorrow" | weekday
  pm25_mid: number;             // lowest day-mean on the horizon
  n_hours: number;
  partial: boolean;
  delta_vs_mean: number;        // day-mean minus horizon mean (negative)
  line: string;                 // "wednesday looks least-bad — avg ~120
                                // vs ~210 ug/m3 across the horizon"
}

export interface V2OutlookResponse {
  lat: number;
  lon: number;
  tz: string;                   // "Asia/Kolkata"
  generated_ist: string;        // ISO instant the fold was computed
  horizon_days: number;         // day rows served (≤5 — the real reach)
  horizon_hours: number;        // hourly slots folded across all days
  days: V2OutlookDay[];
  best_day: V2OutlookBestDay | null;  // null on a flat horizon — the
                                      // verdict then says so instead
  flat: boolean;                // every day within noise of the rest
  verdict: string;              // one honest sentence either way
  model: string;                // same model string /v2/day carries
  band_basis: string;           // hour-band basis + the per-day fold rule
  field_age_s: number | null;
  field: FieldStatus;
  forecast?: V2ForecastStatus;
  error?: string;               // "outside service area…" / "forecast
                                //  unavailable" paths emit days: []
}

export const V2_ENDPOINTS = {
  search: "/v2/search",
  districts: "/v2/districts",
  place: "/v2/place",
  reverse: "/v2/reverse",
  plan: "/v2/plan",
  reroute: "/v2/reroute",
  strip: "/v2/strip",
  trip: "/v2/trip",
  city: "/v2/city",
  city_moves: "/v2/city/moves",
  day: "/v2/day",
  outlook: "/v2/outlook",
  ledger: "/v2/ledger",
  // /v2/today and /v2/depart are wire aliases for the v1 handlers —
  // same shapes as /today and /depart above, surfaced under the v2
  // prefix for symmetry with the rest of the v2 surface.
  today: "/v2/today",
  depart: "/v2/depart",
} as const;

export type TravelMode = "driving" | "cycling" | "walking";
export type VehicleClass =
  | "driving_car_ac" | "driving_car_open" | "driving_two_wheeler"
  | "auto_rickshaw" | "bus" | "metro" | "cycling" | "walking";
