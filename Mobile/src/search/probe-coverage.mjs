#!/usr/bin/env node
/* search-coverage lane probe — hydrates the SHIPPED chunked index and
   queries the owner's raw phrases + 10 more he'd plausibly type.
   Run: node src/search/probe-coverage.mjs */
import { registerHooks, createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";

globalThis.__DEV__ = false;
globalThis.require = createRequire(new URL("./x.ts", import.meta.url));

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

const { query } = await import("./t0.ts");
const { parseQuery } = await import("./parse.ts");

{
  const mod = await import(pathToFileURL(
    fileURLToPath(new URL("../../assets/t0-index/chunks.js", import.meta.url)),
  ).href);
  globalThis.__t0_index_mode = "prebuilt";
  const { __t0 } = await import("./t0.ts");
  __t0.hydrate(mod.default ?? mod);
}

const LOC = { lat: 28.68, lon: 77.29 }; // Shahdara-ish, owner's turf

const QUERIES = [
  // — the owner's three verbatim laws —
  "nandanagri a block pocket",
  "ashook nagar shadara gali no 4",
  "pawan bakery near hanuman mandir",
  // — 10 more he'd type —
  "nand nagri b block",
  "ashok nagar gali 4",
  "bakery paas hanuman mandir",
  "mandir near kailash nagar",
  "clinic near ashok nagar shahdara",
  "atta chakki near shiv mandir",
  "e block defence colony",
  "gali no 7 jahangirpuri",
  "sector 62 noida h block",
  "kirana store near bhajanpura",
];

const show = (q, loc = LOC) => {
  const t = Date.now();
  const rows = query(q, loc, 6);
  const ms = Date.now() - t;
  console.log(`\n=== "${q}" (${ms}ms) → ${rows.length} rows`);
  for (const r of rows.slice(0, 5)) {
    const lat = r.lat != null ? r.lat.toFixed(4) : "?";
    const lon = r.lon != null ? r.lon.toFixed(4) : "?";
    console.log(`  ${(r.name || "").slice(0, 46).padEnd(46)} | ${(r.kind || "").padEnd(18)} | ${(r.subtitle || "").slice(0, 38).padEnd(38)} | ${lat},${lon}`);
  }
  return rows;
};

for (const q of QUERIES) {
  const p = parseQuery(q);
  console.log(`\n>>> parse "${q}": toks=${JSON.stringify(p?.toks)} units=${JSON.stringify(p?.units)} kind=${p?.kind} near=${JSON.stringify(p?.near)}`);
  show(q);
}
