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

test("SearchScreen never focuses the input programmatically", () => {
  const path = fileURLToPath(new URL("../screens/SearchScreen.tsx", import.meta.url));
  const src = readFileSync(path, "utf8");
  /* the gate itself proved insufficient: runAfterInteractions waits on RN's
     interaction queue but not MapLibre's draw thread, so a timed focus()
     still SIGSEGV'd (ios-journey-overnight lane — stealKB signature with
     d791879's gate present). The invariant is now stronger: NO focus() or
     autoFocus anywhere; the keyboard rises only on the user's own tap. */
  assert.equal(src.match(/inputRef\.current\?\.focus\(\)/g)?.length ?? 0, 0,
    "programmatic focus() reintroduced — keyboard must rise on user tap only");
  assert.equal(src.match(/autoFocus\s*[=={]/g)?.length ?? 0, 0,
    "autoFocus prop reintroduced — same responder-handoff crash class");
});
