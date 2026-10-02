import { File, Paths } from "expo-file-system";

// cigarette equivalence: Berkeley Earth rule of thumb — 22 µg/m³ ambient
// PM2.5 over a day ≈ one cigarette; at ~14.4 m³/day inhaled volume that is
// ≈316 µg inhaled per cigarette-equivalent.
const CIG_UG = 316;
// WHO 2021 24-h PM2.5 guideline 15 µg/m³ × ~14.4 m³ inhaled/day.
const BUDGET_UG = 216;
const FILE = new File(Paths.document, "ledger.json");
const DEDUPE_MS = 10 * 60 * 1000;

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
};

export async function loadTrips(): Promise<Trip[]> {
  try {
    if (!FILE.exists) return [];
    const t = JSON.parse(await FILE.text());
    return Array.isArray(t) ? t : [];
  } catch {
    return [];
  }
}

export async function logTrip(t: Trip): Promise<Trip[]> {
  const trips = await loadTrips();
  const dup = trips.find(
    (x) => x.from === t.from && x.to === t.to && x.vehicle === t.vehicle &&
      t.ts - x.ts < DEDUPE_MS,
  );
  if (dup) {
    // backfill coords on older entries that predate them
    let changed = false;
    if (dup.fromLat == null && t.fromLat != null) { dup.fromLat = t.fromLat; dup.fromLon = t.fromLon; changed = true; }
    if (dup.toLat == null && t.toLat != null) { dup.toLat = t.toLat; dup.toLon = t.toLon; changed = true; }
    if (changed) {
      try {
        if (!FILE.exists) FILE.create();
        FILE.write(JSON.stringify(trips.slice(-500)));
      } catch {}
    }
    return trips;
  }
  trips.push(t);
  try {
    if (!FILE.exists) FILE.create();
    await FILE.write(JSON.stringify(trips.slice(-500)));
  } catch {}
  return trips;
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

/** Last-7-days rollup for the journey drawer. */
export function weekStats(trips: Trip[], now = new Date()) {
  const days: { label: string; ug: number; trips: number; avoided: number }[] = [];
  for (let i = 6; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    const day = trips.filter((t) => dayKey(t.ts) === dayKey(d.getTime()));
    days.push({
      label: d.toLocaleDateString("en-IN", { weekday: "short" }),
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
