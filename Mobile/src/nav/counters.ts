/**
 * Live counters (doc 04 §5, doc 06 §1–2) — pure 1 Hz math, NO network.
 *
 *   dose_ug += C(alongM) · ME(mode) · VE(mode)[m³/s] · dt
 *   rate_g_s = max(idle_g_s, ef_g_km · v/1000)          (v = GNSS speed)
 *   out_g   += rate · dt · coldFactor(kmDriven) / occupancy
 *
 * Bands are carried end to end — lo, mid, hi always — never collapsed.
 * Shared/per-pkm modes (metro) integrate by distance only: no idle,
 * no cold-start, occupancy already baked into the pkm factor.
 */

import type { Band, EmissionCurve } from "./strip";

/** Measured Delhi microenvironment ratios + minute ventilation —
 *  mirror of server/exposure.py MICROENV/VENTILATION_LPM (Goel et al.
 *  2015 fixed-arterial exceedances, Apte et al. 2011 in-rickshaw ratio,
 *  Zuurbier 2009 measured passenger VE; Sci. Total Environ. 2021,
 *  Discover Atmosphere 2025). Keyed by the route `mode` the server
 *  stores on the route record (car, car_open, bike, auto, bus, metro,
 *  cycle, walk). Unknown modes fall back to open-air ambient — honest.
 *  Oct-2026 re-audit: open/shared modes and seated VE raised to the
 *  measured band (walk 1.0→1.3, car_open 0.8→1.0, bus 0.7→0.9,
 *  bike 1.1→1.2, auto 1.15→1.3, seated VE 7.5–9→10–10.5). */
export const ME_VE: Record<string, { me: number; veLpm: number }> = {
  metro: { me: 0.45, veLpm: 10.0 },
  car: { me: 0.55, veLpm: 10.0 },
  car_open: { me: 1.0, veLpm: 10.0 },
  bus: { me: 0.9, veLpm: 10.0 },
  bike: { me: 1.2, veLpm: 10.5 },
  auto: { me: 1.3, veLpm: 10.0 },
  cycle: { me: 1.1, veLpm: 22.0 },
  walk: { me: 1.3, veLpm: 14.0 },
};
const ME_VE_DEFAULT = { me: 1.0, veLpm: 10.0 };

/** Seated-rest ventilation — the dose profile while a fix-gap says
 *  "we can't see the ride" (backgrounded, parked, GNSS dead). You
 *  kept breathing the air where you stopped, so dose keeps counting,
 *  but not at an effort rate: a parked cyclist isn't working at
 *  22 L/min. Modes already at/below rest keep their VE. */
export const REST_VE_LPM = 10.0;

/** Cold-start uplift tapers linearly from (1+COLD_UPLIFT) at km 0 to
 *  1.0 at cold_start_km. Magnitude is an est. inside the class band —
 *  server only ships the distance param (strip.py _emission_curve). */
export const COLD_UPLIFT = 0.35;

/** PM share of the idle fuel-burn rate — mirrors the `idle_g * 0.004`
 *  term in server/v2/plan.py _emission_band. */
export const PM_IDLE_SHARE = 0.004;

const ZERO: Band = { lo: 0, mid: 0, hi: 0 };
const clone = (b: Band): Band => ({ lo: b.lo, mid: b.mid, hi: b.hi });

export type ConcBand = { lo: number | null; mid: number | null; hi: number | null };

export class LiveCounters {
  /** inhaled PM2.5, µg */
  doseUg: Band = clone(ZERO);
  /** tailpipe CO2, grams (display divides by 1000 → kg) */
  co2G: Band = clone(ZERO);
  /** tailpipe PM2.5, grams */
  pm25G: Band = clone(ZERO);
  /** distance accumulated under the emission integrator, metres */
  travelledM = 0;

  reset(): void {
    this.doseUg = clone(ZERO);
    this.co2G = clone(ZERO);
    this.pm25G = clone(ZERO);
    this.travelledM = 0;
  }

  /** One tick. dtS measured (never assumed), speed in m/s, ddM the
   *  along-route distance covered since last tick (≥0), conc the strip
   *  band at the snapped position. `gap` marks a tick whose interval
   *  had no position stream behind it (engine.ts FIX_GAP_S): dose
   *  accrues at rest ventilation — the air kept hitting — while the
   *  ride's emissions pause. Minting drive-rate CO2 for a minutes-long
   *  gap at the last observed speed was the lifecycle-drive bug
   *  (19 g → 172 g across one 4.6 min park). */
  tick(
    dtS: number,
    speedMps: number,
    ddM: number,
    conc: ConcBand,
    curve: EmissionCurve | null | undefined,
    mode: string,
    gap = false,
  ): void {
    if (!(dtS > 0)) return;
    const { me, veLpm } = ME_VE[mode] ?? ME_VE_DEFAULT;
    const veM3s = (gap ? Math.min(veLpm, REST_VE_LPM) : veLpm) / 60000; // L/min → m³/s
    // breath — each edge independently; null C edge stays put
    const cMid = conc.mid ?? conc.lo ?? conc.hi; // last-resort edge fill
    const add = (c: number | null, fb: number | null) =>
      (c ?? fb) == null ? 0 : (c ?? fb)! * me * veM3s * dtS;
    this.doseUg.lo += add(conc.lo, cMid);
    this.doseUg.mid += add(conc.mid, conc.lo ?? conc.hi);
    this.doseUg.hi += add(conc.hi, cMid);

    // odometer is independent of the emissions curve — a strip failure
    // must not zero the receipt's distance (testnav F1)
    const ddKm = Math.max(0, ddM) / 1000;
    /* speed: GNSS `speedMps` when present, else derived from along-route
       distance — providers without a speed channel (and the emulator's
       test provider) report v=0 while the position still moves, which
       used to collapse every moving leg to idle×time (a real 4 km drive
       printed 0.00 kg). ddM is map-snapped, so ddM/dtS is the honest
       effective speed; capped at 45 m/s (~160 km/h) so a snapped-fix
       jump can't flash an absurd rate into the bands. */
    const vDerived = ddM / dtS;
    /* speedMps (GNSS-reported) is primary; derived covers the GNSS
       speed-dropout case. max()-ing them lets a single location jump
       pin v at the 45 clamp — a GNSS spike would count 4.5× the real
       rate into dose/CO2 (c84b5c2's "exhaust needs no GNSS speed" was
       a fallback, not a max). */
    const v = Math.min(45, speedMps && speedMps > 0
      ? speedMps
      : Math.max(0, vDerived));
    this.travelledM += Math.max(0, ddM);
    const km = this.travelledM / 1000;
    /* gap → the odometer still takes real measured distance, but the
       exhaust ledger pauses: whether the engine idled, ran, or was off
       is unknowable without fixes, so nothing is minted. */
    if (!curve || gap) return;

    if (curve.co2_g_pkm) {
      // shared mode: per passenger-km, no idle/cold (doc 06 §2)
      const c = curve.co2_g_pkm;
      const p = curve.pm25_g_pkm;
      this.co2G.lo += (c?.lo ?? 0) * ddKm;
      this.co2G.hi += (c?.hi ?? 0) * ddKm;
      this.co2G.mid = (this.co2G.lo + this.co2G.hi) / 2;
      this.pm25G.lo += (p?.lo ?? 0) * ddKm;
      this.pm25G.hi += (p?.hi ?? 0) * ddKm;
      this.pm25G.mid = (this.pm25G.lo + this.pm25G.hi) / 2;
      return;
    }

    const coldKm = curve.cold_start_km ?? 0;
    const cold = coldKm > 0 ? 1 + COLD_UPLIFT * Math.max(0, 1 - km / coldKm) : 1;
    const occ = curve.occupancy && curve.occupancy > 0 ? curve.occupancy : 1;
    const idle = curve.idle_g_s ?? 0;

    /* per-tick moving add = ef × max(measured km, speed-implied km).
       The two terms agree on a normal tick (ddM ≈ v·dt); the ddKm
       term is what makes a lost-fix JUMP honest: engine caps credited
       distance at a plausible speed over the fix-gap, and that
       credited km lands in ONE tick — emitting only v·dt for it would
       count ~45 m of a real 2 km leg. When snaps can't measure (GNSS
       speed but no strip progress) the v·dt term covers it as before.
       Idle floor unchanged: standing time still emits idle_g_s. */
    const moveAdd = (efPerKm: number, idleRate: number) =>
      Math.max(idleRate * dtS, efPerKm * Math.max(ddKm, (v * dtS) / 1000)) * cold;
    if (curve.co2_g_km) {
      this.co2G.lo += moveAdd(curve.co2_g_km.lo, idle) / occ;
      this.co2G.hi += moveAdd(curve.co2_g_km.hi, idle) / occ;
      this.co2G.mid = (this.co2G.lo + this.co2G.hi) / 2;
    }
    if (curve.pm25_g_km) {
      const pmIdle = idle * PM_IDLE_SHARE;
      this.pm25G.lo += moveAdd(curve.pm25_g_km.lo, pmIdle) / occ;
      this.pm25G.hi += moveAdd(curve.pm25_g_km.hi, pmIdle) / occ;
      this.pm25G.mid = (this.pm25G.lo + this.pm25G.hi) / 2;
    }
  }
}
