// ALive-108 design tokens — monochrome canvas + one accent + one
// dose ramp. Nothing else has color. (docs/24-design-language-spec.md)
export const T = {
  ink: "#1C1917",
  ink2: "#57534E",
  ink3: "#A8A29E",
  paper: "#F7F7F6",
  surface: "#FCFCFB",
  hairline: "#E7E5E4",
  ambientInk: "#06070A",
  ambientPaper: "#F5F5F4",

  go: "#1D4ED8",          // the only accent — interactive elements only
  goSoft: "rgba(29,78,216,0.08)",

  // dose ramp — single hue, monotonic lightness; quiet = neutral
  doseQuiet: "#78716C",
  doseWarn: "#FB7185",
  doseOver: "#E11D48",
  doseSevere: "#9F1239",
  doseExtreme: "#4C0519",

  // legacy aliases kept for old components until they're rebuilt
  glass: "#FCFCFB",
  glassBorder: "#E7E5E4",
  accent: "#1D4ED8",
  accentSoft: "rgba(29,78,216,0.08)",
  doseLow: "#78716C",
  doseMid: "#E11D48",
  doseHigh: "#9F1239",
  ambient: "#06070A",
};

export const F = {
  light: "Outfit_300Light",
  reg: "Outfit_400Regular",
  med: "Outfit_500Medium",
  semi: "Outfit_600SemiBold",
  bold: "Outfit_700Bold",
};

export const NUM = { fontVariant: ["tabular-nums" as const] };

/** dose color — keyed to concentration vs the day's quiet band */
export const doseColor = (avg: number | null | undefined) =>
  avg == null || avg < 60 ? T.doseQuiet
    : avg < 130 ? T.doseWarn
    : avg < 250 ? T.doseOver
    : avg < 400 ? T.doseSevere
    : T.doseExtreme;

/** cigarette-equivalents: 1 🚬 = 316µg inhaled PM2.5 */
export const CIG_UG = 316;
export const cigOf = (ug: number | null | undefined) =>
  ug == null ? null : Math.round((ug / CIG_UG) * 100) / 100;

// ── v2 dark design system (docs/plan/03-design-system.md) ────────────────
// New code imports from V2T. T stays until the old components are rebuilt.
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
