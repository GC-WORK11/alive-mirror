#!/usr/bin/env node
/* search-depth eval harness — NOT shipped; dev verification for the
   search lane. 30 real Delhi queries against the SHIPPED chunked index.
   Each row: expected substring → HIT (in top-5) / SUB (category or area
   stand-in leads) / MISS, plus ms. Address-mode queries also report the
   'shops & places here' row count inside 800 m.
   Run: node src/search/eval-search.mjs */
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

const { query, __t0, nearbyPOIs, isBrowseAnchor } = await import("./t0.ts");
{
  const mod = await import(pathToFileURL(
    fileURLToPath(new URL("../../assets/t0-index/chunks.js", import.meta.url)),
  ).href);
  __t0.hydrate(mod.default ?? mod);
}

const LOC = { lat: 28.68, lon: 77.29 }; // Shahdara-ish, owner's turf

/* [query, expected name substring (lower) | null = browse/kind mode] */
const CASES = [
  // — localities & landmarks (name-search mode)
  ["karol bagh", "karol"],
  ["shahdara", "shahdara"],
  ["seelampur", "seelampur"],
  ["laxmi nagar", "laxmi"],
  ["greater kailash", "greater kailash"],
  ["rohini sector 7", "rohini"],
  ["dwarka sector 6", "dwarka"],
  ["chandni chowk", "chandni"],
  ["noida sector 18", "sector 18"],
  ["pitampura", "pitampura"],
  ["india gate", "india gate"],
  ["connaught place", "connaught"],
  ["cp", "connaught"],
  // — exact shops ('type shop → get it')
  ["haldiram", "haldiram"],
  ["nirula", "nirula"],
  ["barista", "barista"],
  ["dominos vikaspuri", "domino"],
  ["jain sweets", "jain"],
  ["agarwal sweets", "agarwal"],
  ["pawan bakery shahdara", "pawan"],
  ["pappu bakery shahdara", "pappu"],
  // — address/area anchors ('type address → see its shops')
  ["gali no 5 bhalswa", null],
  ["ashok nagar shahdara gali no 4", null],
  ["nand nagri block a", null],
  ["vikas marg laxmi nagar", null],
  ["main market rani bagh", null],
  ["khanpur devli road", null],
  // — kind asks near anchors
  ["bakery near hanuman mandir", null],
  ["atm near karol bagh", null],
  ["chemist near seelampur", null],
  // — scorer-prior lane: 15 more real Delhi queries
  ["sarojini nagar market", "sarojini"],
  ["gurudwara bangla sahib", "bangla"],
  ["select citywalk", "citywalk"],
  ["atm near cp", null],
  ["school sector 62 noida", null],
  ["beta 2", "beta"],
  ["alpha 1 greater noida", "alpha"],
  ["chandi chowk", "chandni"],     // typo query — canonical must beat
                                  // Overture's 'Chandini Chowk' rows
  ["chandini chowk", "chandini"], // exact misspelling — canonical first,
                                  // the shop below it
  ["hauz khas", "hauz"],
  ["khan market", "khan"],
  ["lajpat nagar", "lajpat"],
  ["majnu ka tila", "majnu"],
  ["sarai kale khan", "sarai"],
  ["lotus temple", "lotus"],
];

let hits = 0, subs = 0, misses = 0;
console.log("| # | query | top-3 (name · kind) | verdict | ms | here |");
console.log("|---|-------|---------------------|---------|----|----|");
CASES.forEach(([q, want], i) => {
  const t = performance.now();
  const rows = query(q, LOC, 8);
  const ms = performance.now() - t;
  const tops = rows.slice(0, 3)
    .map((r) => `${r.name.slice(0, 26)} · ${r.kind}`)
    .join(" / ");
  let verdict;
  if (want && rows.slice(0, 5).some((r) => r.name.toLowerCase().includes(want))) {
    verdict = "HIT"; hits++;
  } else if (rows[0] && (rows[0].match === "category" || rows[0].match === "area")) {
    verdict = "SUB"; subs++;
  } else if (!rows.length) {
    verdict = "MISS"; misses++;
  } else if (want == null) {
    verdict = "ANS"; hits++;       // browse-mode: any honest answer counts
  } else {
    verdict = "MISS"; misses++;
  }
  const anchor = rows.find((r) => isBrowseAnchor(r.kind));
  const here = anchor ? nearbyPOIs(anchor, 800).length : 0;
  console.log(`| ${i + 1} | ${q} | ${tops} | ${verdict} | ${ms.toFixed(1)} | ${here || "—"} |`);
});
console.log(`\nHIT/ANS ${hits} · SUB ${subs} · MISS ${misses} of ${CASES.length}`);
