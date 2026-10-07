// Picked-place memory for S2 (docs/plan/02): last 5 recents plus the two
// saved slots, Home and Work. Persists as a JSON document via
// expo-file-system; if the FS ever fails we still work in memory for the
// session. Same File/Paths pattern as src/store/ledger.ts.
import { purgeJsonDoc, readJsonDoc, writeJsonDoc } from "../store/safefile";
import { normalize, type PlaceResult } from "./t0";

const NAME = "places.json";
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
  /* atomic + .bak via safefile — a kill mid-write used to leave a torn
     places.json; in-memory copy still holds either way (best-effort) */
  writeJsonDoc(NAME, s);
}

/** Load the store (recents + home + work). */
export async function getPlaces(): Promise<PlaceStore> {
  if (mem) return mem;
  /* bare-format read w/ .bak fallback: the shape check keeps a
     garbage-typed main from shadowing a good .bak; sanitize() then
     handles torn-but-parseable content → EMPTY, never garbage places */
  mem = sanitize(
    (await readJsonDoc(NAME, (v): v is PlaceStore => !!v && typeof v === "object")) ?? null,
  );
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

/** "Delete my data" — recents + saved slots are location history, the
 *  most personal thing on the phone. Drop the mirror AND the file. */
export async function clearPlaces(): Promise<void> {
  mem = null;
  purgeJsonDoc(NAME); // file + .tmp + .bak — no residue holds a place
}
