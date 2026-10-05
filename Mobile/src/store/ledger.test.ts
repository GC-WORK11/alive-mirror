/// <reference types="node" />
/**
 * Ledger append honesty (docs/lanes/ledger-batch.md §1, app-stress F2).
 *
 * The removed 10-min same-name keep-first dedupe silently dropped real
 * trips — a phantom 0-km entry absorbed the real ride that followed,
 * and the key itself was locale-fragile (from/to are display strings).
 * The engine's arrivedRef already guarantees one arrival callback per
 * session, so every completed trip must land as its own row.
 *
 * Run: cd Mobile && node src/store/test-runner.mjs
 */
import { describe, it, beforeEach } from "node:test";
import assert from "node:assert/strict";
import {
  logTrip,
  loadTrips,
  clearTrips,
  resetLedgerCache,
  type Trip,
} from "./ledger";

const MIN = 60 * 1000;
const T0 = new Date(2026, 9, 6, 10, 0).getTime(); // Oct 6, local

const trip = (ts: number, over: Partial<Trip> = {}): Trip => ({
  ts,
  label: "Auto-rickshaw",
  vehicle: "auto",
  dose_ug: 1.1,
  avoided_ug: 40.0,
  from: "Connaught Place",
  to: "India Gate",
  ...over,
});

describe("logTrip — no same-name dedupe", () => {
  beforeEach(async () => {
    resetLedgerCache();           // drop the module mirror
    await clearTrips();           // and the persisted stub-file rows
  });

  it("two same-name trips 4 min apart both land", async () => {
    await logTrip(trip(T0, { dose_ug: 1.8 }));
    const trips = await logTrip(trip(T0 + 4 * MIN, { dose_ug: 0.7 }));
    assert.equal(trips.length, 2);
    assert.deepEqual(trips.map((t) => t.dose_ug), [1.8, 0.7]);
  });

  it("a real trip is never absorbed by an earlier same-route row", async () => {
    /* F2's exact wound: a 0-km phantom at T0, then the real 1.8 km ride
       9 min later — the old dedupe kept the phantom and ate the ride. */
    await logTrip(trip(T0, { dose_ug: 0.4 }));         // phantom-grade row
    const trips = await logTrip(trip(T0 + 9 * MIN, { dose_ug: 1.1 }));
    assert.equal(trips.length, 2);
    assert.equal(trips[1].dose_ug, 1.1);
  });

  it("same O&D + vehicle persists as separate rows across reload", async () => {
    await logTrip(trip(T0));
    await logTrip(trip(T0 + 4 * MIN));
    resetLedgerCache();           // force a disk re-read
    const trips = await loadTrips();
    assert.equal(trips.length, 2);
    assert.equal(trips[0].ts, T0);
    assert.equal(trips[1].ts, T0 + 4 * MIN);
  });

  it("deleteTrip still removes exactly one row", async () => {
    await logTrip(trip(T0));
    await logTrip(trip(T0 + 4 * MIN));
    const { deleteTrip } = await import("./ledger");
    const trips = await deleteTrip({
      ts: T0, from: "Connaught Place", to: "India Gate", vehicle: "auto",
    });
    assert.equal(trips.length, 1);
    assert.equal(trips[0].ts, T0 + 4 * MIN);
  });
});
