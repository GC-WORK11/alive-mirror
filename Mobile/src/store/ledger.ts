import { File, Paths } from "expo-file-system";
import { afterFirstFrame } from "../startup/idle";

// cigarette equivalence: Berkeley Earth rule of thumb — 22 µg/m³ ambient
// PM2.5 over a day ≈ one cigarette; at ~14.4 m³/day inhaled volume that is
// ≈316 µg inhaled per cigarette-equivalent.
const CIG_UG = 316;
// WHO 2021 24-h PM2.5 guideline 15 µg/m³ × ~14.4 m³ inhaled/day.
const BUDGET_UG = 216;
const FILE = new File(Paths.document, "ledger.json");
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

async function readDisk(): Promise<Trip[]> {
  await afterFirstFrame(); // trip history isn't frame-1 data — let the mount win
  if (mem) return mem;     // a writer (clearTrips/deleteTrip) won while we waited
  try {
    if (FILE.exists) {
      const t = JSON.parse(await FILE.text());
      mem = Array.isArray(t) ? (t as Trip[]).slice(-MAX_TRIPS) : [];
      return mem;
    }
  } catch {}
  mem = [];
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
      try {
        if (!FILE.exists) FILE.create();
        FILE.write(JSON.stringify(mem.slice(-MAX_TRIPS)));
      } catch {}
    })
    .catch(() => {});
}

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
  return trips.slice();
}

const dayKey = (ts: number) => new Date(ts).toDateString();

export function stats(trips: Trip[], now = new Date()) {
  const today = trips.filter((t) => dayKey(t.ts) === dayKey(now.getTime()));
  const todayUg = today.reduce((s, t) => s + t.dose_ug, 0);
  const avoidedUg = today.reduce((s, t) => s + t.avoided_ug, 0);
  const allAvoided = trips.reduce((s, t) => s + t.avoided_ug, 0);

  const byDay = new Map<string, number>();
  for (const t of trips)
    byDay.set(dayKey(t.ts), (byDay.get(dayKey(t.ts)) ?? 0) + t.dose_ug);

  let streak = 0;
  const d = new Date(now);
  if (todayUg > 0 && todayUg < BUDGET_UG) streak++;
  else if (todayUg === 0 && byDay.size > 0) streak++;
  for (;;) {
    d.setDate(d.getDate() - 1);
    const v = byDay.get(dayKey(d.getTime()));
    if (v === undefined) break;
    if (v < BUDGET_UG) streak++;
    else break;
  }

  return {
    todayUg: Math.round(todayUg * 10) / 10,
    avoidedUg: Math.round(avoidedUg * 10) / 10,
    allAvoidedUg: Math.round(allAvoided * 10) / 10,
    cigEq: Math.round((todayUg / CIG_UG) * 100) / 100,
    budgetUg: BUDGET_UG,
    budgetPct: Math.min(999, Math.round((todayUg / BUDGET_UG) * 100)),
    streak,
    today,
  };
}

/** Last-7-days rollup for the journey drawer. `weekday:"narrow"` is the
 *  CLDR one-glyph label — en gives "M T W…", hi gives "सो मं बु…" — and
 *  slicing short names would split Devanagari aksharas mid-glyph. */
export function weekStats(trips: Trip[], now = new Date(), lang = "en") {
  const days: { label: string; ug: number; trips: number; avoided: number }[] = [];
  for (let i = 6; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    const day = trips.filter((t) => dayKey(t.ts) === dayKey(d.getTime()));
    days.push({
      label: d.toLocaleDateString(lang === "hi" ? "hi-IN" : "en-IN", { weekday: "narrow" }),
      ug: Math.round(day.reduce((s, t) => s + t.dose_ug, 0) * 10) / 10,
      trips: day.length,
      avoided: Math.round(day.reduce((s, t) => s + t.avoided_ug, 0) * 10) / 10,
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
  return next.slice();
}

/** "Delete all trips" — the ledger file is rewritten empty. */
export async function clearTrips(): Promise<Trip[]> {
  mem = [];
  scheduleWrite();
  return [];
}

/** Cache reset for settings.clearAllData() — it removes the file directly,
 *  so the mirror must drop too or wiped trips would resurrect on read. */
export function resetLedgerCache(): void {
  mem = null;
  inflight = null;
}
