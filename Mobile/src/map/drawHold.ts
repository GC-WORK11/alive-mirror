/** drawHold — sim-only throttle of MapLibre's draw pump across overlay
 * mount/unmount commits.
 *
 * The residual SIGSEGV in this stack is a mount-vs-draw race: a sheet's
 * native view commit lands while the map's render thread is mid-frame on
 * the simulator's virtualised GPU and the Metal/XPC pipe dies under it —
 * reproduceable on the search sheet and on the compare sheet, ~1.6 s
 * after mount (docs/lanes/search-fix-verify-report.md). Focus removal,
 * always-mounted map children, JS-driven springs and staggered camera
 * work each shrank a trigger but the mount commit itself still races
 * the draw — at 60 fps a ~300 ms mount window can intersect ~18 draws.
 *
 * Two levers, both sim-only (Device.isDevice — same precedent as
 * cam.ts' camDur, hardware is untouched):
 *  - preferredFramesPerSecond: pin the map's render loop to 2 fps for the
 *    window so at most a couple of draws coexist with a mount commit.
 *  - whenMapDrawFree: hold map-side imperative work (camera commits)
 *    until the window ends so it can never ride the mount frame.
 *
 * Ordering: holdMapDrawThen() opens the hold on the caller's task — the
 * useSyncExternalStore notification flushes synchronously inside a
 * discrete event — and defers the setState one task, so the throttle
 * prop commits on the native view BEFORE the mount it precedes.
 */
import { useCallback, useState, useSyncExternalStore, type SetStateAction } from "react";
import * as Device from "expo-device";

/* window length: covers a sheet's enter spring (~0.4 s) plus the deferred
   body/rows commits that trail it (search bodyReady, compare cards,
   recents) — the observed crash lands ~1.6 s post-mount, inside this. */
export const MAP_DRAW_HOLD_MS = 1400;
/* grace after the last hold before fps restores — a mount's trailing
   commits cluster just past the window edge */
const TAIL_MS = 600;
const POLL_MS = 80;

let held = false;
let deadline = 0;
let timer: ReturnType<typeof setTimeout> | null = null;
const listeners = new Set<() => void>();

const emit = () => listeners.forEach((l) => l());

function releaseCheck() {
  const wait = deadline + TAIL_MS - Date.now();
  if (wait > 0) { timer = setTimeout(releaseCheck, wait); return; }
  timer = null;
  held = false;
  emit();
}

/** Open (or extend) a draw-hold window of `ms`: the map's render loop
 *  runs throttled until the window + TAIL_MS elapse. No-op on hardware. */
export function holdMapDraw(ms = MAP_DRAW_HOLD_MS) {
  if (Device.isDevice) return;
  deadline = Date.now() + ms;
  if (!held) { held = true; emit(); }
  if (timer) clearTimeout(timer);
  timer = setTimeout(releaseCheck, ms + TAIL_MS);
}

export function mapDrawHeld() { return held; }

/** React binding for <Map preferredFramesPerSecond>. */
export function useMapDrawHeld(): boolean {
  return useSyncExternalStore(
    useCallback((cb: () => void) => {
      listeners.add(cb);
      return () => { listeners.delete(cb); };
    }, []),
    mapDrawHeld);
}

/** Run `cb` once the pump is free — immediately when no hold is open,
 *  else when the current window ends (capped so rapid open/close
 *  sequences can't starve camera work). Runs synchronously on hardware. */
export function whenMapDrawFree(cb: () => void, capMs = 2600) {
  if (Device.isDevice || !held) { cb(); return; }
  const t0 = Date.now();
  const poll = () => {
    if (!held || Date.now() - t0 > capMs) cb();
    else setTimeout(poll, POLL_MS);
  };
  setTimeout(poll, POLL_MS);
}

/** `setState` ordered AFTER the fps drop commits: the hold opens now
 *  (its store notification flushes inside this event's sync work), the
 *  caller's update lands next task in its own commit — the throttle is
 *  already on the native view when the mount it precedes arrives. */
export function holdMapDrawThen(cb: () => void, ms = MAP_DRAW_HOLD_MS) {
  if (Device.isDevice) { cb(); return; }
  holdMapDraw(ms);
  setTimeout(cb, 0);
}

/** useState whose setter commits inside a draw-hold — for the flags that
 *  mount/unmount an overlay over the map. */
export function useHeldState<T>(init: T | (() => T)): [T, (v: SetStateAction<T>) => void] {
  const [v, setV] = useState(init);
  const set = useCallback((n: SetStateAction<T>) => holdMapDrawThen(() => setV(n)), []);
  return [v, set];
}
