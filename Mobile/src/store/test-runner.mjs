#!/usr/bin/env node
/**
 * Store-layer unit-test runner (ALive-108, lane ledger-audit).
 *
 *   cd Mobile && node src/store/test-runner.mjs
 *
 * Same machinery as src/nav/test-runner.mjs: the app's bundler-style
 * extensionless imports are retried with ".ts", and the two native
 * modules the persistence stores touch are stubbed:
 *  - expo-file-system → an in-memory File (no disk) so daylog's
 *    readDisk/scheduleWrite exercise the real code path harmlessly.
 *  - react-native     → minimal Platform.select (transitively pulled
 *    by i18n-adjacent modules on other lanes; cheap insurance).
 *
 * Every *.test.ts in this directory is imported in-process; node:test
 * auto-runs them and the process exits non-zero on failure.
 */
import { registerHooks } from "node:module";
import { readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

/* Metro injects __DEV__ at bundle time; the API-base modules read it at
   import. Node has no such global — tests want production values. */
globalThis.__DEV__ = false;

registerHooks({
  resolve(specifier, context, next) {
    if (specifier === "expo-file-system") {
      return { url: "storetest:expo-file-system", shortCircuit: true };
    }
    if (specifier === "react-native") {
      return { url: "storetest:react-native", shortCircuit: true };
    }
    /* startup/idle's afterFirstFrame uses requestAnimationFrame, which
       Node lacks — the stores' persistence calls would hang. Stub to an
       already-idle resolve; the delay isn't the unit under test. */
    if (specifier === "../startup/idle") {
      return { url: "storetest:idle", shortCircuit: true };
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
    if (url === "storetest:expo-file-system") {
      return {
        format: "module",
        shortCircuit: true,
        /* in-memory stand-in for expo-file-system's File/Paths API —
           same surface daylog.ts/ledger.ts/daysum.ts call (exists,
           create, text, write, delete, copySync, moveSync with the
           overwrite semantics safefile's atomic rename needs).
           Persistence across runs isn't the unit under test; the
           reconstruction math is. */
        source:
          "const store = globalThis.__storetest_fs ??= new Map();" +
          "export const Paths = { document: '/storetest-docs' };" +
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
          /* Directory — only the surface api/cache.ts touches (exists,
             create, list); needed so settings.clearAllData can be
             exercised in-process. */
          "export class Directory {" +
          "  constructor(dir, name) { this.uri = name ? dir + '/' + name : String(dir); }" +
          "  get exists() { return true; }" +
          "  create() {}" +
          "  delete() {}" +
          "  list() {" +
          "    const p = this.uri + '/';" +
          "    return [...store.keys()].filter((k) => k.startsWith(p)).map((u) => new File(u));" +
          "  }" +
          "}",
      };
    }
    if (url === "storetest:idle") {
      return {
        format: "module",
        shortCircuit: true,
        source: "export const afterFirstFrame = () => Promise.resolve();",
      };
    }
    if (url === "storetest:react-native") {
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
  console.error("test-runner: no *.test.ts files found in src/store");
  process.exit(1);
}
for (const f of files) {
  await import("./" + f);
}
