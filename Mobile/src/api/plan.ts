/** POST /v2/plan client (server/v2/plan.py) — Contract-sync: maps
 *  V2PlanResponse → PlanResultFresh (V2Option rows). One call → ranked options
 *  with dose + emissions bands, tags and the reason line computed by the
 *  server's doc-06 §4 ε-constraint rank. We map snake_case onto V2Option
 *  and keep every field nullable where the server is honest about nulls
 *  (no field sigma → lo/hi null; no route → option absent). */
import { API, postJson } from "../components/shell/net";
import { mark } from "../perf";
import type { Band, PlanResult, V2Option } from "../components/shell/types";
import { cacheKeys } from "./cache";
import { fetchCached } from "../offline/net";
import type { PucInfo } from "../store/vehicle";

/** `vehicle` is a class string the server understands: car | car_open |
 *  bike | auto | bus | metro | cycle | walk (+ aliases two_wheeler,
 *  scooter, car_ac, cab, rickshaw, walking, cycling). See
 *  store/vehicle.ts `planVehicle` for the S8 profile → string mapping. */
export type PlanRequest = {
  from: { lat: number; lon: number };
  to: { lat: number; lon: number };
  vehicle?: string;
  /** full S8 profile — server `_parse_vehicle` reads fuel/year_bucket
      out of it; omitting it quietly falls back to the fleet prior. `puc`
      rides along verbatim (store/vehicle.ts `PucInfo`) — additive for
      the backend's emissions calibration; dropped safely until then. */
  vehicle_profile?: {
    class: string; fuel?: string; year_bucket?: string;
    puc?: PucInfo | null;
  } | null;
  depart_at?: string;
};

/** Field-status block the server ALREADY serves under `field` on
 *  /v2/plan and /v2/reroute — it is `airfield.FIELD.status()` verbatim
 *  (server/v2/plan.py `_field_status`). Every key optional: when the
 *  status probe itself throws, the payload degrades to just
 *  `{"source": "unavailable"}`. Field-age + provenance feed
 *  components/FreshnessChip; `serving`/`sigma_coverage` keep dose
 *  honesty visible. (status() also emits wind/coverage/snapshot/
 *  load_warn_files — not mapped yet; extend here if a lane needs it.)
 *
 *  Contract-sync: shadowed subset of Bridge/contract.ts `FieldStatus`
 *  (duplicated, not imported — see the header note in contract.ts;
 *  server/tests/test_contract_sync.py enforces the wire both ways). */
export type FieldStatus = {
  source?: string;              // "open-meteo/cams" | "openaq-stations+open-meteo/cams" | "unavailable"
  samples?: number;             // model lattice samples in the blend
  station_readings?: number;    // live station readings blended in — 0 = stations dark
  age_s?: number | null;        // seconds since the served field was fetched/built
  stale?: boolean | null;       // server's verdict: age_s > stale_after_s; null when age unknown
  stale_after_s?: number;       // server's stale threshold in seconds (2700 = 45 min)
  serving?: "snapshot" | "live" | "none";  // built snapshot index vs live blend vs nothing
  kriging?: string;             // "on" | "idw" — whether σ is kriged
  engine?: string;              // "alive_core" | "python" — which engine serves
  sigma_coverage?: string;      // "full" | "none" | "partial:N/M" | "per-query"
  load_warnings?: number;       // corrupt snapshot files skipped at load
  /** the live instrument sites the blend is anchored to — lat/lon/name
      only (the wire carries no per-station value; the field IS their
      blended read). The air map paints these as the station rings. */
  stations?: { lat: number; lon: number; name?: string | null }[];
  stations_src?: string;        // "waqi+dpcc"-style feed provenance
};

/** PlanResult with `field` typed to what the server really sends —
 *  types.ts keeps the narrow three-key shape that earlier lanes lean
 *  on; this widens additively (all extra keys optional) and stays
 *  assignable to PlanResult, so existing callers compile unchanged. */
export type PlanResultFresh = Omit<PlanResult, "field"> & {
  field: FieldStatus | null;
};

/** Provenance tokens for FreshnessChip's `sources` prop: splits the
 *  server's "+"-joined `field.source` ("openaq-stations+open-meteo/cams")
 *  and prepends the serving mode so a snapshot serve is visible. Empty
 *  field → [] → the chip makes no provenance claim. */
export function fieldSources(f: FieldStatus | null | undefined): string[] {
  if (!f) return [];
  const toks = (f.source ?? "")
    .split("+")
    .map((x) => x.trim())
    .filter(Boolean);
  if (f.serving && !toks.includes(f.serving)) toks.unshift(f.serving);
  return toks;
}

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
      coverage: num(dose.coverage),
    },
    emissions: {
      co2_kg: band(em.co2_kg),
      pm25_g: band(em.pm25_g),
      nox_g: band(em.nox_g),
      // "none" is the server's null-marker for non-motorized modes —
      // as a bare string it would render the literal word in the explainer
      label: em.label === "none" ? null : str(em.label),
      basis: em.basis === "none" ? null : str(em.basis),
      occupancy: num(em.occupancy),
      bs_class: str(em.bs_class),
      bs_options: Array.isArray(em.bs_options) ? em.bs_options.filter((x): x is string => typeof x === "string") : null,
      confidence: str(em.confidence),
      fuel: str(em.fuel),
      class: str(em.class),
      puc_calibrated: em.puc_calibrated === true ? true : null,
      breakdown: em.breakdown && typeof em.breakdown === "object"
        ? (() => {
            const bd = em.breakdown as Record<string, unknown>;
            const mid = (k: string) =>
              bd[k] && typeof bd[k] === "object"
                ? { co2: num((bd[k] as Record<string, unknown>).co2) }
                : null;
            return {
              moving_mid: mid("moving_mid"),
              idle_mid: mid("idle_mid"),
              cold_extra_mid: mid("cold_extra_mid"),
            };
          })()
        : null,
      non_exhaust: em.non_exhaust && typeof em.non_exhaust === "object"
        ? {
            pm10_g: band((em.non_exhaust as Record<string, unknown>).pm10_g),
            note: str((em.non_exhaust as Record<string, unknown>).note) ?? undefined,
          }
        : null,
    },
    tag: str(o.tag),
    safest_path: o.safest_path === true ? true : null,
    recommended: o.recommended === true,
    reason_line: str(o.reason_line) ?? "",
    route_id: str(o.route_id),
    /* the judges' number — 'purest vs default' exposure drop + time
       penalty; nulls pass through untouched (a comparison the server
       couldn't make honestly is never fabricated here either) */
    delta: (() => {
      if (!o.delta || typeof o.delta !== "object") return null;
      const d = o.delta as Record<string, unknown>;
      const basis = str(d.basis);
      if (basis !== "route" && basis !== "default" &&
          basis !== "fastest" && basis !== "self") return null;
      return {
        basis,
        vs_label: str(d.vs_label),
        air_ug: num(d.air_ug),
        air_pct: num(d.air_pct),
        min_added: num(d.min_added),
        band_drop: num(d.band_drop),
      };
    })(),
    engine: str(o.engine),
    via_names: Array.isArray(o.via_names)
      ? o.via_names.filter((x): x is string => typeof x === "string" && x.length > 0)
      : null,
    alternative_index: num(o.alternative_index),
    your_vehicle: o.your_vehicle === true,
    geometry: (o.route_geojson ?? o.geometry ?? null) as GeoJSON.Geometry | null,
    stations: stations
      ? { board: str(stations.board) ?? "", alight: str(stations.alight) ?? "" }
      : null,
    lines: Array.isArray(stations?.lines)
      ? (stations.lines as unknown[]).filter((x): x is string => typeof x === "string")
      : null,
    transfers: num(stations?.transfers),
    steps: Array.isArray(o.steps) ? (o.steps as V2Option["steps"]) : null,
    // per-stretch field paint from v2/plan (`{geometry, pm25, band}` spans);
    // absent on older servers — RouteTint then falls back to the flat dose tint
    segments: Array.isArray(o.segments)
      ? (o.segments as V2Option["segments"])
      : undefined,
  };
}

/** One POST to `${API}/v2/plan`, wrapped in last-good cache: offline →
 *  the previous options for this ~100 m-rounded O/D pair come back and
 *  the net-status pill labels them stale. Throws only when the network
 *  fails AND nothing is cached — callers show the retry state. */
export async function planOptions(req: PlanRequest, timeoutMs = 12000): Promise<PlanResultFresh> {
  mark("plan:req");
  const r = await fetchCached<PlanResultFresh>(`${API}/v2/plan`, {
    ttlMs: 15 * 60 * 1000,                       // field cadence is ~15 min
    key: cacheKeys.plan(req.from.lat, req.from.lon, req.to.lat, req.to.lon,
      req.vehicle_profile
        ? `${req.vehicle ?? ""}:${req.vehicle_profile.fuel ?? ""}:${req.vehicle_profile.year_bucket ?? ""}`
        : req.vehicle ?? ""),
    timeoutMs,
    fetcher: async () => {
      const j = (await postJson(`${API}/v2/plan`, req, timeoutMs)) as Record<string, unknown>;
      return mapPlan(j);
    },
  });
  if (!r.ok) { mark("plan:fail"); throw new Error("plan failed"); }
  mark("plan:resp");
  /* last-good: the field block's stamped age froze at write time — add
     the cache sit so the map chip doesn't call a stale serve "9 min". */
  if (r.stale && r.data.field) {
    const f = r.data.field;
    return {
      ...r.data,
      field: {
        ...f,
        age_s: f.age_s == null ? null : f.age_s + r.ageS,
        stale: true,
      },
    };
  }
  return r.data;
}

/** Engine-first paint: POST /v2/plan with `fast:true` returns only the
 *  least-inhalation engine rows (~engine time, no public-router wait).
 *  Never cached — the full plan replaces it moments later. */
export async function planEngineFirst(req: PlanRequest, timeoutMs = 9000): Promise<PlanResultFresh> {
  mark("plan:req");
  try {
    const j = (await postJson(`${API}/v2/plan`, { ...req, fast: true }, timeoutMs)) as Record<string, unknown>;
    mark("plan:resp");
    return mapPlan(j);
  } catch (e) { mark("plan:fail"); throw e; }
}

/** Server `field` block → FieldStatus. Guards every key — the payload
 *  degrades to {"source":"unavailable"} when status() itself throws. */
function mapFieldStatus(f: Record<string, unknown>): FieldStatus {
  const serv = str(f.serving);
  return {
    source: str(f.source) ?? undefined,
    samples: num(f.samples) ?? undefined,
    station_readings: num(f.station_readings) ?? undefined,
    age_s: num(f.age_s),
    stale: typeof f.stale === "boolean" ? f.stale : null,
    stale_after_s: num(f.stale_after_s) ?? undefined,
    serving: serv === "snapshot" || serv === "live" || serv === "none"
      ? serv
      : undefined,
    kriging: str(f.kriging) ?? undefined,
    engine: str(f.engine) ?? undefined,
    sigma_coverage: str(f.sigma_coverage) ?? undefined,
    load_warnings: num(f.load_warnings) ?? undefined,
  };
}

/* The wire's "least-smoke" family is named by the least-inhalation
   engine against its OWN primary — not against the same-mode rows the
   sheet actually shows. That puts '· least-smoke alt 2' on options
   measurably smokier than the mode's plain row (component-audit #22:
   'least-smoke alt 1' at 34.4 µg over a 26.0 µg primary — the same lie
   the isSafest fallback already guards elsewhere). The claim is
   re-derived here against the dose.mids we display: only the group's
   true lightest row may keep the qualifier; every other member degrades
   to the factual '· alt N'. */
const LEAST_SMOKE_RE = /^(.*) · least-smoke (?:rd|alt \d+)$/;
const LEAST_SMOKE_EPS = 0.05; // display-precision slack — doses render rounded

function relabelLeastSmoke(options: V2Option[]): void {
  const groups = new Map<string, V2Option[]>();
  for (const o of options) {
    if (!LEAST_SMOKE_RE.test(o.label ?? "")) continue;
    const g = groups.get(o.mode) ?? [];
    g.push(o);
    groups.set(o.mode, g);
  }
  for (const rows of groups.values()) {
    const mode = rows[0].mode;
    /* every same-mode row counts, qualifier or not — 'least' must hold
       against the plain 'Bicycle' row too */
    const mids = options
      .filter((o) => o.mode === mode && o.dose?.mid != null)
      .map((o) => o.dose.mid!);
    if (!mids.length) continue; // nothing to verify against — leave the wire as-is
    const min = Math.min(...mids);
    let altN = 0;
    for (const o of rows) {
      const base = LEAST_SMOKE_RE.exec(o.label!)![1];
      const isLightest = o.dose?.mid != null && o.dose.mid <= min + LEAST_SMOKE_EPS;
      o.label = isLightest ? `${base} · least-smoke rd` : `${base} · alt ${++altN}`;
    }
  }
}

/* exported for the unit tests (api/plan.test.ts) — production callers
   use fetchPlan/fetchReroute which run this same mapper on the wire. */
export function mapPlan(j: Record<string, unknown>): PlanResultFresh {
  const raw = Array.isArray(j.options) ? j.options : [];
  const field = j.field && typeof j.field === "object"
    ? (j.field as Record<string, unknown>)
    : null;
  const options = raw.map(toOption).filter((o): o is V2Option => o !== null);
  relabelLeastSmoke(options);
  return {
    options,
    field: field ? mapFieldStatus(field) : null,
    vehicle: str(j.vehicle) ?? undefined,
    error: str(j.error) ?? undefined,
    code: str(j.code) ?? undefined,
    degraded: Array.isArray(j.degraded)
      ? j.degraded.filter((x): x is string => typeof x === "string")
      : undefined,
  };
}
