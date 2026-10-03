// My-vehicle profile (docs/plan/02 §S8) — asked once, editable.
// Persists as a JSON document via expo-file-system; same File/Paths
// pattern as src/search/recents.ts and src/store/ledger.ts. If the FS
// fails we still work in memory for the session.
import { File, Paths } from "expo-file-system";
import { t, type Lang, type StringKey } from "../i18n/strings";

const FILE = new File(Paths.document, "vehicle.json");

/** Chips offered by the S8 sheet (docs/plan/02 §S8 + mission brief). */
export type VehicleClass = "car" | "auto" | "bike" | "bus" | "metro" | "walk" | "cycle";
export type Fuel = "petrol" | "diesel" | "cng" | "ev";
export type YearBand = "pre_2010" | "y2010_2016" | "y2017_2020" | "y2021_plus" | "not_sure";

export type VehicleProfile = {
  cls: VehicleClass;
  fuel: Fuel | null;      // asked for car/bike only (doc: car/scooter/bike)
  year: YearBand | null;  // null or "not_sure" → Delhi fleet prior (doc 06 §2)
};

const CLASSES: VehicleClass[] = ["car", "auto", "bike", "bus", "metro", "walk", "cycle"];
const FUELS: Fuel[] = ["petrol", "diesel", "cng", "ev"];
const YEARS: YearBand[] = ["pre_2010", "y2010_2016", "y2017_2020", "y2021_plus", "not_sure"];

// In-memory cache — the fast path, and the whole store when the
// document directory is unavailable.
let mem: VehicleProfile | null | undefined;

function sanitize(raw: unknown): VehicleProfile | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Partial<VehicleProfile>;
  if (!o.cls || !CLASSES.includes(o.cls)) return null;
  return {
    cls: o.cls,
    fuel: o.fuel && FUELS.includes(o.fuel) ? o.fuel : null,
    year: o.year && YEARS.includes(o.year) ? o.year : null,
  };
}

/** Load the saved profile (null = never answered). */
export async function getVehicle(): Promise<VehicleProfile | null> {
  if (mem !== undefined) return mem;
  try {
    if (FILE.exists) {
      mem = sanitize(JSON.parse(await FILE.text()));
      return mem;
    }
  } catch {}
  mem = null;
  return mem;
}

export async function saveVehicle(p: VehicleProfile): Promise<VehicleProfile> {
  mem = p;
  try {
    if (!FILE.exists) FILE.create();
    FILE.write(JSON.stringify(p));
  } catch {
    // in-memory copy still holds — persistence is best-effort
  }
  return p;
}

export async function clearVehicle(): Promise<void> {
  mem = null;
  try {
    if (FILE.exists) FILE.delete();
  } catch {}
}

/** Profile → the `vehicle` string /v2/plan accepts (server/v2/plan.py:
 *  a mode-class string; aliases like "cab"/"scooter" resolve server-side).
 *  All seven chip classes are already canonical plan modes. */
export function planVehicle(p: VehicleProfile | null): string {
  return p?.cls ?? "car";   // server default is also "car"
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

/** Chip / sidebar label: "2010–2016 petrol car"; partial answers shrink
 *  gracefully ("petrol car", "car"); nothing answered → the caller shows
 *  `t("vehicle_likeYours")` ("vehicles like yours") instead. */
export function vehicleLabel(p: VehicleProfile | null, lang: Lang = "en"): string {
  if (!p) return t("vehicle_likeYours", lang);
  const parts = [
    p.year && p.year !== "not_sure" ? t(YEAR_KEY[p.year], lang) : null,
    p.fuel ? t(FUEL_KEY[p.fuel], lang) : null,
    t(CLS_KEY[p.cls], lang),
  ].filter(Boolean);
  return parts.join(" ");
}

export { CLASSES as VEHICLE_CLASSES, YEARS as YEAR_BANDS };
