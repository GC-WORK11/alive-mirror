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

export const airFieldAgeS = (
  fc: GeoJSON.FeatureCollection | null,
  now = Date.now(),
): number | null => {
  if (!fc) return null;
  const v = airFieldEpoch(fc);
  return v == null ? null : Math.max(0, now / 1000 - v);
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
        fieldAgeS: airFieldAgeS(fc),
        basis:
          ((fc as { properties?: { basis?: unknown } }).properties?.basis as
            | string
            | undefined) ?? null,
      };
    },
  });
}

export type FieldCellSample = {
  /** the painted cell's own blended read, µg/m³ */
  pm25: number;
  /** the cell's confidence grade verbatim ("hi"|"med"|"lo"), null when
   *  the serve carries none */
  conf: string | null;
};

/** Point → the painted cell's own read. The layer's cells are the
 *  server's square NCR tiling (server/grid.py emits axis-aligned
 *  rectangles), so containment is a bbox scan — exact for these
 *  polygons and ~free at the 28-grid's few hundred cells. Local +
 *  instant + offline-safe: the readout answers from the same data the
 *  user is already looking at, so tap and tint can never disagree.
 *
 *  null = no served cell covers the point (a dropped-cell hole, or
 *  past the grid's edge): honest absence — the caller falls back to
 *  /aqi or says so, never a nearest-cell guess. Edge hits resolve to
 *  whichever neighbour is scanned first; either is a fair area read. */
export function sampleFieldAt(
  fc: GeoJSON.FeatureCollection | null | undefined,
  lat: number,
  lon: number,
): FieldCellSample | null {
  if (!fc?.features?.length) return null;
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  const EPS = 1e-9;
  for (const f of fc.features) {
    const g = f?.geometry;
    if (!g || g.type !== "Polygon") continue;
    const ring = (g as GeoJSON.Polygon).coordinates?.[0];
    if (!Array.isArray(ring) || ring.length === 0) continue;
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const pt of ring) {
      const px = pt?.[0], py = pt?.[1];
      if (typeof px !== "number" || typeof py !== "number") continue;
      if (px < x0) x0 = px;
      if (px > x1) x1 = px;
      if (py < y0) y0 = py;
      if (py > y1) y1 = py;
    }
    if (!Number.isFinite(x0)) continue;
    if (lon < x0 - EPS || lon > x1 + EPS || lat < y0 - EPS || lat > y1 + EPS) {
      continue;
    }
    const p = (f.properties ?? {}) as Record<string, unknown>;
    const v = p.pm25;
    if (typeof v !== "number" || !Number.isFinite(v)) continue;
    return { pm25: v, conf: typeof p.conf === "string" ? p.conf : null };
  }
  return null;
}
