/** Shell settings — one JSON file in the app's document dir.
 * lang · voice guidance · anonymous data sharing · morning brief ·
 * saved vehicle · saved places. Delete-my-data wipes it along with
 * the ledger and contributor id. */
import { File, Paths } from "expo-file-system";
import type { Lang } from "../../i18n/strings";

export type SavedPlace = { name: string; lat: number; lon: number };

export type ShellSettings = {
  lang: Lang;
  voice: boolean;          // turn-guidance voice (SEAM: TTS engine lands with nav lane)
  share: boolean;          // anonymous traversal donation — on by default (doc 02 §7)
  brief: boolean;          // daily cleanest-window notification
  vehicle: string | null;  // S8 choice, e.g. "bike" | "car" | "auto"
  home: SavedPlace | null;
  work: SavedPlace | null;
};

export const DEFAULT_SETTINGS: ShellSettings = {
  lang: "en", voice: true, share: true, brief: false,
  vehicle: null, home: null, work: null,
};

const FILE = new File(Paths.document, "settings.json");

export async function loadSettings(): Promise<ShellSettings> {
  try {
    if (FILE.exists) {
      const j = JSON.parse(await FILE.text());
      return { ...DEFAULT_SETTINGS, ...(j ?? {}) };
    }
  } catch {}
  return { ...DEFAULT_SETTINGS };
}

export function saveSettings(s: ShellSettings): void {
  try {
    if (!FILE.exists) FILE.create();
    FILE.write(JSON.stringify(s));
  } catch {}
}

/** "Delete my data" — ledger, contributor id, settings. Real removal. */
export function clearAllData(): void {
  for (const name of ["settings.json", "ledger.json", "contributor.txt", "intro_seen.txt"]) {
    try {
      const f = new File(Paths.document, name);
      if (f.exists) f.delete();
    } catch {}
  }
}
