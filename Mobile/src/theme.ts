// ALive-108 design tokens — the shared paper/ink register (docs/plan/03
// + server/landing.html, city.html, admin.html): light paper, serif display,
// mono for every number, hairlines at ~10% ink, muted CPCB band palette as
// the ONLY colour that means data. No gradients, no emoji.
// V2T / V2Type / V2Radius / fam are the contract other lanes build on —
// keep names + keys stable; only values may move. (V2Elev / band* helpers
// are additive — the depth pass's own vocabulary.)
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
  text3: "#6E7278",  // ink3 — caption ink, AA on paper (4.6:1); was
                      //  #8A8D94 @ 3.2:1 which read as faint gray
  text4: "#A6ACB8",  // ink4 — empty states, "insufficient data"

  // the only non-data accent in the register — forest, not olive:
  // the overhaul's muted-expensive discipline (deep, saturated, classy —
  // no lime-slime / chocolaty green / cheap yellow). Contrast on paper
  // stays ≥4.5:1 for the primary-CTA fill.
  accent: "#3A6844",       // forest
  accentInk: "#2B4E32",    // accent text on paper
  accentWash: "#EAF0E4",   // flat forest wash — selected states
  accentTint: "#DCE7D1",   // deeper forest wash — pressed states

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
  glass: "rgba(255,255,255,0.91)",      // panes: sheets, drawer, HUD tiles
  glassDeep: "rgba(255,255,255,0.95)",  // full-height screens
  glassSoft: "rgba(255,255,255,0.76)",  // rows resting on a milk pane
  glassFaint: "rgba(255,255,255,0.86)", // floating chips, FABs, peek card
  glassSel: "rgba(234,240,228,0.88)",   // forest-wash glass — selected rows
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

/** Colour for a CPCB band INDEX (0–5) — for payloads that carry the
 *  category itself rather than a concentration. */
export function bandColorIdx(i: number | null | undefined): string | null {
  if (i == null) return null;
  return BANDS[Math.max(0, Math.min(5, i))];
}

// ── elevation ────────────────────────────────────────────────────────────
// Physical presence for surfaces: Android reads `elevation` (soft native
// shadow around the view), iOS gets the shadow_* pair — same scale either
// way. Warm-ink shadow colour, low and tight: a card should sit ON the
// paper, not hover. Translucent panes keep elevation modest — an alpha
// surface lets its own shadow ghost through the edges.
export const V2Elev = {
  /** resting card on a sheet / panel */
  card: { elevation: 2, shadowColor: "#16181D", shadowOpacity: 0.10, shadowRadius: 8, shadowOffset: { width: 0, height: 2 } },
  /** floating chrome over the map — FABs, pills, peek card */
  float: { elevation: 5, shadowColor: "#16181D", shadowOpacity: 0.16, shadowRadius: 12, shadowOffset: { width: 0, height: 3 } },
  /** sheets/drawers — the cast goes UP (they rise from the bottom edge) */
  sheet: { elevation: 12, shadowColor: "#16181D", shadowOpacity: 0.18, shadowRadius: 24, shadowOffset: { width: 0, height: -4 } },
  /** popovers/receipts — the biggest cast we allow */
  pop: { elevation: 18, shadowColor: "#16181D", shadowOpacity: 0.22, shadowRadius: 30, shadowOffset: { width: 0, height: -6 } },
} as const;

// ── band washes: colour as feeling ───────────────────────────────────────
// A CPCB band whispers on a surface — the day/stack should FEEL severe
// without a neon alarm. Solid blends toward white (predictable over both
// paper and the milky panes), never alpha fills that composite on whatever
// is behind.
const hexMix = (a: string, b: string, t: number): string => {
  const pa = [1, 3, 5].map((i) => parseInt(a.slice(i, i + 2), 16));
  const pb = [1, 3, 5].map((i) => parseInt(b.slice(i, i + 2), 16));
  const c = pa.map((v, i) => Math.round(v + (pb[i] - v) * t));
  return `#${c.map((v) => v.toString(16).padStart(2, "0")).join("")}`;
};
/** ~10% band on surface — cell/tile fills, selected whispers */
export const bandWashIdx = (i: number) => hexMix(BANDS[Math.max(0, Math.min(5, i))], "#FFFFFF", 0.90);
export const bandWash = (v: number | null | undefined) => {
  const i = bandIdx(v); return i == null ? null : bandWashIdx(i);
};
/** ~18% band — pastel card surfaces that carry the day's colour
 *  (the overhaul's tinted-hero grammar: a card CAN wear its band) */
export const bandWashMidIdx = (i: number) => hexMix(BANDS[Math.max(0, Math.min(5, i))], "#FFFFFF", 0.82);
export const bandWashMid = (v: number | null | undefined) => {
  const i = bandIdx(v); return i == null ? null : bandWashMidIdx(i);
};
/** ~26% band — tile fills where the band itself must scan at a glance
 *  (the days-ahead row: five 10% washes read identical on paper) */
export const bandWashDeepIdx = (i: number) => hexMix(BANDS[Math.max(0, Math.min(5, i))], "#FFFFFF", 0.74);
/** ~38% band — a hairline that carries the day's colour */
export const bandEdgeIdx = (i: number) => hexMix(BANDS[Math.max(0, Math.min(5, i))], "#FFFFFF", 0.60);
export const bandEdge = (v: number | null | undefined) => {
  const i = bandIdx(v); return i == null ? null : bandEdgeIdx(i);
};
/** band deepened ~15% toward ink — band-coloured text that still reads */
export const bandInkIdx = (i: number) => hexMix(BANDS[Math.max(0, Math.min(5, i))], "#16181D", 0.15);
export const bandInk = (v: number | null | undefined) => {
  const i = bandIdx(v); return i == null ? null : bandInkIdx(i);
};

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
  heroXL: 62,     // the number that owns the card (dose hero, big verdicts)
} as const;

// Chunky-component register: one-idea cards carry ~20px; rows and wells
// sit at ~13px; the sheet keeps the platform top-corner roundness; `pill`
// for the few true pill semantics (chips, the primary CTA, tab pills).
export const V2Radius = { row: 13, card: 20, sheet: 24, pill: 999 } as const;

// ── component tint wells ─────────────────────────────────────────────────
// Feature doors, icon tiles and select-pills wear pastel identity colours
// that are NOT the CPCB ramp — colour here means component identity, never
// data (a band hue still means pollution). Each well is a wash + a
// readable ink for the glyph/label on top. Muted-expensive: every tone is
// a deep hue pulled ~80% toward paper.
const well = (hex: string) => ({ wash: hexMix(hex, "#FFFFFF", 0.80), ink: hexMix(hex, "#16181D", 0.28) });
export const V2Tint = {
  forest: well("#3A6844"),   // accent family — primary doors (map, go)
  sky:    well("#4A6B80"),   // slate-blue  — city surfaces
  clay:   well("#8A5648"),   // terracotta  — trips/ledger
  sand:   well("#8A7440"),   // warm oat    — spare identity
  plum:   well("#6E4E62"),   // muted plum  — spare identity
} as const;

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

/** A mono-styled slot that carries LOCALIZED text — eyebrows, note lines,
 *  number+word readouts. Plex Mono ships no Devanagari, so hi takes FH
 *  (the mono look simply doesn't exist for Hindi); en keeps Plex Mono.
 *  Slots that can only ever show digits/units keep famMono. */
export const famMonoText = (lang: Lang, w: MW = "reg") =>
  lang === "hi" ? FH[w] : FMONO[w];

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
