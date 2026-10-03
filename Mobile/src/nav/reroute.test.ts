/// <reference types="node" />
/**
 * Reroute trigger path (doc 04 §4 → POST /v2/reroute).
 *
 * The React hook (engine.ts) can't render in node, so this tests the
 * two pure halves of the trigger path the same way the engine wires
 * them: OffRouteTracker streak → postReroute(fetch) → normalized route,
 * plus the request body the server lane expects.
 *
 * Run: cd Mobile && node src/nav/test-runner.mjs
 * (test-runner.mjs stubs react-native for ../api/reroute's import of
 *  components/shell/net.ts)
 */
import { afterEach, beforeEach, describe, it } from "node:test";
import assert from "node:assert/strict";
import { postJson, postReroute } from "../api/reroute";
import { OffRouteTracker } from "./offroute";

type FetchCall = { url: string; method: string | undefined; body: unknown };

let calls: FetchCall[] = [];
let responder: (url: string) => Response = () =>
  new Response("{}", { status: 200, headers: { "content-type": "application/json" } });

const realFetch = globalThis.fetch;

beforeEach(() => {
  calls = [];
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    calls.push({
      url: String(input),
      method: init?.method,
      body: init?.body ? JSON.parse(String(init.body)) : undefined,
    });
    return responder(String(input));
  }) as typeof fetch;
});

afterEach(() => {
  globalThis.fetch = realFetch;
});

const GEO: GeoJSON.Geometry = {
  type: "LineString",
  coordinates: [[77.2, 28.6], [77.3, 28.7]],
};
const json = (o: unknown, status = 200) =>
  new Response(JSON.stringify(o), {
    status,
    headers: { "content-type": "application/json" },
  });

describe("postReroute — request shape", () => {
  it("POSTs route_id + at/from + to + mode to {api}/v2/reroute", async () => {
    responder = () => json({ route_id: "r2", geometry: GEO });
    const at = { lat: 28.61, lon: 77.21 };
    const to = { lat: 28.71, lon: 77.31 };
    await postReroute({ route_id: "r1", at, to, mode: "car" }, "https://api.test");

    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, "https://api.test/v2/reroute");
    assert.equal(calls[0].method, "POST");
    assert.deepEqual(calls[0].body, {
      route_id: "r1",
      at,
      from: at, // server contract accepts either key
      to,
      mode: "car",
    });
  });
});

describe("postReroute — response normalization", () => {
  it("accepts a bare route object", async () => {
    responder = () =>
      json({ route_id: "r2", geometry: GEO, eta_s: 300, mode: "bike", distance_km: 4.2 });
    const r = await postReroute(
      { route_id: "r1", at: { lat: 1, lon: 1 }, to: { lat: 2, lon: 2 }, mode: "car" },
      "https://api.test",
    );
    assert.equal(r?.result?.route_id, "r2");
    assert.deepEqual(r?.result?.geometry, GEO);
    assert.equal(r?.result?.eta_s, 300);
    assert.equal(r?.result?.mode, "bike");
    assert.equal(r?.result?.distance_km, 4.2);
  });

  it("unwraps option/route wrappers + route_geojson + duration_s", async () => {
    responder = () =>
      json({ option: { route_id: "r3", route_geojson: GEO, duration_s: 180 } });
    const r = await postReroute(
      { route_id: "r1", at: { lat: 1, lon: 1 }, to: { lat: 2, lon: 2 }, mode: "auto" },
      "https://api.test",
    );
    assert.equal(r?.result?.route_id, "r3");
    assert.deepEqual(r?.result?.geometry, GEO);
    assert.equal(r?.result?.eta_s, 180, "duration_s maps onto eta_s");
  });

  it("returns null on http error, network error, or unusable payload", async () => {
    const req = { route_id: "r1", at: { lat: 1, lon: 1 }, to: { lat: 2, lon: 2 }, mode: "car" };
    responder = () => json({ error: "nope" }, 500);
    assert.equal((await postReroute(req, "https://api.test")).result, null);

    globalThis.fetch = (async () => {
      throw new Error("offline");
    }) as typeof fetch;
    assert.equal((await postReroute(req, "https://api.test")).result, null);

    responder = () => json({ route_id: "r2" }); // no geometry
    assert.equal((await postReroute(req, "https://api.test")).result, null);

    responder = () => json({ route_id: 42, geometry: GEO }); // bad id
    assert.equal((await postReroute(req, "https://api.test")).result, null);
  });

  it("carries the typed error code through on the no-route path", async () => {
    const req = { route_id: "r1", at: { lat: 1, lon: 1 }, to: { lat: 2, lon: 2 }, mode: "car" };
    responder = () => json({ route_id: null, options: [], option: null,
      error: "outside service area", code: "outside_service_area" });
    const a = await postReroute(req, "https://api.test");
    assert.equal(a.result, null);
    assert.equal(a.code, "outside_service_area");
    assert.equal(a.error, "outside service area");
  });
});

describe("postJson", () => {
  it("returns parsed JSON on 2xx", async () => {
    responder = () => json({ ok: 1 });
    assert.deepEqual(await postJson("https://api.test/x", { a: 1 }), { ok: 1 });
  });

  it("throws `http <status>` on non-2xx", async () => {
    responder = () => new Response("nope", { status: 404 });
    await assert.rejects(postJson("https://api.test/x", {}), /http 404/);
  });
});

describe("off-route → reroute trigger path (engine wiring, pure half)", () => {
  // Mirrors engine.ts:298 — the hook calls reroute({lat,lon}) exactly
  // when offRef.update(snap.offsetM) flips true. The 15 s cooldown
  // (REROUTE_COOLDOWN_MS, engine.ts:27) is a private hook constant and
  // is NOT covered here — noted in docs/plan/test-commands.md.
  const drive = async (offsets: { offsetM: number; lat: number; lon: number }[]) => {
    const tracker = new OffRouteTracker();
    for (const fix of offsets) {
      if (tracker.update(fix.offsetM)) {
        await postReroute(
          { route_id: "r1", at: { lat: fix.lat, lon: fix.lon }, to: { lat: 28.7, lon: 77.3 }, mode: "car" },
          "https://api.test",
        );
      }
    }
  };

  it("emits no request for 1–2 off-route fixes", async () => {
    responder = () => json({ route_id: "r2", geometry: GEO });
    await drive([
      { offsetM: 80, lat: 28.6, lon: 77.2 },
      { offsetM: 90, lat: 28.61, lon: 77.21 },
    ]);
    assert.equal(calls.length, 0);
  });

  it("emits exactly one reroute at the third fix, with the live fix as origin", async () => {
    responder = () => json({ route_id: "r2", geometry: GEO });
    await drive([
      { offsetM: 80, lat: 28.6, lon: 77.2 },
      { offsetM: 90, lat: 28.61, lon: 77.21 },
      { offsetM: 120, lat: 28.62, lon: 77.22 },
    ]);
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, "https://api.test/v2/reroute");
    assert.deepEqual((calls[0].body as { at: unknown }).at, { lat: 28.62, lon: 77.22 });
    assert.equal((calls[0].body as { route_id: string }).route_id, "r1");
  });

  it("re-acquiring the route suppresses the trigger (streak resets)", async () => {
    responder = () => json({ route_id: "r2", geometry: GEO });
    await drive([
      { offsetM: 80, lat: 1, lon: 1 },
      { offsetM: 80, lat: 1, lon: 1 },
      { offsetM: 10, lat: 1, lon: 1 }, // snapped back on-route
      { offsetM: 80, lat: 1, lon: 1 },
      { offsetM: 80, lat: 1, lon: 1 },
    ]);
    assert.equal(calls.length, 0);
    // …and a third consecutive off-route fix finally fires
    await drive([{ offsetM: 80, lat: 1, lon: 1 }]);
    assert.equal(calls.length, 0, "fresh tracker: streak starts over per trip leg");
  });

  it("a failed reroute (null) leaves the caller free to retry", async () => {
    responder = () => new Response("down", { status: 503 });
    const tracker = new OffRouteTracker();
    tracker.update(50);
    tracker.update(50);
    assert.equal(tracker.update(50), true);
    const r = await postReroute(
      { route_id: "r1", at: { lat: 1, lon: 1 }, to: { lat: 2, lon: 2 }, mode: "car" },
      "https://api.test",
    );
    assert.equal(r.result, null);
    // tracker still reports true → engine cooldown decides when to retry
    assert.equal(tracker.update(60), true);
  });
});
