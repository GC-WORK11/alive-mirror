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
    if (specifier === "expo-file-system") {
      return { url: "offtest:expo-file-system", shortCircuit: true };
    }
    if (specifier === "react-native") {
      return { url: "offtest:react-native", shortCircuit: true };
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
    if (url === "offtest:expo-file-system") {
      return {
        format: "module",
        shortCircuit: true,
        /* in-memory stand-in for expo-file-system's File/Paths API —
           same surface queue.ts calls (exists, create, text, write,
           delete). Disk durability isn't the unit under test; the
           wipe-generation guard is. */
        source:
          "const store = globalThis.__offtest_fs ??= new Map();" +
          "export const Paths = { document: '/offtest-docs' };" +
          "export class Directory {" +   /* api/cache.ts constructs one at load */
          "  constructor(dir, name) { this.uri = dir + '/' + name; }" +
          "  get exists() { return store.has(this.uri); }" +
          "  create() { store.set(this.uri, 'dir'); }" +
          "  list() { return []; }" +
          "}" +
          "export class File {" +
          "  constructor(dir, name) { this.uri = dir + '/' + name; }" +
          "  get exists() { return store.has(this.uri); }" +
          "  create() { if (!store.has(this.uri)) store.set(this.uri, ''); }" +
          "  text() { return Promise.resolve(store.get(this.uri) ?? ''); }" +
          "  write(s) { store.set(this.uri, String(s)); }" +
          "  delete() { store.delete(this.uri); }" +
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
