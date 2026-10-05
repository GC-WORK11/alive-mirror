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
           same surface daylog.ts and ledger.ts call (exists, create,
           text, write). Persistence across runs isn't the unit under
           test; the reconstruction math is. */
        source:
          "const store = globalThis.__storetest_fs ??= new Map();" +
          "export const Paths = { document: '/storetest-docs' };" +
          "export class File {" +
          "  constructor(dir, name) { this.uri = dir + '/' + name; }" +
          "  get exists() { return store.has(this.uri); }" +
          "  create() { if (!store.has(this.uri)) store.set(this.uri, ''); }" +
          "  text() { return Promise.resolve(store.get(this.uri) ?? ''); }" +
          "  write(s) { store.set(this.uri, String(s)); }" +
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
