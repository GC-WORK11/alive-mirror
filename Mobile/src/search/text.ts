// Shared query/name text handling for the search tiers — normalization,
// Delhi abbreviations, and the transliteration fold. Kept dependency-free
// so t0 (on-device index), parse (query understanding) and client (server
// tiers) can all agree on how a name reads. Comments in t0.ts explain the
// index side; this file is only vocabulary.

// Hinglish / common abbreviations (docs/plan/04 §2 normalization table).
// Applied query-side; full names are also reverse-aliased at index time so
// "gk" finds Greater Kailash even before expansion is considered.
export const ABBREV: Record<string, string> = {
  cp: "connaught place",
  gk: "greater kailash",
  sec: "sector",
  ngr: "nagar",
  vhr: "vihar",
  ext: "extension",
  encl: "enclave",
  mkt: "market",
  rd: "road",
  stn: "station",
  chok: "chowk",
  ph: "phase",
  clny: "colony",
};
export const EXPANSIONS: [string, string][] = Object.entries(ABBREV).map(
  ([ab, exp]) => [exp, ab]);

/** Shared normalization: lowercase, punctuation → space, abbreviation
 * expansion, single spaces. Used for queries, index keys and dedupe. */
export function normalize(q: string): string {
  const s = q.toLowerCase().replace(/[^a-z0-9]+/g, " ").replace(/\s+/g, " ").trim();
  if (!s) return "";
  return s
    .split(" ")
    .map((tok) => ABBREV[tok] ?? tok)
    .join(" ");
}

/** Transliteration fold — how Delhi names actually get typed. Romanised
 * Hindi/urdu spellings are wildly inconsistent ("nandanagri" vs "nand
 * nagri", "shadara"/"shahdara", "vihaar"/"vihar", "bagh"/"bag"): digraphs
 * collapse to their sound ('sh'→x, 'th'→t, 'kh'→k…), silent 'h' drops,
 * vowels drop, repeats collapse. Two spellings of the same place almost
 * always land on one skeleton:
 *   ashok → xk, ashook → xk;  shahdara → xdr, shadara → xdr;
 *   nagar → ngr, nagri → ngr, naggar → ngr;  nand nagri → ndngr = nandanagri.
 * Matching on skeletons is honest — it maps spellings, it never invents a
 * place. (kept in step with server/core_engine.py's use; the idea mirrors
 * Photon/Nominatim's normalised search.) */
const DIGRAPHS: [RegExp, string][] = [
  [/ph/g, "f"], [/th/g, "t"], [/dh/g, "d"], [/bh/g, "b"], [/gh/g, "g"],
  [/kh/g, "k"], [/sh/g, "x"], [/ch/g, "c"], [/zh/g, "z"], [/qu/g, "k"],
  [/ck/g, "k"], [/sch/g, "x"],
];
export function fold(tok: string): string {
  let s = tok;
  for (const [re, to] of DIGRAPHS) s = s.replace(re, to);
  return s
    .replace(/h/g, "")          // 'h' left over after digraphs is silent
    .replace(/[aeiou]/g, "")
    .replace(/(.)\1+/g, "$1");
}

/** fold() over a whole normalized name — the fused-spelling skeleton:
 * 'nand nagri' and 'nandanagri' are the same fold. */
export const foldName = (nrm: string): string => fold(nrm.replace(/ /g, ""));
