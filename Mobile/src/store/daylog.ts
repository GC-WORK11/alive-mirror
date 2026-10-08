/** Day log — the on-device spine of "your day in dose" (alive-depth L1/L3).
 *
 *  What it holds, and only ever on this phone:
 *   - ambient foreground samples {ts, lat, lon, amb, bz} — taken while the
 *     app is open (no background tracking: battery + the promise on the
 *     card), each one a real GET /aqi read at the position the OS reports.
 *   - the five-second symptom check-in {breath, eyes, energy} per local day.
 *
 *  What it never does: upload. Privacy is architecture — the timeline is
 *  reconstructed here, and only the existing consented k>=3 aggregates
 *  leave through the trip-donation path this file never touches.
 *  `clearAllData` deletes the file outright.
 */
import { afterFirstFrame } from "../startup/idle";
import { readJsonDoc, writeJsonDoc } from "./safefile";
import type { Trip } from "./ledger";
import { clockTight, modeLabel, placeNameLabel, type Lang } from "../i18n/strings";

/* on-disk: <document>/daylog.json via safefile — bare {samples,checkins}
   object (drive lanes read it raw), atomic rename + .bak */

/** A single ambient read while the app was in the foreground. */
export type AmbientSample = {
  ts: number;
  lat: number;
  lon: number;
  /** ambient PM2.5 at that place+time — the field's own number */
  amb: number;
  /** breathing-zone PM2.5 the server estimates you'd actually inhale
   *  standing in it (smoke×microenv composite); null when the payload
   *  didn't carry it — never back-filled with a guess */
  bz: number | null;
};

/** City fallback and old fixes/fields may inform a labelled card, not a personal log. */
export function personalAmbientSample(
  fix: { lat: number; lon: number; ts: number } | null,
  read: { amb: number | null; bz: number | null; fieldAgeS: number | null },
  now = Date.now(),
): AmbientSample | null {
  if (!fix || !Number.isFinite(fix.lat) || !Number.isFinite(fix.lon)
      || !Number.isFinite(fix.ts) || fix.ts > now || now - fix.ts > 15 * 60 * 1000
      || read.fieldAgeS == null || !Number.isFinite(read.fieldAgeS)
      || read.fieldAgeS < 0 || read.fieldAgeS > 15 * 60
      || read.amb == null || !Number.isFinite(read.amb) || read.amb < 0) return null;
  return { ts: now, lat: fix.lat, lon: fix.lon, amb: read.amb,
    bz: read.bz != null && Number.isFinite(read.bz) && read.bz >= 0 ? read.bz : null };
}

/** One daily check-in — 0 fine · 1 meh · 2 rough, per facet. */
export type Checkin = { ts: number; breath: number; eyes: number; energy: number };

type DayLogFile = { samples: AmbientSample[]; checkins: Record<string, Checkin> };

/** Samples live 21 days — enough for the check-in correlation window,
 *  short enough that the file stays a timeline, not an archive. */
const SAMPLE_KEEP_MS = 21 * 24 * 3600 * 1000;
const MAX_SAMPLES = 4000;
/** The count needs this many of today's reads before the hero calls
 *  the day counted (one trip also counts it) — the sparse hero's
 *  "N of M samples" meter reads the same constant the gate does. */
export const THIN_SAMPLE_MIN = 3;
/** A sample can stand for a gap this long between reads — past it the
 *  timeline honestly stops claiming coverage. */
const GAP_INTERP_MS = 45 * 60 * 1000;
/** Resting/seated minute ventilation ≈ 10 L/min → 0.6 m³ breathed per hour
 *  (Zuurbier 2009 / EPA EFH seated-adult figure used app-wide). */
const VE_REST_M3H = 0.6;

let mem: DayLogFile | null = null;
let inflight: Promise<DayLogFile> | null = null;
let writeTail: Promise<unknown> = Promise.resolve();
/* wipe generation — the outbox/cache guard: a disk read that started
   before delete-my-data must not resurrect the mirror after it (the
   store lacked this — its file was deleted but mem survived, and the
   next recordSample resurrected every wiped sample + check-in). */
let wipeGen = 0;

async function readDisk(): Promise<DayLogFile> {
  await afterFirstFrame(); // the day's data is not frame-1 data — mount wins
  if (mem) return mem;
  const gen = wipeGen;
  /* safefile read: bare-object format unchanged; .bak is the rollback
     generation if the main file is torn or corrupt. */
  const j = await readJsonDoc<Partial<DayLogFile>>("daylog.json",
    (v): v is Partial<DayLogFile> => v != null && typeof v === "object");
  if (gen !== wipeGen || mem !== null) {
    // wiped mid-read, or a writer won the race while we parsed
    if (mem) return mem;
    return { samples: [], checkins: {} };
  }
  mem = {
    samples: j && Array.isArray(j.samples) ? j.samples : [],
    checkins: j?.checkins && typeof j.checkins === "object" ? j.checkins : {},
  };
  return mem;
}

/** "Delete my data" — the file is removed by clearAllData; the mirror
 *  must drop here too or the next write resurrects every wiped row. */
export function resetDaylogCache(): void {
  wipeGen++;
  mem = null;
  inflight = null;
}

function ensureMem(): Promise<DayLogFile> {
  if (mem) return Promise.resolve(mem);
  if (!inflight) inflight = readDisk();
  return inflight;
}

function scheduleWrite(): void {
  writeTail = writeTail
    .then(() => {
      if (mem === null) return; // wiped — a queued flush must not resurrect it
      writeJsonDoc("daylog.json", mem); // atomic rename + .bak (safefile)
    })
    .catch(() => {});
}

/* ---- mutation listeners ---------------------------------------------------
 * daysum.ts subscribes so an appended sample marks its day dirty — no
 * caller has to remember. Check-ins don't change dose reconstruction,
 * so setCheckin does not fire; only sample appends do. */
const listeners = new Set<(e: { day: string }) => void>();
export function onDaylogMutation(cb: (e: { day: string }) => void): () => void {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}
function fire(day: string): void {
  for (const cb of [...listeners]) {
    try {
      cb({ day });
    } catch {}
  }
}

/** Local calendar-day key — the check-in and the arc both bucket by it. */
export const dayKey = (ts: number) => {
  const d = new Date(ts);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

/** Record a foreground ambient read. Dedupes: a read <8 min old at a spot
 *  inside ~0.9 km carries no new information — the file stays sparse. */
export async function recordSample(s: AmbientSample): Promise<boolean> {
  const d = await ensureMem();
  const last = d.samples[d.samples.length - 1];
  if (last && s.ts - last.ts < 8 * 60 * 1000) {
    const dlat = Math.abs(s.lat - last.lat), dlon = Math.abs(s.lon - last.lon);
    // Manhattan-degree gate: 0.008° ≈ 0.9 km N-S, ~0.6 km diagonal
    if (dlat + dlon < 0.008) return false; // ~0.9 km + fresh — nothing learned
  }
  d.samples.push(s);
  // bounded: oldest beyond the keep-window drop off the tail first
  const cutoff = s.ts - SAMPLE_KEEP_MS;
  if (d.samples.length > MAX_SAMPLES || d.samples[0].ts < cutoff) {
    d.samples = d.samples.filter((x) => x.ts >= cutoff).slice(-MAX_SAMPLES);
  }
  scheduleWrite();
  fire(dayKey(s.ts)); // this sample's day rollup is stale now
  return true;
}

/** Write today's check-in (same-day overwrite is an edit, not a second
 *  entry — the day keeps one answer per facet). */
export async function setCheckin(ts: number, c: Omit<Checkin, "ts">): Promise<void> {
  const d = await ensureMem();
  d.checkins[dayKey(ts)] = { ...c, ts };
  // keep ~120 days of answers — the correlation never looks further
  const keys = Object.keys(d.checkins).sort();
  while (keys.length > 120) {
    const k = keys.shift()!;
    delete d.checkins[k];
  }
  scheduleWrite();
}

export async function getCheckins(): Promise<Record<string, Checkin>> {
  const d = await ensureMem();
  return { ...d.checkins };
}

export async function allSamples(): Promise<AmbientSample[]> {
  return (await ensureMem()).samples.slice();
}

/* ---- the reconstruction ------------------------------------------------
 * A "covered segment" is a stretch of the day where we know where you were:
 * between two foreground reads ≤45 min apart the concentration interpolates
 * between the two real readings (reconstruction, not invention — both ends
 * are measured); a lone read covers only a point on the arc, no span.
 * Trips contribute their real logged dose — those numbers were measured
 * against the route strip at travel time. Everything else is shown as
 * uncovered: the arc leaves it blank instead of inventing exposure. */

export type ArcHour = {
  hour: number;                 // local hour 0..23
  /** ambient µg/m³ attributable to this hour, when covered */
  conc: number | null;
  /** inhaled µg attributable to this hour (stays + trips) */
  dose_ug: number;
  covered: boolean;
  trip_marks: number;           // real trip endpoints landing in this hour
};

/* weighted-mean accumulation per hour — segments can overlap hour
   boundaries, so conc is accrued per covered minute, not overwritten */
type Acc = { wMin: number; concW: number };

export type DayReconstruction = {
  day: string;
  /** 24 slots, past+present hours only */
  arc: ArcHour[];
  /** inhaled µg so far — sum over covered spans + real trip doses */
  totalUg: number;
  /** hours of the day the phone could actually account for */
  coveredMin: number;
  /** top contributors, most µg first — stays labelled by their window,
   *  trips by their real route names */
  parts: { label: string; ug: number }[];
  /** concentration samples still sparse enough to call the day thin */
  thin: boolean;
  /** ambient reads inside this day — the sparse hero's progress meter
   *  (N of THIN_SAMPLE_MIN) and the only honest 'how far along' it can
   *  show; named *Today because the hero's rec is always today */
  samplesToday: number;
};

/** Reconstruct one local day from samples + trips. Now bounds it —
 *  hours in the future are never claimed. */
export function reconstructDay(
  day: string, samples: AmbientSample[], trips: Trip[], now = Date.now(),
  /** parts labels re-render in the UI language — stored mode labels and
   *  sentinel place names are save-time English by design */
  lang: Lang = "en",
): DayReconstruction {
  const hours: ArcHour[] = Array.from({ length: 24 }, (_, h) => ({
    hour: h, conc: null, dose_ug: 0, covered: false, trip_marks: 0,
  }));

  // stays: pairs of consecutive samples; a pair spanning ≤45 min covers
  // the gap at the linear ramp between the two measured breathing-zone
  // (or ambient-only) values. Segments are clipped to this day's window
  // so a midnight-crossing stay never writes into the wrong hour slot.
  const dayStart = new Date(`${day}T00:00:00`).getTime();
  const dayEnd = Math.min(dayStart + 24 * 3600 * 1000, now);
  const segs: { t0: number; t1: number; c0: number; c1: number }[] = [];
  const conc = (s: AmbientSample) => s.bz ?? s.amb; // prefer breathing-zone; ambient when absent
  for (let i = 0; i < samples.length; i++) {
    const a = samples[i];
    const b = samples[i + 1];
    if (!b) break;
    // pairs that overlap the day at all — a read just before midnight
    // can still cover the start of this day
    if (a.ts >= dayEnd || b.ts <= dayStart) continue;
    const gap = b.ts - a.ts;
    if (gap <= 0 || gap > GAP_INTERP_MS) continue;
    const t0 = Math.max(a.ts, dayStart), t1 = Math.min(b.ts, dayEnd);
    if (t1 <= t0) continue;
    // clip keeps the interpolation linear across the cut
    const c0 = conc(a) + (conc(b) - conc(a)) * ((t0 - a.ts) / gap);
    const c1 = conc(a) + (conc(b) - conc(a)) * ((t1 - a.ts) / gap);
    segs.push({ t0, t1, c0, c1 });
  }

  const acc: Acc[] = Array.from({ length: 24 }, () => ({ wMin: 0, concW: 0 }));
  let coveredMs = 0;
  for (const sg of segs) {
    coveredMs += sg.t1 - sg.t0;
    // accrue dose hour-by-hour, weighted by overlap + interpolated conc
    let t = sg.t0;
    while (t < sg.t1) {
      const h = new Date(t).getHours();
      const hourEnd = Math.min(sg.t1, new Date(new Date(t).setMinutes(60, 0, 0)).getTime());
      const span = Math.max(1, hourEnd - t);
      /* trapezoid per sub-span — the same integral `parts` and `totalUg`
         apply to the whole segment, so the arc's hour bars always sum to
         the hero number (the ledger-audit lane caught left-edge sampling
         disagreeing with the total on every ramping pair) */
      const f0 = (t - sg.t0) / (sg.t1 - sg.t0);
      const f1 = (hourEnd - sg.t0) / (sg.t1 - sg.t0);
      const cMean =
        (sg.c0 + (sg.c1 - sg.c0) * f0 + sg.c0 + (sg.c1 - sg.c0) * f1) / 2;
      const hh = hours[h];
      acc[h].wMin += span / 60000;
      acc[h].concW += cMean * span;
      hh.dose_ug += cMean * VE_REST_M3H * (span / 3600000);
      hh.covered = true;
      t = hourEnd;
    }
  }
  for (let h = 0; h < 24; h++) {
    if (acc[h].wMin > 0) hours[h].conc = acc[h].concW / (acc[h].wMin * 60000);
  }

  // trips: the logged dose lands on its hour, named in `parts`
  const parts: { label: string; ug: number }[] = [];
  let tripUg = 0;
  for (const tr of trips) {
    if (dayKey(tr.ts) !== day || !(tr.dose_ug > 0)) continue;
    const h = new Date(tr.ts).getHours();
    hours[h].dose_ug += tr.dose_ug;
    hours[h].trip_marks += 1;
    hours[h].covered = true;
    tripUg += tr.dose_ug;
    parts.push({
      label: `${modeLabel(tr.vehicle, tr.label, lang)} · ${placeNameLabel(tr.from, lang)} → ${placeNameLabel(tr.to, lang)}`,
      ug: tr.dose_ug,
    });
  }

  // stay spans as parts — labelled by their clock window (no invented
  // place names; trips already carry real names)
  for (const sg of segs) {
    const ug = ((sg.c0 + sg.c1) / 2) * VE_REST_M3H * ((sg.t1 - sg.t0) / 3600000);
    if (ug < 2) continue;
    /* the stay window prints in the app's one clock convention —
       '9:30am–1:15pm', the same form the ledger prints */
    parts.push({ label: `${clockTight(sg.t0, lang)}–${clockTight(sg.t1, lang)}`, ug });
  }
  parts.sort((a, b) => b.ug - a.ug);

  // the arc ends at the last hour the day could possibly cover — today's
  // current hour, or 23 for a day already over (a past day's evening used
  // to be dropped by slicing at *now's* clock hour)
  const endHour = Math.max(-1, Math.min(23, Math.floor((dayEnd - dayStart) / 3600000)));
  for (let h = endHour + 1; h < 24; h++) hours[h].covered = false;

  const stayOnlyUg = segs.reduce((s, sg) =>
    s + ((sg.c0 + sg.c1) / 2) * VE_REST_M3H * ((sg.t1 - sg.t0) / 3600000), 0);
  const totalUg = stayOnlyUg + tripUg;
  const coveredMin = Math.round(coveredMs / 60000) + Math.min(60, parts.filter(p => p.label.includes("→")).length * 15);
  const daySamples = samples.filter((s) => dayKey(s.ts) === day).length;
  const dayTrips = trips.filter((t) => dayKey(t.ts) === day).length;
  return {
    day,
    arc: hours.slice(0, endHour + 1),
    totalUg: Math.round(totalUg * 10) / 10,
    coveredMin,
    parts: parts.slice(0, 4),
    thin: daySamples < THIN_SAMPLE_MIN && dayTrips === 0,
    samplesToday: daySamples,
  };
}

/* ---- the symptom lens ----------------------------------------------------
 * On-device correlation between check-ins and reconstructed exposure:
 * a "rough" check-in day is any facet at 2. We compare the mean inhaled
 * estimate on the day BEFORE rough mornings vs before smooth ones —
 * lag-1 is the honest read (yesterday's air, this morning's body). */
export type LensVerdict =
  | { kind: "early"; days: number; need: number }
  | { kind: "flat"; days: number }
  | { kind: "link"; days: number; heavyUg: number; lightUg: number;
      /** the facet that most often reads rough — names the line honestly */
      facet: "breath" | "eyes" | "energy" };

export function symptomLens(
  checkins: Record<string, Checkin>,
  doseByDay: Record<string, number>,
): LensVerdict {
  const days = Object.keys(checkins).sort();
  if (days.length < 7) return { kind: "early", days: days.length, need: 7 };
  const roughPrev: number[] = [];
  const smoothPrev: number[] = [];
  const facetCount = { breath: 0, eyes: 0, energy: 0 };
  for (const k of days) {
    const c = checkins[k];
    for (const f of ["breath", "eyes", "energy"] as const) {
      if (c[f] >= 2) facetCount[f]++;
    }
    const rough = c.breath >= 2 || c.eyes >= 2 || c.energy >= 2;
    const d = new Date(`${k}T00:00:00`);
    d.setDate(d.getDate() - 1);
    const prev = doseByDay[dayKey(d.getTime())];
    if (prev == null) continue;
    (rough ? roughPrev : smoothPrev).push(prev);
  }
  const mean = (a: number[]) => a.reduce((s, x) => s + x, 0) / (a.length || 1);
  if (roughPrev.length < 2 || smoothPrev.length < 2) return { kind: "flat", days: days.length };
  const heavy = mean(roughPrev), light = mean(smoothPrev);
  const facet = (Object.entries(facetCount) as [keyof typeof facetCount, number][])
    .sort((a, b) => b[1] - a[1])[0][0];
  return heavy > light * 1.15
    ? { kind: "link", days: days.length, heavyUg: Math.round(heavy), lightUg: Math.round(light), facet }
    : { kind: "flat", days: days.length };
}
