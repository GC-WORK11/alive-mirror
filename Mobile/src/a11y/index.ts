/**
 * ALive-108 accessibility toolkit — the contract for doc 03 §accessibility:
 * dynamic type up to 130% without layout break, every control labelled,
 * colour never the only signal. Other components import from here; the
 * audit lane (scripts/a11y_audit.py) checks the same rules statically.
 *
 * Android TalkBack + iOS VoiceOver only — no web branch needed.
 */
import { useEffect, useRef, useState } from "react";
import {
  AccessibilityInfo,
  PixelRatio,
  Platform,
  type AccessibilityRole,
  type AccessibilityState,
  type StyleProp,
  type ViewStyle,
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

/** Ensure a style's box is at least MIN_TOUCH on both edges. Numeric
 *  width/height below the floor get a matching min* (Yoga: min wins over
 *  size); non-numeric or absent edges always get the floor. Padding-only
 *  pressables get the floor too. */
export function ensureTouch(style?: ViewStyle): StyleProp<ViewStyle> {
  const w = style?.width;
  const h = style?.height;
  const needsW = typeof w !== "number" || w < MIN_TOUCH;
  const needsH = typeof h !== "number" || h < MIN_TOUCH;
  if (!needsW && !needsH) return style;
  return [
    style,
    needsW && { minWidth: MIN_TOUCH },
    needsH && { minHeight: MIN_TOUCH },
  ];
}

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

/** Current font scale after the 130% cap (never <1 — a user-shrunk scale
 *  is honoured, accessibility-wise shrinking hurts no one). */
export const fontScale = () => {
  const s = PixelRatio.getFontScale();
  return Math.min(s > 0 ? s : 1, MAX_FONT_SCALE);
};

/** Devanagari glyphs carry the shirorekha headline + stacked conjuncts —
 *  ~4% more px reaches the same x-height legibility as Inter at a size. */
const HI_SIZE_BUMP = 1.04;

/** Pt size → device px after the capped system font scale. For computed
 *  styles where a props spread won't reach (e.g. canvas/manual metrics). */
export const scaledFont = (size: number, lang: Lang = "en") =>
  Math.round(size * fontScale() * (lang === "hi" ? HI_SIZE_BUMP : 1) * 10) / 10;

// ── WCAG contrast ───────────────────────────────────────────────────────────
type Rgba = { r: number; g: number; b: number; a: number };

/** Parse #rgb / #rgba / #rrggbb / #rrggbbaa / rgb() / rgba() → 0-255 + alpha. */
export function parseColor(c: string): Rgba | null {
  const s = c.trim();
  const m = /^rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)(?:[\s,/]+([\d.]+%?))?\s*\)$/i.exec(s);
  if (m) {
    const a = m[4] == null ? 1 : m[4].endsWith("%") ? parseFloat(m[4]) / 100 : parseFloat(m[4]);
    return { r: +m[1], g: +m[2], b: +m[3], a: Math.min(1, Math.max(0, a)) };
  }
  const h = s.replace(/^#/, "");
  const n = h.length === 3 || h.length === 4
    ? h.split("").map((x) => x + x).join("")
    : h;
  if (!/^[0-9a-f]{6}([0-9a-f]{2})?$/i.test(n)) return null;
  return {
    r: parseInt(n.slice(0, 2), 16),
    g: parseInt(n.slice(2, 4), 16),
    b: parseInt(n.slice(4, 6), 16),
    a: n.length === 8 ? parseInt(n.slice(6, 8), 16) / 255 : 1,
  };
}

const lin = (v: number) => {
  const c = v / 255;
  return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
};

const luminance = ({ r, g, b }: Rgba) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);

/** Composite a translucent fg onto an opaque bg (rgba() tokens such as
 *  "rgba(76,141,255,0.12)" pressed-state washes). */
const over = (fg: Rgba, bg: Rgba): Rgba => ({
  r: fg.a * fg.r + (1 - fg.a) * bg.r,
  g: fg.a * fg.g + (1 - fg.a) * bg.g,
  b: fg.a * fg.b + (1 - fg.a) * bg.b,
  a: 1,
});

/** WCAG 2.x contrast ratio, 1–21. A translucent fg is composited over bg. */
export function contrast(fg: string, bg: string): number {
  const f = parseColor(fg);
  const b = parseColor(bg);
  if (!f || !b) return NaN;
  const eff = f.a < 1 ? over(f, b) : f;
  const l1 = luminance(eff);
  const l2 = luminance({ ...b, a: 1 });
  return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
}

/** AA thresholds: 4.5 normal text, 3.0 large (≥18pt / ≥14pt bold) and
 *  non-text UI components (borders, focus indicators). */
export function contrastPass(fg: string, bg: string, opts?: { large?: boolean; nonText?: boolean }) {
  const need = opts?.nonText ? 3 : opts?.large ? 3 : 4.5;
  const ratio = contrast(fg, bg);
  return { ratio, need, pass: ratio >= need };
}

/** Dev-only assert — warns loudly in Metro, silent in release. Returns the
 *  ratio so callers can log it. */
export function assertContrast(fg: string, bg: string, ctx: string, opts?: { large?: boolean; nonText?: boolean }) {
  const { ratio, need, pass } = contrastPass(fg, bg, opts);
  if (__DEV__ && !pass) {
    console.warn(
      `[a11y] contrast ${ratio.toFixed(2)}:1 < ${need}:1 — ${ctx} (${fg} on ${bg})`,
    );
  }
  return ratio;
}

// ── live regions / announcements ────────────────────────────────────────────
/** Spread onto a View/Text whose text updates on its own (nav counters —
 *  doc 02 §S6 ticks ~1 Hz). Android TalkBack announces each change
 *  *politely*; VoiceOver ignores liveRegion → pair with useA11yAnnounce. */
export const liveRegion = {
  accessible: true,
  accessibilityLiveRegion: "polite",
} as const;

/**
 * Announce a changing value to the screen reader, at most once per
 * `throttleMs` and only when the text actually changed — the 1 Hz "breathed
 * ≈0.04🚬" tick must not become a 1 Hz voice. Leading announce on change,
 * trailing announce of the newest pending text once the window elapses.
 *
 * iOS only by design: on Android `liveRegion` already announces text
 * changes — announcing here too would double-speak. iOS VoiceOver has no
 * liveRegion equivalent, so this hook is the iOS half of the pair.
 */
export function useA11yAnnounce(text: string | null | undefined, throttleMs = 10_000) {
  const lastText = useRef("");
  const lastTime = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (Platform.OS !== "ios") return;
    if (!text || text === lastText.current) return;
    const now = Date.now();
    const speak = (s: string) => {
      lastText.current = s;
      lastTime.current = Date.now();
      AccessibilityInfo.announceForAccessibility(s);
    };
    if (now - lastTime.current >= throttleMs) {
      speak(text);
      return;
    }
    // inside the throttle window — park this text; newest pending wins
    if (timer.current) clearTimeout(timer.current);
    const pending = text;
    timer.current = setTimeout(() => {
      if (pending !== lastText.current) speak(pending);
    }, throttleMs - (now - lastTime.current));
  }, [text, throttleMs]);

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);
}

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
