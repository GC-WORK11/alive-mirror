/** Shell settings — one JSON file in the app's document dir.
 * lang · voice guidance · anonymous data sharing · departure reminders ·
 * morning brief · saved vehicle · saved places. Delete-my-data wipes it
 * along with the ledger and contributor id. */
import { File, Paths } from "expo-file-system";
import type { Lang } from "../../i18n/strings";
import { resetLedgerCache } from "../../store/ledger";
import { clearConsent } from "../../store/consent";
import { clearWelcomeSeen } from "../../store/welcome";
import { clearVehicle } from "../../store/vehicle";
import { clearPlaces } from "../../search/recents";
import { clearOutbox } from "../../offline/queue";
import { cacheClear } from "../../api/cache";

export type SavedPlace = { name: string; lat: number; lon: number };

export type ShellSettings = {
  lang: Lang;
  voice: boolean;          // turn-guidance voice (SEAM: TTS engine lands with nav lane)
  share: boolean;          // anonymous traversal donation — on by default (doc 02 §7)
  brief: boolean;          // daily cleanest-window notification
  remind: boolean;         // master switch for "leave later, breathe less" pings (doc 02 §S4)
  show_cig: boolean;       // cigarette-equivalence framing — OFF by default;
                           // dose reads in µg unless the user opts in
  vehicle: string | null;  // S8 choice, e.g. "bike" | "car" | "auto"
  home: SavedPlace | null;
  work: SavedPlace | null;
  /** L4 exposure ceiling profile — a ceiling the user sets, not a medical
   *  line. Drives the day card's budget flag + the tiles' remaining µg. */
  profile: "general" | "sensitive" | "child";
};

export const DEFAULT_SETTINGS: ShellSettings = {
  lang: "en", voice: true, share: true, brief: false, remind: true,
  show_cig: false,
  vehicle: null, home: null, work: null,
  profile: "general",
};

/** Daily inhaled-µg ceilings per profile — the honest basis lives in the
 *  UI label (WHO 24-h 15µg/m³ guide × resting-day volume is the anchor;
 *  sensitive takes the WHO annual guide as a daily ceiling; child scales
 *  the volume down ~60%). A user-set ceiling, never a medical claim. */
export const PROFILE_BUDGET_UG = { general: 216, sensitive: 72, child: 130 } as const;

const FILE = new File(Paths.document, "settings.json");

/* perf (r4): in-memory mirror + deduped first read + serialized writes.
   loadSettings used to hit disk on every call (boot AND notify prefs());
   the read stays eager because `lang` paints frame-1 text — only repeat
   callers get the free path. */
let mem: ShellSettings | null = null;
let inflight: Promise<ShellSettings> | null = null;
let writeTail: Promise<unknown> = Promise.resolve();

export async function loadSettings(): Promise<ShellSettings> {
  if (mem) return { ...mem };
  let p = inflight;
  if (!p) {
    p = (async (): Promise<ShellSettings> => {
      try {
        if (FILE.exists) {
          const j = JSON.parse(await FILE.text());
          const s: ShellSettings = { ...DEFAULT_SETTINGS, ...(j ?? {}) };
          mem = s;
          return s;
        }
      } catch {}
      const s: ShellSettings = mem ?? { ...DEFAULT_SETTINGS };
      mem = s;
      return s;
    })();
    inflight = p;
  }
  return p.then((s) => ({ ...s }));
}

export function saveSettings(s: ShellSettings): void {
  mem = { ...s };
  writeTail = writeTail
    .then(() => {
      if (mem === null) return; // wiped by clearAllData — don't resurrect
      try {
        if (!FILE.exists) FILE.create();
        FILE.write(JSON.stringify(mem)); // last-state-wins per flush
      } catch {}
    })
    .catch(() => {});
}

/** "Delete my data" — ledger, contributor id, settings, consent,
 *  vehicle, route caches. Real removal. The in-memory mirrors drop too
 *  (perf r4) or reads would resurrect wiped data until the next launch. */
export function clearAllData(): void {
  mem = null;
  inflight = null;
  resetLedgerCache();
  clearConsent();   // re-arms the onboarding gate on next launch
  clearWelcomeSeen(); // welcome_seen_v1 — the first-breath moment re-arms too
  clearVehicle();   // vehicle.json — the S8 profile
  clearPlaces();    // places.json — recents + home/work, the location history
  clearOutbox();    // outbox.json — queued donations carry token + trajectory
  void cacheClear(); // alive-cache/ — last-good plan/strip payloads carry route GPS coords
  for (const name of ["settings.json", "ledger.json", "contributor.txt", "intro_seen.txt", "daylog.json"]) {
    try {
      const f = new File(Paths.document, name);
      if (f.exists) f.delete();
    } catch {}
  }
}
