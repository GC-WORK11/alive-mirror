// T0 — the on-device search tier (docs/plan/04 §2).
// Bundled Delhi gazetteer behind a prefix index; answers in <5 ms so the
// first suggestion paints inside a frame (<16 ms) while the server tiers
// (client.ts) stream in behind it. normalize() is shared with the
// merge/dedupe layer so every tier keys names identically.

type Raw = { n: string; c: string; lat: number; lon: number; w: number; k: number };

export type LatLon = { lat: number; lon: number };
export type SearchTier = "t0" | "t1" | "t2";

export type PlaceResult = {
  name: string;
  subtitle: string;          // short address or category label
  lat: number;
  lon: number;
  kind: string;              // gazetteer/server category
  outside_ncr: boolean;
  tier: SearchTier;
};

// What the shell receives from SearchScreen.onSelect.
export type SearchSelection =
  | { type: "place"; place: PlaceResult }
  | { type: "current_location" }
  | { type: "choose_on_map" };

// Delhi NCR bounds — the same box App.tsx uses for the "outside Delhi" tag.
const NCR = { minLon: 76.75, maxLon: 77.95, minLat: 28.15, maxLat: 28.98 };
export const inNcr = (lat: number, lon: number) =>
  lon > NCR.minLon && lon < NCR.maxLon && lat > NCR.minLat && lat < NCR.maxLat;
export const DELHI_CENTER: LatLon = { lat: 28.6139, lon: 77.209 };

// Fast km estimate near Delhi (~28.6°N) — same constants as the rest of the
// app so distances read identically everywhere.
export const distKm = (a: LatLon, b: LatLon): number =>
  Math.hypot((a.lat - b.lat) * 110.6, (a.lon - b.lon) * 99.4);

// Hinglish / common abbreviations (docs/plan/04 §2 normalization table).
// Applied query-side; full names are also reverse-aliased at index time so
// "gk" finds Greater Kailash even before expansion is considered.
const ABBREV: Record<string, string> = {
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
const EXPANSIONS: [string, string][] = Object.entries(ABBREV).map(([ab, exp]) => [exp, ab]);

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

// Category → short label (mirrors src/gazetteer.ts so T0 rows read the same).
const SUB: Record<string, string> = {
  locality: "delhi", macrohood: "delhi", neighborhood: "neighbourhood",
  monument: "monument", historic_site: "historic site", museum: "museum",
  restaurant: "restaurant", cafe: "cafe", hotel: "hotel", hospital: "hospital",
  place_of_worship: "place of worship", hindu_temple: "temple", mosque: "mosque",
  gurudwara: "gurdwara", church: "church", shopping_mall: "mall",
  bank_or_credit_union: "bank", school: "school", college: "college",
  university: "university", park: "park", stadium: "stadium",
  metro_station: "metro station", transit_stop: "transit stop",
  train_station: "railway station", bus_station: "bus station",
  airport: "airport", movie_theater: "cinema", gym: "gym",
  police: "police", fire_station: "fire station", fuel_station: "fuel",
  landmark: "landmark", tourist_attraction: "attraction",
};

type Entry = {
  n: string; c: string; lat: number; lon: number; w: number; k: number;
  nrm: string; toks: string[];
};

let ENTRIES: Entry[] | null = null;
let PREFIX: Map<string, number[]> | null = null;

const MAX_PREFIX = 8;   // longest indexed prefix per token
const PREFIX_CAP = 80;  // max ids kept per prefix (heaviest first)

const weight = (e: Entry) => e.w + e.k * 2;

function build(): void {
  if (ENTRIES) return;
  const raw = require("../../assets/delhi-gazetteer.json") as Raw[];
  const entries: Entry[] = [];
  const prefix = new Map<string, number[]>();

  for (const g of raw) {
    const nrm = g.n.toLowerCase().replace(/[^a-z0-9]+/g, " ").replace(/\s+/g, " ").trim();
    if (!nrm) continue;
    const e: Entry = { n: g.n, c: g.c, lat: g.lat, lon: g.lon, w: g.w, k: g.k, nrm, toks: nrm.split(" ") };
    const id = entries.push(e) - 1;

    const keys = new Set<string>();
    for (const tok of e.toks)
      for (let l = 1; l <= Math.min(tok.length, MAX_PREFIX); l++) keys.add(tok.slice(0, l));
    // reverse aliases: a name containing "greater kailash" also answers to "gk"
    for (const [exp, ab] of EXPANSIONS)
      if (nrm.includes(exp))
        for (let l = 1; l <= Math.min(ab.length, MAX_PREFIX); l++) keys.add(ab.slice(0, l));

    for (const key of keys) {
      const list = prefix.get(key);
      if (list) list.push(id);
      else prefix.set(key, [id]);
    }
  }

  for (const ids of prefix.values())
    if (ids.length > PREFIX_CAP) {
      ids.sort((a, b) => weight(entries[b]) - weight(entries[a]));
      ids.length = PREFIX_CAP;
    }

  ENTRIES = entries;
  PREFIX = prefix;
}

/** Preload the gazetteer + index (call when the search UI opens). */
export function warm(): void {
  build();
}

/** On-device search: prefix-index lookup, distance+weight ranked.
 * Typical <5 ms. */
export function query(q: string, userLoc?: LatLon | null, limit = 8): PlaceResult[] {
  build();
  const nq = normalize(q);
  const entries = ENTRIES!;
  const prefix = PREFIX!;
  if (!nq) return [];

  const qToks = nq.split(" ");
  // Candidate pool = posting list of the rarest query token; every other
  // token is then verified against the entry's tokens. Postings are capped
  // at PREFIX_CAP so the scan is bounded.
  const lists = qToks.map((tk) => prefix.get(tk.slice(0, MAX_PREFIX)) ?? []);
  if (lists[0].length === 0) return [];
  let base = 0;
  for (let i = 1; i < lists.length; i++) if (lists[i].length < lists[base].length) base = i;

  const scored: { s: number; e: Entry }[] = [];
  outer: for (const id of lists[base]) {
    const e = entries[id];
    const allToks = qToks.every((qt) => e.toks.some((nt) => nt.startsWith(qt)));
    const phrase = e.nrm.startsWith(nq) || e.nrm.includes(` ${nq}`) || e.nrm.includes(nq);
    if (!allToks && !phrase) continue outer;
    let s = e.nrm.startsWith(nq) ? 100 : allToks ? 70 : 40;
    s += weight(e);
    if (userLoc) s -= Math.min(distKm(e, userLoc), 60) * 0.8;
    scored.push({ s, e });
  }

  scored.sort((a, b) => b.s - a.s);
  const seen = new Set<string>();
  const out: PlaceResult[] = [];
  for (const { e } of scored) {
    const key = `${e.nrm}|${e.lat.toFixed(3)}|${e.lon.toFixed(3)}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({
      name: e.n,
      subtitle: SUB[e.c] ?? e.c.replace(/_/g, " "),
      lat: e.lat,
      lon: e.lon,
      kind: e.c,
      outside_ncr: !inNcr(e.lat, e.lon),
      tier: "t0",
    });
    if (out.length >= limit) break;
  }
  return out;
}
