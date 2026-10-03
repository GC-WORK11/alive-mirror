/**
 * routeTint self-test — node-runnable, zero RN imports in its graph.
 * Not a jest/vitest file (the app has no test runner); run it by emitting
 * the pure modules to CJS and executing with node:
 *
 *   cd Mobile
 *   npx tsc src/map/routeTint.test.ts --ignoreConfig --outDir /tmp/rgt-check \
 *     --module nodenext --moduleResolution nodenext --target es2022 \
 *     --skipLibCheck --esModuleInterop --strict --types geojson
 *   node /tmp/rgt-check/map/routeTint.test.js
 *
 * Prints "routeTint self-test OK" and exits 0 on pass; throws (exit 1)
 * on the first failed assertion.
 */
import { MAP_QUIET, MAP_WARN, MAP_HEAVY, MAP_SEVERE,
  collectionsFor,
  cumOf,
  featureFor,
  pmColor,
  resampleLine,
  TINT_STEP_M,
} from "./routeTint";

import type { StripSample } from "../nav/strip";
import type { Seg, V2Option } from "../components/shell/types";

let checks = 0;
const ok = (cond: boolean, msg: string) => {
  checks += 1;
  if (!cond) throw new Error(`routeTint self-test FAILED: ${msg}`);
};

const mkOption = (p: Partial<V2Option>): V2Option => ({
  mode: "car",
  vehicle: "car",
  label: "Car (AC)",
  eta_s: 600,
  duration_min: 10,
  distance_km: 1.1,
  dose: { lo: null, mid: null, hi: null, avg_conc_ugm3: null },
  emissions: { co2_kg: null },
  tag: null,
  recommended: false,
  reason_line: "",
  route_id: null,
  geometry: null,
  ...p,
});

/* ~1.1 km due east at Delhi latitude — two vertices only, so resampling
 * must interpolate interior cut points. */
const geom: GeoJSON.LineString = {
  type: "LineString",
  coordinates: [
    [77.2, 28.6],
    [77.2113, 28.6],
  ],
};
const total = cumOf(geom.coordinates as [number, number][]).pop()!;
ok(total > 900 && total < 1400, `geometry ~1.1 km, got ${total.toFixed(0)} m`);

/* ── resampleLine ─────────────────────────────────────────────────────── */
const chunks = resampleLine(geom.coordinates as [number, number][], TINT_STEP_M);
ok(chunks.length === Math.ceil(total / TINT_STEP_M), "chunk count = ceil(total/step)");
ok(chunks.every((c) => c.length >= 2), "every chunk has ≥2 points");
ok(
  chunks[0][0][0] === geom.coordinates[0][0] &&
    chunks[chunks.length - 1][chunks[chunks.length - 1].length - 1][0] ===
      geom.coordinates[geom.coordinates.length - 1][0],
  "chunks start at origin and end at destination",
);
const tiled = chunks
  .map((c) => cumOf(c).pop() ?? 0)
  .reduce((a, b) => a + b, 0);
ok(Math.abs(tiled - total) < 1, `chunks tile the route: ${tiled.toFixed(1)} vs ${total.toFixed(1)} m`);
ok(
  resampleLine([[77.2, 28.6], [77.201, 28.6]], TINT_STEP_M).length === 1,
  "sub-step line → single chunk",
);

/* ── strip path: fieldAtAlongM over fake samples ──────────────────────── */
// five strip samples — chunk ends at 250/500/750/1000/total m, pm25 ramp
// quiet → amber → orange → red → amber
const ends = [250, 500, 750, 1000, total];
const pm = [40, 80, 160, 300, 80];
const samples: StripSample[] = ends.map((e, i) => ({
  lat: 28.6,
  lon: 77.2 + (e / total) * 0.0113,
  dist_m: i === 0 ? e : e - ends[i - 1],
  pm25: pm[i],
  lo: pm[i] * 0.8,
  hi: pm[i] * 1.2,
}));
const optStrip = mkOption({ geometry: geom, route_id: "rid-a" });
const fcStrip = featureFor(optStrip, { strip: { route_id: "rid-a", mode: "car", step_m: 250, samples, emissions_curve: { mode: "car" } } });
ok(fcStrip.features.length === chunks.length, "strip path: one feature per chunk");
ok(
  fcStrip.features.every((f) => f.properties?.src === "strip"),
  "strip path: src=strip",
);
// chunk mids at 125/375/625/875/~(1000+total)/2 — interpolated pm25:
//  125→40(clamp)  375→60  625→120  875→230  ~1050→~190
ok(fcStrip.features[0].properties?.pm25 === 40, "chunk0 clamps to first sample (40)");
ok(fcStrip.features[0].properties?.color === MAP_QUIET, "chunk0 (<60) is quiet grey");
ok(fcStrip.features[1].properties?.color === MAP_WARN, "chunk1 (60) is amber");
ok(fcStrip.features[2].properties?.color === MAP_WARN, "chunk2 (120) is amber");
ok(fcStrip.features[3].properties?.color === MAP_HEAVY, "chunk3 (230) is orange");
ok(
  (fcStrip.features[3].properties?.pm25 ?? 0) > (fcStrip.features[0].properties?.pm25 ?? 1e9),
  "pm25 rises into the hot zone",
);
ok(
  fcStrip.features.every(
    (f) => f.properties?.color === pmColor(f.properties?.pm25),
  ),
  "every baked colour === pmColor(pm25) — one scale",
);
ok(
  fcStrip.features[0].properties?.lo != null && fcStrip.features[0].properties?.hi != null,
  "strip band lo/hi carried onto features",
);

/* ── option.segments path (legacy Seg seam) ───────────────────────────── */
const segs: Seg[] = [
  { start_frac: 0, end_frac: 0.5, dose_ug: 10, avg_conc_ugm3: 45, color: "#000000",
    coords: [[77.2, 28.6], [77.20565, 28.6]] },
  { start_frac: 0.5, end_frac: 1, dose_ug: 90, avg_conc_ugm3: 280, color: "#ffffff",
    coords: [[77.20565, 28.6], [77.2113, 28.6]] },
];
const fcSegs = featureFor(mkOption({ geometry: geom, segments: segs }));
ok(fcSegs.features.length === 2, "segments path: one feature per Seg");
ok(fcSegs.features[0].properties?.src === "segments", "segments path: src=segments");
// NOTE: Seg.color is server-side legacy scale — we re-tint on doseColor's
// scale so map colours agree with the compare sheet (assert overrides).
ok(fcSegs.features[0].properties?.color === MAP_QUIET, "seg avg 45 → quiet grey");
ok(fcSegs.features[1].properties?.color === MAP_SEVERE, "seg avg 280 → red");
ok(
  (fcSegs.features[0].geometry as GeoJSON.LineString).coordinates.length === 2,
  "seg coords carried verbatim",
);

/* ── fallback path: dose.avg_conc_ugm3 flat tint ──────────────────────── */
const fcAvg = featureFor(
  mkOption({ geometry: geom, dose: { lo: null, mid: null, hi: null, avg_conc_ugm3: 200 } }),
);
ok(fcAvg.features.length === chunks.length, "avg path: still chunked");
ok(
  fcAvg.features.every(
    (f) => f.properties?.pm25 === 200 && f.properties?.color === MAP_HEAVY && f.properties?.src === "avg",
  ),
  "avg path: flat 200 → orange everywhere, src=avg",
);
const fcNone = featureFor(mkOption({ geometry: geom }));
ok(
  fcNone.features.every((f) => f.properties?.pm25 === null && f.properties?.color === MAP_QUIET),
  "no data at all → null pm25 → quiet grey (never invented)",
);
ok(featureFor(mkOption({})).features.length === 0, "null geometry → empty collection");

/* ── collectionsFor: selected split by index AND by route_id ──────────── */
const optA = mkOption({ geometry: geom, route_id: "rid-a" });
const optB = mkOption({
  route_id: "rid-b",
  dose: { lo: null, mid: null, hi: null, avg_conc_ugm3: 300 },
  geometry: {
    type: "MultiLineString",
    coordinates: [
      [
        [77.2, 28.61],
        [77.205, 28.61],
      ],
      [
        [77.205, 28.61],
        [77.2113, 28.61],
      ],
    ],
  },
});
const byIdx = collectionsFor([optA, optB], 1);
ok(byIdx.alts.features.every((f) => f.properties?.opt === 0), "alts = unselected only");
ok(byIdx.selected.features.every((f) => f.properties?.opt === 1), "selected = chosen option");
ok(byIdx.perOption.length === 2, "perOption aligned with options");
ok(
  byIdx.selected.features.every((f) => f.properties?.color === MAP_SEVERE),
  "selected option tinted by its own avg (300 → red)",
);
const byId = collectionsFor([optA, optB], "rid-b");
ok(
  byId.selected.features.length === byIdx.selected.features.length,
  "route_id selection == index selection",
);
const stripMap = { "rid-a": { route_id: "rid-a", mode: "car", step_m: 250, samples, emissions_curve: { mode: "car" } } };
const withStrips = collectionsFor([optA, optB], 0, stripMap);
ok(
  withStrips.selected.features.some((f) => f.properties?.src === "strip"),
  "strips lookup by route_id feeds the selected option",
);
ok(
  withStrips.alts.features.every((f) => f.properties?.src === "avg"),
  "options without strips fall back to their dose average",
);

console.log(`routeTint self-test OK — ${checks} assertions`);
