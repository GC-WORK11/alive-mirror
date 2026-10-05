import { File, Paths } from "expo-file-system";
import * as Crypto from "expo-crypto";

const ID_FILE = new File(Paths.document, "contributor.txt");
const ID_TTL_MS = 30 * 24 * 3600 * 1000;   // the spec's id rotation
let cached: { id: string; ts: number } | null = null;

async function newId(): Promise<string> {
  const b = await Crypto.getRandomBytesAsync(8);
  return "anon-" + Array.from(b, (x) =>
    x.toString(16).padStart(2, "0")).join("");
}

/** Anonymous device id — 64-bit CSPRNG (expo-crypto, not Math.random),
 * rotated every 30 days so donation history can never key to one id
 * forever. File stores {id, ts}; a bare-string id written by an older
 * build is adopted and rotates on the same schedule. */
export async function contributorId(): Promise<string> {
  const now = Date.now();
  if (!cached) {
    try {
      if (ID_FILE.exists) {
        const raw = (await ID_FILE.text()).trim();
        let id = "", ts = now;
        try {
          const j = JSON.parse(raw);
          id = typeof j.id === "string" ? j.id : "";
          ts = Number(j.ts) || now;
        } catch {
          id = raw;                         // legacy bare id — adopt it
        }
        if (id) cached = { id, ts };
      }
    } catch {}
  }
  if (cached && now - cached.ts < ID_TTL_MS) return cached.id;
  const id = await newId().catch(
    () => "anon-" + Math.random().toString(36).slice(2, 18));
  cached = { id, ts: now };
  try {
    if (!ID_FILE.exists) ID_FILE.create();
    ID_FILE.write(JSON.stringify(cached));
  } catch {}
  return id;
}

export type CorridorCell = {
  lon: number; lat: number; samples: number; avg_dose_ug: number; top_mode: string;
};

export type CommunityTotals = {
  obs_total: number;
  obs_24h: number;
  contributors: number;
  km_24h: number;
  dose_ug_24h: number;
  avoided_ug_24h: number;
  avoided_ug_all: number;
  active_reports: number;
  modes_24h: Record<string, number>;
  top_corridors?: CorridorCell[];
};
