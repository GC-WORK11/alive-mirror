/** Shared shell constants + fetch helper. */
import { Platform } from "react-native";
import * as Location from "expo-location";
import { nearestPlace, inNcr } from "../../search/t0";

// EXPO_PUBLIC_API_URL, else the emulator loopback aliases (dev only —
// release bundles must not ship loopback strings; missing env in a
// release build fails requests fast instead of silently aiming at a dev
// machine).
export const API =
  process.env.EXPO_PUBLIC_API_URL ??
  (__DEV__
    ? Platform.select({ android: "http://10.0.2.2:8000", default: "http://localhost:8000" }) ??
      "http://localhost:8000"
    : "");

export const DELHI: [number, number] = [77.209, 28.6139];
/* inNcr is single-sourced in src/search/t0 (server NCR_BBOX) — re-exported
   here so the shell keeps one import surface. */
export { inNcr };

/* Fresh fix first, honest cached fix second: getCurrentPositionAsync can
   return null while a perfectly good last-known fix sits in the fused
   provider (network-positioning dead but GNSS alive — the emulator rig
   reproduced it; a cold first launch indoors hits the same shape).
   Without the fallback the plan flow dead-ended on "couldn't get your
   location" while the home read (same device, last-known path at the
   aqi poll) showed real numbers. Guards match the home read: in-NCR +
   15 min freshness, so a stale or out-of-area fix still fails honestly. */
export type PosFix = {
  pos: Location.LocationObject;
  /** true = a live GNSS read just answered; false = the fused provider's
      last-known fix — real but up to 15 min old. Callers label it "near
      {locality}"/"last known", NEVER "Your location" (hunter: the boot
      where-to used to claim a fresh GPS fix over a cached coordinate). */
  fresh: boolean;
  /** fix age in seconds; 0 for a fresh read */
  ageS: number;
};

export const posNowDetailed = async (): Promise<PosFix | null> => {
  /* a fix that can't answer inside ~9 s used to hang the caller forever —
     an offline map pick ate the tap and produced nothing (walk F3).
     Racing the request means every caller reaches its honest failure
     path (locPickFailed / locDenied) instead of waiting on a GNSS fix
     that may never come. */
  const cur = await Promise.race([
    Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced }).catch(() => null),
    new Promise<null>((resolve) => { setTimeout(() => resolve(null), 9000); }),
  ]);
  if (cur) {
    return { pos: cur, fresh: true, ageS: Math.max(0, Math.round((Date.now() - cur.timestamp) / 1000)) };
  }
  const last = await Location.getLastKnownPositionAsync().catch(() => null);
  if (!last) return null;
  if (!inNcr(last.coords.latitude, last.coords.longitude)) return null;
  const ageS = Math.round((Date.now() - last.timestamp) / 1000);
  if (ageS > 15 * 60) return null;
  return { pos: last, fresh: false, ageS };
};

export const posNow = async () => (await posNowDetailed())?.pos ?? null;

export const fetchJson = (url: string, timeoutMs = 9000) => {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  return fetch(url, { signal: ctrl.signal })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`http ${r.status}`))))
    .finally(() => clearTimeout(t));
};

/** POST a JSON body; same timeout/abort behaviour as fetchJson. */
export const postJson = (url: string, body: unknown, timeoutMs = 9000) => {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  return fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    signal: ctrl.signal,
  })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`http ${r.status}`))))
    .finally(() => clearTimeout(t));
};

/** Name a dropped pin honestly.
 *
 *  /v2/reverse first (server gazetteer -> amazon -> honest 404). On
 *  network failure or 404, the bundled t0 gazetteer still names the
 *  nearest real place within 150 m — "nearest: X ~80 m" makes the
 *  approximation explicit. Last resort is the raw coordinate, which is
 *  honest by itself (no invented name). */
export const reverseName = async (lat: number, lon: number): Promise<{ name: string; subtitle: string }> => {
  try {
    const j = await fetchJson(`${API}/v2/reverse?lat=${lat}&lon=${lon}`, 6000);
    if (j?.name) {
      const d = typeof j.distance_m === "number" ? Math.round(j.distance_m) : null;
      const sub = [d != null && d > 30 ? `~${d} m away` : null,
                   typeof j.subtitle === "string" && j.subtitle ? j.subtitle : null]
        .filter(Boolean).join(" · ");
      return { name: j.name, subtitle: sub };
    }
  } catch { /* offline or no named place — fall through to the bundle */ }
  try {
    const near = nearestPlace({ lat, lon }, 150);
    if (near) {
      const d = Math.round(near.distance_m);
      return { name: `nearest: ${near.name}`, subtitle: `~${d} m away · offline` };
    }
  } catch { /* gazetteer not warmed — the coordinate is still honest */ }
  return { name: `${lat.toFixed(4)}, ${lon.toFixed(4)}`, subtitle: "dropped pin" };
};
