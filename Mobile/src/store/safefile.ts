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
import { File, Paths } from "expo-file-system";

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
