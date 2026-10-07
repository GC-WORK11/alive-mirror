import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

/* crash regression (docs/lanes/sigsegv-mount-fix-report.md): the residual
   sheet-mount SIGSEGV is a mount-vs-draw race — an overlay's native
   commit lands while MapLibre's render thread is mid-frame on the
   virtualised-GPU sim. The fix throttles the pump through
   preferredFramesPerSecond across every mount window and makes
   map-side imperative work wait for draw-idle. Guard the wiring so a
   refactor can't silently drop the hold. */

const read = (p: string) => readFileSync(fileURLToPath(new URL(p, import.meta.url)), "utf8");

test("drawHold is sim-gated on Device.isDevice", () => {
  const src = read("../map/drawHold.ts");
  assert.match(src, /Device\.isDevice/, "drawHold must no-op on real hardware (camDur precedent)");
  assert.match(src, /export function holdMapDraw/, "holdMapDraw export missing");
  assert.match(src, /export function whenMapDrawFree/, "whenMapDrawFree export missing");
  assert.match(src, /export function holdMapDrawThen/, "holdMapDrawThen export missing");
});

test("the Map's preferredFramesPerSecond rides the draw-hold", () => {
  const app = read("../../App.tsx");
  assert.match(app, /preferredFramesPerSecond=\{drawHeld \? 2 : -1\}/,
    "MapTree must pass the hold through preferredFramesPerSecond");
  assert.match(app, /useMapDrawHeld\(\)/, "AppInner must subscribe to the hold store");
});

test("phase transitions commit inside a draw-hold", () => {
  const flow = read("../components/shell/useShellFlow.ts");
  const wrapped = flow.match(/holdMapDrawThen\(\(\) => setPhaseState\(p\)\)/);
  assert.ok(wrapped, "setPhase must commit via holdMapDrawThen so the fps drop lands before the mount");
});

test("camera commits wait for draw-idle", () => {
  const flow = read("../components/shell/useShellFlow.ts");
  const frees = flow.match(/whenMapDrawFree/g)?.length ?? 0;
  /* fitBounds (plan fit) + flyTo/setStop (nav enter) + setStop (nav exit)
     — all three imperative camera sites must ride the hold */
  assert.ok(frees >= 3, `expected whenMapDrawFree at >=3 camera sites, found ${frees}`);
  assert.match(flow, /whenMapDrawFree\(\(\) => \{\s*if \(!cancelled\) camRef\.current\?\.fitBounds/,
    "the plan fitBounds must wait for draw-idle");
});

test("the cold-boot watch holds the pump while the first tile stream runs", () => {
  const src = read("../map/drawHold.ts");
  /* testday-ios §9: mounts inside the first ~90 s of a cold launch die
     on the young render pipeline even with the mount-window hold — the
     watch keeps the throttle armed for the whole fixed window */
  assert.match(src, /noteMapBusy/, "noteMapBusy export missing");
  assert.match(src, /noteMapIdle/, "noteMapIdle export missing");
  assert.match(src, /BOOT_WATCH_MS/, "boot watch needs a fixed span past the residual window");
  assert.match(src, /holdMapDrawThen[\s\S]*mapBusy/, "in-window mounts must wait for draw-idle");
});

test("the map feeds render busy/idle into the boot watch", () => {
  const app = read("../../App.tsx");
  assert.match(app, /onWillStartRenderingMap=\{onMapBusy\}/,
    "Map must wire onWillStartRenderingMap into noteMapBusy");
  assert.match(app, /onDidFinishRenderingMapFully=\{onMapFullyRendered\}/,
    "Map must wire onDidFinishRenderingMapFully into noteMapIdle");
  assert.match(app, /const onMapFullyRendered = \(\) => \{ onMapIdle\(\)/,
    "the fully-rendered handler must call onMapIdle (basemap prefetch rides it)");
  assert.match(app, /const onMapBusy = \(\) => noteMapBusy\(\)/,
    "onMapBusy must call noteMapBusy");
  assert.match(app, /noteMapIdle\(\)/, "onMapIdle must call noteMapIdle");
});
