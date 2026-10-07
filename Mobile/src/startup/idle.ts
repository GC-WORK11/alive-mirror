// "Off the critical path" scheduler for boot-time work: resolves after the
// first painted frame AND any in-flight JS interactions — or after a hard
// cap so a caller can never hang waiting on an animation that never ends.
// Used by the persistence stores so disk reads + JSON.parse don't compete
// with font loading and the mount commit; resolution is memoized, so calls
// made later in the session resolve on the next microtask.
let firstIdle: Promise<void> | null = null;

/* ---- input-priority signal for boot-time background work ----
   The root view's onTouchStart marks every touch-down; schedulers of
   boot bursts (gazetteer warm, tile-pack prefetch) check msSinceInput()
   before each work slice so a user's tap never queues behind deferred
   work — the boot-burst freeze class (docs/lanes/boot-burst-report.md). */
let lastInputAt = 0;

export function noteUserInput(): void {
  lastInputAt = Date.now();
}

/** ms since the last observed touch; Infinity until the first one. */
export function msSinceInput(): number {
  return lastInputAt ? Date.now() - lastInputAt : Number.POSITIVE_INFINITY;
}

export function afterFirstFrame(capMs = 1200): Promise<void> {
  if (!firstIdle) {
    firstIdle = new Promise<void>((resolve) => {
      let done = false;
      const finish = () => {
        if (done) return;
        done = true;
        resolve();
      };
      const t = setTimeout(finish, capMs);
      // after two painted frames + a macrotask — the mount commit and any
      // queued interactions have had their beat; the cap above is the hard
      // bound either way. (InteractionManager is deprecated in new arch.)
      requestAnimationFrame(() =>
        requestAnimationFrame(() => setTimeout(() => { clearTimeout(t); finish(); }, 0)),
      );
    });
  }
  return firstIdle;
}
