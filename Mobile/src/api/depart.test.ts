/** depart wire-contract regression — the "ug_saved_vs_now is µg" bug.
 *
 *  The server has always served the leave-later saving as a PERCENT
 *  (server/main.py: round(100*(1-best/now))), once under the misleading
 *  `ug_saved_vs_now` name alone. useShellFlow.remind read it as µg and
 *  recomputed saved/(best.dose+saved) — a served 13% became ~33% in the
 *  scheduled-notification copy (demo-rehearsal §4). The fix: the wire
 *  value is taken VERBATIM — `pct_less_vs_now` is the honest key,
 *  `ug_saved_vs_now` its legacy alias for the same percent.
 *
 *  Run: `node src/api/test-runner.mjs`
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { departSavedPct } from "./depart";

/* What useShellFlow.remind schedules: clamp+round of the SERVED percent —
   never a recompute off the trip dose. Mirrors the call site verbatim. */
const scheduledPct = (d: Parameters<typeof departSavedPct>[0]) =>
  Math.max(0, Math.round(departSavedPct(d) ?? 0));

test("the served percent is taken verbatim — the µg recompute is dead", () => {
  // the rehearsal's live payload shape: best.dose_ug 26.8, saved pct 13
  const pct = scheduledPct({ pct_less_vs_now: 13, ug_saved_vs_now: 13 });
  assert.equal(pct, 13);
  // what the bug produced off the same wire — must never come back
  const deadRecompute = Math.max(0, Math.round(100 * 13 / (26.8 + 13))); // ≈33
  assert.notEqual(pct, deadRecompute);
});

test("ug_saved_vs_now alone (older server) still reads as a percent", () => {
  assert.equal(scheduledPct({ ug_saved_vs_now: 13 }), 13);
});

test("pct_less_vs_now wins when both keys ride the wire", () => {
  assert.equal(departSavedPct({ pct_less_vs_now: 8, ug_saved_vs_now: 13 }), 8);
});

test("null payloads are honest — no fabricated saving", () => {
  assert.equal(departSavedPct(null), null);
  assert.equal(departSavedPct({}), null);
  assert.equal(scheduledPct(null), 0);
});
