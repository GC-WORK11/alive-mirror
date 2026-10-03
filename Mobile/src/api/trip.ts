/** POST /v2/trip client (server/v2/trip.py) — donates an anonymized
 *  traversal to the collective field. The server re-runs the privacy
 *  pipeline itself (drop 300 m at both ends, thin to ~100 m, round to
 *  4 decimals, store H3-res-8 cells only) so this client just sends the
 *  honest summary + raw-ish points; lighter pre-thinning is still good
 *  manners on a slow uplink.
 *
 *  SEAM(trip-submit): owned by the nav lane — the flow hook no longer
 *  calls this; it exists for whoever finishes live navigation. */
import { API, postJson } from "../components/shell/net";
import { contributorId } from "../community";

/** Summary fields the server keeps (server/v2/trip.py _SUMMARY_FIELDS). */
export type TripSummary = {
  mode?: string;
  distance_km?: number;
  duration_s?: number;
  dose_ug?: number;
  co2_kg_mid?: number;
  pm25_g_mid?: number;
  switched?: boolean;
};

export type TripPoint = { lat: number; lon: number } | [number, number]; // [lon,lat] GeoJSON order ok

export type TripPost = {
  summary: TripSummary;
  trajectory: TripPoint[];
  /** opaque anon token; defaults to contributorId() when omitted */
  device_token?: string;
};

export type TripAck = {
  stored: boolean;
  cells_traversed?: number;
  points_used?: number;
  privacy?: Record<string, unknown>;
  ts?: number;
};

/** Donate a finished trip. Fails soft (caller catches) — this is a
 *  donation, never a blocker for the user's receipt. */
export async function postTrip(p: TripPost, timeoutMs = 12000): Promise<TripAck> {
  const device_token = p.device_token ?? (await contributorId());
  return (await postJson(`${API}/v2/trip`, {
    device_token,
    summary: p.summary,
    trajectory: p.trajectory,
  }, timeoutMs)) as TripAck;
}
