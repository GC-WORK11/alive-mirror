/** useShellFlow — the trip-flow state machine behind the shell:
 * search → pick → compare → nav → receipt, plus the on-device ledger.
 * Kept out of App.tsx so the composition root stays declarative.
 *
 * /v2 migration: options come from POST /v2/plan (dose + emissions bands,
 * doc-06 §4 tags/reason_line computed server-side). Legacy /depart and
 * /directions remain — /v2/plan carries no turn steps yet. */
import { useCallback, useEffect, useState, type RefObject } from "react";
import { Keyboard } from "react-native";
import * as Location from "expo-location";
import type { CameraRef } from "@maplibre/maplibre-react-native";
import { requestPerms, scheduleDeparture, scheduleDailyBrief } from "../../notify";
import { loadTrips, logTrip, type Trip } from "../../store/ledger";
import type { CommunityTotals } from "../../community";
import {
  getVehicle, saveVehicle, clearVehicle, planVehicle, type VehicleProfile,
} from "../../store/vehicle";
import { planOptions, type FieldStatus } from "../../api/plan";
import { fetchStrip } from "../../api/strip";
import { departCurveResult, type DepartCurve } from "../../api/depart";
import type { RouteStrip } from "../../nav/strip";
import { t } from "../../i18n/strings";
import { API, DELHI, fetchJson, inNcr } from "./net";
import type { Depart, Place, Step, V2Option } from "./types";

export type Phase = "idle" | "search" | "compare" | "nav";
export type Which = "to" | "from";
/** network = we never got an answer (offline/timeout/http); server =
 *  /v2/plan answered with an `error` reason — different blame, the
 *  sheet labels each honestly instead of blaming the connection. */
export type PlanError = { kind: "network" | "server"; detail?: string };

export function useShellFlow(camRef: RefObject<CameraRef | null>, shareEnabled: boolean, lang: "en" | "hi" = "en") {
  const [phase, setPhase] = useState<Phase>("idle");
  const [from, setFrom] = useState<Place | null>(null);
  const [to, setTo] = useState<Place | null>(null);
  const [editWhich, setEditWhich] = useState<Which>("to");
  const [options, setOptions] = useState<V2Option[]>([]);
  const [selected, setSelected] = useState(0);
  const [depart, setDepart] = useState<Depart>(null);
  const [trips, setTrips] = useState<Trip[]>([]);
  const [community, setCommunity] = useState<CommunityTotals | null>(null);
  const [follow, setFollow] = useState(false);
  const [loadingRoute, setLoadingRoute] = useState(false);
  const [planError, setPlanError] = useState<PlanError | null>(null);
  const [planNonce, setPlanNonce] = useState(0);
  const [planField, setPlanField] = useState<FieldStatus | null>(null);
  const [strips, setStrips] = useState<Record<string, RouteStrip>>({});
  const [departCurve, setDepartCurve] = useState<DepartCurve | null>(null);
  const [vehicle, setVehicle] = useState<VehicleProfile | null>(null);
  const [vehicleLoaded, setVehicleLoaded] = useState(false);
  const [notified, setNotified] = useState(false);
  const [steps, setSteps] = useState<Step[] | null>(null);
  const [stepsOpen, setStepsOpen] = useState(false);
  const [navDose] = useState(0); // kept: NavChrome's legacy prop path (engine's `nav` supersedes)

  // SEAM(trip-submit): anonymous traversal donation moved to POST /v2/trip
  // (src/api/trip.ts) — the nav lane owns it and will read `shareEnabled`
  // there. Kept referenced so the prop stays meaningful for App.tsx.
  void shareEnabled;

  /* the S8 vehicle answer — loaded once, drives the /v2/plan `vehicle`
     param (which option is flagged `your_vehicle`). */
  useEffect(() => {
    getVehicle()
      .then((v) => { setVehicle(v); setVehicleLoaded(true); })
      .catch(() => setVehicleLoaded(true));
  }, []);

  /** Persist a new S8 answer; changing it re-plans (vehicle is a dep of
   *  the compare effect below). null = wiped (delete-my-data) — clear
   *  the store instead of resurrecting a file. */
  const setVehicleProfile = useCallback((p: VehicleProfile | null) => {
    if (p == null) {
      clearVehicle().catch(() => {});
      setVehicle(null);
      return;
    }
    saveVehicle(p).catch(() => {});
    setVehicle(p);
  }, []);

  /* search itself lives in src/screens/SearchScreen (S2: T0 on-device +
     cancellable server tiers); this hook owns the phases around it. */
  const pick = useCallback(async (p: Place, which?: Which) => {
    Keyboard.dismiss();
    if ((which ?? editWhich) === "from") {
      setFrom(p);
      setPhase(to ? "compare" : "search");
      setEditWhich("to");
      return;
    }
    setTo(p);
    if (!from) {
      const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced }).catch(() => null);
      setFrom(pos
        ? { name: t("placeCurrentLocation", lang), subtitle: "", lat: pos.coords.latitude, lon: pos.coords.longitude }
        : { name: t("placeCentralDelhi", lang), subtitle: "", lat: DELHI[1], lon: DELHI[0] });
    }
    setPhase("compare");
    camRef.current?.flyTo({ center: [p.lon, p.lat], zoom: 13.5, duration: 800 });
  }, [editWhich, from, to, camRef, lang]);

  /* ---- routes: destination+origin set → /v2/plan + legacy /depart ---- */
  useEffect(() => {
    if (phase !== "compare" || !from || !to || !vehicleLoaded) return;
    let cancelled = false;
    (async () => {
      setNotified(false);
      setSteps(null); setStepsOpen(false);
      setLoadingRoute(true);
      setPlanError(null);
      try {
        const pj = await planOptions({
          from: { lat: from.lat, lon: from.lon },
          to: { lat: to.lat, lon: to.lon },
          vehicle: planVehicle(vehicle),
        }, 15000);
        if (cancelled) return;
        if (pj.error && pj.options.length === 0) {
          setOptions([]); setDepart(null);
          setPlanError({ kind: "server", detail: pj.error });
          return;
        }
        const opts = pj.options;
        setOptions(opts); setSelected(0);
        setPlanField(pj.field);
        setStrips({});
        // per-route PM2.5 strips → the gradient tint resolves from flat
        // dose-mean into real along-route colour as each lands (cached
        // 15 min, failures leave the flat tint — never faked)
        for (const o of opts) {
          if (!o.route_id) continue;
          fetchStrip(o.route_id).then((s) => {
            if (!cancelled) setStrips((m) => (m[o.route_id!] ? m : { ...m, [o.route_id!]: s }));
          }).catch(() => {});
        }
        const g = opts[0]?.geometry;
        if (g?.type === "LineString") {
          const c = (g as GeoJSON.LineString).coordinates;
          camRef.current?.fitBounds(
            [Math.min(...c.map((x) => x[0])), Math.min(...c.map((x) => x[1])),
             Math.max(...c.map((x) => x[0])), Math.max(...c.map((x) => x[1]))],
            { padding: { top: 200, bottom: 340, left: 50, right: 50 }, duration: 700 });
        }
      } catch {
        if (!cancelled) {
          setOptions([]); setDepart(null);
          setPlanError({ kind: "network" });   // honest retry state — no silent /decide fallback
        }
      } finally { if (!cancelled) setLoadingRoute(false); }
    })();
    return () => { cancelled = true; };
  }, [phase, from, to, vehicle, vehicleLoaded, planNonce, camRef]);

  /** Error retry — re-runs the compare effect. */
  const retryPlan = useCallback(() => setPlanNonce((n) => n + 1), []);

  /* ---- leave-time window follows the SELECTED mode (was hardcoded
     vehicle=auto — claims audit: the window must model the chosen ride).
     Full 24h curve via departCurveResult (fetchCached → last-good +
     stale label free); `depart` stays the legacy best-slot shape. ---- */
  useEffect(() => {
    const mode = options[selected]?.mode;
    if (phase !== "compare" || !from || !to || !mode) return;
    let cancelled = false;
    departCurveResult(
      { from: { lat: from.lat, lon: from.lon }, to: { lat: to.lat, lon: to.lon }, vehicle: mode })
      .then((r) => {
        if (cancelled) return;
        const c = r.ok ? r.data : null;
        setDepartCurve(c?.slots?.length ? c : null);
        setDepart(c?.best
          ? { best: { hours_ahead: c.best.hour, start: c.best.start, dose_ug: c.best.dose_mid },
              ug_saved_vs_now: c.ug_saved_vs_now }
          : null);
      })
      .catch(() => { if (!cancelled) { setDepartCurve(null); setDepart(null); } });
    return () => { cancelled = true; };
  }, [phase, from, to, options, selected]);

  /* ---- turn-by-turn steps for the selected (road) option ----
     /v2/plan options carry no steps yet → legacy /directions stays. */
  useEffect(() => {
    const o = options[selected];
    let cancelled = false;
    // deferred one tick — setState directly inside an effect cascades renders
    Promise.resolve().then(() => { if (!cancelled) setSteps(null); });
    if (!o || !from || !to || o.mode === "metro") return () => { cancelled = true; };
    if (Array.isArray(o.steps) && o.steps.length) {   // inlined steps win when they exist
      const inline = o.steps;
      Promise.resolve().then(() => { if (!cancelled) setSteps(inline); });
      return () => { cancelled = true; };
    }
    const profile = o.mode === "cycle" ? "cycling" : o.mode === "walk" ? "walking" : "driving";
    fetchJson(
      `${API}/directions?from_lat=${from.lat}&from_lon=${from.lon}` +
        `&to_lat=${to.lat}&to_lon=${to.lon}&profile=${profile}&vehicle=${o.mode}`, 10000)
      .then((j) => { if (!cancelled && Array.isArray(j.steps)) setSteps(j.steps); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [selected, options, from, to]);

  const clearRoute = useCallback(() => {
    setTo(null); setOptions([]); setDepart(null); setDepartCurve(null);
    setSteps(null); setStepsOpen(false); setStrips({});
    setPlanError(null); setPlanField(null);
    setPhase("idle"); setFollow(false);
  }, []);

  /* ---- navigation phase transitions; the live engine (src/nav) owns
     the watcher, strip, counters, off-route + arrival — nothing here
     ticks or polls during nav anymore. ---- */
  const startNav = useCallback(async () => {
    const o = options[selected];
    if (!o || !from || !to) return;
    setPhase("nav");
    Keyboard.dismiss();
    const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced }).catch(() => null);
    setFollow(!!(pos && inNcr(pos.coords.latitude, pos.coords.longitude)));
    camRef.current?.flyTo({ center: [from.lon, from.lat], zoom: 15.5, duration: 700 });
    camRef.current?.setStop({ pitch: 55, duration: 800 });
  }, [options, selected, from, to, camRef]);

  const exitNav = useCallback(() => {
    setPhase("compare"); setFollow(false);
    camRef.current?.setStop({ pitch: 0, duration: 700 });
  }, [camRef]);

  /* ---- ledger: only a COMPLETED trip is logged (claims audit — logging
     on option view fabricated trips + inflated every avoided-µg total).
     The nav session calls this with its real arrival summary. ---- */
  const recordTrip = useCallback(async (t: {
    label: string; vehicle: string; doseUg: number | null; avoidedUg: number | null;
  }) => {
    if (!from || !to) return;
    try {
      setTrips(await logTrip({
        ts: Date.now(), label: t.label, vehicle: t.vehicle,
        dose_ug: Math.round((t.doseUg ?? 0) * 10) / 10,
        avoided_ug: Math.max(0, Math.round((t.avoidedUg ?? 0) * 10) / 10),
        from: from.name, to: to.name,
        fromLat: from.lat, fromLon: from.lon, toLat: to.lat, toLon: to.lon,
      }));
    } catch { /* ledger write is best-effort */ }
  }, [from, to]);

  /* route polylines tinted per ~250 m by field PM2.5 — the derivation
     moved inside <RouteTintSource/> (App.tsx); we just hand the strips
     through so each option's flat dose-mean tint resolves into the real
     along-route gradient as its strip lands. */

  const armDailyBrief = useCallback(async (): Promise<boolean> => {
    if (!(await requestPerms())) return false;
    const p = to ?? from ?? { lat: DELHI[1], lon: DELHI[0] };
    const j = await fetchJson(`${API}/today?lat=${p.lat}&lon=${p.lon}`).catch(() => null);
    const h: number[] | undefined = j?.hours_ist;
    if (!Array.isArray(h) || h.length < 24) return false;
    let best = 0;
    for (let i = 0; i <= 21; i++) if (h[i] + h[i + 1] + h[i + 2] < h[best] + h[best + 1] + h[best + 2]) best = i;
    const drop = Math.max(0, Math.round((1 - ((h[best] + h[best + 1] + h[best + 2]) / 3) / (h.reduce((a, b) => a + b, 0) / 24)) * 100));
    return (await scheduleDailyBrief({ startHour: best, endHour: (best + 3) % 24, dropPct: drop })) != null;
  }, [from, to]);

  const remind = useCallback(async () => {
    if (!depart?.best?.start || notified || !(await requestPerms())) return;
    const fire = new Date(depart.best.start.endsWith("Z") ? depart.best.start : depart.best.start + "Z");
    /* /depart returns ug_saved_vs_now in µg — the notification copy wants
       a real percent: saved / dose-if-left-now (claims audit: no unit wash). */
    const saved = depart.ug_saved_vs_now ?? 0;
    const doseNow = (depart.best.dose_ug ?? 0) + saved;
    const pct = doseNow > 0 ? Math.max(0, Math.round((saved / doseNow) * 100)) : 0;
    if (await scheduleDeparture({ fireAt: fire, savedPct: pct })) setNotified(true);
  }, [depart, notified]);

  const reloadTrips = useCallback(() => { loadTrips().then(setTrips).catch(() => {}); }, []);

  /* doc 02 §S5: the vehicle question belongs on first private-mode pick —
     the integrator opens <VehicleSheet/> when this flips true. */
  const sel = options[selected];
  const needsVehicle =
    vehicleLoaded && vehicle == null &&
    (sel?.mode === "car" || sel?.mode === "car_open" || sel?.mode === "bike");

  return {
    phase, setPhase, from, setFrom, to, setTo,
    editWhich, setEditWhich, options, selected, setSelected,
    depart, notified, trips, setTrips, recordTrip, community, setCommunity, follow, setFollow,
    loadingRoute, planError, retryPlan, planField, departCurve,
    vehicle, setVehicleProfile, needsVehicle,
    steps, stepsOpen, setStepsOpen, navDose,
    pick, clearRoute, startNav, exitNav, remind, armDailyBrief,
    strips, reloadTrips,
  };
}
