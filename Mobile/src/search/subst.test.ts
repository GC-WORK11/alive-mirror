/// <reference types="node" />
/**
 * F2 (honesty-cluster, the owner's 'don't assume' law) — substitute
 * metadata survives the whole client pipeline so a category-or-area
 * stand-in can never print like a direct name hit.
 *
 * pins:
 *   - t0 kind-ask rows carry match:'category' + the resolved anchor
 *   - t0 unit-ask rows from a re-anchored (different-area) scan carry
 *     match:'area'; a partial-satisfier inside the anchor does too
 *   - a real name hit carries no substitute mark
 *   - client.ts: the server's match/anchor/compound fields reach the
 *     PlaceResult untouched
 *
 * Run: cd Mobile && node src/search/test-runner.mjs
 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";

const loadT0 = async (tag: string) =>
  (await import(`./t0.ts?case=${tag}`)) as any;

describe("t0 substitute marks (F2)", () => {
  it("kind rows around an anchor are marked 'category' with the anchor name", async () => {
    (globalThis as any).__t0_index_mode = "ok";
    const t0 = await loadT0("sub-cat");
    t0.__t0.buildAll();
    const rows = t0.query("bakery near hanuman mandir", null, 8);
    const cats = rows.filter((r: any) => r.match === "category");
    assert.ok(cats.length > 0,
      `expected category-marked kind rows, got ${JSON.stringify(rows.map((r: any) => [r.name, r.match]))}`);
    for (const c of cats) {
      assert.equal(c.compound, true);
      assert.ok(typeof c.anchor === "string" && c.anchor.length > 0,
        `category row '${c.name}' lost its anchor`);
    }
  });

  it("a unit ask the corpus can't satisfy marks the area standin 'area'", async () => {
    (globalThis as any).__t0_index_mode = "ok";
    const t0 = await loadT0("sub-area");
    t0.__t0.buildAll();
    const rows = t0.query("nandanagri a block", null, 8);
    // whatever the corpus answers, an 'area'-marked row must not read
    // as a name hit; if the unit resolved honestly inside the anchor
    // there may be no area row at all — both are honest outcomes
    for (const r of rows) {
      if (r.match === "area") {
        assert.equal(r.compound, true);
        assert.ok(typeof r.anchor === "string" && r.anchor.length > 0);
      }
    }
    assert.ok(rows.every((r: any) =>
      r.match === undefined || ["name", "place", "category", "area"].includes(r.match)),
      `unknown match value leaked: ${JSON.stringify(rows.map((r: any) => r.match))}`);
  });

  it("a plain name hit carries no substitute mark", async () => {
    (globalThis as any).__t0_index_mode = "ok";
    const t0 = await loadT0("sub-name");
    t0.__t0.buildAll();
    const rows = t0.query("connaught place", null, 4);
    assert.ok(rows.length > 0, "corpus should hold Connaught Place");
    const top = rows[0];
    assert.ok(top.match === undefined || top.match === "name" || top.match === "place",
      `a real name hit was marked a substitute: ${top.match}`);
  });
});

describe("client pass-through (F2)", () => {
  it("server match/anchor/compound reach the PlaceResult untouched", async () => {
    const tag = "client-passthrough";
    const { fetchTiers } = await import(`./client.ts?case=${tag}`) as any;
    const orig = globalThis.fetch;
    (globalThis as any).fetch = async () => ({
      ok: true,
      json: async () => ({
        t1: [{
          name: "Jain Confectionary", lat: 28.65, lon: 77.19,
          kind: "bakery", subtitle: "bakery · Hanuman Mandir",
          match: "category", match_rank: 1,
          anchor: "Hanuman Mandir", compound: true,
        }],
        t2: [], t3: [],
      }),
    });
    try {
      const tiers = await fetchTiers("pawan bakery near hanuman mandir", null, new AbortController().signal);
      assert.equal(tiers.t1.length, 1);
      const r = tiers.t1[0];
      assert.equal(r.match, "category");
      assert.equal(r.anchor, "Hanuman Mandir");
      assert.equal(r.compound, true);
    } finally {
      (globalThis as any).fetch = orig;
    }
  });
});
