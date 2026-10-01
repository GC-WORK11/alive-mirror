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

export const ENDPOINTS = {
  health: "/health",
  search: "/search",
  route: "/route",
  reverse: "/reverse",
  aqi: "/aqi",
} as const;

export type TravelMode = "driving" | "cycling" | "walking";
export type VehicleClass =
  | "driving_car_ac" | "driving_car_open" | "driving_two_wheeler"
  | "auto_rickshaw" | "bus" | "metro" | "cycling" | "walking";
