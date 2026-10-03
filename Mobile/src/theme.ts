// ALive-108 design tokens — v2 dark design system (docs/plan/03-design-system.md).
// r4 refresh: graphite/ink ramp + solid-surface doctrine (docs/plan/theme-r4.md).
// V2T / V2Type / V2Radius are the contract other lanes build on — keep names+keys.
import type { Lang } from "./i18n/strings";

// ── v2 dark tokens ────────────────────────────────────────────────────────
// Graphite/ink ramp: every surface sits at hue ≈ 216–220° with B ≥ G > R, so
// the palette reads cool blue-black and can never tip green (Linear / Apple
// Maps dark territory). "Good" has no colour — lightness is shown by absence.
//
// Solid-surface doctrine: elevation is a ladder of SOLID fills
//   bg → surface (= sheet = card) → surface2 → surface3
// rgba() is reserved for scrims and data overlays — never a surface fill.
// Pre-composited accentWash/accentTint replace translucent accent washes.
export const V2T = {
  // canvas + elevation ladder — all solid
  bg: "#090B0F",
  surface: "#12151B",
  surface2: "#1B2029", // raised: inputs, pressed rows, pills
  surface3: "#242B37", // top solid step: floating controls, pressed-on-raised

  // semantic surfaces (same solid step as `surface` — sheets/cards are never
  // translucent; the map must not bleed through a sheet)
  sheet: "#12151B",
  card: "#12151B",

  // borders
  line: "#2A303C",     // dividers, default 1-px edges
  hairline: "#333C4A", // crisp card/sheet edge — 1.6:1 on surface

  // scrims stay rgba — tuned blue-black (was flat rgba(0,0,0,…))
  scrim: "rgba(5,7,11,0.45)",     // sheet backdrops
  scrimDeep: "rgba(5,7,11,0.60)", // drawer / full takeover

  text: "#F2F4F7",   // 16.6:1 surface · 14.8:1 surface2
  text2: "#A6ADB9",  //  8.1:1 surface ·  7.2:1 surface2
  text3: "#8A94A0",  //  5.9:1 surface ·  5.3:1 surface2 · 4.6:1 surface3
  accent: "#4F90FF", // the one interactive colour; `bg` text on it: 6.3:1

  // SOLID accent washes — pre-composited accent @8% / @12% over `sheet`.
  // Drop-in for "rgba(76,141,255,0.08|0.12)" selected states; accent text on
  // accentTint still reads 5.0:1.
  accentWash: "#171F2D",
  accentTint: "#192436",

  // smoke you breathe — warm ramp, light → heavy
  breath1: "#F2C14E", //  9.7:1 surface2
  breath2: "#F08A3C", //  6.5:1 surface2
  breath3: "#F26366", //  5.3:1 surface2 · 4.6:1 surface3 (was #EE5A5F: 4.2:1 on s3)
  // smoke your ride puts out — cool greys
  out1: "#9AA4B2",
  out2: "#6E7A8A",
  out3: "#3E4754",
  pinDest: "#E5484D",
  // map overrides — same ink family as the UI ramp. Park tint is cool slate:
  // the "no green" rule applies to the basemap too (old #121A15 read
  // green-black on OLED at night).
  mapMotorway: "#383F4B",
  mapPrimary: "#2B313C",
  mapMinor: "#222730",
  mapBuilding: "#181D25",
  mapWater: "#0C1520",
  mapPark: "#10151D",
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
// stay legible until rebuilt. New code uses V2T/F directly. Translucent
// washes (goSoft/accentSoft) now resolve to the SOLID tint tokens — same
// string contract, no alpha, per the solid-surface doctrine.
export const T = {
  ink: V2T.text,
  ink2: V2T.text2,
  ink3: V2T.text3,
  paper: V2T.bg,
  surface: V2T.surface,
  hairline: V2T.hairline,
  ambientInk: V2T.bg,
  ambientPaper: V2T.text,

  go: V2T.accent,
  goSoft: V2T.accentTint,

  doseQuiet: V2T.text3,
  doseWarn: V2T.breath1,
  doseOver: V2T.breath2,
  doseSevere: V2T.breath3,
  doseExtreme: "#A93A3F",

  glass: V2T.sheet,
  glassBorder: V2T.hairline,
  accent: V2T.accent,
  accentSoft: V2T.accentTint,
  doseLow: V2T.text3,
  doseMid: V2T.breath2,
  doseHigh: V2T.breath3,
  ambient: V2T.bg,
};
