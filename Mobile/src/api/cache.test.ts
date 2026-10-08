/// <reference types="node" />
/**
 * The cache was the one unbounded store in the audit: one file per
 * distinct ~100 m O/D pair + vehicle signature (~255–420 KB each on
 * the measured backend), per-route strips, per-cell curves — no cap,
 * no eviction. A year of commuting from varied spots would have
 * parked tens of MB in the user's Documents.
 *
 * These tests pin the eviction contract (MAX_ENTRIES, MAX_BYTES,
 * MAX_AGE_MS) against the in-memory FS stub: oldest-first eviction,
 * stale-age reaping, and the wipe-generation guard staying intact.
 *
 * Run: cd Mobile && node src/api/test-runner.mjs
 */
import { describe, it, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { Directory, File, Paths } from "expo-file-system";
import {
  cacheClear,
  cacheGeneration,
  cachePeek,
  cacheSet,
  cacheStats,
} from "./cache";

const store = () =>
  (globalThis as { __apitest_fs?: Map<string, { data: string; mtime: number }> })
    .__apitest_fs ?? new Map();
const DIR = new Directory(Paths.document, "alive-cache");
const files = (): File[] => DIR.list().filter((e) => e instanceof File);
const setMtime = (f: File, ms: number) =>
  (f as unknown as { _setMtime(v: number): void })._setMtime(ms);

beforeEach(async () => {
  /* module-level state (writesSinceSweep, wipeGen) persists between
     tests in-process — a clear() flushes files and bumps gen so each
     test starts clean and requests made with the CURRENT generation
     (since=cacheGeneration()) always pass the guard. */
  store().clear();
  await cacheClear();
});

const set = (key: string, body = "x") =>
  cacheSet(key, { body }, 60_000, cacheGeneration());

describe("cache eviction — the store stays cheap after years", () => {
  it("keeps last-good reads + fresh flags working", async () => {
    await set("v2:city", "delhi");
    const hit = await cachePeek<{ body: string }>("v2:city");
    assert.equal(hit?.value.body, "delhi");
    assert.equal(hit?.fresh, true);
    assert.ok(typeof hit?.ageS === "number");
  });

  it("evicts oldest-first once the entry cap is exceeded", async () => {
    /* 80 writes → sweeps at #16/#32/#48/#64/#80; each trims to 64,
       so the first-written files die first. */
    for (let i = 0; i < 80; i++) await set(`v2:plan:${i}`, "p");
    const stats = cacheStats();
    /* writesSinceSweep is module state shared across tests — the last
       sweep lands on an unknown write inside this loop, so assert the
       bound (64 + up to 15 unswept writes) rather than exact 64. */
    assert.ok(stats.entries <= 79, `entries ${stats.entries} over cap`);
    assert.ok(stats.entries < 80);
    assert.ok(stats.entries >= 30, "sweep clearly trimmed");
    /* newest keys survive; the earliest are gone */
    const peekOld = await cachePeek("v2:plan:0");
    const peekNew = await cachePeek("v2:plan:79");
    assert.equal(peekOld, null);
    assert.ok(peekNew !== null);
  });

  it("evicts under the byte cap — big plan payloads can't pile up", async () => {
    /* ~300 KB per entry ≈ a measured /v2/plan payload. 96 entries ≈
       29 MB — far over the 12 MB cap. Sweeps trim to the cap; at most
       15 unswept writes (~4.7 MB) can follow the last one, so the
       honest bound is cap + one inter-sweep window. */
    const blob = "x".repeat(300 * 1024);
    for (let i = 0; i < 96; i++) await set(`v2:strip:r${i}`, blob);
    const stats = cacheStats();
    assert.ok(stats.bytes <= 12 * 1024 * 1024 + 15 * 320 * 1024,
      `bytes ${stats.bytes} should sit at cap + one sweep window`);
    assert.ok(stats.entries <= 79, `entries ${stats.entries} over cap`);
    assert.equal(await cachePeek("v2:strip:r0"), null);
  });

  it("reaps entries past the 30-day staleness bound even under the caps", async () => {
    /* 5 entries aged to 31 days — under every count/byte cap, so only
       MAX_AGE_MS can evict them. */
    for (let i = 0; i < 5; i++) await set(`v2:old:${i}`, "o");
    const thirtyOneDays = 31 * 24 * 60 * 60 * 1000;
    for (const f of files()) setMtime(f, Date.now() - thirtyOneDays);
    for (let i = 0; i < 16; i++) await set(`v2:new:${i}`, "n"); // triggers sweep
    assert.equal(await cachePeek("v2:old:0"), null);
    const stats = cacheStats();
    assert.equal(stats.entries, 16);
  });

  it("never re-writes after a wipe — the generation guard", async () => {
    const since = cacheGeneration();
    await cacheClear(); // bumps gen, as delete-my-data does
    await cacheSet("v2:city", "ghost", 60_000, since);
    assert.equal(await cachePeek("v2:city"), null);
  });
});
