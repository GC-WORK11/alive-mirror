// "Off the critical path" scheduler for boot-time work: resolves after the
// first painted frame AND any in-flight JS interactions — or after a hard
// cap so a caller can never hang waiting on an animation that never ends.
// Used by the persistence stores so disk reads + JSON.parse don't compete
// with font loading and the mount commit; resolution is memoized, so calls
// made later in the session resolve on the next microtask.
import { InteractionManager } from "react-native";

let firstIdle: Promise<void> | null = null;

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
      requestAnimationFrame(() =>
        InteractionManager.runAfterInteractions(() => {
          clearTimeout(t);
          finish();
        }),
      );
    });
  }
  return firstIdle;
}
