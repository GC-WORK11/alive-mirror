// Typed TTL cache on expo-file-system (docs/plan/offline.md §1).
//
// One JSON file per key under <document>/alive-cache/, envelope
// { k, t, ttl, v }. Lives in Paths.document — last-good data must
// survive the OS purging Paths.cache when storage is tight.
//
// One read mode, because "last known air" is still honest data:
//   cachePeek — last-good semantics: returns whatever is on disk and
//               flags `fresh` so the caller can dim/label it
// Every hit carries ageS so the UI can say how old the number is.
import { Directory, File, Paths } from "expo-file-system";

const DIR = new Directory(Paths.document, "alive-cache");

/* Bounds — the store must stay cheap after years (owner ask). Before
   eviction, plan entries (~100 m O/D pairs + vehicle signature) and
   per-route strips accumulated one file per distinct key forever:
   measured 255–420 KB per plan, ~7 KB per strip → a year of commuting
   from varied spots would have grown this dir to tens of MB.
   MAX_AGE: last-good stays last-good while it is plausible "recent
   air" — beyond 30 days even a labeled number is just stale bytes. */
const MAX_ENTRIES = 64;
const MAX_BYTES = 12 * 1024 * 1024;
const MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000;
/* sweep is amortized: every Nth write, so reads (every request) never
   pay for a directory listing and writes stay O(1) in the hot path. */
const SWEEP_EVERY = 16;
let writesSinceSweep = 0;

type Envelope<T> = { k: string; t: number; ttl: number; v: T };

export type CacheHit<T> = {
  value: T;
  /** epoch ms when the entry was written */
  savedAt: number;
  /** whole seconds since the entry was written */
  ageS: number;
  /** ageS*1000 <= ttlMs — within the declared freshness window */
  fresh: boolean;
  ttlMs: number;
};

/** Filesystem-safe, collision-safe file name for a cache key:
 * FNV-1a hex + a readable tail for debugging. */
function fileFor(key: string): File {
  let h = 0x811c9dc5;
  for (let i = 0; i < key.length; i++) {
    h ^= key.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  const tail = key.replace(/[^a-zA-Z0-9._-]/g, "_").slice(-24);
  return new File(DIR, `${(h >>> 0).toString(16)}-${tail}.json`);
}

let dirReady = false;
function ensureDir(): void {
  if (dirReady) return;
  try {
    if (!DIR.exists) DIR.create({ intermediates: true, idempotent: true });
    dirReady = true;
  } catch {
    // leave dirReady false — every call retries
  }
}

function toHit<T>(e: Envelope<T>, now: number): CacheHit<T> {
  const ageMs = Math.max(0, now - e.t);
  return {
    value: e.v,
    savedAt: e.t,
    ageS: Math.floor(ageMs / 1000),
    fresh: ageMs <= e.ttl,
    ttlMs: e.ttl,
  };
}

async function read<T>(key: string): Promise<CacheHit<T> | null> {
  try {
    const f = fileFor(key);
    if (!f.exists) return null;
    const e = JSON.parse(await f.text()) as Envelope<T>;
    if (e == null || typeof e.t !== "number" || e.k !== key) return null;
    return toHit(e, Date.now());
  } catch {
    return null;
  }
}

/** Last-good read: whatever is on disk, `fresh` flag included.
 * This is the read offline fallbacks use — a labeled 3-hour-old AQI
 * beats nothing on screen (docs/plan/02: show it only when it's true,
 * and say when it stopped being true). */
export async function cachePeek<T>(key: string): Promise<CacheHit<T> | null> {
  return read<T>(key);
}

/* Wipe generation: bump on every cacheClear so a fetch that STARTED
   before delete-my-data can never re-write route-GPS files after the
   wipe (Android forensic S2 — plan/strip payloads embed ~100 m O/D
   coords; a late-resolving request resurrected them post-delete). */
let wipeGen = 0;
export function cacheGeneration(): number {
  return wipeGen;
}

/** Write a value under `key`, declaring `ttlMs` as its freshness window.
 * `since` = the generation captured when the request started; a wipe in
 * between means this payload belongs to the deleted era — don't write. */
export async function cacheSet<T>(key: string, value: T, ttlMs: number, since?: number): Promise<void> {
  try {
    if (since != null && since !== wipeGen) return;
    ensureDir();
    const f = fileFor(key);
    if (!f.exists) f.create({ intermediates: true });
    const env: Envelope<T> = { k: key, t: Date.now(), ttl: ttlMs, v: value };
    f.write(JSON.stringify(env));
    if (++writesSinceSweep >= SWEEP_EVERY) {
      writesSinceSweep = 0;
      sweep();
    }
  } catch {
    // cache is best-effort — a failed write must never break the caller
  }
}

/** Metadata-only listing — LRU order without parsing a single body. */
function listEntries(): { f: File; mtime: number; size: number }[] {
  const out: { f: File; mtime: number; size: number }[] = [];
  for (const e of DIR.list()) {
    if (!(e instanceof File)) continue;
    try {
      const mtime = e.modificationTime;
      out.push({
        f: e,
        mtime: typeof mtime === "number" ? mtime : 0,
        size: typeof e.size === "number" ? e.size : 0,
      });
    } catch {}
  }
  out.sort((a, b) => a.mtime - b.mtime); // oldest first
  return out;
}

/** Evict: entries past MAX_AGE_MS die first (in mtime order), then
   oldest-first until entry-count and byte caps hold. Runs inside
   cacheSet — the file just written is newest, so it survives. */
function sweep(): void {
  try {
    const files = listEntries();
    const now = Date.now();
    let bytes = 0;
    for (const e of files) bytes += e.size;
    let left = files.length;
    for (const e of files) {
      const overCount = left > MAX_ENTRIES;
      const overBytes = bytes > MAX_BYTES;
      const tooOld = now - e.mtime > MAX_AGE_MS;
      if (!overCount && !overBytes && !tooOld) break; // sorted oldest-first
      try {
        e.f.delete();
        left--;
        bytes -= e.size;
      } catch {}
    }
  } catch {}
}

/** Directory size + entry count — settings diagnostics and the
   storage audit read this; metadata only, no bodies parsed. */
export function cacheStats(): { entries: number; bytes: number } {
  try {
    const files = listEntries();
    let bytes = 0;
    for (const e of files) bytes += e.size;
    return { entries: files.length, bytes };
  } catch {
    return { entries: 0, bytes: 0 };
  }
}

/** Drop every cached entry. */
export async function cacheClear(): Promise<number> {
  wipeGen++;
  let n = 0;
  try {
    ensureDir();
    for (const e of DIR.list()) {
      if (e instanceof File) {
        try {
          e.delete();
          n++;
        } catch {}
      }
    }
  } catch {}
  return n;
}

/** Canonical cache keys — keep them here so every lane agrees. */
export const cacheKeys = {
  /** last-good GET /v2/city ("Delhi today") */
  city: (): string => "v2:city",
  /** last-good POST /v2/plan options, keyed by a ~100 m-rounded O/D pair
   *  + the vehicle signature — a changed S8 answer must not serve the
   *  stale fleet-prior emissions bands it asked with an older profile.
   *  ~100 m rounding keeps O/D neighbours sharing one entry, so "same
   *  trip as before" finds its cached options */
  plan: (fromLat: number, fromLon: number, toLat: number, toLon: number,
    vkey = ""): string =>
    `v2:plan:${fromLat.toFixed(3)},${fromLon.toFixed(3)}>${toLat.toFixed(3)},${toLon.toFixed(3)}|${vkey}`,
  /** last-good GET /v2/strip by route_id */
  strip: (routeId: string): string => `v2:strip:${routeId}`,
};
