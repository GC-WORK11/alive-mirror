/// <reference types="node" />
/**
 * Offline-pill debounce (component-audit #24): one dropped request used
 * to flip "offline — showing last known air" on a healthy connection.
 * The pill must hold its tongue until FAILS_BEFORE_OFFLINE consecutive
 * failures, recover on the next "up", and re-probe once at the moment
 * it changes state.
 *
 * Each case imports a fresh status.ts via the runner's ?case=N cache
 * bust, and the /health probe is stubbed so nothing touches a socket.
 *
 * Run: cd Mobile && node src/offline/test-runner.mjs
 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";

type StatusModule = typeof import("./status");
let caseN = 0;
async function freshStatus(): Promise<{ m: StatusModule; probes: { n: number } }> {
  const m = (await import(`./status.ts?case=${++caseN}`)) as StatusModule;
  const probes = { n: 0 };
  m.statusForTest(async () => {
    probes.n += 1;
    return false;
  });
  return { m, probes };
}

describe("net-status debounce — no pill off a single flap", () => {
  it("one or two failed reads stay silent", async () => {
    const { m, probes } = await freshStatus();
    m.handleNetEvent({ type: "down" });
    assert.equal(m.statusForTest().state, "online");
    m.handleNetEvent({ type: "down" });
    assert.equal(m.statusForTest().state, "online");
    assert.equal(probes.n, 0, "no probe before the threshold");
  });

  it("the third consecutive failure shows offline and probes once", async () => {
    const { m, probes } = await freshStatus();
    for (let i = 0; i < 3; i++) m.handleNetEvent({ type: "down" });
    const s = m.statusForTest();
    assert.equal(s.state, "offline");
    assert.equal(probes.n, 1, "recovery probe fires exactly once at the flip");
    /* more failures while offline don't spam probes */
    m.handleNetEvent({ type: "down" });
    assert.equal(probes.n, 1);
  });

  it("a stale answer needs the same streak and carries the age", async () => {
    const { m } = await freshStatus();
    m.handleNetEvent({ type: "stale", key: "k", ageS: 812 });
    m.handleNetEvent({ type: "stale", key: "k", ageS: 813 });
    assert.equal(m.statusForTest().state, "online");
    m.handleNetEvent({ type: "stale", key: "k", ageS: 814 });
    const s = m.statusForTest();
    assert.equal(s.state, "stale");
    assert.equal(s.staleAgeS, 814);
  });

  it("any success resets the streak — the next flap starts from zero", async () => {
    const { m } = await freshStatus();
    m.handleNetEvent({ type: "down" });
    m.handleNetEvent({ type: "down" });
    m.handleNetEvent({ type: "up" });
    assert.equal(m.statusForTest().state, "online");
    /* post-recovery, two more failures still don't trip the pill */
    m.handleNetEvent({ type: "down" });
    m.handleNetEvent({ type: "down" });
    assert.equal(m.statusForTest().state, "online");
    m.handleNetEvent({ type: "down" });
    assert.equal(m.statusForTest().state, "offline");
  });
});
