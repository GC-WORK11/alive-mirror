#!/usr/bin/env node
/**
 * API layer unit-test runner — same hooks as src/nav/test-runner.mjs:
 * extensionless ".ts" resolution retry, a minimal react-native stub for
 * components/shell/net.ts (Platform.select), and an expo-file-system
 * stub for api/cache.ts (tested code never touches the disk cache).
 *
 *   cd Mobile && node src/api/test-runner.mjs
 *
 * Every *.test.ts in this directory is imported in-process; node:test
 * auto-runs them and the process exits non-zero on failure.
 */
import { registerHooks } from "node:module";
import { readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

/* RN's __DEV__ global (components/shell/net.ts reads it at module load). */
globalThis.__DEV__ = true;

registerHooks({
  resolve(specifier, context, next) {
    if (specifier === "react-native") {
      return { url: "apitest:react-native", shortCircuit: true };
    }
    if (specifier === "expo-file-system") {
      return { url: "apitest:expo-file-system", shortCircuit: true };
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
    if (url === "apitest:react-native") {
      return {
        format: "module",
        shortCircuit: true,
        source:
          "export const Platform = { select: (o) => o?.default };" +
          "export default {};",
      };
    }
    if (url === "apitest:expo-file-system") {
      return {
        format: "module",
        shortCircuit: true,
        source:
          "export class Directory {} export class File {} export const Paths = {};" +
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
  console.error("test-runner: no *.test.ts files found in src/api");
  process.exit(1);
}
for (const f of files) {
  await import("./" + f);
}
