// Typed TTL cache on expo-file-system (docs/plan/offline.md §1).
//
// One JSON file per key under <document>/alive-cache/, envelope
// { k, t, ttl, v }. Lives in Paths.document — last-good data must
// survive the OS purging Paths.cache when storage is tight.
//
// Two read modes, because "last known air" is still honest data:
//   cacheGet  — standard TTL semantics: past ttlMs is a miss
//   cachePeek — last-good semantics: returns whatever is on disk and
//               flags `fresh` so the caller can dim/label it
// Every hit carries ageS so the UI can say how old the number is.
import { Directory, File, Paths } from "expo-file-system";

const DIR = new Directory(Paths.document, "alive-cache");

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

/** Standard TTL read: null when missing OR past its freshness window. */
export async function cacheGet<T>(key: string): Promise<CacheHit<T> | null> {
  const hit = await read<T>(key);
  return hit != null && hit.fresh ? hit : null;
}

/** Last-good read: whatever is on disk, `fresh` flag included.
 * This is the read offline fallbacks use — a labeled 3-hour-old AQI
 * beats nothing on screen (docs/plan/02: show it only when it's true,
 * and say when it stopped being true). */
export async function cachePeek<T>(key: string): Promise<CacheHit<T> | null> {
  return read<T>(key);
}

/** Write a value under `key`, declaring `ttlMs` as its freshness window. */
export async function cacheSet<T>(key: string, value: T, ttlMs: number): Promise<void> {
  try {
    ensureDir();
    const f = fileFor(key);
    if (!f.exists) f.create({ intermediates: true });
    const env: Envelope<T> = { k: key, t: Date.now(), ttl: ttlMs, v: value };
    f.write(JSON.stringify(env));
  } catch {
    // cache is best-effort — a failed write must never break the caller
  }
}

/** Drop one key. Safe when absent. */
export async function cacheInvalidate(key: string): Promise<void> {
  try {
    const f = fileFor(key);
    if (f.exists) f.delete();
  } catch {}
}

/** Age in whole seconds of the saved copy, or null when absent —
 * for pills that say "as of 40 min ago" without loading the payload. */
export async function cacheAgeS(key: string): Promise<number | null> {
  const hit = await read<unknown>(key);
  return hit ? hit.ageS : null;
}

/** Drop every cached entry. */
export async function cacheClear(): Promise<number> {
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
