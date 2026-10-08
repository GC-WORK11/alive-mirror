/** Shell settings — one JSON file in the app's document dir.
 * lang · voice guidance · anonymous data sharing · departure reminders ·
 * morning brief · saved vehicle · saved places. Delete-my-data wipes it
 * along with the ledger and contributor id. */
import { File, Paths } from "expo-file-system";
import type { Lang } from "../../i18n/strings";
import { resetLedgerCache } from "../../store/ledger";
import { resetDaylogCache } from "../../store/daylog";
import { resetDaySum } from "../../store/daysum";
import { purgeJsonDoc, purgeUrlCaches, readJsonDoc, writeJsonDoc } from "../../store/safefile";
import { mark } from "../../perf";
import { clearConsent } from "../../store/consent";
import { clearWelcomeSeen } from "../../store/welcome";
import { clearTourSeen } from "../../store/tour";
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
  remind: boolean;         // master switch for clean-window pings (doc 02 §S4)
  /* air alerts — real-event pings out of store/events.ts: fires building,
     the band crossing upward, still air, severe days, clean windows.
     Master + three kinds; every ping traces to a served field. */
  alerts: boolean;
  alerts_fires: boolean;   // NW burn-belt builds (fires spike)
  alerts_band: boolean;    // air turning worse — band crossings, severe days,
                           // stagnation, the recorded city-mean trend, GRAP steps
  alerts_windows: boolean; // the day's clean window opening + tomorrow's fold
  alerts_reflect: boolean; // yesterday's trips — the once-a-day look-back
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
  alerts: true, alerts_fires: true, alerts_band: true, alerts_windows: true,
  alerts_reflect: true,
  show_cig: false,
  vehicle: null, home: null, work: null,
  profile: "general",
};

/** WHO 2021 24-h PM2.5 guideline (µg/m³) — the denominator behind every
 *  "× WHO daily limit" read-out. Was duplicated per screen; one truth. */
export const WHO_DAILY_UG = 15;

/** Daily inhaled-µg ceilings per profile — the honest basis lives in the
 *  UI label (WHO 24-h 15µg/m³ guide × resting-day volume is the anchor;
 *  sensitive takes the WHO annual guide as a daily ceiling; child scales
 *  the volume down ~60%). A user-set ceiling, never a medical claim. */
export const PROFILE_BUDGET_UG = { general: 216, sensitive: 72, child: 130 } as const;

const NAME = "settings.json";

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
      /* atomic+.bak read: the object shape check keeps a garbage-typed
         main from shadowing a good .bak; spread-merge over defaults is
         the existing migration path (new keys default honestly) */
      const j = await readJsonDoc(NAME, (v): v is Partial<ShellSettings> =>
        !!v && typeof v === "object" && !Array.isArray(v));
      if (j) {
        const s: ShellSettings = { ...DEFAULT_SETTINGS, ...j };
        mem = s;
        return s;
      }
      const s: ShellSettings = mem ?? { ...DEFAULT_SETTINGS };
      mem = s;
      return s;
    })();
    inflight = p;
  }
  return p.then((s) => ({ ...s }));
}

export function saveSettings(s: ShellSettings): void {
  mark("settings.save");
  mem = { ...s };
  writeTail = writeTail
    .then(() => {
      if (mem === null) return; // wiped by clearAllData — don't resurrect
      /* atomic + .bak — lang/alert prefs are read on frame-1; a torn
         file must not silently reset them */
      writeJsonDoc(NAME, mem); // last-state-wins per flush
      mark("settings.write");
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
  resetDaylogCache(); // daylog.json mirror — without it a wipe resurrects
                      // every sample/check-in on the next recordSample
  resetDaySum();      // daysum.json — the rollup engine's file + .tmp/.bak
  clearConsent();   // re-arms the onboarding gate on next launch
  clearWelcomeSeen(); // welcome_seen_v1 — the first-breath moment re-arms too
  clearTourSeen();  // coach_tour_seen_v1 — a wiped phone is a first run again
  clearVehicle();   // vehicle.json — the S8 profile
  clearPlaces();    // places.json — recents + home/work, the location history
  clearOutbox();    // outbox.json — queued donations carry token + trajectory
  void cacheClear(); // alive-cache/ — last-good plan/strip payloads carry route GPS coords
  /* safefile stores purge their .tmp/.bak too — a torn write's artifacts
     are still user data */
  purgeJsonDoc("ledger.json");
  purgeJsonDoc("daylog.json");
  purgeJsonDoc(NAME); // settings.json
  /* fetch() bodies also sit on disk: NSURLCache's fsCachedData + Cache.db
     and the HTTPStorages jar carry geocode/route payloads (and the anon
     contributor id in request URLs). "Deleting actually deletes" has to
     reach them too — verified against the real sim container (wipe-verify). */
  purgeUrlCaches();
  for (const name of ["contributor.txt", "intro_seen.txt", "events.json"]) {
    try {
      const f = new File(Paths.document, name);
      if (f.exists) f.delete();
    } catch {}
  }
}
