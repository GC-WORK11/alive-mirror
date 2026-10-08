/// <reference types="node" />
/**
 * t0 prebuilt index — the index-prebuild lane's pins:
 *
 *   - the shipped assets/t0-index/ matches the bundled gazetteer
 *     byte-for-byte (manifest gaz_sha256) — a stale blob fails here
 *   - query() before the index is ready answers [] and NEVER runs a
 *     synchronous build — the early-typer re-arm is the bug this lane
 *     removes; the corpus isn't even parsed
 *   - the probe loads NO chunk data (a ~8 s monolithic hydrate was the
 *     cold-boot killer — hydration must stay chunked)
 *   - a corrupt index asset falls back to the lazy build, still honest
 *   - the prebuilt path returns IDENTICAL results to the lazy build —
 *     same data, same ranking, same nearest-place
 *
 * Run: cd Mobile && node src/search/test-runner.mjs
 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";

const MOBILE = new URL("../../", import.meta.url);
const GAZ = fileURLToPath(new URL("assets/delhi-gazetteer.json", MOBILE));
const IDX_DIR = fileURLToPath(new URL("assets/t0-index/", MOBILE));
const CHUNKS_JS = fileURLToPath(new URL("assets/t0-index/chunks.js", MOBILE));

const LOC = { lat: 28.68, lon: 77.29 }; // Shahdara-ish — test-t0.mjs's anchor
const PIN = { lat: 28.6517, lon: 77.2215 };

/** exercise name/fold/unit/near/kind/miss paths alike */
const QUERIES = [
  "karol bagh", "india gate", "ashok nagar shahdara gali no 4",
  "ashook nagar shadara gali no 4", "nandanagri a block pocket something",
  "nand nagri block a", "bakery near hanuman mandir",
  "pawan bakery near hanuman mandir", "gali no 5 bhalswa",
  "connaught place", "cp", "atm near karol bagh",
  "zyxwv nonsense placename", "seelampur", "gali",
];

const loadT0 = async (tag: string) =>
  (await import(`./t0.ts?case=${tag}`)) as any;

describe("t0 prebuilt index", () => {
  it("freshness: manifest sig matches the bundled gazetteer + chunks are whole", async () => {
    const manifest = JSON.parse(readFileSync(`${IDX_DIR}manifest.json`, "utf8"));
    const gazBytes = readFileSync(GAZ);
    const sha = createHash("sha256").update(gazBytes).digest("hex");
    assert.equal(manifest.v, 1, "index format version");
    assert.equal(manifest.gaz_sha256, sha,
      "t0-index is stale vs delhi-gazetteer.json — run npm run build:t0");
    const gazRows = (JSON.parse(gazBytes.toString("utf8")) as unknown[]).length;
    assert.equal(manifest.gaz_rows, gazRows);
    assert.ok(manifest.chunks > 0);
    // every chunk the manifest promises exists on disk and is well-shaped
    let entries = 0;
    for (let i = 0; i < manifest.chunks; i++) {
      const c = JSON.parse(readFileSync(`${IDX_DIR}c${i}.json`, "utf8"));
      for (const t of ["e", "p", "fp", "fs", "a", "g"])
        assert.ok(Array.isArray(c[t]), `c${i}.${t}`);
      entries += c.e.length;
    }
    assert.ok(entries > 0 && entries <= gazRows);
    // the generated dispatch really does lazy literal requires
    const mod = (await import(pathToFileURL(CHUNKS_JS).href)) as any;
    const real = mod.default ?? mod;
    assert.equal(real.v, 1);
    assert.equal(real.chunks, manifest.chunks);
    assert.equal(real.gaz_sha256, sha);
    for (const t of ["e", "p", "fp", "fs", "a", "g"]) {
      assert.ok(Array.isArray(real.load(0)[t]), `load(0).${t}`);
      assert.ok(Array.isArray(real.load(manifest.chunks - 1)[t]), `load(${manifest.chunks - 1}).${t}`);
    }
    assert.equal(real.load(manifest.chunks), null);
  });

  it("early query: honest miss, never a synchronous build, probe reads no chunks", async () => {
    (globalThis as any).__t0_index_mode = "ok";
    const t0 = await loadT0("early");
    const t = Date.now();
    assert.deepEqual(t0.query("co", LOC, 8), []);
    assert.ok(Date.now() - t < 500,
      "query() must not park on index work");
    const st = t0.__t0.state();
    assert.equal(st.built, false);
    assert.equal(st.prebuilt, "ok",
      "probe resolves the asset question — cheap, no chunk data");
    assert.equal(st.rawLoaded, false,
      "the early query must not even parse the raw corpus");
    assert.equal(st.hchunk, 0, "no chunk hydrated on the query path");
    let fired = 0;
    t0.onIndexReady(() => fired++);
    t0.__t0.buildAll();
    assert.equal(fired, 1, "queued listener fires exactly once on ready");
    assert.equal(t0.__t0.state().loadedFrom, "lazy");
    assert.ok(t0.query("karol bagh", LOC, 8).length > 0);
  });

  it("corrupt asset: falls back to the lazy build, never throws", async () => {
    (globalThis as any).__t0_index_mode = "corrupt";
    const t0 = await loadT0("corrupt");
    assert.deepEqual(t0.query("co", LOC, 8), []);
    assert.equal(t0.__t0.state().prebuilt, "failed");
    t0.__t0.buildAll();
    assert.equal(t0.__t0.state().loadedFrom, "lazy");
    assert.ok(t0.query("karol bagh", LOC, 8).length > 0);
  });

  it("missing asset: require throws → lazy build, still honest", async () => {
    (globalThis as any).__t0_index_mode = "missing";
    const t0 = await loadT0("missing");
    assert.deepEqual(t0.query("co", LOC, 8), []);
    assert.equal(t0.__t0.state().prebuilt, "failed");
    t0.__t0.buildAll();
    assert.equal(t0.__t0.state().loadedFrom, "lazy");
    assert.ok(t0.query("karol bagh", LOC, 8).length > 0);
  });

  it("prebuilt hydrate: identical results to the lazy build", async () => {
    (globalThis as any).__t0_index_mode = "missing";
    const lazy = await loadT0("lazy");
    lazy.__t0.buildAll();
    (globalThis as any).__t0_index_mode = "ok";
    const pre = await loadT0("pre");
    // hydrate via the REAL generated dispatch — import() loads chunks.js
    // natively, exercising the same module Metro bundles
    const mod = (await import(pathToFileURL(CHUNKS_JS).href)) as any;
    pre.__t0.hydrate(mod.default ?? mod);
    assert.equal(pre.__t0.state().loadedFrom, "prebuilt");
    assert.equal(pre.__t0.state().built, true);
    for (const q of QUERIES)
      assert.deepEqual(pre.query(q, LOC, 8), lazy.query(q, LOC, 8), q);
    assert.deepEqual(pre.nearestPlace(PIN), lazy.nearestPlace(PIN));
  });
});
