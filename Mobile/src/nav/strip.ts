/**
 * Route strip (doc 04 §5): the field sampled every ~250 m along the
 * route + the emission-curve params the live counters integrate.
 * Pure math + types — no RN imports, unit-testable.
 *
 * Server shape: GET /v2/strip?route_id=… →
 *   { route_id, mode, step_m,
 *     samples: [{lat, lon, dist_m, pm25, lo, hi}],
 *     emissions_curve: { mode, co2_g_km|co2_g_pkm:{lo,hi},
 *                        pm25_g_km|pm25_g_pkm:{lo,hi},
 *                        idle_g_s, occupancy, cold_start_km, basis },
 *     field: {...} }
 * Note: server `dist_m` is the length of the ~250 m chunk ENDING at the
 * sample (exposure.segment_samples), not a cumulative odometer — so the
 * sample's position along the route is the running sum.
 */

export type Band = { lo: number; mid: number; hi: number };

export type StripSample = {
  lat: number;
  lon: number;
  dist_m: number;
  pm25: number | null;
  lo: number | null;
  hi: number | null;
};

export type EmissionCurve = {
  mode: string;
  /** per vehicle-km bands (motorized private modes) */
  co2_g_km?: { lo: number; hi: number } | null;
  pm25_g_km?: { lo: number; hi: number } | null;
  /** per passenger-km bands (shared modes, e.g. metro incl. electricity) */
  co2_g_pkm?: { lo: number; hi: number } | null;
  pm25_g_pkm?: { lo: number; hi: number } | null;
  idle_g_s?: number | null;
  occupancy?: number | null;
  cold_start_km?: number | null;
  basis?: string;
};

export type RouteStrip = {
  route_id: string;
  mode: string | null;
  step_m: number;
  samples: StripSample[];
  emissions_curve: EmissionCurve;
  field?: {
    source?: string;
    age_min?: number;
    ts?: number;
    [k: string]: unknown;
  } | null;
};

/** Cumulative along-route metres of each sample (its chunk's end). */
export function stripCumM(samples: StripSample[]): number[] {
  const cum: number[] = [];
  let acc = 0;
  for (const s of samples) {
    acc += Math.max(0, s.dist_m || 0);
    cum.push(acc);
  }
  return cum;
}

/** Field concentration at along-route distance, linearly interpolated
 * between neighbouring samples; clamps to the nearest sample at the
 * ends. Missing values propagate as nulls in each band edge — honest,
 * never invented. */
export function fieldAtAlongM(
  samples: StripSample[],
  cum: number[],
  alongM: number,
): { lo: number | null; mid: number | null; hi: number | null } {
  const n = samples.length;
  if (n === 0) return { lo: null, mid: null, hi: null };
  const pick = (i: number) => ({
    lo: samples[i].lo, mid: samples[i].pm25, hi: samples[i].hi,
  });
  if (n === 1 || alongM <= cum[0]) return pick(0);
  if (alongM >= cum[n - 1]) return pick(n - 1);
  // binary search for the bracketing pair
  let lo = 0;
  let hiI = n - 1;
  while (hiI - lo > 1) {
    const m = (lo + hiI) >> 1;
    if (cum[m] <= alongM) lo = m; else hiI = m;
  }
  const span = cum[hiI] - cum[lo];
  const t = span > 0 ? (alongM - cum[lo]) / span : 0;
  const lerp = (a: number | null, b: number | null) =>
    a == null || b == null ? null : a + (b - a) * t;
  return {
    lo: lerp(samples[lo].lo, samples[hiI].lo),
    mid: lerp(samples[lo].pm25, samples[hiI].pm25),
    hi: lerp(samples[lo].hi, samples[hiI].hi),
  };
}
