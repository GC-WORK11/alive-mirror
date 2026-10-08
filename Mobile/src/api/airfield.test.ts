/** sampleFieldAt — the air map's tap-to-read sampler. The readout must
 *  answer from the painted cells themselves (tap and tint can never
 *  disagree), stay honest where no cell reaches (a dropped-cell hole or
 *  past the grid edge → null, the caller falls back to /aqi or says
 *  "outside"), and never invent a value off a neighbouring cell.
 *
 *  Cells mirror server/grid.py's as_geojson: axis-aligned Polygon
 *  rectangles with properties {pm25, conf}; cells whose field read is
 *  None are dropped (holes in the collection).
 *
 *  Run: `node src/api/test-runner.mjs`
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { sampleFieldAt, airFieldAgeS } from "./airfield";

test("map age follows its painted grid epoch, not a newer home or plan read", () => {
  const now = Date.UTC(2026, 9, 8, 10);
  const grid = { type: "FeatureCollection", features: [],
    properties: { cell_epoch: [now / 1000 - 960, 0] } } as GeoJSON.FeatureCollection;
  assert.equal(airFieldAgeS(grid, now), 960);
  assert.equal(airFieldAgeS(grid, now + 60000), 1020);
  assert.equal(airFieldAgeS(null, now), null);
  assert.equal(airFieldAgeS({ type: "FeatureCollection", features: [] }, now), null);
});

/* a two-cell strip: [10,0]–[20,10] and [20,0]–[30,10] — the second
   deliberately hole-less for the edge case; the "hole" region is just
   the absence of a cell */
const cell = (x0: number, y0: number, x1: number, y1: number, pm25: number, conf = "hi") => ({
  type: "Feature" as const,
  geometry: { type: "Polygon" as const,
    coordinates: [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]] },
  properties: { pm25, conf },
});

const FC: GeoJSON.FeatureCollection = {
  type: "FeatureCollection",
  features: [cell(10, 0, 20, 10, 42), cell(20, 0, 30, 10, 96.4, "lo")],
};

test("a point inside a cell reads that cell's served value", () => {
  assert.deepEqual(sampleFieldAt(FC, 5, 15), { pm25: 42, conf: "hi" });
  assert.deepEqual(sampleFieldAt(FC, 9.9, 29.7), { pm25: 96.4, conf: "lo" });
});

test("a shared edge reads a real neighbour — never interpolated", () => {
  const s = sampleFieldAt(FC, 5, 20);
  assert.ok(s && (s.pm25 === 42 || s.pm25 === 96.4));
});

test("a hole and the outside are honest absence — no nearest guess", () => {
  assert.equal(sampleFieldAt(FC, 5, 35), null);          // no third cell
  assert.equal(sampleFieldAt(FC, 5, 5), null);          // south of the strip
  assert.equal(sampleFieldAt(null, 5, 15), null);
  assert.equal(sampleFieldAt({ type: "FeatureCollection", features: [] }, 5, 15), null);
  assert.equal(sampleFieldAt(FC, NaN, 15), null);
});

test("degenerate features are skipped, not crashed on", () => {
  const odd: GeoJSON.FeatureCollection = {
    type: "FeatureCollection",
    features: [
      { type: "Feature", geometry: { type: "Point", coordinates: [15, 5] },
        properties: { pm25: 1 } },
      { type: "Feature", geometry: { type: "Polygon", coordinates: [[]] },
        properties: { pm25: 2 } },
      { type: "Feature", geometry: { type: "Polygon",
          coordinates: [[[10, 0], [20, 0], [20, 10], [10, 10], [10, 0]]] },
        properties: {} },                    // no pm25 → not an answer
      cell(10, 0, 20, 10, 77, "med"),
    ],
  };
  assert.deepEqual(sampleFieldAt(odd, 5, 15), { pm25: 77, conf: "med" });
});
