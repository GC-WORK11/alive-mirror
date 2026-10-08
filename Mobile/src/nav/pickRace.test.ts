import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { pickTailGate } from "../components/shell/pickGate";

/* pick-race regression (docs/lanes/demo-vid-android-report.md, t104–105 s):
   a tap landed exactly as the results list swapped stale→fresh rows and the
   journey bounced to an EMPTY Where-to. Two mechanisms, two guards:

   1) the pick must commit the identity under the finger at touch-down, not
      whatever row the index-keyed fiber holds at release → SearchScreen's
      pickAtPress capture + the committing latch;
   2) a pick's async tail (dismiss ≤500 ms + posNow ≤9 s) must only steer
      the journey while its own surface is still up → useShellFlow's
      phaseRef/pickSeq guards through pickTailGate. A stale tail writing
      setPhase("search") after compare mounted is what reopened the sheet
      empty. */

const SH = fileURLToPath(new URL("../components/shell/useShellFlow.ts", import.meta.url));
const SC = fileURLToPath(new URL("../screens/SearchScreen.tsx", import.meta.url));
const APP = fileURLToPath(new URL("../../App.tsx", import.meta.url));

test("pickTailGate: 'stay' only while search owns the surface", () => {
  for (const ph of ["search"]) assert.ok(pickTailGate(ph, "stay"));
  for (const ph of ["idle", "compare", "vehicle", "nav", "receipt"])
    assert.equal(pickTailGate(ph, "stay"), false, `${ph} must not take a 'stay' write`);
});

test("pickTailGate: 'advance' tolerates the pick's own direction only", () => {
  assert.ok(pickTailGate("search", "advance"));
  assert.ok(pickTailGate("compare", "advance"));
  for (const ph of ["idle", "vehicle", "nav", "receipt"])
    assert.equal(pickTailGate(ph, "advance"), false,
      `a late advance must not hijack ${ph} (mapPickArmed idle included)`);
});

test("stale pick tail writes nothing; closed surface never reopens", async () => {
  /* replays pick()'s own ordering: capture seq → await the origin fix →
     bail when superseded → surface-gate every remaining write. This is
     the state machine the fix installs, driven through the real gate. */
  let pickSeq = 0;
  let phase = "search";
  const writes: string[] = [];
  const runPick = async (fix: "ok" | "fail", during: () => void = () => {}) => {
    const seq = ++pickSeq;
    await Promise.resolve();          // the posNow await — the race window
    during();
    if (seq !== pickSeq) return;      // superseded tail — dead
    if (fix === "ok") {
      if (pickTailGate(phase, "advance")) { phase = "compare"; writes.push("advance"); }
      return;
    }
    if (!pickTailGate(phase, "stay")) { writes.push("cleared"); return; }
    writes.push("rearm");
  };

  /* race: P1 in flight when P2 lands — P1's resume dies before writing */
  const p1 = runPick("fail");
  const p2 = runPick("ok");
  await Promise.all([p1, p2]);
  assert.deepEqual(writes, ["advance"], "the superseded pick wrote nothing");
  assert.equal(phase, "compare");

  /* the drive's bounce: pick → BACK/close moves the surface on → the
     failure tail must not reopen an empty Where-to */
  pickSeq = 0; phase = "search"; writes.length = 0;
  await runPick("fail", () => { phase = "idle"; });
  assert.equal(phase, "idle");
  assert.deepEqual(writes, ["cleared"], "a dead surface must not remount");

  /* a failed pick while search still owns the surface re-arms it — same
     mounted sheet, query intact, honest notice (not an empty remount) */
  pickSeq = 0; phase = "search"; writes.length = 0;
  await runPick("fail");
  assert.deepEqual(writes, ["rearm"]);
  assert.equal(phase, "search");
});

test("useShellFlow keeps the race guards wired", () => {
  const src = readFileSync(SH, "utf8");
  assert.match(src, /phaseRef\.current/, "phaseRef must mirror the requested phase");
  assert.match(src, /seq !== pickSeq\.current/, "stale-generation bail must precede the tail's writes");
  assert.match(src, /pickTailGate\(phaseRef\.current, "stay"\)/);
  assert.match(src, /pickTailGate\(phaseRef\.current, "advance"\)/);
  assert.match(src, /setPickDone/, "the sheet's latch needs the resolution signal");
});

test("SearchScreen commits the press-in identity and latches during confirm", () => {
  const src = readFileSync(SC, "utf8");
  assert.match(src, /pickAtPress\.current = \{ p, at: Date\.now\(\) \}/,
    "rows must capture their identity at onPressIn — index-keyed fibers swap props under a finger");
  assert.match(src, /onPressIn=\{onPressIn\}/, "PlaceRow must forward onPressIn to Pressable");
  assert.match(src, /if \(committing\.current\) return;/,
    "second tap during a pick's confirm window must be held, not raced");
  assert.match(src, /committing\.current = false; \}, \[pickDone\]\)/,
    "the latch must release on the shell's pickDone signal");
});

test("root BACK never bare-exits — double-press-to-exit instead", () => {
  const src = readFileSync(APP, "utf8");
  /* eject-to-launcher (demo-vid-android drawer→settings→Trips walk): the
     dispatcher's root fell through to `return false` and Android finished
     the activity mid-walk. Require the warn-first pattern. */
  assert.match(src, /lastBackAt\.current/, "needs the last-press timestamp");
  assert.match(src, /ToastAndroid\.show\(t\("backToExit"/,
    "the first root press must warn instead of exiting");
  /* the dispatcher must not still end in a bare `return false` at root */
  const tail = src.match(/phase === "idle" && !homeOpen[\s\S]{0,1200}?\}\);/);
  assert.ok(tail, "root dispatcher tail not found");
  assert.doesNotMatch(tail[0].replace(/lastBackAt[\s\S]*$/, ""), /return false;?\s*\}\);?\s*$/,
    "a bare 'return false' at the root ejects the app on any stray press");
});
