import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Keyboard,
  LogBox,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import * as SplashScreen from "expo-splash-screen";
import { useFonts } from "@expo-google-fonts/outfit";
import {
  Outfit_300Light,
  Outfit_400Regular,
  Outfit_500Medium,
  Outfit_600SemiBold,
  Outfit_700Bold,
} from "@expo-google-fonts/outfit";
import * as Location from "expo-location";
import { File, Paths } from "expo-file-system";
import {
  Camera,
  GeoJSONSource,
  Layer,
  Map,
  Marker,
  UserLocation,
  type CameraRef,
} from "@maplibre/maplibre-react-native";
import { F, NUM, T, cigOf, doseColor } from "./src/theme";
import { Icon, reportGlyph, vehicleGlyph } from "./src/icons";
import { AlertBanner, CigStrip, EndpointPin, Fab, ModeRow, SearchPill, Sheet } from "./src/ui";
import { AmbientMode } from "./src/components/AmbientMode";
import { requestPerms, scheduleDeparture, scheduleDailyBrief } from "./src/notify";
import { FieldLayer } from "./src/components/FieldLayer";
import { LedgerSheet } from "./src/components/LedgerSheet";
import { JourneyDrawer } from "./src/components/JourneyDrawer";
import { ReportsLayer } from "./src/components/ReportsLayer";
import { CorridorLayer } from "./src/components/CorridorLayer";
import { loadTrips, logTrip, stats as ledgerStats, weekStats } from "./src/store/ledger";
import { observeTrip, postReport, type CommunityTotals, type ReportKind } from "./src/community";

SplashScreen.preventAutoHideAsync().catch(() => {});

const API =
  process.env.EXPO_PUBLIC_API_URL ??
  Platform.select({
    android: "http://10.0.2.2:8000",
    default: "http://localhost:8000",
  });

const STYLE_URL = "https://tiles.openfreemap.org/styles/positron";
const DELHI: [number, number] = [77.209, 28.6139];
const NCR = { minLon: 76.75, maxLon: 77.95, minLat: 28.15, maxLat: 28.98 };
const inNcr = (lat: number, lon: number) =>
  lon > NCR.minLon && lon < NCR.maxLon && lat > NCR.minLat && lat < NCR.maxLat;

type Place = { name: string; subtitle: string; lat: number; lon: number; outside_ncr?: boolean };
type Exposure = {
  dose_ug: number | null;
  avg_conc_ugm3: number | null;
  peak_conc?: number | null;
  confidence: "high" | "medium" | "low" | "none";
  coverage?: number;
  factors?: { microenv: number | string; ventilation_lpm: number | string; road_uplift: number | string };
  dose_vs_best_pct?: number;
  ug_saved_vs_worst?: number;
};
type Seg = { start_frac: number; end_frac: number; dose_ug: number | null; avg_conc_ugm3: number | null; color: string; coords: number[][] };
type CompareOption = {
  decision_score?: number;
  decision_reasons?: string[];
  vehicle: string;
  label: string;
  distance_km: number;
  duration_min: number;
  duration_s?: number;
  duration_model?: "osrm" | "estimated";
  geometry: GeoJSON.Geometry;
  stations?: { board: string; alight: string };
  segments?: Seg[];
  hotspots?: { share_pct: number; midpoint_coord: number[] }[];
  exposure?: Exposure;
};
type Depart = {
  best: { hours_ahead: number; start: string | null; dose_ug: number };
  ug_saved_vs_now: number | null;
} | null;
type FieldRead = {
  pm25: number;
  pm25_lo?: number | null;
  pm25_hi?: number | null;
  pm10?: number | null;
  nearest_sample_km?: number;
  typical?: { median: number; vs_now_pct: number | null } | null;
  wind?: { speed_kmh: number; from_deg: number; factor: number } | null;
  grap?: { indicative_stage: number | null; basis_pm25: number | null } | null;
  field?: { age_s: number | null } | null;
  lat: number;
  lon: number;
};

// liberty ships a few vector tiles MLRN can't parse — a native dev-only
// console warning; nothing in our layers is involved
LogBox.ignoreLogs(["Invalid geometry in line layer"]);

const COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
const windFrom = (deg: number) => COMPASS[Math.round(deg / 45) % 8];
const HORIZONS = [0, 6, 12, 24];

const arrivalLabel = (durationMin: number) => {
  const d = new Date(Date.now() + durationMin * 60000);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
};

const hourLabel = (iso: string | null, ahead: number) => {
  if (iso) {
    const d = new Date(iso.endsWith("Z") ? iso : iso + "Z");
    if (!isNaN(d.getTime())) {
      const ist = new Date(d.getTime() + 5.5 * 3600 * 1000);
      const hh = String(ist.getUTCHours()).padStart(2, "0");
      const today = new Date(Date.now() + 5.5 * 3600 * 1000);
      const day = ist.getUTCDate() !== today.getUTCDate() ? "tomorrow " : "";
      return `${day}${hh}:30`;
    }
  }
  return `+${ahead}h`;
};

type Step = { instruction: string; distance_m: number; type?: string };
type Phase = "idle" | "search" | "compare" | "nav";
type Which = "to" | "from";

const fetchJson = (url: string, timeoutMs = 9000) => {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  return fetch(url, { signal: ctrl.signal })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`http ${r.status}`))))
    .finally(() => clearTimeout(t));
};

export default function App() {
  const camRef = useRef<CameraRef>(null);
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
  const [fieldRead, setFieldRead] = useState<FieldRead | null>(null);
  const [grid, setGrid] = useState<GeoJSON.FeatureCollection | null>(null);
  const [horizonH, setHorizonH] = useState(0);
  const [trips, setTrips] = useState<Awaited<ReturnType<typeof loadTrips>>>([]);
  const [community, setCommunity] = useState<CommunityTotals | null>(null);
  const [shiftCig, setShiftCig] = useState<number | null>(null);
  const [escape, setEscape] = useState<{ name?: string; pm25: number; pct_less_than_here?: number } | null>(null);
  const [reports, setReports] = useState<GeoJSON.FeatureCollection | null>(null);
  const [profileOpen, setProfileOpen] = useState(false);
  const [reportMode, setReportMode] = useState(false);
  const [follow, setFollow] = useState(false);
  const [hasLoc, setHasLoc] = useState(false);
  const [loadingRoute, setLoadingRoute] = useState(false);
  const [apiOk, setApiOk] = useState<boolean | null>(null);
  const [ledger, setLedger] = useState<ReturnType<typeof ledgerStats>>({
    todayUg: 0, avoidedUg: 0, allAvoidedUg: 0, cigEq: 0,
    budgetUg: 216, budgetPct: 0, streak: 0, today: [],
  });
  const [showLedger, setShowLedger] = useState(false);
  const [ambient, setAmbient] = useState(false);
  const [curve, setCurve] = useState<number[] | null>(null);
  const [curveHour, setCurveHour] = useState<number | null>(null);
  const [notified, setNotified] = useState(false);
  const [introSeen, setIntroSeen] = useState<boolean | null>(null);
  const [steps, setSteps] = useState<Step[] | null>(null);
  const [stepsOpen, setStepsOpen] = useState(false);
  const [navDose, setNavDose] = useState(0);       // live inhaled µg this trip
  const [navConc, setNavConc] = useState<number | null>(null);
  const [receipt, setReceipt] = useState<{ doseUg: number; savedUg: number } | null>(null);
  const debounce = useRef<ReturnType<typeof setTimeout> | null>(null);
  const searchSeq = useRef(0);
  const navDoseRef = useRef(0);

  const [fontsLoaded] = useFonts({
    Outfit_300Light, Outfit_400Regular, Outfit_500Medium,
    Outfit_600SemiBold, Outfit_700Bold,
  });
  useEffect(() => {
    if (fontsLoaded) SplashScreen.hideAsync().catch(() => {});
  }, [fontsLoaded]);

  /* ---- boot: warm the API, load field/community/ledger, resolve location ---- */
  useEffect(() => {
    const ping = () => fetch(`${API}/health`, { keepalive: true })
      .then((r) => setApiOk(r.ok)).catch(() => setApiOk(false));
    ping();
    const healthIv = setInterval(ping, 15000);
    fetchJson(`${API}/grid`, 15000).then(setGrid).catch(() => {});
    fetchJson(`${API}/community`).then(setCommunity).catch(() => {});
    fetchJson(`${API}/shift?lat=28.6139&lon=77.2090&hours=8&vehicle=driving_two_wheeler`)
      .then((j) => setShiftCig(j.cig_equiv ?? null)).catch(() => {});
    const poll = () => fetchJson(`${API}/reports`).then(setReports).catch(() => {});
    poll();
    const iv = setInterval(poll, 60000);
    loadTrips().then((t) => { setTrips(t); setLedger(ledgerStats(t)); }).catch(() => {});
    (async () => {
      const r = await Location.requestForegroundPermissionsAsync().catch(() => null);
      setHasLoc(!!r?.granted);
      const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced }).catch(() => null);
      const lat = pos?.coords.latitude ?? DELHI[1];
      const lon = pos?.coords.longitude ?? DELHI[0];
      if (pos) {
        setFrom({ name: "current location", subtitle: "", lat, lon });
        camRef.current?.flyTo({ center: [lon, lat], zoom: 12.5, duration: 900 });
      }
      fetchJson(`${API}/escape?lat=${lat}&lon=${lon}&limit=3`)
        .then((j) => setEscape(j?.best?.[0] ?? null)).catch(() => {});
    })();
    setIntroSeen(new File(Paths.document, "intro_seen.txt").exists);
    return () => { clearInterval(iv); clearInterval(healthIv); };
  }, []);

  const dismissIntro = useCallback(() => {
    setIntroSeen(true);
    try { new File(Paths.document, "intro_seen.txt").write("1"); } catch {}
  }, []);

  /* ---- search: debounced, aborted, keeps prior results visible ---- */
  const doSearch = useCallback((text: string) => {
    if (debounce.current) clearTimeout(debounce.current);
    if (text.trim().length < 2) { setResults(null); setSearching(false); return; }
    setSearching(true);
    const seq = ++searchSeq.current;
    debounce.current = setTimeout(async () => {
      try {
        const bias = from ?? { lat: DELHI[1], lon: DELHI[0] };
        const j = await fetchJson(
          `${API}/search?q=${encodeURIComponent(text)}&limit=8&lat=${bias.lat}&lon=${bias.lon}`, 8000);
        if (seq !== searchSeq.current) return;
        setResults(j.results ?? []);
      } catch {
        // keep previous results — never blank the list mid-type
      } finally {
        if (seq === searchSeq.current) setSearching(false);
      }
    }, 160);
  }, [from]);

  const openSearch = useCallback((which: Which) => {
    setEditWhich(which);
    setQuery(which === "to" ? "" : "");
    setResults(null);
    setPhase("search");
  }, []);

  const closeSearch = useCallback(() => {
    setPhase(to && from ? "compare" : to ? "compare" : "idle");
    setResults(null);
    Keyboard.dismiss();
  }, [from, to]);

  const pick = useCallback(
    async (p: Place) => {
      Keyboard.dismiss();
      setResults(null);
      if (editWhich === "from") {
        setFrom(p);
        setPhase(to ? "compare" : "search");
        setEditWhich("to");
        if (!to) return;
      } else {
        setTo(p);
        // destination-first: origin defaults to current location
        let o = from;
        if (!o) {
          try {
            const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
            o = { name: "current location", subtitle: "", lat: pos.coords.latitude, lon: pos.coords.longitude };
            setFrom(o);
          } catch {
            o = { name: "central delhi", subtitle: "", lat: DELHI[1], lon: DELHI[0] };
            setFrom(o);
          }
        }
        setPhase("compare");
        camRef.current?.flyTo({ center: [p.lon, p.lat], zoom: 13.5, duration: 800 });
      }
    },
    [editWhich, from, to]
  );

  const sendReport = useCallback(async (kind: ReportKind) => {
    setReportMode(false);
    try {
      const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced }).catch(() => null);
      const lat = pos?.coords.latitude ?? DELHI[1];
      const lon = pos?.coords.longitude ?? DELHI[0];
      await postReport(API, kind, lat, lon);
      const r = await fetch(`${API}/reports`);
      setReports(await r.json());
    } catch {}
  }, []);

  const scrubField = useCallback((h: number) => {
    setHorizonH(h);
    const url = h > 0 ? `${API}/grid?h=${h}` : `${API}/grid`;
    fetchJson(url).then(setGrid).catch(() => {});
  }, []);

  /* ---- routes: destination+origin set → decide + depart ---- */
  useEffect(() => {
    if (phase !== "compare" || !from || !to) return;
    let cancelled = false;
    setNotified(false);
    setSteps(null); setStepsOpen(false);
    const load = async () => {
      setLoadingRoute(true);
      try {
        const qs = `from_lat=${from.lat}&from_lon=${from.lon}&to_lat=${to.lat}&to_lon=${to.lon}`;
        const [cj, dj] = await Promise.all([
          fetchJson(`${API}/decide?${qs}`, 12000),
          fetchJson(`${API}/depart?${qs}&vehicle=auto&hours=24`).catch(() => null),
        ]);
        if (cancelled) return;
        const opts: CompareOption[] = cj.options ?? [];
        setOptions(opts);
        setSelected(0);
        setDepart(dj?.best ? { best: dj.best, ug_saved_vs_now: dj.ug_saved_vs_now } : null);
        const g = opts[0]?.geometry;
        if (g?.type === "LineString") {
          const coords = (g as GeoJSON.LineString).coordinates;
          const lons = coords.map((c) => c[0]);
          const lats = coords.map((c) => c[1]);
          camRef.current?.fitBounds(
            [Math.min(...lons), Math.min(...lats), Math.max(...lons), Math.max(...lats)],
            { padding: { top: 200, bottom: 340, left: 50, right: 50 }, duration: 700 }
          );
        }
      } catch {
        if (!cancelled) { setOptions([]); setDepart(null); }
      } finally {
        if (!cancelled) setLoadingRoute(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [phase, from, to]);

  /* ---- turn-by-turn steps for the selected (road) option ---- */
  useEffect(() => {
    setSteps(null);
    const o = options[selected];
    if (!o || !from || !to) return;
    if (o.vehicle === "metro") return;
    const profile = o.vehicle === "walk" ? "walking" : o.vehicle === "cycle" ? "cycling" : "driving";
    if (profile !== "driving") return;
    fetchJson(
      `${API}/directions?from_lat=${from.lat}&from_lon=${from.lon}` +
        `&to_lat=${to.lat}&to_lon=${to.lon}&profile=${profile}&vehicle=${o.vehicle}`, 10000)
      .then((j) => { if (Array.isArray(j.steps)) setSteps(j.steps); })
      .catch(() => {});
  }, [selected, options, from, to]);

  const clearRoute = useCallback(() => {
    setTo(null); setOptions([]); setDepart(null); setSteps(null); setStepsOpen(false);
    setPhase("idle"); setFollow(false); setReceipt(null);
  }, []);

  /* ---- navigation: live dose meter = conc × ventilation × microenv × dt ---- */
  const startNav = useCallback(async () => {
    const o = options[selected];
    if (!o || !from || !to) return;
    setPhase("nav");
    setNavDose(0); navDoseRef.current = 0;
    setReceipt(null);
    Keyboard.dismiss();
    const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced }).catch(() => null);
    setFollow(!!(pos && inNcr(pos.coords.latitude, pos.coords.longitude)));
    camRef.current?.flyTo({ center: [from.lon, from.lat], zoom: 15.5, duration: 700 });
    camRef.current?.setStop({ pitch: 55, duration: 800 });
  }, [options, selected, from, to]);

  useEffect(() => {
    if (phase !== "nav") { setNavConc(null); return; }
    const o = options[selected];
    const ventLpm = typeof o?.exposure?.factors?.ventilation_lpm === "number"
      ? o.exposure.factors.ventilation_lpm : 12;
    const micro = typeof o?.exposure?.factors?.microenv === "number"
      ? o.exposure.factors.microenv : 1;
    const tick = async () => {
      const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced }).catch(() => null);
      if (!pos || !inNcr(pos.coords.latitude, pos.coords.longitude)) return;
      const j = await fetchJson(`${API}/aqi?lat=${pos.coords.latitude}&lon=${pos.coords.longitude}`, 6000).catch(() => null);
      if (j?.pm25 != null) {
        setNavConc(Math.round(j.pm25));
        // dose += conc(µg/m³) × microenv × vent(L/min)/1000 × dt(min)
        const dtMin = 25 / 60;
        navDoseRef.current += j.pm25 * micro * (ventLpm / 1000) * dtMin;
        setNavDose(Math.round(navDoseRef.current * 10) / 10);
      }
    };
    tick();
    const iv = setInterval(tick, 25000);
    return () => clearInterval(iv);
  }, [phase, options, selected]);

  const exitNav = useCallback(() => {
    setPhase("compare");
    setFollow(false);
    camRef.current?.setStop({ pitch: 0, duration: 700 });
    const o = options[selected];
    if (o && navDoseRef.current > 0.5) {
      const worst = Math.max(...options.map((x) => x.exposure?.dose_ug ?? 0));
      setReceipt({ doseUg: navDoseRef.current, savedUg: Math.max(0, worst - (o.exposure?.dose_ug ?? 0)) });
    }
    const g = options[selected]?.geometry;
    if (g?.type === "LineString") {
      const coords = (g as GeoJSON.LineString).coordinates;
      const lons = coords.map((c) => c[0]);
      const lats = coords.map((c) => c[1]);
      camRef.current?.fitBounds(
        [Math.min(...lons), Math.min(...lats), Math.max(...lons), Math.max(...lats)],
        { padding: { top: 200, bottom: 340, left: 50, right: 50 }, duration: 700 }
      );
    }
  }, [options, selected]);

  /* ---- ledger: a picked option is a trip + traversal donation ---- */
  useEffect(() => {
    const o = options[selected];
    if (!o?.exposure?.dose_ug || !from || !to || phase !== "compare") return;
    const worst = Math.max(...options.map((x) => x.exposure?.dose_ug ?? 0));
    const avoided = Math.max(0, Math.round((worst - o.exposure.dose_ug) * 10) / 10);
    logTrip({
      ts: Date.now(), label: o.label, vehicle: o.vehicle,
      dose_ug: o.exposure.dose_ug,
      avoided_ug: avoided,
      from: from.name, to: to.name,
      fromLat: from.lat, fromLon: from.lon, toLat: to.lat, toLon: to.lon,
    }).then((t) => { setTrips(t); setLedger(ledgerStats(t)); }).catch(() => {});
    const g = o.geometry;
    const coords = g?.type === "LineString" ? (g as GeoJSON.LineString).coordinates : [];
    if (coords.length > 1) {
      const step = Math.max(1, Math.floor(coords.length / 60));
      observeTrip(API, {
        vehicle: o.vehicle,
        coords: coords.filter((_, i) => i % step === 0),
        duration_s: o.duration_s ?? (o.duration_min || 0) * 60,
        dose_ug: o.exposure.dose_ug,
        avoided_ug: avoided,
      }).then(() => fetchJson(`${API}/community`).then(setCommunity)).catch(() => {});
    }
  }, [selected, options, from, to, phase]);

  const routeSegs = useMemo<GeoJSON.FeatureCollection>(() => {
    const segs = options[selected]?.segments;
    if (!segs?.length) {
      const g = options[selected]?.geometry;
      const ok =
        g &&
        ((g.type === "LineString" && (g as GeoJSON.LineString).coordinates.length >= 2) ||
          (g.type === "MultiLineString" &&
            (g.type === "MultiLineString" &&
              (g as GeoJSON.MultiLineString).coordinates.every((l) => l.length >= 2))));
      return {
        type: "FeatureCollection",
        features: ok ? [{ type: "Feature", properties: { color: T.go }, geometry: g! }] : [],
      };
    }
    return {
      type: "FeatureCollection",
      features: segs
        .filter((sg) => Array.isArray(sg.coords) && sg.coords.length >= 2)
        .map((sg) => ({
          type: "Feature" as const,
          properties: { color: sg.color },
          geometry: { type: "LineString" as const, coordinates: sg.coords },
        })),
    };
  }, [options, selected]);

  const recents = useMemo<Place[]>(() => {
    const seen = new Set<string>();
    const out: Place[] = [];
    for (let i = trips.length - 1; i >= 0 && out.length < 6; i--) {
      const t = trips[i];
      for (const cand of [
        { name: t.to, lat: t.toLat, lon: t.toLon },
        { name: t.from, lat: t.fromLat, lon: t.fromLon },
      ]) {
        if (cand.lat == null || cand.lon == null || seen.has(cand.name)) continue;
        seen.add(cand.name);
        out.push({ name: cand.name, subtitle: "", lat: cand.lat, lon: cand.lon });
        if (out.length >= 6) break;
      }
    }
    return out;
  }, [trips]);

  const altSegs = useMemo<GeoJSON.FeatureCollection>(() => ({
    type: "FeatureCollection",
    features: options
      .map((o, i) => ({ o, i }))
      .filter(
        ({ o, i }) =>
          i !== selected &&
          o.geometry?.type === "LineString" &&
          (o.geometry as GeoJSON.LineString).coordinates.length >= 2
      )
      .map(({ o }) => ({ type: "Feature" as const, properties: {}, geometry: o.geometry })),
  }), [options, selected]);

  const openLedger = useCallback(async () => {
    setShowLedger(true);
    try {
      const p = to ?? from;
      if (p) {
        const j = await fetchJson(`${API}/today?lat=${p.lat}&lon=${p.lon}`);
        setCurve(j.hours_ist ?? null);
        setCurveHour(j.hour_now_ist ?? null);
      }
    } catch {}
  }, [from, to]);

  const openAmbient = useCallback(async () => {
    setAmbient(true);
    try {
      const p = to ?? from ?? { lat: DELHI[1], lon: DELHI[0] };
      const j = await fetchJson(`${API}/aqi?lat=${p.lat}&lon=${p.lon}`);
      if (j.pm25 != null)
        setFieldRead({ pm25: j.pm25, pm25_lo: j.pm25_lo, pm25_hi: j.pm25_hi, pm10: j.pm10, nearest_sample_km: j.nearest_sample_km, typical: j.typical, wind: j.wind, grap: j.grap, field: j.field, lat: p.lat, lon: p.lon });
    } catch {}
  }, [from, to]);

  const armDailyBrief = useCallback(async (): Promise<boolean> => {
    if (!(await requestPerms())) return false;
    const p = to ?? from ?? { lat: DELHI[1], lon: DELHI[0] };
    const j = await fetchJson(`${API}/today?lat=${p.lat}&lon=${p.lon}`).catch(() => null);
    const h: number[] | undefined = j?.hours_ist;
    if (!Array.isArray(h) || h.length < 24) return false;
    let best = 0;
    for (let i = 0; i <= 21; i++) {
      if (h[i] + h[i + 1] + h[i + 2] < h[best] + h[best + 1] + h[best + 2]) best = i;
    }
    const meanAll = h.reduce((a, b) => a + b, 0) / 24;
    const meanWin = (h[best] + h[best + 1] + h[best + 2]) / 3;
    const drop = Math.max(5, Math.round((1 - meanWin / meanAll) * 100));
    const id = await scheduleDailyBrief({ startHour: best, endHour: (best + 3) % 24, dropPct: drop });
    return id != null;
  }, [from, to]);

  const remind = useCallback(async () => {
    if (!depart?.best?.start || notified) return;
    if (!(await requestPerms())) return;
    const fire = new Date(depart.best.start.endsWith("Z") ? depart.best.start : depart.best.start + "Z");
    const id = await scheduleDeparture({ fireAt: fire, savedPct: depart.ug_saved_vs_now ?? 0 });
    if (id) setNotified(true);
  }, [depart, notified]);

  if (!fontsLoaded) return null;

  const week = weekStats(trips);
  const sel = options[selected];
  const worstDose = options.length ? Math.max(...options.map((o) => o.exposure?.dose_ug ?? 0)) : 0;
  const bestDose = options.length ? Math.min(...options.map((o) => o.exposure?.dose_ug ?? Infinity)) : 0;

  return (
    <View style={s.root}>
      <StatusBar style="dark" />
      <Map
        mapStyle={STYLE_URL}
        style={StyleSheet.absoluteFill}
        onPress={async (f) => {
          const c = f.nativeEvent.lngLat;
          if (!c || phase === "search" || phase === "nav") return;
          try {
            const j = await fetchJson(`${API}/aqi?lat=${c[1]}&lon=${c[0]}`, 6000);
            if (j.pm25 != null)
              setFieldRead({ pm25: j.pm25, pm25_lo: j.pm25_lo, pm25_hi: j.pm25_hi, pm10: j.pm10, nearest_sample_km: j.nearest_sample_km, typical: j.typical, wind: j.wind, grap: j.grap, field: j.field, lat: c[1], lon: c[0] });
          } catch {}
        }}
        onLongPress={async (f) => {
          const c = f.nativeEvent.lngLat;
          if (!c) return;
          let name = `${c[1].toFixed(4)}, ${c[0].toFixed(4)}`;
          try {
            const j = await fetchJson(`${API}/reverse?lat=${c[1]}&lon=${c[0]}`, 6000);
            if (j.name) name = j.name;
          } catch {}
          setTo({ name, subtitle: "", lat: c[1], lon: c[0] });
          if (!from) {
            const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced }).catch(() => null);
            setFrom(pos
              ? { name: "current location", subtitle: "", lat: pos.coords.latitude, lon: pos.coords.longitude }
              : { name: "central delhi", subtitle: "", lat: DELHI[1], lon: DELHI[0] });
          }
          setPhase("compare");
        }}
      >
        <Camera ref={camRef} initialViewState={{ center: DELHI, zoom: 11 }} maxBounds={[76.75, 28.15, 77.95, 28.98]}
          trackUserLocation={follow ? "default" : undefined}
          onTrackUserLocationChange={(e) => { if (!e.nativeEvent.trackUserLocation) setFollow(false); }} />
        {hasLoc && <UserLocation animated accuracy />}
        <CorridorLayer corridors={community?.top_corridors ?? null} />
        <FieldLayer grid={grid} />
        <ReportsLayer reports={reports} />
        <Layer
          id="buildings3d"
          type="fill-extrusion"
          source="openmaptiles"
          source-layer="building"
          minzoom={14}
          paint={{
            "fill-extrusion-color": "#E3E1DE",
            "fill-extrusion-height": ["coalesce", ["get", "render_height"], ["get", "height"], 10],
            "fill-extrusion-opacity": 0.5,
          }}
        />
        <GeoJSONSource id="alts" data={altSegs}>
          <Layer id="alts-line" type="line"
            paint={{ "line-color": "rgba(87,83,78,0.3)", "line-width": 2.5, "line-dasharray": [2, 2] }}
            layout={{ "line-cap": "round", "line-join": "round" }} />
        </GeoJSONSource>
        <GeoJSONSource id="route" data={routeSegs}>
          <Layer id="route-casing" type="line"
            paint={{ "line-color": "#FCFCFB", "line-width": 8, "line-opacity": 0.85 }}
            layout={{ "line-cap": "round", "line-join": "round" }} />
          <Layer id="route-line" type="line"
            paint={{ "line-color": ["get", "color"], "line-width": 4.5 }}
            layout={{ "line-cap": "round", "line-join": "round" }} />
        </GeoJSONSource>
        {from && phase === "compare" && (
          <Marker lngLat={[from.lon, from.lat]} anchor="center">
            <EndpointPin kind="origin" />
          </Marker>
        )}
        {to && (
          <Marker lngLat={[to.lon, to.lat]} anchor="bottom">
            <EndpointPin kind="dest" />
          </Marker>
        )}
      </Map>

      {/* ============ SEARCH PILL — always visible except in nav ============ */}
      {phase !== "nav" && (
        <View style={s.pillWrap}>
          <SearchPill
            placeholder={phase === "compare" && to ? to.name : "Where to in Delhi?"}
            value={phase === "search" ? query : ""}
            onFocus={() => { if (phase !== "search") openSearch("to"); }}
            onChange={(t) => { setQuery(t); doSearch(t); }}
            onAvatar={() => setProfileOpen(true)}
            hint={searching ? "searching" : undefined}
            left={phase === "compare"
              ? <Pressable onPress={clearRoute} hitSlop={8}><Icon name="close" color={T.ink3} size={16} /></Pressable>
              : undefined}
          />
          {/* origin row — quiet, inside the search sheet only */}
          {phase === "search" && (
            <Pressable style={s.originRow} onPress={() => setEditWhich(editWhich === "from" ? "to" : "from")}>
              <View style={s.originDot} />
              <Text style={s.originTxt} numberOfLines={1}>
                from: <Text style={{ color: T.ink }}>{from?.name ?? "current location"}</Text>
              </Text>
              <Text style={s.originEdit}>{editWhich === "from" ? "editing" : "change"}</Text>
            </Pressable>
          )}
          {phase === "search" && editWhich === "from" && (
            <Text style={s.searchHint}>type to change where you start from</Text>
          )}
          {phase === "search" && (
            <View style={s.resultsSheet}>
              {(results ?? (query.trim().length < 2 ? recents : [])).map((p, i) => (
                <Pressable key={`${p.lat},${p.lon},${i}`} onPress={() => pick(p)}
                  style={({ pressed }) => [s.result, pressed && { opacity: 0.55 }]}>
                  <Icon name="pin" color={T.ink3} size={16} />
                  <View style={{ flex: 1, marginLeft: 10 }}>
                    <Text style={s.rname} numberOfLines={1}>{p.name}</Text>
                    {!!p.subtitle && <Text style={s.rsub} numberOfLines={1}>{p.subtitle}</Text>}
                  </View>
                  {p.outside_ncr && <Text style={s.outsideTag}>outside ncr</Text>}
                </Pressable>
              ))}
              {results && results.length === 0 && !searching && (
                <Text style={s.noResults}>nothing found — try a bigger name</Text>
              )}
              {searching && !results?.length && (
                <View style={{ paddingVertical: 14, alignItems: "center" }}>
                  <ActivityIndicator size="small" color={T.go} />
                </View>
              )}
            </View>
          )}
        </View>
      )}

      {/* ============ FAB COLUMN — locate + report (screen budget: 2) ============ */}
      {(phase === "idle" || phase === "compare") && (
        <View style={s.fabCol}>
          {hasLoc && <Fab glyph="locate" active={follow} onPress={() => setFollow(!follow)} />}
          <Fab glyph="flag" onPress={() => setReportMode(!reportMode)} />
        </View>
      )}

      {/* report picker — four pictographs, wordless */}
      {reportMode && phase !== "nav" && (
        <View style={s.reportRow}>
          {(["dust", "smoke", "burning", "clean"] as ReportKind[]).map((k) => (
            <Pressable key={k} onPress={() => sendReport(k)}
              style={({ pressed }) => [s.reportOpt, pressed && { opacity: 0.55 }]}>
              <Icon name={reportGlyph(k)} color={T.ink} size={26} />
            </Pressable>
          ))}
        </View>
      )}

      {/* horizon chips — only while comparing routes */}
      {phase === "compare" && (
        <View style={s.horizonWrap}>
          {HORIZONS.map((h) => (
            <Pressable key={h} onPress={() => scrubField(h)}
              style={({ pressed }) => [s.hChip, horizonH === h && s.hChipOn, pressed && { opacity: 0.6 }]}>
              <Text style={[s.hTxt, NUM, horizonH === h && s.hTxtOn]}>
                {h === 0 ? "now" : `+${h}h`}
              </Text>
            </Pressable>
          ))}
        </View>
      )}

      {apiOk === false && (
        <View style={s.offlineWrap} pointerEvents="none">
          <Text style={s.offlineTxt}>server offline — retrying</Text>
        </View>
      )}

      {/* tapped-point field readout — one chip, wordless-ish */}
      {fieldRead && !showLedger && phase !== "nav" && (
        <View style={[s.fieldWrap, phase === "compare" && { bottom: 370 }]} pointerEvents="box-none">
          <Pressable onPress={() => setFieldRead(null)} style={s.fieldChip}>
            <Text style={[s.fieldDose, NUM, { color: doseColor(fieldRead.pm25) }]}>
              {Math.round(fieldRead.pm25)} µg/m³
            </Text>
            {fieldRead.typical?.vs_now_pct != null && Math.abs(fieldRead.typical.vs_now_pct) > 8 && (
              <Text style={s.fieldMeta}>
                {fieldRead.typical.vs_now_pct > 0
                  ? `${Math.round(fieldRead.typical.vs_now_pct)}% smokier than usual`
                  : `${Math.round(-fieldRead.typical.vs_now_pct)}% cleaner than usual`}
              </Text>
            )}
            {fieldRead.pm25_lo != null && fieldRead.pm25_hi != null && (
              <Text style={s.fieldMeta}>
                honestly {Math.round(fieldRead.pm25_lo)}–{Math.round(fieldRead.pm25_hi)}
              </Text>
            )}
            {fieldRead.field?.age_s != null && (
              <Text style={s.fieldMeta}>
                updated {Math.max(1, Math.round(fieldRead.field.age_s / 60))} min ago
              </Text>
            )}
            {fieldRead.grap?.indicative_stage != null && fieldRead.grap.indicative_stage > 0 && (
              <Text style={s.grapTxt}>delhi emergency tier {fieldRead.grap.indicative_stage}</Text>
            )}
          </Pressable>
        </View>
      )}

      {/* today's dose chip — only when there's a dose to show */}
      {phase === "idle" && ledger.todayUg > 0 && (
        <Pressable style={s.doseChip} onPress={openLedger}>
          <Icon name="cigarette" color={T.ink} size={15} />
          <Text style={[s.doseChipTxt, NUM]}>{cigOf(ledger.todayUg) ?? 0} today</Text>
        </Pressable>
      )}

      {/* ============ COMPARE SHEET — modes ranked by what you'd breathe ============ */}
      {phase === "compare" && !showLedger && (
        <Sheet detent="half" onClose={clearRoute} style={s.compareSheet}>
          {loadingRoute ? (
            <View style={{ paddingVertical: 26, alignItems: "center" }}>
              <ActivityIndicator size="small" color={T.go} />
              <Text style={s.loadingTxt}>checking every way there…</Text>
            </View>
          ) : options.length > 0 ? (
            <ScrollView showsVerticalScrollIndicator={false}>
              {depart?.ug_saved_vs_now != null && depart.ug_saved_vs_now > 8 && (
                <Pressable onPress={remind} style={s.departRow}>
                  <Icon name={notified ? "bell" : "clock"} color={T.go} size={16} filled={notified} />
                  <Text style={s.departTxt}>
                    {notified ? "we'll ping you" : `leave ${hourLabel(depart.best.start, depart.best.hours_ahead)} → breathe ~${Math.round(depart.ug_saved_vs_now)}% less`}
                  </Text>
                </Pressable>
              )}
              {options.map((o, i) => (
                <ModeRow
                  key={`${o.vehicle}-${i}`}
                  vehicle={o.vehicle}
                  label={o.label}
                  etaMin={Math.round(o.duration_min)}
                  meta={`${o.distance_km} km · arrive ${arrivalLabel(o.duration_min)}${o.stations ? ` · ${o.stations.board}→${o.stations.alight}` : ""}`}
                  doseUg={o.exposure?.dose_ug ?? null}
                  best={i === 0 && (o.exposure?.dose_ug ?? 0) < worstDose}
                  selected={i === selected}
                  reason={o.decision_reasons?.[0]}
                  onPress={() => setSelected(i)}
                />
              ))}
              {/* steps / start row */}
              {sel && (
                <View style={s.startRow}>
                  <Pressable onPress={() => setStepsOpen(!stepsOpen)} style={s.stepsBtn}>
                    <Text style={s.stepsBtnTxt}>{stepsOpen ? "hide turns" : "turn-by-turn"}</Text>
                  </Pressable>
                  <Pressable onPress={startNav} style={s.goBtn}>
                    <Text style={s.goBtnTxt}>start</Text>
                  </Pressable>
                </View>
              )}
              {stepsOpen && steps && (
                <View style={s.stepsList}>
                  {sel?.vehicle === "metro" && sel.stations ? (
                    <Text style={s.stepTxt}>board at {sel.stations.board} → get off at {sel.stations.alight}</Text>
                  ) : steps.map((st, i) => (
                    <View key={i} style={s.stepRow}>
                      <View style={s.stepDot} />
                      <Text style={s.stepTxt}>{st.instruction}</Text>
                      <Text style={[s.stepDist, NUM]}>
                        {st.distance_m >= 1000 ? `${(st.distance_m / 1000).toFixed(1)} km` : `${Math.round(st.distance_m)} m`}
                      </Text>
                    </View>
                  ))}
                </View>
              )}
              {stepsOpen && sel?.vehicle !== "metro" && !steps && (
                <Text style={s.stepTxt}>driving directions appear for road modes</Text>
              )}
            </ScrollView>
          ) : (
            <Text style={s.noResults}>no routes found between those two</Text>
          )}
        </Sheet>
      )}

      {/* ============ NAV MODE — banner + live dose meter ============ */}
      {phase === "nav" && sel && (
        <>
          <View style={s.navBanner}>
            <View style={{ flex: 1 }}>
              <Text style={s.navInstr} numberOfLines={2}>
                {sel.vehicle === "metro" && sel.stations
                  ? `board ${sel.stations.board} → ${sel.stations.alight}`
                  : steps?.[0]?.instruction ?? "follow the blue line"}
              </Text>
              <Text style={[s.navMeta, NUM]}>
                {Math.round(sel.duration_min)} min · {sel.distance_km} km · arrive {arrivalLabel(sel.duration_min)}
              </Text>
            </View>
            <Pressable onPress={exitNav} hitSlop={10} style={s.navX}>
              <Icon name="close" color={T.ambientPaper} size={18} />
            </Pressable>
          </View>
          <View style={s.liveDose}>
            <Icon name="cigarette" color={T.ambientPaper} size={16} />
            <Text style={[s.liveDoseTxt, NUM]}>
              {navConc != null ? `breathing ${navConc}` : `${navDose} µg so far`}
            </Text>
            {navDose > 0 && navConc != null && (
              <Text style={[s.liveDoseSub, NUM]}>{navDose} µg inhaled</Text>
            )}
          </View>
        </>
      )}

      {/* trip receipt — the dose ledger entry for what you just breathed */}
      {receipt && phase === "compare" && (
        <View style={s.receipt}>
          <Text style={s.receiptTitle}>trip done</Text>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 10, marginTop: 4 }}>
            <CigStrip ug={receipt.doseUg} size={18} color={T.ink} />
            <Text style={[s.receiptNum, NUM]}>{Math.round(receipt.doseUg)} µg</Text>
          </View>
          {receipt.savedUg > 2 && (
            <Text style={s.receiptSub}>the smokiest way would have cost you {Math.round(receipt.savedUg)} µg more</Text>
          )}
          <Pressable onPress={() => setReceipt(null)} hitSlop={8} style={{ marginTop: 8 }}>
            <Text style={{ fontFamily: F.med, fontSize: 13, color: T.go }}>ok</Text>
          </Pressable>
        </View>
      )}

      {/* ============ PROFILE SHEET (avatar → journeys/ledger/community) ============ */}
      {profileOpen && (
        <JourneyDrawer
          week={week}
          stats={ledger}
          community={community}
          shiftCig={shiftCig}
          escape={escape}
          onAmbient={() => { setProfileOpen(false); openAmbient(); }}
          onReminders={armDailyBrief}
          onClose={() => setProfileOpen(false)}
        />
      )}

      {showLedger && (
        <LedgerSheet
          stats={ledger}
          curve={curve}
          hourNow={curveHour}
          onClose={() => setShowLedger(false)}
        />
      )}

      {ambient && (
        <AmbientMode
          pm25={fieldRead?.pm25 ?? null}
          bestHourLabel={depart?.best ? hourLabel(depart.best.start, depart.best.hours_ahead) : null}
          savedPct={depart?.ug_saved_vs_now ?? null}
          locationName={to?.name ?? from?.name ?? "Delhi NCR"}
          onExit={() => setAmbient(false)}
        />
      )}

      {introSeen === false && (
        <View style={s.intro}>
          <Text style={s.introTitle}>every trip in delhi has an air price.</Text>
          <Text style={s.introBody}>
            pick where you're going — we rank every way there by what you'd actually breathe,
            not just how fast it is. your journeys anonymously build a shared air map of the city.
          </Text>
          <Pressable onPress={dismissIntro} style={s.introBtn}>
            <Text style={s.introBtnTxt}>got it</Text>
          </Pressable>
        </View>
      )}

      {fieldRead?.grap?.indicative_stage != null && fieldRead.grap.indicative_stage >= 3 && phase === "idle" && (
        <View style={s.alertWrap}>
          <AlertBanner
            text={`delhi emergency air tier ${fieldRead.grap.indicative_stage} — prefer the metro today`}
            onClose={() => setFieldRead(null)}
          />
        </View>
      )}
    </View>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: T.paper },

  pillWrap: { position: "absolute", top: 54, left: 16, right: 16 },
  originRow: {
    flexDirection: "row", alignItems: "center", marginTop: 6,
    backgroundColor: T.surface, borderRadius: 12, paddingHorizontal: 14, paddingVertical: 8,
    borderWidth: StyleSheet.hairlineWidth, borderColor: T.hairline,
  },
  originDot: { width: 8, height: 8, borderRadius: 4, borderWidth: 2, borderColor: T.go, marginRight: 8 },
  originTxt: { flex: 1, fontFamily: F.reg, fontSize: 13, color: T.ink2 },
  originEdit: { fontFamily: F.med, fontSize: 12, color: T.go },
  searchHint: { fontFamily: F.reg, fontSize: 12, color: T.ink3, marginTop: 6, marginLeft: 6 },
  resultsSheet: {
    marginTop: 6, backgroundColor: T.surface, borderRadius: 14,
    borderWidth: StyleSheet.hairlineWidth, borderColor: T.hairline,
    shadowColor: "#000", shadowOpacity: 0.08, shadowRadius: 8, shadowOffset: { width: 0, height: 2 },
    elevation: 3, overflow: "hidden",
  },
  result: {
    flexDirection: "row", alignItems: "center",
    paddingHorizontal: 14, paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: T.hairline,
  },
  rname: { fontFamily: F.med, fontSize: 15, color: T.ink },
  rsub: { fontFamily: F.reg, fontSize: 12, color: T.ink3, marginTop: 1 },
  outsideTag: { fontFamily: F.med, fontSize: 10, color: T.ink3, marginLeft: 8 },
  noResults: { fontFamily: F.reg, fontSize: 13, color: T.ink3, padding: 16, textAlign: "center" },

  fabCol: { position: "absolute", right: 14, bottom: 190, gap: 10 },
  reportRow: {
    position: "absolute", right: 14, bottom: 246,
    backgroundColor: T.surface, borderRadius: 14, padding: 8, gap: 4,
    borderWidth: StyleSheet.hairlineWidth, borderColor: T.hairline,
    shadowColor: "#000", shadowOpacity: 0.12, shadowRadius: 10, shadowOffset: { width: 0, height: 3 },
    elevation: 5,
  },
  reportOpt: {
    width: 46, height: 46, borderRadius: 12, alignItems: "center", justifyContent: "center",
    backgroundColor: T.paper,
  },

  horizonWrap: {
    position: "absolute", top: 118, left: 16, flexDirection: "row", gap: 6,
  },
  hChip: {
    paddingHorizontal: 12, paddingVertical: 6, borderRadius: 16,
    backgroundColor: T.surface, borderWidth: StyleSheet.hairlineWidth, borderColor: T.hairline,
  },
  hChipOn: { backgroundColor: T.go, borderColor: T.go },
  hTxt: { fontFamily: F.med, fontSize: 12, color: T.ink2 },
  hTxtOn: { color: T.ambientPaper },

  offlineWrap: {
    position: "absolute", top: 108, alignSelf: "center",
    backgroundColor: T.ink, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 6,
  },
  offlineTxt: { fontFamily: F.med, fontSize: 12, color: T.ambientPaper },

  fieldWrap: { position: "absolute", bottom: 40, left: 16 },
  fieldChip: {
    backgroundColor: T.surface, borderRadius: 12, padding: 12,
    borderWidth: StyleSheet.hairlineWidth, borderColor: T.hairline,
    shadowColor: "#000", shadowOpacity: 0.1, shadowRadius: 8, shadowOffset: { width: 0, height: 2 },
    elevation: 4, maxWidth: 240,
  },
  fieldDose: { fontFamily: F.bold, fontSize: 20 },
  fieldMeta: { fontFamily: F.reg, fontSize: 11, color: T.ink2, marginTop: 3 },
  grapTxt: { fontFamily: F.med, fontSize: 11, color: T.doseSevere, marginTop: 4 },

  doseChip: {
    position: "absolute", bottom: 40, left: 16,
    flexDirection: "row", alignItems: "center", gap: 6,
    backgroundColor: T.surface, borderRadius: 20, paddingHorizontal: 12, paddingVertical: 8,
    borderWidth: StyleSheet.hairlineWidth, borderColor: T.hairline,
    shadowColor: "#000", shadowOpacity: 0.1, shadowRadius: 8, shadowOffset: { width: 0, height: 2 },
    elevation: 4,
  },
  doseChipTxt: { fontFamily: F.med, fontSize: 13, color: T.ink },

  compareSheet: { position: "absolute", bottom: 0, left: 0, right: 0 },
  loadingTxt: { fontFamily: F.reg, fontSize: 13, color: T.ink3, marginTop: 8 },
  departRow: {
    flexDirection: "row", alignItems: "center", gap: 8,
    marginHorizontal: 16, marginTop: 6, marginBottom: 2,
    paddingHorizontal: 12, paddingVertical: 8, borderRadius: 10,
    backgroundColor: T.goSoft,
  },
  departTxt: { fontFamily: F.med, fontSize: 13, color: T.go },
  startRow: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingHorizontal: 16, paddingVertical: 10,
  },
  stepsBtn: { paddingVertical: 8, paddingHorizontal: 14 },
  stepsBtnTxt: { fontFamily: F.med, fontSize: 14, color: T.ink2 },
  goBtn: {
    backgroundColor: T.go, borderRadius: 22, paddingHorizontal: 34, paddingVertical: 11,
  },
  goBtnTxt: { fontFamily: F.semi, fontSize: 16, color: T.ambientPaper },
  stepsList: { paddingHorizontal: 16, paddingBottom: 10 },
  stepRow: { flexDirection: "row", alignItems: "flex-start", paddingVertical: 5, gap: 10 },
  stepDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: T.go, marginTop: 5 },
  stepTxt: { flex: 1, fontFamily: F.reg, fontSize: 14, color: T.ink, paddingHorizontal: 0, paddingBottom: 4 },
  stepDist: { fontFamily: F.reg, fontSize: 12, color: T.ink3 },

  navBanner: {
    position: "absolute", top: 50, left: 12, right: 12,
    flexDirection: "row", alignItems: "center",
    backgroundColor: T.ink, borderRadius: 16, padding: 14,
    shadowColor: "#000", shadowOpacity: 0.25, shadowRadius: 12, shadowOffset: { width: 0, height: 4 },
    elevation: 8,
  },
  navInstr: { fontFamily: F.semi, fontSize: 17, color: T.ambientPaper },
  navMeta: { fontFamily: F.reg, fontSize: 12, color: T.ink3, marginTop: 3 },
  navX: { marginLeft: 10, padding: 6 },
  liveDose: {
    position: "absolute", bottom: 44, left: 16,
    flexDirection: "row", alignItems: "center", gap: 7,
    backgroundColor: T.ink, borderRadius: 22, paddingHorizontal: 14, paddingVertical: 10,
    shadowColor: "#000", shadowOpacity: 0.2, shadowRadius: 8, shadowOffset: { width: 0, height: 3 },
    elevation: 6,
  },
  liveDoseTxt: { fontFamily: F.med, fontSize: 14, color: T.ambientPaper },
  liveDoseSub: { fontFamily: F.reg, fontSize: 11, color: T.ink3 },

  receipt: {
    position: "absolute", top: 110, alignSelf: "center",
    backgroundColor: T.surface, borderRadius: 16, padding: 16,
    borderWidth: StyleSheet.hairlineWidth, borderColor: T.hairline,
    shadowColor: "#000", shadowOpacity: 0.15, shadowRadius: 14, shadowOffset: { width: 0, height: 4 },
    elevation: 8, minWidth: 220,
  },
  receiptTitle: { fontFamily: F.semi, fontSize: 15, color: T.ink },
  receiptNum: { fontFamily: F.bold, fontSize: 22, color: T.ink },
  receiptSub: { fontFamily: F.reg, fontSize: 12, color: T.ink2, marginTop: 4, maxWidth: 240 },

  intro: {
    position: "absolute", top: 0, bottom: 0, left: 0, right: 0,
    backgroundColor: "rgba(28,25,23,0.55)", alignItems: "center", justifyContent: "center", padding: 32,
  },
  introTitle: { fontFamily: F.bold, fontSize: 26, color: T.ambientPaper, textAlign: "center" },
  introBody: {
    fontFamily: F.reg, fontSize: 15, color: "#d6d3d1", textAlign: "center",
    marginTop: 14, lineHeight: 22,
  },
  introBtn: {
    marginTop: 26, backgroundColor: T.ambientPaper, borderRadius: 24,
    paddingHorizontal: 30, paddingVertical: 12,
  },
  introBtnTxt: { fontFamily: F.semi, fontSize: 16, color: T.ink },

  alertWrap: { position: "absolute", bottom: 40, left: 16, right: 16 },
});
