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
import { BlurView } from "expo-blur";
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
import { F, T, doseColor } from "./src/theme";
import { AmbientMode } from "./src/components/AmbientMode";
import { FieldLayer } from "./src/components/FieldLayer";
import { LedgerSheet } from "./src/components/LedgerSheet";
import { JourneyDrawer } from "./src/components/JourneyDrawer";
import { ReportsLayer } from "./src/components/ReportsLayer";
import { loadTrips, logTrip, stats as ledgerStats, weekStats } from "./src/store/ledger";
import { observeTrip, postReport, type CommunityTotals, type ReportKind } from "./src/community";
import { requestPerms, scheduleDeparture } from "./src/notify";

SplashScreen.preventAutoHideAsync().catch(() => {});

const API =
  process.env.EXPO_PUBLIC_API_URL ??
  Platform.select({
    android: "http://10.0.2.2:8000",
    default: "http://localhost:8000",
  });

const STYLE_URL = "https://tiles.openfreemap.org/styles/liberty";
const DELHI: [number, number] = [77.209, 28.6139];

type Place = { name: string; subtitle: string; lat: number; lon: number };
type Which = "from" | "to";
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
  pm10?: number | null;
  nearest_sample_km?: number;
  typical?: { median: number; vs_now_pct: number | null } | null;
  wind?: { speed_kmh: number; from_deg: number; factor: number } | null;
  grap?: { indicative_stage: number | null; basis_pm25: number | null } | null;
  field?: { age_s: number | null } | null;
  lat: number;
  lon: number;
};

// the liberty basemap ships a few vector tiles MLRN can't parse — a
// native "Invalid geometry in line layer" console warning that only
// surfaces as a dev toast (release builds never show it). Nothing in
// our layers is involved; silence exactly that message.
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

/* Vehicle icons drawn with views — stroke style, no emoji, no assets. */

function _wheels(color: string, gap: number, y: number) {
  return (
    <>
      <View style={{ position: "absolute", bottom: y, left: gap, width: 4, height: 4, borderRadius: 2, backgroundColor: color }} />
      <View style={{ position: "absolute", bottom: y, right: gap, width: 4, height: 4, borderRadius: 2, backgroundColor: color }} />
    </>
  );
}

function ModeIcon({ vehicle, color, size = 22 }: { vehicle: string; color: string; size?: number }) {
  const k = (vehicle || "").toLowerCase();
  const bw = 1.4;
  let body: React.ReactNode;
  if (k.includes("walk")) {
    body = (
      <View style={{ width: 16, height: 20, alignItems: "center" }}>
        <View style={{ width: 5, height: 5, borderRadius: 2.5, backgroundColor: color }} />
        <View style={{ width: bw, height: 7, backgroundColor: color, marginTop: 1 }} />
        <View style={{ flexDirection: "row", gap: 2 }}>
          <View style={{ width: bw, height: 6, backgroundColor: color, transform: [{ rotate: "18deg" }] }} />
          <View style={{ width: bw, height: 6, backgroundColor: color, transform: [{ rotate: "-18deg" }] }} />
        </View>
      </View>
    );
  } else if (k.includes("cycle") || k.includes("bicycle")) {
    body = (
      <View style={{ width: 22, height: 16, flexDirection: "row", justifyContent: "space-between", alignItems: "flex-end" }}>
        <View style={{ width: 9, height: 9, borderRadius: 5, borderWidth: bw, borderColor: color }} />
        <View style={{ position: "absolute", left: 7, top: 3, width: 8, height: 8, borderLeftWidth: bw, borderTopWidth: bw, borderColor: color, transform: [{ rotate: "-30deg" }] }} />
        <View style={{ width: 9, height: 9, borderRadius: 5, borderWidth: bw, borderColor: color }} />
      </View>
    );
  } else if (k.includes("bike") || k.includes("scooter") || k.includes("two_wheeler")) {
    body = (
      <View style={{ width: 22, height: 14, justifyContent: "flex-end" }}>
        <View style={{ position: "absolute", top: 0, left: 8, width: 6, height: 5, borderWidth: bw, borderColor: color, borderRadius: 2 }} />
        <View style={{ position: "absolute", top: 4, left: 10, width: 8, height: 1.6, backgroundColor: color, transform: [{ rotate: "-25deg" }] }} />
        <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
          <View style={{ width: 7, height: 7, borderRadius: 4, borderWidth: bw, borderColor: color }} />
          <View style={{ width: 7, height: 7, borderRadius: 4, borderWidth: bw, borderColor: color }} />
        </View>
      </View>
    );
  } else if (k.includes("bus")) {
    body = (
      <View style={{ width: 15, height: 18, alignItems: "center" }}>
        <View style={{ width: 15, height: 15, borderWidth: bw, borderColor: color, borderRadius: 3 }}>
          <View style={{ height: 5, borderBottomWidth: bw, borderColor: color }} />
          <View style={{ flexDirection: "row", justifyContent: "center", gap: 5, marginTop: 4 }}>
            <View style={{ width: 3, height: 3, borderRadius: 1.5, backgroundColor: color }} />
            <View style={{ width: 3, height: 3, borderRadius: 1.5, backgroundColor: color }} />
          </View>
        </View>
        {_wheels(color, 2, -2.5)}
      </View>
    );
  } else if (k.includes("metro")) {
    body = (
      <View style={{ width: 16, height: 18, alignItems: "center" }}>
        <View style={{ width: 14, height: 13, borderWidth: bw, borderColor: color, borderRadius: 4 }}>
          <View style={{ height: 4, borderBottomWidth: bw, borderColor: color }} />
        </View>
        <View style={{ flexDirection: "row", gap: 4, marginTop: 2 }}>
          <View style={{ width: 6, height: bw, backgroundColor: color, transform: [{ rotate: "25deg" }] }} />
          <View style={{ width: 6, height: bw, backgroundColor: color, transform: [{ rotate: "-25deg" }] }} />
        </View>
      </View>
    );
  } else if (k.includes("auto") || k.includes("rickshaw")) {
    body = (
      <View style={{ width: 18, height: 15, alignItems: "center" }}>
        <View style={{ width: 13, height: 6, borderWidth: bw, borderColor: color, borderTopLeftRadius: 5, borderTopRightRadius: 5 }} />
        <View style={{ width: 17, height: 6, borderWidth: bw, borderColor: color, borderRadius: 2, marginTop: -1 }} />
        {_wheels(color, 3, -3)}
      </View>
    );
  } else {
    // car (default) — rounded body + cabin + wheels
    body = (
      <View style={{ width: 21, height: 14, alignItems: "center", justifyContent: "flex-end" }}>
        <View style={{ width: 11, height: 5, borderWidth: bw, borderColor: color, borderTopLeftRadius: 4, borderTopRightRadius: 4, marginBottom: -1 }} />
        <View style={{ width: 21, height: 8, borderWidth: bw, borderColor: color, borderRadius: 3 }} />
        {_wheels(color, 3, -3.5)}
      </View>
    );
  }
  return (
    <View style={{ width: size + 8, height: size, alignItems: "center", justifyContent: "center" }}>
      {body}
    </View>
  );
}

/** Smoke meter — 5 ascending bars, filled by how much you'd breathe. */
function SmokeMeter({ level, color }: { level: number; color: string }) {
  return (
    <View style={{ flexDirection: "row", alignItems: "flex-end", gap: 1.5, height: 14 }}>
      {[0, 1, 2, 3, 4].map((i) => (
        <View key={i} style={{
          width: 3.2, height: 3 + i * 2.6, borderRadius: 1,
          backgroundColor: i < level ? color : "rgba(87,83,78,0.18)",
        }} />
      ))}
    </View>
  );
}

/** Google-Maps-style teardrop pin. */
function Pin({ letter, color }: { letter: string; color: string }) {
  return (
    <View style={{ alignItems: "center" }}>
      <View style={{
        width: 26, height: 26, borderRadius: 13, backgroundColor: color,
        borderWidth: 2, borderColor: "#fff", alignItems: "center", justifyContent: "center",
        shadowColor: "#000", shadowOpacity: 0.25, shadowRadius: 4, shadowOffset: { width: 0, height: 2 },
      }}>
        <Text style={{ fontFamily: F.bold, fontSize: 12, color: "#fff" }}>{letter}</Text>
      </View>
      <View style={{
        width: 0, height: 0, marginTop: -1,
        borderLeftWidth: 5, borderRightWidth: 5, borderTopWidth: 8,
        borderLeftColor: "transparent", borderRightColor: "transparent",
        borderTopColor: color,
      }} />
    </View>
  );
}

const VEHICLE_PROFILE: Record<string, string> = {
  cycle: "cycling", walk: "walking",
};

export default function App() {
  const camRef = useRef<CameraRef>(null);
  const [from, setFrom] = useState<Place | null>(null);
  const [to, setTo] = useState<Place | null>(null);
  const [fromText, setFromText] = useState("");
  const [toText, setToText] = useState("");
  const [active, setActive] = useState<Which | null>(null);
  const [listFor, setListFor] = useState<Which | null>(null);
  const [results, setResults] = useState<Place[]>([]);
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
  const [drawerOpen, setDrawerOpen] = useState(false);
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
  const [cardH, setCardH] = useState(0);
  const [steps, setSteps] = useState<Step[] | null>(null);
  const [nav, setNav] = useState(false);
  const debounce = useRef<ReturnType<typeof setTimeout> | null>(null);
  const searchSeq = useRef(0);

  const [fontsLoaded] = useFonts({
    Outfit_300Light, Outfit_400Regular, Outfit_500Medium,
    Outfit_600SemiBold, Outfit_700Bold,
  });
  useEffect(() => {
    if (fontsLoaded) SplashScreen.hideAsync().catch(() => {});
  }, [fontsLoaded]);

  useEffect(() => {
    fetch(`${API}/health`).then((r) => setApiOk(r.ok)).catch(() => setApiOk(false));
    fetch(`${API}/grid`).then((r) => r.json()).then(setGrid).catch(() => {});
    fetch(`${API}/community`).then((r) => r.json()).then(setCommunity).catch(() => {});
    fetch(`${API}/shift?lat=28.6139&lon=77.2090&hours=8&vehicle=driving_two_wheeler`)
      .then((r) => r.json()).then((j) => setShiftCig(j.cig_equiv ?? null)).catch(() => {});
    (async () => {
      const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced }).catch(() => null);
      const lat = pos?.coords.latitude ?? DELHI[1];
      const lon = pos?.coords.longitude ?? DELHI[0];
      const r = await fetch(`${API}/escape?lat=${lat}&lon=${lon}&limit=3`).then((x) => x.json()).catch(() => null);
      setEscape(r?.best?.[0] ?? null);
    })();
    const poll = () => fetch(`${API}/reports`).then((r) => r.json()).then(setReports).catch(() => {});
    poll();
    const iv = setInterval(poll, 60000);
    loadTrips().then((t) => { setTrips(t); setLedger(ledgerStats(t)); }).catch(() => {});
    Location.requestForegroundPermissionsAsync().then((r) => setHasLoc(r.granted)).catch(() => {});
    setIntroSeen(new File(Paths.document, "intro_seen.txt").exists);
    return () => clearInterval(iv);
  }, []);

  const dismissIntro = useCallback(() => {
    setIntroSeen(true);
    try { new File(Paths.document, "intro_seen.txt").write("1"); } catch {}
  }, []);

  const useMyLocation = useCallback(async () => {
    try {
      const r = await Location.requestForegroundPermissionsAsync();
      if (!r.granted) return;
      const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
      const { latitude, longitude } = pos.coords;
      let name = "my location";
      try {
        const rr = await fetch(`${API}/reverse?lat=${latitude}&lon=${longitude}`);
        const j = await rr.json();
        if (j.name) name = j.name;
      } catch {}
      setFrom({ name, subtitle: "", lat: latitude, lon: longitude });
      setFromText(name);
      setActive(null);
      setListFor(null);
      setResults([]);
      Keyboard.dismiss();
      camRef.current?.flyTo({ center: [longitude, latitude], zoom: 14, duration: 900 });
    } catch {}
  }, []);

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
    fetch(url).then((r) => r.json()).then(setGrid).catch(() => {});
  }, []);

  const doSearch = useCallback((text: string, which: Which) => {
    if (debounce.current) clearTimeout(debounce.current);
    if (text.trim().length < 2) { setResults([]); setListFor(null); setSearching(false); return; }
    setListFor(which);
    setSearching(true);
    const seq = ++searchSeq.current;
    debounce.current = setTimeout(async () => {
      try {
        const r = await fetch(`${API}/search?q=${encodeURIComponent(text)}&limit=8`);
        const j = await r.json();
        if (seq !== searchSeq.current) return;
        setResults(j.results ?? []);
      } catch {
        if (seq === searchSeq.current) setResults([]);
      } finally {
        if (seq === searchSeq.current) setSearching(false);
      }
    }, 180);
  }, []);

  const pick = useCallback(
    (p: Place) => {
      if (listFor === "from") { setFrom(p); setFromText(p.name); }
      else if (listFor === "to") { setTo(p); setToText(p.name); }
      setActive(null);
      setListFor(null);
      setResults([]);
      Keyboard.dismiss();
      camRef.current?.flyTo({ center: [p.lon, p.lat], zoom: 14, duration: 900 });
    },
    [listFor]
  );

  const swap = useCallback(() => {
    const f = from; const ft = fromText;
    setFrom(to); setFromText(toText); setTo(f ?? null); setToText(ft);
  }, [from, to, fromText, toText]);

  useEffect(() => {
    if (!from || !to) return;
    let cancelled = false;
    setNotified(false);
    const load = async () => {
      setLoadingRoute(true);
      try {
        const qs = `from_lat=${from.lat}&from_lon=${from.lon}&to_lat=${to.lat}&to_lon=${to.lon}`;
        const [cr, dr] = await Promise.all([
          fetch(`${API}/decide?${qs}`),
          fetch(`${API}/depart?${qs}&vehicle=auto&hours=24`),
        ]);
        const [cj, dj] = await Promise.all([cr.json(), dr.json()]);
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
            { padding: { top: 240, bottom: 300, left: 60, right: 60 }, duration: 700 }
          );
          camRef.current?.setStop({ pitch: 32, duration: 900 });
        }
      } catch {
        if (!cancelled) { setOptions([]); setDepart(null); }
      } finally {
        if (!cancelled) setLoadingRoute(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [from, to]);

  // turn-by-turn steps for the selected option — the public OSRM demo
  // only computes the driving graph, so walk/cycle get no step list
  useEffect(() => {
    setSteps(null);
    const o = options[selected];
    if (!o || !from || !to) return;
    const profile = VEHICLE_PROFILE[o.vehicle] ?? "driving";
    if (profile !== "driving") return;
    fetch(
      `${API}/directions?from_lat=${from.lat}&from_lon=${from.lon}` +
        `&to_lat=${to.lat}&to_lon=${to.lon}&profile=${profile}&vehicle=${o.vehicle}`
    )
      .then((r) => r.json())
      .then((j) => { if (Array.isArray(j.steps)) setSteps(j.steps); })
      .catch(() => {});
  }, [selected, options, from, to]);

  const clearRoute = useCallback(() => {
    setFrom(null); setTo(null); setFromText(""); setToText("");
    setOptions([]); setDepart(null); setSteps(null); setNav(false); setFollow(false);
  }, []);

  const startNav = useCallback(async () => {
    const o = options[selected];
    if (!o || !from || !to) return;
    setNav(true);
    Keyboard.dismiss();
    // follow the blue dot only when the device is actually in Delhi —
    // outside NCR (sim, demo elsewhere) the route stays the subject
    const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced }).catch(() => null);
    const inNcr =
      pos &&
      pos.coords.longitude > 76.75 && pos.coords.longitude < 77.95 &&
      pos.coords.latitude > 28.15 && pos.coords.latitude < 28.98;
    setFollow(!!inNcr);
    camRef.current?.flyTo({ center: [from.lon, from.lat], zoom: 15.5, duration: 700 });
    camRef.current?.setStop({ pitch: 55, duration: 800 });
  }, [options, selected, from, to]);

  const exitNav = useCallback(() => {
    setNav(false);
    setFollow(false);
    camRef.current?.setStop({ pitch: 0, duration: 700 });
    const g = options[selected]?.geometry;
    if (g?.type === "LineString") {
      const coords = (g as GeoJSON.LineString).coordinates;
      const lons = coords.map((c) => c[0]);
      const lats = coords.map((c) => c[1]);
      camRef.current?.fitBounds(
        [Math.min(...lons), Math.min(...lats), Math.max(...lons), Math.max(...lats)],
        { padding: { top: 240, bottom: 300, left: 60, right: 60 }, duration: 700 }
      );
    }
  }, [options, selected]);

  // ledger: a picked option is a trip — deduped inside the store
  useEffect(() => {
    const o = options[selected];
    if (!o?.exposure?.dose_ug || !from || !to) return;
    const worst = Math.max(...options.map((x) => x.exposure?.dose_ug ?? 0));
    const avoided = Math.max(0, Math.round((worst - o.exposure.dose_ug) * 10) / 10);
    logTrip({
      ts: Date.now(), label: o.label, vehicle: o.vehicle,
      dose_ug: o.exposure.dose_ug,
      avoided_ug: avoided,
      from: from.name, to: to.name,
      fromLat: from.lat, fromLon: from.lon, toLat: to.lat, toLon: to.lon,
    }).then((t) => { setTrips(t); setLedger(ledgerStats(t)); }).catch(() => {});
    // donate the traversal — commuters become the sensor network
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
      }).then(() => fetch(`${API}/community`).then((r) => r.json()).then(setCommunity)).catch(() => {});
    }
  }, [selected, options, from, to]);

  const routeSegs = useMemo<GeoJSON.FeatureCollection>(() => {
    const segs = options[selected]?.segments;
    if (!segs?.length) {
      const g = options[selected]?.geometry;
      const ok =
        g &&
        ((g.type === "LineString" && (g as GeoJSON.LineString).coordinates.length >= 2) ||
          (g.type === "MultiLineString" &&
            (g as GeoJSON.MultiLineString).coordinates.every((l) => l.length >= 2)));
      return {
        type: "FeatureCollection",
        features: ok ? [{ type: "Feature", properties: { color: T.accent }, geometry: g! }] : [],
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

  // recent places — last distinct trip endpoints, newest first (like
  // Google Maps' recents under an empty search box)
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
        out.push({ name: cand.name, subtitle: "recent", lat: cand.lat, lon: cand.lon });
        if (out.length >= 6) break;
      }
    }
    return out;
  }, [trips]);

  // faint alternates — every other option's path under the selected one
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
        const r = await fetch(`${API}/today?lat=${p.lat}&lon=${p.lon}`);
        const j = await r.json();
        setCurve(j.hours_ist ?? null);
        setCurveHour(j.hour_now_ist ?? null);
      }
    } catch {}
  }, [from, to]);

  const openAmbient = useCallback(async () => {
    setAmbient(true);
    try {
      const p = to ?? from ?? { lat: DELHI[1], lon: DELHI[0] };
      const r = await fetch(`${API}/aqi?lat=${p.lat}&lon=${p.lon}`);
      const j = await r.json();
      if (j.pm25 != null)
        setFieldRead({ pm25: j.pm25, pm10: j.pm10, nearest_sample_km: j.nearest_sample_km, typical: j.typical, wind: j.wind, grap: j.grap, field: j.field, lat: p.lat, lon: p.lon });
    } catch {}
  }, [from, to]);

  const remind = useCallback(async () => {
    if (!depart?.best?.start || notified) return;
    if (!(await requestPerms())) return;
    const fire = new Date(depart.best.start.endsWith("Z") ? depart.best.start : depart.best.start + "Z");
    const id = await scheduleDeparture({ fireAt: fire, savedPct: depart.ug_saved_vs_now ?? 0 });
    if (id) setNotified(true);
  }, [depart, notified]);

  if (!fontsLoaded) return null;

  return (
    <View style={s.root}>
      <StatusBar style="dark" />
      <Map
        mapStyle={STYLE_URL}
        style={StyleSheet.absoluteFill}
        onPress={async (f) => {
          const c = f.nativeEvent.lngLat;
          if (!c) return;
          try {
            const r = await fetch(`${API}/aqi?lat=${c[1]}&lon=${c[0]}`);
            const j = await r.json();
            if (j.pm25 != null)
              setFieldRead({ pm25: j.pm25, pm10: j.pm10, nearest_sample_km: j.nearest_sample_km, typical: j.typical, wind: j.wind, grap: j.grap, field: j.field, lat: c[1], lon: c[0] });
          } catch {}
        }}
        onLongPress={async (f) => {
          const c = f.nativeEvent.lngLat;
          if (!c) return;
          let name = `${c[1].toFixed(4)}, ${c[0].toFixed(4)}`;
          try {
            const r = await fetch(`${API}/reverse?lat=${c[1]}&lon=${c[0]}`);
            const j = await r.json();
            if (j.name) name = j.name;
          } catch {}
          if (!from || !to) {
            // drop a pin to start a trip — the empty field takes it
            if (!from) { setFrom({ name, subtitle: "", lat: c[1], lon: c[0] }); setFromText(name); }
            else { setTo({ name, subtitle: "", lat: c[1], lon: c[0] }); setToText(name); }
          } else {
            setTo({ name, subtitle: "", lat: c[1], lon: c[0] });
            setToText(name);
          }
        }}
      >
        <Camera ref={camRef} initialViewState={{ center: DELHI, zoom: 11 }} maxBounds={[76.75, 28.15, 77.95, 28.98]}
          trackUserLocation={follow ? "default" : undefined}
          onTrackUserLocationChange={(e) => { if (!e.nativeEvent.trackUserLocation) setFollow(false); }} />
        {hasLoc && <UserLocation animated accuracy />}
        <FieldLayer grid={grid} />
        <ReportsLayer reports={reports} />
        <Layer
          id="buildings3d"
          type="fill-extrusion"
          source="openmaptiles"
          source-layer="building"
          minzoom={14}
          paint={{
            "fill-extrusion-color": "#e3dfd8",
            "fill-extrusion-height": ["coalesce", ["get", "render_height"], ["get", "height"], 10],
            "fill-extrusion-opacity": 0.55,
          }}
        />
        <GeoJSONSource id="alts" data={altSegs}>
          <Layer id="alts-line" type="line"
            paint={{ "line-color": "rgba(87,83,78,0.35)", "line-width": 2.5, "line-dasharray": [2, 2] }}
            layout={{ "line-cap": "round", "line-join": "round" }} />
        </GeoJSONSource>
        <GeoJSONSource id="route" data={routeSegs}>
          <Layer id="route-casing" type="line"
            paint={{ "line-color": "#ffffff", "line-width": 8, "line-opacity": 0.8 }}
            layout={{ "line-cap": "round", "line-join": "round" }} />
          <Layer id="route-line" type="line"
            paint={{ "line-color": ["get", "color"], "line-width": 4.5 }}
            layout={{ "line-cap": "round", "line-join": "round" }} />
        </GeoJSONSource>
        {from && (
          <Marker lngLat={[from.lon, from.lat]} anchor="bottom">
            <Pin letter="A" color={T.accent} />
          </Marker>
        )}
        {to && (
          <Marker lngLat={[to.lon, to.lat]} anchor="bottom">
            <Pin letter="B" color={T.doseMid} />
          </Marker>
        )}
      </Map>

      {/* search card — hidden during turn-by-turn nav */}
      {!nav && (
      <View style={s.cardWrap}>
        <BlurView intensity={45} tint="light" style={s.card}>
          <View style={s.row}>
            <Text style={s.rowGlyph}>A</Text>
            <TextInput style={s.input} placeholder="From — anywhere in Delhi NCR"
              placeholderTextColor={T.ink3} autoCorrect={false} autoCapitalize="none"
              value={fromText}
              onFocus={() => setActive("from")}
              onBlur={() => setActive(null)}
              onChangeText={(t) => { setFromText(t); setFrom(null); setOptions([]); setDepart(null); setActive("from"); doSearch(t, "from"); }}
              returnKeyType="search" clearButtonMode="while-editing" />
            {hasLoc && (
              <Pressable onPress={useMyLocation} style={s.swap} hitSlop={8}>
                <Text style={s.swapTxt}>⌖</Text>
              </Pressable>
            )}
            <Pressable onPress={swap} style={s.swap} hitSlop={8}><Text style={s.swapTxt}>⇅</Text></Pressable>
          </View>
          <View style={s.div} />
          <View style={s.row}>
            <Text style={s.rowGlyph}>B</Text>
            <TextInput style={s.input} placeholder="To — anywhere in Delhi NCR"
              placeholderTextColor={T.ink3} autoCorrect={false} autoCapitalize="none"
              value={toText}
              onFocus={() => setActive("to")}
              onBlur={() => setActive(null)}
              onChangeText={(t) => { setToText(t); setTo(null); setOptions([]); setDepart(null); setActive("to"); doSearch(t, "to"); }}
              returnKeyType="search" clearButtonMode="while-editing" />
            {searching && <ActivityIndicator size="small" color={T.ink3} />}
          </View>
        </BlurView>

        {listFor && results.length > 0 && (
          <BlurView intensity={50} tint="light" style={[s.card, { marginTop: 8 }]}>
            {results.map((p, i) => (
              <Pressable key={`${p.lat},${p.lon},${i}`} onPress={() => pick(p)}
                style={({ pressed }) => [s.result, pressed && { opacity: 0.55 }]}>
                <View style={{ flex: 1 }}>
                  <Text style={s.rname} numberOfLines={1}>{p.name}</Text>
                  {!!p.subtitle && <Text style={s.rsub} numberOfLines={1}>{p.subtitle}</Text>}
                </View>
              </Pressable>
            ))}
          </BlurView>
        )}
        {listFor && results.length === 0 && recents.length > 0 &&
          !(listFor === "from" ? fromText : toText) && (
          <BlurView intensity={50} tint="light" style={[s.card, { marginTop: 8 }]}>
            {recents.map((p, i) => (
              <Pressable key={`r${p.lat},${p.lon},${i}`} onPress={() => pick(p)}
                style={({ pressed }) => [s.result, pressed && { opacity: 0.55 }]}>
                <View style={{ flex: 1 }}>
                  <Text style={s.rname} numberOfLines={1}>{p.name}</Text>
                  <Text style={s.rsub}>recent</Text>
                </View>
              </Pressable>
            ))}
          </BlurView>
        )}
      </View>
      )}

      {/* horizon scrubber — now / +6h / +12h / +24h; hidden while a field is focused */}
      {!active && !nav && (
      <View style={s.horizonWrap}>
        {HORIZONS.map((h) => (
          <Pressable key={h} onPress={() => scrubField(h)}
            style={({ pressed }) => [s.hChip, horizonH === h && s.hChipOn, pressed && s.chipPressed]}>
            <Text style={[s.hTxt, horizonH === h && s.hTxtOn]}>
              {h === 0 ? "now" : `+${h}h`}
            </Text>
          </Pressable>
        ))}
      </View>
      )}

      {/* top-right: journey drawer, ledger, ambient */}
      {!active && !nav && (
      <View style={s.topRight}>
        <Pressable onPress={() => setDrawerOpen(true)} style={({ pressed }) => [s.aodBtn, pressed && s.chipPressed]} hitSlop={10}>
          <Text style={s.aodGlyph}>☰</Text>
        </Pressable>
        <Pressable onPress={openLedger} style={({ pressed }) => [s.todayPill, pressed && s.chipPressed]}>
          <Text style={s.todayTxt}>
            today {ledger.todayUg > 0 ? `${ledger.todayUg} µg` : "0 µg"}
          </Text>
        </Pressable>
        <Pressable onPress={openAmbient} style={({ pressed }) => [s.aodBtn, pressed && s.chipPressed]} hitSlop={10}>
          <View style={s.aodCrescent}><View style={s.aodHalf} /></View>
        </Pressable>
      </View>
      )}

      {apiOk === false && (
        <View style={s.offlineWrap} pointerEvents="none">
          <Text style={s.offlineTxt}>server offline</Text>
        </View>
      )}

      {/* action column: recenter + air report — rendered AFTER the dose
          card and anchored just above its measured height so the card
          can never swallow the buttons */}
      {!active && !drawerOpen && !nav && (
        <View style={[s.fabCol, { bottom: Math.max(cardH + 44, 300) }]}>
          {hasLoc && (
            <Pressable style={({ pressed }) => [s.fab, follow && s.fabOn, pressed && s.chipPressed]} onPress={() => setFollow(!follow)}>
              <Text style={[s.fabGlyph, follow && s.fabGlyphOn]}>⌖</Text>
            </Pressable>
          )}
          <Pressable style={({ pressed }) => [s.fab, pressed && s.chipPressed]} onPress={() => setReportMode(!reportMode)}>
            <Text style={s.fabGlyph}>◍</Text>
          </Pressable>
        </View>
      )}

      {reportMode && (
        <View style={[s.reportCard, { bottom: Math.max(cardH + 44, 300) }]}>
          <Text style={s.reportTitle}>report the air where you are</Text>
          <View style={s.reportRow}>
            {(["dust", "smoke", "burning", "clean"] as ReportKind[]).map((k) => (
              <Pressable key={k} style={({ pressed }) => [s.reportOpt, pressed && s.chipPressed]} onPress={() => sendReport(k)}>
                <Text style={s.reportOptTxt}>{k === "clean" ? "clean air" : k}</Text>
              </Pressable>
            ))}
          </View>
          <Pressable onPress={() => setReportMode(false)}>
            <Text style={s.reportCancel}>cancel</Text>
          </Pressable>
        </View>
      )}

      {/* tapped-point field readout */}
      {fieldRead && !showLedger && (
        <View style={[s.fieldWrap, options.length > 0 && { bottom: 480 }]} pointerEvents="box-none">
          <Pressable onPress={() => setFieldRead(null)} style={s.fieldChip}>
            <Text style={[s.fieldDose, { color: doseColor(fieldRead.pm25) }]}>
              {Math.round(fieldRead.pm25)} µg/m³
            </Text>
            <Text style={s.fieldMeta}>
              PM2.5 here
              {fieldRead.nearest_sample_km != null ? ` · nearest sample ${fieldRead.nearest_sample_km} km` : ""}
            </Text>
            {fieldRead.typical?.median != null && (
              <Text style={s.fieldMeta}>
                decade median {Math.round(fieldRead.typical.median)} µg/m³ this month·hour
                {fieldRead.typical.vs_now_pct != null
                  ? ` · now ${fieldRead.typical.vs_now_pct > 0 ? "+" : ""}${Math.round(fieldRead.typical.vs_now_pct)}%`
                  : ""}
              </Text>
            )}
            {fieldRead.wind && fieldRead.wind.speed_kmh > 0 && (
              <Text style={s.fieldMeta}>
                air arrives from {windFrom(fieldRead.wind.from_deg)} · {Math.round(fieldRead.wind.speed_kmh)} km/h
              </Text>
            )}
            {fieldRead.field?.age_s != null && (
              <Text style={s.fieldMeta}>
                field updated {Math.max(1, Math.round(fieldRead.field.age_s / 60))} min ago
              </Text>
            )}
            {fieldRead.grap?.indicative_stage != null && fieldRead.grap.indicative_stage > 0 && (
              <Text style={s.grapTxt}>
                GRAP-{fieldRead.grap.indicative_stage} air (indicative)
              </Text>
            )}
          </Pressable>
        </View>
      )}

      {/* ways-to-go bottom sheet — Google-Maps grade */}
      {from && to && !nav && (
        <View style={s.bottomWrap}
          onLayout={(e) => setCardH(e.nativeEvent.layout.height)}>
          <BlurView intensity={55} tint="light" style={s.summary}>
            {loadingRoute ? (
              <ActivityIndicator size="small" color={T.accent} style={{ marginVertical: 14 }} />
            ) : options.length > 0 ? (
              <View>
                <View style={s.sheetHead}>
                  <Text style={s.sheetTitle}>ways to go</Text>
                  <Pressable onPress={clearRoute} hitSlop={10}
                    style={({ pressed }) => [s.sheetX, pressed && { opacity: 0.5 }]}>
                    <Text style={s.sheetXTxt}>✕</Text>
                  </Pressable>
                </View>
                <ScrollView style={{ maxHeight: 300 }} showsVerticalScrollIndicator={false}>
                  {options.map((o, i) => {
                    const conc = o.exposure?.avg_conc_ugm3 ?? 0;
                    const c = doseColor(conc);
                    const meter = conc <= 0 ? 0 : Math.max(1, Math.min(5, Math.round(conc / 60) + 1));
                    const sel = i === selected;
                    return (
                      <View key={`${o.vehicle}-${i}`}>
                        <Pressable onPress={() => setSelected(i)}
                          style={({ pressed }) => [s.optRow, sel && s.optRowSel, pressed && s.chipPressed]}>
                          <ModeIcon vehicle={o.vehicle} color={sel ? T.accent : T.ink2} />
                          <View style={{ flex: 1, marginLeft: 10 }}>
                            <Text style={s.optLabel}>
                              {o.label}
                              {i === 0 ? <Text style={s.bestTag}>  cleanest ride</Text> : null}
                            </Text>
                            {o.decision_reasons?.length ? (
                              <Text style={s.optReason} numberOfLines={1}>{o.decision_reasons[0]}</Text>
                            ) : null}
                            {o.stations ? (
                              <Text style={s.optMeta} numberOfLines={1}>{o.stations.board} → {o.stations.alight}</Text>
                            ) : null}
                          </View>
                          <View style={{ alignItems: "flex-end", marginRight: 10 }}>
                            <Text style={s.optEta}>{o.duration_min} min</Text>
                            <Text style={s.optMeta}>{o.distance_km} km · {arrivalLabel(o.duration_min)}</Text>
                          </View>
                          <View style={{ alignItems: "flex-end", width: 44 }}>
                            <SmokeMeter level={meter} color={c} />
                            <Text style={[s.optDose, { color: c }]}>
                              {o.exposure?.dose_ug != null ? `${o.exposure.dose_ug}` : "—"}
                            </Text>
                            <Text style={s.optMeta}>µg</Text>
                          </View>
                        </Pressable>
                        {sel && steps && steps.length > 0 && (
                          <View style={s.stepsBox}>
                            {steps.map((st, si) => (
                              <View key={si} style={s.stepRow}>
                                <View style={s.stepDot} />
                                <Text style={s.stepTxt} numberOfLines={2}>
                                  {st.instruction}
                                  {st.distance_m >= 40 && st.type !== "arrive"
                                    ? <Text style={s.stepDist}>  {st.distance_m >= 1000 ? `${(st.distance_m / 1000).toFixed(1)} km` : `${Math.round(st.distance_m / 10) * 10} m`}</Text>
                                    : null}
                                </Text>
                              </View>
                            ))}
                          </View>
                        )}
                      </View>
                    );
                  })}
                </ScrollView>
                {depart?.ug_saved_vs_now != null && depart.ug_saved_vs_now > 10 && (
                  <View style={s.departRow}>
                    <Text style={s.departHint}>
                      leave {hourLabel(depart.best.start, depart.best.hours_ahead)} — same trip, {depart.ug_saved_vs_now}% less smoke
                    </Text>
                    <Pressable onPress={remind} hitSlop={6}>
                      <Text style={s.remindTxt}>{notified ? "set ✓" : "remind me"}</Text>
                    </Pressable>
                  </View>
                )}
                <Pressable onPress={startNav}
                  style={({ pressed }) => [s.startBtn, pressed && { opacity: 0.85 }]}>
                  <Text style={s.startTxt}>start</Text>
                </Pressable>
                <Text style={s.sheetFoot}>
                  smoke bars show how much you'd actually breathe — measured live across Delhi
                </Text>
              </View>
            ) : (
              <Text style={s.summarySub}>no way found — try another spot</Text>
            )}
          </BlurView>
        </View>
      )}

      {/* nav mode — maneuver banner + slim ETA bar */}
      {nav && options[selected] && (
        <>
          <View style={s.navBanner} pointerEvents="none">
            <BlurView intensity={55} tint="light" style={s.navBannerIn}>
              <Text style={s.navStep} numberOfLines={2}>
                {steps?.find((st) => st.type !== "depart")?.instruction ?? "follow the route"}
              </Text>
              <Text style={s.navSub}>
                {from?.name ?? ""} → {to?.name ?? ""}
              </Text>
            </BlurView>
          </View>
          <View style={s.navBar}>
            <BlurView intensity={55} tint="light" style={s.navBarIn}>
              <View>
                <Text style={s.navEta}>{options[selected].duration_min} min</Text>
                <Text style={s.navSub}>
                  {options[selected].distance_km} km · arrive {arrivalLabel(options[selected].duration_min)}
                </Text>
              </View>
              <Pressable onPress={exitNav}
                style={({ pressed }) => [s.navExit, pressed && { opacity: 0.7 }]}>
                <Text style={s.navExitTxt}>exit</Text>
              </Pressable>
            </BlurView>
          </View>
        </>
      )}

      {showLedger && (
        <LedgerSheet stats={ledger} curve={curve} hourNow={curveHour}
          onClose={() => setShowLedger(false)} />
      )}

      {drawerOpen && (
        <JourneyDrawer week={weekStats(trips)} stats={ledger}
          community={community} shiftCig={shiftCig} escape={escape}
          onClose={() => setDrawerOpen(false)} />
      )}

      {introSeen === false && (
        <Pressable style={s.introScrim} onPress={dismissIntro}>
          <View style={s.introCard}>
            <Text style={s.introTitle}>ALive-108</Text>
            <Text style={s.introBody}>
              every trip in Delhi has an air price. we show it —
              pick any two places, see exactly what you'd breathe
              in a car, auto, metro or on foot.{"\n\n"}
              your journeys also build a shared air map made by
              people like you — covering streets no station
              can see. that's how Delhi starts breathing easier.
            </Text>
            <Text style={s.introCta}>tap anywhere to start</Text>
          </View>
        </Pressable>
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
    </View>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: T.paper },
  cardWrap: { position: "absolute", top: Platform.select({ ios: 58, android: 38 }), left: 16, right: 16 },
  card: {
    borderRadius: 22, overflow: "hidden", backgroundColor: T.glass,
    borderWidth: 1, borderColor: T.glassBorder,
  },
  row: { flexDirection: "row", alignItems: "center", paddingHorizontal: 16, paddingVertical: 13 },
  rowGlyph: { fontFamily: F.semi, fontSize: 13, color: T.accent, width: 18 },
  input: { flex: 1, fontFamily: F.med, fontSize: 16, color: T.ink, padding: 0 },
  swap: { marginLeft: 8, padding: 4 },
  swapTxt: { fontSize: 17, color: T.ink3, fontFamily: F.reg },
  div: { height: StyleSheet.hairlineWidth, backgroundColor: T.glassBorder, marginHorizontal: 16 },
  result: { paddingHorizontal: 16, paddingVertical: 11 },
  rname: { fontFamily: F.semi, fontSize: 15, color: T.ink },
  rsub: { fontFamily: F.reg, fontSize: 12, color: T.ink2, marginTop: 1 },
  topRight: {
    position: "absolute", top: Platform.select({ ios: 162, android: 142 }), right: 16,
    flexDirection: "row", alignItems: "center", gap: 10,
  },
  horizonWrap: {
    position: "absolute", top: Platform.select({ ios: 162, android: 142 }), left: 16,
    flexDirection: "row", gap: 6,
  },
  hChip: {
    backgroundColor: T.glass, borderRadius: 999, paddingHorizontal: 11, paddingVertical: 6,
    borderWidth: 1, borderColor: T.glassBorder,
  },
  hChipOn: { backgroundColor: T.accentSoft, borderColor: T.accent },
  hTxt: { fontFamily: F.med, fontSize: 11.5, color: T.ink2 },
  hTxtOn: { color: T.accent },
  chipPressed: { backgroundColor: "rgba(15,118,110,0.18)", transform: [{ scale: 0.96 }] },
  todayPill: {
    backgroundColor: T.glass, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 7,
    borderWidth: 1, borderColor: T.glassBorder,
  },
  todayTxt: { fontFamily: F.semi, fontSize: 12, color: T.ink },
  aodBtn: {
    width: 34, height: 34, borderRadius: 17, backgroundColor: T.glass,
    borderWidth: 1, borderColor: T.glassBorder, alignItems: "center", justifyContent: "center",
  },
  aodCrescent: {
    width: 14, height: 14, borderRadius: 7, borderWidth: 1.5, borderColor: T.ink,
    overflow: "hidden",
  },
  aodHalf: { position: "absolute", right: 0, top: 0, bottom: 0, width: 7, backgroundColor: T.ink },
  offlineWrap: { position: "absolute", top: Platform.select({ ios: 162, android: 142 }), alignSelf: "center" },
  offlineTxt: { fontFamily: F.med, fontSize: 12, color: T.doseMid },
  fabCol: { position: "absolute", right: 16, bottom: 300, gap: 10 },
  fab: {
    width: 42, height: 42, borderRadius: 21, backgroundColor: T.glass,
    borderWidth: 1, borderColor: T.glassBorder, alignItems: "center", justifyContent: "center",
    shadowColor: "#000", shadowOpacity: 0.10, shadowRadius: 8, shadowOffset: { width: 0, height: 3 },
  },
  fabOn: { backgroundColor: T.accentSoft, borderColor: T.accent },
  fabGlyph: { fontSize: 17, color: T.ink2, fontFamily: F.med },
  fabGlyphOn: { color: T.accent },
  aodGlyph: { fontSize: 15, color: T.ink, fontFamily: F.med },
  reportCard: {
    position: "absolute", bottom: 300, alignSelf: "center", width: 280,
    backgroundColor: T.glass, borderRadius: 18, padding: 14,
    borderWidth: 1, borderColor: T.glassBorder,
    shadowColor: "#000", shadowOpacity: 0.10, shadowRadius: 14, shadowOffset: { width: 0, height: 4 },
  },
  reportTitle: { fontFamily: F.semi, fontSize: 13, color: T.ink, textAlign: "center" },
  reportRow: { flexDirection: "row", gap: 8, marginTop: 12 },
  reportOpt: {
    flex: 1, backgroundColor: T.accentSoft, borderRadius: 12, paddingVertical: 10,
    alignItems: "center", borderWidth: 1, borderColor: "rgba(15,118,110,0.25)",
  },
  reportOptTxt: { fontFamily: F.semi, fontSize: 12, color: T.accent },
  reportCancel: { fontFamily: F.med, fontSize: 12, color: T.ink3, textAlign: "center", marginTop: 10 },
  fieldWrap: { position: "absolute", bottom: 300, alignSelf: "center" },
  fieldChip: {
    alignItems: "center", backgroundColor: T.glass, paddingHorizontal: 18, paddingVertical: 10,
    borderRadius: 18, borderWidth: 1, borderColor: T.glassBorder,
    shadowColor: "#000", shadowOpacity: 0.10, shadowRadius: 14, shadowOffset: { width: 0, height: 4 },
  },
  fieldDose: { fontFamily: F.semi, fontSize: 20, fontVariant: ["tabular-nums"] },
  fieldMeta: { fontFamily: F.reg, fontSize: 11, color: T.ink2, marginTop: 2 },
  grapTxt: { fontFamily: F.semi, fontSize: 11, color: T.doseMid, marginTop: 4, letterSpacing: 0.4 },
  bottomWrap: { position: "absolute", bottom: 30, left: 16, right: 16 },
  summary: {
    borderRadius: 22, overflow: "hidden", backgroundColor: T.glass,
    borderWidth: 1, borderColor: T.glassBorder, paddingVertical: 14, paddingHorizontal: 14,
    shadowColor: "#000", shadowOpacity: 0.12, shadowRadius: 18, shadowOffset: { width: 0, height: 8 },
  },
  optRow: { flexDirection: "row", alignItems: "center", paddingVertical: 8, paddingHorizontal: 10, borderRadius: 14 },
  optRowSel: { backgroundColor: T.accentSoft },
  optLabel: { fontFamily: F.semi, fontSize: 14, color: T.ink },
  bestTag: { fontFamily: F.med, fontSize: 11, color: T.accent },
  optMeta: { fontFamily: F.reg, fontSize: 11, color: T.ink2, marginTop: 1 },
  optReason: { fontFamily: F.med, fontSize: 10.5, color: T.accent, marginTop: 1 },
  optDose: { fontFamily: F.bold, fontSize: 16, fontVariant: ["tabular-nums"] },
  departRow: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    marginTop: 8, paddingTop: 9, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: T.glassBorder,
  },
  departHint: { fontFamily: F.semi, fontSize: 12.5, color: T.accent, flex: 1 },
  remindTxt: { fontFamily: F.med, fontSize: 12, color: T.ink2, paddingLeft: 10 },
  summarySub: { fontFamily: F.reg, fontSize: 11.5, color: T.ink3, marginTop: 9, textAlign: "center" },
  arriveTxt: { fontFamily: F.reg, fontSize: 11, color: T.ink3, marginTop: 8, textAlign: "center" },
  sheetHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 12, paddingTop: 4, paddingBottom: 6 },
  sheetTitle: { fontFamily: F.semi, fontSize: 13, color: T.ink2, letterSpacing: 0.4 },
  sheetX: { width: 26, height: 26, borderRadius: 13, backgroundColor: "rgba(87,83,78,0.10)", alignItems: "center", justifyContent: "center" },
  sheetXTxt: { fontFamily: F.semi, fontSize: 11, color: T.ink2 },
  optEta: { fontFamily: F.bold, fontSize: 15, color: T.ink, fontVariant: ["tabular-nums"] },
  stepsBox: {
    marginHorizontal: 10, marginBottom: 6, paddingHorizontal: 12, paddingVertical: 8,
    borderRadius: 12, backgroundColor: "rgba(87,83,78,0.06)",
    borderLeftWidth: 2, borderLeftColor: T.accent,
  },
  stepRow: { flexDirection: "row", alignItems: "flex-start", paddingVertical: 3 },
  stepDot: { width: 4, height: 4, borderRadius: 2, backgroundColor: T.accent, marginTop: 6, marginRight: 8 },
  stepTxt: { flex: 1, fontFamily: F.reg, fontSize: 12.5, color: T.ink },
  stepDist: { fontFamily: F.reg, fontSize: 11.5, color: T.ink3 },
  startBtn: {
    marginTop: 8, marginHorizontal: 10, paddingVertical: 13, borderRadius: 16,
    backgroundColor: T.accent, alignItems: "center",
  },
  startTxt: { fontFamily: F.semi, fontSize: 15, color: "#fff", letterSpacing: 0.6 },
  sheetFoot: { fontFamily: F.reg, fontSize: 10.5, color: T.ink3, marginTop: 8, marginBottom: 4, textAlign: "center", paddingHorizontal: 16 },
  navBanner: { position: "absolute", top: 60, left: 16, right: 16 },
  navBannerIn: { borderRadius: 16, overflow: "hidden", padding: 14 },
  navStep: { fontFamily: F.semi, fontSize: 16, color: T.ink },
  navSub: { fontFamily: F.reg, fontSize: 11.5, color: T.ink2, marginTop: 3 },
  navBar: { position: "absolute", bottom: 30, left: 16, right: 16 },
  navBarIn: { borderRadius: 16, overflow: "hidden", padding: 12, flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  navEta: { fontFamily: F.bold, fontSize: 18, color: T.ink, fontVariant: ["tabular-nums"] },
  navExit: { paddingVertical: 10, paddingHorizontal: 18, borderRadius: 12, backgroundColor: "rgba(178,58,48,0.12)" },
  navExitTxt: { fontFamily: F.semi, fontSize: 13, color: T.doseHigh ?? "#b23a30" },
  introScrim: {
    position: "absolute", top: 0, bottom: 0, left: 0, right: 0,
    backgroundColor: "rgba(247,246,243,0.94)", alignItems: "center", justifyContent: "center",
  },
  introCard: { width: 290, alignItems: "center" },
  introTitle: { fontFamily: F.semi, fontSize: 26, color: T.accent, letterSpacing: -0.5 },
  introBody: { fontFamily: F.reg, fontSize: 14, color: T.ink2, textAlign: "center", marginTop: 14, lineHeight: 21 },
  introCta: { fontFamily: F.med, fontSize: 12, color: T.ink3, marginTop: 20 },
  whyTxt: { fontFamily: F.reg, fontSize: 11.5, color: T.ink2, marginTop: 5, textAlign: "center", lineHeight: 16 },
});
