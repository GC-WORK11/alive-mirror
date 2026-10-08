/** /v2/stays + /v2/playtime — the 'stay & play' surfaces (hackathon
 *  features 2 & 3). Thin typed fetchers in dayfield.ts's register: the
 *  server computes every number off the live field + anchored forecast;
 *  here we only shape requests and return honest nulls — no fills. */
import { API, fetchJson } from "../components/shell/net";

export type ExploreMode = "stays" | "playtime";
export type ExploreAnchor = { lat: number; lon: number } | { name: string };

const nearParam = (a: ExploreAnchor) =>
  "lat" in a ? `${a.lat},${a.lon}` : a.name;

export type NearRef = {
  lat: number; lon: number;
  name: string | null; kind?: string;
  via: "coords" | "search";
};

export type StayRow = {
  id: string; name: string; kind: string;
  lat: number; lon: number; dist_km: number;
  pm25_now: number | null; window_mean_ug: number | null;
  n_hours: number; scored_on: "next24h" | "now" | "unrated";
  band: string; cleaner_by_ug: number | null;
  sparse: boolean; nearest_station_km: number | null;
};

export type StaysData = {
  near: NearRef;
  stays: StayRow[];
  k: number; window_h: number; scored_h: number;
  lodging_rows: number; ranked_on: string;
  anchor_pm25_now: number | null; anchor_band: string;
  sparse: boolean; beyond_edge: boolean;
  nearest_station_km: number | null;
  model: string; field_age_s: number | null;
  error?: string;
};

export type PlaytimeHour = {
  h: number; start: string | null; ist_label: string;
  pm25_mid: number; pm25_lo: number | null; pm25_hi: number | null;
  us_aqi: number | null; band: string;
  confidence: "hi" | "med" | "lo";
  date_ist: string; day_offset: number;
};

export type PlaytimeWindow = {
  start_h: number; end_h: number | null;
  start_label?: string; end_label?: string | null;
  pm25_mid?: number; basis: string;
  start_day_offset: number; end_day_offset: number;
};

export type PlaytimeData = {
  near: NearRef;
  tz: string; generated_ist: string;
  hours: PlaytimeHour[];
  served_h: number; window_h: number;
  now_pm25: number | null; mean_pm25: number | null;
  best_window: PlaytimeWindow | null;
  worst_window: PlaytimeWindow | null;
  cleaner_by_ug: number | null;
  flat: boolean;
  confidence: "hi" | "med" | "lo" | null;
  verdict: string;
  decisions: { label: string; line: string }[];
  sparse: boolean; beyond_edge: boolean | null;
  nearest_station_km: number | null;
  model: string; band_basis: string;
  field_age_s: number | null;
  error?: string;
};

export async function fetchStays(anchor: ExploreAnchor, k = 8): Promise<StaysData | null> {
  try {
    const d = (await fetchJson(
      `${API}/v2/stays?near=${encodeURIComponent(nearParam(anchor))}&k=${k}`,
      15000)) as StaysData | null;
    if (!d || !Array.isArray(d.stays)) return null;
    return d;
  } catch {
    return null;
  }
}

export async function fetchPlaytime(anchor: ExploreAnchor): Promise<PlaytimeData | null> {
  try {
    const d = (await fetchJson(
      `${API}/v2/playtime?near=${encodeURIComponent(nearParam(anchor))}`,
      15000)) as PlaytimeData | null;
    if (!d || !Array.isArray(d.hours)) return null;
    return d;
  } catch {
    return null;
  }
}
