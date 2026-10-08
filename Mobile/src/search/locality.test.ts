/// <reference types="node" />
/**
 * localityAt — the ambient hero's 'read near <locality>' caption source
 * (precision-audit lane: the owner's repeated ask was a place NAME at his
 * precision demand, not 'your location').
 *
 * pins:
 *   - a real Delhi fix names a real gazetteer locality (areaNear's
 *     weight-minus-distance pick — the same rule search subtitles use)
 *   - beyond locality reach and outside NCR it answers null, never a guess
 *   - index not ready -> null and NO synchronous build (the early-typer
 *     rule every t0 reader shares)
 *
 * Run: cd Mobile && node src/search/test-runner.mjs
 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";

const loadT0 = async (tag: string) =>
  (await import(`./t0.ts?case=${tag}`)) as any;

describe("localityAt", () => {
  it("names the locality a real Delhi fix sits in", async () => {
    (globalThis as any).__t0_index_mode = "ok";
    const t0 = await loadT0("loc-name");
    t0.__t0.buildAll();
    // Karol Bagh's market heart — the worked example in the lane brief
    const n = t0.localityAt({ lat: 28.6517, lon: 77.1907 });
    assert.ok(
      typeof n === "string" && n.length > 0,
      `expected a locality name, got ${n}`,
    );
  });

  it("answers null beyond locality reach — never a guess", async () => {
    (globalThis as any).__t0_index_mode = "ok";
    const t0 = await loadT0("loc-null");
    t0.__t0.buildAll();
    assert.equal(t0.localityAt({ lat: 26.5, lon: 77.9 }), null);
    assert.equal(t0.localityAt({ lat: 51.5, lon: -0.12 }), null);
  });

  it("index not ready -> null, no sync build", async () => {
    (globalThis as any).__t0_index_mode = "ok";
    const t0 = await loadT0("loc-cold");
    assert.equal(t0.localityAt({ lat: 28.65, lon: 77.19 }), null);
    const st = t0.__t0.state();
    assert.equal(st.hchunk, 0, "no chunk hydrated on the null path");
  });
});
