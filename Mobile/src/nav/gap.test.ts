/// <reference types="node" />
/**
 * Fix-gap honesty tests (lane nav-gap-fix).
 *
 * Replays the lifecycle lane's catalogued bug through the same call
 * shape the engine uses: fixes feed the odometer via jumpCreditM, the
 * 1 Hz ticker classifies each tick via classifyGap and hands the flag
 * to LiveCounters.tick. During a gap, dose integrates at the rest-VE
 * floor and emissions pause — the air kept hitting, the ride didn't.
 *
 * Run: cd Mobile && node src/nav/test-runner.mjs
 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { classifyGap, FIX_GAP_S, jumpCreditM } from "./gap";
import { LiveCounters, ME_VE, REST_VE_LPM } from "./counters";
import type { EmissionCurve } from "./strip";

const CONC = { lo: 50, mid: 100, hi: 150 };
const CAR: EmissionCurve = {
  mode: "car",
  co2_g_km: { lo: 100, hi: 200 },
  pm25_g_km: null,
  idle_g_s: 0.4,
  occupancy: 1.4,
  cold_start_km: 3,
};

/* the engine's tick loop, minus React: fixAge is seconds since the
   freshest fix (null before the first), pendM is credited advance. */
const engineTick = (
  c: LiveCounters,
  realDt: number,
  v: number,
  pendM: number,
  fixAgeS: number | null,
  curve: EmissionCurve | null = CAR,
  mode = "car",
) => {
  const gap = classifyGap(realDt, fixAgeS);
  c.tick(realDt, v, pendM, CONC, curve, mode, gap);
  return gap;
};

describe("classifyGap — when did the stream go blind?", () => {
  it("young fixes + 1 s ticks: no gap (real stop-and-go included)", () => {
    assert.equal(classifyGap(1, 0.4), false);
    assert.equal(classifyGap(1, FIX_GAP_S), false); // edge: stops exactly at the floor
  });
  it("a suspended ticker's catch-up dt is a gap", () => {
    assert.equal(classifyGap(276, 3), true); // the lifecycle bug: 4.6 min in one tick
  });
  it("a running ticker with dead fixes is a gap (parked, screen on)", () => {
    assert.equal(classifyGap(1, FIX_GAP_S + 0.5), true);
  });
  it("no fix ever landed = blind from the start", () => {
    assert.equal(classifyGap(1, null), true);
  });
});

describe("jumpCreditM — only physically-possible distance", () => {
  it("normal 1 s fixes credit their full advance", () => {
    assert.equal(jumpCreditM(9, 1), 9);
  });
  it("a resume-fix after long dead time credits real riding", () => {
    // 2 km leg, fixes dead for 300 s — cap is 45×300 = 13.5 km, whole leg stands
    assert.equal(jumpCreditM(2000, 300), 2000);
  });
  it("a teleport drops the impossible part", () => {
    // 2 km in ~1 s — physics allows ~45 m
    assert.equal(jumpCreditM(2000, 1), 45);
  });
});

describe("the lifecycle bug replayed — parked 5 min mid-ride", () => {
  it("dose keeps counting at rest-VE, emissions pause until fixes resume", () => {
    const c = new LiveCounters();
    // 60 s of riding at 10 m/s — each fix credited 10 m, none a gap
    for (let i = 0; i < 60; i++) {
      const g = engineTick(c, 1, 10, jumpCreditM(10, 1), 0.6);
      assert.equal(g, false);
    }
    const doseBefore = c.doseUg.mid;
    const co2Before = c.co2G.mid;
    const travelBefore = c.travelledM;

    // backgrounded 300 s: ONE catch-up tick, no fix — the old bug
    // booked this as 300 s × last speed of new driving.
    const gResume = engineTick(c, 300, 10, 0, 301);
    assert.equal(gResume, true);
    assert.equal(c.co2G.mid, co2Before); // no parked-time emissions
    assert.equal(c.travelledM, travelBefore); // no minted distance
    assert.ok(c.doseUg.mid > doseBefore); // the air kept hitting

    // ticker keeps running with the watcher still starved — every
    // second still a gap, still no emissions, still rest-dose
    const co2Hold = c.co2G.mid;
    for (let i = 0; i < 30; i++) {
      assert.equal(engineTick(c, 1, 10, 0, 302 + i), true);
    }
    assert.equal(c.co2G.mid, co2Hold);

    // fixes return — meters unpause, emissions resume per-km
    const gBack = engineTick(c, 1, 10, jumpCreditM(12, 1), 0.5);
    assert.equal(gBack, false);
    assert.ok(c.co2G.mid > co2Hold);
  });

  it("rest-dose is honest: heavy-VE modes drop to the rest floor", () => {
    const c = new LiveCounters();
    const me = ME_VE.cycle.me; // 1.1, ve 22 L/min riding
    for (let i = 0; i < 60; i++) engineTick(c, 1, 6, jumpCreditM(6, 1), 0.6, null, "cycle");
    const before = c.doseUg.mid;
    engineTick(c, 120, 6, 0, 121, null, "cycle"); // 2 min off the bike
    const got = c.doseUg.mid - before;
    const rest = 100 * me * (REST_VE_LPM / 60000) * 120;
    const ridingWouldBe = 100 * me * (ME_VE.cycle.veLpm / 60000) * 120;
    assert.ok(Math.abs(got - rest) < 1e-9, `rest dose ${rest}, got ${got}`);
    assert.ok(got < ridingWouldBe / 2);
  });

  it("stop-and-go traffic still counts — only fix-gaps pause", () => {
    const c = new LiveCounters();
    // 120 s idling at a light: fixes flowing (age < 1 s), v ≈ 0
    for (let i = 0; i < 120; i++) {
      assert.equal(engineTick(c, 1, 0.1, jumpCreditM(0.1, 1), 0.4), false);
    }
    const me = ME_VE.car.me, ve = ME_VE.car.veLpm / 60000;
    assert.ok(Math.abs(c.doseUg.mid - 100 * me * ve * 120) < 1e-9);
    assert.ok(c.co2G.mid > 0); // idle-rate emissions accrue — real route exposure
  });
});
