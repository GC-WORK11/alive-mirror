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

export interface RouteResult {
  distance_km: number;
  duration_min: number;
  geometry: RouteGeometry;
}

export interface RouteResponse {
  routes: RouteResult[];
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
} as const;

export type TravelMode = "driving" | "cycling" | "walking";
