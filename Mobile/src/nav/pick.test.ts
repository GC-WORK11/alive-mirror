/// <reference types="node" />
/**
 * nav-start-pick: a compare-sheet pick must survive a /v2/plan payload
 * swap — server route_ids are per-call UUIDs (server/v2/store.py), so
 * preserving selection by route_id reset every pick to the recommended
 * card the moment the full plan landed; Start then launched it.
 *
 *   cd Mobile && node src/nav/test-runner.mjs
 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { preserveIdx, sameOption } from "../components/shell/types";
import type { V2Option } from "../components/shell/types";

const opt = (mode: string, extra: Partial<V2Option> = {}): V2Option => ({
  mode,
  vehicle: mode,
  label: mode,
  eta_s: 600,
  duration_min: 10,
  distance_km: 8,
  dose: { lo: null, mid: null, hi: null },
  emissions: { co2_kg: null },
  tag: null,
  recommended: false,
  reason_line: "",
  geometry: null,
  ...extra,
});

describe("sameOption — identity across plan responses", () => {
  it("same logical option matches despite fresh route_id + moved eta/dose", () => {
    const a = opt("metro+walk", {
      route_id: "uuid-callA", stations: { board: "Rajiv Chowk", alight: "Nehru Place" },
      dose: { lo: 10, mid: 20, hi: 30 }, eta_s: 1200,
    });
    const b = opt("metro+walk", {
      route_id: "uuid-callB", stations: { board: "Rajiv Chowk", alight: "Nehru Place" },
      dose: { lo: 11, mid: 22, hi: 33 }, eta_s: 1320, recommended: true, tag: "lightest for you",
    });
    assert.ok(sameOption(a, b));
  });

  it("corridor alternatives of one mode stay distinct (via_names + index)", () => {
    const ring = opt("car", { alternative_index: 1, via_names: ["Ring Rd"] });
    const outer = opt("car", { alternative_index: 2, via_names: ["Outer Ring Rd"] });
    assert.ok(!sameOption(ring, outer));
    assert.ok(!sameOption(opt("car"), ring)); // primary vs alternative
  });

  it("different transit legs are different options", () => {
    const a = opt("metro+walk", { stations: { board: "A", alight: "B" } });
    const b = opt("metro+walk", { stations: { board: "A", alight: "C" } });
    assert.ok(!sameOption(a, b));
  });
});

describe("preserveIdx — the swap keeps the pick, else the recommended default", () => {
  /* engine-first paint vs the full plan: same logical rows, every
     route_id freshly minted — the exact swap the flag came through */
  const engineRows = [
    opt("car", { route_id: "uA1", engine: "alive_core-path", recommended: true }),
    opt("bike", { route_id: "uA2", engine: "alive_core-path" }),
  ];
  const fullRows = [
    opt("car", { route_id: "uB1", engine: "alive_core-path", recommended: true }),
    opt("metro+walk", { route_id: "uB2", stations: { board: "Rajiv Chowk", alight: "Nehru Place" } }),
    opt("bike", { route_id: "uB3", engine: "alive_core-path" }),
    opt("bus", { route_id: "uB4" }),
  ];

  it("pick-bike during refining → still bike after the full plan lands", () => {
    assert.equal(preserveIdx(engineRows[1], fullRows), 2);
  });

  it("no pick → 0: Start follows the recommended card (unchanged default)", () => {
    assert.equal(preserveIdx(undefined, fullRows), 0);
    assert.equal(fullRows[0].recommended, true);
  });

  it("pick whose option is gone from the new set → recommended default", () => {
    assert.equal(preserveIdx(opt("cycle", { route_id: "uA9" }), fullRows), 0);
  });

  it("re-plan keeps a transit pick (vehicle answer / retry swap)", () => {
    const firstPlan = [
      opt("car", { route_id: "uC1", recommended: true }),
      opt("metro+walk", { route_id: "uC2", stations: { board: "Rajiv Chowk", alight: "Nehru Place" } }),
    ];
    const secondPlan = [
      opt("car", { route_id: "uD1", recommended: true }),
      opt("metro+walk", { route_id: "uD2", stations: { board: "Rajiv Chowk", alight: "Nehru Place" } }),
      opt("auto", { route_id: "uD3" }),
    ];
    assert.equal(preserveIdx(firstPlan[1], secondPlan), 1);
  });
});
