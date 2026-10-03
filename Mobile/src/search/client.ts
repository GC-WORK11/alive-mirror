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
// hit the same backend.
export const API_BASE: string =
  process.env.EXPO_PUBLIC_API_URL ??
  Platform.select({ android: "http://10.0.2.2:8000", default: "http://localhost:8000" }) ??
  "http://localhost:8000";

export type ServerTiers = {
  t1: PlaceResult[];
  t2: PlaceResult[];
  tookMs: number | null;
};

export const EMPTY_TIERS: ServerTiers = { t1: [], t2: [], tookMs: null };

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

function toPlace(r: RawRow, tier: "t1" | "t2"): PlaceResult | null {
  if (typeof r.lat !== "number" || typeof r.lon !== "number") return null;
  const name = (r.name ?? r.label?.split(",")[0] ?? "").trim();
  if (!name) return null;
  return {
    name,
    subtitle: (r.subtitle ?? r.address ?? (r.label ? r.label.split(",").slice(1).join(",").trim() : "")).trim(),
    lat: r.lat,
    lon: r.lon,
    kind: r.kind ?? r.category ?? "place",
    outside_ncr: r.outside_ncr ?? !inNcr(r.lat, r.lon),
    tier,
  };
}

/** One shot at `${API_BASE}/v2/search`. Caller owns the AbortSignal. */
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
  const res = await fetch(url, { signal });
  if (!res.ok) throw new Error(`v2/search http ${res.status}`);
  const j = (await res.json()) as {
    t1?: RawRow[];
    t2?: RawRow[];
    results?: RawRow[];   // legacy /search shape — treated as t1
    took_ms?: number;
  };
  const t1raw = Array.isArray(j.t1) ? j.t1 : Array.isArray(j.results) ? j.results : [];
  const t2raw = Array.isArray(j.t2) ? j.t2 : [];
  return {
    t1: t1raw.map((r) => toPlace(r, "t1")).filter((r): r is PlaceResult => r !== null),
    t2: t2raw.map((r) => toPlace(r, "t2")).filter((r): r is PlaceResult => r !== null),
    tookMs: typeof j.took_ms === "number" ? j.took_ms : null,
  };
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
      fetchTiers(text, loc, ctrl.signal)
        .then((tiers) => {
          if (seq === this.seq) onResults(tiers, text);
        })
        .catch((err: unknown) => {
          if (seq !== this.seq) return;
          if (err instanceof Error && err.name === "AbortError") return;
          // dead network still leaves T0 on screen — deliver empty tiers so
          // the UI can stop waiting
          onResults(EMPTY_TIERS, text);
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
