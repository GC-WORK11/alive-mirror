/**
 * GET /v2/strip?route_id=… — the live-counter strip (server/v2/strip.py).
 * Field samples every ~250 m along the route + emission-curve params the
 * client integrates locally (doc 04 §5: no per-second network).
 */
import { API, fetchJson } from "../components/shell/net";
import type { RouteStrip } from "../nav/strip";

export async function fetchStrip(routeId: string, api: string = API): Promise<RouteStrip> {
  const j = await fetchJson(`${api}/v2/strip?route_id=${encodeURIComponent(routeId)}`, 9000);
  return {
    route_id: String(j?.route_id ?? routeId),
    mode: j?.mode ?? null,
    step_m: typeof j?.step_m === "number" ? j.step_m : 250,
    samples: Array.isArray(j?.samples) ? j.samples : [],
    emissions_curve: j?.emissions_curve ?? { mode: j?.mode ?? "" },
    field: j?.field ?? null,
  };
}
