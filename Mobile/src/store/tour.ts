// One-time coach-tour flag — the first-run spotlight walk of the home
// surface plays once per install (docs/lanes/coach-tour), then
// `coach_tour_seen_v1` is on disk forever. Same File/Paths JSON-document
// store as welcome.ts / consent.ts: if the FS ever fails we still work
// in memory — the flag must never wedge the app, and a lost flag only
// ever means the tour plays once more, skippable as always.
//
// Persistence goes through safefile (atomic tmp→rename + .bak) — a torn
// naive write used to read as never-seen on every later open.
import { purgeJsonDoc, readJsonDoc, writeJsonDoc } from "./safefile";

const NAME = "coach_tour_seen_v1.json";

let mem: boolean | null = null;

/** True once the tour has been presented (finished, skipped, or left). */
export async function loadTourSeen(): Promise<boolean> {
  if (mem != null) return mem;
  const j = await readJsonDoc(NAME, (v): v is { seen?: unknown } =>
    !!v && typeof v === "object");
  mem = j?.seen === true;
  return mem;
}

/** Persist the seen flag — called on every exit path (done, skip, or
 *  the surface underneath taking over: the tour never re-arms once it
 *  has been presented). */
export async function markTourSeen(): Promise<void> {
  mem = true;
  writeJsonDoc(NAME, { seen: true, ts: Date.now() });
}

/** "Delete my data" seam — reset alongside the other stores so a wiped
 *  phone re-arms the first-run tour on next launch. */
export function clearTourSeen(): void {
  mem = false;
  purgeJsonDoc(NAME);
}

/** Test seam — drop the in-memory mirror so the next load re-reads disk
 *  (relaunch simulation; same convention as resetConsentCache). */
export function resetTourCache(): void {
  mem = null;
}
