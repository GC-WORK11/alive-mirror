/** The days ahead — GET /v2/outlook: the server's per-day fold of its REAL
 *  120h CAMS horizon (today's remainder + up to four IST days; the last is
 *  often a sliver, served `partial`, never padded into a fake week).
 *
 *  Same live-anchored machinery as /v2/day — the client renders what the
 *  endpoint serves, nothing derived client-side: a dead or bare endpoint
 *  means no card, not a synthesized week. Last-good cache (~15 min, the
 *  field's own refresh cadence) rides through fetchCached; a first-run
 *  failure returns null and the caller hides the card.
 */
import { API, fetchJson } from "../components/shell/net";
import { fetchCached } from "../offline/net";

/** ≥_CLEAN_UG pm2.5 and the server calls its best day 'least-bad', not
 *  'cleanest' — same threshold, mirrored for the marker + verdict word. */
export const CLEAN_UG = 60;

export type OutlookWindow = {
  start_h?: number;
  end_h?: number | null;
  start_label?: string;
  end_label?: string | null;
  pm25_mid?: number;
  basis?: string;
};

export type OutlookDay = {
  date_ist: string;                  // IST civil date, e.g. "2026-10-07"
  label: string;                     // "today" | "tomorrow" | weekday name
  partial: boolean;                  // <24 slots served — remainder/sliver
  n_hours: number;
  pm25_mid: number;
  pm25_lo: number | null;
  pm25_hi: number | null;
  band: string;                      // modal CPCB category of the day
  heavy_hours_ist: string[];         // IST start-labels ≥ mean+¼·spread
  cleanest_window: OutlookWindow | null;
  confidence: "hi" | "med" | "lo" | string;
  note?: string;
};

export type Outlook = {
  days: OutlookDay[];
  best_day: {
    date_ist: string; label: string; pm25_mid: number;
    n_hours: number; partial: boolean; delta_vs_mean: number; line: string;
  } | null;
  flat: boolean;
  verdict: string;                   // the one honest sentence, verbatim
  /** the served field's own age — today's anchor basis 'as of'.
   *  null = the card can't say how fresh today's basis is. */
  fieldAgeS?: number | null;
  /** the server's own stale verdict on that field */
  fieldStale?: boolean | null;
};

type V2OutlookResponse = {
  days?: OutlookDay[];
  best_day?: Outlook["best_day"];
  flat?: boolean;
  verdict?: string;
  field_age_s?: number | null;
  field?: { age_s?: number | null; stale?: boolean | null } | null;
  error?: string;                    // OUT_OF_AREA / "forecast unavailable"
};

/** CPCB category name (server districts.cpcb_band) → band index. Unknown
 *  names return null — the caller falls back to the mid's own colour. */
const CPCB_BAND_IDX: Record<string, number> = {
  good: 0, satisfactory: 1, moderate: 2, poor: 3, "very poor": 4, severe: 5,
};
export const bandIdxForName = (band: string | null | undefined): number | null =>
  band ? CPCB_BAND_IDX[band.trim().toLowerCase()] ?? null : null;

/** Shape the wire payload into a render-safe Outlook. Days keep every field
 *  the card dereferences safe — `heavy_hours_ist` is coerced to a string list
 *  (the detail reads `.length` unconditionally) — and `best_day` only
 *  survives when its caption fields are actually present, since the Hindi
 *  caption calls `label.trim()`. Runs inside the fetcher AND on cached data
 *  read back, so a malformed payload — live or stale — degrades to a
 *  hidden card/marker instead of a render-time TypeError. */
export function normalizeOutlook(d: V2OutlookResponse | Outlook): Outlook {
  const days = (Array.isArray(d.days) ? d.days : [])
    .filter((x): x is OutlookDay => !!x && typeof x.pm25_mid === "number" && typeof x.label === "string")
    .map((x) => ({
      ...x,
      heavy_hours_ist: Array.isArray(x.heavy_hours_ist)
        ? x.heavy_hours_ist.filter((h): h is string => typeof h === "string")
        : [],
      cleanest_window:
        x.cleanest_window && typeof x.cleanest_window === "object" ? x.cleanest_window : null,
    }));
  if (!days.length) throw new Error("no usable days");
  const b = d.best_day;
  const best_day =
    b && typeof b === "object" && typeof b.label === "string" && typeof b.pm25_mid === "number"
      ? {
          date_ist: typeof b.date_ist === "string" ? b.date_ist : "",
          label: b.label,
          pm25_mid: b.pm25_mid,
          n_hours: typeof b.n_hours === "number" ? b.n_hours : 0,
          partial: !!b.partial,
          delta_vs_mean: typeof b.delta_vs_mean === "number" ? b.delta_vs_mean : 0,
          line: typeof b.line === "string" ? b.line : "",
        }
      : null;
  /* 'as of' survives normalization — accept the wire shape
     (field_age_s / field.stale) and an already-normalized Outlook
     read back from cache. */
  const wire = d as V2OutlookResponse;
  const fs = (d as Outlook).fieldAgeS;
  const fst = (d as Outlook).fieldStale;
  return {
    days,
    best_day,
    flat: !!d.flat,
    verdict: typeof d.verdict === "string" ? d.verdict : "",
    fieldAgeS:
      typeof fs === "number" ? fs
        : typeof wire.field_age_s === "number" ? wire.field_age_s
          : wire.field?.age_s ?? null,
    fieldStale: wire.field?.stale === true || fst === true,
  };
}

/** Fetch the folded outlook at a point — the same anchor the morning card
 *  uses. Anything that isn't a real outlook (error field, empty days)
 *  throws inside the fetcher so a wobble serves last-good instead of
 *  wiping the card; an empty cache → null → the card stays hidden. */
export async function fetchOutlook(lat: number, lon: number): Promise<Outlook | null> {
  const r = await fetchCached<Outlook>(`${API}/v2/outlook`, {
    ttlMs: 15 * 60 * 1000,
    key: `v2:outlook:${lat.toFixed(2)},${lon.toFixed(2)}`,
    fetcher: async () => {
      const d = (await fetchJson(`${API}/v2/outlook?lat=${lat}&lon=${lon}`, 8000)) as V2OutlookResponse;
      if (!d || d.error || !Array.isArray(d.days) || d.days.length === 0) throw new Error("no outlook");
      return normalizeOutlook(d);
    },
  });
  if (!r.ok) return null;
  /* A cache entry written before normalization existed — or a corrupted
     last-good — gets the same pass on the way out; a totally broken blob
     hides the card rather than crashing it. */
  try {
    return normalizeOutlook(r.data);
  } catch {
    return null;
  }
}
