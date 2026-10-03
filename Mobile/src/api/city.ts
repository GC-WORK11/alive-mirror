// GET /v2/city — the "Delhi today" consumer payload (docs/plan/07 §1).
// The screen shows aggregates only: a day-of-breathing band, k>=3 street
// corridors, field freshness — nothing personal ever leaves the store.
//
// Base URL: API_BASE from search/client — the one resolution rule
// (EXPO_PUBLIC_API_URL, else the emulator loopback aliases). Re-resolving
// here would let this screen drift from the shell's backend.
import { API_BASE } from "../search/client";

export type CityBand = { lo: number; mid: number; hi: number };

export type CityCorridor = {
  cell: string;
  name: string | null;          // null = nothing honest to name it
  lat: number;
  lon: number;
  trips: number;
  devices?: number;
  avg_dose_ug: number;
  relative: "heavier" | "lighter";
};

export type CityDayTotals = {
  trips: number;
  km: number;
  dose_ug: number;
  co2_kg_mid: number;
  pm25_g_mid: number;
  switched: number;
  modes: Record<string, number>;
};

export type CityPayload = {
  ts: number;
  generated_at?: string;
  pm25_stats?: { n: number; mean?: number; median?: number; max?: number };
  /** The hero figure — null when the field has no data (never faked). */
  breath: {
    pm25_ugm3: CityBand;
    day_inhaled_ug: CityBand;
    cigarettes: CityBand;
    n_points?: number;
    basis?: string;
  } | null;
  field_age_s: number | null;
  freshness?: {
    field_age_s: number | null;
    age_min: number | null;
    label: "live" | "stale" | "unknown";
  };
  provenance?: {
    model?: {
      name?: string;
      source?: string | null;
      samples?: number;
      up?: boolean;
    };
    stations?: { count?: number; live?: boolean; note?: string };
    trips?: {
      publishable_corridors?: number;
      cells_tracked?: number;
      window_h?: number;
      k_min?: number;
    };
  };
  corridors?: CityCorridor[];
  /** False until k>=3 corridors exist — the honest empty state. */
  enough_data?: boolean;
  wind?: { speed_kmh?: number | null; from_deg?: number | null };
  sources?: Record<
    string,
    { up?: boolean; count?: number; source?: string | null }
  >;
  trips?: {
    days?: Record<string, CityDayTotals>;
    cells_tracked?: number;
    corridors_publishable?: number;
  };
};

/** One shot at `${API_BASE}/v2/city`. Caller owns the AbortSignal. */
export async function fetchCity(signal?: AbortSignal): Promise<CityPayload> {
  const res = await fetch(`${API_BASE}/v2/city`, { signal });
  if (!res.ok) throw new Error(`v2/city http ${res.status}`);
  return (await res.json()) as CityPayload;
}
