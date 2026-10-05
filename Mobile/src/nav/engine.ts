/**
 * useNavEngine — Phase-4 live navigation (doc 04 §4–5).
 *
 * Self-contained: owns its expo-location watcher (1 s / 5 m,
 * BestForNavigation), a 1 Hz ticker for the two live counters, strip
 * walking, off-route → /v2/reroute, arrival → receipt, and the optional
 * /v2/trip donation. All counter math is local (doc 04 §5 hard rule).
 */

import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import { AppState } from "react-native";
import * as Location from "expo-location";
import type { CameraRef } from "@maplibre/maplibre-react-native";
import { API } from "../components/shell/net";
import { contributorId } from "../community";
import { fetchStrip } from "../api/strip";
import { camDur } from "../map/cam";
import type { EmissionsBreakdown } from "../components/shell/types";
import { postJson, postReroute } from "../api/reroute";
import { enqueueTripDonation } from "../offline/queue";
import { LiveCounters } from "./counters";
import {
  ARRIVE_M, ArrivalTracker, flattenCoords, havM, OffRouteTracker,
  polylineLengthM, snapToPolyline, type LonLat,
} from "./offroute";
import { fieldAtAlongM, stripCumM, type Band, type RouteStrip } from "./strip";
import { CueTracker, speakCue, stopCues, type NavStep } from "./speech";
import { localizeStep } from "./instructions";
import { arrived as arriveHaptic } from "../haptics";
import type { Lang } from "../i18n/strings";

const WATCH_OPTS: Location.LocationOptions = {
  accuracy: Location.Accuracy.BestForNavigation,
  timeInterval: 1000,
  distanceInterval: 5,
  mayShowUserSettingsDialog: true,
};
const REROUTE_COOLDOWN_MS = 15000;
const MAX_TRAJ = 4900; // under server's 5000-point guard (trip.py)

export type NavRoute = {
  route_id: string;
  geometry?: GeoJSON.Geometry | null;
  /** v2/plan options carry it under this name */
  route_geojson?: GeoJSON.Geometry | null;
  eta_s?: number | null;
  duration_s?: number | null;
  distance_km?: number | null;
  mode?: string | null;
  label?: string | null;
  /** destination; default = last polyline point */
  to?: { lat: number; lon: number } | null;
  /** turn steps {instruction, distance_m} — speech cues if enabled */
  steps?: NavStep[] | null;
  /** context for the receipt comparison lines */
  alternatives?: { label: string; doseUgMid?: number | null; co2KgMid?: number | null }[];
  worstDoseUg?: number | null;
  /** heaviest OTHER option's plan-time CO2 mid — the avoided-CO2
      counterfactual for the donation summary, same shape as
      worstDoseUg; null when no alternative carries emissions */
  worstCo2Kg?: number | null;
  /** true only when this trip's emissions estimate ran on a
      PUC-calibrated vehicle profile; null/absent on modes where the
      question doesn't apply (metro/walk/cycle) */
  pucCalibrated?: boolean | null;
  /** the chosen option's CO2 moving/idle/cold split — donated with the
      trip summary so the collective can break out where ride CO2
      comes from; null on modes that never carry a breakdown */
  emissionsBreakdown?: EmissionsBreakdown;
};

export type NavSummary = {
  mode: string;
  routeId: string;
  distanceKm: number;
  durationS: number;
  doseUg: Band;
  co2Kg: Band;
  pm25G: Band;
  donated: boolean;
  /** false when the rider ended the trip manually ("End") before the
      proximity detector fired — the receipt must not claim arrival */
  endedEarly: boolean;
};

export type NavEngineOpts = {
  route: NavRoute;
  camRef?: RefObject<CameraRef | null> | null;
  lang?: Lang;
  onArrive?: (summary: NavSummary) => void;
  /** POST /v2/trip on arrival only when true */
  shareEnabled?: boolean;
  /** voice cues — off unless enabled (settings flag) */
  speech?: boolean;
  apiBase?: string;
  autoStart?: boolean;
};

export type NextStep = { instruction: string; distM: number };

/* Client-side privacy trim for /v2/trip donations — mirrors
 * server/v2/trip.py's privacy_pipeline so endpoints never leave the
 * device (the server still re-applies it, so older builds stay safe):
 * drop the first and last TRIM metres of travelled path, thin the
 * middle to one point per THIN metres keeping both trimmed endpoints,
 * round to ROUND_DP decimals (~11 m). A trip shorter than 2×TRIM
 * donates an empty trajectory — its summary counts, its path doesn't. */
const TRAJ_TRIM_M = 300;
const TRAJ_THIN_M = 100;
const TRAJ_ROUND_DP = 4;

export function privacyTrimTrajectory(
  pts: { lat: number; lon: number }[],
): { lat: number; lon: number }[] {
  if (pts.length < 2) return [];
  const cum = [0];
  for (let i = 1; i < pts.length; i++) {
    cum.push(cum[i - 1] + havM(pts[i - 1].lat, pts[i - 1].lon, pts[i].lat, pts[i].lon));
  }
  const total = cum[cum.length - 1];
  const mid = pts.filter((_, i) => cum[i] >= TRAJ_TRIM_M && cum[i] <= total - TRAJ_TRIM_M);
  if (mid.length === 0) return [];
  const kept: { lat: number; lon: number }[] = [mid[0]];
  for (let i = 1; i < mid.length - 1; i++) {
    const last = kept[kept.length - 1];
    if (havM(last.lat, last.lon, mid[i].lat, mid[i].lon) >= TRAJ_THIN_M) kept.push(mid[i]);
  }
  if (mid.length > 1) kept.push(mid[mid.length - 1]);
  const r = (v: number) => Number(v.toFixed(TRAJ_ROUND_DP));
  return kept.map((p) => ({ lat: r(p.lat), lon: r(p.lon) }));
}

/** emissions.breakdown → the /v2/trip summary's optional CO2 split
 *  (grams, 0.1 g rounding). Each mid is kept independently — a partial
 *  breakdown still reports what it honestly has. */
function co2Split(bd: EmissionsBreakdown | undefined): {
  co2_moving_g?: number; co2_idle_g?: number; co2_cold_g?: number;
} {
  const out: { co2_moving_g?: number; co2_idle_g?: number; co2_cold_g?: number } = {};
  const put = (k: keyof typeof out, v: number | null | undefined) => {
    if (typeof v === "number" && Number.isFinite(v)) out[k] = Math.round(v * 10) / 10;
  };
  put("co2_moving_g", bd?.moving_mid?.co2);
  put("co2_idle_g", bd?.idle_mid?.co2);
  put("co2_cold_g", bd?.cold_extra_mid?.co2);
  return out;
}

export function useNavEngine(opts: NavEngineOpts) {
  const { route, camRef, onArrive, lang = "en", shareEnabled = false, speech = false } = opts;
  const api = opts.apiBase ?? API;

  const [running, setRunning] = useState(false);
  const [arrived, setArrived] = useState(false);
  const [offRoute, setOffRoute] = useState(false);
  /* true once /v2/reroute answers code:'outside_service_area' — the
     rider left the dose field; NavChrome shows it honestly */ const [outsideField, setOutsideField] = useState(false);
  const [snapped, setSnapped] = useState<LonLat | null>(null);
  const [dose, setDose] = useState<Band>({ lo: 0, mid: 0, hi: 0 });
  const [co2, setCo2] = useState<Band>({ lo: 0, mid: 0, hi: 0 });
  const [pm25, setPm25] = useState<Band>({ lo: 0, mid: 0, hi: 0 });
  const [distRemainingM, setDistRemainingM] = useState(0);
  const [etaS, setEtaS] = useState(route.eta_s ?? route.duration_s ?? 0);
  const [progress, setProgress] = useState(0);
  const [nextStep, setNextStep] = useState<NextStep | null>(null);
  const [stripOk, setStripOk] = useState(true);
  const [fieldAgeMin, setFieldAgeMin] = useState<number | null>(null);
  const [summary, setSummary] = useState<NavSummary | null>(null);

  // --- mutable session state (refs: survive renders, drive the loops)
  const subRef = useRef<Location.LocationSubscription | null>(null);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const appSubRef = useRef<ReturnType<typeof AppState.addEventListener> | null>(null);
  const countersRef = useRef(new LiveCounters());
  const offRef = useRef(new OffRouteTracker());
  const arrRef = useRef(new ArrivalTracker());
  const cuesRef = useRef(new CueTracker());
  const coordsRef = useRef<LonLat[]>([]);
  const routeLenRef = useRef(0);
  const destRef = useRef<LonLat | null>(null);
  const stripRef = useRef<RouteStrip | null>(null);
  const cumRef = useRef<number[]>([]);
  const alongRef = useRef(0);
  const pendMRef = useRef(0);        // distance moved since last tick
  const speedRef = useRef(0);        // latest speed estimate, m/s
  const nextStepRef = useRef<NextStep | null>(null);
  const tickDtRef = useRef(0);
  const lastFixRef = useRef<{ lat: number; lon: number; ts: number } | null>(null);
  const lastCamTsRef = useRef(0);    // camera-commit throttle clock
  const lastCamCenterRef = useRef<LonLat | null>(null);
  const trajRef = useRef<{ lat: number; lon: number; ts: number }[]>([]);
  const rerouteAtRef = useRef(0);    // cooldown clock
  const reroutingRef = useRef(false);
  const arrivedRef = useRef(false);
  const runningRef = useRef(false);
  const startTsRef = useRef(0);
  const routeRef = useRef(route);
  const eta0Ref = useRef(route.eta_s ?? route.duration_s ?? 0);
  const speechRef = useRef(speech);
  useEffect(() => {
    routeRef.current = route;
    speechRef.current = speech;
  }, [route, speech]);

  const loadRoute = useCallback((r: NavRoute, coords: LonLat[]) => {
    coordsRef.current = coords;
    routeLenRef.current = polylineLengthM(coords);
    const last = coords[coords.length - 1];
    destRef.current = r.to ? [r.to.lon, r.to.lat] : last ?? null;
    eta0Ref.current = r.eta_s ?? r.duration_s ?? eta0Ref.current;
    cuesRef.current.load(r.steps);
  }, []);

  const refreshStrip = useCallback(async (routeId: string) => {
    try {
      const s = await fetchStrip(routeId, api);
      stripRef.current = s;
      cumRef.current = stripCumM(s.samples);
      const age = s.field?.age_min;
      setFieldAgeMin(typeof age === "number" ? age : null);
      setStripOk(true);
    } catch {
      stripRef.current = null;
      cumRef.current = [];
      setStripOk(false); // honest: counters stop accruing dose
    }
  }, [api]);

  const cleanup = useCallback(() => {
    subRef.current?.remove();
    subRef.current = null;
    appSubRef.current?.remove();
    appSubRef.current = null;
    if (tickRef.current) clearInterval(tickRef.current);
    tickRef.current = null;
    stopCues();
    runningRef.current = false;
  }, []);

  const donate = useCallback(async (s: NavSummary) => {
    const donation = {
      device_token: await contributorId(), // stable anonymous id (src/store)
      trajectory: privacyTrimTrajectory(trajRef.current),
      summary: {
        mode: s.mode,
        distance_km: Math.round(s.distanceKm * 100) / 100,
        duration_s: Math.round(s.durationS),
        dose_ug: Math.round(s.doseUg.mid * 10) / 10,
        co2_kg_mid: Math.round(s.co2Kg.mid * 1000) / 1000,
        pm25_g_mid: Math.round(s.pm25G.mid * 1000) / 1000,
        /* savings the admin /global tiles aggregate — the same
           counterfactuals the receipt and ledger already show:
           avoided_ug = worst OTHER option's plan-time dose mid minus
           this trip's measured mid (clamped, exactly the ledger's
           number); co2_avoided_kg the same shape against the heaviest
           alternative's CO2. Both keys absent when there's no real
           alternative to compare against — never zeros standing in
           for missing data. puc_calibrated is sent only on
           private-motor trips (it's a property of the emissions
           estimate — meaningless on metro/walk/cycle). */
        ...(routeRef.current.worstDoseUg != null
          ? {
              avoided_ug: Math.max(0, Math.round((routeRef.current.worstDoseUg - s.doseUg.mid) * 10) / 10),
              /* "switched to a lighter option" — this trip's measured
                 dose landed under the heaviest option the plan offered.
                 Sent only when a real alternative existed; the
                 donations/admin "switched" counters stay honest-0 when
                 there was nothing to switch from. */
              switched: routeRef.current.worstDoseUg - s.doseUg.mid > 0,
            }
          : {}),
        ...(routeRef.current.worstCo2Kg != null
          ? { co2_avoided_kg: Math.max(0, Math.round((routeRef.current.worstCo2Kg - s.co2Kg.mid) * 1000) / 1000) }
          : {}),
        ...(routeRef.current.pucCalibrated != null
          ? { puc_calibrated: routeRef.current.pucCalibrated }
          : {}),
        /* CO2 split the backend asked for — optional, bounds-checked
           server-side; absent keys are the honest answer on modes
           without a breakdown (metro/walk/cycle), not zeros */
        ...co2Split(routeRef.current.emissionsBreakdown),
      },
    };
    try {
      await postJson(`${api}/v2/trip`, donation, 9000);
      return true;
    } catch {
      /* offline → outbox, not loss: flushes itself when the network
         comes back (pill counts it until then) */
      try { await enqueueTripDonation(api, donation); return true; }
      catch { return false; }
    }
  }, [api]);

  const arrive = useCallback((completed = true) => {
    if (arrivedRef.current) return;
    arrivedRef.current = true;
    cleanup();
    setArrived(true);
    setRunning(false);
    // the trip earned its moment — success buzz on a real arrival, a
    // silent end when the rider exits early
    if (completed) arriveHaptic();
    const c = countersRef.current;
    const s: NavSummary = {
      mode: routeRef.current.mode ?? "",
      routeId: routeRef.current.route_id,
      distanceKm: countersRef.current.travelledM / 1000,
      durationS: (Date.now() - startTsRef.current) / 1000,
      doseUg: { ...c.doseUg },
      co2Kg: { lo: c.co2G.lo / 1000, mid: c.co2G.mid / 1000, hi: c.co2G.hi / 1000 },
      pm25G: { ...c.pm25G },
      donated: false,
      endedEarly: !completed,
    };
    (async () => {
      if (shareEnabled && trajRef.current.length > 1) {
        s.donated = await donate(s);
      }
      setSummary(s);
      onArrive?.(s);
    })();
  }, [cleanup, donate, shareEnabled, onArrive]);

  const reroute = useCallback(async (fix: { lat: number; lon: number }) => {
    const now = Date.now();
    if (reroutingRef.current || now - rerouteAtRef.current < REROUTE_COOLDOWN_MS) return;
    rerouteAtRef.current = now;
    reroutingRef.current = true;
    setOffRoute(true);
    const r = routeRef.current;
    const dest = destRef.current;
    const res = dest
      ? await postReroute(
          { route_id: r.route_id, at: fix, to: { lat: dest[1], lon: dest[0] }, mode: r.mode ?? "" },
          api)
      : null;
    if (res?.code === "outside_service_area") setOutsideField(true);
    if (res?.result?.geometry) {
      const rr = res.result;
      const next: NavRoute = { ...r, route_id: rr.route_id, geometry: rr.geometry,
        eta_s: rr.eta_s ?? r.eta_s, mode: rr.mode ?? r.mode };
      routeRef.current = next;
      loadRoute(next, flattenCoords(rr.geometry));
      alongRef.current = 0;
      offRef.current.reset();
      await refreshStrip(rr.route_id);
    }
    reroutingRef.current = false;
    setOffRoute(false);
  }, [api, loadRoute, refreshStrip]);

  const onFix = useCallback((loc: Location.LocationObject) => {
    if (arrivedRef.current || !runningRef.current) return;
    const { latitude: lat, longitude: lon } = loc.coords;
    const now = loc.timestamp || Date.now();
    if (trajRef.current.length < MAX_TRAJ) trajRef.current.push({ lat, lon, ts: now });

    const coords = coordsRef.current;
    const snap = coords.length >= 2 ? snapToPolyline(coords, lat, lon) : null;
    if (snap) {
      // monotone odometer: jitter never rewinds the strip position
      const adv = Math.max(0, snap.alongM - alongRef.current);
      alongRef.current += adv;
      pendMRef.current += adv;
      // puck marker updates ride the camera gate below — one native commit
      // per fix batch instead of two interleaved churns (SIGSEGV class)

      // arrival by route odometer: a parked rider stops emitting fixes
      // (distanceInterval filters stationary updates on both platforms),
      // so the 2-fix proximity check below can strand the end state.
      // alongM only grows, so one snapped fix within ARRIVE_M of the
      // route end is an honest arrival. Guard: longer routes only, else
      // a sub-90 m trip would arrive on its first fix.
      // NB: deferred — arrive() tears down the location subscription,
      // which must not happen inside its own callback (native SIGSEGV).
      if (routeLenRef.current > ARRIVE_M * 1.5 &&
          routeLenRef.current - alongRef.current <= ARRIVE_M) {
        setTimeout(arrive, 0);
        return;
      }
      // speed: GNSS first, else derive from fix deltas
      let v = typeof loc.coords.speed === "number" && loc.coords.speed >= 0
        ? loc.coords.speed : NaN;
      if (!Number.isFinite(v) && lastFixRef.current) {
        const dt = (now - lastFixRef.current.ts) / 1000;
        if (dt > 0.5) {
          v = havM(lastFixRef.current.lat, lastFixRef.current.lon, lat, lon) / dt;
        }
      }
      if (Number.isFinite(v)) speedRef.current = v;

      const heading = typeof loc.coords.heading === "number" && loc.coords.heading >= 0
        ? loc.coords.heading : snap.headingDeg;
      /* camera commits are the crash vector on the virtualized-GPU iOS sim
         (ci15 telemetry: teleport puck-jump → re-frame SIGSEGV). Throttle
         to ~1.5 Hz and, on teleport-class jumps (sim location commands),
         stretch a single interpolated move instead of snapping. */
      const jumpM = lastCamCenterRef.current
        ? havM(lastCamCenterRef.current[1], lastCamCenterRef.current[0], snap.lat, snap.lon)
        : 0;
      if (now - lastCamTsRef.current >= 650) {
        lastCamTsRef.current = now;
        lastCamCenterRef.current = [snap.lon, snap.lat];
        setSnapped([snap.lon, snap.lat]);
        const teleport = jumpM > 300;
        camRef?.current?.easeTo({
          center: [snap.lon, snap.lat],
          bearing: heading,
          zoom: speedRef.current > 10 ? 16 : 16.8,
          pitch: 55,
          duration: camDur(teleport ? 1600 : 900),
          easing: "linear",
        });
      }

      // speech cues + next-step banner
      for (const cue of cuesRef.current.poll(alongRef.current, lang)) {
        speakCue(cue, lang, speechRef.current);
      }
      const steps = routeRef.current.steps;
      let found: NextStep | null = null;
      if (steps && steps.length > 1) {
        let acc = 0;
        for (let i = 0; i < steps.length - 1; i++) {
          acc += Math.max(0, steps[i].distance_m || 0);
          if (acc > alongRef.current + 5) {
            found = { instruction: localizeStep(steps[i + 1], lang), distM: acc - alongRef.current };
            break;
          }
        }
      }
      // only re-render the banner when it changes meaningfully
      const prev = nextStepRef.current;
      const same = (prev == null && found == null) ||
        (prev != null && found != null &&
          prev.instruction === found.instruction &&
          Math.abs(prev.distM - found.distM) < 50);
      if (!same) {
        nextStepRef.current = found;
        setNextStep(found);
      }

      if (offRef.current.update(snap.offsetM)) void reroute({ lat, lon });
    } else {
      // no usable geometry — still check arrival by raw fix
      setSnapped([lon, lat]);
    }
    lastFixRef.current = { lat, lon, ts: now };

    const dest = destRef.current;
    // deferred for the same reason as the odometer trigger above —
    // arrive() removes the watch subscription mid-callback → segfault
    if (dest && arrRef.current.update(havM(lat, lon, dest[1], dest[0]))) {
      setTimeout(arrive, 0);
    }
  }, [arrive, camRef, lang, reroute]);

  const tick = useCallback(() => {
    if (!runningRef.current || arrivedRef.current) return;
    const c = countersRef.current;
    const strip = stripRef.current;
    const mode = strip?.mode ?? routeRef.current.mode ?? "";
    const conc = strip
      ? fieldAtAlongM(strip.samples, cumRef.current, alongRef.current)
      : { lo: null, mid: null, hi: null };
    // dt measured, never assumed (doc 04 §5)
    const nowMs = Date.now();
    const realDt = Math.max(0.2, (nowMs - (tickDtRef.current || nowMs - 1000)) / 1000);
    tickDtRef.current = nowMs;
    c.tick(realDt, speedRef.current, pendMRef.current,
      conc, strip?.emissions_curve ?? null, mode);
    pendMRef.current = 0;

    const len = routeLenRef.current;
    const rem = Math.max(0, len - alongRef.current);
    const avg = len > 0 && eta0Ref.current > 0 ? len / eta0Ref.current : 8;
    const v = speedRef.current > 0.5 ? speedRef.current : avg;
    setDose({ ...c.doseUg });
    setCo2({ lo: c.co2G.lo / 1000, mid: c.co2G.mid / 1000, hi: c.co2G.hi / 1000 });
    setPm25({ ...c.pm25G });
    setDistRemainingM(rem);
    setEtaS(rem / v);
    setProgress(len > 0 ? Math.min(1, alongRef.current / len) : 0);
  }, []);

  const start = useCallback(async () => {
    if (runningRef.current) return;
    arrivedRef.current = false;   // reusable for the next trip
    const r = routeRef.current;
    countersRef.current.reset();
    offRef.current.reset();
    arrRef.current.reset();
    nextStepRef.current = null;
    setNextStep(null);
    alongRef.current = 0;
    pendMRef.current = 0;
    trajRef.current = [];
    lastFixRef.current = null;
    startTsRef.current = Date.now();
    tickDtRef.current = Date.now();
    loadRoute(r, flattenCoords(r.geometry ?? r.route_geojson));
    runningRef.current = true;
    setRunning(true);
    setArrived(false);
    setOffRoute(false);
    setSummary(null);

    void refreshStrip(r.route_id); // strip failure is non-fatal
    try {
      const perm = await Location.getForegroundPermissionsAsync();
      if (!perm.granted) await Location.requestForegroundPermissionsAsync();
      subRef.current = await Location.watchPositionAsync(WATCH_OPTS, onFix);
    } catch {
      // no permission / provider off — keep ticking; honest zero fixes
    }
    tickRef.current = setInterval(tick, 1000);
    // perf-r4: backgrounding mid-nav must not keep GNSS + the 1 Hz loop
    // burning battery — pause both, re-arm on return (counter math uses
    // real dt, so the pause is honest)
    appSubRef.current?.remove();
    appSubRef.current = AppState.addEventListener("change", (st) => {
      if (!runningRef.current) return;
      if (st === "active") {
        if (!tickRef.current) tickRef.current = setInterval(tick, 1000);
        if (!subRef.current)
          Location.watchPositionAsync(WATCH_OPTS, onFix)
            .then((s) => { subRef.current = s; })
            .catch(() => {});
      } else {
        subRef.current?.remove();
        subRef.current = null;
        if (tickRef.current) {
          clearInterval(tickRef.current);
          tickRef.current = null;
        }
      }
    });
  }, [loadRoute, onFix, refreshStrip, tick]);

  const stop = useCallback(() => {
    cleanup();
    setRunning(false);
  }, [cleanup]);

  /** Recenter the camera on the last fix (NavChrome's onRecenter seam). */
  const recenter = useCallback(() => {
    const f = lastFixRef.current;
    if (!f) return;
    camRef?.current?.easeTo({
      center: [f.lon, f.lat], zoom: 16.8, pitch: 55, duration: camDur(600),
    });
  }, [camRef]);

  useEffect(() => cleanup, [cleanup]);
  useEffect(() => {
    if (opts.autoStart) void start();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    running, start, stop, arrive, recenter,
    dose, co2, pm25,
    progress, distRemainingM, etaS,
    offRoute, arrived, snapped, nextStep,
    stripOk, fieldAgeMin, summary, outsideField,
  };
}

export type NavEngine = ReturnType<typeof useNavEngine>;
