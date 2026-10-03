/// <reference types="node" />
/**
 * LiveCounters 1 Hz integration tests (doc 04 §5, doc 06 §1–2):
 *
 *   dose_ug += C(alongM) · ME(mode) · VE(mode)[m³/s] · dt
 *   rate    = max(idle_g_s | idle·0.004, ef_g_km·v/1000) · coldFactor
 *   out_g  += rate · dt / occupancy          (per vehicle-km modes)
 *   out_g  += ef_g_pkm · ddKm                (shared modes only)
 *
 * Run: cd Mobile && node src/nav/test-runner.mjs
 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  COLD_UPLIFT,
  LiveCounters,
  ME_VE,
  PM_IDLE_SHARE,
} from "./counters";
import type { EmissionCurve } from "./strip";

const closeTo = (actual: number, expected: number, eps = 1e-9) => {
  assert.ok(
    Math.abs(actual - expected) <= eps,
    `expected ${expected} ±${eps}, got ${actual}`,
  );
};

const CONC = { lo: 50, mid: 100, hi: 150 };

describe("dose integration (inhaled PM2.5, µg)", () => {
  it("walk: C·ME·VE·dt per band edge, accumulates over ticks", () => {
    const c = new LiveCounters();
    const veM3s = ME_VE.walk.veLpm / 60000; // 14 L/min → 2.3333e-4 m³/s
    for (let i = 0; i < 60; i++) c.tick(1, 1.4, 0, CONC, null, "walk");
    closeTo(c.doseUg.lo, 50 * 1.0 * veM3s * 60);   // 0.7
    closeTo(c.doseUg.mid, 100 * 1.0 * veM3s * 60);  // 1.4
    closeTo(c.doseUg.hi, 150 * 1.0 * veM3s * 60);   // 2.1
  });

  it("mode changes the ME·VE product (metro breathes less roadside air)", () => {
    const a = new LiveCounters();
    a.tick(1, 5, 0, CONC, null, "metro"); // me 0.45, ve 7.5
    const b = new LiveCounters();
    b.tick(1, 5, 0, CONC, null, "cycle"); // me 1.1, ve 22
    closeTo(a.doseUg.mid, 100 * 0.45 * (7.5 / 60000));
    closeTo(b.doseUg.mid, 100 * 1.1 * (22 / 60000));
    assert.ok(b.doseUg.mid > a.doseUg.mid);
  });

  it("unknown modes fall back to the ambient default (me=1, ve=8)", () => {
    const c = new LiveCounters();
    c.tick(1, 1, 0, CONC, null, "jetpack");
    closeTo(c.doseUg.mid, 100 * 1.0 * (8 / 60000));
  });

  it("dt is measured, not assumed: half-second tick halves the dose", () => {
    const a = new LiveCounters();
    a.tick(0.5, 1, 0, CONC, null, "walk");
    const b = new LiveCounters();
    b.tick(1, 1, 0, CONC, null, "walk");
    closeTo(a.doseUg.mid, b.doseUg.mid / 2);
  });

  it("dt ≤ 0 is a no-op", () => {
    const c = new LiveCounters();
    c.tick(0, 1, 10, CONC, { mode: "car", co2_g_km: { lo: 1, hi: 1 } }, "walk");
    c.tick(-3, 1, 10, CONC, null, "walk");
    assert.equal(c.doseUg.mid, 0);
    assert.equal(c.co2G.lo, 0);
    assert.equal(c.travelledM, 0);
  });

  it("all-null concentration accrues nothing — honest zero", () => {
    const c = new LiveCounters();
    c.tick(1, 1, 0, { lo: null, mid: null, hi: null }, null, "walk");
    assert.equal(c.doseUg.lo, 0);
    assert.equal(c.doseUg.mid, 0);
    assert.equal(c.doseUg.hi, 0);
  });

  it("null edges borrow the nearest available edge (cMid fallback)", () => {
    const c = new LiveCounters();
    // mid+hi null → every edge falls back to lo=100
    c.tick(1, 1, 0, { lo: 100, mid: null, hi: null }, null, "walk");
    const expected = 100 * 1.0 * (14 / 60000);
    closeTo(c.doseUg.lo, expected);
    closeTo(c.doseUg.mid, expected);
    closeTo(c.doseUg.hi, expected);

    const d = new LiveCounters();
    // only hi present → cMid = hi
    d.tick(1, 1, 0, { lo: null, mid: null, hi: 200 }, null, "walk");
    const exp2 = 200 * 1.0 * (14 / 60000);
    closeTo(d.doseUg.lo, exp2);
    closeTo(d.doseUg.mid, exp2);
    closeTo(d.doseUg.hi, exp2);
  });
});

describe("vehicle emissions (co2_g_km / pm25_g_km curve)", () => {
  const CAR: EmissionCurve = {
    mode: "car",
    co2_g_km: { lo: 100, hi: 200 },
    pm25_g_km: { lo: 5, hi: 10 },
    idle_g_s: 0,
    occupancy: 1,
    cold_start_km: 0,
  };

  it("rate = ef·v/1000 while moving; scripted 10 s at 10 m/s", () => {
    const c = new LiveCounters();
    for (let i = 0; i < 10; i++) c.tick(1, 10, 10, CONC, CAR, "car");
    // co2 lo: 100 g/km · 10 m/s / 1000 = 1 g/s → 10 g
    closeTo(c.co2G.lo, 10);
    closeTo(c.co2G.hi, 20);
    closeTo(c.co2G.mid, 15); // mid = (lo+hi)/2
    // pm lo: 5·10/1000 = 0.05 g/s → 0.5 g
    closeTo(c.pm25G.lo, 0.5);
    closeTo(c.pm25G.hi, 1.0);
    closeTo(c.pm25G.mid, 0.75);
    closeTo(c.travelledM, 100);
  });

  it("idle floor: standing still still emits idle_g_s", () => {
    const c = new LiveCounters();
    const curve: EmissionCurve = { ...CAR, idle_g_s: 2 };
    c.tick(1, 0, 0, CONC, curve, "car");
    closeTo(c.co2G.lo, 2);   // max(2, 0) · 1 s
    closeTo(c.co2G.hi, 2);
    // PM idle = idle · PM_IDLE_SHARE, NOT the ef·v term
    closeTo(c.pm25G.lo, 2 * PM_IDLE_SHARE);
    closeTo(c.pm25G.hi, 2 * PM_IDLE_SHARE);
  });

  it("idle floor loses once ef·v/1000 exceeds it", () => {
    const c = new LiveCounters();
    const curve: EmissionCurve = { ...CAR, idle_g_s: 0.5 };
    c.tick(1, 10, 10, CONC, curve, "car");
    closeTo(c.co2G.lo, 1); // max(0.5, 1.0) → driving term wins
  });

  it("occupancy divides the emission rate", () => {
    const c = new LiveCounters();
    c.tick(1, 10, 10, CONC, { ...CAR, occupancy: 4 }, "bus");
    closeTo(c.co2G.lo, 1 / 4);
    c.tick(1, 10, 10, CONC, { ...CAR, occupancy: 0 }, "bus"); // 0 → treated 1
    closeTo(c.co2G.lo, 1 / 4 + 1);
  });

  it("cold-start uplift tapers linearly over cold_start_km", () => {
    const c = new LiveCounters();
    const curve: EmissionCurve = {
      mode: "car",
      co2_g_km: { lo: 100, hi: 100 },
      idle_g_s: 0,
      occupancy: 1,
      cold_start_km: 4,
    };
    // Scripted trajectory: 4 × 1 km legs, each a 1 s tick at 10 m/s.
    // km is measured AFTER the leg lands (travelledM += ddM first).
    for (let i = 0; i < 4; i++) c.tick(1, 10, 1000, CONC, curve, "car");
    const cold = (km: number) =>
      1 + COLD_UPLIFT * Math.max(0, 1 - km / 4);
    const expected =
      1 * (cold(1) + cold(2) + cold(3) + cold(4)); // rate = 1 g/s · dt 1
    closeTo(cold(1), 1 + 0.35 * 0.75);
    closeTo(expected, 4.525);
    closeTo(c.co2G.lo, expected);
    closeTo(c.co2G.mid, expected); // lo == hi band
    closeTo(c.travelledM, 4000);

    // beyond cold_start_km the factor is exactly 1
    c.tick(1, 10, 0, CONC, curve, "car");
    closeTo(c.co2G.lo, expected + 1);
  });

  it("no uplift when cold_start_km is 0/absent", () => {
    const c = new LiveCounters();
    c.tick(1, 10, 1000, CONC, CAR, "car");
    closeTo(c.co2G.lo, 1); // cold factor == 1
  });

  it("negative ddM is clamped (odometer never rewinds)", () => {
    const c = new LiveCounters();
    c.tick(1, 10, -500, CONC, CAR, "car");
    assert.equal(c.travelledM, 0);
  });
});

describe("shared-mode emissions (per passenger-km)", () => {
  it("pkm integrates by distance only — idle/cold/occupancy ignored", () => {
    const c = new LiveCounters();
    const curve: EmissionCurve = {
      mode: "metro",
      co2_g_pkm: { lo: 40, hi: 80 },
      pm25_g_pkm: { lo: 1, hi: 3 },
      // trap values: if any of these leaked in, totals would differ
      idle_g_s: 5,
      occupancy: 9,
      cold_start_km: 2,
    };
    // 2 km leg, speed 0 (standing) — distance is all that counts
    c.tick(1, 0, 2000, CONC, curve, "metro");
    closeTo(c.co2G.lo, 80);
    closeTo(c.co2G.hi, 160);
    closeTo(c.co2G.mid, 120);
    closeTo(c.pm25G.lo, 2);
    closeTo(c.pm25G.hi, 6);
    closeTo(c.pm25G.mid, 4);
    closeTo(c.travelledM, 2000);
  });

  it("pkm branch wins over a stray co2_g_km key", () => {
    const c = new LiveCounters();
    const curve: EmissionCurve = {
      mode: "metro",
      co2_g_pkm: { lo: 40, hi: 40 },
      co2_g_km: { lo: 999, hi: 999 }, // must be ignored
    };
    c.tick(1, 10, 1000, CONC, curve, "metro");
    closeTo(c.co2G.lo, 40);
  });
});

describe("accumulator behaviour", () => {
  it("no curve → dose still accrues, emissions stay 0", () => {
    const c = new LiveCounters();
    c.tick(1, 10, 1000, CONC, null, "car");
    assert.ok(c.doseUg.mid > 0);
    assert.equal(c.co2G.lo, 0);
    assert.equal(c.pm25G.lo, 0);
    // FINDING F1: travelledM also stays 0 with no curve — a strip-failure
    // trip would report distanceKm 0 on the arrival receipt even though
    // the user moved (engine.ts:193 feeds the receipt from travelledM).
    assert.equal(c.travelledM, 0);
  });

  it("reset() zeroes everything", () => {
    const c = new LiveCounters();
    c.tick(1, 10, 1000, CONC, { mode: "car", co2_g_km: { lo: 1, hi: 2 } }, "car");
    c.reset();
    assert.equal(c.doseUg.mid, 0);
    assert.equal(c.co2G.lo, 0);
    assert.equal(c.pm25G.hi, 0);
    assert.equal(c.travelledM, 0);
  });
});
