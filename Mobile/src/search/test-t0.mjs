#!/usr/bin/env node
/* t0 engine harness — NOT shipped; dev verification for the search lane.
   Run: node src/search/test-t0.mjs */
import { registerHooks, createRequire } from "node:module";

globalThis.__DEV__ = false;
// t0.ts uses Metro's require() for the bundled JSON — give it a real one
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
const { fold, foldName } = await import("./text.ts");

const LOC = { lat: 28.68, lon: 77.29 }; // Shahdara-ish, owner's turf
const show = (q, loc = LOC) => {
  const t = Date.now();
  const rows = query(q, loc, 8);
  console.log(`\n=== "${q}" (${Date.now() - t}ms) → ${rows.length}`);
  for (const r of rows.slice(0, 6))
    console.log(`  ${r.name.slice(0, 52).padEnd(52)} | ${r.kind.padEnd(22)} | ${r.subtitle.slice(0, 40)}`);
};

console.log("fold check:", fold("ashook"), fold("ashok"), "|", fold("shadara"), fold("shahdara"), "|", foldName("nand nagri"), foldName("nandanagri"));
console.log("parse 'ashok nagar shahdara gali no 4':", JSON.stringify(parseQuery("ashok nagar shahdara gali no 4"), null, 0));
console.log("parse 'bakery near hanuman mandir':", JSON.stringify(parseQuery("bakery near hanuman mandir"), null, 0));
console.log("parse 'pawan bakery near hanuman mandir':", JSON.stringify(parseQuery("pawan bakery near hanuman mandir"), null, 0));

show("karol bagh");
show("india gate");
show("ashok nagar shahdara gali no 4");
show("ashook nagar shadara gali no 4");
show("nandanagri a block pocket something");
show("nand nagri block a");
show("bakery near hanuman mandir");
show("pawan bakery near hanuman mandir");
show("gali no 5 bhalswa");
show("connaught place");
show("cp");
show("atm near karol bagh");
show("zyxwv nonsense placename");
show("seelampur");
show("gali");
