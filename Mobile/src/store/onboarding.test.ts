/// <reference types="node" />
/**
 * One-time flag persistence — onboarding-gate lane.
 *
 * The owner hit "onboarding comes every time" on the real app. Two wound
 * classes these tests pin:
 *  1. the seen-flag must round-trip disk — `seen:true` written once is
 *     honored on every later load (a relaunch is simulated by dropping
 *     the module's in-memory mirror).
 *  2. a torn main file must fall back to .bak — the pre-safefile stores
 *     did a raw FILE.write; a kill mid-write left a file that parsed as
 *     garbage and read as never-seen on every subsequent launch.
 *
 * Run: cd Mobile && node src/store/test-runner.mjs
 */
import { describe, it, beforeEach } from "node:test";
import assert from "node:assert/strict";
import {
  loadConsent, saveConsent, clearConsent, resetConsentCache,
} from "./consent";
import {
  loadWelcomeSeen, markWelcomeSeen, clearWelcomeSeen, resetWelcomeCache,
} from "./welcome";
import {
  loadTourSeen, markTourSeen, clearTourSeen, resetTourCache,
} from "./tour";
import { purgeJsonDoc } from "./safefile";

const DOCS = "/storetest-docs";
/* the test-runner's expo-file-system stub keeps its "disk" in this map —
   plant/corrupt files directly for the .bak fallback case */
const fsMap = (): Map<string, string> =>
  (globalThis as { __storetest_fs?: Map<string, string> }).__storetest_fs ??
  new Map<string, string>();

describe("consent flag — one-time is one-time", () => {
  beforeEach(() => {
    resetConsentCache();
    purgeJsonDoc("consent.json");
    resetConsentCache();
  });

  it("fresh install reads unseen", async () => {
    const c = await loadConsent();
    assert.equal(c.seen, false);
    assert.equal(c.sharing, null);
  });

  it("seen:true written once survives a relaunch", async () => {
    await saveConsent({ seen: true, sharing: "off", ts: 1 });
    resetConsentCache();                  // drop the mirror — re-reads disk
    const c = await loadConsent();
    assert.equal(c.seen, true);
    assert.equal(c.sharing, "off");
    assert.equal(c.ts, 1);
  });

  it("a sharing-only save never clobbers seen", async () => {
    /* the onboarding write path: consent tap saves {seen:true,...}, then
       patchSettings mirrors {sharing, ts} — seen must survive the merge */
    await saveConsent({ seen: true, sharing: "off", ts: 1 });
    await saveConsent({ sharing: "on", ts: 2 });
    resetConsentCache();
    const c = await loadConsent();
    assert.equal(c.seen, true);
    assert.equal(c.sharing, "on");
    assert.equal(c.ts, 2);
  });

  it("concurrent saves serialize — seen lands and stays", async () => {
    await Promise.all([
      saveConsent({ seen: true, sharing: "on", ts: 3 }),
      saveConsent({ sharing: "off", ts: 4 }),
    ]);
    resetConsentCache();
    const c = await loadConsent();
    assert.equal(c.seen, true);
    assert.equal(c.ts, 4);                // last-state-wins on the merged file
  });

  it("a torn main falls back to .bak — no replay on corrupt disk", async () => {
    /* write a real record, snapshot the good generation to .bak (what
       writeJsonDoc does on the NEXT write), then corrupt main — the old
       raw-write store read this as never-seen forever */
    await saveConsent({ seen: true, sharing: "on", ts: 5 });
    const m = fsMap();
    m.set(`${DOCS}/consent.json.bak`, m.get(`${DOCS}/consent.json`)!);
    m.set(`${DOCS}/consent.json`, '{"seen":tr');   // torn mid-write
    resetConsentCache();
    const c = await loadConsent();
    assert.equal(c.seen, true);
    assert.equal(c.sharing, "on");
  });

  it("a save queued across delete-my-data is dropped whole", async () => {
    /* audit-3: saveConsent's merge body ran on writeTail AFTER a wipe —
       loadConsent repopulated mem (EMPTY) so `mem === null` never fired
       and the stale patch (seen:true, sharing:"on") resurrected the
       file. The generation is now captured at CALL time. */
    const p = saveConsent({ seen: true, sharing: "on", ts: 9 });
    clearConsent();                       // wipe lands before the merge body
    await p;
    const m = fsMap();
    assert.equal(m.has(`${DOCS}/consent.json`), false);
    const c = await loadConsent();
    assert.equal(c.seen, false);
    assert.equal(c.sharing, null);
  });

  it("clearConsent wipes the file and re-arms the gate", async () => {
    await saveConsent({ seen: true, sharing: "on", ts: 6 });
    clearConsent();
    const m = fsMap();
    assert.equal(m.has(`${DOCS}/consent.json`), false);
    assert.equal(m.has(`${DOCS}/consent.json.bak`), false);
    assert.equal(m.has(`${DOCS}/consent.json.tmp`), false);
    const c = await loadConsent();
    assert.equal(c.seen, false);
  });
});

describe("welcome + coach-tour flags — same one-time rule", () => {
  beforeEach(() => {
    clearWelcomeSeen();
    resetWelcomeCache();
    clearTourSeen();
    resetTourCache();
  });

  it("welcome_seen_v1 persists across relaunch", async () => {
    assert.equal(await loadWelcomeSeen(), false);
    await markWelcomeSeen();
    resetWelcomeCache();
    assert.equal(await loadWelcomeSeen(), true);
  });

  it("coach_tour_seen_v1 persists across relaunch", async () => {
    assert.equal(await loadTourSeen(), false);
    await markTourSeen();
    resetTourCache();
    assert.equal(await loadTourSeen(), true);
  });

  it("clears re-arm both flags on wipe", async () => {
    await markWelcomeSeen();
    await markTourSeen();
    clearWelcomeSeen();
    clearTourSeen();
    resetWelcomeCache();
    resetTourCache();
    assert.equal(await loadWelcomeSeen(), false);
    assert.equal(await loadTourSeen(), false);
  });
});
