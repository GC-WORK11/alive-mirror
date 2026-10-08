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
    /* components/shell/net.ts's posNow imports expo-location — the async
       providers are never the unit under test; null keeps callers on
       the last-known path. */
    if (specifier === "expo-location") {
      return { url: "apitest:expo-location", shortCircuit: true };
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
        /* in-memory File/Paths stand-in — same surface api/cache.ts
           touches: exists, create, text, write, delete, size,
           modificationTime, Directory.list(). Entries keep a
           writable mtime so cache.test.ts can age files without
           sleeping. Lives in globalThis so tests can inspect/reset. */
        source:
          "const store = globalThis.__apitest_fs ??= new Map();" +
          "export const Paths = { document: '/apitest-docs' };" +
          "export class File {" +
          "  constructor(dir, name) { const d = (dir && dir.uri) ? dir.uri : String(dir); this.uri = name === undefined ? d : d + '/' + name; }" +
          "  get exists() { return store.has(this.uri); }" +
          "  create() { if (!store.has(this.uri)) store.set(this.uri, { data: '', mtime: Date.now() }); }" +
          "  text() { return Promise.resolve(store.get(this.uri)?.data ?? ''); }" +
          "  write(s) { store.set(this.uri, { data: String(s), mtime: Date.now() }); }" +
          "  delete() { store.delete(this.uri); }" +
          "  get size() { return store.get(this.uri)?.data.length ?? 0; }" +
          "  get modificationTime() { return store.get(this.uri)?.mtime ?? 0; }" +
          "  _setMtime(ms) { const e = store.get(this.uri); if (e) e.mtime = ms; }" +
          "}" +
          "export class Directory {" +
          "  constructor(dir, name) { this.uri = name ? dir + '/' + name : String(dir); }" +
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
    if (url === "apitest:expo-location") {
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
  console.error("test-runner: no *.test.ts files found in src/api");
  process.exit(1);
}
for (const f of files) {
  await import("./" + f);
}
