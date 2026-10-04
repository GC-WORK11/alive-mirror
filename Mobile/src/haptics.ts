/** Haptics (expo-haptics) — a light physical layer on real events only:
 *  a pick lands, the full option set replaces the engine-first paint,
 *  navigation starts, the arrival fires. Nothing vibrates on a timer or
 *  a render — each call site is a user-visible state change.
 *
 *  Every helper swallows failure: simulators without a vibrator, web,
 *  and devices with haptics off must never throw into a gesture path. */
import * as Haptics from "expo-haptics";

/** Selection tick — picking a row/card (compare option, wizard card,
 *  search result). Subtle; fires often, so keep it the lightest. */
export function tick(): void {
  try { void Haptics.selectionAsync(); } catch { /* no vibrator — silent */ }
}

/** Soft confirm — the compare sheet's full option set lands, a reminder
 *  gets armed, a toggle flips state that costs a beat. */
export function tap(): void {
  try { void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light); } catch { /* silent */ }
}

/** Commit bump — Start navigation, save, share. */
export function confirm(): void {
  try { void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium); } catch { /* silent */ }
}

/** Arrival / done buzz — the one celebration the journey earns. */
export function arrived(): void {
  try { void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success); }
  catch { /* silent */ }
}
