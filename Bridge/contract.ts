// Shared wire contract between Mobile/ apps and server/.
// Source of truth for API shapes; behavior lives in server/main.py.

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
  microenv: number;        // in-vehicle/ambient ratio (published, per mode)
  ventilation_lpm: number; // breathing rate L/min
  road_uplift: number;     // near-road multiplier applied
}

export interface Exposure {
  dose_ug: number | null;          // PM2.5 mass inhaled this trip
  avg_conc_ugm3: number | null;    // breathing-zone average
  peak_conc: number | null;
  confidence: "high" | "medium" | "low" | "none";
  coverage: number;                // fraction of route with field data
  sparse: boolean;
  factors: ExposureFactors;
  dose_vs_best_pct?: number;
  ug_saved_vs_worst?: number;
}

export interface RouteResult {
  mode: TravelMode;
  distance_km: number;
  duration_min: number;
  geometry: RouteGeometry;
  exposure: Exposure;
}

export interface FieldStatus {
  source: string;
  samples: number;
  age_s: number | null;
  // emitted on wire, previously undeclared:
  station_readings?: number;
  wind?: Record<string, unknown>;
  kriging?: string;            // "on" | "idw"
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
  lat?: number;                  // server emits {name, subtitle} only —
  lon?: number;                  // lat/lon were declared but never sent
  subtitle?: string;
  distance_m?: number;           // /v2/reverse only
  source?: string;               // /v2/reverse only
}

export interface HealthResponse {
  ok: boolean;
  ts: number;
  // emitted on wire, previously undeclared:
  version?: string;
  build_sha?: string;
  field_age_s?: number | null;
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
  exposure: Exposure;
}

export interface CompareResponse {
  options: CompareOption[]; // ranked, best first
  best?: string | null;     // vehicle key of the lowest-dose option;
                            // absent on the error path
  field?: FieldStatus;      // absent on the error path
  error?: string;
}

export interface DecideResponse {
  options: CompareOption[]; // safety-first ranked (dose+risk+time)
  pick: string | null;      // label of the recommended option
  best: string | null;
  field: FieldStatus;
  error?: string;
}

// CompareOption gains, when served via /decide:
//   decision_score?: number    // 0-100, higher is better
//   decision_reasons?: string[] // plain-English, e.g. "safest mode class"

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
  depart: "/depart",
  reverse: "/reverse",
  aqi: "/aqi",
  today: "/today",
  grid: "/grid",
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
}

export interface V2StripSample {
  lat: number;                  // 5-dp rounded
  lon: number;
  dist_m: number;
  pm25: number | null;
  lo: number | null;
  hi: number | null;
}

export interface V2StripResponse {
  route_id: string;
  mode: string;
  vehicle?: Record<string, unknown> | null;
  route_age_s?: number | null;
  step_m: number;               // 250
  samples: V2StripSample[];
  emissions_curve: Record<string, unknown>;
  field: FieldStatus;
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
}

export interface V2Place {
  id: string;
  name: string;
  subtitle: string;
  lat: number;
  lon: number;
  kind: string;
  source: string;
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

export const V2_ENDPOINTS = {
  search: "/v2/search",
  place: "/v2/place",
  reverse: "/v2/reverse",
  plan: "/v2/plan",
  strip: "/v2/strip",
  trip: "/v2/trip",
  city: "/v2/city",
} as const;

export type TravelMode = "driving" | "cycling" | "walking";
export type VehicleClass =
  | "driving_car_ac" | "driving_car_open" | "driving_two_wheeler"
  | "auto_rickshaw" | "bus" | "metro" | "cycling" | "walking";
