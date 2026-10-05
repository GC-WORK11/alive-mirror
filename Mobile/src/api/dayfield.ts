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

async function fetchSeries(lat: number, lon: number): Promise<DayCurve> {
  const series: (number | null)[] = new Array(DAY_HOURS).fill(null);
  let conf: DayCurve["conf"] = null;
  let covered = false;
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
        })
        .catch(() => {}) /* a dead hour is a hole — the sparkline skips it */,
    ),
  );
  return { series, conf, covered };
}

/** The day's hourly curve at a point — last-good cached under a ~500 m
 *  rounded cell key; offline → the previous curve returns `stale` via
 *  the fetchCached envelope the caller unwraps. */
export async function fetchDayCurve(lat: number, lon: number): Promise<DayCurve | null> {
  const r = await fetchCached<DayCurve>(`${API}/grid`, {
    ttlMs: 15 * 60 * 1000,
    key: `v2:daycurve:${lat.toFixed(2)},${lon.toFixed(2)}`,
    fetcher: async () => fetchSeries(lat, lon),
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
