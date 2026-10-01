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
import {
  Camera,
  GeoJSONSource,
  Layer,
  Map,
  type CameraRef,
} from "@maplibre/maplibre-react-native";

// EXPO_PUBLIC_API_URL overrides (e.g. deployed backend or LAN IP for a real
// device); otherwise the Android emulator reaches the host via 10.0.2.2.
const API =
  process.env.EXPO_PUBLIC_API_URL ??
  Platform.select({
    android: "http://10.0.2.2:8000",
    default: "http://localhost:8000",
  });

const STYLE_URL = "https://tiles.openfreemap.org/styles/positron";
const DELHI: [number, number] = [77.209, 28.6139];

type Place = { name: string; subtitle: string; lat: number; lon: number };
type Which = "from" | "to";
type Exposure = {
  dose_ug: number | null;
  avg_conc_ugm3: number | null;
  peak_conc?: number | null;
  confidence: "high" | "medium" | "low" | "none";
  coverage?: number;
  factors?: { microenv: number; ventilation_lpm: number; road_uplift: number };
  dose_vs_best_pct?: number;
  ug_saved_vs_worst?: number;
};
type CompareOption = {
  vehicle: string;
  label: string;
  distance_km: number;
  duration_min: number;
  duration_model?: "osrm" | "estimated";
  geometry: GeoJSON.Geometry;
  stations?: { board: string; alight: string };
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
  lat: number;
  lon: number;
};

const doseColor = (avg: number | null | undefined) =>
  avg == null ? "#0d9488" : avg < 60 ? "#0d9488" : avg < 130 ? "#d97706" : "#dc2626";

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
  const [loadingRoute, setLoadingRoute] = useState(false);
  const [apiOk, setApiOk] = useState<boolean | null>(null);
  const debounce = useRef<ReturnType<typeof setTimeout> | null>(null);
  const searchSeq = useRef(0);

  useEffect(() => {
    fetch(`${API}/health`)
      .then((r) => setApiOk(r.ok))
      .catch(() => setApiOk(false));
  }, []);

  const doSearch = useCallback((text: string) => {
    if (debounce.current) clearTimeout(debounce.current);
    if (text.trim().length < 2) {
      setResults([]);
      setSearching(false);
      return;
    }
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
      if (active === "from") {
        setFrom(p);
        setFromText(p.name);
      } else if (active === "to") {
        setTo(p);
        setToText(p.name);
      }
      setActive(null);
      setResults([]);
      Keyboard.dismiss();
      camRef.current?.flyTo({ center: [p.lon, p.lat], zoom: 14, duration: 900 });
    },
    [active]
  );

  const swap = useCallback(() => {
    const f = from;
    const ft = fromText;
    setFrom(to);
    setFromText(toText);
    setTo(f ?? null);
    setToText(ft);
  }, [from, to, fromText, toText]);

  // every travel mode, scored live for the same trip — the dose engine
  useEffect(() => {
    if (!from || !to) return;
    let cancelled = false;
    const load = async () => {
      setLoadingRoute(true);
      try {
        const qs = `from_lat=${from.lat}&from_lon=${from.lon}&to_lat=${to.lat}&to_lon=${to.lon}`;
        const [cr, dr] = await Promise.all([
          fetch(`${API}/compare?${qs}`),
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
            { padding: { top: 230, bottom: 280, left: 60, right: 60 }, duration: 700 }
          );
        }
      } catch {
        if (!cancelled) {
          setOptions([]);
          setDepart(null);
        }
      } finally {
        if (!cancelled) setLoadingRoute(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [from, to]);

  const routeFeature = useMemo<GeoJSON.Feature | null>(() => {
    const g = options[selected]?.geometry;
    if (!g) return null;
    return { type: "Feature", properties: {}, geometry: g };
  }, [options, selected]);

  const markers = useMemo<GeoJSON.FeatureCollection>(() => {
    const feats: GeoJSON.Feature[] = [];
    if (from)
      feats.push({
        type: "Feature",
        properties: { kind: "from" },
        geometry: { type: "Point", coordinates: [from.lon, from.lat] },
      });
    if (to)
      feats.push({
        type: "Feature",
        properties: { kind: "to" },
        geometry: { type: "Point", coordinates: [to.lon, to.lat] },
      });
    return { type: "FeatureCollection", features: feats };
  }, [from, to]);

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
              setFieldRead({ pm25: j.pm25, pm10: j.pm10, nearest_sample_km: j.nearest_sample_km, lat: c[1], lon: c[0] });
          } catch {}
        }}
      >
        <Camera
          ref={camRef}
          initialViewState={{ center: DELHI, zoom: 11 }}
          maxBounds={[76.75, 28.15, 77.95, 28.98]}
        />
        <GeoJSONSource id="route" data={routeFeature ?? { type: "FeatureCollection", features: [] }}>
          <Layer
            id="route-casing"
            type="line"
            paint={{ "line-color": "#0f766e", "line-width": 7, "line-opacity": 0.22 }}
            layout={{ "line-cap": "round", "line-join": "round" }}
          />
          <Layer
            id="route-line"
            type="line"
            paint={{ "line-color": "#0d9488", "line-width": 4 }}
            layout={{ "line-cap": "round", "line-join": "round" }}
          />
        </GeoJSONSource>
        <GeoJSONSource id="markers" data={markers}>
          <Layer
            id="endpoint"
            type="circle"
            paint={{
              "circle-radius": 8,
              "circle-color": ["match", ["get", "kind"], "from", "#0d9488", "#e11d48"],
              "circle-stroke-width": 3,
              "circle-stroke-color": "#ffffff",
            }}
          />
        </GeoJSONSource>
      </Map>

      {/* search card */}
      <View style={s.cardWrap}>
        <BlurView intensity={60} tint="light" style={s.card}>
          <View style={s.row}>
            <View style={[s.dot, { backgroundColor: "#0d9488" }]} />
            <TextInput
              style={s.input}
              placeholder="From — anywhere in Delhi NCR"
              placeholderTextColor="#94a3b8"
              autoCorrect={false}
              autoCapitalize="none"
              value={fromText}
              onFocus={() => setActive("from")}
              onChangeText={(t) => {
                setFromText(t);
                setFrom(null);
                setOptions([]);
                setDepart(null);
                setActive("from");
                doSearch(t);
              }}
              returnKeyType="search"
              clearButtonMode="while-editing"
            />
            <Pressable onPress={swap} style={s.swap} hitSlop={8}>
              <Text style={s.swapTxt}>⇅</Text>
            </Pressable>
          </View>
          <View style={s.div} />
          <View style={s.row}>
            <View style={[s.dot, { backgroundColor: "#e11d48" }]} />
            <TextInput
              style={s.input}
              placeholder="To — anywhere in Delhi NCR"
              placeholderTextColor="#94a3b8"
              autoCorrect={false}
              autoCapitalize="none"
              value={toText}
              onFocus={() => setActive("to")}
              onChangeText={(t) => {
                setToText(t);
                setTo(null);
                setOptions([]);
                setDepart(null);
                setActive("to");
                doSearch(t);
              }}
              returnKeyType="search"
              clearButtonMode="while-editing"
            />
            {searching && <ActivityIndicator size="small" color="#64748b" />}
          </View>
        </BlurView>

        {active && results.length > 0 && (
          <BlurView intensity={70} tint="light" style={[s.card, { marginTop: 8 }]}>
            {results.map((p, i) => (
              <Pressable
                key={`${p.lat},${p.lon},${i}`}
                onPress={() => pick(p)}
                style={({ pressed }) => [s.result, pressed && { opacity: 0.6 }]}
              >
                <Text style={s.pin}>◉</Text>
                <View style={{ flex: 1 }}>
                  <Text style={s.rname} numberOfLines={1}>{p.name}</Text>
                  {!!p.subtitle && (
                    <Text style={s.rsub} numberOfLines={1}>{p.subtitle}</Text>
                  )}
                </View>
              </Pressable>
            ))}
          </BlurView>
        )}
      </View>

      {/* status chip */}
      <View style={s.statusWrap} pointerEvents="none">
        <View style={s.statusChip}>
          <View
            style={[
              s.statusDot,
              { backgroundColor: apiOk === null ? "#f59e0b" : apiOk ? "#22c55e" : "#ef4444" },
            ]}
          />
          <Text style={s.statusTxt}>
            {apiOk === null ? "connecting" : apiOk ? "live Delhi data" : "server offline"}
          </Text>
        </View>
      </View>

      {/* tapped-point field readout */}
      {fieldRead && (
        <View style={s.fieldWrap} pointerEvents="box-none">
          <Pressable onPress={() => setFieldRead(null)} style={s.fieldChip}>
            <Text style={[s.fieldDose, { color: doseColor(fieldRead.pm25) }]}>
              {Math.round(fieldRead.pm25)} µg/m³
            </Text>
            <Text style={s.fieldMeta}>
              PM2.5 here · live field
              {fieldRead.nearest_sample_km != null
                ? ` · nearest sample ${fieldRead.nearest_sample_km} km`
                : ""}
            </Text>
          </Pressable>
        </View>
      )}

      {/* dose ranking — every mode, what you actually breathe */}
      {(from && to) && (
        <View style={s.bottomWrap}>
          <BlurView intensity={60} tint="light" style={s.summary}>
            {loadingRoute ? (
              <ActivityIndicator size="small" color="#0f766e" />
            ) : options.length > 0 ? (
              <View>
                <ScrollView style={{ maxHeight: 236 }} showsVerticalScrollIndicator={false}>
                {options.map((o, i) => (
                  <Pressable
                    key={o.vehicle}
                    onPress={() => setSelected(i)}
                    style={[s.optRow, i === selected && s.optRowSel]}
                  >
                    <View style={{ flex: 1 }}>
                      <Text style={s.optLabel}>
                        {o.label}
                        {i === 0 ? "  · breathes least" : ""}
                      </Text>
                      <Text style={s.optMeta}>
                        {o.duration_min} min · {o.distance_km} km
                        {o.exposure?.confidence ? ` · ${o.exposure.confidence}` : ""}
                      </Text>
                      {o.stations ? (
                        <Text style={s.optMeta}>
                          {o.stations.board} → {o.stations.alight}
                        </Text>
                      ) : null}
                    </View>
                    <Text style={[s.optDose, { color: doseColor(o.exposure?.avg_conc_ugm3) }]}>
                      {o.exposure?.dose_ug != null ? `${o.exposure.dose_ug} µg` : "—"}
                    </Text>
                  </Pressable>
                ))}
                </ScrollView>
                {depart?.ug_saved_vs_now != null && depart.ug_saved_vs_now > 10 && (
                  <Text style={s.departHint}>
                    leave {hourLabel(depart.best.start, depart.best.hours_ahead)} — same trip,{" "}
                    {depart.ug_saved_vs_now}% less PM2.5
                  </Text>
                )}
                <Pressable onPress={() => setShowWhy((v) => !v)}>
                  <Text style={s.summarySub}>
                    inhaled PM2.5 · live Delhi field · {showWhy ? "hide why" : "why?"}
                  </Text>
                </Pressable>
                {showWhy && options[selected]?.exposure && (
                  <Text style={s.whyTxt}>
                    {options[selected].label}: breathing-zone ≈ ambient ×{" "}
                    {options[selected].exposure.factors?.microenv ?? "?"} · breathing{" "}
                    {options[selected].exposure.factors?.ventilation_lpm ?? "?"} L/min
                    {options[selected].exposure.peak_conc != null
                      ? ` · peak ${options[selected].exposure.peak_conc} µg/m³`
                      : ""}
                    {options[selected].exposure.coverage != null
                      ? ` · ${Math.round(options[selected].exposure.coverage * 100)}% of trip covered by field`
                      : ""}
                  </Text>
                )}
              </View>
            ) : (
              <Text style={s.summarySub}>no route found</Text>
            )}
          </BlurView>
        </View>
      )}
    </View>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#f1f5f9" },
  cardWrap: {
    position: "absolute",
    top: Platform.select({ ios: 60, android: 40 }),
    left: 16,
    right: 16,
  },
  card: {
    borderRadius: 22,
    overflow: "hidden",
    backgroundColor: "rgba(255,255,255,0.55)",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(15,23,42,0.08)",
  },
  row: { flexDirection: "row", alignItems: "center", paddingHorizontal: 16, paddingVertical: 13 },
  dot: { width: 10, height: 10, borderRadius: 5, marginRight: 12 },
  input: { flex: 1, fontSize: 16, color: "#0f172a", padding: 0 },
  swap: { marginLeft: 8, padding: 4 },
  swapTxt: { fontSize: 17, color: "#64748b" },
  div: { height: StyleSheet.hairlineWidth, backgroundColor: "rgba(15,23,42,0.12)", marginHorizontal: 16 },
  result: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingVertical: 11,
    gap: 10,
  },
  pin: { color: "#0d9488", fontSize: 13 },
  rname: { fontSize: 15, fontWeight: "600", color: "#0f172a" },
  rsub: { fontSize: 12, color: "#64748b", marginTop: 1 },
  statusWrap: { position: "absolute", top: Platform.select({ ios: 108, android: 88 }), alignSelf: "center" },
  statusChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: "rgba(255,255,255,0.8)",
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 999,
  },
  statusDot: { width: 7, height: 7, borderRadius: 4 },
  statusTxt: { fontSize: 11, color: "#475569", fontWeight: "600", letterSpacing: 0.2 },
  bottomWrap: { position: "absolute", bottom: 34, left: 16, right: 16, gap: 10 },
  chipRow: {
    flexDirection: "row",
    borderRadius: 999,
    overflow: "hidden",
    backgroundColor: "rgba(255,255,255,0.55)",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(15,23,42,0.08)",
    padding: 4,
  },
  mchip: { flex: 1, paddingVertical: 9, borderRadius: 999, alignItems: "center" },
  mchipOn: { backgroundColor: "#0f172a" },
  mchipTxt: { fontSize: 13, fontWeight: "600", color: "#475569" },
  mchipTxtOn: { color: "#fff" },
  summary: {
    borderRadius: 20,
    overflow: "hidden",
    backgroundColor: "rgba(255,255,255,0.6)",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(15,23,42,0.08)",
    paddingVertical: 14,
    paddingHorizontal: 16,
  },
  optRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 8,
    paddingHorizontal: 8,
    borderRadius: 12,
  },
  optRowSel: { backgroundColor: "rgba(13,148,136,0.10)" },
  optLabel: { fontSize: 14, fontWeight: "600", color: "#0f172a" },
  optMeta: { fontSize: 11, color: "#64748b", marginTop: 1 },
  optDose: { fontSize: 16, fontWeight: "800", fontVariant: ["tabular-nums"] },
  departHint: {
    fontSize: 13,
    fontWeight: "700",
    color: "#0f766e",
    textAlign: "center",
    marginTop: 8,
    paddingTop: 8,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: "rgba(15,23,42,0.10)",
  },
  summaryMain: { fontSize: 20, fontWeight: "700", color: "#0f172a", fontVariant: ["tabular-nums"] },
  dose: { fontSize: 16, fontWeight: "800", marginTop: 3, fontVariant: ["tabular-nums"] },
  summarySub: { fontSize: 12, color: "#64748b", marginTop: 8, textAlign: "center" },
  whyTxt: { fontSize: 11.5, color: "#475569", marginTop: 4, textAlign: "center", lineHeight: 16 },
  fieldWrap: {
    position: "absolute",
    bottom: 110,
    alignSelf: "center",
  },
  fieldChip: {
    alignItems: "center",
    backgroundColor: "rgba(255,255,255,0.85)",
    paddingHorizontal: 18,
    paddingVertical: 10,
    borderRadius: 18,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(15,23,42,0.10)",
  },
  fieldDose: { fontSize: 22, fontWeight: "800", fontVariant: ["tabular-nums"] },
  fieldMeta: { fontSize: 11, color: "#64748b", marginTop: 2 },
});
