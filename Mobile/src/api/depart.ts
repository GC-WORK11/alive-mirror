/** GET /depart client (server/main.py `depart`) — the leave-later dose
 *  curve: the SAME route scored against the hourly forecast field, one
 *  slot per departure hour for the next `hours` (default 24).
 *
 *  Server response → mapped here (Contract-sync: mapped view of
 *  Bridge/contract.ts DepartResponse — renamed keys, not raw wire):
 *    slots[].hours_ahead   → hour        (0 = leave now)
 *    slots[].start         → start       (naive ISO, UTC — render +5:30)
 *    slots[].dose_ug       → dose_mid    (µg inhaled PM2.5, point estimate)
 *    slots[].avg_conc_ugm3 → avg_conc_ugm3
 *    now / best / worst    → same slot shape
 *    ug_saved_vs_now       → kept AS-IS: despite the name it's a PERCENT
 *                            (server: round(100*(1 - best/now))), matching
 *                            the "breathe ~{n}% less" copy in CompareSheet.
 *    error responses come back as {options:[], error} — we read `slots`
 *    then `options` and surface `error` instead of throwing.
 *
 *  Wrapped in fetchCached (last-good): offline → the previous curve for
 *  this ~100 m-rounded O/D+vehicle returns with stale flagged on the
 *  NetResult — callers that care use `departCurveResult`, the convenience
 *  `fetchDepartCurve` just returns the data or null.
 *
 *  Integration:
 *    const r = await departCurveResult({ from, to, vehicle: "auto" });
 *    if (r.ok) <DepartGraph data={r.data.slots} bestHour={r.data.best?.hour ?? 0} … />
 */
import { API } from "../components/shell/net";
import { fetchCached } from "../offline/net";
import type { NetResult } from "../offline/net";

/** One departure-hour slot — a superset of DepartGraph's DepartDatum,
 *  so `slots` feeds the component's `data` prop directly. */
export type DepartSlot = {
  hour: number;                    // hours ahead of now (0 = now)
  start: string | null;            // naive ISO, UTC basis (server forecast time)
  dose_mid: number;                // µg inhaled for the trip leaving this hour
  dose_lo: number | null;          // reserved — server emits no band yet
  dose_hi: number | null;
  avg_conc_ugm3: number | null;    // mean field PM2.5 along the route that hour
};

export type DepartCurve = {
  vehicle: string | null;
  mode: string | null;             // exposure mode the server scored
  duration_min: number | null;
  distance_km: number | null;
  now: DepartSlot | null;
  best: DepartSlot | null;
  worst: DepartSlot | null;
  /** PERCENT dose saved vs leaving now (misleading server name kept for
   *  drop-in compat with shell/types.ts `Depart`); null when now-dose is 0 */
  ug_saved_vs_now: number | null;
  /** the honest key for the same percent — the server serves it verbatim;
   *  prefer this over the ug_* alias at every read site */
  pct_less_vs_now: number | null;
  slots: DepartSlot[];             // the 24h curve, in hours_ahead order
  forecast_age_s: number | null;   // forecast field age, for "data N min old"
  fieldAgeS: number | null;        // live field the horizon anchors to — its age
  error?: string;                  // server-side failure ("forecast unavailable"…)
};

export type DepartRequest = {
  from: { lat: number; lon: number };
  to: { lat: number; lon: number };
  /** exposure class the server understands: car | car_open | bike | auto |
   *  bus | cycle | walk — the selected plan option's `mode` maps directly */
  vehicle: string;
  hours?: number;                  // curve length, ≤120 server-side; default 24
};

const num = (v: unknown): number | null =>
  typeof v === "number" && Number.isFinite(v) ? v : null;
const str = (v: unknown): string | null => (typeof v === "string" ? v : null);

function toSlot(raw: unknown): DepartSlot | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  const hour = num(r.hours_ahead);
  const dose = num(r.dose_ug);
  if (hour == null || dose == null) return null;
  return {
    hour,
    start: str(r.start),
    dose_mid: dose,
    dose_lo: num(r.dose_lo),
    dose_hi: num(r.dose_hi),
    avg_conc_ugm3: num(r.avg_conc_ugm3),
  };
}

function mapDepart(j: Record<string, unknown>): DepartCurve {
  // success payload uses `slots`; error payloads use `options: []`
  const raw = Array.isArray(j.slots) ? j.slots : Array.isArray(j.options) ? j.options : [];
  const slots = raw.map(toSlot).filter((x): x is DepartSlot => x !== null);
  const fc = j.forecast && typeof j.forecast === "object"
    ? (j.forecast as Record<string, unknown>)
    : null;
  const fld = j.field && typeof j.field === "object"
    ? (j.field as Record<string, unknown>)
    : null;
  return {
    vehicle: str(j.vehicle),
    mode: str(j.mode),
    duration_min: num(j.duration_min),
    distance_km: num(j.distance_km),
    now: toSlot(j.now),
    best: toSlot(j.best),
    worst: toSlot(j.worst),
    ug_saved_vs_now: num(j.ug_saved_vs_now),
    pct_less_vs_now: num(j.pct_less_vs_now),
    slots,
    forecast_age_s: fc ? num(fc.age_s) : null,
    fieldAgeS: num(j.field_age_s) ?? (fld ? num(fld.age_s) : null),
    error: str(j.error) ?? undefined,
  };
}

/** The served dose-saving percent, read verbatim — `pct_less_vs_now` is
 *  the honest key; `ug_saved_vs_now` is the legacy alias for the SAME
 *  percent (server: round(100*(1-best/now))). Neither is µg: reading one
 *  as dose and recomputing a percent off it overstated the scheduled
 *  notification ~2.5× (13% true → ~33%) — take the wire value as-is.
 *  Works on both DepartCurve and the shell's narrower `Depart` shape. */
export function departSavedPct(d: {
  pct_less_vs_now?: number | null;
  ug_saved_vs_now?: number | null;
} | null): number | null {
  return d?.pct_less_vs_now ?? d?.ug_saved_vs_now ?? null;
}

/** Full NetResult — stale/ageS preserved for honest offline labelling. */
export async function departCurveResult(
  req: DepartRequest, timeoutMs = 10000,
): Promise<NetResult<DepartCurve>> {
  const hours = req.hours ?? 24;
  const qs =
    `from_lat=${req.from.lat}&from_lon=${req.from.lon}` +
    `&to_lat=${req.to.lat}&to_lon=${req.to.lon}` +
    `&vehicle=${encodeURIComponent(req.vehicle)}&hours=${hours}`;
  // local key — same ~100 m rounding as cacheKeys.plan, kept inline so
  // api/cache.ts (shared) stays untouched in this lane
  const key =
    `v2:depart:${req.from.lat.toFixed(3)},${req.from.lon.toFixed(3)}>` +
    `${req.to.lat.toFixed(3)},${req.to.lon.toFixed(3)}:${req.vehicle}:${hours}`;
  return fetchCached<DepartCurve>(`${API}/depart?${qs}`, {
    ttlMs: 15 * 60 * 1000,           // forecast field cadence is ~15 min
    key,
    timeoutMs,
    fetcher: async (signal) => {
      const r = await fetch(`${API}/depart?${qs}`, { signal });
      if (!r.ok) throw new Error(`http ${r.status}`);
      return mapDepart((await r.json()) as Record<string, unknown>);
    },
  });
}

/** Convenience: the curve or null (offline with no last-good copy). */
export async function fetchDepartCurve(
  req: DepartRequest, timeoutMs = 10000,
): Promise<DepartCurve | null> {
  const r = await departCurveResult(req, timeoutMs);
  return r.ok ? r.data : null;
}
