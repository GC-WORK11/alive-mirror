// My-vehicle profile (docs/plan/02 §S8) — asked once, editable.
// Persists as a JSON document via expo-file-system; same File/Paths
// pattern as src/search/recents.ts and src/store/ledger.ts. If the FS
// fails we still work in memory for the session.
import { purgeJsonDoc, readJsonDoc, writeJsonDoc } from "./safefile";
import { t, type Lang, type StringKey } from "../i18n/strings";
import { afterFirstFrame } from "../startup/idle";

const NAME = "vehicle.json";

/** Chips offered by the S8 sheet (docs/plan/02 §S8 + mission brief). */
export type VehicleClass = "car" | "auto" | "bike" | "bus" | "metro" | "walk" | "cycle";
export type Fuel = "petrol" | "diesel" | "cng" | "ev";
export type YearBand = "pre_2010" | "y2010_2016" | "y2017_2020" | "y2021_plus" | "not_sure";

/* PUC — the Pollution Under Control certificate every Indian vehicle
 * carries. All fields optional: `bs` is the Bharat stage on the
 * certificate; the readings are its measured values (CO% / HC ppm for
 * petrol & CNG, smoke-opacity % for diesel). The object is optional on the
 * profile and travels verbatim in the /v2/plan vehicle_profile so the
 * backend can calibrate the estimate to the user's real vehicle — the
 * server ignores it gracefully until the calibration lands. */
export type PucInfo = {
  bs: "bs3" | "bs4" | "bs6" | null;
  co_pct: number | null;
  hc_ppm: number | null;
  smoke_pct: number | null;
};

export type VehicleProfile = {
  cls: VehicleClass;
  fuel: Fuel | null;      // asked for car/bike only (doc: car/scooter/bike)
  year: YearBand | null;  // null or "not_sure" → Delhi fleet prior (doc 06 §2)
  puc?: PucInfo | null;   // optional pollution certificate, owned vehicles
};

const CLASSES: VehicleClass[] = ["car", "auto", "bike", "bus", "metro", "walk", "cycle"];
const FUELS: Fuel[] = ["petrol", "diesel", "cng", "ev"];
const YEARS: YearBand[] = ["pre_2010", "y2010_2016", "y2017_2020", "y2021_plus", "not_sure"];

// In-memory cache — the fast path, and the whole store when the
// document directory is unavailable. `inflight` dedupes concurrent first
// reads (perf r4): the profile isn't frame-1 data, so the disk read +
// JSON.parse waits for afterFirstFrame instead of blocking the mount.
let mem: VehicleProfile | null | undefined;
let inflight: Promise<VehicleProfile | null> | null = null;
let writeTail: Promise<unknown> = Promise.resolve();

const BS_STAGES: PucInfo["bs"][] = ["bs3", "bs4", "bs6"];

const numOrNull = (v: unknown): number | null =>
  typeof v === "number" && Number.isFinite(v) ? v : null;

/** Whitelist a stored PUC blob; an all-empty certificate counts as none. */
function sanitizePuc(raw: unknown): PucInfo | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Partial<PucInfo>;
  const puc: PucInfo = {
    bs: o.bs && BS_STAGES.includes(o.bs) ? o.bs : null,
    co_pct: numOrNull(o.co_pct),
    hc_ppm: numOrNull(o.hc_ppm),
    smoke_pct: numOrNull(o.smoke_pct),
  };
  return puc.bs != null || puc.co_pct != null || puc.hc_ppm != null ||
    puc.smoke_pct != null ? puc : null;
}

function sanitize(raw: unknown): VehicleProfile | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Partial<VehicleProfile>;
  if (!o.cls || !CLASSES.includes(o.cls)) return null;
  return {
    cls: o.cls,
    fuel: o.fuel && FUELS.includes(o.fuel) ? o.fuel : null,
    year: o.year && YEARS.includes(o.year) ? o.year : null,
    puc: sanitizePuc(o.puc),
  };
}

/** Load the saved profile (null = never answered). */
export async function getVehicle(): Promise<VehicleProfile | null> {
  if (mem !== undefined) return mem;
  if (!inflight) {
    inflight = (async () => {
      await afterFirstFrame();
      if (mem !== undefined) return mem; // a writer won while we waited
      /* atomic+.bak read via safefile: sanitize() is the shape check;
         a torn main falls through to the previous good generation */
      mem = await readJsonDoc(NAME, (v): v is VehicleProfile => sanitize(v) !== null)
        .then((v) => (v ? sanitize(v) : null));
      return mem ?? null;
    })();
  }
  return inflight;
}

export async function saveVehicle(p: VehicleProfile): Promise<VehicleProfile> {
  mem = p;
  writeTail = writeTail
    .then(() => {
      if (mem == null) return; // cleared meanwhile — don't resurrect the file
      /* atomic + .bak via safefile — the profile drives plan
         calibration; a torn file must not silently reset it */
      writeJsonDoc(NAME, mem);
    })
    .catch(() => {});
  await writeTail;
  return p;
}

export async function clearVehicle(): Promise<void> {
  mem = null;
  purgeJsonDoc(NAME); // file + .tmp + .bak
}

/** Profile → the `vehicle` string /v2/plan accepts (server/v2/plan.py:
 *  a mode-class string; aliases like "cab"/"scooter" resolve server-side).
 *  All seven chip classes are already canonical plan modes. */
export function planVehicle(p: VehicleProfile | null): string {
  return p?.cls ?? "car";   // server default is also "car"
}

/** Profile → the `vehicle_profile` dict /v2/plan parses (server/v2/plan.py
 *  `_parse_vehicle`): {class, fuel?, year_bucket?}. Server buckets are
 *  before_2010 | 2010_2016 | 2017_2019 | 2020_plus | not_sure — our
 *  2017–2020 chip straddles two of them; it maps to 2017_2019 (three of
 *  its four years land there) rather than widening the answer. */
const SERVER_YEAR: Record<Exclude<YearBand, "not_sure">, string> = {
  pre_2010: "before_2010",
  y2010_2016: "2010_2016",
  y2017_2020: "2017_2019",
  y2021_plus: "2020_plus",
};
export function planVehicleProfile(
  p: VehicleProfile | null,
): { class: string; fuel?: string; year_bucket?: string; puc?: PucInfo } | null {
  if (!p) return null;
  const out: { class: string; fuel?: string; year_bucket?: string; puc?: PucInfo } = { class: p.cls };
  if (p.fuel) out.fuel = p.fuel;              // "ev" → server alias 'electric'
  if (p.year && p.year !== "not_sure") out.year_bucket = SERVER_YEAR[p.year];
  if (p.puc) out.puc = p.puc;                 // additive — ignored until the
                                            // backend's calibration lands
  return out;
}

/** Does this class get the fuel question? Doc 02 §S8: car/scooter/bike
 *  only — autos are overwhelmingly CNG, shared + non-motor modes skip. */
export const needsFuel = (cls: VehicleClass) => cls === "car" || cls === "bike";

/** Fuels that exist for the class on Delhi roads (server/emissions.py
 *  _VALID_FUELS: bikes are petrol/electric only — no diesel chip). */
export const fuelsFor = (cls: VehicleClass): Fuel[] =>
  cls === "bike" ? ["petrol", "ev"] : ["petrol", "diesel", "cng", "ev"];

/** Year band is asked for owned road vehicles (car/bike/auto). */
export const needsYear = (cls: VehicleClass) =>
  cls === "car" || cls === "bike" || cls === "auto";

const CLS_KEY: Record<VehicleClass, StringKey> = {
  car: "vehicle_car", auto: "vehicle_auto", bike: "vehicle_bike",
  bus: "vehicle_bus", metro: "vehicle_metro", walk: "vehicle_walk",
  cycle: "vehicle_cycle",
};
const FUEL_KEY: Record<Fuel, StringKey> = {
  petrol: "fuelPetrol", diesel: "fuelDiesel", cng: "fuelCNG", ev: "fuelElectric",
};
const YEAR_KEY: Record<YearBand, StringKey> = {
  pre_2010: "yearBefore2010", y2010_2016: "year2010to2016",
  y2017_2020: "vehicle_year2017to2020", y2021_plus: "vehicle_year2021plus",
  not_sure: "yearNotSure",
};

/** Single-word names for composing server-side sentences client-side
 *  (CompareSheet's emissions-label rebuild) — same maps vehicleLabel uses. */
export function fuelName(f: string, lang: Lang = "en"): string {
  return FUEL_KEY[f as Fuel] ? t(FUEL_KEY[f as Fuel], lang) : f;
}
export function className(c: string, lang: Lang = "en"): string {
  return CLS_KEY[c as VehicleClass] ? t(CLS_KEY[c as VehicleClass], lang) : c;
}

/** Chip / sidebar label: "2010–2016 petrol car"; partial answers shrink
 *  gracefully ("petrol car", "car"); nothing answered → the caller shows
 *  `t("vehicle_likeYours")` ("a typical Delhi ride") instead. */
export function vehicleLabel(p: VehicleProfile | null, lang: Lang = "en"): string {
  if (!p) return t("vehicle_likeYours", lang);
  const parts = [
    p.year && p.year !== "not_sure" ? t(YEAR_KEY[p.year], lang) : null,
    p.fuel ? t(FUEL_KEY[p.fuel], lang) : null,
    t(CLS_KEY[p.cls], lang),
  ].filter(Boolean);
  return parts.join(" ");
}