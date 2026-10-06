// One-time welcome flag — the first-breath cinematic plays once per
// install, then `welcome_seen_v1` is on disk forever (docs/lanes/
// welcome-loading.md). Same File/Paths JSON-document store as
// consent.ts: if the FS ever fails we still work in memory — the
// flag must never wedge the app, and a lost flag only ever means the
// welcome plays once more, skippable as always.
import { File, Paths } from "expo-file-system";

const FILE = new File(Paths.document, "welcome_seen_v1.json");

let mem: boolean | null = null;

/** True once the welcome cinematic has played (or been skipped through). */
export async function loadWelcomeSeen(): Promise<boolean> {
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

/** Persist the seen flag — called on every exit path (auto or tap). */
export async function markWelcomeSeen(): Promise<void> {
  mem = true;
  try {
    if (!FILE.exists) FILE.create();
    FILE.write(JSON.stringify({ seen: true, ts: Date.now() }));
  } catch {
    // best-effort — the in-memory copy still holds for the session
  }
}

/** "Delete my data" seam — reset alongside the other stores so a wiped
 *  phone re-arms the first-breath moment on next launch. */
export function clearWelcomeSeen(): void {
  mem = false;
  try {
    if (FILE.exists) FILE.delete();
  } catch {}
}
