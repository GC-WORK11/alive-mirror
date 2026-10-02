import { File, Paths } from "expo-file-system";

const ID_FILE = new File(Paths.document, "contributor.txt");
let cached: string | null = null;

/** Anonymous 12-char device id — lets the server count contributors
 * without ever knowing who they are. */
export async function contributorId(): Promise<string> {
  if (cached) return cached;
  try {
    if (ID_FILE.exists) {
      const t = (await ID_FILE.text()).trim();
      if (t) { cached = t; return t; }
    }
  } catch {}
  cached = "anon-" + Math.random().toString(36).slice(2, 10);
  try {
    if (!ID_FILE.exists) ID_FILE.create();
    ID_FILE.write(cached);
  } catch {}
  return cached;
}

export type ObservePayload = {
  vehicle: string;
  coords: number[][];
  duration_s: number;
  dose_ug: number | null;
  avoided_ug: number | null;
};

/** Donate a completed traversal to the collective field. */
export async function observeTrip(api: string, p: ObservePayload): Promise<void> {
  const contributor = await contributorId();
  await fetch(`${api}/observe`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ ...p, contributor }),
  });
}

export type ReportKind = "dust" | "smoke" | "burning" | "clean";

export async function postReport(api: string, kind: ReportKind, lat: number, lon: number): Promise<void> {
  const contributor = await contributorId();
  await fetch(`${api}/report`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ kind, lat, lon, contributor }),
  });
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
