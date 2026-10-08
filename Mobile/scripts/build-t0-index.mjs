#!/usr/bin/env node
/**
 * build-t0-index.mjs — emit the prebuilt T0 search index the app ships.
 *
 *   cd Mobile && node scripts/build-t0-index.mjs           # rebuild if stale
 *   cd Mobile && node scripts/build-t0-index.mjs --check   # sig check only (exit 1 if stale)
 *   cd Mobile && node scripts/build-t0-index.mjs --force   # rebuild regardless
 *
 * What it does: reads assets/delhi-gazetteer.json (the bundled corpus —
 * itself emitted by scripts/build_mobile_gaz.py / build_corpus.py
 * --emit-mobile), builds the index THROUGH the app's own t0.ts indexing
 * code (the __t0 hooks — fold/tokens/caps are never re-implemented here),
 * and writes a CHUNKED index to assets/t0-index/:
 *
 *   manifest.json   {v, gaz_sha256, gaz_rows, chunks} — freshness sig
 *   c0.json..cN.json  ~0.9 MB slices; every table (entries + 5 posting
 *                     maps) is sharded across the same N chunks
 *   chunks.js       generated dispatch module — exposes the manifest
 *                   fields plus load(i), a switch of literal requires so
 *                   Metro bundles every chunk but only PARSES the one
 *                   the runtime asks for
 *
 * Why chunked: a single 32 MB JSON parse+hydrate is one ~8 s JS block on
 * a cold-booting device — inside the documented boot-window kill band it
 * jetsams the app outright (iPhone 17 sim: 5/5 cold-boot deaths vs 0/5
 * for the sliced lazy build). Per-chunk parse+merge keeps every block
 * inside the same envelope the old sliced build survived.
 *
 * When it runs: `npm install`/`npm ci` postinstall (package.json) — the
 * same step every build path (dev, expo run, gradle assembleRelease) goes
 * through — plus `scripts/build_mobile_gaz.py --install`, the step that
 * stamps the gazetteer asset itself. Regenerating after ANY gazetteer
 * edit is `npm run build:t0`.
 */
import { registerHooks, createRequire } from "node:module";
import { createHash } from "node:crypto";
import { existsSync, readFileSync, writeFileSync, mkdirSync, rmSync, renameSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

globalThis.__DEV__ = false;
// t0.ts uses Metro's require() for bundled JSON assets — give it a real one
globalThis.require = createRequire(new URL("../src/search/x.ts", import.meta.url));

registerHooks({
  resolve(specifier, context, next) {
    try {
      return next(specifier, context);
    } catch (err) {
      if (specifier.startsWith("./") || specifier.startsWith("../"))
        return next(specifier + ".ts", context);
      throw err;
    }
  },
});

const MOBILE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const GAZ = path.join(MOBILE, "assets", "delhi-gazetteer.json");
const OUT_DIR = path.join(MOBILE, "assets", "t0-index");
const MANIFEST = path.join(OUT_DIR, "manifest.json");
const CHUNK_TARGET = 900_000;  // serialized bytes per c*.json (~0.2-0.3 s parse)

const args = new Set(process.argv.slice(2));
const CHECK = args.has("--check");
const FORCE = args.has("--force");

if (!existsSync(GAZ)) {
  console.error(`gazetteer missing: ${GAZ}`);
  process.exit(2);
}
const sha = createHash("sha256").update(readFileSync(GAZ)).digest("hex");

let manifest = null;
try {
  manifest = JSON.parse(readFileSync(MANIFEST, "utf8"));
} catch { /* absent or corrupt — (re)build below */ }

const chunksPresent = (m) =>
  m && existsSync(path.join(OUT_DIR, "chunks.js"))
    && [...Array(m.chunks).keys()].every((i) => existsSync(path.join(OUT_DIR, `c${i}.json`)));

if (manifest && manifest.gaz_sha256 === sha && chunksPresent(manifest) && !FORCE) {
  console.log(`t0-index fresh: ${manifest.gaz_rows?.toLocaleString?.() ?? "?"} rows, ${manifest.chunks} chunks, sha ${sha.slice(0, 12)}…`);
  process.exit(0);
}
if (CHECK) {
  const why = !manifest ? "index assets missing"
    : manifest.gaz_sha256 !== sha ? "sig mismatch — gazetteer changed since last prebuild"
    : "manifest ok but chunk files missing";
  console.error(`t0-index stale: ${why}. Regenerate: npm run build:t0`);
  process.exit(1);
}

const t0 = await import("../src/search/t0.ts");
const t = Date.now();
t0.__t0.buildAll();                       // indexes the require'd corpus
const buildMs = Date.now() - t;
const data = t0.__t0.serialize();
const rows = t0.__t0.state().cursor;      // rows actually indexed

const tables = ["entries", "prefix", "fprefix", "fskel", "area", "geo"];
const bytes = tables.reduce((n, k) => n + JSON.stringify(data[k]).length, 0);
const N = Math.max(1, Math.ceil(bytes / CHUNK_TARGET));
/* contiguous, byte-balanced shards per table — equal-count slicing makes
   early chunks obese (hot prefixes carry 80-id posting lists); cut each
   table where its running serialized size crosses tableBytes/N */
const shardBytes = (arr) => {
  const lens = arr.map((x) => JSON.stringify(x).length);
  const target = lens.reduce((a, b) => a + b, 0) / N;
  const shards = [];
  let start = 0, acc = 0;
  for (let i = 0; i < arr.length; i++) {
    acc += lens[i];
    if (acc >= target && shards.length < N - 1) {
      shards.push(arr.slice(start, i + 1));
      start = i + 1;
      acc = 0;
    }
  }
  shards.push(arr.slice(start));
  while (shards.length < N) shards.push([]);
  return shards;
};
const shards = Object.fromEntries(tables.map((k) => [k, shardBytes(data[k])]));

const TMP = `${OUT_DIR}.tmp`;
rmSync(TMP, { recursive: true, force: true });
mkdirSync(TMP, { recursive: true });

writeFileSync(path.join(TMP, "manifest.json"),
  JSON.stringify({ v: 1, gaz_sha256: sha, gaz_rows: rows, chunks: N }));

for (let i = 0; i < N; i++) {
  writeFileSync(path.join(TMP, `c${i}.json`), JSON.stringify({
    e: shards.entries[i],
    p: shards.prefix[i],
    fp: shards.fprefix[i],
    fs: shards.fskel[i],
    a: shards.area[i],
    g: shards.geo[i],
  }));
}

/* dispatch module — the switch keeps every require() literal so Metro
   statically bundles all chunks, while only the requested case's JSON
   module factory (its parse) runs at load time */
const cases = [...Array(N).keys()]
  .map((i) => `      case ${i}: return require("./c${i}.json");`)
  .join("\n");
writeFileSync(path.join(TMP, "chunks.js"),
`// GENERATED by scripts/build-t0-index.mjs — do not edit.
// Regenerate after any gazetteer change: cd Mobile && npm run build:t0
module.exports = {
  v: 1,
  gaz_sha256: ${JSON.stringify(sha)},
  gaz_rows: ${rows},
  chunks: ${N},
  load(i) {
    switch (i) {
${cases}
      default: return null;
    }
  },
};
`);

rmSync(OUT_DIR, { recursive: true, force: true });
renameSync(TMP, OUT_DIR);

let total = 0;
for (let i = 0; i < N; i++) total += statSync(path.join(OUT_DIR, `c${i}.json`)).size;
console.log(`t0-index: ${rows.toLocaleString()} rows → ${OUT_DIR}/ (${N} chunks, ${(total / 1e6).toFixed(1)} MB)`);
console.log(`built via t0.__t0 in ${buildMs} ms, sha ${sha.slice(0, 12)}…`);
