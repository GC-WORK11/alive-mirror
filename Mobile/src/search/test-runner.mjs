#!/usr/bin/env node
/**
 * Search-layer unit-test runner (Alive, index-prebuild lane).
 *
 *   cd Mobile && node src/search/test-runner.mjs
 *
 * Same machinery as src/offline/test-runner.mjs: extensionless imports
 * retry with ".ts", ?case=N specifiers resolve as fresh module instances
 * (t0.ts's index state is module-level), and Metro's require() is
 * stubbed — JSON assets are re-read from disk per require so a lazy
 * build in one case can't see another case's consumed corpus array.
 *
 * t0's prebuilt-asset load is controllable through
 * globalThis.__t0_index_mode: "ok" (serves the real assets/t0-index/
 * chunks — manifest fields from manifest.json and load(i) re-parses
 * c{i}.json from disk per call so a merged-and-emptied chunk in one
 * case can't poison the next), "missing" (require throws — asset
 * absent), "corrupt" (serves garbage — validation must reject it).
 * The tests flip it between cases.
 *
 * Every *.test.ts in this directory is imported in-process; node:test
 * auto-runs them and the process exits non-zero on failure.
 */
import { createRequire, registerHooks } from "node:module";
import { readdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

globalThis.__DEV__ = false;
globalThis.__t0_index_mode = "ok";

const SEARCH_DIR = new URL("./", import.meta.url);
const creq = createRequire(new URL("./x.ts", import.meta.url));

const T0_INDEX_DIR = fileURLToPath(new URL("../../assets/t0-index/", SEARCH_DIR));

globalThis.require = (spec) => {
  if (spec.includes("t0-index")) {
    const mode = globalThis.__t0_index_mode;
    if (mode === "missing") throw new Error("Cannot find module './t0-index/chunks.js'");
    if (mode === "corrupt") return { v: 0, garbage: true };
    const manifest = JSON.parse(readFileSync(T0_INDEX_DIR + "manifest.json", "utf8"));
    // synthetic dispatch module — manifest fields real, each load(i) a
    // fresh parse off disk (hydrateNext empties merged arrays in place,
    // so re-reading keeps later cases honest)
    return {
      ...manifest,
      load: (i) =>
        i >= 0 && i < manifest.chunks
          ? JSON.parse(readFileSync(`${T0_INDEX_DIR}c${i}.json`, "utf8"))
          : null,
    };
  }
  // JSON assets: fresh parse per require — a lazy build frees the corpus
  // array it got, and a shared CJS cache would hand the next case the
  // emptied array
  if (spec.endsWith(".json")) {
    const p = fileURLToPath(new URL(spec, SEARCH_DIR));
    return JSON.parse(readFileSync(p, "utf8"));
  }
  return creq(spec);
};

/* armed warm() timers are deferred by design — they'd hold the event
   loop for seconds after the tests finish; unref them all (RN-side
   setTimeout returns a number, so .unref is optional-chained). */
{
  const _setTimeout = globalThis.setTimeout;
  globalThis.setTimeout = (fn, ms, ...a) => {
    const t = _setTimeout(fn, ms, ...a);
    t?.unref?.();
    return t;
  };
}

registerHooks({
  resolve(specifier, context, next) {
    const bare = specifier.split("?")[0];
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
});

const here = fileURLToPath(new URL(".", import.meta.url));
const files = readdirSync(here)
  .filter((f) => f.endsWith(".test.ts"))
  .sort();
if (files.length === 0) {
  console.error("test-runner: no *.test.ts files found in src/search");
  process.exit(1);
}
for (const f of files) {
  await import("./" + f);
}
