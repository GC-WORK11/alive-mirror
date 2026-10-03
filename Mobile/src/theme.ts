// ALive-108 design tokens — v2 dark design system (docs/plan/03-design-system.md).
// V2T / V2Type / V2Radius are the contract other lanes build on — keep names+keys.
import type { Lang } from "./i18n/strings";

// ── v2 dark tokens ────────────────────────────────────────────────────────
// Near-black canvas, one interactive accent, colour reserved for meaning.
// "Good" has no colour — lightness is shown by absence (no green anywhere).
export const V2T = {
  bg: "#0B0D10",
  surface: "#15181D",
  surface2: "#1E2228",
  line: "#2A2F36",
  text: "#F2F4F7",
  text2: "#A3AAB5",
  text3: "#6B7280",
  accent: "#4C8DFF",
  // smoke you breathe — warm ramp, light → heavy
  breath1: "#F2C14E",
  breath2: "#F08A3C",
  breath3: "#E5484D",
  // smoke your ride puts out — cool greys
  out1: "#9AA4B2",
  out2: "#6E7A8A",
  out3: "#3E4754",
  pinDest: "#E5484D",
  // map overrides
  mapMotorway: "#3A4049",
  mapPrimary: "#2E333A",
  mapMinor: "#24282E",
  mapBuilding: "#1C2026",
  mapWater: "#0E1A24",
  mapPark: "#121A15",
} as const;

export const V2Type = {
  hero: 34,
  title: 22,
  body: 17,
  secondary: 15,
  label: 13,
} as const;

export const V2Radius = { row: 12, sheet: 20, pill: 999 } as const;

// ── type ──────────────────────────────────────────────────────────────────
// Inter (OFL) for everything; Noto Sans Devanagari for Hindi. Weights 400/500/600.
// Keys kept stable so transition components compile unchanged.
export const F = {
  light: "Inter_400Regular",   // spec has no 300 — light maps onto regular
  reg: "Inter_400Regular",
  med: "Inter_500Medium",
  semi: "Inter_600SemiBold",
  bold: "Inter_600SemiBold",   // spec caps weight at 600
};

export const FH = {
  reg: "NotoSansDevanagari_400Regular",
  med: "NotoSansDevanagari_500Medium",
  semi: "NotoSansDevanagari_600SemiBold",
};

type W = keyof typeof FH;
/** Font family for a UI language + weight slot. */
export const fam = (lang: Lang, w: W = "reg") => (lang === "hi" ? FH[w] : F[w]);

/** tabular numerals — required on every number (doc 03 §type) */
export const NUM = { fontVariant: ["tabular-nums" as const] };

/** smoke-you-breathe colour — keyed to concentration vs the day's quiet band.
 *  Quiet reads as plain secondary text: absence of colour = lighter air. */
export const doseColor = (avg: number | null | undefined) =>
  avg == null || avg < 60 ? V2T.text3
    : avg < 130 ? V2T.breath1
    : avg < 250 ? V2T.breath2
    : V2T.breath3;

/** cigarette-equivalents: 1 🚬 = 316µg inhaled PM2.5 (Berkeley Earth, doc 10) */
export const CIG_UG = 316;
export const cigOf = (ug: number | null | undefined) =>
  ug == null ? null : Math.round((ug / CIG_UG) * 100) / 100;

// ── legacy aliases ────────────────────────────────────────────────────────
// Old component keys remapped onto the dark palette so transition-era files
// stay legible until rebuilt. New code uses V2T/F directly.
export const T = {
  ink: V2T.text,
  ink2: V2T.text2,
  ink3: V2T.text3,
  paper: V2T.bg,
  surface: V2T.surface,
  hairline: V2T.line,
  ambientInk: V2T.bg,
  ambientPaper: V2T.text,

  go: V2T.accent,
  goSoft: "rgba(76,141,255,0.12)",

  doseQuiet: V2T.text3,
  doseWarn: V2T.breath1,
  doseOver: V2T.breath2,
  doseSevere: V2T.breath3,
  doseExtreme: "#A93A3F",

  glass: V2T.surface,
  glassBorder: V2T.line,
  accent: V2T.accent,
  accentSoft: "rgba(76,141,255,0.12)",
  doseLow: V2T.text3,
  doseMid: V2T.breath2,
  doseHigh: V2T.breath3,
  ambient: V2T.bg,
};
