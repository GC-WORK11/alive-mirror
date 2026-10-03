/// <reference types="node" />
/**
 * Off-route detection, arrival tracking, polyline snapping + haversine
 * (doc 04 §4). Run: cd Mobile && node src/nav/test-runner.mjs
 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  ARRIVE_FIXES,
  ARRIVE_M,
  ArrivalTracker,
  flattenCoords,
  havM,
  OFF_ROUTE_FIXES,
  OFF_ROUTE_M,
  OffRouteTracker,
  polylineLengthM,
  snapToPolyline,
  type LonLat,
} from "./offroute";

const closeTo = (actual: number, expected: number, eps = 1e-6) => {
  assert.ok(
    Math.abs(actual - expected) <= eps,
    `expected ${expected} ±${eps}, got ${actual}`,
  );
};

describe("havM", () => {
  it("is 0 for identical points", () => {
    assert.equal(havM(28.6, 77.2, 28.6, 77.2), 0);
  });

  it("matches the spherical one-degree latitude arc", () => {
    // 2 · 6371000 · π/360 ≈ 111 194.9 m
    closeTo(havM(0, 0, 1, 0), (2 * 6371000 * Math.PI) / 360, 1e-3);
  });

  it("is symmetric and roughly linear for small Delhi distances", () => {
    const d = havM(28.6139, 77.209, 28.6189, 77.209); // ~556 m north
    assert.ok(d > 540 && d < 570, `got ${d}`);
    closeTo(d, havM(28.6189, 77.209, 28.6139, 77.209), 1e-9);
  });
});

describe("flattenCoords / polylineLengthM", () => {
  it("flattens LineString and MultiLineString, rejects the rest", () => {
    assert.deepEqual(flattenCoords(null), []);
    assert.deepEqual(flattenCoords({ type: "Point", coordinates: [77, 28] }), []);
    assert.deepEqual(
      flattenCoords({ type: "LineString", coordinates: [[77, 28], [77.1, 28.1]] }),
      [[77, 28], [77.1, 28.1]],
    );
    // documented flat concat: the shared leg vertex is duplicated
    // (zero-length segment at the join — see offroute.ts:30)
    assert.deepEqual(
      flattenCoords({
        type: "MultiLineString",
        coordinates: [[[77, 28], [77.1, 28]], [[77.1, 28], [77.1, 28.1]]],
      }),
      [[77, 28], [77.1, 28], [77.1, 28], [77.1, 28.1]],
    );
  });

  it("sums per-segment haversine lengths", () => {
    const coords: LonLat[] = [[77, 28], [77, 28.001], [77, 28.002]];
    closeTo(polylineLengthM(coords), 2 * havM(28, 77, 28.001, 77), 1e-9);
    assert.equal(polylineLengthM([]), 0);
    assert.equal(polylineLengthM([[77, 28]]), 0);
  });
});

describe("snapToPolyline", () => {
  // Due-north route: 1.1054 km, lon 77.0, lat 28.0 → 28.01
  const line: LonLat[] = [[77.0, 28.0], [77.0, 28.01]];
  const segLen = 0.01 * 110540; // equirect segment length the snapper uses

  it("projects a point onto the segment middle", () => {
    const s = snapToPolyline(line, 28.005, 77.001);
    assert.ok(s);
    closeTo(s.alongM, segLen / 2, 1.5);
    closeTo(s.offsetM, 0.001 * 111320 * Math.cos((28.005 * Math.PI) / 180), 1.5);
    closeTo(s.lat, 28.005, 1e-4);
    closeTo(s.lon, 77.0, 1e-9);
    closeTo(s.headingDeg, 0, 1e-6); // due north
    assert.equal(s.segIdx, 0);
    closeTo(s.segT, 0.5, 1e-3);
  });

  it("clamps t to segment ends beyond the termini", () => {
    const before = snapToPolyline(line, 27.999, 77.0);
    assert.ok(before);
    assert.equal(before.alongM, 0);
    closeTo(before.offsetM, 0.001 * 110540, 1);

    const after = snapToPolyline(line, 28.02, 77.0);
    assert.ok(after);
    closeTo(after.alongM, segLen, 1e-6);
    closeTo(after.offsetM, 0.01 * 110540, 1);
  });

  it("picks the nearest segment on a multi-leg route", () => {
    // L shape: east 1 km then north 1 km
    const l: LonLat[] = [[77.0, 28.0], [77.01, 28.0], [77.01, 28.01]];
    const s = snapToPolyline(l, 28.005, 77.011); // just east of leg 2
    assert.ok(s);
    assert.equal(s.segIdx, 1);
    assert.ok(s.offsetM < 120, `offset ${s.offsetM}`);
    assert.ok(s.alongM > 0.01 * 110540, `along ${s.alongM}`);
  });

  it("returns null for fewer than 2 coords", () => {
    assert.equal(snapToPolyline([], 28, 77), null);
    assert.equal(snapToPolyline([[77, 28]], 28, 77), null);
  });
});

describe("OffRouteTracker (>40 m × 3 consecutive fixes)", () => {
  it(`spec constants are ${OFF_ROUTE_M} m / ${OFF_ROUTE_FIXES} fixes`, () => {
    assert.equal(OFF_ROUTE_M, 40);
    assert.equal(OFF_ROUTE_FIXES, 3);
  });

  it("two consecutive off-route fixes do NOT trigger", () => {
    const t = new OffRouteTracker();
    assert.equal(t.update(50), false);
    assert.equal(t.update(60), false);
    assert.ok(t.counting);
  });

  it("the third consecutive fix triggers — and every fix after that", () => {
    const t = new OffRouteTracker();
    t.update(50);
    t.update(50);
    assert.equal(t.update(50), true);
    // engine throttles re-emission with REROUTE_COOLDOWN_MS; tracker
    // keeps reporting true so a failed reroute can retry after cooldown
    assert.equal(t.update(50), true);
  });

  it("exactly 40 m is NOT off-route (strict >)", () => {
    const t = new OffRouteTracker();
    assert.equal(t.update(40), false);
    assert.equal(t.update(40), false);
    assert.equal(t.update(40), false);
    assert.equal(t.counting, false);
    assert.equal(t.update(40.0001), false); // count 1
    assert.equal(t.update(40.0001), false); // count 2
    assert.equal(t.update(40.0001), true);  // count 3
  });

  it("a single re-acquired fix resets the streak", () => {
    const t = new OffRouteTracker();
    t.update(80);
    t.update(80);
    assert.equal(t.update(5), false); // back on route
    assert.equal(t.counting, false);
    assert.equal(t.update(80), false);
    assert.equal(t.update(80), false);
    assert.equal(t.update(80), true); // fresh streak of 3
  });

  it("reset() clears the count", () => {
    const t = new OffRouteTracker();
    t.update(100);
    t.update(100);
    t.reset();
    assert.equal(t.counting, false);
    assert.equal(t.update(100), false);
  });
});

describe(`ArrivalTracker (≤${ARRIVE_M} m × ${ARRIVE_FIXES} fixes)`, () => {
  it("spec constants are 60 m / 2 fixes", () => {
    assert.equal(ARRIVE_M, 60);
    assert.equal(ARRIVE_FIXES, 2);
  });

  it("fires on the second consecutive in-radius fix", () => {
    const t = new ArrivalTracker();
    assert.equal(t.update(59), false);
    assert.equal(t.update(59), true);
  });

  it("boundary 60 m counts; 60.1 m does not", () => {
    const t = new ArrivalTracker();
    assert.equal(t.update(60), false);
    assert.equal(t.update(60), true);

    const u = new ArrivalTracker();
    u.update(60.1);
    u.update(60.1);
    u.update(60.1);
    assert.equal(u.update(60), false); // count restarted
    assert.equal(u.update(60), true);
  });

  it("keeps returning true each in-radius fix — the engine dedupes", () => {
    // NOTE: tracker-level contract is "true while streak ≥ 2"; the
    // engine's arrivedRef guard (engine.ts:184) is what makes the
    // arrival STATE fire exactly once. That guard lives inside the
    // React hook and is not reachable from a node test.
    const t = new ArrivalTracker();
    t.update(10);
    assert.equal(t.update(10), true);
    assert.equal(t.update(10), true);
  });

  it("leaving the radius and reset() both restart the streak", () => {
    const t = new ArrivalTracker();
    t.update(30);
    assert.equal(t.update(500), false);
    assert.equal(t.update(30), false);
    t.reset();
    assert.equal(t.update(30), false);
    assert.equal(t.update(30), true);
  });
});
