#!/usr/bin/env node
/**
 * Storage-growth simulation for the local-store audit
 * (docs/lanes/local-store-report.md). Drives the REAL store modules
 * (ledger/daylog/daysum/api/cache) against an in-memory expo-file-system
 * and measures the on-disk JSON footprint at 1 month / 1 year / 3 years
 * of a heavy-Delhi-commuter usage profile:
 *
 *   - 3 logged trips/day (commute out, commute back, one errand)
 *   - ~28 ambient samples/day (15-min foreground spacing over 2×3.5 h
 *     commute windows — above recordSample's 8-min/0.9-km dedupe)
 *   - 1 symptom check-in/day
 *   - 4 distinct /v2/plan + /v2/strip cache writes/day at ~100 m-jittered
 *     coords (realistic: a new cache key whenever the user plans from a
 *     different corner), each payload at the measured 300 KB size
 *   - every day's rollup sealed via daysum.getDay (the "daily rollup"
 *     the owner asked for — daysum.json, 400-day cap)
 *
 * Usage: cd Mobile && node scripts/storage-growth-sim.mjs [days]
 */
import { registerHooks } from "node:module";
import { readdirSync } from "node:fs";

/* ---- in-memory expo-file-system (mirrors src/api/test-runner.mjs) ---- */
globalThis.__DEV__ = true;

registerHooks({
  resolve(specifier, context, next) {
    if (specifier === "expo-file-system") {
      return { url: "sim:expo-file-system", shortCircuit: true };
    }
    if (specifier.endsWith("/startup/idle") || specifier === "../startup/idle") {
      return { url: "sim:idle", shortCircuit: true };
    }
    try {
      return next(specifier, context);
    } catch (err) {
      if (specifier.startsWith("./") || specifier.startsWith("../")) {
        return next(specifier + ".ts", context);
      }
      throw err;
    }
  },
  load(url, context, next) {
    if (url === "sim:expo-file-system") {
      return {
        format: "module",
        shortCircuit: true,
        source:
          "const store = globalThis.__simfs ??= new Map();" +
          "export const Paths = { document: '/sim-docs', cache: '/sim-cache' };" +
          "export class File {" +
          "  constructor(dir, name) { const d = (dir && dir.uri) ? dir.uri : String(dir); this.uri = name === undefined ? d : d + '/' + name; }" +
          "  get exists() { return store.has(this.uri); }" +
          "  create() { if (!store.has(this.uri)) store.set(this.uri, { data: '', mtime: Date.now() }); }" +
          "  text() { return Promise.resolve(store.get(this.uri)?.data ?? ''); }" +
          "  write(s) { store.set(this.uri, { data: String(s), mtime: Date.now() }); }" +
          "  delete() { store.delete(this.uri); }" +
          "  get size() { return store.get(this.uri)?.data.length ?? 0; }" +
          "  get modificationTime() { return store.get(this.uri)?.mtime ?? 0; }" +
          "  copySync(dest, opts) {" +
          "    if (store.has(dest.uri) && !(opts && opts.overwrite)) throw new Error('dest exists');" +
          "    store.set(dest.uri, { data: store.get(this.uri)?.data ?? '', mtime: Date.now() });" +
          "  }" +
          "  moveSync(dest, opts) {" +
          "    if (store.has(dest.uri) && !(opts && opts.overwrite)) throw new Error('dest exists');" +
          "    store.set(dest.uri, { data: store.get(this.uri)?.data ?? '', mtime: Date.now() });" +
          "    store.delete(this.uri);" +
          "  }" +
          "}" +
          "export class Directory {" +
          "  constructor(dir, name) { const d = (dir && dir.uri) ? dir.uri : String(dir); this.uri = name ? d + '/' + name : d; }" +
          "  get exists() { return true; }" +
          "  create() {}" +
          "  delete() {}" +
          "  list() {" +
          "    const p = this.uri + '/';" +
          "    return [...store.keys()].filter((k) => k.startsWith(p)).map((u) => new File(u));" +
          "  }" +
          "}" +
          "export default {};",
      };
    }
    if (url === "sim:idle") {
      return {
        format: "module",
        shortCircuit: true,
        source: "export const afterFirstFrame = () => Promise.resolve();",
      };
    }
    return next(url, context);
  },
});

const DAYS = Number(process.argv[2] ?? 1095);
const DAY_MS = 86400_000;
const now = Date.now();

const { logTrip, loadTrips } = await import("../src/store/ledger.ts");
const { recordSample, setCheckin, allSamples } = await import("../src/store/daylog.ts");
const { getDay } = await import("../src/store/daysum.ts");
const { cacheSet, cacheStats, cacheGeneration } = await import("../src/api/cache.ts");

const fs = () => globalThis.__simfs;
const bytesOf = (pred) =>
  [...fs().entries()]
    .filter(([k]) => pred(k))
    .reduce((a, [, e]) => a + e.data.length, 0);

const trip = (ts, i) => ({
  ts,
  label: "metro",
  vehicle: i % 3 === 0 ? "car" : i % 3 === 1 ? "metro" : "walk",
  dose_ug: 8.4 + (i % 17),
  avoided_ug: 3.1,
  from: "Rohini Sector 18",
  to: "Hauz Khas Village",
  fromLat: 28.7041,
  fromLon: 77.1125,
  toLat: 28.5494,
  toLon: 77.2001,
  emit_kg: 2.7,
  dose_lo_ug: 6.2,
  dose_hi_ug: 11.8,
  donated: i % 5 === 0,
});

/* measured /v2/plan envelope ≈ 255–420 KB on the live backend — the
   sim writes 300 KB bodies so eviction math runs against real sizes. */
const PLAN_BLOB = "x".repeat(300 * 1024);

const dayKey = (ts) => new Date(ts).toISOString().slice(0, 10);
const marks = new Set([30, 365, 730, 1095].filter((d) => d <= DAYS));
const report = [];

for (let d = DAYS - 1; d >= 0; d--) {
  const dayStart = now - d * DAY_MS;
  /* trips: 07:40, 18:20, 20:10 */
  for (let i = 0; i < 3; i++) await logTrip(trip(dayStart + (7 + i * 5) * 3600_000, d * 3 + i));
  /* ambient: 15-min spacing through two commute windows + scattered coords */
  for (let s = 0; s < 28; s++) {
    await recordSample({
      ts: dayStart + 6 * 3600_000 + s * 15 * 60_000,
      lat: 28.55 + ((d * 7 + s) % 13) * 0.021,
      lon: 77.15 + ((d * 5 + s) % 11) * 0.019,
      amb: 90 + ((d * 31 + s * 7) % 220),
      bz: 110 + ((d * 13 + s * 3) % 180),
    });
  }
  await setCheckin(dayStart + 21 * 3600_000, { breath: d % 3, eyes: d % 3, energy: (d + 1) % 3 });
  /* cache: 4 plan writes at ~100 m-jittered O/D + one strip → new keys */
  const gen = cacheGeneration();
  for (let c = 0; c < 4; c++) {
    const j = (d * 4 + c) % 997;
    await cacheSet(`v2:plan:${(28.5 + j * 0.001).toFixed(3)},${(77.1 + j * 0.001).toFixed(3)}>28.6,77.2|v`, PLAN_BLOB, 600_000, gen);
    await cacheSet(`v2:strip:${(d * 4 + c).toString(16)}x${j}`, "s".repeat(7 * 1024), 600_000, gen);
  }
  await getDay(dayKey(dayStart)); // seal the daily rollup

  const lived = DAYS - d;
  if (marks.has(lived)) {
    const trips = await loadTrips();
    const samples = await allSamples();
    report.push({
      months: Math.round(lived / 30.44),
      days: lived,
      ledger_json: bytesOf((k) => k.endsWith("ledger.json")),
      ledger_rows: trips.length,
      daylog_json: bytesOf((k) => k.endsWith("daylog.json")),
      daylog_samples: samples.length,
      daysum_json: bytesOf((k) => k.endsWith("daysum.json")),
      daysum_days: Object.keys(
        (JSON.parse(fs().get("/sim-docs/daysum.json")?.data ?? "{}").d ?? {}).days ?? {},
      ).length,
      alive_cache: cacheStats(),
      outbox: bytesOf((k) => k.endsWith("outbox.json")),
      total_bytes: [...fs().values()].reduce((a, e) => a + e.data.length, 0),
    });
  }
}

const kb = (n) => (n / 1024).toFixed(1);
const mb = (n) => (n / 1024 / 1024).toFixed(2);
console.log("lived | ledger.json (rows) | daylog.json (samples) | daysum.json (days) | alive-cache (files) | TOTAL app docs");
for (const r of report) {
  console.log(
    `${r.days}d`.padEnd(5) +
    ` | ${kb(r.ledger_json)} KB (${r.ledger_rows})` +
    ` | ${kb(r.daylog_json)} KB (${r.daylog_samples})` +
    ` | ${kb(r.daysum_json)} KB (${r.daysum_days})` +
    ` | ${mb(r.alive_cache.bytes)} MB (${r.alive_cache.entries})` +
    ` | ${mb(r.total_bytes)} MB`,
  );
}
