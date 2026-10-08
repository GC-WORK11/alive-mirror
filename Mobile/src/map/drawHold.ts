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
 *
 * ---- cold-boot watch ----
 * The window above only covers a mount's own ~2 s. On a cold launch
 * the render pipeline stays fragile for ~90 s — the mount-vs-draw
 * race fires on a sheet mount ~2 s after the tap even when the tile
 * cache is warm (8/20 gate iterations died that way: tap ~6.5 s
 * post-launch → SIGSEGV ~2.3 s later). While the watch is open the
 * pump stays throttled for a FIXED BOOT_WATCH_MS window (residual
 * ~90 s + margin), and a mount commit additionally waits for a
 * measured draw-idle gap (mapBusy clear, BOOT_MOUNT_WAIT_MS cap) so
 * it lands inside the ~500 ms gap the 2 fps throttle creates, not
 * inside a frame.
 *
 * The watch must NOT close on an early idle report: a warm tile
 * cache fires didFinishLoadingMap/Fully within ~1 s of eval — the
 * first iteration of this fix measured "settled" at +666 ms and the
 * gate still crashed 8/20, because the fragile phase is the young
 * render pipeline, not tile streaming. At BOOT_WATCH_MS steady-state
 * semantics resume. On hardware every branch below is dead code:
 * watchDone is born true. */
import { useCallback, useEffect, useRef, useState, useSyncExternalStore, type SetStateAction } from "react";
import * as Device from "expo-device";

/* window length: covers a sheet's enter spring (~0.4 s) plus the deferred
   body/rows commits that trail it (search bodyReady, compare cards,
   recents) — the observed crash lands ~1.6 s post-mount, inside this. */
export const MAP_DRAW_HOLD_MS = 1400;
/* grace after the last hold before fps restores — a mount's trailing
   commits cluster just past the window edge */
const TAIL_MS = 600;
const POLL_MS = 80;

/* ---- cold-boot window constants ----
   the residual window measured ~90 s post-launch; the watch holds
   the throttle for its whole fixed length — never for an early idle
   report (see the docstring: warm caches idle in ~1 s) */
const BOOT_WATCH_MS = 100_000;
/* release poll cadence while the watch is open */
const BOOT_POLL_MS = 400;
/* a mount waits at most this long for a measured draw-idle gap, then
   commits anyway (the pump is already throttled — bounded risk) */
const BOOT_MOUNT_WAIT_MS = 1400;
/* mounts that land in the cold window get a longer hold — cold-boot
   trailing commits (deferred body, recents file read, fetch rows)
   trail measurably further than warm ones */
const BOOT_MOUNT_HOLD_MS = 2600;
const BOOT_IDLE_POLL_MS = 60;

let held = false;
let deadline = 0;
let timer: ReturnType<typeof setTimeout> | null = null;
const listeners = new Set<() => void>();

/* boot-watch state — sim only; on hardware watchDone is born true so
   every read short-circuits without touching these */
let mapBusy = true;            // render thread has work — until the map proves idle
let watchDone = Device.isDevice;

/* lane instrumentation — flip to watch the window from Metro logs */
const DEBUG = false;
const dbg = (what: string) => {
  if (DEBUG) console.log(`[drawHold] ${what} t=${Math.round(performance.now())}`);
};

const emit = () => listeners.forEach((l) => l());

function bootWatchOpen() { return !watchDone; }

function endBootWatch() {
  watchDone = true;
  mapBusy = false;                       // stop gating mounts on idle
  dbg("watch end (100 s cap)");
  releaseCheck();                        // drop the boot arm; live holds still honored
}

function releaseCheck() {
  /* while the watch is open the boot arm owns `held` — mount-window
     deadlines are tracked but can't release until the window closes */
  if (bootWatchOpen()) { timer = setTimeout(releaseCheck, BOOT_POLL_MS); return; }
  const wait = deadline + TAIL_MS - Date.now();
  if (wait > 0) { timer = setTimeout(releaseCheck, wait); return; }
  timer = null;
  held = false;
  emit();
}

/** Map began a render pass — wire to the Map's onWillStartRenderingMap.
 *  Busy evidence keeps the settle tail from firing mid-stream. */
export function noteMapBusy() {
  if (Device.isDevice) return;
  if (!mapBusy) dbg("busy");
  mapBusy = true;
}

/** Map fully rendered (onDidFinishRenderingMapFully) or fully loaded
 *  (onDidFinishLoadingMap — fallback settle evidence): the draw pump is
 *  idle right now. A quiet stretch of these closes the boot watch. */
export function noteMapIdle() {
  if (Device.isDevice) return;
  if (mapBusy) dbg("idle");
  mapBusy = false;
}

/* open the watch at module eval on sim: `held` stays armed for the whole
   fixed BOOT_WATCH_MS window (releaseCheck refuses to release while the
   watch is open) — every overlay commit in the window rides the
   throttle plus the idle-wait. The watch ends only at the cap: an
   early idle report is not evidence the pipeline is safe. */
if (!Device.isDevice) {
  held = true;
  timer = setTimeout(releaseCheck, BOOT_POLL_MS);
  setTimeout(endBootWatch, BOOT_WATCH_MS);
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

/* the pump is safe to ride when no hold is armed — and, inside the boot
   window, whenever the map reports a genuinely-idle gap between bursts */
function drawFree() {
  return !held || (bootWatchOpen() && !mapBusy);
}

/** Run `cb` once the pump is free — immediately when no hold is open,
 *  else when the current window ends (capped so rapid open/close
 *  sequences can't starve camera work). Inside the boot window an
 *  idle gap frees it early. Runs synchronously on hardware. */
export function whenMapDrawFree(cb: () => void, capMs = 2600) {
  /* whatever runs here is an app-driven map op — mark the window so a
     touch-attributed region event it emits can't read as a user drag */
  const run = () => { noteMapTransition(); cb(); };
  if (Device.isDevice || drawFree()) { run(); return; }
  const t0 = Date.now();
  const poll = () => {
    if (drawFree() || Date.now() - t0 > capMs) run();
    else setTimeout(poll, POLL_MS);
  };
  setTimeout(poll, POLL_MS);
}

/* app-driven transition window — every overlay mount/unmount and every
   programmatic camera op rides holdMapDrawThen / whenMapDrawFree, so the
   marker arms inside both. Gesture handlers read it to tell a real drag
   from transition noise: the bare-map nit — a tap's own
   userInteraction=true region event arriving inside the nav-exit or
   search-mount window latched the label drop (airfieldValues +
   airStationNames + every basemap name) for seconds past the sheet. */
let transitionUntil = 0;
/** Mark an app-driven transition window of `ms` — read by gesture
 *  handlers so transition-attributed camera events can't hide labels. */
export function noteMapTransition(ms = 1600) {
  const until = Date.now() + ms;
  if (until > transitionUntil) transitionUntil = until;
}
/** Inside an app-driven transition? A userInteraction=true region event
 *  here is noise (the tap that closed the sheet, the settle camera), not
 *  a real drag — label-drop arming must skip it. */
export function inMapTransition() {
  return Date.now() < transitionUntil;
}

/** `setState` ordered AFTER the fps drop commits: the hold opens now
 *  (its store notification flushes inside this event's sync work), the
 *  caller's update lands next task in its own commit — the throttle is
 *  already on the native view when the mount it precedes arrives.
 *
 *  In the boot window the commit also waits for a measured draw-idle
 *  gap (bounded by BOOT_MOUNT_WAIT_MS) and lands under the longer cold
 *  hold — a mid-tile-flush mount is the residual crash. */
export function holdMapDrawThen(cb: () => void, ms = MAP_DRAW_HOLD_MS) {
  noteMapTransition();
  if (Device.isDevice) { cb(); return; }
  holdMapDraw(ms);
  if (!bootWatchOpen()) { setTimeout(() => { noteMapTransition(); cb(); }, 0); return; }
  const t0 = Date.now();
  const fire = () => { holdMapDraw(BOOT_MOUNT_HOLD_MS); noteMapTransition(); cb(); };
  const poll = () => {
    if (!mapBusy || Date.now() - t0 > BOOT_MOUNT_WAIT_MS) fire();
    else setTimeout(poll, BOOT_IDLE_POLL_MS);
  };
  setTimeout(poll, BOOT_IDLE_POLL_MS);
}

/** useState whose setter commits inside a draw-hold — for the flags that
 *  mount/unmount an overlay over the map.
 *
 *  A set that resolves to the current value mounts nothing — skip it
 *  entirely instead of arming a hold window for a commit that will never
 *  exist (e.g. openSidebar's unconditional setLayersOpen(false) when the
 *  layers sheet wasn't up). pendRef tracks the last value this setter
 *  accepted so a same-tick set→set still sees the pending one, not the
 *  committed one. */
export function useHeldState<T>(init: T | (() => T)): [T, (v: SetStateAction<T>) => void] {
  const [v, setV] = useState(init);
  const pendRef = useRef(v);
  useEffect(() => { pendRef.current = v; }, [v]);
  const set = useCallback((n: SetStateAction<T>) => {
    const next = typeof n === "function" ? (n as (p: T) => T)(pendRef.current) : n;
    if (Object.is(next, pendRef.current)) return;
    pendRef.current = next;
    holdMapDrawThen(() => setV(next));
  }, []);
  return [v, set];
}
