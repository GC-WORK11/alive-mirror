/**
 * Alive accessibility toolkit — the contract for doc 03 §accessibility:
 * dynamic type up to 130% without layout break, every control labelled,
 * colour never the only signal. Other components import from here; the
 * audit lane (scripts/a11y_audit.py) checks the same rules statically.
 *
 * Android TalkBack + iOS VoiceOver only — no web branch needed.
 */
import { useEffect, useState } from "react";
import {
  AccessibilityInfo,
  type AccessibilityRole,
  type AccessibilityState,
} from "react-native";
import type { Lang } from "../i18n/strings";

// ── touch targets ──────────────────────────────────────────────────────────
/** Minimum touch-target edge, pt/dp. Apple HIG: 44×44; Android asks 48×48 —
 *  we floor at 44 and pad icon-only controls with `hitSlop` past that. */
export const MIN_TOUCH = 44;

/** Extra touch area for controls that must *look* small (sheet X, clear
 *  buttons). Spread as `hitSlop={slop()}` — the glyph stays 16 px, the
 *  finger gets 44+. */
export const slop = (px = 10) => ({ top: px, bottom: px, left: px, right: px });

// ── prop bundler ────────────────────────────────────────────────────────────
export type A11yOpts = Pick<
  AccessibilityState,
  "disabled" | "selected" | "checked" | "busy" | "expanded"
> & {
  /** UI language of the label — maps to BCP-47 so the screen reader picks
   *  the right voice for mixed-language screens (iOS). */
  lang?: Lang;
};

/** Bundle the four accessibility props every control needs:
 *  `a11y(t("a11yLocate", lang), t("hintLocate", lang), "button", { selected })`
 *  → spread onto Pressable/Touchable/Icon-button. `undefined` parts are
 *  omitted so spreading never clobbers. */
export function a11y(
  label: string,
  hint?: string,
  role: AccessibilityRole = "button",
  opts?: A11yOpts,
) {
  const state: AccessibilityState = {};
  if (opts) {
    for (const k of ["disabled", "selected", "checked", "busy", "expanded"] as const) {
      if (opts[k] !== undefined) state[k] = opts[k] as never;
    }
  }
  return {
    accessible: true,
    accessibilityLabel: label,
    accessibilityRole: role,
    ...(hint ? { accessibilityHint: hint } : null),
    ...(Object.keys(state).length ? { accessibilityState: state } : null),
    ...(opts?.lang ? { accessibilityLanguage: opts.lang } : null),
  };
}

// ── dynamic type (doc 03: up to 130%, no layout break) ─────────────────────
/** Hard cap matching the spec — spread `DYNAMIC_TYPE` onto every <Text> /
 *  <TextInput> so a system font scale of 150–200% can't explode layouts. */
export const MAX_FONT_SCALE = 1.3;
export const DYNAMIC_TYPE = {
  allowFontScaling: true,
  maxFontSizeMultiplier: MAX_FONT_SCALE,
} as const;

// ── motion (doc 03 §motion: respect "reduce motion") ────────────────────────
/** True when the OS "reduce motion" toggle is on — callers should swap
 *  springs/camera glides for instant or crossfade. Subscribes live so a
 *  user flipping the setting mid-session is honoured. */
export function useReduceMotion(): boolean {
  const [reduce, setReduce] = useState(false);
  useEffect(() => {
    AccessibilityInfo.isReduceMotionEnabled().then(setReduce).catch(() => {});
    const sub = AccessibilityInfo.addEventListener("reduceMotionChanged", setReduce);
    return () => sub.remove();
  }, []);
  return reduce;
}
