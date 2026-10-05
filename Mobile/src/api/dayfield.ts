/** Per-cell hourly field — the morning card's data (alive-depth L2).
 *
 *  The field serves the CAMS-anchored forecast surface as GeoJSON cells:
 *  GET /grid?cells=N&param=pm2_5&h=H, one request per forecast hour. There
 *  is no single per-point day endpoint, so we fetch the h-series in
 *  parallel at a modest cell count, take the cell that actually contains
 *  the user, and cache the assembled curve ~15 min (the field's own
 *  refresh cadence) with last-good fallback through fetchCached.
 *
 *  Honesty contract: a failed hour is a hole (null), not a guess; a point
 *  outside the krige window gets `outside` — never a neighbouring cell's
 *  number relabelled as theirs.
 */
import { API, fetchJson } from "../components/shell/net";
import { fetchCached } from "../offline/net";

/** cells=8 over the served bbox → ~11×8 km cells: district-scale, the
 *  right fidelity for "your area today" without a heavyweight payload. */
const GRID_CELLS = 8;
/** forecast hours pulled — h=0 is "this hour" on the horizon */
export const DAY_HOURS = 12;

export type DayWindow = { from: number; to: number; conc: number };

export type DayCurve = {
  /** pm2.5 µg/m³ per forecast hour, index = hours ahead of `atIst`;
   *  null = that hour's fetch failed (a hole, not a guess) */
  series: (number | null)[];
  /** worst confidence the cell reported across the series */
  conf: "hi" | "med" | "lo" | null;
  /** whether the served grid covered the point at all */
  covered: boolean;
  /** server epoch-ish: the field's own refresh tag when present */
  epoch?: string;
  /** seconds since the served field was built — /v2/day's field_age_s
   *  (or the grid's cell_epoch on the fallback path). null = the card
   *  can't say how fresh its basis is, and must not imply one. */
  fieldAgeS?: number | null;
  /** the server's own stale verdict on that field, when it said one */
  fieldStale?: boolean | null;
  /** when /v2/day served the point: its windows + decision lines.
   *  Present means "the server answered" — windows may still be null
   *  on an honest flat/short day. */
  server?: {
    heavy: DayWindow | null;
    clean: DayWindow | null;
    decisions: { label: string; line: string }[];
    /** "17:30" IST labels the server generated — spare a client clock */
    heavyLabel?: string | null;
    cleanLabel?: string | null;
    heavyEndLabel?: string | null;
    cleanEndLabel?: string | null;
  };
};

/** Axis-aligned cell rect → containment. The grid's polygons are plain
 *  rectangles; testing the point against the ring's bbox IS the truth. */
function cellContains(feat: GeoJSON.Feature, lat: number, lon: number): boolean {
  const g = feat.geometry;
  if (!g || g.type !== "Polygon") return false;
  const ring = (g.coordinates as number[][][])[0];
  if (!ring || ring.length < 4) return false;
  let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
  for (const [x, y] of ring) {
    if (x < x0) x0 = x; if (x > x1) x1 = x;
    if (y < y0) y0 = y; if (y > y1) y1 = y;
  }
  return lon >= x0 && lon <= x1 && lat >= y0 && lat <= y1;
}

function pickCell(fc: GeoJSON.FeatureCollection, lat: number, lon: number) {
  const feats = fc?.features ?? [];
  for (const f of feats) if (cellContains(f, lat, lon)) return f;
  return null;
}

const confRank = (c: unknown): number => (c === "hi" ? 2 : c === "med" ? 1 : c === "lo" ? 0 : -1);

/** /grid?h= stamps cell_epoch [forecast_fetch, field_fetch, obs_ver] —
 *  index 1 is the live field's own build epoch (plain /grid stores it
 *  at 0). Epoch seconds, not ms. */
const fieldAgeFromEpoch = (fc: GeoJSON.FeatureCollection): number | null => {
  const ep = (fc as { properties?: { cell_epoch?: unknown[] } })
    .properties?.cell_epoch;
  if (!Array.isArray(ep)) return null;
  const fieldEp = ep.length >= 2 ? ep[1] : ep[0];
  return typeof fieldEp === "number" && Number.isFinite(fieldEp)
    ? Math.max(0, Date.now() / 1000 - fieldEp)
    : null;
};

async function fetchSeries(lat: number, lon: number): Promise<DayCurve> {
  const series: (number | null)[] = new Array(DAY_HOURS).fill(null);
  let conf: DayCurve["conf"] = null;
  let covered = false;
  let fieldAgeS: number | null = null;
  // parallel — the waterfall version costs ~12× a round-trip
  await Promise.all(
    Array.from({ length: DAY_HOURS }, (_, h) =>
      fetchJson(`${API}/grid?cells=${GRID_CELLS}&param=pm2_5&h=${h}`, 12000)
        .then((fc) => {
          const cell = pickCell(fc, lat, lon);
          if (!cell) return;
          covered = true;
          const v = (cell.properties as Record<string, unknown> | undefined)?.pm25;
          if (typeof v === "number" && Number.isFinite(v)) series[h] = v;
          const c = (cell.properties as Record<string, unknown> | undefined)?.conf;
          const cr = confRank(c);
          if (cr >= 0 && (conf === null || confRank(conf) > cr)) conf = c as DayCurve["conf"];
          if (fieldAgeS == null) fieldAgeS = fieldAgeFromEpoch(fc);
        })
        .catch(() => {}) /* a dead hour is a hole — the sparkline skips it */,
    ),
  );
  return { series, conf, covered, fieldAgeS };
}

/* ---- /v2/day: the server's day-at-a-point -------------------------------
 * One request replaces the 12-request h-series when the backend serves it
 * (per-hour mid/lo/hi + heavy/cleanest windows + decision lines). Old
 * servers 404 → we fall back to the grid derivation. */
type V2DayHour = {
  h: number; ist_label: string;
  pm25_mid: number; pm25_lo: number | null; pm25_hi: number | null;
  confidence?: string;
};
type V2DayWindow = {
  start_h: number; end_h: number | null;
  start_label?: string; end_label?: string | null;
  pm25_mid?: number; basis?: string;
};
type V2DayResponse = {
  hours?: V2DayHour[];
  heavy_window?: V2DayWindow | null;
  cleanest_window?: V2DayWindow | null;
  decisions?: { label: string; line: string }[];
  /** the served field's own age + verdict — the card's 'as of' */
  field_age_s?: number | null;
  field?: { age_s?: number | null; stale?: boolean | null } | null;
  error?: string;
};

const mapWin = (w: V2DayWindow | null | undefined, series: (number | null)[]): DayWindow | null => {
  if (!w || typeof w.start_h !== "number") return null;
  const slice = series.slice(w.start_h, w.end_h ?? series.length).filter((v): v is number => v != null);
  const conc = typeof w.pm25_mid === "number" ? w.pm25_mid
    : slice.length ? slice.reduce((s, x) => s + x, 0) / slice.length : null;
  if (conc == null) return null;
  return { from: w.start_h, to: w.end_h ?? series.length, conc };
};

async function fetchDayServer(lat: number, lon: number): Promise<DayCurve | null> {
  try {
    const d = (await fetchJson(`${API}/v2/day?lat=${lat}&lon=${lon}`, 8000)) as V2DayResponse;
    if (!d || !Array.isArray(d.hours) || d.error) return null;
    const series: (number | null)[] = [];
    let conf: DayCurve["conf"] = null;
    for (const h of d.hours) {
      if (typeof h.h !== "number" || typeof h.pm25_mid !== "number") continue;
      series[h.h] = h.pm25_mid;
      const cr = confRank(h.confidence);
      if (cr >= 0 && (conf === null || confRank(conf) > cr)) conf = h.confidence as DayCurve["conf"];
    }
    if (!series.some((v) => v != null)) return null;
    return {
      series,
      conf,
      covered: true,
      fieldAgeS:
        typeof d.field_age_s === "number" ? d.field_age_s : d.field?.age_s ?? null,
      fieldStale: d.field?.stale === true,
      server: {
        heavy: mapWin(d.heavy_window, series),
        clean: mapWin(d.cleanest_window, series),
        decisions: (d.decisions ?? []).filter((x) => x && typeof x.line === "string"),
        heavyLabel: d.heavy_window?.start_label ?? null,
        cleanLabel: d.cleanest_window?.start_label ?? null,
        heavyEndLabel: d.heavy_window?.end_label ?? null,
        cleanEndLabel: d.cleanest_window?.end_label ?? null,
      },
    };
  } catch {
    return null; // 404 on older servers / any parse wobble → grid path
  }
}

/** The day's hourly curve at a point — prefers /v2/day (one request),
 *  falls back to the 12-payload grid derivation; last-good cached under
 *  a ~500 m rounded cell key; offline → the previous curve returns
 *  `stale` via the fetchCached envelope the caller unwraps. */
export async function fetchDayCurve(lat: number, lon: number): Promise<DayCurve | null> {
  const r = await fetchCached<DayCurve>(`${API}/grid`, {
    ttlMs: 15 * 60 * 1000,
    key: `v2:daycurve:${lat.toFixed(2)},${lon.toFixed(2)}`,
    fetcher: async () => (await fetchDayServer(lat, lon)) ?? fetchSeries(lat, lon),
  });
  if (!r.ok) return null;
  return r.data;
}

/* ---- the morning answers ------------------------------------------------
 * Derived client-side from the h-series — three answers, each honest:
 * the day's heaviest contiguous window, its cleanest window, and the ONE
 * decision the swing changes ("same errand at X instead of Y breathes N×
 * lighter") — never "don't go out", always the cheaper-for-lungs version
 * of the same plan. A flat day says it's flat. */

export type MorningAnswers = {
  /** heaviest ~3h window */
  heavy: { from: number; to: number; conc: number } | null;
  /** cleanest ~3h window (at least 2 valid hours inside) */
  clean: { from: number; to: number; conc: number } | null;
  /** heavy-to-clean ratio — the decision's real weight */
  ratio: number | null;
  /** true when the day's spread is too small to claim windows */
  flat: boolean;
};

export function morningAnswers(series: (number | null)[]): MorningAnswers {
  const vals = series.filter((v): v is number => v != null);
  if (vals.length < 3) return { heavy: null, clean: null, ratio: null, flat: true };
  const W = 3;
  let heavy: { from: number; to: number; conc: number } | null = null;
  let clean: { from: number; to: number; conc: number } | null = null;
  for (let i = 0; i + W <= series.length; i++) {
    const w = series.slice(i, i + W);
    const ok = w.filter((v): v is number => v != null);
    if (ok.length < 2) continue;
    const mean = ok.reduce((s, x) => s + x, 0) / ok.length;
    if (!heavy || mean > heavy.conc) heavy = { from: i, to: i + W, conc: mean };
    if (!clean || mean < clean.conc) clean = { from: i, to: i + W, conc: mean };
  }
  if (!heavy || !clean) return { heavy, clean, ratio: null, flat: true };
  const ratio = clean.conc > 0 ? heavy.conc / clean.conc : null;
  // a <20% swing reads "flat" — no honest window to pick
  const flat = ratio != null && ratio < 1.2;
  return { heavy, clean, ratio, flat };
}
