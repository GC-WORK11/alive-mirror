/**
 * gap.ts — fix-gap honesty (lane nav-gap-fix).
 *
 * The nav engine's 1 Hz ticker trusts two clocks: the wall time between
 * its own ticks (realDt) and the age of the freshest GPS fix. When the
 * phone is backgrounded, parked with a dead radio, or iOS simply starves
 * the watcher, fixes stop arriving — but the last-known driving speed is
 * still sitting in the integrator. Pre-fix, one resumed tick accrued the
 * whole silent stretch as "driving": dose tripled (defensible — the air
 * kept hitting) while emissions claimed ~0.9 km of parked "riding".
 *
 * These are the two pure decisions the engine makes on that data:
 *
 *   classifyGap — is the stream blind right now? true while either clock
 *     says the fixes stopped flowing (realDt > FIX_GAP_S after a
 *     suspended resume, or fixAgeS > FIX_GAP_S while the ticker kept
 *     running but the watcher starved, or null fixAge — no fix yet at
 *     all). During a gap the counters integrate dose at the rest-VE
 *     floor and skip emissions entirely: you breathed the air where you
 *     stood, you didn't ride it anywhere. Stop-and-go traffic is NOT a
 *     gap — fixes keep flowing, speed drops, both clocks stay young.
 *
 *   jumpCreditM — how much of an observed position advance is real
 *     riding? Caps each fix's contribution at JUMP_CREDIT_MPS × the time
 *     since the previous fix (~160 km/h ceiling). A parked phone that
 *     re-locks 700 m away after 300 s gets credited 45×300 = 13.5 km of
 *     headroom — plenty for real riding that continued unsampled — but a
 *     teleport or a fix that re-locks mid-gap can never land further
 *     than physics allows in the interval it actually took.
 */

export const FIX_GAP_S = 45;
export const JUMP_CREDIT_MPS = 45;

/** Is the fix stream blind? fixAgeS null = no fix has ever landed. */
export function classifyGap(realDtS: number, fixAgeS: number | null): boolean {
  return realDtS > FIX_GAP_S || fixAgeS === null || fixAgeS > FIX_GAP_S;
}

/** Distance credit for one fix advance, capped to physically possible. */
export function jumpCreditM(advM: number, fixDtS: number): number {
  return Math.min(advM, JUMP_CREDIT_MPS * fixDtS);
}
