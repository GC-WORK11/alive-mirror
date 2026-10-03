/** useShellFlow — the trip-flow state machine behind the shell:
 * search → pick → compare → nav → receipt, plus the on-device ledger.
 * Kept out of App.tsx so the composition root stays declarative. */
import { useCallback, useEffect, useMemo, useRef, useState, type RefObject } from "react";
import { Keyboard } from "react-native";
import * as Location from "expo-location";
import type { CameraRef } from "@maplibre/maplibre-react-native";
import { V2T } from "../../theme";
import { localSearch } from "../../gazetteer";
import { requestPerms, scheduleDeparture, scheduleDailyBrief } from "../../notify";
import { loadTrips, logTrip, type Trip } from "../../store/ledger";
import { observeTrip, type CommunityTotals } from "../../community";
import { API, DELHI, fetchJson, inNcr, normName } from "./net";
import type { CompareOption, Depart, Place, Step } from "./types";

export type Phase = "idle" | "search" | "compare" | "nav";
export type Which = "to" | "from";

export function useShellFlow(camRef: RefObject<CameraRef | null>, shareEnabled: boolean) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [from, setFrom] = useState<Place | null>(null);
  const [to, setTo] = useState<Place | null>(null);
  const [query, setQuery] = useState("");
  const [editWhich, setEditWhich] = useState<Which>("to");
  const [results, setResults] = useState<Place[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [options, setOptions] = useState<CompareOption[]>([]);
  const [selected, setSelected] = useState(0);
  const [depart, setDepart] = useState<Depart>(null);
  const [trips, setTrips] = useState<Trip[]>([]);
  const [community, setCommunity] = useState<CommunityTotals | null>(null);
  const [follow, setFollow] = useState(false);
  const [loadingRoute, setLoadingRoute] = useState(false);
  const [notified, setNotified] = useState(false);
  const [steps, setSteps] = useState<Step[] | null>(null);
  const [stepsOpen, setStepsOpen] = useState(false);
  const [navDose, setNavDose] = useState(0);
  const [receipt, setReceipt] = useState<{ doseUg: number; savedUg: number } | null>(null);
  const debounce = useRef<ReturnType<typeof setTimeout> | null>(null);
  const searchSeq = useRef(0);
  const navDoseRef = useRef(0);

  /* ---- search: instant local gazetteer under a debounced remote merge ---- */
  const doSearch = useCallback((text: string) => {
    if (debounce.current) clearTimeout(debounce.current);
    if (text.trim().length < 2) { setResults(null); setSearching(false); return; }
    const bias = from ?? { lat: DELHI[1], lon: DELHI[0] };
    const local = localSearch(text, bias, 8);
    setResults(local);
    setSearching(true);
    const seq = ++searchSeq.current;
    debounce.current = setTimeout(async () => {
      try {
        const j = await fetchJson(
          `${API}/search?q=${encodeURIComponent(text)}&limit=8&lat=${bias.lat}&lon=${bias.lon}`, 8000);
        if (seq !== searchSeq.current) return;
        const remote: Place[] = j.results ?? [];
        const seen = new Set(remote.map((r) => `${normName(r.name)}|${r.lat.toFixed(3)}`));
        setResults([...remote, ...local.filter((l) => !seen.has(`${normName(l.name)}|${l.lat.toFixed(3)}`))].slice(0, 10));
      } catch { /* local answers are already on screen */ }
      finally { if (seq === searchSeq.current) setSearching(false); }
    }, 160);
  }, [from]);

  const pick = useCallback(async (p: Place, which?: Which) => {
    Keyboard.dismiss();
    setResults(null);
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
        ? { name: "current location", subtitle: "", lat: pos.coords.latitude, lon: pos.coords.longitude }
        : { name: "central delhi", subtitle: "", lat: DELHI[1], lon: DELHI[0] });
    }
    setPhase("compare");
    camRef.current?.flyTo({ center: [p.lon, p.lat], zoom: 13.5, duration: 800 });
  }, [editWhich, from, to, camRef]);

  /* ---- routes: destination+origin set → decide + depart ---- */
  useEffect(() => {
    if (phase !== "compare" || !from || !to) return;
    let cancelled = false;
    (async () => {
      setNotified(false);
      setSteps(null); setStepsOpen(false);
      setLoadingRoute(true);
      try {
        const qs = `from_lat=${from.lat}&from_lon=${from.lon}&to_lat=${to.lat}&to_lon=${to.lon}`;
        const [cj, dj] = await Promise.all([
          fetchJson(`${API}/decide?${qs}`, 12000),
          fetchJson(`${API}/depart?${qs}&vehicle=auto&hours=24`).catch(() => null),
        ]);
        if (cancelled) return;
        const opts: CompareOption[] = cj.options ?? [];
        setOptions(opts); setSelected(0);
        setDepart(dj?.best ? { best: dj.best, ug_saved_vs_now: dj.ug_saved_vs_now } : null);
        const g = opts[0]?.geometry;
        if (g?.type === "LineString") {
          const c = (g as GeoJSON.LineString).coordinates;
          camRef.current?.fitBounds(
            [Math.min(...c.map((x) => x[0])), Math.min(...c.map((x) => x[1])),
             Math.max(...c.map((x) => x[0])), Math.max(...c.map((x) => x[1]))],
            { padding: { top: 200, bottom: 340, left: 50, right: 50 }, duration: 700 });
        }
      } catch { if (!cancelled) { setOptions([]); setDepart(null); } }
      finally { if (!cancelled) setLoadingRoute(false); }
    })();
    return () => { cancelled = true; };
  }, [phase, from, to, camRef]);

  /* ---- turn-by-turn steps for the selected (road) option ---- */
  useEffect(() => {
    const o = options[selected];
    let cancelled = false;
    Promise.resolve().then(() => { if (!cancelled) setSteps(null); });
    if (!o || !from || !to || o.vehicle === "metro") return () => { cancelled = true; };
    fetchJson(
      `${API}/directions?from_lat=${from.lat}&from_lon=${from.lon}` +
        `&to_lat=${to.lat}&to_lon=${to.lon}&profile=driving&vehicle=${o.vehicle}`, 10000)
      .then((j) => { if (!cancelled && Array.isArray(j.steps)) setSteps(j.steps); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [selected, options, from, to]);

  const clearRoute = useCallback(() => {
    setTo(null); setOptions([]); setDepart(null); setSteps(null); setStepsOpen(false);
    setPhase("idle"); setFollow(false); setReceipt(null);
  }, []);

  /* ---- navigation: live dose = conc × ventilation × microenv × dt ---- */
  const startNav = useCallback(async () => {
    const o = options[selected];
    if (!o || !from || !to) return;
    setPhase("nav");
    setNavDose(0); navDoseRef.current = 0; setReceipt(null);
    Keyboard.dismiss();
    const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced }).catch(() => null);
    setFollow(!!(pos && inNcr(pos.coords.latitude, pos.coords.longitude)));
    camRef.current?.flyTo({ center: [from.lon, from.lat], zoom: 15.5, duration: 700 });
    camRef.current?.setStop({ pitch: 55, duration: 800 });
  }, [options, selected, from, to, camRef]);

  const exitNav = useCallback(() => {
    setPhase("compare"); setFollow(false);
    camRef.current?.setStop({ pitch: 0, duration: 700 });
    const o = options[selected];
    if (o && navDoseRef.current > 0.5) {
      const worst = Math.max(...options.map((x) => x.exposure?.dose_ug ?? 0));
      setReceipt({ doseUg: navDoseRef.current, savedUg: Math.max(0, worst - (o.exposure?.dose_ug ?? 0)) });
    }
  }, [options, selected, camRef]);

  useEffect(() => {
    if (phase !== "nav") return;
    const o = options[selected];
    const ventLpm = typeof o?.exposure?.factors?.ventilation_lpm === "number" ? o.exposure.factors.ventilation_lpm : 12;
    const micro = typeof o?.exposure?.factors?.microenv === "number" ? o.exposure.factors.microenv : 1;
    const tick = async () => {
      const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced }).catch(() => null);
      if (!pos || !inNcr(pos.coords.latitude, pos.coords.longitude)) return;
      const j = await fetchJson(`${API}/aqi?lat=${pos.coords.latitude}&lon=${pos.coords.longitude}`, 6000).catch(() => null);
      if (j?.pm25 != null) {
        navDoseRef.current += j.pm25 * micro * (ventLpm / 1000) * (25 / 60);
        setNavDose(Math.round(navDoseRef.current * 10) / 10);
      }
      if (to) {
        const dLat = (pos.coords.latitude - to.lat) * 110.6;
        const dLon = (pos.coords.longitude - to.lon) * 99.4;
        if (Math.sqrt(dLat * dLat + dLon * dLon) * 1000 < 80) exitNav();
      }
    };
    tick();
    const iv = setInterval(tick, 25000);
    return () => clearInterval(iv);
  }, [phase, options, selected, to, exitNav]);

  /* ---- ledger: a picked option is a trip + traversal donation ---- */
  useEffect(() => {
    const o = options[selected];
    if (!o?.exposure?.dose_ug || !from || !to || phase !== "compare") return;
    const worst = Math.max(...options.map((x) => x.exposure?.dose_ug ?? 0));
    const avoided = Math.max(0, Math.round((worst - o.exposure.dose_ug) * 10) / 10);
    logTrip({
      ts: Date.now(), label: o.label, vehicle: o.vehicle, dose_ug: o.exposure.dose_ug,
      avoided_ug: avoided, from: from.name, to: to.name,
      fromLat: from.lat, fromLon: from.lon, toLat: to.lat, toLon: to.lon,
    }).then(setTrips).catch(() => {});
    const coords = o.geometry?.type === "LineString" ? (o.geometry as GeoJSON.LineString).coordinates : [];
    if (coords.length > 1 && shareEnabled) {   // data sharing: on by default, one tap off
      const step = Math.max(1, Math.floor(coords.length / 60));
      observeTrip(API, {
        vehicle: o.vehicle, coords: coords.filter((_, i) => i % step === 0),
        duration_s: o.duration_s ?? (o.duration_min || 0) * 60,
        dose_ug: o.exposure.dose_ug, avoided_ug: avoided,
      }).then(() => fetchJson(`${API}/community`).then(setCommunity)).catch(() => {});
    }
  }, [selected, options, from, to, phase, shareEnabled]);

  const routeSegs = useMemo<GeoJSON.FeatureCollection>(() => {
    const segs = options[selected]?.segments;
    if (!segs?.length) {
      const g = options[selected]?.geometry;
      const ok = g && (g.type === "LineString" ? (g as GeoJSON.LineString).coordinates.length >= 2
        : g.type === "MultiLineString" && (g as GeoJSON.MultiLineString).coordinates.every((l) => l.length >= 2));
      return { type: "FeatureCollection", features: ok ? [{ type: "Feature", properties: { color: V2T.accent }, geometry: g! }] : [] };
    }
    return { type: "FeatureCollection", features: segs
      .filter((sg) => Array.isArray(sg.coords) && sg.coords.length >= 2)
      .map((sg) => ({ type: "Feature" as const, properties: { color: sg.color },
        geometry: { type: "LineString" as const, coordinates: sg.coords } })) };
  }, [options, selected]);

  const altSegs = useMemo<GeoJSON.FeatureCollection>(() => ({
    type: "FeatureCollection",
    features: options.map((o, i) => ({ o, i }))
      .filter(({ o, i }) => i !== selected && o.geometry?.type === "LineString" &&
        (o.geometry as GeoJSON.LineString).coordinates.length >= 2)
      .map(({ o }) => ({ type: "Feature" as const, properties: {}, geometry: o.geometry })),
  }), [options, selected]);

  const recents = useMemo<Place[]>(() => {
    const seen = new Set<string>(); const out: Place[] = [];
    for (let i = trips.length - 1; i >= 0 && out.length < 6; i--) {
      for (const c of [{ name: trips[i].to, lat: trips[i].toLat, lon: trips[i].toLon },
                       { name: trips[i].from, lat: trips[i].fromLat, lon: trips[i].fromLon }]) {
        if (c.lat == null || c.lon == null || seen.has(c.name)) continue;
        seen.add(c.name);
        out.push({ name: c.name, subtitle: "", lat: c.lat, lon: c.lon });
        if (out.length >= 6) break;
      }
    }
    return out;
  }, [trips]);

  const armDailyBrief = useCallback(async (): Promise<boolean> => {
    if (!(await requestPerms())) return false;
    const p = to ?? from ?? { lat: DELHI[1], lon: DELHI[0] };
    const j = await fetchJson(`${API}/today?lat=${p.lat}&lon=${p.lon}`).catch(() => null);
    const h: number[] | undefined = j?.hours_ist;
    if (!Array.isArray(h) || h.length < 24) return false;
    let best = 0;
    for (let i = 0; i <= 21; i++) if (h[i] + h[i + 1] + h[i + 2] < h[best] + h[best + 1] + h[best + 2]) best = i;
    const drop = Math.max(5, Math.round((1 - ((h[best] + h[best + 1] + h[best + 2]) / 3) / (h.reduce((a, b) => a + b, 0) / 24)) * 100));
    return (await scheduleDailyBrief({ startHour: best, endHour: (best + 3) % 24, dropPct: drop })) != null;
  }, [from, to]);

  const remind = useCallback(async () => {
    if (!depart?.best?.start || notified || !(await requestPerms())) return;
    const fire = new Date(depart.best.start.endsWith("Z") ? depart.best.start : depart.best.start + "Z");
    if (await scheduleDeparture({ fireAt: fire, savedPct: depart.ug_saved_vs_now ?? 0 })) setNotified(true);
  }, [depart, notified]);

  const reloadTrips = useCallback(() => { loadTrips().then(setTrips).catch(() => {}); }, []);

  return {
    phase, setPhase, from, setFrom, to, setTo, query, setQuery,
    editWhich, setEditWhich, results, searching, options, selected, setSelected,
    depart, notified, trips, setTrips, community, setCommunity, follow, setFollow,
    loadingRoute, steps, stepsOpen, setStepsOpen, navDose, receipt, setReceipt,
    doSearch, pick, clearRoute, startNav, exitNav, remind, armDailyBrief,
    routeSegs, altSegs, recents, reloadTrips,
  };
}
