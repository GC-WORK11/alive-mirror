/**
 * routeTint — per-segment AQI shading for /v2/plan route polylines.
 * Lane r4-routegrad. Pure math + types: NO React Native / MapLibre imports,
 * so the whole module unit-tests under plain node (see routeTint.test.ts
 * header for the tsc→node recipe). The MapLibre binding is
 * src/components/RouteTint.tsx.
 *
 * ── WIRING CONTRACT (what App.tsx / useShellFlow passes) ──────────────────
 * Input is the V2Option set from planOptions() (POST /v2/plan). Each option
 * already carries everything this module can consume — nothing here fetches:
 *
 *   option.geometry            GeoJSON LineString (`route_geojson`) — REQUIRED
 *   option.route_id?           → caller fetches GET /v2/strip and passes the
 *                              RouteStrip in via `strips` (see StripLookup)
 *   option.segments?           legacy per-segment strip seam (Seg[] with
 *                              avg_conc_ugm3 + coords, server/segments.py) —
 *                              consumed verbatim when a payload carries it
 *   option.dose.avg_conc_ugm3? route-mean concentration — flat fallback tint
 *                              when no per-segment data exists yet
 *
 * Data priority per option:  option.segments  >  strip samples  >  dose.avg
 * (`segments` and strip both carry real per-position field values; the dose
 * average is honest — it IS the option's mean — just spatially flat.)
 *
 *   // caller side, once per plan fetch (compare phase):
 *   const [strips, setStrips] = useState<Record<string, RouteStrip>>({});
 *   options.forEach((o) => o.route_id &&
 *     fetchStrip(o.route_id).then((s) =>
 *       setStrips((m) => (m[o.route_id!] ? m : { ...m, [o.route_id!]: s })))
 *       .catch(() => {}));
 *   const tint = collectionsFor(options, selected, strips);   // memo this
 *
 * `collectionsFor` returns { alts, selected, perOption } FeatureCollections;
 * every feature is a short LineString with properties:
 *   pm25   µg/m³ field concentration at the chunk midpoint (null = unknown)
 *   lo, hi the strip's band edges at that point (null when no strip)
 *   color  baked doseColor() value — the existing layers' ["get","color"]
 *   seg    chunk index within the option   opt   option index
 *   src    "segments" | "strip" | "avg" | "none" — which path supplied pm25
 *
 * Drop-in for the existing useShellFlow memos: `routeSegs` ←
 * collectionsFor(...).selected, `altSegs` ← .alts — both App.tsx layers
 * already paint ["get","color"]. Or mount <RouteTintSource/> and delete
 * the "alts"+"route" GeoJSONSources entirely (preferred — see that file).
 *
 * COLOUR SCALE — same THRESHOLDS as theme.doseColor, muted editorial hues
 * tuned for the light basemap (bronze → brick → wine, never neon):
 *   null or pm25 < 60  → MAP_QUIET   #8A93A3  quiet = absence of colour
 *   60 ≤ pm25 < 130    → MAP_WARN    #B0763B  bronze
 *   130 ≤ pm25 < 250   → MAP_HEAVY   #B05355  brick
 *   pm25 ≥ 250         → MAP_SEVERE  #8A2D3E  wine
 * ──────────────────────────────────────────────────────────────────────────
 */

import {
  fieldAtAlongM,
  stripCumM,
  type RouteStrip,
  type StripSample,
} from "../nav/strip";
import { flattenCoords, havM, type LonLat } from "../nav/offroute";
import type { V2Option } from "../components/shell/types";

/** Chunk length — matches server/v2/strip.py STEP_M so tint chunks land on
 *  the same ~250 m cadence the strip samples at. */
export const TINT_STEP_M = 250;

/** doseColor() thresholds (µg/m³) — the single scale every surface shares. */
export const PM25_BANDS = { quiet: 60, warn: 130, severe: 250 } as const;

/** On-map ramp — muted editorial twin of the chrome dose ramp (light
 *  basemap: same bands, hues deepened to read on paper, not neon). */
export const MAP_QUIET = "#8A93A3";
export const MAP_WARN = "#B0763B";   // muted bronze
export const MAP_HEAVY = "#B05355";  // dusty brick
export const MAP_SEVERE = "#8A2D3E"; // deep wine

/** µg/m³ → hex colour for the light map — same bands as theme.doseColor. */
export const pmColor = (pm25: number | null | undefined) =>
  pm25 == null || pm25 < PM25_BANDS.quiet ? MAP_QUIET
    : pm25 < PM25_BANDS.warn ? MAP_WARN
    : pm25 < PM25_BANDS.severe ? MAP_HEAVY
    : MAP_SEVERE;


/** Anything a caller can hand us as "the strip": a full RouteStrip, a bare
 *  sample array, or nothing. */
export type StripLike = RouteStrip | StripSample[] | null | undefined;

/** How a caller supplies strips for many options — keyed by route_id as a
 *  plain map, a Map, or a lookup callback (e.g. reading a ref/store). */
export type StripLookup =
  | Record<string, StripLike>
  | ReadonlyMap<string, StripLike>
  | ((routeId: string) => StripLike)
  | null
  | undefined;

export type TintOpts = {
  /** chunk length in metres (default TINT_STEP_M = 250) */
  stepM?: number;
  /** strip for THIS option — see StripLike */
  strip?: StripLike;
  /** flat tint override; defaults to option.dose.avg_conc_ugm3 */
  fallbackPm25?: number | null;
};

/** Per-feature properties on every emitted LineString. */
export type TintProps = {
  pm25: number | null;
  lo: number | null;
  hi: number | null;
  color: string;
  seg: number;
  opt: number;
  src: "segments" | "strip" | "avg" | "none";
};

const FC = (features: GeoJSON.Feature[]): GeoJSON.FeatureCollection => ({
  type: "FeatureCollection",
  features,
});

const feat = (
  coords: LonLat[] | number[][],
  pm25: number | null,
  lo: number | null,
  hi: number | null,
  seg: number,
  opt: number,
  src: TintProps["src"],
): GeoJSON.Feature => ({
  type: "Feature",
  properties: { pm25, lo, hi, color: pmColor(pm25), seg, opt, src } satisfies TintProps,
  geometry: { type: "LineString", coordinates: coords },
});

const samplesOf = (strip: StripLike): StripSample[] => {
  if (!strip) return [];
  if (Array.isArray(strip)) return strip;
  return Array.isArray(strip.samples) ? strip.samples : [];
};

const lookupStrip = (strips: StripLookup, o: V2Option): StripLike => {
  const id = o.route_id;
  if (!id || !strips) return null;
  if (typeof strips === "function") return strips(id) ?? null;
  const get = (strips as { get?: unknown }).get;
  if (typeof get === "function") {
    return (get as (k: string) => StripLike).call(strips, id) ?? null;
  }
  return (strips as Record<string, StripLike>)[id] ?? null;
};

/** Cumulative along-route metres at each vertex ([lon,lat] in, metres out).
 *  Same haversine as nav/offroute — one implementation, one truth. */
export function cumOf(coords: LonLat[]): number[] {
  const cum: number[] = [0];
  for (let i = 1; i < coords.length; i++) {
    cum.push(
      cum[i - 1] +
        havM(coords[i - 1][1], coords[i - 1][0], coords[i][1], coords[i][0]),
    );
  }
  return cum;
}

const pushPt = (cur: LonLat[], p: LonLat) => {
  const q = cur[cur.length - 1];
  if (Math.abs(p[0] - q[0]) > 1e-12 || Math.abs(p[1] - q[1]) > 1e-12) cur.push(p);
};

/** Cut a polyline into contiguous chunks of ≈stepM, slicing edges at exact
 *  boundary points (linear lon/lat interpolation — error «1 m at these
 *  lengths). Chunk k spans along-route metres [k·stepM, min((k+1)·stepM,
 *  total)] — the caller derives each chunk's midpoint for the strip query.
 *  Zero-length repeats are dropped; chunk order follows travel direction. */
export function resampleLine(coords: LonLat[], stepM = TINT_STEP_M): LonLat[][] {
  const n = coords.length;
  if (n < 2) return [];
  if (!(stepM > 0)) return [coords.slice()];
  const cum = cumOf(coords);
  const total = cum[n - 1];
  if (!(total > 0)) return [coords.slice()];

  const chunks: LonLat[][] = [];
  let cur: LonLat[] = [coords[0]];
  let nextB = stepM;
  for (let i = 1; i < n; i++) {
    const a = coords[i - 1];
    const b = coords[i];
    const s0 = cum[i - 1];
    const s1 = cum[i];
    const span = s1 - s0;
    while (nextB <= s1) {
      const t = span > 0 ? Math.min(1, Math.max(0, (nextB - s0) / span)) : 1;
      pushPt(cur, [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]);
      if (cur.length >= 2) chunks.push(cur);
      cur = [cur[cur.length - 1]];
      nextB += stepM;
    }
    pushPt(cur, b);
  }
  if (cur.length >= 2) chunks.push(cur);
  return chunks;
}

/** One option → a FeatureCollection of short LineStrings, each shaded by
 *  the field PM2.5 at its midpoint.
 *
 *  Resolution order (see header):
 *   1. option.segments — verbatim coords, pm25 = avg_conc_ugm3 (null →
 *      strip probe at the seg's mid-fraction → dose average → null)
 *   2. strip samples   — geometry resampled to ~stepM chunks; each chunk's
 *      pm25 = fieldAtAlongM at its midpoint, with the strip's odometer
 *      rescaled onto geometry metres when the two totals disagree (both
 *      describe the same path; the ratio is ~1 modulo sampling)
 *   3. fallback        — option.dose.avg_conc_ugm3 as a flat tint, still
 *      chunked so the shape + property contract is uniform
 *
 *  MultiLineString flattens to one polyline (contiguous legs — the same
 *  documented approximation offroute.flattenCoords already makes). */
export function featureFor(
  option: V2Option,
  opts: TintOpts = {},
  optIdx = 0,
): GeoJSON.FeatureCollection {
  const stepM = opts.stepM ?? TINT_STEP_M;
  const fallback = opts.fallbackPm25 ?? option.dose?.avg_conc_ugm3 ?? null;
  const coords = flattenCoords(option.geometry);
  const geomCum = cumOf(coords);
  const geomTotal = geomCum[geomCum.length - 1] ?? 0;

  const samples = samplesOf(opts.strip);
  const stripCum = stripCumM(samples);
  const stripTotal = stripCum[stripCum.length - 1] ?? 0;
  // geometry metres → strip metres (clamps inside fieldAtAlongM either way)
  const scale = geomTotal > 0 && stripTotal > 0 ? stripTotal / geomTotal : 1;
  const atM = (alongM: number) =>
    samples.length
      ? fieldAtAlongM(samples, stripCum, alongM * scale)
      : { lo: null, mid: null, hi: null };

  // 1 — server per-segment payload (the `segments` seam on V2Option)
  const segs = (option.segments ?? []).filter(
    (s) => Array.isArray(s.coords) && s.coords.length >= 2,
  );
  if (segs.length) {
    return FC(
      segs.map((sg, i) => {
        const midFrac = ((sg.start_frac ?? 0) + (sg.end_frac ?? 0)) / 2;
        const probe = sg.avg_conc_ugm3 == null ? atM(midFrac * geomTotal) : null;
        const pm25 = sg.avg_conc_ugm3 ?? probe?.mid ?? fallback;
        return feat(sg.coords, pm25, probe?.lo ?? null, probe?.hi ?? null, i, optIdx, "segments");
      }),
    );
  }

  // 2/3 — resampled chunks tinted by the strip, else the flat dose average
  if (coords.length < 2) return FC([]);
  const chunks = resampleLine(coords, stepM);
  const src: TintProps["src"] = samples.length
    ? "strip"
    : fallback != null
      ? "avg"
      : "none";
  return FC(
    chunks.map((ch, i) => {
      const a0 = Math.min(i * stepM, geomTotal);
      const a1 = Math.min((i + 1) * stepM, geomTotal);
      const probe = atM((a0 + a1) / 2);
      const pm25 = probe.mid ?? fallback;
      return feat(ch, pm25, probe.lo, probe.hi, i, optIdx, src);
    }),
  );
}

export type TintCollections = {
  /** merged features of every NON-selected option — render dim/thin */
  alts: GeoJSON.FeatureCollection;
  /** merged features of the selected option — render full width on top */
  selected: GeoJSON.FeatureCollection;
  /** per-option collections aligned with `options` (one entry each — the
   *  precomputed cache if a caller wants per-option sources or reuse) */
  perOption: GeoJSON.FeatureCollection[];
};

/** All options → { alts, selected, perOption }. `selected` is either the
 *  option INDEX (App's flow.selected) or a route_id string — both are
 *  supported so the compare screen and any future id-keyed store wire up
 *  without reshaping state. Pure; memoize the call (useMemo on
 *  [options, selected, strips]) — the per-option work runs once per plan
 *  fetch, never per render. */
export function collectionsFor(
  options: V2Option[],
  selected: number | string | null | undefined,
  strips?: StripLookup,
  opts: Omit<TintOpts, "strip"> = {},
): TintCollections {
  const perOption = options.map((o, i) =>
    featureFor(o, { ...opts, strip: lookupStrip(strips, o) }, i),
  );
  const isSel = (o: V2Option, i: number) =>
    typeof selected === "number"
      ? i === selected
      : typeof selected === "string"
        ? o.route_id === selected
        : false;
  const altFeats: GeoJSON.Feature[] = [];
  const selFeats: GeoJSON.Feature[] = [];
  perOption.forEach((fc, i) =>
    (isSel(options[i], i) ? selFeats : altFeats).push(...fc.features),
  );
  return { alts: FC(altFeats), selected: FC(selFeats), perOption };
}
