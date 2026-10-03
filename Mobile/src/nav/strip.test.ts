/// <reference types="node" />
/**
 * Strip interpolation tests — stripCumM + fieldAtAlongM (doc 04 §5).
 * Run: cd Mobile && node src/nav/test-runner.mjs
 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { fieldAtAlongM, stripCumM, type StripSample } from "./strip";

const S = (
  dist_m: number,
  pm25: number | null,
  lo: number | null,
  hi: number | null,
): StripSample => ({ lat: 28.6, lon: 77.2, dist_m, pm25, lo, hi });

const closeTo = (actual: number | null, expected: number, eps = 1e-9) => {
  assert.ok(
    actual !== null && Math.abs(actual - expected) <= eps,
    `expected ${expected}, got ${actual}`,
  );
};

describe("stripCumM", () => {
  it("returns [] for no samples", () => {
    assert.deepEqual(stripCumM([]), []);
  });

  it("accumulates chunk lengths (dist_m is per-chunk, not an odometer)", () => {
    const cum = stripCumM([S(250, 1, 1, 1), S(250, 1, 1, 1), S(300, 1, 1, 1)]);
    assert.deepEqual(cum, [250, 500, 800]);
  });

  it("clamps negative and missing dist_m to 0", () => {
    const cum = stripCumM([
      S(-50, 1, 1, 1),
      { lat: 0, lon: 0, dist_m: undefined as unknown as number, pm25: 1, lo: 1, hi: 1 },
      S(100, 1, 1, 1),
    ]);
    assert.deepEqual(cum, [0, 0, 100]);
  });
});

describe("fieldAtAlongM", () => {
  // samples at along 250 m and 500 m
  const samples = [S(250, 100, 80, 120), S(250, 200, 160, 240)];
  const cum = stripCumM(samples); // [250, 500]

  it("returns nulls for an empty strip", () => {
    assert.deepEqual(fieldAtAlongM([], [], 100), { lo: null, mid: null, hi: null });
  });

  it("clamps to the first sample at/below the first knot (incl. d<0)", () => {
    for (const d of [-50, 0, 100, 250]) {
      const f = fieldAtAlongM(samples, cum, d);
      assert.equal(f.mid, 100, `d=${d}`);
      assert.equal(f.lo, 80, `d=${d}`);
      assert.equal(f.hi, 120, `d=${d}`);
    }
  });

  it("clamps to the last sample at/above the last knot (incl. d>length)", () => {
    for (const d of [500, 501, 10000]) {
      const f = fieldAtAlongM(samples, cum, d);
      assert.equal(f.mid, 200, `d=${d}`);
      assert.equal(f.lo, 160, `d=${d}`);
      assert.equal(f.hi, 240, `d=${d}`);
    }
  });

  it("linearly interpolates at the midpoint (t=0.5)", () => {
    const f = fieldAtAlongM(samples, cum, 375);
    closeTo(f.mid, 150);
    closeTo(f.lo, 120);
    closeTo(f.hi, 180);
  });

  it("linearly interpolates at t=0.25", () => {
    const f = fieldAtAlongM(samples, cum, 312.5);
    closeTo(f.mid, 125);
    closeTo(f.lo, 100);
    closeTo(f.hi, 150);
  });

  it("returns the knot sample exactly at an interior knot (t=0)", () => {
    const s3 = [S(250, 100, 80, 120), S(250, 200, 160, 240), S(250, 300, 240, 360)];
    const c3 = stripCumM(s3); // [250, 500, 750]
    const f = fieldAtAlongM(s3, c3, 500);
    assert.equal(f.mid, 200);
    assert.equal(f.lo, 160);
    assert.equal(f.hi, 240);
  });

  it("single-sample strip returns that sample for any distance", () => {
    const one = [S(250, 42, 40, 50)];
    const c1 = stripCumM(one);
    for (const d of [-10, 0, 100, 250, 99999]) {
      const f = fieldAtAlongM(one, c1, d);
      assert.equal(f.mid, 42, `d=${d}`);
      assert.equal(f.lo, 40, `d=${d}`);
      assert.equal(f.hi, 50, `d=${d}`);
    }
  });

  it("propagates null per band edge — never invents a value", () => {
    const s = [S(250, 100, null, 120), S(250, 200, 160, null)];
    const c = stripCumM(s);
    const f = fieldAtAlongM(s, c, 375);
    assert.equal(f.lo, null, "lo edge: null in one bracketing sample");
    closeTo(f.mid, 150);
    assert.equal(f.hi, null, "hi edge: null in the other sample");
  });

  it("handles unevenly spaced samples", () => {
    const s = [S(100, 10, 10, 10), S(400, 110, 110, 110)]; // knots at 100 and 500
    const c = stripCumM(s);
    const f = fieldAtAlongM(s, c, 300); // t = 0.5 of the 400 m span
    closeTo(f.mid, 60);
  });
});
