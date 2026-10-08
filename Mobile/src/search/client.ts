// Server search tiers (docs/plan/04 §2): one HTTP call per keystroke to our
// server, which races T1 (C++ index, OSM + cached Amazon places) against T2
// (Amazon Location Suggest / HERE). Mechanics enforced here:
//   - every keystroke cancels the in-flight request (AbortController)
//   - first character fires immediately; further typing debounces 80 ms
//   - stale responses are dropped by a sequence guard
import { Platform } from "react-native";
import { DELHI_CENTER, NCR_BOUNDS, inNcr, normalize, type LatLon, type PlaceResult } from "./t0";

// Same resolution as App.tsx — EXPO_PUBLIC_API_URL, else the emulator
// loopback aliases. Do not diverge: the shell and the search tiers must
// hit the same backend. Release builds bake EXPO_PUBLIC_API_URL and must
// not ship loopback strings — the fallback is dev-only so Hermes folds
// it out of the production bundle.
export const API_BASE: string =
  process.env.EXPO_PUBLIC_API_URL ??
  (__DEV__
    ? Platform.select({ android: "http://10.0.2.2:8000", default: "http://localhost:8000" }) ??
      "http://localhost:8000"
    : "");

export type ServerTiers = {
  t1: PlaceResult[];
  t2: PlaceResult[];
  /** t3 — public-OSM geocoder fallback (Photon). Labeled rows that ride
      behind our own tiers; never shadows t0/t1/t2 in the merge order. */
  t3: PlaceResult[];
  tookMs: number | null;
};

export const EMPTY_TIERS: ServerTiers = { t1: [], t2: [], t3: [], tookMs: null };

type RawRow = {
  name?: string;
  label?: string;
  subtitle?: string;
  address?: string;
  lat?: number;
  lon?: number;
  kind?: string;
  category?: string;
  outside_ncr?: boolean;
  /* F2 — the server's substitution metadata (v2/search._place_row /
     _area_row / _compound_row): how the row matched, the resolved
     anchor's name, whether the ask was multi-part. Dropping it made a
     category-or-area substitute print like a direct name hit. */
  match?: string;
  match_rank?: number;
  anchor?: string;
  compound?: boolean;
};

/** Gazetteer rows occasionally surface raw OSM tag strings
 * ("amenity:place_of_worship") as the address/subtitle — strip the
 * namespace prefix and tidy underscores so the row reads like an
 * address, not a tag. Real addresses keep their commas untouched. */
const OSM_TAG_PREFIX = /^(amenity|tourism|shop|leisure|office|historic|building|man_made|natural|place|highway|aeroway|railway|public_transport|addr|landuse|waterway|power|junction|barrier|entrance|military|indoor|aerialway|craft|healthcare|emergency|club|boundary|misc):/;

/** Tag-value residues that are still jargon after the prefix strip —
 * mapped to the plain word a person would say. */
const RESIDUE_LABELS: Record<string, string> = {
  interpolation: "address",
  housenumber: "address",
  housename: "address",
  named: "place",
};

function cleanSubtitle(s: string): string {
  const t = s.trim();
  if (OSM_TAG_PREFIX.test(t)) {
    const raw = t.replace(OSM_TAG_PREFIX, "").trim();
    return RESIDUE_LABELS[raw] ?? raw.replace(/_/g, " ").trim();
  }
  // bare kind token ("historic_site") — read like words, not a tag
  if (/^[a-z][a-z_]+$/.test(t) && t.includes("_")) return t.replace(/_/g, " ");
  return t;
}

function toPlace(r: RawRow, tier: "t1" | "t2"): PlaceResult | null {
  if (typeof r.lat !== "number" || typeof r.lon !== "number") return null;
  const name = (r.name ?? r.label?.split(",")[0] ?? "").trim();
  if (!name) return null;
  return {
    name,
    subtitle: cleanSubtitle(
      r.subtitle ?? r.address ?? (r.label ? r.label.split(",").slice(1).join(",").trim() : ""),
    ),
    lat: r.lat,
    lon: r.lon,
    kind: r.kind ?? r.category ?? "place",
    outside_ncr: r.outside_ncr ?? !inNcr(r.lat, r.lon),
    tier,
    /* the wire's own honesty fields ride through untouched — an
       unexpected match value still surfaces, never silently zeroed */
    ...(r.match != null
      ? { match: r.match as PlaceResult["match"], anchor: r.anchor, compound: r.compound }
      : {}),
  };
}

/** One shot at `${API_BASE}/v2/search`. Caller owns the AbortSignal; we add
 * a hard ceiling so a hung socket can't pin the suggestions panel — a search
 * still running at SEARCH_TIMEOUT_MS is dead for typing UX anyway. */
export const SEARCH_TIMEOUT_MS = 5000;

export async function fetchTiers(
  q: string,
  loc: LatLon | null | undefined,
  signal: AbortSignal,
  limit = 12,
): Promise<ServerTiers> {
  const bias = loc ?? DELHI_CENTER;
  const url =
    `${API_BASE}/v2/search?q=${encodeURIComponent(q)}` +
    `&lat=${bias.lat}&lon=${bias.lon}&limit=${limit}`;
  // link the caller's signal into our own controller so either aborts the fetch
  const inner = new AbortController();
  const onAbort = () => inner.abort();
  if (signal.aborted) inner.abort();
  else signal.addEventListener("abort", onAbort);
  const timer = setTimeout(() => inner.abort(), SEARCH_TIMEOUT_MS);
  let res: Response;
  try {
    res = await fetch(url, { signal: inner.signal });
  } finally {
    clearTimeout(timer);
    signal.removeEventListener("abort", onAbort);
  }
  if (!res.ok) throw new Error(`v2/search http ${res.status}`);
  const j = (await res.json()) as {
    t1?: RawRow[];
    t2?: RawRow[];
    results?: RawRow[];   // legacy /search shape — treated as t1
    took_ms?: number | { total?: number };
  };
  const t1raw = Array.isArray(j.t1) ? j.t1 : Array.isArray(j.results) ? j.results : [];
  const t2raw = Array.isArray(j.t2) ? j.t2 : [];
  const tookMs = typeof j.took_ms === "number" ? j.took_ms
    : typeof j.took_ms?.total === "number" ? j.took_ms.total : null;
  return {
    t1: t1raw.map((r) => toPlace(r, "t1")).filter((r): r is PlaceResult => r !== null),
    t2: t2raw.map((r) => toPlace(r, "t2")).filter((r): r is PlaceResult => r !== null),
    t3: [],
    tookMs,
  };
}

/* ---------------------------------------------------------------------------
 * t3 — public free geocoders, the ₹0 honest network fallback: Photon
 * (photon.komoot.io — faster, GeoJSON) first, one Nominatim shot when
 * Photon errors or answers empty. OSM-derived like our own corpus and it
 * natively understands 'X near Y' + address parts our bundled index can't
 * reach. Rows are labeled 'from the web · live' in the subtitle so the
 * panel never passes a network answer off as a bundled one. Throttled to
 * one web call per WEB_MIN_MS (Nominatim's 1 req/s policy is the strict
 * tier), >=3 chars, NCR-bounded, and gated on WEAK local coverage — a
 * healthy own-index answer never spends a public-API call. It also never
 * rides inside the t1/t2 delivery path: rows stream in on a second
 * callback so a slow public geocoder can't hold back our own tiers.
 * ------------------------------------------------------------------------- */

const PHOTON_URL = "https://photon.komoot.io/api/";
const NOMINATIM_URL = "https://nominatim.openstreetmap.org/search";
const WEB_MIN_MS = 1000;
const WEB_MIN_CHARS = 3;
/** t0+t1+t2 rows at/above which the web tier stays off. */
const WEB_WEAK_MAX = 3;
const WEB_LIVE = "from the web · live";
let lastWebAt = 0;

type PhotonFeature = {
  geometry?: { coordinates?: [number, number] };
  properties?: {
    name?: string; street?: string; housenumber?: string;
    locality?: string; district?: string; city?: string; state?: string;
    postcode?: string; osm_key?: string; osm_value?: string; type?: string;
  };
};

export async function fetchPhoton(
  q: string,
  loc: LatLon | null | undefined,
  signal: AbortSignal,
  limit = 6,
): Promise<PlaceResult[]> {
  const bias = loc ?? DELHI_CENTER;
  const url =
    `${PHOTON_URL}?q=${encodeURIComponent(q)}&limit=${limit}` +
    `&lat=${bias.lat}&lon=${bias.lon}` +
    // bbox = minLon,minLat,maxLon,maxLat — the NCR box, server-canonical
    `&bbox=${NCR_BOUNDS.join(",")}`;
  const inner = new AbortController();
  const onAbort = () => inner.abort();
  if (signal.aborted) inner.abort();
  else signal.addEventListener("abort", onAbort);
  const timer = setTimeout(() => inner.abort(), SEARCH_TIMEOUT_MS);
  let res: Response;
  try {
    res = await fetch(url, {
      signal: inner.signal,
      headers: { Accept: "application/json" },
    });
  } finally {
    clearTimeout(timer);
    signal.removeEventListener("abort", onAbort);
  }
  if (!res.ok) throw new Error(`photon http ${res.status}`);
  const j = (await res.json()) as { features?: PhotonFeature[] };
  const out: PlaceResult[] = [];
  for (const f of j.features ?? []) {
    const c = f.geometry?.coordinates;
    const p = f.properties;
    if (!c || typeof c[0] !== "number" || typeof c[1] !== "number") continue;
    const name = (p?.name ?? "").trim()
      || [p?.housenumber, p?.street].filter(Boolean).join(" ").trim()
      || (p?.type ?? "").trim();
    if (!name) continue;
    // resolved address like Google shows it: house + street, area, city
    const addr = [p?.housenumber, p?.street].filter(Boolean).join(" ").trim();
    const area = [p?.locality, p?.district, p?.city].filter(Boolean).join(", ").trim();
    const sub = [addr && addr !== name ? addr : "", area]
      .filter(Boolean).join(", ");
    out.push({
      name,
      subtitle: `${sub ? `${sub} · ` : ""}${WEB_LIVE}`,
      lat: c[1],
      lon: c[0],
      kind: p?.osm_value ?? p?.type ?? "place",
      outside_ncr: !inNcr(c[1], c[0]),
      tier: "t3",
    });
  }
  return out;
}

/* Nominatim — the second web shot. Public endpoint: honest UA + contact
 * style tag (their usage policy), JSON v2 with addressdetails so the
 * subtitle can show a real house/street/area breakdown like Photon's. */
type NomRow = {
  display_name?: string;
  name?: string;
  lat?: string;
  lon?: string;
  type?: string;
  class?: string;
  address?: {
    house_number?: string; road?: string; neighbourhood?: string;
    suburb?: string; city?: string; state?: string;
  };
};

export async function fetchNominatim(
  q: string,
  loc: LatLon | null | undefined,
  signal: AbortSignal,
  limit = 6,
): Promise<PlaceResult[]> {
  const bias = loc ?? DELHI_CENTER;
  const url =
    `${NOMINATIM_URL}?q=${encodeURIComponent(q)}&format=jsonv2&limit=${limit}` +
    // viewbox = left(lonMin),top(latMax),right(lonMax),bottom(latMin)
    `&viewbox=${NCR_BOUNDS[0]},${NCR_BOUNDS[3]},${NCR_BOUNDS[2]},${NCR_BOUNDS[1]}` +
    `&lat=${bias.lat}&lon=${bias.lon}&accept-language=en,hi&addressdetails=1`;
  const inner = new AbortController();
  const onAbort = () => inner.abort();
  if (signal.aborted) inner.abort();
  else signal.addEventListener("abort", onAbort);
  // tighter than the server tier — a public geocoder that hasn't answered
  // in ~1.5 s isn't going to beat 'weak local' honestly anyway
  const timer = setTimeout(() => inner.abort(), 1500);
  let res: Response;
  try {
    res = await fetch(url, {
      signal: inner.signal,
      headers: {
        Accept: "application/json",
        // honest identification per nominatim.openstreetmap.org policy
        "User-Agent": "ALive-108 Delhi-NCR air quality app (search fallback)",
      },
    });
  } finally {
    clearTimeout(timer);
    signal.removeEventListener("abort", onAbort);
  }
  if (!res.ok) throw new Error(`nominatim http ${res.status}`);
  const j = (await res.json()) as NomRow[];
  const out: PlaceResult[] = [];
  for (const r of Array.isArray(j) ? j : []) {
    const lat = parseFloat(r.lat ?? "");
    const lon = parseFloat(r.lon ?? "");
    if (!isFinite(lat) || !isFinite(lon)) continue;
    const parts = (r.display_name ?? r.name ?? "")
      .split(",").map((s) => s.trim()).filter(Boolean);
    const name = parts[0] ?? "";
    if (!name) continue;
    const a = r.address;
    const area = [a?.neighbourhood ?? a?.suburb, a?.city ?? a?.state]
      .filter(Boolean).join(", ");
    const sub = area || parts.slice(1, 3).join(", ");
    out.push({
      name,
      subtitle: `${sub ? `${sub} · ` : ""}${WEB_LIVE}`,
      lat,
      lon,
      kind: r.type ?? r.class ?? "place",
      outside_ncr: !inNcr(lat, lon),
      tier: "t3",
    });
  }
  return out;
}

/** The web fallback chain: one throttled call slot. Photon answers first
 * (or fails fast — a dropped network packet throws immediately, no
 * timeout wait), then a single Nominatim shot. Offline both throw and
 * the tier honestly delivers nothing. */
export async function fetchWeb(
  q: string,
  loc: LatLon | null | undefined,
  signal: AbortSignal,
  limit = 6,
): Promise<PlaceResult[]> {
  const now = Date.now();
  if (now - lastWebAt < WEB_MIN_MS) return [];
  lastWebAt = now;
  try {
    const r = await fetchPhoton(q, loc, signal, limit);
    if (r.length) return r;
  } catch {
    /* photon unreachable — take the nominatim shot */
  }
  try {
    return await fetchNominatim(q, loc, signal, limit);
  } catch {
    return [];
  }
}

/** Admin-area rows name the place they contain — the OSM "Connaught
 * Place" district polygon IS Connaught Place, not a second destination
 * worth its own row. Same normalized name + an admin container on either
 * side → one place; the loose bound matches t0's own same-name radius
 * (a polygon centroid sits a few hundred metres off the place point —
 * the gazetteer district row is 117 m from the macrohood). Two
 * non-admin rows still need the tight 75 m — real same-name neighbours
 * exist (the two Connaught Lanes are 600 m apart). */
const ADMIN_KINDS = new Set(["administrative", "district"]);
const isAdminArea = (p: PlaceResult) => ADMIN_KINDS.has(p.kind);

export const sameNamedPlace = (a: PlaceResult, b: PlaceResult): boolean => {
  if (normalize(a.name) !== normalize(b.name)) return false;
  const d = Math.hypot((a.lat - b.lat) * 110.6, (a.lon - b.lon) * 99.4) * 1000;
  return d < 75 || (d < 400 && (isAdminArea(a) || isAdminArea(b)));
};

/** Merge server tiers + dedupe by same-named-place rule (doc 04 §2; t0's
 *  own dedupe is upstream). Earlier lists win — except an admin row that
 *  arrived first hands its slot to the real place row of the same name,
 *  so the kept row is always the actionable one. */
export function mergeResults(...lists: PlaceResult[][]): PlaceResult[] {
  const kept: PlaceResult[] = [];
  for (const list of lists)
    for (const p of list) {
      const dup = kept.findIndex((k) => sameNamedPlace(k, p));
      if (dup < 0) { kept.push(p); continue; }
      if (isAdminArea(kept[dup]) && !isAdminArea(p)) kept[dup] = p;
    }
  return kept;
}

export type OnServerResults = (tiers: ServerTiers, forQuery: string) => void;

/** Keystroke-driver for the server tiers. One instance per mounted search
 * screen. setQuery() aborts whatever is in flight — the latest call is the
 * only one whose results are delivered. */
export class ServerSearch {
  private ctrl: AbortController | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private seq = 0;
  private prevText = "";

  /* parameter property avoided — node's strip-types loader (the unit
     runners) can't parse `constructor(private x)` */
  private debounceMs: number;
  constructor(debounceMs = 80) { this.debounceMs = debounceMs; }

  /** Feed the raw text field contents. First character of a fresh query
   * fires immediately; subsequent edits debounce. */
  setQuery(
    q: string,
    loc: LatLon | null | undefined,
    onResults: OnServerResults,
    opts?: { localCount?: () => number },
  ): void {
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    const text = q.trim();
    const firstChar = this.prevText === "" && text !== "";
    this.prevText = text;
    if (!text) {
      this.cancel();
      return;
    }
    const fire = () => {
      const seq = ++this.seq;
      this.ctrl?.abort();
      const ctrl = new AbortController();
      this.ctrl = ctrl;
      const localCount = opts?.localCount?.() ?? 0;

      /* the web tier never rides inside the t1/t2 path: own-server rows
         deliver on the first callback, and — only when total coverage is
         weak — the public geocoders answer on a SECOND callback. */
      const web = (base: ServerTiers) => {
        if (text.length < WEB_MIN_CHARS) return;
        if (localCount + base.t1.length + base.t2.length >= WEB_WEAK_MAX) return;
        fetchWeb(text, loc, ctrl.signal)
          .then((t3) => {
            if (seq !== this.seq || t3.length === 0) return;
            onResults({ t1: base.t1, t2: base.t2, t3, tookMs: base.tookMs }, text);
          })
          .catch(() => {});
      };

      fetchTiers(text, loc, ctrl.signal)
        .then((tiers) => {
          if (seq !== this.seq) return;
          onResults(tiers, text);   // t1/t2 land the moment our server answers
          web(tiers);
        })
        .catch((err: unknown) => {
          if (seq !== this.seq) return;
          // caller-initiated aborts are already dropped by the seq bump;
          // a TIMEOUT abort (fetchTiers' inner ceiling) must still deliver
          // empty tiers or the panel waits forever
          if (err instanceof Error && err.name === "AbortError"
              && ctrl.signal.aborted) return;
          // dead network still leaves T0 on screen — deliver empty tiers so
          // the UI can stop waiting, then let the web tier take its shot
          onResults(EMPTY_TIERS, text);
          web(EMPTY_TIERS);
        });
    };
    if (firstChar) fire();
    else this.timer = setTimeout(fire, this.debounceMs);
  }

  cancel(): void {
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    this.seq++;
    this.ctrl?.abort();
    this.ctrl = null;
  }

  /** Full reset — call when the screen hides. */
  dispose(): void {
    this.cancel();
    this.prevText = "";
  }
}
