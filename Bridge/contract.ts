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
  match?: "exact-prefix" | "token-prefix" | "fuzzy" | "other";
  match_rank?: number;
  score?: number;               // gazetteer ranking score (T1 rows)
  cov?: number;                 // SearchIndex token-coverage ratio (T1)
  fuzzy?: boolean;              // SearchIndex DL-only match flag (T1)
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
  station_readings?: number;       // live station readings blended — 0 = dark
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
  error?: string;
}

export interface AqiResponse {
  pm25: number | null;
  pm10?: number | null;
  no2?: number | null;
  nearest_sample_km?: number;
  smoke_modifier?: number;         // fire-season multiplier (1.0 = none)
  field?: FieldStatus;             // absent on the "field unavailable" path
  error?: string;
  // emitted on wire, previously undeclared:
  pm25_ambient?: number;
  pm25_lo?: number | null;
  pm25_hi?: number | null;
  us_aqi?: number | null;
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
  slots?: DepartSlot[];
  forecast?: { aq_points: number; met_points: number; hours: number;
               age_s: number | null };
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

export interface DoseBand {
  lo: number | null;
  mid: number | null;
  hi: number | null;
  avg_conc_ugm3?: number | null;
  confidence?: "high" | "medium" | "low" | "none" | null;
  basis?: string | null;
  note?: string;
  /** fraction of sampled route inside the field — <1 on edge-crossing
      trips (the uncovered span is excluded, never clamped). For leg-based
      doses (transit) it is the weakest leg's coverage. */
  coverage?: number | null;
  sparse?: boolean | null;
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

export interface V2PlanOption {
  mode: string;                 // car|car_open|bike|auto|bus|cycle|walk|metro
  label: string;
  route_geojson: RouteGeometry;
  geometry?: RouteGeometry;     // alias of route_geojson
  steps?: V2PlanStep[];         // turn list — client needn't call /directions
  steps_source?: string;        // osrm | amazon | transit | none
  distance_km: number | null;
  eta_s: number | null;
  freeflow_s: number | null;
  eta_model: string;            // amazon-location | osrm-freeflow | estimated | gtfs
  dose: DoseBand;
  emissions: EmissionBand;
  tag: V2PlanTag;
  recommended: boolean;
  reason_line: string;
  your_vehicle: boolean;
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
}

export interface V2PlanResponse {
  from: { lat: number; lon: number };
  to: { lat: number; lon: number };
  vehicle: string;              // canonical class the engine modelled
  vehicle_requested: string;    // raw client echo ("unicycle" stays honest)
  vehicle_profile?: Record<string, unknown> | null;
  depart_at: string | null;
  options: V2PlanOption[];      // recommended first when scored
  ranking: string;
  field: FieldStatus;
  took_ms: number;
  error?: string;               // malformed from/to path
  /** stable machine code on the error path — 'outside_service_area';
      clients key on this, never on error text. */
  code?: string;
}

export interface V2StripSample {
  lat: number;                  // 5-dp rounded
  lon: number;
  dist_m: number;
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
  dose?: DoseBand;
  emissions?: EmissionBand;
  mode?: string;
  option?: V2PlanOption | null;
  field?: FieldStatus;
  took_ms?: number;
  error?: string;
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
  relative: "heavier" | "lighter";
}

export interface V2CityResponse {
  ts: number;
  generated_at?: string;
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
  wind: Record<string, unknown>;
  sources: Record<string, { up: boolean; [k: string]: unknown }>;
  trips: { days: Record<string, unknown>;
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

export const V2_ENDPOINTS = {
  search: "/v2/search",
  place: "/v2/place",
  reverse: "/v2/reverse",
  plan: "/v2/plan",
  reroute: "/v2/reroute",
  strip: "/v2/strip",
  trip: "/v2/trip",
  city: "/v2/city",
  city_moves: "/v2/city/moves",
  ledger: "/v2/ledger",
} as const;

export type TravelMode = "driving" | "cycling" | "walking";
export type VehicleClass =
  | "driving_car_ac" | "driving_car_open" | "driving_two_wheeler"
  | "auto_rickshaw" | "bus" | "metro" | "cycling" | "walking";
