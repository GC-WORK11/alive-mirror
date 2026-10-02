import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Keyboard,
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
import {
  Camera,
  GeoJSONSource,
  Layer,
  Map,
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

export default function App() {
  const camRef = useRef<CameraRef>(null);
  const [from, setFrom] = useState<Place | null>(null);
  const [to, setTo] = useState<Place | null>(null);
  const [fromText, setFromText] = useState("");
  const [toText, setToText] = useState("");
  const [active, setActive] = useState<Which | null>(null);
  const [results, setResults] = useState<Place[]>([]);
  const [searching, setSearching] = useState(false);
  const [options, setOptions] = useState<CompareOption[]>([]);
  const [selected, setSelected] = useState(0);
  const [depart, setDepart] = useState<Depart>(null);
  const [showWhy, setShowWhy] = useState(false);
  const [fieldRead, setFieldRead] = useState<FieldRead | null>(null);
  const [grid, setGrid] = useState<GeoJSON.FeatureCollection | null>(null);
  const [horizonH, setHorizonH] = useState(0);
  const [trips, setTrips] = useState<Awaited<ReturnType<typeof loadTrips>>>([]);
  const [community, setCommunity] = useState<CommunityTotals | null>(null);
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
    const poll = () => fetch(`${API}/reports`).then((r) => r.json()).then(setReports).catch(() => {});
    poll();
    const iv = setInterval(poll, 60000);
    loadTrips().then((t) => { setTrips(t); setLedger(ledgerStats(t)); }).catch(() => {});
    Location.requestForegroundPermissionsAsync().then((r) => setHasLoc(r.granted)).catch(() => {});
    return () => clearInterval(iv);
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

  const doSearch = useCallback((text: string) => {
    if (debounce.current) clearTimeout(debounce.current);
    if (text.trim().length < 2) { setResults([]); setSearching(false); return; }
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
      if (active === "from") { setFrom(p); setFromText(p.name); }
      else if (active === "to") { setTo(p); setToText(p.name); }
      setActive(null);
      setResults([]);
      Keyboard.dismiss();
      camRef.current?.flyTo({ center: [p.lon, p.lat], zoom: 14, duration: 900 });
    },
    [active]
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
      const ok = g && (g.type === "LineString" || g.type === "MultiLineString");
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

  // faint alternates — every other option's path under the selected one
  const altSegs = useMemo<GeoJSON.FeatureCollection>(() => ({
    type: "FeatureCollection",
    features: options
      .map((o, i) => ({ o, i }))
      .filter(({ o, i }) => i !== selected && o.geometry?.type === "LineString")
      .map(({ o }) => ({ type: "Feature" as const, properties: {}, geometry: o.geometry })),
  }), [options, selected]);

  const markers = useMemo<GeoJSON.FeatureCollection>(() => {
    const feats: GeoJSON.Feature[] = [];
    if (from) feats.push({ type: "Feature", properties: { kind: "from" }, geometry: { type: "Point", coordinates: [from.lon, from.lat] } });
    if (to) feats.push({ type: "Feature", properties: { kind: "to" }, geometry: { type: "Point", coordinates: [to.lon, to.lat] } });
    return { type: "FeatureCollection", features: feats };
  }, [from, to]);

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
        <GeoJSONSource id="markers" data={markers}>
          <Layer id="endpoint" type="circle" paint={{
            "circle-radius": 7,
            "circle-color": ["match", ["get", "kind"], "from", T.accent, T.doseMid],
            "circle-stroke-width": 2.5, "circle-stroke-color": "#ffffff",
          }} />
        </GeoJSONSource>
      </Map>

      {/* search card */}
      <View style={s.cardWrap}>
        <BlurView intensity={45} tint="light" style={s.card}>
          <View style={s.row}>
            <Text style={s.rowGlyph}>A</Text>
            <TextInput style={s.input} placeholder="From — anywhere in Delhi NCR"
              placeholderTextColor={T.ink3} autoCorrect={false} autoCapitalize="none"
              value={fromText}
              onFocus={() => setActive("from")}
              onChangeText={(t) => { setFromText(t); setFrom(null); setOptions([]); setDepart(null); setActive("from"); doSearch(t); }}
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
              onChangeText={(t) => { setToText(t); setTo(null); setOptions([]); setDepart(null); setActive("to"); doSearch(t); }}
              returnKeyType="search" clearButtonMode="while-editing" />
            {searching && <ActivityIndicator size="small" color={T.ink3} />}
          </View>
        </BlurView>

        {active && results.length > 0 && (
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
      </View>

      {/* horizon scrubber — now / +6h / +12h / +24h; hidden while a field is focused */}
      {!active && (
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
      {!active && (
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

      {/* action column: recenter + air report */}
      {!active && !drawerOpen && (
        <View style={s.fabCol}>
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
        <View style={s.reportCard}>
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

      {/* dose ranking */}
      {from && to && (
        <View style={s.bottomWrap}>
          <BlurView intensity={45} tint="light" style={s.summary}>
            {loadingRoute ? (
              <ActivityIndicator size="small" color={T.accent} />
            ) : options.length > 0 ? (
              <View>
                <ScrollView style={{ maxHeight: 246 }} showsVerticalScrollIndicator={false}>
                  {options.map((o, i) => (
                    <Pressable key={`${o.vehicle}-${i}`} onPress={() => setSelected(i)}
                      style={({ pressed }) => [s.optRow, i === selected && s.optRowSel, pressed && s.chipPressed]}>
                      <View style={{ flex: 1 }}>
                        <Text style={s.optLabel}>
                          {o.label}
                          {i === 0 ? <Text style={s.bestTag}>  recommended</Text> : null}
                        </Text>
                        {o.decision_reasons?.length ? (
                          <Text style={s.optReason}>{o.decision_reasons.join(" · ")}</Text>
                        ) : null}
                        <Text style={s.optMeta}>
                          {o.duration_min} min · {o.distance_km} km
                          {o.exposure?.confidence ? ` · ${o.exposure.confidence}` : ""}
                          {o.hotspots?.[0]?.share_pct && o.hotspots[0].share_pct > 30
                            ? ` · ${o.hotspots[0].share_pct}% in one stretch` : ""}
                        </Text>
                        {o.stations ? (
                          <Text style={s.optMeta}>{o.stations.board} → {o.stations.alight}</Text>
                        ) : null}
                      </View>
                      <Text style={[s.optDose, { color: doseColor(o.exposure?.avg_conc_ugm3) }]}>
                        {o.exposure?.dose_ug != null ? `${o.exposure.dose_ug} µg` : "—"}
                      </Text>
                    </Pressable>
                  ))}
                </ScrollView>
                {options[selected] && (
                  <Text style={s.arriveTxt}>
                    arrives ~{arrivalLabel(options[selected].duration_min)} by {options[selected].label}
                  </Text>
                )}
                {depart?.ug_saved_vs_now != null && depart.ug_saved_vs_now > 10 && (
                  <View style={s.departRow}>
                    <Text style={s.departHint}>
                      leave {hourLabel(depart.best.start, depart.best.hours_ahead)} — same trip, {depart.ug_saved_vs_now}% less PM2.5
                    </Text>
                    <Pressable onPress={remind} hitSlop={6}>
                      <Text style={s.remindTxt}>{notified ? "set ✓" : "remind me"}</Text>
                    </Pressable>
                  </View>
                )}
                <Pressable onPress={() => setShowWhy((v) => !v)}>
                  <Text style={s.summarySub}>
                    inhaled PM2.5 · measured field {showWhy ? "· hide" : "· why?"}
                  </Text>
                </Pressable>
                {showWhy && options[selected]?.exposure && (
                  <Text style={s.whyTxt}>
                    {options[selected].label}: breathing-zone ≈ ambient ×{" "}
                    {options[selected].exposure.factors?.microenv ?? "?"} · breathing{" "}
                    {options[selected].exposure.factors?.ventilation_lpm ?? "?"} L/min
                    {options[selected].exposure.peak_conc != null ? ` · peak ${options[selected].exposure.peak_conc} µg/m³` : ""}
                    {options[selected].exposure.coverage != null ? ` · ${Math.round(options[selected].exposure.coverage * 100)}% of trip covered` : ""}
                  </Text>
                )}
              </View>
            ) : (
              <Text style={s.summarySub}>no route found</Text>
            )}
          </BlurView>
        </View>
      )}

      {showLedger && (
        <LedgerSheet stats={ledger} curve={curve} hourNow={curveHour}
          onClose={() => setShowLedger(false)} />
      )}

      {drawerOpen && (
        <JourneyDrawer week={weekStats(trips)} stats={ledger}
          community={community} onClose={() => setDrawerOpen(false)} />
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
  whyTxt: { fontFamily: F.reg, fontSize: 11.5, color: T.ink2, marginTop: 5, textAlign: "center", lineHeight: 16 },
});
