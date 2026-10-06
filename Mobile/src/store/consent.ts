// First-run consent state — the consent gate (docs/plan/onboarding.md,
// doc 07 §3 "Disclosure"). One JSON document in the app's document dir,
// same File/Paths pattern as src/search/recents.ts + src/store/ledger.ts.
// If the FS ever fails we still work in memory for the session — the gate
// must never wedge the app.
import { File, Paths } from "expo-file-system";

const FILE = new File(Paths.document, "consent.json");

export type SharingChoice = "on" | "off";

export type ConsentState = {
  seen: boolean;                  // onboarding finished by any path
  sharing: SharingChoice | null;  // anonymous trip donation — null until answered
  ts: number | null;              // epoch ms when `sharing` was last set
};

const EMPTY: ConsentState = { seen: false, sharing: null, ts: null };

// In-memory cache — fast path after first load, whole store when the
// document directory is unavailable. `inflight` dedupes concurrent first
// reads (perf r4); writes are serialized through `writeTail` so the file
// always lands last-state-wins.
let mem: ConsentState | null = null;
let inflight: Promise<ConsentState> | null = null;
let writeTail: Promise<unknown> = Promise.resolve();

function sanitize(raw: unknown): ConsentState {
  if (!raw || typeof raw !== "object") return EMPTY;
  const o = raw as Partial<ConsentState>;
  return {
    seen: o.seen === true,
    sharing: o.sharing === "on" || o.sharing === "off" ? o.sharing : null,
    ts: typeof o.ts === "number" ? o.ts : null,
  };
}

async function persist(s: ConsentState): Promise<void> {
  mem = s;
  try {
    if (!FILE.exists) FILE.create();
    FILE.write(JSON.stringify(mem));
  } catch {
    // best-effort — the in-memory copy still holds
  }
}

/** Load the consent record (seen · sharing · ts). Stays eager — it gates
 *  the onboarding sheet — but concurrent first callers share one read. */
export async function loadConsent(): Promise<ConsentState> {
  if (mem) return mem;
  if (!inflight) {
    inflight = (async () => {
      try {
        if (FILE.exists) {
          mem = sanitize(JSON.parse(await FILE.text()));
          return mem;
        }
      } catch {}
      mem ??= EMPTY;
      return mem;
    })();
  }
  return inflight;
}

/** Merge a patch and persist — the only writer. Settings' share toggle
 *  calls `saveConsent({ sharing: "on"|"off", ts: Date.now() })`. The
 *  whole read-modify-write runs inside the writeTail chain: two
 *  concurrent saves that each merged from the same base state would
 *  last-writer-wins away each other's keys (the onboarding race —
 *  `sharing` landed but `seen: true` was clobbered). */
export function saveConsent(patch: Partial<ConsentState>): Promise<ConsentState> {
  const p = writeTail.then(async () => {
    const next = { ...(await loadConsent()), ...patch };
    await persist(next);
    return next;
  });
  writeTail = p.catch(() => {});
  return p;
}

/** "Delete my data" seam — call from settings.clearAllData() so wiping the
 *  phone also wipes this file and re-arms the gate on next launch. */
export function clearConsent(): void {
  mem = EMPTY;
  try {
    if (FILE.exists) FILE.delete();
  } catch {}
}
