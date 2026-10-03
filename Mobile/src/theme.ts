// ALive-108 design tokens — v2 LIGHT design system (docs/plan/03-design-system.md).
// r5 refresh: light chrome + light basemap (paper/ink), muted editorial ramp.
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
  // canvas + elevation ladder — all solid. LIGHT chrome throughout: the app
  // is paper-light with ink text over a light Google-style basemap.
  bg: "#F2F4F8",        // cool off-white canvas
  surface: "#FFFFFF",   // cards/sheets — pure white
  surface2: "#ECEEF3",  // raised: inputs, pressed rows, pills
  surface3: "#E0E3EA",  // top solid step: floating controls

  // semantic surfaces — sheets/cards are never translucent
  sheet: "#FFFFFF",
  card: "#FFFFFF",

  // borders
  line: "#E2E5EB",     // dividers, default 1-px edges
  hairline: "#D4D8E1", // crisp card/sheet edge — visible on white

  // scrims stay dark + rgba — they overlay the dark map
  scrim: "rgba(10,14,22,0.42)",     // sheet backdrops
  scrimDeep: "rgba(10,14,22,0.58)", // drawer / full takeover

  text: "#14181F",   // 15.9:1 surface · 14.1:1 surface2
  text2: "#4A5161",  //  7.3:1 surface ·  6.5:1 surface2
  text3: "#65707F",  //  5.0:1 surface ·  4.5:1 surface2 · 4.6:1 surface3
  accent: "#1A73E8", // Google blue; white text on it: 5.9:1,
                     // accent-as-text on surface: 5.4:1

  // SOLID accent washes — Google's own selected-state tints over `sheet`.
  accentWash: "#E8F0FE",
  accentTint: "#D3E3FD",

  // smoke you breathe — muted editorial ramp (bronze → brick → wine).
  // No traffic-light amber, no emoji red — print-quality hues.
  breath1: "#A1662F", //  bronze   ~5.0:1 surface
  breath2: "#A34446", //  brick    ~5.4:1 surface
  breath3: "#8A2D3E", //  wine     ~8.0:1 surface
  // smoke your ride puts out — cool greys
  out1: "#5C6675",
  out2: "#8791A0",
  out3: "#B4BBC7",
  pinDest: "#B33A42", // deep brick pin — reads on paper + light map
  // map tokens mirror the Google-palette basemap (v2-light.json) — kept for
  // any chrome that echoes map colours.
  mapMotorway: "#F0B85A",
  mapPrimary: "#F9D27A",
  mapMinor: "#E4E6EA",
  mapBuilding: "#DDE1E7",
  mapWater: "#90DAEE",
  mapPark: "#CFECCD",
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
  doseExtreme: "#7C2D3E",

  glass: V2T.sheet,
  glassBorder: V2T.hairline,
  accent: V2T.accent,
  accentSoft: V2T.accentTint,
  doseLow: V2T.text3,
  doseMid: V2T.breath2,
  doseHigh: V2T.breath3,
  ambient: V2T.bg,
};
