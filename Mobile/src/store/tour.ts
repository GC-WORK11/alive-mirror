// One-time coach-tour flag — the first-run spotlight walk of the home
// surface plays once per install (docs/lanes/coach-tour), then
// `coach_tour_seen_v1` is on disk forever. Same File/Paths JSON-document
// store as welcome.ts / consent.ts: if the FS ever fails we still work
// in memory — the flag must never wedge the app, and a lost flag only
// ever means the tour plays once more, skippable as always.
import { File, Paths } from "expo-file-system";

const FILE = new File(Paths.document, "coach_tour_seen_v1.json");

let mem: boolean | null = null;

/** True once the tour has been presented (finished, skipped, or left). */
export async function loadTourSeen(): Promise<boolean> {
  if (mem != null) return mem;
  try {
    if (FILE.exists) {
      const j = JSON.parse(await FILE.text());
      mem = j?.seen === true;
      return mem;
    }
  } catch {}
  mem = false;
  return mem;
}

/** Persist the seen flag — called on every exit path (done, skip, or
 *  the surface underneath taking over: the tour never re-arms once it
 *  has been presented). */
export async function markTourSeen(): Promise<void> {
  mem = true;
  try {
    if (!FILE.exists) FILE.create();
    FILE.write(JSON.stringify({ seen: true, ts: Date.now() }));
  } catch {
    // best-effort — the in-memory copy still holds for the session
  }
}

/** "Delete my data" seam — reset alongside the other stores so a wiped
 *  phone re-arms the first-run tour on next launch. */
export function clearTourSeen(): void {
  mem = false;
  try {
    if (FILE.exists) FILE.delete();
  } catch {}
}
