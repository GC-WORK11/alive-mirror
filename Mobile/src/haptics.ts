/** Haptics (expo-haptics) — a light physical layer on real events only:
 *  a pick lands, the full option set replaces the engine-first paint,
 *  navigation starts, the arrival fires. Nothing vibrates on a timer or
 *  a render — each call site is a user-visible state change.
 *
 *  Every helper swallows failure: simulators without a vibrator, web,
 *  devices with haptics off, and platforms where the method is missing
 *  must never throw into a gesture path. That includes ASYNC failure —
 *  a rejected promise escapes a plain try/catch as an unhandled
 *  rejection, so each call also attaches a no-op .catch. */
import * as Haptics from "expo-haptics";

const silent = (p: Promise<void> | undefined): void => {
  try { void p?.catch(() => { /* no haptics — silent */ }); }
  catch { /* synchronous throw — silent */ }
};

/** Selection tick — picking a row/card (compare option, wizard card,
 *  search result). Subtle; fires often, so keep it the lightest. */
export function tick(): void {
  try { silent(Haptics.selectionAsync()); } catch { /* no vibrator — silent */ }
}

/** Soft confirm — the compare sheet's full option set lands, a reminder
 *  gets armed, a toggle flips state that costs a beat. */
export function tap(): void {
  try { silent(Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light)); } catch { /* silent */ }
}

/** Commit bump — Start navigation, save, share. */
export function confirm(): void {
  try { silent(Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium)); } catch { /* silent */ }
}

/** Arrival / done buzz — the one celebration the journey earns. */
export function arrived(): void {
  try { silent(Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success)); }
  catch { /* silent */ }
}
