import { afterFirstFrame } from "../startup/idle";
import { readJsonDoc, writeJsonDoc } from "./safefile";

// cigarette equivalence: Berkeley Earth rule of thumb — 22 µg/m³ ambient
// PM2.5 over a day ≈ one cigarette; at ~14.4 m³/day inhaled volume that is
// ≈316 µg inhaled per cigarette-equivalent.
const CIG_UG = 316;
// WHO 2021 24-h PM2.5 guideline 15 µg/m³ × ~14.4 m³ inhaled/day.
const BUDGET_UG = 216;
/* on-disk: <document>/ledger.json via safefile — bare trip array
   (documented format other lanes read raw), atomic rename + .bak */
const MAX_TRIPS = 500; // persisted bound — every write truncates to this

export type Trip = {
  ts: number;
  label: string;
  vehicle: string;
  dose_ug: number;
  avoided_ug: number;
  from: string;
  to: string;
  fromLat?: number;
  fromLon?: number;
  toLat?: number;
  toLon?: number;
  // SEAM(emissions): kg the ride put out — rows predate the field, so it
  // stays optional and is only rendered when present (doc 02 §4).
  emit_kg?: number;
  // SEAM(bands): dose band when the logged estimate carries σ — doc 10
  // allows lo/mid/hi at details level; never fabricated from the point dose.
  dose_lo_ug?: number;
  dose_hi_ug?: number;
  // SEAM(donation): set when this traversal was donated to the shared field.
  donated?: boolean;
};

/* ---- in-memory mirror + deferred first read + serialized writes ----
   perf (r4): ledger.json is read+parsed once per launch, on the first real
   call — and that call is scheduled after the first frame so JSON.parse
   can't block the mount/font window. Every later call is a slice() off
   `mem`. Writes funnel through one tail promise: read-modify-write cycles
   can't interleave, and a burst lands last-state-wins in a single write. */
let mem: Trip[] | null = null;
let inflight: Promise<Trip[]> | null = null;
let writeTail: Promise<unknown> = Promise.resolve();
/* wipe generation — a read that STARTED before delete-my-data must not
   repopulate the mirror after it (the outbox/cache guard). */
let wipeGen = 0;

async function readDisk(): Promise<Trip[]> {
  await afterFirstFrame(); // trip history isn't frame-1 data — let the mount win
  if (mem) return mem;     // a writer (clearTrips/deleteTrip) won while we waited
  const gen = wipeGen;
  /* safefile: bare array format unchanged (drive lanes read it raw via
     adb/simctl); the .bak fallback covers a torn/corrupt main file. */
  const t = await readJsonDoc<Trip[]>("ledger.json",
    (v): v is Trip[] => Array.isArray(v));
  if (gen !== wipeGen || mem !== null) {
    if (mem) return mem;   // wiped mid-read, or a writer won the race
    return [];
  }
  mem = t ? t.slice(-MAX_TRIPS) : [];
  return mem;
}

/** The authoritative array — internal callers mutate `mem`, external
 *  callers only ever get a copy via loadTrips(). */
function ensureMem(): Promise<Trip[]> {
  if (mem) return Promise.resolve(mem);
  if (!inflight) inflight = readDisk();
  return inflight;
}

/** Persist current `mem` — serialized through writeTail. Skipped when the
 *  mirror is null (post-clearAllData) so a queued flush can't recreate a
 *  file the user just wiped. */
function scheduleWrite(): void {
  writeTail = writeTail
    .then(() => {
      if (mem === null) return;
      /* atomic tmp→rename + .bak of the previous good generation
         (safefile) — a crash mid-write can no longer zero the ledger */
      writeJsonDoc("ledger.json", mem.slice(-MAX_TRIPS));
    })
    .catch(() => {});
}

/* ---- mutation listeners ---------------------------------------------------
 * The day-rollup engine (daysum.ts) subscribes here so a ledger change
 * marks exactly one day dirty — no caller has to remember to invalidate.
 * `day` is the ISO day key (YYYY-MM-DD, daylog's convention); null means
 * the whole history changed (clearTrips). */
export type LedgerMutation = { day: string | null };
const listeners = new Set<(e: LedgerMutation) => void>();
export function onLedgerMutation(cb: (e: LedgerMutation) => void): () => void {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}
function fire(day: string | null): void {
  for (const cb of [...listeners]) {
    try {
      cb({ day });
    } catch {}
  }
}
const isoDay = (ts: number) => {
  const d = new Date(ts);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

export async function loadTrips(): Promise<Trip[]> {
  return (await ensureMem()).slice(); // a copy — callers must not mutate mem
}

export async function logTrip(t: Trip): Promise<Trip[]> {
  /* No dedupe — deliberately. The nav engine's arrivedRef already
     guarantees one arrival callback per session, and the old 10-min
     same-name keep-first suppression only ever masked phantom-arrival
     noise while silently eating real trips: two genuine rides with the
     same O&D inside the window merged into one row (app-stress F2), and
     the key itself was locale-fragile (from/to are display strings that
     change with the app language). A ledger must never drop a real
     trip — every completed ride lands as its own row. */
  const trips = await ensureMem();
  trips.push(t);
  scheduleWrite();
  fire(isoDay(t.ts));
  return trips.slice();
}

const dayKey = (ts: number) => new Date(ts).toDateString();

export function stats(trips: Trip[], now = new Date(), budgetUg = BUDGET_UG) {
  /* one pass: day → {ug, avoided, rows}; the old version ran four scans
     per call (today filter, all-time reduce, byDay map, then a per-day
     filter inside weekStats callers) — same answers, one walk.
     streak/budgetPct take the caller's profile budget — the hardcoded
     general-budget version read a 216-day as "good" for a 72-µg
     sensitive profile (numbers-sweep: latent lie in dead fields). */
  type DayAcc = { ug: number; avoided: number; rows: Trip[] };
  const byDay = new Map<string, DayAcc>();
  let allAvoided = 0;
  const todayK = dayKey(now.getTime());
  for (const t of trips) {
    const k = dayKey(t.ts);
    const acc = byDay.get(k) ?? { ug: 0, avoided: 0, rows: [] };
    acc.ug += t.dose_ug;
    acc.avoided += t.avoided_ug;
    acc.rows.push(t);
    byDay.set(k, acc);
    allAvoided += t.avoided_ug;
  }
  const todayAcc = byDay.get(todayK);
  const todayUg = todayAcc?.ug ?? 0;
  const avoidedUg = todayAcc?.avoided ?? 0;
  const today = todayAcc?.rows ?? [];

  let streak = 0;
  const d = new Date(now);
  if (todayUg > 0 && todayUg < budgetUg) streak++;
  else if (todayUg === 0 && byDay.size > 0) streak++;
  for (;;) {
    d.setDate(d.getDate() - 1);
    const v = byDay.get(dayKey(d.getTime()));
    if (v === undefined) break;
    if (v.ug < budgetUg) streak++;
    else break;
  }

  return {
    todayUg: Math.round(todayUg * 10) / 10,
    avoidedUg: Math.round(avoidedUg * 10) / 10,
    allAvoidedUg: Math.round(allAvoided * 10) / 10,
    cigEq: Math.round((todayUg / CIG_UG) * 100) / 100,
    budgetUg,
    budgetPct: Math.min(999, Math.round((todayUg / budgetUg) * 100)),
    streak,
    today,
  };
}

/** Last-7-days rollup for the journey drawer. `weekday:"narrow"` is the
 *  CLDR one-glyph label — en gives "M T W…", hi gives "सो मं बु…" — and
 *  slicing short names would split Devanagari aksharas mid-glyph. */
export function weekStats(trips: Trip[], now = new Date(), lang = "en") {
  /* one pass instead of seven filters — the per-day numbers are the
     same, the work is O(n) not O(7n) */
  const byDay = new Map<string, { ug: number; avoided: number; n: number }>();
  for (const t of trips) {
    const k = dayKey(t.ts);
    const acc = byDay.get(k) ?? { ug: 0, avoided: 0, n: 0 };
    acc.ug += t.dose_ug;
    acc.avoided += t.avoided_ug;
    acc.n++;
    byDay.set(k, acc);
  }
  const days: { label: string; ug: number; trips: number; avoided: number }[] = [];
  for (let i = 6; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    const acc = byDay.get(dayKey(d.getTime()));
    days.push({
      label: d.toLocaleDateString(lang === "hi" ? "hi-IN" : "en-IN", { weekday: "narrow" }),
      ug: Math.round((acc?.ug ?? 0) * 10) / 10,
      trips: acc?.n ?? 0,
      avoided: Math.round((acc?.avoided ?? 0) * 10) / 10,
    });
  }
  const weekUg = days.reduce((s, d) => s + d.ug, 0);
  const weekAvoided = days.reduce((s, d) => s + d.avoided, 0);
  return {
    days,
    weekUg: Math.round(weekUg * 10) / 10,
    weekAvoided: Math.round(weekAvoided * 10) / 10,
    weekCigEq: Math.round((weekUg / CIG_UG) * 100) / 100,
    totalTrips: trips.length,
  };
}

/** Remove one trip. Matched on ts + route + mode — ts alone can repeat
 *  across devices/restores. Returns the persisted list. */
export async function deleteTrip(
  match: Pick<Trip, "ts" | "from" | "to" | "vehicle">,
): Promise<Trip[]> {
  const trips = await ensureMem();
  const next = trips.filter(
    (x) =>
      !(x.ts === match.ts && x.from === match.from &&
        x.to === match.to && x.vehicle === match.vehicle),
  );
  mem = next;
  scheduleWrite();
  if (next.length < trips.length) fire(isoDay(match.ts));
  return next.slice();
}

/** "Delete all trips" — the ledger file is rewritten empty. */
export async function clearTrips(): Promise<Trip[]> {
  mem = [];
  scheduleWrite();
  fire(null); // every day's rollup is stale now
  return [];
}

/** Cache reset for settings.clearAllData() — it removes the file directly,
 *  so the mirror must drop too or wiped trips would resurrect on read. */
export function resetLedgerCache(): void {
  wipeGen++;              // a pre-wipe read resolving now is discarded
  mem = null;
  inflight = null;
}
