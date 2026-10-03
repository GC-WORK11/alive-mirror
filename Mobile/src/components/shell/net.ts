/** Shared shell constants + fetch helper. */
import { Platform } from "react-native";

export const API =
  process.env.EXPO_PUBLIC_API_URL ??
  Platform.select({ android: "http://10.0.2.2:8000", default: "http://localhost:8000" });

export const DELHI: [number, number] = [77.209, 28.6139];
export const NCR = { minLon: 76.75, maxLon: 77.95, minLat: 28.15, maxLat: 28.98 };
export const inNcr = (lat: number, lon: number) =>
  lon > NCR.minLon && lon < NCR.maxLon && lat > NCR.minLat && lat < NCR.maxLat;
export const normName = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, "");

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
