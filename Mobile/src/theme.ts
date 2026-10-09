// Alive design tokens — the shared paper/ink register (docs/plan/03
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
  line: "#ECE9E2",      // dividers
  hairline: "#E3E0D7",  // crisp card/sheet edge
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
  accent: "#35614B",       // forest
  accentInk: "#2A4D3B",    // accent text on paper
  accentWash: "#EFEDE7",   // flat forest wash — selected states
  accentTint: "#E5E2DA",   // deeper forest wash — pressed states

  // ── CPCB band palette, muted to sit on paper (landing.html BAND) ─────
  // Colour means data: these six are the ONLY hues used for pollution
  // values. Order is the scale — index by CPCB pm2.5 band breaks.
  band0: "#6E93AE", // good          ≤30 µg/m³
  band1: "#C7A34F", // satisfactory  ≤60 — muted gold, not olive
  band2: "#CF8A50", // moderate      ≤90
  band3: "#C05F3A", // poor          ≤120 — ember, not rust-brown
  band4: "#A83D30", // very poor     ≤250 — brick red, not brown
  band5: "#6E2D28", // severe        >250 — deep maroon, not stool-brown

  // smoke you breathe — indexed onto the band ramp so a dose number and
  // a field cell of the same concentration read the same colour.
  breath1: "#CF8A50", // moderate
  breath2: "#C05F3A", // poor
  breath3: "#A83D30", // very poor→severe hue
  // smoke your ride puts out — neutral greys
  out1: "#4A4E57",
  out2: "#8A8D94",
  out3: "#A6ACB8",
  pinDest: "#C05F3A", // band 'poor' hue — reads on paper + light map

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
  glassSel: "rgba(239,237,231,0.92)",   // forest-wash glass — selected rows
  glassEdge: "rgba(255,255,255,0.85)",
  glassLine: "rgba(22,24,29,0.06)",     // the register's hairline on glass
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
/** segment count of the CPCB scale (0 good … 5 severe) — BandScale maps onto it */
export const BAND_SEG_COUNT = BANDS.length;
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
  card: { elevation: 1, shadowColor: "#3B3423", shadowOpacity: 0.07, shadowRadius: 18, shadowOffset: { width: 0, height: 6 } },
  /** floating chrome over the map — FABs, pills, peek card */
  float: { elevation: 4, shadowColor: "#3B3423", shadowOpacity: 0.12, shadowRadius: 22, shadowOffset: { width: 0, height: 8 } },
  /** sheets/drawers — the cast goes UP (they rise from the bottom edge) */
  sheet: { elevation: 12, shadowColor: "#3B3423", shadowOpacity: 0.12, shadowRadius: 30, shadowOffset: { width: 0, height: -6 } },
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
/** ~32% band — tile fills where the band itself must scan at a glance
 *  (the days-ahead row: five 10% washes read identical on paper)
 *  app-home-sexy: deepened 26%→32% — the subtle state holds on the warm
 *  base but the band is unmistakable at a glance */
export const bandWashDeepIdx = (i: number) => hexMix(BANDS[Math.max(0, Math.min(5, i))], "#FFFFFF", 0.68);
/** ~40% band — a hairline/marker that carries the day's colour */
export const bandEdgeIdx = (i: number) => hexMix(BANDS[Math.max(0, Math.min(5, i))], "#FFFFFF", 0.60);
/** band deepened ~20% toward ink — band-coloured text that reads on the
 *  warm base (was 15% — too close to a tint at caption sizes) */
export const bandInkIdx = (i: number) => hexMix(BANDS[Math.max(0, Math.min(5, i))], "#16181D", 0.20);
/** the air field's on-map tone — the band at its painted hi-confidence
 *  alpha (.32) composited over the basemap's urban land (#EDEAE3): what
 *  a field cell literally reads as, so the air-map legend swatches the
 *  tone you see on the streets, not the raw band chip */
export const bandFieldIdx = (i: number) => hexMix(BANDS[Math.max(0, Math.min(5, i))], "#EDEAE3", 0.68);

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
// design-v4: colour never names a component. Every well is warm stone;
// band hues stay reserved for air-quality meaning.
const STONE = { wash: "#F1EFE9", ink: "#4A4E57" };
export const V2Tint = {
  forest: { wash: "#EFEDE7", ink: "#35614B" },   // accent family — primary doors (map, go)
  /* identity hues retired (design-v4): colour never names a component,
     so every non-accent well is the same warm stone */
  sky:    STONE,
  clay:   STONE,
  sand:   STONE,
  plum:   STONE,
} as const;

// ── fonts ─────────────────────────────────────────────────────────────────
// One voice (design-v4): Satoshi (Indian Type Foundry) carries display,
// body, labels AND numbers — the serif/sans/mono trio read as a template.
// Hierarchy comes from size + weight, never from switching families.
// Hindi keeps Noto Sans Devanagari (Satoshi has no Devanagari cut).
export const F = {
  light: "Satoshi-Light",
  reg: "Satoshi-Regular",
  med: "Satoshi-Medium",
  semi: "Satoshi-Bold",
  bold: "Satoshi-Bold",
};

export const FH = {
  reg: "NotoSansDevanagari_400Regular",
  med: "NotoSansDevanagari_500Medium",
  semi: "NotoSansDevanagari_600SemiBold",
};

export const FSERIF = {
  /* display voice — Satoshi. "light" is the hero-numeral cut (the
     Carrot Weather move: ultra-light, huge, tight tracking); "black"
     exists for brand moments. no real italic — Satoshi ships upright
     only, italic slots fall back to reg. */
  light: "Satoshi-Light",
  reg: "Satoshi-Regular",
  med: "Satoshi-Medium",
  semi: "Satoshi-Bold",
  black: "Satoshi-Black",
  italic: "Satoshi-Regular",
};

/* design-v4: the instrument-panel mono voice is retired — numbers speak
   in the same Satoshi as the words (tabular via NUM). The slot names stay
   so every caller keeps compiling. */
export const FMONO = {
  reg: "Satoshi-Regular",
  med: "Satoshi-Medium",
  semi: "Satoshi-Bold",
};

type W = keyof typeof FH;
/** Font family for a UI language + weight slot (sans body voice). */
export const fam = (lang: Lang, w: W = "reg") => (lang === "hi" ? FH[w] : F[w]);

type SW = keyof typeof FSERIF;
/** Display voice — falls back to Noto in Hindi (no Devanagari cut).
 *  light/black collapse onto the nearest Devanagari weight. */
export const famSerif = (lang: Lang, w: SW = "reg") =>
  lang === "hi"
    ? FH[w === "semi" || w === "black" ? "semi" : w === "med" ? "med" : "reg"]
    : FSERIF[w];

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

/** A dose dot — colour comes from the day's fraction of the user's budget,
 *  not ambient bands (µg inhaled isn't µg/m³ air). Lighter reads quieter. */
export const doseDotColor = (ug: number, budgetUg: number): string => {
  const r = budgetUg > 0 ? ug / budgetUg : 1;
  if (ug <= 0) return "transparent";
  if (r < 0.34) return V2T.band0;
  if (r < 0.67) return V2T.band2;
  if (r <= 1) return V2T.band3;
  return V2T.band4;
};

/** Which CPCB band the day's dose-fraction whispers — the same thresholds
 *  doseDotColor uses, returned as an index so a cell can take a pastel
 *  wash + edge. null = a quiet day stays paper. */
export const doseTierIdx = (ug: number, budgetUg: number): number | null => {
  const r = budgetUg > 0 ? ug / budgetUg : 1;
  if (ug <= 0 || r < 0.34) return null;
  if (r < 0.67) return 2;
  if (r <= 1) return 3;
  return 4;
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
