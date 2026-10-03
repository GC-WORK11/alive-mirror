/**
 * POST /v2/reroute — off-route → a new route from the current fix
 * (docs/plan/05 §3). The server lane ships the handler; this client
 * posts the documented body and tolerates either a bare route object
 * or an option wrapper, with geometry under `geometry` or
 * `route_geojson` and ETA under `eta_s` or `duration_s`.
 */
import { API } from "../components/shell/net";

export type RerouteRequest = {
  route_id: string;
  at: { lat: number; lon: number };
  to: { lat: number; lon: number };
  mode: string;
};

// Contract-sync: extracted view of Bridge/contract.ts V2RerouteResponse —
// normRoute() flattens the wire's `option` wrapper into this shape.
export type RerouteResult = {
  route_id: string;
  geometry: GeoJSON.Geometry | null;
  eta_s: number | null;
  distance_km: number | null;
  mode: string | null;
  steps?: { instruction: string; distance_m: number; type?: string }[] | null;
};

/** Small POST helper shared by the v2 write endpoints. */
export async function postJson<T = unknown>(
  url: string,
  body: unknown,
  timeoutMs = 9000,
): Promise<T> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const r = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
      signal: ctrl.signal,
    });
    if (!r.ok) throw new Error(`http ${r.status}`);
    return (await r.json()) as T;
  } finally {
    clearTimeout(t);
  }
}

function normRoute(j: Record<string, unknown> | null | undefined): RerouteResult | null {
  if (!j) return null;
  const inner = (j.option ?? j.route ?? j) as Record<string, unknown>;
  const geometry = (inner.geometry ?? inner.route_geojson) as GeoJSON.Geometry | undefined;
  const routeId = inner.route_id ?? j.route_id;
  if (typeof routeId !== "string" || !geometry) return null;
  const eta = (inner.eta_s ?? inner.duration_s) as number | undefined;
  const steps = Array.isArray(inner.steps) ? inner.steps : null;
  return {
    route_id: routeId,
    geometry: geometry ?? null,
    eta_s: typeof eta === "number" ? eta : null,
    distance_km: typeof inner.distance_km === "number" ? inner.distance_km : null,
    mode: (inner.mode as string) ?? null,
    steps,
  };
}

/** Returns null when the endpoint is absent/errored — caller keeps the
 *  old route and backs off. */
export async function postReroute(req: RerouteRequest, api: string = API): Promise<RerouteResult | null> {
  try {
    const j = await postJson<Record<string, unknown>>(
      `${api}/v2/reroute`,
      { route_id: req.route_id, at: req.at, from: req.at, to: req.to, mode: req.mode },
      9000,
    );
    return normRoute(j);
  } catch {
    return null;
  }
}
