/** Day-sum rollup — the on-device analytics engine (docs/lanes/pocket-engine).
 *
 *  What it is: one persisted record per local day — the day's dose
 *  reconstruction, its trip/stay split, per-mode totals, coverage — built
 *  ONLY from the real inputs already on the phone (daylog samples, ledger
 *  trips). It is a cache of truths, never a source of new numbers: every
 *  figure is `reconstructDay` output computed once per input-change and
 *  then sealed. Nothing is recomputed per render, and nothing is
 *  fabricated — a day with no samples and no trips reads thin/zero, the
 *  same honesty rule the live path has always used.
 *
 *  How it stays fresh without callers remembering anything: this module
 *  subscribes to the stores' own mutation hooks at import time —
 *  logTrip/deleteTrip/recordSample mark exactly their day dirty;
 *  clearTrips marks all. Reads seal lazily: getDay recomputes a day only
 *  when it is missing, dirty, sealed mid-day and the day has since ended
 *  (partial → final), still running today (volatile by definition), or
 *  storing part-labels in another language. The dirty set is persisted,
 *  so a kill between "source file written" and "rollup refreshed" still
 *  re-seals on the next read.
 *
 *  Bounds (the low-RAM contract):
 *   - ≤ MAX_DAYS day records — ~13 months of history, FIFO.
 *   - hour arcs (24 slots each) kept only for the last ARC_KEEP_DAYS —
 *     the week strip never reaches further; older days keep totals,
 *     parts and coverage, which is all the symptom lens reads.
 *   - file is one checksummed envelope (safefile): corrupt main → .bak;
 *     corrupt both → honest empty, never garbage rendered as dose.
 *   - wipe-generation guard like outbox/cache: a read that started
 *     before delete-my-data cannot resurrect the file after.
 *   - "delete my data" → resetDaySum() purges file + .tmp + .bak.
 *
 *  What it never does: upload, raw-trace, or invent. The only numbers in
 *  daysum.json are arithmetic over daylog.json + ledger.json. */
import {
  allSamples,
  dayKey,
  onDaylogMutation,
  reconstructDay,
  type DayReconstruction,
} from "./daylog";
import { loadTrips, onLedgerMutation } from "./ledger";
import { purgeJsonDoc, readJsonDoc, writeJsonDoc } from "./safefile";
import type { Lang } from "../i18n/strings";

const NAME = "daysum.json";

/** ~13 months of per-day rollups — check-ins cap at 120 days, so the
 *  symptom lens's full look-back is always covered. */
const MAX_DAYS = 400;
/** Hour-by-hour arcs are only ever rendered for the trailing week —
 *  keep the slots for a margin of days, prune beyond. */
const ARC_KEEP_DAYS = 14;

/** One sealed day. `rec` is verbatim reconstructDay output; the rollup
 *  adds the splits the store itself doesn't keep. */
export type DaySum = {
  /** the day's reconstruction — arc is [] once the day ages past
   *  ARC_KEEP_DAYS (arcPruned says so; totals/parts/coverage stay full) */
  rec: DayReconstruction;
  /** inhaled µg from logged trips (dose_ug>0 rows only, same gate as
   *  reconstructDay) — rec.totalUg = trip_ug + stay_ug exactly */
  trip_ug: number;
  /** inhaled µg from covered stay spans (ambient interpolation) */
  stay_ug: number;
  /** all ledger rows on this day — including 0-dose trips the rec skips */
  trips: number;
  /** per-mode split {rides, inhaled µg} — the "how do I usually move"
   *  answer, computed from the same real rows */
  modes: Record<string, { n: number; ug: number }>;
  /** language the stored part labels were rendered in — a mismatch on
   *  read re-seals the day so a lang flip never shows frozen labels */
  lang: Lang;
  /** epoch ms when this record was computed */
  at: number;
  /** true when the seal ran while the day was still in progress — the
   *  first read after that day ends re-seals it final (arc to hour 23) */
  partial: boolean;
  /** arc was pruned for age — totals/parts are complete regardless */
  arcPruned?: boolean;
};

type DaySumData = { days: Record<string, DaySum>; dirty: string[] };

let mem: DaySumData | null = null;
let inflight: Promise<DaySumData> | null = null;
let writeTail: Promise<unknown> = Promise.resolve();
/* wipe generation — the outbox/cache pattern: a disk read or queued
   write that started before delete-my-data must not land after it. */
let wipeGen = 0;

/* invalidations that arrived before the first disk read — merged in
   readDisk so an early mutation can't be lost to a slow boot */
const earlyDirty = new Set<string>();
let earlyAllDirty = false;

const validData = (v: unknown): v is DaySumData =>
  v != null && typeof v === "object" &&
  typeof (v as DaySumData).days === "object" &&
  Array.isArray((v as DaySumData).dirty);

function mergeDirty(d: DaySumData): boolean {
  let changed = false;
  if (earlyAllDirty) {
    d.dirty = [...new Set([...d.dirty, ...Object.keys(d.days)])];
    earlyAllDirty = false;
    changed = true;
  }
  if (earlyDirty.size) {
    d.dirty = [...new Set([...d.dirty, ...earlyDirty])];
    earlyDirty.clear();
    changed = true;
  }
  return changed;
}

/** Retention: drop the oldest day keys past MAX_DAYS, prune arcs past
 *  ARC_KEEP_DAYS. Mutates `d` in place. */
function prune(d: DaySumData): void {
  const keys = Object.keys(d.days).sort(); // ISO keys sort chronologically
  while (keys.length > MAX_DAYS) {
    const k = keys.shift()!;
    delete d.days[k];
  }
  const cutoff = dayKey(Date.now() - ARC_KEEP_DAYS * 86400000);
  for (const k of keys) {
    if (k >= cutoff) continue;             // ISO strings compare as dates
    const s = d.days[k];
    if (s && s.rec.arc.length > 0) {
      s.rec = { ...s.rec, arc: [] };
      s.arcPruned = true;
    }
  }
}

async function readDisk(): Promise<DaySumData> {
  if (mem) return mem;
  const gen = wipeGen;
  const j = await readJsonDoc<DaySumData>(NAME, validData, { checksum: true });
  if (gen !== wipeGen) return { days: {}, dirty: [] }; // wiped mid-read — don't resurrect
  mem = j ?? { days: {}, dirty: [] };
  mergeDirty(mem);
  prune(mem);
  return mem;
}

function ensureMem(): Promise<DaySumData> {
  if (mem) return Promise.resolve(mem);
  if (!inflight) inflight = readDisk();
  return inflight;
}

function scheduleWrite(): void {
  writeTail = writeTail
    .then(() => {
      if (mem === null) return; // wiped — a queued flush must not resurrect it
      writeJsonDoc(NAME, mem, { checksum: true });
    })
    .catch(() => {});
}

/** Mark one day's rollup stale. Public so tests can force it; production
 *  callers arrive through the ledger/daylog mutation hooks below. The
 *  mark is persisted at once — a kill before the next read still finds
 *  the day dirty at boot. */
export function invalidateDay(day: string): void {
  if (!mem) {
    earlyDirty.add(day);
    // merges into the loaded data (and gets persisted by the seal writes)
    void ensureMem().catch(() => {});
    return;
  }
  if (!mem.dirty.includes(day)) {
    mem.dirty.push(day);
    scheduleWrite();
  }
}

/** Every stored day is stale (clearTrips) — re-seal lazily per access. */
export function invalidateAllDays(): void {
  if (!mem) {
    earlyAllDirty = true;
    void ensureMem().catch(() => {});
    return;
  }
  mem.dirty = [...new Set([...mem.dirty, ...Object.keys(mem.days)])];
  scheduleWrite();
}

/* the engine's own wiring: stores announce their mutations; we translate
   them into dirty marks. No app call-site ever invalidates by hand. */
onLedgerMutation((e) => {
  if (e.day) invalidateDay(e.day);
  else invalidateAllDays();
});
onDaylogMutation((e) => {
  if (e.day) invalidateDay(e.day);
});

const endOfDayTs = (k: string) => new Date(`${k}T23:59:59`).getTime();

/* NOTE: reconstructDay's per-day bound is "now" for today, 23:59:59 for
   a finished day — the same rule useDayData ran before this store. */
async function computeDay(k: string, lang: Lang): Promise<DaySum> {
  const [samples, trips] = await Promise.all([allSamples(), loadTrips()]);
  const now = Date.now();
  const today = k === dayKey(now);
  const rec = reconstructDay(k, samples, trips, today ? now : endOfDayTs(k), lang);
  const modes: Record<string, { n: number; ug: number }> = {};
  let tripUg = 0;
  let n = 0;
  for (const t of trips) {
    if (dayKey(t.ts) !== k) continue;
    n++;
    const m = modes[t.vehicle] ?? { n: 0, ug: 0 };
    m.n++;
    if (t.dose_ug > 0) m.ug += t.dose_ug;
    modes[t.vehicle] = m;
    if (t.dose_ug > 0) tripUg += t.dose_ug;
  }
  const r10 = (x: number) => Math.round(x * 10) / 10;
  return {
    rec,
    trip_ug: r10(tripUg),
    stay_ug: r10(rec.totalUg - tripUg),
    trips: n,
    modes,
    lang,
    at: now,
    partial: today,
  };
}

/** One sealed day. Recomputes only when stale; persists the seal. */
export async function getDay(k: string, lang: Lang = "en"): Promise<DaySum> {
  const d = await ensureMem();
  const today = k === dayKey(Date.now());
  const cur = d.days[k];
  const stale =
    cur == null ||
    today ||                                   // today is volatile by definition
    d.dirty.includes(k) ||
    cur.lang !== lang ||                       // part labels are lang-rendered
    (cur.partial && Date.now() > endOfDayTs(k)); // mid-day seal → final seal
  if (!stale) return cur;
  const next = await computeDay(k, lang);
  d.days[k] = next;
  d.dirty = d.dirty.filter((x) => x !== k);
  prune(d);
  scheduleWrite();
  return next;
}

/** Batch read — the week strip and the symptom lens ask in sets. */
export async function getDays(
  ks: string[], lang: Lang = "en",
): Promise<Record<string, DaySum>> {
  const out: Record<string, DaySum> = {};
  for (const k of ks) out[k] = await getDay(k, lang);
  return out;
}

/** "Delete my data" — drop the mirror AND every byte on disk
 *  (file + .tmp + .bak); the generation bump kills any read or queued
 *  write still in flight. Called from settings.clearAllData(). */
export function resetDaySum(): void {
  wipeGen++;
  mem = null;
  inflight = null;
  earlyDirty.clear();
  earlyAllDirty = false;
  purgeJsonDoc(NAME);
}
