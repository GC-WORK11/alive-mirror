// One-time welcome flag — the first-breath cinematic plays once per
// install, then `welcome_seen_v1` is on disk forever (docs/lanes/
// welcome-loading.md). Same File/Paths JSON-document store as
// consent.ts: if the FS ever fails we still work in memory — the
// flag must never wedge the app, and a lost flag only ever means the
// welcome plays once more, skippable as always.
//
// Persistence goes through safefile (atomic tmp→rename + .bak) — a torn
// naive write used to read as never-seen on every later open.
import { purgeJsonDoc, readJsonDoc, writeJsonDoc } from "./safefile";

const NAME = "welcome_seen_v1.json";

let mem: boolean | null = null;

/** True once the welcome cinematic has played (or been skipped through). */
export async function loadWelcomeSeen(): Promise<boolean> {
  if (mem != null) return mem;
  const j = await readJsonDoc(NAME, (v): v is { seen?: unknown } =>
    !!v && typeof v === "object");
  mem = j?.seen === true;
  return mem;
}

/** Persist the seen flag — called on every exit path (auto or tap). */
export async function markWelcomeSeen(): Promise<void> {
  mem = true;
  writeJsonDoc(NAME, { seen: true, ts: Date.now() });
}

/** "Delete my data" seam — reset alongside the other stores so a wiped
 *  phone re-arms the first-breath moment on next launch. */
export function clearWelcomeSeen(): void {
  mem = false;
  purgeJsonDoc(NAME);
}

/** Test seam — drop the in-memory mirror so the next load re-reads disk
 *  (relaunch simulation; same convention as resetConsentCache). */
export function resetWelcomeCache(): void {
  mem = null;
}
