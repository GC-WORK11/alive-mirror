// Picked-place memory for S2 (docs/plan/02): last 5 recents plus the two
// saved slots, Home and Work. Persists as a JSON document via
// expo-file-system; if the FS ever fails we still work in memory for the
// session. Same File/Paths pattern as src/store/ledger.ts.
import { File, Paths } from "expo-file-system";
import { normalize, type PlaceResult } from "./t0";

const FILE = new File(Paths.document, "places.json");
const MAX_RECENTS = 5;

export type SavedSlot = "home" | "work";

export type PlaceStore = {
  recents: PlaceResult[];
  home: PlaceResult | null;
  work: PlaceResult | null;
};

const EMPTY: PlaceStore = { recents: [], home: null, work: null };

// In-memory cache — the fast path after first load, and the whole store
// when the document directory is unavailable.
let mem: PlaceStore | null = null;

const samePlace = (a: PlaceResult, b: PlaceResult) =>
  normalize(a.name) === normalize(b.name) &&
  Math.abs(a.lat - b.lat) < 0.001 &&
  Math.abs(a.lon - b.lon) < 0.001;

function sanitize(raw: unknown): PlaceStore {
  if (!raw || typeof raw !== "object") return EMPTY;
  const o = raw as Partial<PlaceStore>;
  const place = (p: unknown): PlaceResult | null => {
    const r = p as PlaceResult | null;
    return r && typeof r.name === "string" && typeof r.lat === "number" && typeof r.lon === "number"
      ? { ...r, subtitle: r.subtitle ?? "", kind: r.kind ?? "place", tier: r.tier ?? "t0", outside_ncr: !!r.outside_ncr }
      : null;
  };
  return {
    recents: Array.isArray(o.recents)
      ? o.recents.map(place).filter((p): p is PlaceResult => p !== null).slice(0, MAX_RECENTS)
      : [],
    home: place(o.home),
    work: place(o.work),
  };
}

async function persist(s: PlaceStore): Promise<void> {
  mem = s;
  try {
    if (!FILE.exists) FILE.create();
    FILE.write(JSON.stringify(s));
  } catch {
    // in-memory copy still holds — persistence is best-effort
  }
}

/** Load the store (recents + home + work). */
export async function getPlaces(): Promise<PlaceStore> {
  if (mem) return mem;
  try {
    if (FILE.exists) {
      mem = sanitize(JSON.parse(await FILE.text()));
      return mem;
    }
  } catch {}
  mem = EMPTY;
  return mem;
}

/** Record a picked place — most-recent first, deduped, capped at 5. */
export async function addRecent(p: PlaceResult): Promise<PlaceResult[]> {
  const s = await getPlaces();
  const recents = [p, ...s.recents.filter((r) => !samePlace(r, p))].slice(0, MAX_RECENTS);
  await persist({ ...s, recents });
  return recents;
}

/** Set or clear a saved slot. `setSaved("home", null)` removes Home. */
export async function setSaved(slot: SavedSlot, p: PlaceResult | null): Promise<PlaceStore> {
  const s = await getPlaces();
  const next = { ...s, [slot]: p };
  await persist(next);
  return next;
}

/** Drop all recents (saved slots untouched). */
export async function clearRecents(): Promise<PlaceStore> {
  const s = await getPlaces();
  const next = { ...s, recents: [] };
  await persist(next);
  return next;
}

/** "Delete my data" — recents + saved slots are location history, the
 *  most personal thing on the phone. Drop the mirror AND the file. */
export async function clearPlaces(): Promise<void> {
  mem = null;
  try {
    if (FILE.exists) FILE.delete();
  } catch {}
}
