/** Shared shell types — /v2/plan payloads plus the legacy /depart +
 *  /directions shapes still in use (see server/v2/plan.py). */
export type Place = { name: string; subtitle: string; lat: number; lon: number; outside_ncr?: boolean };

/** Every estimate is an honest band {lo,mid,hi} — never a point value
 *  (docs/plan/06 §2, claims ledger: per-vehicle truth is unknowable). */
export type Band = { lo: number | null; mid: number | null; hi: number | null };

/** Inhaled-dose band from the live field (server exposure.dose). */
export type DoseBand = Band & {
  avg_conc_ugm3?: number | null;
  confidence?: string | null;    // "high" | "medium" | "low" | "none"
  basis?: string | null;         // e.g. "est." — jargon lives in details only
  note?: string | null;          // e.g. "dose engine unavailable"
  /** fraction of sampled route inside the field — <1 on edge-crossing
      trips; the uncovered span is excluded, never clamped */
  coverage?: number | null;
  sparse?: boolean | null;
};

/** Trip emissions — tailpipe bands + provenance. Two payload flavours:
 *  the fallback table (basis = human string) and emissions.py
 *  (basis = "per_vkm"/"per_pax_km", label = the human string). */
export type Emissions = {
  co2_kg: Band | null;
  pm25_g?: Band | null;
  nox_g?: Band | null;
  label?: string | null;         // "estimated for vehicles like yours (…)"
  basis?: string | null;
  occupancy?: number | null;     // per-passenger divisor on shared modes
  bs_class?: string | null;
  bs_options?: string[] | null;
  confidence?: string | null;
  non_exhaust?: { pm10_g?: Band | null; note?: string } | null;
};

/** One ranked option from POST /v2/plan (server/v2/plan.py `rank_options`).
 *  `vehicle`, `duration_min`, `geometry` mirror the legacy /decide fields so
 *  transition-era consumers (NavChrome, vehicleGlyph) compile unchanged. */
export type V2Option = {
  mode: string;                       // car | car_open | bike | auto | bus | metro | cycle | walk
  vehicle: string;                    // == mode; legacy field name kept for NavChrome/ui
  label: string;                      // server display label, e.g. "Car (AC)"
  eta_s: number | null;
  freeflow_s?: number | null;
  eta_model?: string | null;          // "amazon-location" | "osrm-freeflow" | "gtfs" | "estimated"
  duration_min: number;               // derived: eta_s / 60
  distance_km: number | null;
  dose: DoseBand;
  emissions: Emissions;
  tag: string | null;                 // "lightest on both" | "lightest for you" | "lightest for Delhi"
  recommended: boolean;               // doc 06 §4 winner
  reason_line: string;                // server one-liner under the row
  route_id?: string | null;           // for GET /v2/strip (nav lane)
  your_vehicle?: boolean;             // matches the declared S8 class
  geometry: GeoJSON.Geometry | null;  // mapped from `route_geojson`
  stations?: { board: string; alight: string } | null;
  steps?: Step[] | null;              // only if a future payload inlines them
  segments?: Seg[];                   // legacy colour-per-segment strip — kept as a seam
};

/** Legacy name kept for files outside this lane (NavChrome.tsx). */
export type CompareOption = V2Option;

export type Seg = {
  start_frac: number; end_frac: number; dose_ug: number | null;
  avg_conc_ugm3: number | null; color: string; coords: number[][];
};

export type Depart = {
  best: { hours_ahead: number; start: string | null; dose_ug: number };
  ug_saved_vs_now: number | null;
} | null;

export type Step = { instruction: string; distance_m: number; type?: string };

/** Top-level POST /v2/plan response. */
export type PlanResult = {
  options: V2Option[];
  field: { source?: string; age_s?: number | null; samples?: number } | null;
  vehicle?: string;
  error?: string;
};
