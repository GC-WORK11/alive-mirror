/** The air map's painted surface: the served PM2.5 field as GeoJSON
 *  cells.
 *
 *  GET /grid?cells=N&param=pm2_5 — plain /grid (no h) is the CURRENT
 *  measured field (server basis "recorded", cell_epoch[0] = its build
 *  epoch). That is distinct from dayfield.ts's /grid?h=N slices, which
 *  scrub the forecast horizon for the morning card — the air map shows
 *  right now, so it reads the recorded surface.
 *
 *  Honesty contract: one shot through fetchCached (last-good). A dead
 *  fetch → the previous surface marked `stale`; nothing → empty, the
 *  map just doesn't tint. Never a generated/fake field.
 */
import { API, fetchJson } from "../components/shell/net";
import { fetchCached } from "../offline/net";

/** cells=28 over the served bbox → ~4×3 km cells: street-district
 *  fidelity without the 36-grid's 375 KB cost (~1.7 s on prod). */
export const FIELD_GRID_CELLS = 28;

export type AirFieldGrid = {
  /** cell polygons; properties: { pm25:number, param:"pm2_5",
   *  conf:"hi"|"med"|"lo" } — empty collection when the server has
   *  nothing honest to say */
  fc: GeoJSON.FeatureCollection;
  /** seconds since the served field was built — /grid's cell_epoch[0].
   *  null = the server didn't stamp it; never invented client-side */
  fieldAgeS: number | null;
  /** the surface's own basis word when served ("recorded") */
  basis?: string | null;
};

/** The field's own build epoch — /grid's cell_epoch[0]. Doubles as the
 *  surface's identity: same epoch = same serve, callers can skip the
 *  re-render. null = the server didn't stamp it. */
export const airFieldEpoch = (fc: GeoJSON.FeatureCollection): number | null => {
  const ep = (fc as { properties?: { cell_epoch?: unknown[] } })
    .properties?.cell_epoch;
  const v = Array.isArray(ep) ? ep[0] : null;
  return typeof v === "number" && Number.isFinite(v) ? v : null;
};

const fieldAgeFromEpoch = (fc: GeoJSON.FeatureCollection): number | null => {
  const v = airFieldEpoch(fc);
  return v == null ? null : Math.max(0, Date.now() / 1000 - v);
};

export async function fetchAirField(cells: number = FIELD_GRID_CELLS) {
  const url = `${API}/grid?cells=${cells}&param=pm2_5`;
  return fetchCached<AirFieldGrid>(url, {
    key: `airfield:grid:${cells}:pm2_5`,
    ttlMs: 10 * 60 * 1000, // inside the field's own ~15 min refresh cadence
    timeoutMs: 15000,
    fetcher: async () => {
      const fc = (await fetchJson(url, 15000)) as GeoJSON.FeatureCollection;
      return {
        fc,
        fieldAgeS: fieldAgeFromEpoch(fc),
        basis:
          ((fc as { properties?: { basis?: unknown } }).properties?.basis as
            | string
            | undefined) ?? null,
      };
    },
  });
}
