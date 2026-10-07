#!/usr/bin/env node
/**
 * Nav engine unit-test runner (ALive-108, lane r4-testnav).
 *
 *   cd Mobile && node src/nav/test-runner.mjs
 *
 * Why a runner instead of bare `node --test`:
 *  - The app's tsconfig uses moduleResolution "bundler" → sources and
 *    tests import extensionless ("./strip"). Node ESM requires an
 *    explicit ".ts" suffix, so we install a resolve hook that retries
 *    failed relative imports with ".ts" appended. tsc stays clean
 *    because the source text keeps bundler-style specifiers.
 *  - api/reroute.ts transitively imports react-native (via
 *    components/shell/net.ts). The hook stubs it with a minimal
 *    Platform.select so pure fetch code is exercisable in node.
 *
 * Every *.test.ts in this directory is imported in-process; node:test
 * auto-runs them and the process exits non-zero on failure.
 */
import { registerHooks } from "node:module";
import { readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

/* `__DEV__` is a compile-time global Metro/babel injects into RN bundles;
   several modules (shell/net, search/client, a11y) read it bare. Node has
   no such global — async callbacks that reach it (debounce timers, a11y
   pass) died with ReferenceError AFTER the suite finished, turning the
   runner's exit code red despite every test passing. Metro defines it
   true in dev bundles; mirror that here. */
globalThis.__DEV__ = true;

registerHooks({
  resolve(specifier, context, next) {
    if (specifier === "react-native") {
      return { url: "navtest:react-native", shortCircuit: true };
    }
    /* components/shell/net.ts's posNow imports expo-location — the async
       providers are never the unit under test; null keeps callers on
       the last-known path. */
    if (specifier === "expo-location") {
      return { url: "navtest:expo-location", shortCircuit: true };
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
    if (url === "navtest:react-native") {
      return {
        format: "module",
        shortCircuit: true,
        source:
          "export const Platform = { select: (o) => o?.default };" +
          "export default {};",
      };
    }
    if (url === "navtest:expo-location") {
      return {
        format: "module",
        shortCircuit: true,
        source:
          "export const Accuracy = { Balanced: 3 };" +
          "export const getCurrentPositionAsync = async () => null;" +
          "export const getLastKnownPositionAsync = async () => null;" +
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
  console.error("test-runner: no *.test.ts files found in src/nav");
  process.exit(1);
}
for (const f of files) {
  await import("./" + f);
}
