// Shared wire contract between Mobile/ apps and server/.
// Source of truth for API shapes; behavior lives in server/main.py.

export interface Place {
  name: string;
  subtitle: string;
  lat: number;
  lon: number;
  kind?: string;
}

export interface SearchResponse {
  results: Place[];
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
}

export interface RouteResponse {
  routes: RouteResult[];
  field: FieldStatus;
}

export interface AqiResponse {
  pm25: number | null;
  pm10?: number | null;
  no2?: number | null;
  nearest_sample_km?: number;
  smoke_modifier?: number;         // fire-season multiplier (1.0 = none)
  field: FieldStatus;
  error?: string;
}

export interface ReverseResponse {
  name: string;
  lat: number;
  lon: number;
}

export interface HealthResponse {
  ok: boolean;
  ts: number;
}

export interface CompareOption {
  vehicle: string;
  label: string;
  mode: VehicleClass;
  distance_km: number;
  duration_min: number;
  duration_s: number;
  duration_model: "osrm" | "estimated"; // honest flag: non-car times are distance/speed
  geometry: RouteGeometry;
  stations?: { board: string; alight: string; access_km: number; egress_km: number }; // metro only
  segments?: RouteSegment[];  // ~90 s spans, own dose+color each (road modes)
  hotspots?: RouteHotspot[];  // top-3 dose stretches
  legs?: unknown[]; // metro walk-metro-walk decomposition
  exposure: Exposure;
}

export interface CompareResponse {
  options: CompareOption[]; // ranked, best first
  best: string | null;      // vehicle key of the lowest-dose option
  field: FieldStatus;
  error?: string;
}

export interface DepartSlot {
  hours_ahead: number;
  start: string | null;      // ISO hour label
  dose_ug: number;
  avg_conc_ugm3: number;
}

export interface DepartResponse {
  vehicle: string;
  mode: VehicleClass;
  duration_min: number;
  distance_km: number;
  now: DepartSlot;
  best: DepartSlot;
  worst: DepartSlot;
  ug_saved_vs_now: number | null; // % less PM2.5 by leaving at best hour
  slots: DepartSlot[];
  forecast: { aq_points: number; met_points: number; hours: number; age_s: number | null };
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
  lat: number;
  lon: number;
  month: number;
  station: string;
  hours_ist: (number | null)[]; // 24 medians, index = IST hour
  hour_now_ist: number;
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

export type TravelMode = "driving" | "cycling" | "walking";
export type VehicleClass =
  | "driving_car_ac" | "driving_car_open" | "driving_two_wheeler"
  | "auto_rickshaw" | "bus" | "metro" | "cycling" | "walking";
