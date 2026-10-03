/**
 * useNavEngine — Phase-4 live navigation (doc 04 §4–5).
 *
 * Self-contained: owns its expo-location watcher (1 s / 5 m,
 * BestForNavigation), a 1 Hz ticker for the two live counters, strip
 * walking, off-route → /v2/reroute, arrival → receipt, and the optional
 * /v2/trip donation. All counter math is local (doc 04 §5 hard rule).
 */

import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import * as Location from "expo-location";
import type { CameraRef } from "@maplibre/maplibre-react-native";
import { API } from "../components/shell/net";
import { contributorId } from "../community";
import { fetchStrip } from "../api/strip";
import { postJson, postReroute } from "../api/reroute";
import { enqueueTripDonation } from "../offline/queue";
import { LiveCounters } from "./counters";
import {
  ArrivalTracker, flattenCoords, havM, OffRouteTracker,
  polylineLengthM, snapToPolyline, type LonLat,
} from "./offroute";
import { fieldAtAlongM, stripCumM, type Band, type RouteStrip } from "./strip";
import { CueTracker, speakCue, stopCues, type NavStep } from "./speech";
import type { Lang } from "../i18n/strings";

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

export function useNavEngine(opts: NavEngineOpts) {
  const { route, camRef, onArrive, lang = "en", shareEnabled = false, speech = false } = opts;
  const api = opts.apiBase ?? API;

  const [running, setRunning] = useState(false);
  const [arrived, setArrived] = useState(false);
  const [offRoute, setOffRoute] = useState(false);
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
    if (tickRef.current) clearInterval(tickRef.current);
    tickRef.current = null;
    stopCues();
    runningRef.current = false;
  }, []);

  const donate = useCallback(async (s: NavSummary) => {
    const donation = {
      device_token: await contributorId(), // stable anonymous id (src/store)
      trajectory: trajRef.current.map((p) => ({ lat: p.lat, lon: p.lon })),
      summary: {
        mode: s.mode,
        distance_km: Math.round(s.distanceKm * 100) / 100,
        duration_s: Math.round(s.durationS),
        dose_ug: Math.round(s.doseUg.mid * 10) / 10,
        co2_kg_mid: Math.round(s.co2Kg.mid * 1000) / 1000,
        pm25_g_mid: Math.round(s.pm25G.mid * 1000) / 1000,
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

  const arrive = useCallback(() => {
    if (arrivedRef.current) return;
    arrivedRef.current = true;
    cleanup();
    setArrived(true);
    setRunning(false);
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
    if (res?.geometry) {
      const next: NavRoute = { ...r, route_id: res.route_id, geometry: res.geometry,
        eta_s: res.eta_s ?? r.eta_s, mode: res.mode ?? r.mode };
      routeRef.current = next;
      loadRoute(next, flattenCoords(res.geometry));
      alongRef.current = 0;
      offRef.current.reset();
      await refreshStrip(res.route_id);
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
      setSnapped([snap.lon, snap.lat]);
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
      camRef?.current?.easeTo({
        center: [snap.lon, snap.lat],
        bearing: heading,
        zoom: speedRef.current > 10 ? 16 : 16.8,
        pitch: 55,
        duration: 900,
        easing: "linear",
      });

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
            found = { instruction: steps[i + 1].instruction, distM: acc - alongRef.current };
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
    if (dest && arrRef.current.update(havM(lat, lon, dest[1], dest[0]))) arrive();
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
      subRef.current = await Location.watchPositionAsync(
        {
          accuracy: Location.Accuracy.BestForNavigation,
          timeInterval: 1000,
          distanceInterval: 5,
          mayShowUserSettingsDialog: true,
        },
        onFix,
      );
    } catch {
      // no permission / provider off — keep ticking; honest zero fixes
    }
    tickRef.current = setInterval(tick, 1000);
  }, [loadRoute, onFix, refreshStrip, tick]);

  const stop = useCallback(() => {
    cleanup();
    setRunning(false);
  }, [cleanup]);

  useEffect(() => cleanup, [cleanup]);
  useEffect(() => {
    if (opts.autoStart) void start();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    running, start, stop, arrive,
    dose, co2, pm25,
    progress, distRemainingM, etaS,
    offRoute, arrived, snapped, nextStep,
    stripOk, fieldAgeMin, summary,
  };
}

export type NavEngine = ReturnType<typeof useNavEngine>;
