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
import { MAP_QUIET,
  navCollectionsFor,
  candidatesFor,
  chooserVerdict,
  collectionsFor,
  cumOf,
  featureFor,
  pmColor,
  pointAtFrac,
  resampleLine,
  TINT_STEP_M,
} from "./routeTint";
import { bandColor } from "../theme";

import type { StripSample } from "../nav/strip";
import type { Seg, V2Option } from "../components/shell/types";

/* CPCB ramp hexes (theme.V2T.band*) the assertions below expect. */
const SAT = bandColor(45)!, MOD = bandColor(75)!,
  POOR = bandColor(110)!, VPOOR = bandColor(200)!, SEVERE = bandColor(300)!;

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
ok(fcStrip.features[0].properties?.color === SAT, "chunk0 (40) is CPCB satisfactory");
ok(fcStrip.features[1].properties?.color === SAT, "chunk1 (60) is satisfactory");
ok(fcStrip.features[2].properties?.color === POOR, "chunk2 (120) is poor");
ok(fcStrip.features[3].properties?.color === VPOOR, "chunk3 (230) is very poor");
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

/* ── option.segments path — legacy Seg seam AND the v2/plan
      {geometry, pm25, band} wire are both accepted ──────────────────── */
const segs: Seg[] = [
  { start_frac: 0, end_frac: 0.5, dose_ug: 10, avg_conc_ugm3: 45, color: "#000000",
    coords: [[77.2, 28.6], [77.20565, 28.6]] },
  { start_frac: 0.5, end_frac: 1, dose_ug: 90, avg_conc_ugm3: 280, color: "#ffffff",
    coords: [[77.20565, 28.6], [77.2113, 28.6]] },
];
const fcSegs = featureFor(mkOption({ geometry: geom, segments: segs }));
ok(fcSegs.features.length === 2, "segments path: one feature per Seg");
ok(fcSegs.features[0].properties?.src === "segments", "segments path: src=segments");
// NOTE: Seg.color is server-side legacy scale — we re-tint on the CPCB
// ramp so map colours agree with every other surface.
ok(fcSegs.features[0].properties?.color === SAT, "seg avg 45 → satisfactory");
ok(fcSegs.features[1].properties?.color === SEVERE, "seg avg 280 → severe");
ok(
  (fcSegs.features[0].geometry as GeoJSON.LineString).coordinates.length === 2,
  "seg coords carried verbatim",
);

/* v2/plan wire: {geometry, pm25, band, start_frac, end_frac, dist_m} —
   geometry wins over the option's own path, the served band name beats
   re-binning, and a null pm25 is honest (quiet + no band colour). */
const v2segs: Seg[] = [
  { start_frac: 0, end_frac: 0.34, dose_ug: null, avg_conc_ugm3: null, color: "",
    coords: [], dist_m: 400,
    geometry: { type: "LineString", coordinates: [[77.2, 28.6], [77.204, 28.6]] },
    pm25: 75, band: "Moderate" },
  { start_frac: 0.34, end_frac: 0.67, dose_ug: null, avg_conc_ugm3: null, color: "",
    coords: [], dist_m: 400,
    geometry: { type: "LineString", coordinates: [[77.204, 28.6], [77.208, 28.6]] },
    pm25: null, band: "No data" },
  { start_frac: 0.67, end_frac: 1, dose_ug: null, avg_conc_ugm3: null, color: "",
    coords: [], dist_m: 400,
    geometry: { type: "LineString", coordinates: [[77.208, 28.6], [77.2113, 28.6]] },
    pm25: 260, band: "Severe" },
];
const fcV2 = featureFor(mkOption({ geometry: geom, segments: v2segs }));
ok(fcV2.features.length === 3, "v2 segments: one feature per span");
ok(fcV2.features.every((f) => f.properties?.src === "segments"), "v2 segs src=segments");
ok(fcV2.features[0].properties?.pm25 === 75, "v2 seg pm25 carried");
ok(fcV2.features[0].properties?.color === MOD, "v2 seg band 'Moderate' → band2");
ok(fcV2.features[0].properties?.band === "Moderate", "v2 seg band name on feature");
ok(
  (fcV2.features[0].geometry as GeoJSON.LineString).coordinates[0][0] === 77.2,
  "v2 seg geometry carried verbatim",
);
ok(fcV2.features[1].properties?.pm25 === null, "v2 null read stays null");
// no served band + null pm25 → quiet; 'No data' isn't a CPCB colour
ok(fcV2.features[1].properties?.color === MAP_QUIET, "v2 null read → quiet grey");
ok(fcV2.features[2].properties?.color === SEVERE, "v2 seg 260 'Severe' → band5");

/* ── fallback path: dose.avg_conc_ugm3 flat tint ──────────────────────── */
const fcAvg = featureFor(
  mkOption({ geometry: geom, dose: { lo: null, mid: null, hi: null, avg_conc_ugm3: 200 } }),
);
ok(fcAvg.features.length === chunks.length, "avg path: still chunked");
ok(
  fcAvg.features.every(
    (f) => f.properties?.pm25 === 200 && f.properties?.color === VPOOR && f.properties?.src === "avg",
  ),
  "avg path: flat 200 → very poor everywhere, src=avg",
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
  byIdx.selected.features.every((f) => f.properties?.color === SEVERE),
  "selected option tinted by its own avg (300 → severe)",
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

/* ── the chooser: candidatesFor / chooserVerdict / pointAtFrac ─────────── */
const optNoGeom = mkOption({ route_id: "rid-t", geometry: null }); // transit row
const optC = mkOption({ geometry: geom, route_id: "rid-c" });
{
  const cols = collectionsFor([optA, optNoGeom, optC, optB], 3);
  /* candidates = ≤3 drawable rows, selected LAST — rid-t (no geometry)
     never enters the stage */
  const cands = candidatesFor([optA, optNoGeom, optC, optB], 3, cols.perOption);
  ok(cands.length === 3, "chooser caps at three candidates");
  ok(cands[cands.length - 1] === 3, "selected draws last");
  ok(!cands.includes(1), "geometry-less option is never a candidate");
  ok(
    candidatesFor([optA, optB], 0, collectionsFor([optA, optB], 0).perOption)
      .join(",") === "1,0",
    "two options → both candidates, winner last",
  );
  ok(
    candidatesFor([optA], 0, collectionsFor([optA], 0).perOption).length === 1,
    "a lone option draws alone — honest fewer candidates",
  );
}

/* chooserVerdict — every claim re-derived from the served numbers */
const doseOf = (mid: number | null) => ({ lo: null, mid, hi: null, avg_conc_ugm3: null });
{
  /* least dose + fastest → the double win */
  const v1 = chooserVerdict([
    mkOption({ dose: doseOf(5), eta_s: 500 }),
    mkOption({ dose: doseOf(9), eta_s: 900 }),
  ], 0);
  ok(v1?.kind === "best", "least dose AND fastest → 'best'");

  /* least dose but a faster option exists that breathes 40% more →
     'cleanestVsFastest' with the real percentage */
  const v2 = chooserVerdict([
    mkOption({ dose: doseOf(6), eta_s: 900 }),
    mkOption({ dose: doseOf(10), eta_s: 500 }),
  ], 0);
  ok(
    v2?.kind === "cleanestVsFastest" && v2.pct === 40,
    `cleanest vs fastest carried the real gap (40), got ${JSON.stringify(v2)}`,
  );

  /* least dose, no meaningful faster contrast → plain cleanest; the
     flag beats dose-min ordering (mirrors the sheet's isSafest) */
  const v3 = chooserVerdict([
    mkOption({ dose: doseOf(6), eta_s: 900, safest_path: true }),
    mkOption({ dose: doseOf(6.02), eta_s: 500 }),
  ], 0);
  ok(v3?.kind === "cleanest", "safest_path flag → cleanest");

  /* a user's pick that's the fastest but NOT the cleanest → fastest */
  const v4 = chooserVerdict([
    mkOption({ dose: doseOf(6), eta_s: 900 }),
    mkOption({ dose: doseOf(10), eta_s: 500 }),
  ], 1);
  ok(v4?.kind === "fastest", "fastest non-cleanest pick → 'fastest'");

  /* a pick that's neither → the server's own reason_line, or null
     when there's nothing honest to say */
  const v5 = chooserVerdict([
    mkOption({ dose: doseOf(6), eta_s: 900 }),
    mkOption({ dose: doseOf(10), eta_s: 500 }),
    mkOption({ dose: doseOf(8), eta_s: 800, reason_line: "a reason" }),
  ], 2);
  ok(v5?.kind === "reason" && v5.text === "a reason", "middle pick → server reason_line");
  const v6 = chooserVerdict([
    mkOption({ dose: doseOf(6), eta_s: 900 }),
    mkOption({ dose: doseOf(10), eta_s: 500 }),
    mkOption({ dose: doseOf(8), eta_s: 800 }),
  ], 2);
  ok(v6 === null, "no numbers, no reason → the pill stays silent");
}

/* pointAtFrac — the pill anchor sits ON the route at its frac point */
{
  const mid = pointAtFrac(geom, 0.5)!;
  ok(
    Math.abs(mid[0] - 77.20565) < 0.0005 && Math.abs(mid[1] - 28.6) < 1e-6,
    `midpoint anchor on the line, got ${mid}`,
  );
  ok(pointAtFrac(null) === null, "no geometry → no anchor");
  ok(
    pointAtFrac({ type: "LineString", coordinates: [[77.2, 28.6]] })?.[0] === 77.2,
    "single-point geometry anchors on itself",
  );
}

/* navCollectionsFor — the live-travel split: chunks fully behind the
   odometer dim into `behind`, everything else keeps its band colour in
   `ahead`; the straddling chunk stays ahead so the re-tint edge lands
   at the position dot. */
{
  const nav = navCollectionsFor(geom, samples, 0);
  ok(nav.behind.features.length === 0, "odometer 0 → nothing travelled");
  ok(nav.ahead.features.length === nav.behind.features.length + nav.ahead.features.length,
    "ahead holds the whole line at odometer 0");
  const moved = navCollectionsFor(geom, samples, 300);
  ok(moved.behind.features.length === 1, "300 m in → one full 250 m chunk travelled");
  ok(
    moved.behind.features[0].properties?.seg === 0,
    "the travelled chunk is the first span",
  );
  ok(
    moved.ahead.features.length === nav.ahead.features.length - 1,
    "ahead lost exactly the travelled chunk",
  );
  const all = navCollectionsFor(geom, samples, 1e9);
  ok(all.ahead.features.length === 0, "past the end → nothing ahead");
  const none = navCollectionsFor(null, samples, 100);
  ok(none.ahead.features.length === 0 && none.behind.features.length === 0,
    "no geometry → empty, never a crash");
}

console.log(`routeTint self-test OK — ${checks} assertions`);
