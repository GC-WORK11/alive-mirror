/** Crash-safe JSON document IO — the write pattern for stores whose loss
 *  would be user-visible (ledger, daylog, daysum). docs/lanes/pocket-engine.
 *
 *  WRITE: serialize → <name>.tmp → snapshot current file to <name>.bak →
 *  moveSync(tmp → name, overwrite). The rename is atomic on the
 *  filesystem: a crash mid-write leaves either the old file or a stray
 *  .tmp, never a half-written main. .bak always holds the previous good
 *  generation.
 *
 *  READ: parse + shape-check main; on any failure fall back to .bak;
 *  null when both are unreadable — callers keep their honest empty.
 *
 *  FORMATS: legacy stores (ledger.json, daylog.json) keep their bare
 *  payload — drive lanes read them raw via adb/simctl. `checksum: true`
 *  opts into the enveloped {v,sum,d} form (FNV-1a over the payload) —
 *  used by daysum.json, which nothing else reads. Both forms get the
 *  same atomic+backup writes. */
import { Directory, File, Paths } from "expo-file-system";

/** FNV-1a — the same hash api/cache.ts uses for key filenames. */
export function fnv1a(s: string): string {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return (h >>> 0).toString(16);
}

const at = (name: string, suffix = ""): File =>
  new File(Paths.document, `${name}${suffix}`);

/** Atomic write of one JSON document. Never throws — persistence is
 *  best-effort everywhere it is used (a failed flush must not break the
 *  mutation that scheduled it). */
export function writeJsonDoc(
  name: string, payload: unknown, opts: { checksum?: boolean } = {},
): void {
  try {
    const body = JSON.stringify(payload);
    const text = opts.checksum
      ? JSON.stringify({ v: 1, sum: fnv1a(body), d: payload })
      : body;
    const f = at(name), tmp = at(name, ".tmp"), bak = at(name, ".bak");
    if (tmp.exists) tmp.delete();
    tmp.create({ intermediates: true });
    tmp.write(text);
    if (f.exists) f.copySync(bak, { overwrite: true }); // previous good → .bak
    tmp.moveSync(f, { overwrite: true });             // atomic rename
  } catch {}
}

/** Read + validate one JSON document, falling back to its .bak.
 *  `validate` is the shape check — an object that parses but fails it is
 *  treated as corrupt and skipped (the integrity check for bare-format
 *  files; enveloped files verify their checksum instead). */
export async function readJsonDoc<T>(
  name: string,
  validate: (v: unknown) => v is T,
  opts: { checksum?: boolean } = {},
): Promise<T | null> {
  for (const cand of [at(name), at(name, ".bak")]) {
    try {
      if (!cand.exists) continue;
      const j = JSON.parse(await cand.text()) as unknown;
      let v: unknown = j;
      if (opts.checksum) {
        const env = j as { v?: number; sum?: string; d?: unknown } | null;
        if (env == null || env.v !== 1 || typeof env.sum !== "string") continue;
        if (env.sum !== fnv1a(JSON.stringify(env.d))) continue; // tampered or torn
        v = env.d;
      }
      if (validate(v)) return v;
    } catch {}
  }
  return null;
}

/** "Delete my data" helper — removes the document and its write artifacts. */
export function purgeJsonDoc(name: string): void {
  for (const f of [at(name), at(name, ".tmp"), at(name, ".bak")]) {
    try {
      if (f.exists) f.delete();
    } catch {}
  }
}

/** "Delete my data" — fetch() response bodies also persist on disk,
 *  outside Documents/: NSURLCache's store under
 *  Library/Caches/<bundle>/{fsCachedData/,Cache.db*} and the shared
 *  Library/HTTPStorages jar. Those bodies are personal data — geocode
 *  replies carry the query text plus the caller's live-position bias,
 *  route replies carry origin/destination coords and labels, and
 *  request URLs/headers bake in the anonymous contributor id. Wiping
 *  Documents alone leaves them recoverable until iOS evicts the cache.
 *  Removes exactly the URL-cache artifacts inside the app's cache dir
 *  (shader/font caches are left alone) and the app's HTTPStorages jar;
 *  the OS recreates them empty on the next request. Best-effort like
 *  every purge here — an undeletable entry stays, which a cache is
 *  allowed to do anyway. Verified on iOS sim (wipe-verify lane). */
export function purgeUrlCaches(): void {
  try {
    for (const entry of new Directory(Paths.cache).list()) {
      if (!(entry instanceof Directory)) continue;
      let names: Set<string>;
      try {
        names = new Set(entry.list().map((e) => e.name));
      } catch {
        continue;
      }
      if (!names.has("fsCachedData") && ![...names].some((n) => n.startsWith("Cache.db"))) {
        continue;
      }
      /* <caches>/<bundle>/ — the app's URL-cache home. Delete only the
         URL-cache artifacts, not sibling OS caches (metal shaders etc). */
      for (const e of entry.list()) {
        if (e.name === "fsCachedData" || e.name.startsWith("Cache.db")) {
          try {
            e.delete();
          } catch {}
        }
      }
    }
  } catch {}
  try {
    const lib = new Directory(Paths.cache).parentDirectory; // …/Library
    for (const jar of new Directory(lib, "HTTPStorages").list()) {
      try {
        jar.delete();
      } catch {}
    }
  } catch {}
}
