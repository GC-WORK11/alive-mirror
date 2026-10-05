// ALive-108 design tokens — the shared paper/ink register (docs/plan/03
// + server/landing.html, city.html, admin.html): light paper, serif display,
// mono for every number, hairlines at ~10% ink, muted CPCB band palette as
// the ONLY colour that means data. No shadows, no gradients, no emoji.
// V2T / V2Type / V2Radius / fam are the contract other lanes build on —
// keep names + keys stable; only values may move.
import type { Lang } from "./i18n/strings";

// ── paper / ink ───────────────────────────────────────────────────────────
// Straight off the web register: --paper #fafaf7, ink ramp, warm hairlines.
// Elevation is a ladder of flat fills; translucency is reserved for scrims
// and the milky floating chrome that sits over the basemap.
export const V2T = {
  // canvas + elevation ladder — flat fills, no elevation tricks
  bg: "#FAFAF7",        // paper
  surface: "#FFFFFF",   // cards/sheets — one step whiter than paper
  surface2: "#F3F2EC",  // raised: inputs, pressed rows
  surface3: "#EBE9E1",  // top flat step: floating controls

  sheet: "#FFFFFF",
  card: "#FFFFFF",

  // hairlines — ~10% ink equivalents on paper (web --line/--line2)
  line: "#E4E1D8",      // dividers
  hairline: "#D8D5C9",  // crisp card/sheet edge
  ink10: "rgba(22,24,29,0.10)", // true ~10%-ink hairline for overlays

  // scrims stay dark + rgba — they dim the map behind sheets
  scrim: "rgba(10,14,22,0.42)",
  scrimDeep: "rgba(10,14,22,0.58)",

  text: "#16181D",   // ink — 15+:1 on surface
  text2: "#4A4E57",  // ink2
  text3: "#8A8D94",  // ink3 — weakest ink that still reads on paper
  text4: "#A6ACB8",  // ink4 — empty states, "insufficient data"

  // the only non-data accent in the register — web --sage
  accent: "#4D7C0F",       // sage
  accentInk: "#3D610A",    // accent text on paper
  accentWash: "#EEF2E2",   // flat sage wash — selected states
  accentTint: "#E3E9D3",   // deeper sage wash — pressed states

  // ── CPCB band palette, muted to sit on paper (landing.html BAND) ─────
  // Colour means data: these six are the ONLY hues used for pollution
  // values. Order is the scale — index by CPCB pm2.5 band breaks.
  band0: "#7AAB59", // good          ≤30 µg/m³
  band1: "#C8B25A", // satisfactory  ≤60
  band2: "#D58C4A", // moderate      ≤90
  band3: "#B85442", // poor          ≤120
  band4: "#8F3C49", // very poor     ≤250
  band5: "#6E3C54", // severe        >250

  // smoke you breathe — indexed onto the band ramp so a dose number and
  // a field cell of the same concentration read the same colour.
  breath1: "#D58C4A", // moderate
  breath2: "#B85442", // poor
  breath3: "#8F3C49", // very poor→severe hue
  // smoke your ride puts out — neutral greys
  out1: "#4A4E57",
  out2: "#8A8D94",
  out3: "#A6ACB8",
  pinDest: "#B85442", // band 'poor' hue — reads on paper + light map

  // map tokens mirror the light basemap (v2-light.json)
  mapMotorway: "#F0B85A",
  mapPrimary: "#F9D27A",
  mapMinor: "#E4E6EA",
  mapBuilding: "#DDE1E7",
  mapWater: "#90DAEE",
  mapPark: "#CFECCD",

  // ── floating chrome over the map ──────────────────────────────────────
  // Alpha-frosted paper panes — the map must stay legible under them, so
  // they keep alpha ≥ .62 and a 10%-ink hairline edge. No blur library.
  glass: "rgba(255,255,255,0.86)",      // panes: sheets, drawer, HUD tiles
  glassDeep: "rgba(255,255,255,0.92)",  // full-height screens
  glassSoft: "rgba(255,255,255,0.66)",  // rows resting on a milk pane
  glassFaint: "rgba(255,255,255,0.78)", // floating chips, FABs, peek card
  glassSel: "rgba(238,242,226,0.82)",   // sage-wash glass — selected rows
  glassEdge: "rgba(255,255,255,0.85)",
  glassLine: "rgba(22,24,29,0.10)",     // the register's hairline on glass
} as const;

/** CPCB pm2.5 band index (0 good … 5 severe) — web bandIdx(), same breaks. */
export const PM25_BREAKS = [30, 60, 90, 120, 250] as const;
export function bandIdx(v: number | null | undefined): number | null {
  if (v == null) return null;
  let i = 0;
  while (i < PM25_BREAKS.length && v > PM25_BREAKS[i]) i++;
  return Math.min(i, 5);
}
const BANDS = [V2T.band0, V2T.band1, V2T.band2, V2T.band3, V2T.band4, V2T.band5];
/** Muted CPCB colour for a concentration — null-safe (absence → null). */
export function bandColor(v: number | null | undefined): string | null {
  const i = bandIdx(v);
  return i == null ? null : BANDS[i];
}

// ── type ──────────────────────────────────────────────────────────────────
// The register's ramp: 11/13/17/22/30/44 — eyebrow micro → hero display.
// `secondary` stays as a 15px between-step legacy callers already use for
// dense secondary text; new surfaces pick the canonical steps.
export const V2Type = {
  micro: 11,
  label: 13,
  secondary: 15,  // dense-reading step kept for existing rows
  body: 17,
  title: 22,
  display: 30,
  hero: 44,
} as const;

// Squared-ish register: hairline cards carry a small radius; only the
// sheet keeps the platform top-corner roundness; `pill` for the few true
// pill semantics left (chips that are themselves capsule-shaped data).
export const V2Radius = { row: 8, card: 12, sheet: 20, pill: 999 } as const;

// ── fonts ─────────────────────────────────────────────────────────────────
// Three voices like the web pages: serif display (Fraunces — the "New York"
// stand-in), sans body (Inter), ui-monospace for EVERY number and every
// eyebrow/label. Hindi keeps Noto Sans Devanagari in all three slots —
// Fraunces and Plex Mono carry no Devanagari glyphs.
export const F = {
  light: "Inter_400Regular",
  reg: "Inter_400Regular",
  med: "Inter_500Medium",
  semi: "Inter_600SemiBold",
  bold: "Inter_600SemiBold",
};

export const FH = {
  reg: "NotoSansDevanagari_400Regular",
  med: "NotoSansDevanagari_500Medium",
  semi: "NotoSansDevanagari_600SemiBold",
};

export const FSERIF = {
  reg: "Fraunces_400Regular",
  med: "Fraunces_500Medium",
  semi: "Fraunces_600SemiBold",
  italic: "Fraunces_400Regular_Italic",
};

export const FMONO = {
  reg: "IBMPlexMono_400Regular",
  med: "IBMPlexMono_500Medium",
  semi: "IBMPlexMono_600SemiBold",
};

type W = keyof typeof FH;
/** Font family for a UI language + weight slot (sans body voice). */
export const fam = (lang: Lang, w: W = "reg") => (lang === "hi" ? FH[w] : F[w]);

type SW = keyof typeof FSERIF;
/** Serif display voice — falls back to Noto in Hindi (no Devanagari serif). */
export const famSerif = (lang: Lang, w: SW = "reg") =>
  lang === "hi" ? FH[w === "italic" ? "reg" : w] : FSERIF[w];

type MW = keyof typeof FMONO;
/** The numbers voice — use only on pure-numeric/Latin text; in Hindi it
 *  still ships (digits are Latin glyphs in Plex Mono). */
export const famMono = (_lang: Lang, w: MW = "reg") => FMONO[w];

/** tabular numerals — belt under the mono face on every number */
export const NUM = { fontVariant: ["tabular-nums" as const] };

/** smoke-you-breathe colour — indexed onto the CPCB ramp; quiet air reads
 *  as plain muted text (absence of colour = lighter air, doc 03). */
export const doseColor = (avg: number | null | undefined) => {
  const i = bandIdx(avg);
  if (i == null || i <= 1) return V2T.text3;
  return BANDS[i];
};

/** cigarette-equivalents: 1 cig = 316µg inhaled PM2.5 (Berkeley Earth,
 *  doc 10) — a quiet receipt footnote only, never a hero number. */
export const CIG_UG = 316;
export const cigOf = (ug: number | null | undefined) =>
  ug == null ? null : Math.round((ug / CIG_UG) * 100) / 100;

// ── legacy aliases ────────────────────────────────────────────────────────
// Old component keys remapped onto the paper palette so transition-era
// files stay legible until rebuilt. New code uses V2T/F directly.
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
  goSoft: V2T.accentWash,

  doseQuiet: V2T.text3,
  doseWarn: V2T.breath1,
  doseOver: V2T.breath2,
  doseSevere: V2T.breath3,
  doseExtreme: V2T.band5,

  glass: V2T.sheet,
  glassBorder: V2T.hairline,
  accent: V2T.accent,
  accentSoft: V2T.accentWash,
  doseLow: V2T.text3,
  doseMid: V2T.breath2,
  doseHigh: V2T.breath3,
  ambient: V2T.bg,
};
