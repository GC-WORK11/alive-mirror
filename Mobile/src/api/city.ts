// GET /v2/city — the "Delhi today" consumer payload (docs/plan/07 §1).
// The screen shows aggregates only: a day-of-breathing band, k>=3 street
// corridors, field freshness — nothing personal ever leaves the store.
//
// Base URL: API_BASE from search/client — the one resolution rule
// (EXPO_PUBLIC_API_URL, else the emulator loopback aliases). Re-resolving
// here would let this screen drift from the shell's backend.
import { API_BASE } from "../search/client";
import { cacheKeys } from "./cache";
import { fetchCached, linkSignals } from "../offline/net";

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

// Contract-sync: shadows Bridge/contract.ts V2CityResponse (duplicated,
// not imported — see the header note there; test_contract_sync.py holds
// the wire honest in both directions).
export type CityPayload = {
  ts: number;
  generated_at?: string;
  pm25_stats?: { n: number; mean?: number; median?: number; max?: number };
  /** Every other real species the field serves — lattice mean/median/max
      over the same NCR points; a species is omitted when the serving
      field has no data for it (never guessed). */
  species?: Record<
    string,
    { mean: number; median: number; max: number; n: number }
  >;
  /** Decade-climatology vs now at the city centroid — omitted when the
      archive or the live mean is missing (no fabricated baseline). */
  typical?: {
    month: number;
    hour_ist: number;
    median: number;
    p25?: number | null;
    p75?: number | null;
    vs_now_pct?: number | null;
  } | null;
  /** Live-anchored CAMS forecast at the centroid — next 12 hours. */
  next_hours?: { h: number; start: string | null; pm25: number }[] | null;
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
  /** "Why tonight" — the causal read line (Bridge contract: null when the
      explainer can't run — the number stands alone before it guesses). */
  why?: { line: string | null;
          /** The parali/news line — plain-words context built only from
              measured fields (belt detections, carry wind, ventilation,
              recorded city mean). Canonical English; `cause_note_fields`
              carries the ingredient set for re-localization. */
          cause_note?: string | null;
          cause_note_fields?: Record<string, unknown> | null;
          drivers: { kind: string; weight: string; score: number;
                     evidence: string; direction?: string }[];
          why_url: string } | null;
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

/** One shot at `${API_BASE}/v2/city`, last-good cached: offline → the
 * previous payload returns and the net-status pill labels it stale.
 * Caller owns the AbortSignal for cancel-not-cache semantics — aborts
 * fall through to the cache like any other failure. */
export async function fetchCity(signal?: AbortSignal): Promise<CityPayload> {
  const r = await fetchCached<CityPayload>(`${API_BASE}/v2/city`, {
    ttlMs: 15 * 60 * 1000,
    key: cacheKeys.city(),
    fetcher: async (sig) => {
      /* caller cancel AND the cache timeout must both reach the wire —
         signal ?? sig dropped the timeout and hung the skeleton
         forever on a dead-but-up server. */
      const res = await fetch(`${API_BASE}/v2/city`, { signal: linkSignals(signal, sig) });
      if (!res.ok) throw new Error(`v2/city http ${res.status}`);
      return (await res.json()) as CityPayload;
    },
  });
  if (!r.ok) throw new Error("v2/city unreachable");
  /* last-good: the payload's own "updated N min ago" was stamped when
     the server built it — add the time it sat in cache so the chip
     doesn't claim a 40-minute-old read is "10 min old". */
  if (r.stale) {
    const d = { ...r.data };
    if (d.freshness) {
      d.freshness = {
        ...d.freshness,
        field_age_s: d.freshness.field_age_s == null ? null : d.freshness.field_age_s + r.ageS,
        age_min: d.freshness.age_min == null ? null : Math.round(d.freshness.age_min + r.ageS / 60),
        label: "stale",
      };
    } else if (d.field_age_s != null) {
      d.field_age_s = d.field_age_s + r.ageS;
    }
    return d;
  }
  return r.data;
}

/* ---- GET /v2/city/moves — "how Delhi moves" (server/v2/city.py) ----------
 * Aggregate mobility only: mode share, active corridor count, per-trip
 * dose/emission percentile bands. Every emitted row clears k>=3 — a mode
 * with fewer trips never gets a row of its own (it pools into "other",
 * itself k-gated, or ships only as a suppressed count). */

/** The honest middle half of a small sample. n is the row count behind
 *  the band — the UI can say how thin the data is instead of guessing. */
export type CityMovesBand = { p25: number; p50: number; p75: number; n: number };

export type CityMovesModeRow = {
  /** server mode id ("car", "metro", …) or the pooled "other" bucket */
  mode: string;
  trips: number;
  /** trips / n_trips across the window */
  share: number;
};

// Contract-sync: shadows Bridge/contract.ts V2CityMovesResponse.
export type CityMovesPayload = {
  ts: number;
  generated_at?: string;
  /** trailing UTC day buckets the day counters span (server: 7) */
  window?: { days: number; from: string; to: string };
  min_k: number;
  n_trips: number;
  n_days: number;
  /** true while n_trips < min_k — show the empty state, never the
   *  distributions; the counts themselves are still real. */
  insufficient_data: boolean;
  /** only rows with >= min_k trips; may be empty even when trips exist */
  mode_share: CityMovesModeRow[];
  /** trips below the k threshold even when pooled — a count, not a row */
  mode_share_suppressed_trips: number;
  corridors?: {
    /** the corridor rule's own window (server: 72) */
    window_h: number;
    /** publishable cells right now — each >=3 distinct devices */
    active: number;
    /** every cell ever seen — context, not gated */
    tracked: number;
    /** distribution of per-cell mean dose across publishable cells */
    avg_dose_ug: CityMovesBand | null;
  };
  per_trip?: {
    /** days that qualified (>=min_k trips) — the band's real sample */
    n_days: number;
    dose_ug: CityMovesBand | null;
    co2_kg: CityMovesBand | null;
    pm25_g: CityMovesBand | null;
    basis?: string;
  };
  basis?: string;
};

/** Last-good cache key — mirrors cacheKeys' naming ("v2:…"); kept local
 *  so this lane touches only this file (cache.ts is shared). */
const MOVES_CACHE_KEY = "v2:city:moves";

/** One shot at `${API_BASE}/v2/city/moves`, last-good cached like
 *  fetchCity — offline serves the previous aggregate labelled stale. */
export async function fetchCityMoves(
  signal?: AbortSignal,
): Promise<CityMovesPayload> {
  const r = await fetchCached<CityMovesPayload>(`${API_BASE}/v2/city/moves`, {
    ttlMs: 15 * 60 * 1000,
    key: MOVES_CACHE_KEY,
    fetcher: async (sig) => {
      const res = await fetch(`${API_BASE}/v2/city/moves`, {
        signal: linkSignals(signal, sig),
      });
      if (!res.ok) throw new Error(`v2/city/moves http ${res.status}`);
      return (await res.json()) as CityMovesPayload;
    },
  });
  if (!r.ok) throw new Error("v2/city/moves unreachable");
  return r.data;
}
