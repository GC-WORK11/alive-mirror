/// <reference types="node" />
/**
 * Outbox wipe-generation guard (docs/lanes/mobile-audit.md MED BUG):
 * a trip donation whose POST started BEFORE delete-my-data must never
 * re-create outbox.json after the wipe — mirrors the guard cache.ts
 * already runs on cacheSet/clearOutbox's sibling path (fetchCached →
 * cacheSet). A wiped user must not silently re-donate.
 *
 * The File backend is the test-runner's in-memory stub, so queueSize /
 * onQueueChange observe the real code path end to end.
 *
 * Run: cd Mobile && node src/offline/test-runner.mjs
 */
import { describe, it, beforeEach } from "node:test";
import assert from "node:assert/strict";
import {
  enqueue,
  enqueueTripDonation,
  flush,
  onQueueChange,
  outboxGeneration,
  queueSize,
  clearOutbox,
  MAX_QUEUE,
  type TripDonation,
} from "./queue";

const DONATION: TripDonation = {
  device_token: "tok-test",
  summary: { mode: "auto", distance_km: 4.2, duration_s: 900, dose_ug: 12.3 },
  trajectory: [{ lat: 28.6315, lon: 77.2167 }, { lat: 28.5245, lon: 77.2066 }],
};

describe("enqueue/clearOutbox — the resurrect-after-wipe guard", () => {
  /* every test starts from a wiped store — the in-memory File map
     persists across cases in a run */
  beforeEach(async () => {
    await clearOutbox();
  });

  it("a donation that started before the wipe must not write after it", async () => {
    /* the exact audit sequence: POST in flight (gen captured) →
       delete-my-data runs → POST fails → enqueue lands. Before the fix
       this wrote outbox.json and auto-flushed on the next up event. */
    const gen = outboxGeneration();
    await clearOutbox();
    const r = await enqueueTripDonation("http://api.test", DONATION, gen);
    assert.equal(r.size, 0);
    assert.equal(r.droppedNow, 0);
    assert.equal(await queueSize(), 0);
  });

  it("a same-era enqueue still writes — the guard only kills the stale era", async () => {
    const gen = outboxGeneration();
    const r = await enqueueTripDonation("http://api.test", DONATION, gen);
    assert.equal(r.size, 1);
    assert.equal(await queueSize(), 1);
  });

  it("the queue itself survives the wipe — new-era items still enqueue", async () => {
    await clearOutbox();
    /* no `since` (or a fresh generation) → post-wipe donations queue
       normally; the guard is scoped to the deleted era, not a lockout */
    const r = await enqueueTripDonation("http://api.test", DONATION);
    assert.equal(r.size, 1);
    const r2 = await enqueue("http://api.test/x", { a: 1 }, outboxGeneration());
    assert.equal(r2.size, 2);
  });

  it("watchers see the wipe and never a resurrected depth", async () => {
    const seen: number[] = [];
    const off = onQueueChange((n) => seen.push(n));
    const gen = outboxGeneration();
    await clearOutbox();                     // → 0
    await enqueueTripDonation("http://api.test", DONATION, gen); // dropped — no notify
    off();
    assert.deepEqual(seen, [0]);
    assert.equal(await queueSize(), 0);
  });

  it("flush on an empty post-wipe outbox reports nothing pending", async () => {
    const gen = outboxGeneration();
    await clearOutbox();
    await enqueueTripDonation("http://api.test", DONATION, gen);
    const rep = await flush();
    assert.equal(rep.sent, 0);
    assert.equal(rep.remaining, 0);
  });

  it("a stale-era enqueue cannot overflow back into the queue", async () => {
    /* belt-and-braces: even at cap boundaries the stale item drops */
    const gen = outboxGeneration();
    await clearOutbox();
    for (let i = 0; i < MAX_QUEUE; i++) await enqueue("http://api.test/x", { i });
    assert.equal(await queueSize(), MAX_QUEUE);
    await clearOutbox(); // delete-my-data mid-session
    assert.equal(await queueSize(), 0);
    const r = await enqueueTripDonation("http://api.test", DONATION, gen);
    assert.equal(r.size, 0);
    assert.equal(await queueSize(), 0);
  });
});
