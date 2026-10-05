/// <reference types="node" />
/**
 * Ledger-math audit (docs/lanes/ledger-audit.md) — does the hero's
 * "≈N µg breathed" equal timeline × field, computed by the SAME
 * `reconstructDay` the home stack runs?
 *
 * The stay samples below are REAL field reads captured live against the
 * production field (GET /aqi at each point, 2026-10-06 ~02:45 IST,
 * field age_s≈163, kriging on, smoke_modifier 1.09):
 *   Connaught Place 28.6315,77.2167 → pm25_ambient 69.2, pm25 (bz) 75.4
 *   Saket           28.5245,77.2066 → pm25_ambient 57.5, pm25 (bz) 62.6
 *   (Karol Bagh cross-read 28.6519,77.1907 → 54.7/59.6 — report's table)
 * and the trip dose is a live POST /v2/plan CP→Saket auto mid: 17.6 µg.
 *
 * Hand recomputation: dose = ∫ conc(t) dt × 0.6 m³/h (VE_REST), conc
 * linear between the two measured sample values — a trapezoid per
 * covered pair. Run: cd Mobile && node src/store/test-runner.mjs
 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  reconstructDay,
  recordSample,
  allSamples,
  dayKey,
  type AmbientSample,
} from "./daylog";
import type { Trip } from "./ledger";

const VE_M3H = 0.6; // VE_REST_M3H — seated/resting 10 L/min

/* local-time construction keeps the fixture tz-agnostic — every boundary
   derives from the same Date getters reconstructDay uses */
const at = (h: number, m = 0) => new Date(2026, 9, 6, h, m).getTime(); // Oct 6, local
const NOW = at(12, 0);
const DAY = dayKey(NOW);
const MIN = 60 * 1000;

const samp = (ts: number, lat: number, lon: number, amb: number, bz: number | null): AmbientSample =>
  ({ ts, lat, lon, amb, bz });

/* the live reads, frozen as of capture */
const CP = { lat: 28.6315, lon: 77.2167, amb: 69.2, bz: 75.4 };
const SAKET = { lat: 28.5245, lon: 77.2066, amb: 57.5, bz: 62.6 };
const TRIP: Trip = {
  ts: at(8, 35), label: "Auto-rickshaw", vehicle: "auto",
  dose_ug: 17.6, avoided_ug: 179.2, // live /v2/plan CP→Saket auto mid vs walk worst
  from: "Connaught Place", to: "Saket",
};

const trap = (c0: number, c1: number, ms: number) =>
  ((c0 + c1) / 2) * VE_M3H * (ms / 3600000);
const close = (a: number, b: number, eps = 0.05) =>
  assert.ok(Math.abs(a - b) < eps, `${a} vs ${b}`);

describe("reconstructDay — live-field fixture", () => {
  /* stand at CP 08:00–08:25 → ride to Saket (field ramps down) →
     indoors at Saket until 09:05 + the logged auto trip at 08:35 */
  const samples = [
    samp(at(8, 0), CP.lat, CP.lon, CP.amb, CP.bz),
    samp(at(8, 25), CP.lat, CP.lon, CP.amb, CP.bz),
    samp(at(8, 40), SAKET.lat, SAKET.lon, SAKET.amb, SAKET.bz),
    samp(at(9, 5), SAKET.lat, SAKET.lon, SAKET.amb, SAKET.bz),
  ];
  /* hand math: A = 75.4×0.6×(25/60)=18.85 · B = (75.4+62.6)/2×0.6×0.25=10.35
     · C = 62.6×0.6×(25/60)=15.65 · stays 44.85 · +trip 17.6 → 62.45 */
  const rec = reconstructDay(DAY, samples, [TRIP], NOW);

  it("hero total equals hand trapezoid over the live reads", () => {
    close(rec.totalUg, 18.85 + 10.35 + 15.65 + 17.6, 0.06); // ≈62.5
    assert.equal(rec.thin, false);
  });

  it("per-hour arc sums to the hero — no dose falls between the bars", () => {
    const arcSum = rec.arc.reduce((s, h) => s + h.dose_ug, 0);
    /* stays(44.85) + trip(17.6) = 62.45 — every accumulated µg must land
       in a bar (pre-fix: left-edge sampling made the arc disagree with
       the total on every ramping pair — 63.41 vs 62.45 on this fixture) */
    close(arcSum, 62.45, 1e-6);
  });

  it("hour split: the 08:40–09:05 leg pays its first 20min into h8", () => {
    const h8 = rec.arc[8], h9 = rec.arc[9];
    /* h8 = A 18.85 + B(ramp) 10.35 + C's 08:40–09:00 62.6×0.6×(20/60)=12.52
       + trip 17.6 = 59.32 ; h9 = C's 09:00–09:05 62.6×0.6×(5/60) = 3.13 */
    close(h8.dose_ug, 18.85 + 10.35 + 12.52 + 17.6, 1e-9); // 59.32
    close(h9.dose_ug, 3.13, 1e-6);
    assert.equal(h8.trip_marks, 1);
    assert.equal(h8.covered, true);
    assert.equal(h9.covered, true);
  });

  it("per-hour conc is the time-weighted mean of the ramp, not an edge", () => {
    const h8 = rec.arc[8];
    /* (75.4×25min + ramp-mean 69.0×15min + 62.6×20min) / 60 covered min */
    close(h8.conc!, (75.4 * 25 + 69.0 * 15 + 62.6 * 20) / 60, 0.05); // 69.53
  });

  it("parts: stays labelled by clock window, trips by route, sorted desc", () => {
    const labels = rec.parts.map((p) => p.label);
    assert.deepEqual(rec.parts.map((p) => Math.round(p.ug * 100) / 100),
      [18.85, 17.6, 15.65, 10.35]);
    assert.ok(labels[1].includes("→"), "trip part carries the route names");
    assert.equal(labels[0], "08:00–08:25");
  });
});

describe("reconstructDay — honesty edges", () => {
  it("single sample: covered nowhere, thin — no invented exposure", () => {
    const rec = reconstructDay(DAY, [samp(at(8), CP.lat, CP.lon, CP.amb, CP.bz)], [], NOW);
    assert.equal(rec.totalUg, 0);
    assert.equal(rec.coveredMin, 0);
    assert.equal(rec.thin, true);
    assert.ok(rec.arc.every((h) => !h.covered || h.dose_ug === 0));
  });

  it("gap >45min is a hole, not an interpolation", () => {
    const rec = reconstructDay(DAY, [
      samp(at(8), CP.lat, CP.lon, CP.amb, CP.bz),
      samp(at(9, 0), SAKET.lat, SAKET.lon, SAKET.amb, SAKET.bz), // 60 min
      samp(at(9, 20), SAKET.lat, SAKET.lon, SAKET.amb, SAKET.bz),
    ], [], NOW);
    assert.equal(rec.coveredMin, 20); // only 09:00–09:20 is claimed
    close(rec.totalUg, trap(62.6, 62.6, 20 * MIN), 0.06); // totalUg rounds to 0.1
    assert.equal(rec.arc[8].covered, false);
    assert.equal(rec.arc[9].covered, true);
  });

  it("breathing-zone preferred, ambient fallback when bz absent", () => {
    const rec = reconstructDay(DAY, [
      samp(at(8), CP.lat, CP.lon, CP.amb, null),   // bz missing → amb 69.2
      samp(at(8, 20), CP.lat, CP.lon, CP.amb, CP.bz), // bz 75.4
    ], [], NOW);
    close(rec.totalUg, trap(69.2, 75.4, 20 * MIN), 0.06); // ≈14.46→14.5
  });

  it("a stay crossing midnight writes into both days, clipped", () => {
    const prev = new Date(at(0, 0));
    prev.setDate(prev.getDate() - 1);
    const dPrev = dayKey(prev.getTime());
    const s0 = samp(at(0, 0) - 5 * MIN, CP.lat, CP.lon, CP.amb, CP.bz); // 23:55 prev
    const s1 = samp(at(0, 5), CP.lat, CP.lon, CP.amb, CP.bz);           // 00:05
    const rPrev = reconstructDay(dPrev, [s0, s1], [], at(12, 0));
    const rCur = reconstructDay(DAY, [s0, s1], [], NOW);
    /* a past day keeps all 24 hours — the arc is bounded by the day's own
       end, not by the clock hour of `now` (pre-fix sliced at nowHour) */
    assert.equal(rPrev.arc.length, 24);
    close(rPrev.arc[23].dose_ug, trap(75.4, 75.4, 5 * MIN), 1e-9); // 75.4×0.6×5/60=3.77
    close(rCur.arc[0].dose_ug, trap(75.4, 75.4, 5 * MIN), 1e-9);
    assert.equal(rPrev.arc[0]?.dose_ug ?? 0, 0); // nothing bleeds into prev day's morning
  });

  it("a pair spanning `now` clips at now — the future is never claimed", () => {
    const s0 = samp(at(11, 50), CP.lat, CP.lon, CP.amb, CP.bz);
    const s1 = samp(at(12, 10), CP.lat, CP.lon, CP.amb, CP.bz);
    const rec = reconstructDay(DAY, [s0, s1], [], NOW); // NOW = 12:00
    close(rec.totalUg, trap(75.4, 75.4, 10 * MIN), 0.06); // 11:50–12:00 only
    assert.equal(rec.arc.length, 13); // hours 0..12 — 13+ never rendered
    assert.ok(rec.arc.every((h, i) => i <= 12));
  });

  it("trip-only day is not thin; the dose lands on its hour", () => {
    const rec = reconstructDay(DAY, [], [TRIP], NOW);
    assert.equal(rec.thin, false);
    close(rec.totalUg, 17.6, 1e-9);
    assert.equal(rec.arc[8].trip_marks, 1);
  });

  it("samples in another day never leak into this day", () => {
    const far = samp(at(8) - 48 * 3600 * 1000, CP.lat, CP.lon, CP.amb, CP.bz);
    const rec = reconstructDay(DAY, [far, samp(at(8), CP.lat, CP.lon, CP.amb, CP.bz)], [], NOW);
    assert.equal(rec.totalUg, 0); // pair gap is ~48h ≫ 45min
    assert.equal(rec.coveredMin, 0);
  });

  /* the sparse hero's progress meter (docs/lanes/hero-sparse): the count
     a fresh install can honestly show — today's own reads, toward the
     same 3-sample gate that lifts `thin` */
  it("samplesToday is the sparse meter — thin lifts at THIN_SAMPLE_MIN", () => {
    const s = (m: number) => samp(at(8, m), CP.lat, CP.lon, CP.amb, CP.bz);
    const r0 = reconstructDay(DAY, [], [], NOW);
    assert.equal(r0.samplesToday, 0);
    assert.equal(r0.thin, true);
    const r2 = reconstructDay(DAY, [s(0), s(10)], [], NOW);
    assert.equal(r2.samplesToday, 2);
    assert.equal(r2.thin, true);
    const r3 = reconstructDay(DAY, [s(0), s(10), s(20)], [], NOW);
    assert.equal(r3.samplesToday, 3);
    assert.equal(r3.thin, false);
    /* a day already over counts its own reads — yesterday's samples
       never pad today's meter */
    const prev = new Date(at(0, 0)); prev.setDate(prev.getDate() - 1);
    const sPrev = samp(prev.getTime() + 8 * 3600 * 1000, CP.lat, CP.lon, CP.amb, CP.bz);
    const rp = reconstructDay(dayKey(prev.getTime()), [sPrev], [], NOW);
    assert.equal(rp.samplesToday, 1);
    const rt = reconstructDay(DAY, [sPrev], [], NOW);
    assert.equal(rt.samplesToday, 0);
  });
});

describe("recordSample — the dedupe the file depends on", () => {
  it("drops a <8min read at a <450m spot; keeps a moved or older one", async () => {
    const t0 = at(8, 0);
    assert.equal(await recordSample(samp(t0, CP.lat, CP.lon, CP.amb, CP.bz)), true);
    // 5 min later, ~50 m away → nothing learned, file stays sparse
    assert.equal(await recordSample(samp(t0 + 5 * MIN, CP.lat + 0.0004, CP.lon, CP.amb, CP.bz)), false);
    // 5 min later but ~2 km away (moved) → kept
    assert.equal(await recordSample(samp(t0 + 10 * MIN, SAKET.lat, SAKET.lon, SAKET.amb, SAKET.bz)), true);
    // 10 min later, same place → kept (new time = new read)
    assert.equal(await recordSample(samp(t0 + 20 * MIN, SAKET.lat, SAKET.lon, SAKET.amb, SAKET.bz)), true);
    const all = await allSamples();
    assert.equal(all.length, 3);
  });
});
