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
};

type V2OutlookResponse = {
  days?: OutlookDay[];
  best_day?: Outlook["best_day"];
  flat?: boolean;
  verdict?: string;
  error?: string;                    // OUT_OF_AREA / "forecast unavailable"
};

/** CPCB category name (server districts.cpcb_band) → band index. Unknown
 *  names return null — the caller falls back to the mid's own colour. */
const CPCB_BAND_IDX: Record<string, number> = {
  good: 0, satisfactory: 1, moderate: 2, poor: 3, "very poor": 4, severe: 5,
};
export const bandIdxForName = (band: string | null | undefined): number | null =>
  band ? CPCB_BAND_IDX[band.trim().toLowerCase()] ?? null : null;

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
      const days = d.days.filter((x) => x && typeof x.pm25_mid === "number" && typeof x.label === "string");
      if (!days.length) throw new Error("no usable days");
      return {
        days,
        best_day: d.best_day ?? null,
        flat: !!d.flat,
        verdict: typeof d.verdict === "string" ? d.verdict : "",
      };
    },
  });
  if (!r.ok) return null;
  return r.data;
}
