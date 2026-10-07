/// <reference types="node" />
/**
 * least-smoke honesty (component-audit #22): the engine names its
 * "least-smoke" family against ITS primary, not against the same-mode
 * rows the compare sheet displays — so '· least-smoke alt 1' used to
 * sit on a 34.4 µg row while a 26.0 µg sibling looked ordinary. The
 * client re-derives the claim: a qualifier only survives on the row
 * whose displayed dose.mid is the group's minimum; every other member
 * degrades to the factual '· alt N'.
 *
 * Run: cd Mobile && node src/api/test-runner.mjs
 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { mapPlan } from "./plan";

const opt = (mode: string, label: string, mid: number) => ({
  mode,
  label,
  eta_s: 900,
  dose: { lo: mid - 2, mid, hi: mid + 8 },
});
const labels = (r: ReturnType<typeof mapPlan>) => r.options.map((o) => o.label);

describe("relabelLeastSmoke — the qualifier only sits on the true lightest", () => {
  it("strips 'least-smoke' from a row measurably smokier than the plain one", () => {
    /* the audit's live payload: engine called the 0.8 µg alt least-smoke
       while the plain Car row displayed 0.6 */
    const r = mapPlan({
      options: [
        opt("car", "Car (AC)", 0.6),
        opt("car", "Car (AC) · least-smoke rd", 0.8),
        opt("car", "Car (AC) · least-smoke alt 1", 1.1),
      ],
    });
    assert.deepEqual(labels(r), ["Car (AC)", "Car (AC) · alt 1", "Car (AC) · alt 2"]);
  });

  it("keeps the qualifier on the group's real minimum (live CP→Lajpat values)", () => {
    const r = mapPlan({
      options: [
        opt("cycle", "Bicycle", 71),
        opt("cycle", "Bicycle · least-smoke rd", 55),
        opt("cycle", "Bicycle · least-smoke alt 1", 62),
        opt("cycle", "Bicycle · least-smoke alt 2", 65),
      ],
    });
    assert.deepEqual(labels(r), [
      "Bicycle",
      "Bicycle · least-smoke rd",
      "Bicycle · alt 1",
      "Bicycle · alt 2",
    ]);
  });

  it("display-precision ties keep the qualifier (0.05 eps)", () => {
    const r = mapPlan({
      options: [
        opt("car", "Car (AC)", 0.60),
        opt("car", "Car (AC) · least-smoke rd", 0.63),
      ],
    });
    assert.equal(r.options[1].label, "Car (AC) · least-smoke rd");
  });

  it("a qualified row with no displayed dose can't prove the claim — demoted", () => {
    const r = mapPlan({
      options: [
        opt("auto", "Auto-rickshaw", 18),
        { mode: "auto", label: "Auto-rickshaw · least-smoke rd", eta_s: 900 },
        opt("auto", "Auto-rickshaw · alt 1", 15),
      ],
    });
    assert.equal(r.options[1].label, "Auto-rickshaw · alt 1");
  });

  it("a group with no doses at all leaves the wire as-is", () => {
    const r = mapPlan({
      options: [
        { mode: "walk", label: "On foot · least-smoke rd", eta_s: 900 },
        { mode: "walk", label: "On foot · least-smoke alt 1", eta_s: 960 },
      ],
    });
    assert.deepEqual(labels(r), ["On foot · least-smoke rd", "On foot · least-smoke alt 1"]);
  });
});
