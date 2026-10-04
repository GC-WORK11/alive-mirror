/**
 * Voice turn cues (doc 04 §4: announce at 500 m / 150 m / at turn).
 * Thin wrapper over expo-speech (SDK 57: Speech.speak(text, {language}),
 * Speech.stop()). Everything is behind an enabled flag — the engine
 * works silently without it, and if steps are absent nothing speaks.
 */

import * as Speech from "expo-speech";
import { t, type Lang } from "../i18n/strings";

const LANG_TAG: Record<Lang, string> = { en: "en-IN", hi: "hi-IN" };

/** Steps carry only instruction + distance_m (the length of that step's
 *  leg); the maneuver sits at the cumulative boundary. */
export type NavStep = { instruction: string; distance_m: number; type?: string };

export function stepBoundaryM(steps: NavStep[]): number[] {
  const out: number[] = [];
  let acc = 0;
  for (let i = 0; i < steps.length - 1; i++) {
    acc += Math.max(0, steps[i].distance_m || 0);
    out.push(acc);
  }
  return out;
}

const CUE_M = [500, 150, 0] as const;

/* A fix this far past a boundary means the turn already happened (GPS
   jump, tunnel exit, nav started mid-trip): its cues are marked consumed
   without speaking — announcing a maneuver hundreds of metres late is
   worse than silence. Matches the window the 500 m cue opens ahead. */
const PASSED_M = 160;

/** Per-maneuver cue tracker — fires each threshold once. */
export class CueTracker {
  private fired: boolean[][] = [];
  private steps: NavStep[] = [];
  private bounds: number[] = [];

  load(steps: NavStep[] | null | undefined): void {
    this.steps = steps ?? [];
    this.bounds = stepBoundaryM(this.steps);
    this.fired = this.bounds.map(() => CUE_M.map(() => false));
  }

  /** Call on each fix with along-route metres; returns cues to speak. */
  poll(alongM: number, lang: Lang): string[] {
    const out: string[] = [];
    for (let i = 0; i < this.bounds.length; i++) {
      const remain = this.bounds[i] - alongM;
      const instr = this.steps[i + 1]?.instruction;
      if (!instr) continue;
      if (remain < -PASSED_M) {
        // well past: consume silently — a jump must not queue a spoken
        // "now" for every manoeuvre it leapfrogged
        for (let j = 0; j < CUE_M.length; j++) this.fired[i][j] = true;
        continue;
      }
      CUE_M.forEach((cm, j) => {
        if (this.fired[i][j]) return;
        if (cm === 0 ? remain <= 25 : remain <= cm && remain > cm - 160) {
          this.fired[i][j] = true;
          out.push(
            cm === 0
              ? t("nav_now", lang, { i: instr })
              : t("nav_in", lang, { d: cm, i: instr }),
          );
        }
      });
    }
    return out;
  }

  reset(): void {
    this.fired = this.bounds.map(() => CUE_M.map(() => false));
  }
}

export function speakCue(text: string, lang: Lang, enabled: boolean): void {
  if (!enabled || !text) return;
  try {
    Speech.speak(text, { language: LANG_TAG[lang] ?? "en-IN", rate: 1.0 });
  } catch {
    // TTS unavailable (web, silent mode) — nav keeps working silently
  }
}

export function stopCues(): void {
  try {
    Speech.stop();
  } catch {
    /* no-op */
  }
}
