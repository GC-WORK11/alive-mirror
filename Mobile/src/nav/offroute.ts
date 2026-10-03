/**
 * Off-route detection + polyline snapping (doc 04 §4).
 * Pure math — no RN imports.
 *
 * Map matching: perpendicular projection of the GNSS fix onto every
 * route segment; the winner gives `alongM` (odometer on the route),
 * `offsetM` (cross-track error) and the segment heading. A fix counts
 * as off-route when offset > OFF_ROUTE_M; OFF_ROUTE_FIXES consecutive
 * such fixes trigger a reroute (task spec: >40 m × 3).
 */

export const OFF_ROUTE_M = 40;
export const OFF_ROUTE_FIXES = 3;
export const ARRIVE_M = 60;           // within this of the destination
export const ARRIVE_FIXES = 2;        // … for this many consecutive fixes

export type LonLat = [number, number];

export function havM(aLat: number, aLon: number, bLat: number, bLon: number): number {
  const p1 = (aLat * Math.PI) / 180;
  const p2 = (bLat * Math.PI) / 180;
  const dp = ((bLat - aLat) * Math.PI) / 180;
  const dl = ((bLon - aLon) * Math.PI) / 180;
  const h = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * 6371000 * Math.asin(Math.sqrt(h));
}

/** GeoJSON LineString | MultiLineString → one [lon,lat] polyline.
 *  MultiLineString legs are contiguous (metro + walk legs), so a flat
 *  concat is the documented approximation. */
export function flattenCoords(geometry: GeoJSON.Geometry | null | undefined): LonLat[] {
  if (!geometry) return [];
  if (geometry.type === "LineString") {
    return (geometry.coordinates as number[][]).map((c) => [c[0], c[1]]);
  }
  if (geometry.type === "MultiLineString") {
    const out: LonLat[] = [];
    for (const line of geometry.coordinates as number[][][]) {
      for (const c of line) out.push([c[0], c[1]]);
    }
    return out;
  }
  return [];
}

export function polylineLengthM(coords: LonLat[]): number {
  let d = 0;
  for (let i = 1; i < coords.length; i++) {
    d += havM(coords[i - 1][1], coords[i - 1][0], coords[i][1], coords[i][0]);
  }
  return d;
}

export type Snap = {
  /** odometer along the route, metres */
  alongM: number;
  /** cross-track distance to the route, metres */
  offsetM: number;
  /** snapped point on the route */
  lon: number;
  lat: number;
  /** segment index + fraction within it */
  segIdx: number;
  segT: number;
  /** segment bearing, degrees clockwise from north */
  headingDeg: number;
};

/** Project a fix onto the nearest route segment.
 *  Local equirectangular projection around the fix latitude — error
 *  <<1 m inside Delhi. Returns null for a degenerate polyline. */
export function snapToPolyline(
  coords: LonLat[],
  lat: number,
  lon: number,
): Snap | null {
  if (coords.length < 2) return null;
  const mPerDegLat = 110540;
  const mPerDegLon = 111320 * Math.cos((lat * Math.PI) / 180);
  let best: Snap | null = null;
  let cum = 0;
  for (let i = 1; i < coords.length; i++) {
    const ax = (coords[i - 1][0] - lon) * mPerDegLon;
    const ay = (coords[i - 1][1] - lat) * mPerDegLat;
    const bx = (coords[i][0] - lon) * mPerDegLon;
    const by = (coords[i][1] - lat) * mPerDegLat;
    const dx = bx - ax;
    const dy = by - ay;
    const len2 = dx * dx + dy * dy;
    const segLen = Math.sqrt(len2);
    let t = 0;
    if (len2 > 0) {
      t = -(ax * dx + ay * dy) / len2;
      t = Math.max(0, Math.min(1, t));
    }
    const px = ax + dx * t;
    const py = ay + dy * t;
    const off = Math.sqrt(px * px + py * py);
    if (best === null || off < best.offsetM) {
      best = {
        alongM: cum + segLen * t,
        offsetM: off,
        lon: coords[i - 1][0] + (coords[i][0] - coords[i - 1][0]) * t,
        lat: coords[i - 1][1] + (coords[i][1] - coords[i - 1][1]) * t,
        segIdx: i - 1,
        segT: t,
        headingDeg: len2 > 0
          ? ((Math.atan2(dx, dy) * 180) / Math.PI + 360) % 360
          : 0,
      };
    }
    cum += segLen;
  }
  return best;
}

/** Consecutive-fix off-route tracker (hysteresis: one good fix resets). */
export class OffRouteTracker {
  private n = 0;
  /** Returns true on every fix at/above the consecutive threshold —
   *  callers throttle with a cooldown so it can re-trigger if the
   *  reroute fails. A single on-route fix resets the count. */
  update(offsetM: number): boolean {
    if (offsetM > OFF_ROUTE_M) {
      this.n += 1;
      return this.n >= OFF_ROUTE_FIXES;
    }
    this.n = 0;
    return false;
  }
  get counting(): boolean {
    return this.n > 0;
  }
  reset(): void {
    this.n = 0;
  }
}

/** Arrival: within ARRIVE_M of the destination for ARRIVE_FIXES fixes. */
export class ArrivalTracker {
  private n = 0;
  update(distToDestM: number): boolean {
    if (distToDestM <= ARRIVE_M) {
      this.n += 1;
      return this.n >= ARRIVE_FIXES;
    }
    this.n = 0;
    return false;
  }
  reset(): void {
    this.n = 0;
  }
}
