/// <reference types="node" />
/**
 * tileWarm — the offline basemap pack must hand MapLibre a fetchable
 * http(s) style URL (docs/lanes/offline-walk-report.md: the file://
 * style_url made Android's Mbgl-HttpRequest reject the fetch, region row
 * created with 0 tiles). These cases pin:
 *
 *   - createPack gets `${API_BASE}/v2-light.json`, never file://
 *   - the legacy r1 pack (dead file:// region row) is deleted on sight
 *   - pack rev bumped to r2 so a stored r1 row can't shadow the fix
 *   - warming is skipped for non-bundled styles (env/pmtiles overrides)
 *   - warming is skipped when the API base isn't http(s)
 *   - all native failures stay silent (map streams online like before)
 *
 * Module state (`started`) latches per launch, so each case imports a
 * fresh tileWarm via a ?case=N query — the runner's resolve hook treats
 * it as a distinct module and gives it fresh stub globals.
 *
 * Run: cd Mobile && node src/offline/test-runner.mjs
 */
import { describe, it, beforeEach } from "node:test";
import assert from "node:assert/strict";

type MlState = {
  packs: Record<string, unknown>[];
  created: Record<string, unknown>[];
  deleted: string[];
  maxAmbient: number | null;
  failCreate?: boolean;
};

const ml = () =>
  ((globalThis as Record<string, unknown>).__offtest_ml ??= {
    packs: [],
    created: [],
    deleted: [],
    maxAmbient: null,
  }) as MlState;

const BUNDLED = () =>
  (globalThis as Record<string, unknown>).__offtest_v2style;

let caseN = 0;
/** Fresh tileWarm module per case — isolated `started`, stubs re-read
 *  the current globals. */
const loadWarm = async () =>
  (await import(`../map/tileWarm.ts?case=${++caseN}`)) as {
    warmBasemap: (style: unknown) => void;
  };

/** Spin micro/macrotasks until the fire-and-forget warm() settles. */
async function settled(): Promise<void> {
  for (let i = 0; i < 25; i++) await new Promise((r) => setImmediate(r));
}

beforeEach(() => {
  (globalThis as Record<string, unknown>).__offtest_ml = {
    packs: [],
    created: [],
    deleted: [],
    maxAmbient: null,
  };
  (globalThis as Record<string, unknown>).__offtest_api_base = "http://api.test";
});

describe("tileWarm — fetchable pack style (offline-walk fix)", () => {
  it("creates the r2 pack over http(s) and deletes the dead r1 row", async () => {
    ml().packs = [
      { id: "uuid-r1", metadata: { name: "delhi-ncr-z9-13-r1" } },
    ];
    const { warmBasemap } = await loadWarm();
    warmBasemap(BUNDLED());
    await settled();

    const spec = ml().created[0] as Record<string, unknown>;
    assert.equal(spec.mapStyle, "http://api.test/v2-light.json");
    assert.match(String(spec.mapStyle), /^https?:\/\//);
    assert.doesNotMatch(String(spec.mapStyle), /file:\/\//);
    assert.deepEqual(spec.bounds, [76.8, 28.2, 77.9, 28.95]);
    assert.equal(spec.minZoom, 9);
    assert.equal(spec.maxZoom, 13);
    assert.deepEqual(spec.metadata, { name: "delhi-ncr-z9-13-r2" });
    assert.deepEqual(ml().deleted, ["uuid-r1"]);
    assert.equal(ml().maxAmbient, 160 * 1024 * 1024);
  });

  it("fires once per launch even if the map idles repeatedly", async () => {
    const { warmBasemap } = await loadWarm();
    warmBasemap(BUNDLED());
    warmBasemap(BUNDLED());
    warmBasemap(BUNDLED());
    await settled();
    assert.equal(ml().created.length, 1);
  });

  it("skips non-bundled styles — an env/pmtiles override warms no pack", async () => {
    const { warmBasemap } = await loadWarm();
    warmBasemap({ version: 8, sources: { openmaptiles: { url: "pmtiles://…" } } });
    warmBasemap("https://styles.example/x.json");
    await settled();
    assert.equal(ml().created.length, 0);
  });

  it("skips when the API base isn't http(s)", async () => {
    (globalThis as Record<string, unknown>).__offtest_api_base = "";
    const { warmBasemap } = await loadWarm();
    warmBasemap(BUNDLED());
    await settled();
    assert.equal(ml().created.length, 0);
  });

  it("an existing r2 pack is resumed, not re-created", async () => {
    let resumed = 0;
    ml().packs = [
      {
        id: "uuid-r2",
        metadata: { name: "delhi-ncr-z9-13-r2" },
        status: async () => ({ state: "inactive", percentage: 40 }),
        resume: async () => {
          resumed++;
        },
      },
    ];
    const { warmBasemap } = await loadWarm();
    warmBasemap(BUNDLED());
    await settled();
    assert.equal(ml().created.length, 0);
    assert.equal(resumed, 1);
  });

  it("createPack failure stays silent — the online map is unaffected", async () => {
    ml().failCreate = true;
    const { warmBasemap } = await loadWarm();
    warmBasemap(BUNDLED());
    await settled(); // must not throw / unhandled-reject
    assert.equal(ml().created.length, 0);
    assert.equal(ml().maxAmbient, 160 * 1024 * 1024);
  });
});
