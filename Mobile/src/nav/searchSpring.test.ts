import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

/* crash regression (docs/lanes/search-crash-report.md): the search sheet's
   enter spring must stay on the JS driver. a85517f flipped it to
   useNativeDriver:true; the sheet then SIGSEGV'd — natively diagnosed as a
   Hermes GC heap stomp — when reopened over a running map/camera
   transition. Native anim-driver node graphs mutate JS-managed state from
   the render thread; the JS driver keeps the graph off it. Guard the flag
   so the perf A/B can't silently flip it back. */
test("SearchScreen enter spring stays on the JS driver", () => {
  const path = fileURLToPath(new URL("../screens/SearchScreen.tsx", import.meta.url));
  const src = readFileSync(path, "utf8");
  const spring = src.match(/Animated\.spring\(enter,[\s\S]*?\)\.start\(\)/);
  assert.ok(spring, "SearchScreen enter spring call not found");
  assert.match(spring![0], /useNativeDriver:\s*false/,
    "enter spring must run with useNativeDriver:false (native driver segfaults this stack)");
});

test("SearchScreen autofocus is gated behind runAfterInteractions", () => {
  const path = fileURLToPath(new URL("../screens/SearchScreen.tsx", import.meta.url));
  const src = readFileSync(path, "utf8");
  /* focus()/becomeFirstResponder inside the mount-commit window is the
     segfault trigger (see docs/lanes/search-crash-report.md): every call
     into inputRef.current?.focus() must be queued behind
     InteractionManager.runAfterInteractions so the responder handoff
     lands after the enter spring + commit queue drain. */
  const focusCalls = src.match(/inputRef\.current\?\.focus\(\)/g) ?? [];
  assert.ok(focusCalls.length > 0, "autofocus call not found");
  const gate = src.match(/InteractionManager\.runAfterInteractions\([\s\S]*?inputRef\.current\?\.focus\(\)/);
  assert.ok(gate, "focus() must run inside InteractionManager.runAfterInteractions");
  const outside = src.replace(/InteractionManager\.runAfterInteractions\([\s\S]*?\}\);/g, "");
  assert.equal(outside.match(/inputRef\.current\?\.focus\(\)/g)?.length ?? 0, 0,
    "focus() found outside the runAfterInteractions gate");
});
