// Server search tiers (docs/plan/04 §2): one HTTP call per keystroke to our
// server, which races T1 (C++ index, OSM + cached Amazon places) against T2
// (Amazon Location Suggest / HERE). Mechanics enforced here:
//   - every keystroke cancels the in-flight request (AbortController)
//   - first character fires immediately; further typing debounces 80 ms
//   - stale responses are dropped by a sequence guard
import { Platform } from "react-native";
import { DELHI_CENTER, inNcr, normalize, type LatLon, type PlaceResult } from "./t0";

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
 * t3 — Photon public geocoder (photon.komoot.io), the ₹0 honest network
 * fallback. OSM-derived like our own corpus, free for this request volume,
 * and it natively understands 'X near Y' + address parts our bundled index
 * can't reach. Rows are labeled '· OpenStreetMap' in the subtitle so the
 * panel never passes a network answer off as a bundled one. Throttled to
 * one call per PHOTON_MIN_MS per screen, >=3 chars, NCR-bounded.
 * ------------------------------------------------------------------------- */

const PHOTON_URL = "https://photon.komoot.io/api/";
const PHOTON_MIN_MS = 700;
const PHOTON_MIN_CHARS = 3;
let lastPhotonAt = 0;

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
  const now = Date.now();
  if (now - lastPhotonAt < PHOTON_MIN_MS) return [];
  lastPhotonAt = now;
  const bias = loc ?? DELHI_CENTER;
  const url =
    `${PHOTON_URL}?q=${encodeURIComponent(q)}&limit=${limit}` +
    `&lat=${bias.lat}&lon=${bias.lon}` +
    // bbox = minLon,minLat,maxLon,maxLat — the NCR box, server-style
    `&bbox=76.75,28.15,77.95,28.98`;
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
      subtitle: `${sub ? `${sub} · ` : ""}OpenStreetMap`,
      lat: c[1],
      lon: c[0],
      kind: p?.osm_value ?? p?.type ?? "place",
      outside_ncr: !inNcr(c[1], c[0]),
      tier: "t3",
    });
  }
  return out;
}

/** Merge server tiers + dedupe by normalized name within ~75 m
 * (doc 04 §2). Earlier lists win. */
export function mergeResults(...lists: PlaceResult[][]): PlaceResult[] {
  const kept: PlaceResult[] = [];
  for (const list of lists)
    for (const p of list) {
      const dup = kept.some(
        (k) => normalize(k.name) === normalize(p.name) && Math.hypot(
          (k.lat - p.lat) * 110.6, (k.lon - p.lon) * 99.4) * 1000 < 75,
      );
      if (!dup) kept.push(p);
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

  constructor(private debounceMs = 80) {}

  /** Feed the raw text field contents. First character of a fresh query
   * fires immediately; subsequent edits debounce. */
  setQuery(q: string, loc: LatLon | null | undefined, onResults: OnServerResults): void {
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
      const photon = text.length >= PHOTON_MIN_CHARS
        ? fetchPhoton(text, loc, ctrl.signal).catch(() => [] as PlaceResult[])
        : Promise.resolve([] as PlaceResult[]);
      fetchTiers(text, loc, ctrl.signal)
        .then(async (tiers) => {
          if (seq !== this.seq) return;
          tiers.t3 = await photon;
          if (seq === this.seq) onResults(tiers, text);
        })
        .catch((err: unknown) => {
          if (seq !== this.seq) return;
          // caller-initiated aborts are already dropped by the seq bump;
          // a TIMEOUT abort (fetchTiers' inner ceiling) must still deliver
          // empty tiers or the panel waits forever
          if (err instanceof Error && err.name === "AbortError"
              && ctrl.signal.aborted) return;
          // dead network still leaves T0 on screen — deliver empty tiers so
          // the UI can stop waiting. t3 may still have landed: deliver it
          // rather than drop a real answer to a flaky own-server roundtrip
          photon
            .then((t3) => { if (seq === this.seq) onResults({ ...EMPTY_TIERS, t3 }, text); })
            .catch(() => { if (seq === this.seq) onResults(EMPTY_TIERS, text); });
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
