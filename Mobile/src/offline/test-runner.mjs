#!/usr/bin/env node
/**
 * Offline-layer unit-test runner (ALive-108, lane fix-mobile-audit).
 *
 *   cd Mobile && node src/offline/test-runner.mjs
 *
 * Same machinery as src/nav/test-runner.mjs: the app's bundler-style
 * extensionless imports are retried with ".ts", and the native modules
 * queue.ts transitively touches are stubbed:
 *  - expo-file-system → an in-memory File (exists/create/text/write/
 *    delete — queue.ts uses all five; no disk).
 *  - react-native     → minimal Platform.select (queue.ts → net.ts →
 *    components/shell/net.ts reads Platform + __DEV__ at load).
 *
 * Every *.test.ts in this directory is imported in-process; node:test
 * auto-runs them and the process exits non-zero on failure.
 */
import { registerHooks } from "node:module";
import { readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

globalThis.__DEV__ = true;

registerHooks({
  resolve(specifier, context, next) {
    /* specifier may carry a ?case=N query — cache-bust imports let a test
       re-load tileWarm.ts (and the stubs it transitively pulls) as a fresh
       module so per-launch state like `started` resets between cases. */
    const bare = specifier.split("?")[0];
    const parent = context.parentURL ?? "";
    const pq = parent.includes("?") ? parent.slice(parent.indexOf("?")) : "";
    if (bare === "expo-file-system") {
      return { url: "offtest:expo-file-system", shortCircuit: true };
    }
    if (bare === "react-native") {
      return { url: "offtest:react-native", shortCircuit: true };
    }
    /* tileWarm.ts deps — stubbed only when imported from tileWarm; other
       files keep resolving the real modules. The parent query propagates
       so each fresh tileWarm gets fresh stub globals. */
    if (bare === "@maplibre/maplibre-react-native" && parent.includes("/map/tileWarm.ts")) {
      return { url: "offtest:maplibre" + pq, shortCircuit: true };
    }
    if (bare === "../search/client" && parent.includes("/map/tileWarm.ts")) {
      return { url: "offtest:search-client" + pq, shortCircuit: true };
    }
    if (bare === "./style" && parent.includes("/map/tileWarm.ts")) {
      return { url: "offtest:map-style" + pq, shortCircuit: true };
    }
    try {
      const r = next(bare, context);
      if (specifier.includes("?") && r.url) r.url += specifier.slice(specifier.indexOf("?"));
      return r;
    } catch (err) {
      if (bare.startsWith("./") || bare.startsWith("../")) {
        const r = next(bare + ".ts", context);
        if (specifier.includes("?") && r.url) r.url += specifier.slice(specifier.indexOf("?"));
        return r;
      }
      throw err;
    }
  },
  load(url, context, next) {
    const bare = url.split("?")[0];
    if (bare === "offtest:maplibre") {
      return {
        format: "module",
        shortCircuit: true,
        /* OfflineManager spy — packs seeded, calls recorded into
           globalThis.__offtest_ml. Methods read the global lazily so a
           test can swap the whole state object between cases. */
        source:
          "const S = () => (globalThis.__offtest_ml ??= { packs: [], created: [], deleted: [], maxAmbient: null });" +
          "export const OfflineManager = {" +
          "  async setMaximumAmbientCacheSize(n) { S().maxAmbient = n; }," +
          "  async getPacks() { return S().packs.slice(); }," +
          "  async deletePack(id) { S().deleted.push(id); S().packs = S().packs.filter((p) => p.id !== id); }," +
          "  async createPack(opts) {" +
          "    if (S().failCreate) throw new Error('offline db unavailable');" +
          "    S().created.push(opts);" +
          "    return { id: 'pack-' + S().created.length, metadata: opts.metadata };" +
          "  }," +
          "};" +
          "export default {};",
      };
    }
    if (bare === "offtest:search-client") {
      return {
        format: "module",
        shortCircuit: true,
        source:
          "export const API_BASE = globalThis.__offtest_api_base ?? 'http://api.test';",
      };
    }
    if (bare === "offtest:map-style") {
      return {
        format: "module",
        shortCircuit: true,
        /* the bundled-style sentinel — identity is what tileWarm's gate
           compares, so one object per process via the global slot */
        source:
          "export const v2Style = (globalThis.__offtest_v2style ??= { version: 8, marker: 'bundled' });",
      };
    }
    if (url === "offtest:expo-file-system") {
      return {
        format: "module",
        shortCircuit: true,
        /* in-memory stand-in for expo-file-system's File/Paths API —
           same surface queue.ts calls via safefile (exists, create,
           text, write, delete, copySync, moveSync with the overwrite
           semantics safefile's atomic rename needs — the store
           runner's stub, mirrored). Disk durability isn't the unit
           under test; the wipe-generation guard is. */
        source:
          "const store = globalThis.__offtest_fs ??= new Map();" +
          "export const Paths = { document: '/offtest-docs' };" +
          "export class File {" +
          "  constructor(dir, name) { this.uri = name === undefined ? String(dir) : dir + '/' + name; }" +
          "  get exists() { return store.has(this.uri); }" +
          "  create() { if (!store.has(this.uri)) store.set(this.uri, ''); }" +
          "  text() { return Promise.resolve(store.get(this.uri) ?? ''); }" +
          "  write(s) { store.set(this.uri, String(s)); }" +
          "  delete() { store.delete(this.uri); }" +
          "  copySync(dest, opts) {" +
          "    if (store.has(dest.uri) && !(opts && opts.overwrite)) throw new Error('dest exists');" +
          "    store.set(dest.uri, store.get(this.uri) ?? '');" +
          "  }" +
          "  moveSync(dest, opts) {" +
          "    if (store.has(dest.uri) && !(opts && opts.overwrite)) throw new Error('dest exists');" +
          "    store.set(dest.uri, store.get(this.uri) ?? '');" +
          "    store.delete(this.uri);" +
          "  }" +
          "}" +
          "export class Directory {" +   /* api/cache.ts constructs one at load */
          "  constructor(dir, name) { this.uri = name === undefined ? String(dir) : dir + '/' + name; }" +
          "  get exists() { return store.has(this.uri); }" +
          "  create() { store.set(this.uri, 'dir'); }" +
          "  list() { return []; }" +
          "}",
      };
    }
    if (url === "offtest:react-native") {
      return {
        format: "module",
        shortCircuit: true,
        source:
          "export const Platform = { select: (o) => o?.default };" +
          "export default {};",
      };
    }
    return next(url, context);
  },
});

const here = fileURLToPath(new URL(".", import.meta.url));
const files = readdirSync(here)
  .filter((f) => f.endsWith(".test.ts"))
  .sort();
if (files.length === 0) {
  console.error("test-runner: no *.test.ts files found in src/offline");
  process.exit(1);
}
for (const f of files) {
  await import("./" + f);
}
