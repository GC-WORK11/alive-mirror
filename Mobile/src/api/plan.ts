/** POST /v2/plan client (server/v2/plan.py). One call → ranked options
 *  with dose + emissions bands, tags and the reason line computed by the
 *  server's doc-06 §4 ε-constraint rank. We map snake_case onto V2Option
 *  and keep every field nullable where the server is honest about nulls
 *  (no field sigma → lo/hi null; no route → option absent). */
import { API, postJson } from "../components/shell/net";
import type { Band, PlanResult, V2Option } from "../components/shell/types";
import { cacheKeys } from "./cache";
import { fetchCached } from "../offline/net";

/** `vehicle` is a class string the server understands: car | car_open |
 *  bike | auto | bus | metro | cycle | walk (+ aliases two_wheeler,
 *  scooter, car_ac, cab, rickshaw, walking, cycling). See
 *  store/vehicle.ts `planVehicle` for the S8 profile → string mapping. */
export type PlanRequest = {
  from: { lat: number; lon: number };
  to: { lat: number; lon: number };
  vehicle?: string;
  depart_at?: string;
};

const num = (v: unknown): number | null =>
  typeof v === "number" && Number.isFinite(v) ? v : null;

const band = (v: unknown): Band | null => {
  if (!v || typeof v !== "object") return null;
  const b = v as Record<string, unknown>;
  return { lo: num(b.lo), mid: num(b.mid), hi: num(b.hi) };
};

const str = (v: unknown): string | null => (typeof v === "string" ? v : null);

function toOption(raw: unknown): V2Option | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const mode = str(o.mode) ?? str(o.vehicle) ?? "";
  const dose = (o.dose ?? {}) as Record<string, unknown>;
  const em = (o.emissions ?? {}) as Record<string, unknown>;
  const eta = num(o.eta_s ?? o.duration_s);
  const stations = o.stations && typeof o.stations === "object"
    ? (o.stations as Record<string, unknown>)
    : null;
  return {
    mode,
    vehicle: mode,                                   // legacy alias — NavChrome reads option.vehicle
    label: str(o.label) ?? mode,
    eta_s: eta,
    freeflow_s: num(o.freeflow_s),
    eta_model: str(o.eta_model),
    duration_min: eta != null ? eta / 60 : 0,
    distance_km: num(o.distance_km),
    dose: {
      ...(band(dose) ?? { lo: null, mid: null, hi: null }),
      avg_conc_ugm3: num(dose.avg_conc_ugm3),
      confidence: str(dose.confidence),
      basis: str(dose.basis),
      note: str(dose.note),
    },
    emissions: {
      co2_kg: band(em.co2_kg),
      pm25_g: band(em.pm25_g),
      nox_g: band(em.nox_g),
      label: str(em.label),
      basis: str(em.basis),
      occupancy: num(em.occupancy),
      bs_class: str(em.bs_class),
      bs_options: Array.isArray(em.bs_options) ? em.bs_options.filter((x): x is string => typeof x === "string") : null,
      confidence: str(em.confidence),
      non_exhaust: em.non_exhaust && typeof em.non_exhaust === "object"
        ? {
            pm10_g: band((em.non_exhaust as Record<string, unknown>).pm10_g),
            note: str((em.non_exhaust as Record<string, unknown>).note) ?? undefined,
          }
        : null,
    },
    tag: str(o.tag),
    recommended: o.recommended === true,
    reason_line: str(o.reason_line) ?? "",
    route_id: str(o.route_id),
    your_vehicle: o.your_vehicle === true,
    geometry: (o.route_geojson ?? o.geometry ?? null) as GeoJSON.Geometry | null,
    stations: stations
      ? { board: str(stations.board) ?? "", alight: str(stations.alight) ?? "" }
      : null,
    steps: Array.isArray(o.steps) ? (o.steps as V2Option["steps"]) : null,
  };
}

/** One POST to `${API}/v2/plan`, wrapped in last-good cache: offline →
 *  the previous options for this ~100 m-rounded O/D pair come back and
 *  the net-status pill labels them stale. Throws only when the network
 *  fails AND nothing is cached — callers show the retry state. */
export async function planOptions(req: PlanRequest, timeoutMs = 12000): Promise<PlanResult> {
  const r = await fetchCached<PlanResult>(`${API}/v2/plan`, {
    ttlMs: 15 * 60 * 1000,                       // field cadence is ~15 min
    key: cacheKeys.plan(req.from.lat, req.from.lon, req.to.lat, req.to.lon),
    timeoutMs,
    fetcher: async () => {
      const j = (await postJson(`${API}/v2/plan`, req, timeoutMs)) as Record<string, unknown>;
      return mapPlan(j);
    },
  });
  if (!r.ok) throw new Error("plan failed");
  return r.data;
}

function mapPlan(j: Record<string, unknown>): PlanResult {
  const raw = Array.isArray(j.options) ? j.options : [];
  const field = j.field && typeof j.field === "object"
    ? (j.field as Record<string, unknown>)
    : null;
  return {
    options: raw.map(toOption).filter((o): o is V2Option => o !== null),
    field: field
      ? { source: str(field.source) ?? undefined, age_s: num(field.age_s), samples: num(field.samples) ?? undefined }
      : null,
    vehicle: str(j.vehicle) ?? undefined,
    error: str(j.error) ?? undefined,
  };
}
