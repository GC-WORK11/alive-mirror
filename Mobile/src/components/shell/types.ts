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

/** emissions.py `breakdown` — where the ride CO2 actually came from,
 *  all values in grams (`units_g_except_co2_g`: the *_mid dicts carry
 *  co2/pm25/nox; we keep only the co2 mids the trip-donation split
 *  needs). Absent for metro/walk/cycle options. */
export type EmissionsBreakdown = {
  moving_mid?: { co2?: number | null } | null;
  idle_mid?: { co2?: number | null } | null;
  cold_extra_mid?: { co2?: number | null } | null;
} | null;

/** Trip emissions — tailpipe bands + provenance. Two payload flavours:
 *  the fallback table (basis = human string) and emissions.py
 *  (basis = "per_vkm"/"per_pax_km", label = the human string). */
export type Emissions = {
  co2_kg: Band | null;
  pm25_g?: Band | null;
  nox_g?: Band | null;
  breakdown?: EmissionsBreakdown;
  label?: string | null;         // "estimated for vehicles like yours (…)"
  basis?: string | null;
  occupancy?: number | null;     // per-passenger divisor on shared modes
  bs_class?: string | null;
  bs_options?: string[] | null;
  confidence?: string | null;
  fuel?: string | null;          // resolved fuel (petrol|diesel|cng|electric)
  class?: string | null;         // resolved class (car|bike|auto|…) — lets the
                                 // client rebuild `label` in the user's language
  puc_calibrated?: boolean | null; // tuned to the user's PUC certificate
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
  /** server flag on the least-inhalation route (dose-optimized variant
   *  when the path engine ships) — the headline "safest route" chip. */
  safest_path?: boolean | null;
  recommended: boolean;               // doc 06 §4 winner
  reason_line: string;                // server one-liner under the row
  route_id?: string | null;           // for GET /v2/strip (nav lane)
  your_vehicle?: boolean;             // matches the declared S8 class
  /** least-inhalation engine rows ("alive_core-path"): corridor roads the
      path takes, and 1..N on corridor-diverse alternatives (absent on
      the primary) — surfaced so alternatives read "via Outer Circle",
      not three identical "Car" rows */
  engine?: string | null;
  via_names?: string[] | null;
  alternative_index?: number | null;
  geometry: GeoJSON.Geometry | null;  // mapped from `route_geojson`
  stations?: { board: string; alight: string } | null;
  /** server `stations.lines` — transit line names the rider transfers
   *  across ("Orange/Airport", "Blue", "781") — shown next to board→alight. */
  lines?: string[] | null;
  transfers?: number | null;
  steps?: Step[] | null;              // only if a future payload inlines them
  segments?: Seg[];                   // legacy colour-per-segment strip — kept as a seam
};

/** A transit option: the server only ships `stations` on transit rows
 *  (metro+walk, bus+walk) — the mode string is "metro+walk"/"bus…", never
 *  exactly "metro", so `mode === "metro"` checks were dead before this. */
export const isTransit = (o: { stations?: unknown }): boolean => o.stations != null;

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

export type Step = { instruction: string; distance_m: number; type?: string; modifier?: string; street?: string };

/** Top-level POST /v2/plan response. */
export type PlanResult = {
  options: V2Option[];
  field: { source?: string; age_s?: number | null; samples?: number } | null;
  vehicle?: string;
  error?: string;
  /** stable machine code for the error path — 'outside_service_area' when
      the OD can't be served; clients key on this, not on error text. */
  code?: string;
};
