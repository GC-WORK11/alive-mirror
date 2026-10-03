/** Shared shell types — the /search, /decide, /depart, /directions payloads. */
export type Place = { name: string; subtitle: string; lat: number; lon: number; outside_ncr?: boolean };

export type Exposure = {
  dose_ug: number | null;
  avg_conc_ugm3: number | null;
  peak_conc?: number | null;
  confidence: "high" | "medium" | "low" | "none";
  coverage?: number;
  factors?: { microenv: number | string; ventilation_lpm: number | string; road_uplift: number | string };
  dose_vs_best_pct?: number;
  ug_saved_vs_worst?: number;
};

export type Seg = {
  start_frac: number; end_frac: number; dose_ug: number | null;
  avg_conc_ugm3: number | null; color: string; coords: number[][];
};

export type CompareOption = {
  decision_score?: number;
  decision_reasons?: string[];
  vehicle: string;
  label: string;
  distance_km: number;
  duration_min: number;
  duration_s?: number;
  duration_model?: "osrm" | "estimated" | "gtfs";
  geometry: GeoJSON.Geometry;
  stations?: { board: string; alight: string };
  segments?: Seg[];
  hotspots?: { share_pct: number; midpoint_coord: number[] }[];
  exposure?: Exposure;
};

export type Depart = {
  best: { hours_ahead: number; start: string | null; dose_ug: number };
  ug_saved_vs_now: number | null;
} | null;

export type Step = { instruction: string; distance_m: number; type?: string };
