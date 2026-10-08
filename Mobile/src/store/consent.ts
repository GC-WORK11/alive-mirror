// First-run consent state — the consent gate (docs/plan/onboarding.md,
// doc 07 §3 "Disclosure"). One JSON document in the app's document dir,
// same File/Paths pattern as src/search/recents.ts + src/store/ledger.ts.
// If the FS ever fails we still work in memory for the session — the gate
// must never wedge the app.
//
// Persistence goes through safefile (atomic tmp→rename + .bak): the old
// naive FILE.create()+FILE.write() could leave a torn/empty consent.json
// — JSON.parse threw, the flag read as `seen:false`, and onboarding
// replayed on every cold open forever. .bak restores the last good
// generation instead.
import { purgeJsonDoc, readJsonDoc, writeJsonDoc } from "./safefile";

const NAME = "consent.json";

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
/* wipe generation — a save that merged pre-wipe state must not resurrect
   the file (saveSettings' `mem === null` convention, daylog's wipeGen). */
let wipeGen = 0;

function sanitize(raw: unknown): ConsentState {
  if (!raw || typeof raw !== "object") return EMPTY;
  const o = raw as Partial<ConsentState>;
  return {
    seen: o.seen === true,
    sharing: o.sharing === "on" || o.sharing === "off" ? o.sharing : null,
    ts: typeof o.ts === "number" ? o.ts : null,
  };
}

/** Load the consent record (seen · sharing · ts). Stays eager — it gates
 *  the onboarding sheet — but concurrent first callers share one read. */
export async function loadConsent(): Promise<ConsentState> {
  if (mem) return mem;
  if (!inflight) {
    inflight = (async () => {
      const g = wipeGen;
      /* atomic+.bak read — a torn main falls back to the previous good
         generation instead of reading as never-seen (the replay bug) */
      const j = await readJsonDoc(NAME, (v): v is Partial<ConsentState> =>
        !!v && typeof v === "object");
      if (g !== wipeGen || mem !== null) {
        // wiped mid-read, or a writer won the race while we parsed
        if (mem) return mem;
        return EMPTY;
      }
      mem = j ? sanitize(j) : EMPTY;
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
    if (mem === null) return next;  // wiped mid-merge — don't resurrect
    mem = next;
    writeJsonDoc(NAME, mem);        // atomic rename + .bak (safefile)
    return next;
  });
  writeTail = p.catch(() => {});
  return p;
}

/** "Delete my data" seam — call from settings.clearAllData() so wiping the
 *  phone also wipes this file and re-arms the gate on next launch. Mirrors
 *  drop too (null = wiped), or a queued save would resurrect the file. */
export function clearConsent(): void {
  wipeGen += 1;
  mem = null;
  inflight = null;
  purgeJsonDoc(NAME); // main + .tmp + .bak — a wiped phone keeps no copy
}

/** Test seam — drop the in-memory mirror so the next load re-reads disk
 *  (same convention as resetDaylogCache/resetLedgerCache). Simulates a
 *  relaunch without touching the file. */
export function resetConsentCache(): void {
  mem = null;
  inflight = null;
}
